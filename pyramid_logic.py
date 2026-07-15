"""Weinstein Commander — Pyramid / Trim Manager (shared logic).

Single source of truth for the Pyramid/Trim page, called from TWO places:
  • weinstein_commander_web_v4.0.py  → inline page  (elif page == 'PYRAMID')
  • pages/5_pyramid.py               → standalone Streamlit page

Five-rung ladder (2026-07, Jay + Gemini) — best-of-each logic, RRG is a
SELECTION tool, never a forced exit:
  • EXIT   (full, 100%)  = structure/thesis/risk broken — price-structure break
      (positional close < 30-WMA / swing close < swing-low), Stage 4, Chandelier
      stop-out (catalyst-aware trail via risk_common — SAME as Risk Shield), at
      journal SL with P&L≤0, thesis underwater (≤ −8%), or dead-money time-stop.
  • TRIM   (partial)     = harvest a WINNER, trend intact — R-multiple ladder
      (≥2R book ⅓, ≥3R book ½), target hit, over-extension (≥4×ATR over 20-EMA),
      or earnings within 3 days.
  • REDUCE (soft)        = RS deterioration / decay (RRG LAGGING, < 50-DMA, low
      score) → tighten stop & don't pyramid; NOT a sell.
  • ADD                  = a leader (RRG LEADING/WEAKENING + Score + winning) AT
      a good location (pullback to 20-EMA, above rising 200-DMA, not extended).
  • HOLD                 = everything else.
Triggers drawn from Pyramid/Trim (price-structure, REDUCE), Risk Shield
(pullback-location, time-stop, earnings) and the Exit Signal Engine (R-ladder).
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

import bull_screener as bs
import data_provider as dp
import risk_common as rc   # shared Chandelier / trail logic (synced with Risk Shield)

_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(_DIR, "trade_journal_v6.db")
BENCH   = "^CRSLDX"
ATR_LEN = 14


# ── Data helpers ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_open_positions(db_path: str = DB_FILE) -> pd.DataFrame:
    """Load all open positions from the trade journal (status stored UPPER-case)."""
    if not os.path.exists(db_path):
        return pd.DataFrame()
    con = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            # Case-insensitive: dhan_journal_v7 stores status as 'OPEN'; a plain
            # status='open' matched nothing (SQLite = is case-sensitive).
            "SELECT id, symbol, entry_date, buy_price, quantity, stoploss, "
            "target, sector, trade_type, timeframe, setup, status "
            "FROM journal WHERE UPPER(status) = 'OPEN'",
            con,
        )
    finally:
        con.close()
    if df.empty:
        return df
    df["entry_date"] = pd.to_datetime(df["entry_date"], errors="coerce")
    df["days_held"]  = (pd.Timestamp.now().normalize() - df["entry_date"]).dt.days
    df["buy_price"]  = pd.to_numeric(df["buy_price"], errors="coerce")
    df["stoploss"]   = pd.to_numeric(df["stoploss"], errors="coerce")
    df["quantity"]   = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["target"]     = pd.to_numeric(df["target"], errors="coerce")   # for TRIM target-hit
    return df


@st.cache_data(ttl=300, show_spinner=False)
def fetch_bench_weekly() -> pd.DataFrame:
    """Fetch + tail-extend ^CRSLDX weekly (same fix as bull_screener.py v1.5)."""
    df_w = bs._flatten_cols(dp.fetch_ohlcv(BENCH, period="3y", interval="1wk"))
    df_d = bs._flatten_cols(dp.fetch_ohlcv(BENCH, period="2y", interval="1d"))
    if not df_d.empty:
        res = df_d.resample("W-MON", closed="left", label="left").agg({
            "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
        }).dropna(subset=["Close"])
        if not res.empty and not df_w.empty:
            extra = res[res.index > df_w.index[-1]]
            if not extra.empty:
                df_w = pd.concat([df_w, extra])
    return df_w


def fetch_symbol_full(symbol: str, df_bench_w: pd.DataFrame,
                      setup: str = "", bear: bool = False, swing=None) -> dict:
    """Full bull_screener per-symbol record + LTP/ATR + price-structure exit
    levels (50-DMA, 30-WMA, swing low) + catalyst-aware Chandelier trail.
    ``setup`` (journal setup) + ``bear`` (regime) drive the Chandelier multiplier;
    ``swing`` (journal trade_type: True/False/None) drives the trade-type-aware
    trail window (14 swing / 22 positional) — all via the shared risk_common
    helper, kept in sync with the Risk Shield page. Empty dict on failure."""
    try:
        rec = bs.screen_symbol(symbol, df_bench_w, force_output=True, mkt_bull=True)
    except Exception:
        rec = None
    if rec is None:
        return {}

    try:
        yf_sym = bs.to_yf(symbol)
        df_d = bs._flatten_cols(dp.fetch_ohlcv(yf_sym, period="1y", interval="1d"))
    except Exception:
        df_d = pd.DataFrame()

    ltp = float(df_d["Close"].iloc[-1]) if not df_d.empty else np.nan
    atr14 = dma50 = swing_low = ema20 = sma200 = sma200_slope = close_5d_ago = np.nan
    if not df_d.empty and len(df_d) >= ATR_LEN + 1:
        try:
            h, l, c = df_d["High"], df_d["Low"], df_d["Close"]
            tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
            atr14 = float(tr.rolling(ATR_LEN).mean().iloc[-1])
            ema20 = float(c.ewm(span=20, adjust=False).mean().iloc[-1])   # 20-EMA (ADD location + over-extension)
            if len(c) >= 50:
                dma50 = float(c.rolling(50).mean().iloc[-1])          # 50-DMA (positional warning)
            if len(l) >= 11:
                swing_low = float(l.iloc[-11:-1].min())               # recent swing low (swing exit)
            if len(c) >= 6:
                close_5d_ago = float(c.iloc[-6])                      # 5 sessions ago (pullback gate)
            if len(c) >= 200:
                _s200 = c.rolling(200).mean()                        # 200-DMA + slope (ADD trend gate)
                sma200 = float(_s200.iloc[-1])
                if len(_s200) >= 11 and _s200.iloc[-11] and not np.isnan(_s200.iloc[-11]):
                    sma200_slope = float((_s200.iloc[-1] - _s200.iloc[-11]) / _s200.iloc[-11] * 100)
        except Exception:
            pass

    wma30 = np.nan
    try:
        df_w = bs._flatten_cols(dp.fetch_ohlcv(yf_sym, period="3y", interval="1wk"))
        if not df_w.empty and len(df_w) >= 30:
            wma30 = float(df_w["Close"].rolling(30).mean().iloc[-1])  # 30-WMA (positional exit)
    except Exception:
        pass

    # Catalyst-aware CHANDELIER trail — SAME helper Risk Shield uses (risk_common),
    # so a Chandelier stop-out reads identically on both screens. cap_protect /
    # custom-mult are Risk-Shield operational overrides not applied on this review
    # screen (documented divergence). above200 derived from live price vs 200-DMA.
    chandelier = np.nan
    try:
        _n = rc.trail_window_for(setup, swing)     # 14 swing / 22 positional
        if not df_d.empty and len(df_d) >= _n:
            _above200 = bool(_numok(sma200) and _numok(ltp) and ltp > sma200)
            _ce, _cem, _ces = rc.chandelier_exit(
                df_d["High"], df_d["Low"], df_d["Close"],
                setup=setup, bear=bear, above200=_above200, swing=swing)
            if _ce is not None:
                chandelier = float(_ce)
    except Exception:
        pass

    # days_to_earnings — best-effort (guarded; None if no source). Feeds the
    # TRIM "de-risk into a binary event" trigger, matching Risk Shield.
    days_to_earnings = None
    try:
        import yfinance as _yf
        _cal = _yf.Ticker(yf_sym).calendar
        _edate = None
        if isinstance(_cal, dict):
            _ev = _cal.get("Earnings Date")
            _edate = (_ev[0] if isinstance(_ev, (list, tuple)) and _ev else _ev)
        elif _cal is not None and hasattr(_cal, "loc") and "Earnings Date" in getattr(_cal, "index", []):
            _edate = _cal.loc["Earnings Date"].iloc[0]
        if _edate is not None:
            _d = (pd.Timestamp(_edate).normalize() - pd.Timestamp.now().normalize()).days
            if _d >= 0:
                days_to_earnings = int(_d)
    except Exception:
        days_to_earnings = None

    return {
        "ltp": ltp, "atr14": atr14, "dma50": dma50, "wma30": wma30, "swing_low": swing_low,
        "ema20": ema20, "sma200": sma200, "sma200_slope": sma200_slope,
        "close_5d_ago": close_5d_ago, "days_to_earnings": days_to_earnings,
        "chandelier": chandelier,
        "score_100pt":    int(rec.get("Score", 0)),
        "catalyst":       rec.get("Catalyst", "None"),
        "stage":          int(rec.get("Stage", 0)),
        "rrg_quadrant":   rec.get("RRG_Quadrant", "n/a"),
        "rrg_next":       rec.get("RRG_Next", "n/a"),
        "rrg_trajectory": rec.get("RRG_Trajectory", "n/a"),
        "rrg_arrow":      rec.get("RRG_Arrow", "•"),
        "rrg_score":      int(rec.get("RRG_Score", 0)),
        "rrg_tradeable":  bool(rec.get("RRG_Tradeable", False)),
        "rs_ratio":       float(rec.get("JdK_RS_Ratio", 100.0)),
        "rs_momentum":    float(rec.get("JdK_RS_Momentum", 100.0)),
        "rel_vol":        float(rec.get("Rel_Vol", 0.0) or 0.0),
        "rsi14":          float(rec.get("RSI", 0.0) or 0.0),
        "vcp_valid":      bool(rec.get("VCP_Valid", False)),
    }


def swing_from_trade_type(tt) -> bool | None:
    """Journal trade_type → swing flag for the trail window: 'swing'→True,
    'pos…'→False, blank/unknown→None (risk_common then senses from the setup
    prefix, else defaults positional)."""
    t = str(tt or "").lower()
    if "swing" in t:
        return True
    if "pos" in t:
        return False
    return None


def _numok(x) -> bool:
    """True for a real number (not None / NaN)."""
    return bool(pd.notna(x))


# ── Tunable constants for the ladder ──────────────────────────────────────────
EXT_ATR_MULT  = 4.0     # over-extension: ltp this many ATRs above the 20-EMA = climactic
# Time-stop ("dead money") — aligned to Jay's DNA holding windows, NOT Risk
# Shield's aggressive 10d/42d: swing = 8-12 weeks (~60 trading days), positional
# = 6-8 months (~180). Only flags a position that has languished PAST its
# expected window still making no progress (< TIME_STOP_R).
SWING_DAYS    = 60
POS_DAYS      = 180
TIME_STOP_R   = 0.5
MIN_RISK_FRAC = 0.005   # R is meaningful only if (buy − stop) ≥ 0.5% of price;
                        # a stop trailed to ~breakeven makes R explode — treat as N/A.


def classify(row: dict) -> tuple[str, str]:
    """Return (classification, trigger_reason). ∈ {ADD, TRIM, REDUCE, EXIT, HOLD}.

    Five-rung ladder, best-of-each logic (2026-07):
      EXIT  (full)   — structure/thesis/risk broken (price-structure, Stage 4,
                       at-SL, ≤−8%, dead-money time-stop). trade_type-aware.
      TRIM  (partial)— trend intact, harvest/de-risk (R-multiple ladder, target
                       hit, over-extension, earnings-soon). Winners only.
      REDUCE (soft)  — RS/decay warning, price intact (RRG LAGGING, <50-DMA,
                       score decay) → tighten stop & don't add. NOT a sell.
      ADD            — leader (RRG+Score+winning) AND good location (pullback to
                       EMA20, not extended, rising 200-DMA).
      HOLD           — everything else.
    RRG is SELECTION-only; it never forces an exit (that caused over-cycling).
    """
    quad   = row.get("rrg_quadrant", "n/a")
    score  = int(row.get("score_100pt", 0) or 0)
    stage  = int(row.get("stage", 0) or 0)
    catal  = row.get("catalyst", "None")
    pnl    = row.get("pnl_pct", 0.0)
    ltp    = row.get("ltp", np.nan)
    buy    = row.get("buy_price", np.nan)
    sl     = row.get("stoploss", np.nan)
    tgt    = row.get("target", np.nan)
    atr14  = row.get("atr14", np.nan)
    dma50  = row.get("dma50", np.nan)
    wma30  = row.get("wma30", np.nan)
    swing_low = row.get("swing_low", np.nan)
    ema20  = row.get("ema20", np.nan)
    sma200 = row.get("sma200", np.nan)
    sma200_slope = row.get("sma200_slope", np.nan)
    c5     = row.get("close_5d_ago", np.nan)
    d2e    = row.get("days_to_earnings", None)
    days_held = row.get("days_held", None)
    # Journal `timeframe` (Positional/Swing) is the horizon field; trade_type is the
    # DIRECTION (LONG) and never matched — the old parse silently defaulted
    # everything to positional (audit finding, 14-Jul-2026).
    tt     = str(row.get("timeframe", "") or row.get("trade_type", "") or "").lower()
    is_swing = "swing" in tt
    is_positional = ("pos" in tt) or (not is_swing)   # positional is the default (wider) structure

    # R-multiple from journal risk. Valid only when risk-per-share is meaningful
    # (≥ MIN_RISK_FRAC of price) — a stop at/near breakeven makes R explode.
    _risk_ps = (buy - sl) if (_numok(buy) and _numok(sl)) else np.nan
    R = ((ltp - buy) / _risk_ps) if (_numok(ltp) and _numok(_risk_ps) and _risk_ps >= MIN_RISK_FRAC * buy) else np.nan

    # ══ 1. EXIT (full, 100%) — structure / thesis / risk broken ══════════
    if _numok(ltp) and _numok(sl) and _numok(atr14) and atr14 > 0 and (ltp - sl) <= 1.5 * atr14 and pnl <= 0:
        return "EXIT", f"At SL: {(ltp-sl)/atr14:.1f}× ATR from stop, P&L {pnl:+.1f}% — exit"
    if pnl <= -8.0:
        return "EXIT", f"P&L {pnl:+.1f}% — thesis underwater, exit"
    if stage == 4:
        return "EXIT", "Stage 4 (declining) — trend broken, exit"
    if is_swing and _numok(swing_low) and _numok(ltp) and ltp < swing_low:
        return "EXIT", f"Closed below swing low ₹{swing_low:,.0f} — swing structure broken"
    if is_positional and _numok(wma30) and _numok(ltp) and ltp < wma30:
        return "EXIT", f"Closed below 30-WMA ₹{wma30:,.0f} — Stage-4 trigger"
    chandelier = row.get("chandelier", np.nan)
    if _numok(chandelier) and _numok(ltp) and ltp < chandelier:
        return "EXIT", f"Chandelier stop-out — price below trail ₹{chandelier:,.0f}"
    if days_held is not None and _numok(R):
        _lim = SWING_DAYS if is_swing else POS_DAYS
        if days_held >= _lim and R < TIME_STOP_R:
            return "EXIT", f"Time-stop: {int(days_held)}d held, only {R:.1f}R — dead money, exit"

    # ══ 2. TRIM (partial) — trend intact, harvest / de-risk (winners only) ══
    if pnl > 0:
        if _numok(R) and R >= 3.0:
            return "TRIM", f"At {R:.1f}R — book ½, trail the rest"
        if _numok(R) and R >= 2.0:
            return "TRIM", f"At {R:.1f}R — book ⅓, lock 0.5R on the rest"
        if _numok(tgt) and _numok(ltp) and ltp >= tgt:
            return "TRIM", f"Target ₹{tgt:,.0f} reached — book partial"
        if _numok(ema20) and _numok(atr14) and atr14 > 0 and (ltp - ema20) / atr14 >= EXT_ATR_MULT:
            return "TRIM", f"Over-extended {((ltp-ema20)/atr14):.1f}× ATR above 20-EMA — book into strength"
        if d2e is not None and d2e <= 3:
            return "TRIM", f"Earnings in {int(d2e)}d — trim into the event"

    # ══ 3. REDUCE (soft) — tighten stop / don't add — NOT a sell ═════════
    if quad == "LAGGING":
        return "REDUCE", "RS LAGGING vs N500 — tighten stop & don't pyramid (price still intact)"
    if is_positional and _numok(dma50) and _numok(ltp) and ltp < dma50:
        return "REDUCE", f"Below 50-DMA ₹{dma50:,.0f} — early warning; tighten stop toward 30-WMA"
    if score <= 25:
        return "REDUCE", f"Score {score} — setup/RS decay; demote, tighten stop"

    # ══ 4. ADD (pyramid) — leader AND good location ══════════════════════
    _is_leader = (quad in ("LEADING", "WEAKENING") and pnl >= 5.0 and score >= 60) or \
                 (quad == "LEADING" and pnl >= 8.0)
    _at_location = (_numok(sma200) and _numok(ltp) and ltp > sma200 and
                    _numok(sma200_slope) and sma200_slope > 0 and
                    _numok(c5) and ltp <= c5 * 1.10 and
                    _numok(ema20) and ltp > ema20)
    if _is_leader and _at_location:
        return "ADD", f"Score {score} · {quad} {row.get('rrg_arrow','')} · pullback to EMA20 · {catal}"
    if _is_leader and not _at_location:
        # A leader that's extended / not at a pullback — hold, don't chase.
        return "HOLD", f"Leader ({quad}, Score {score}) but extended — wait for pullback to add"

    return "HOLD", f"Score {score} · {quad} {row.get('rrg_arrow','')} · {row.get('rrg_trajectory','')}"


def color_class(val: str) -> str:
    if val == "ADD":    return "background-color: #1e4620; color: #4ade80; font-weight: 600;"   # green
    if val == "TRIM":   return "background-color: #43290f; color: #fb923c; font-weight: 600;"   # orange (partial)
    if val == "REDUCE": return "background-color: #10314f; color: #60a5fa; font-weight: 600;"   # blue (watch/defensive)
    if val == "EXIT":   return "background-color: #4a1d1d; color: #f87171; font-weight: 600;"   # red (full sell)
    if val == "HOLD":   return "background-color: #2d2d2d; color: #d1d5db;"
    return ""


def render_section(label: str, subset: pd.DataFrame, sort_col: str, ascending: bool):
    if subset.empty:
        st.caption(f"_{label}_: none")
        return
    sorted_df = subset.sort_values(sort_col, ascending=ascending)
    display_cols = ["symbol", "trade_type", "classification", "days_held", "buy_price", "ltp",
                     "pnl_pct", "r_mult", "score_100pt", "catalyst", "rrg_quadrant",
                     "rrg_arrow", "ema20", "wma30", "dma50", "swing_low", "chandelier", "target",
                     "stage", "sl_dist_atr", "trigger"]
    cols_present = [c for c in display_cols if c in sorted_df.columns]
    styled = sorted_df[cols_present].style.applymap(
        color_class, subset=["classification"]
    ).format({
        "buy_price": "₹{:.2f}", "ltp": "₹{:.2f}",
        "ema20": "₹{:.0f}", "wma30": "₹{:.0f}", "dma50": "₹{:.0f}",
        "swing_low": "₹{:.0f}", "chandelier": "₹{:.0f}", "target": "₹{:.0f}",
        "pnl_pct": "{:+.2f}%", "r_mult": "{:+.1f}R",
        "sl_dist_atr": "{:.1f}× ATR",
        "score_100pt": "{:d}",
    }, na_rep="—")
    st.dataframe(styled, width="stretch", hide_index=True)


def get_precomputed_classifications() -> pd.DataFrame:
    """Precompute the classification rows for all open positions.
    Returns a DataFrame containing the fully computed rows."""
    df_open = load_open_positions(DB_FILE)
    if df_open.empty:
        return pd.DataFrame()

    df_bench_w = fetch_bench_weekly()

    # Market-regime bear flag — SAME source Risk Shield uses (market_regime score
    # ≤ 5), so the catalyst-aware Chandelier multiplier matches between screens.
    _bear = False
    try:
        from market_regime import compute_regime as _creg
        _rscore = _creg(persist=False).get("score")
        _bear = (_rscore is not None and _rscore <= 5)
    except Exception:
        _bear = False

    rows = []
    for _, pos in df_open.reset_index(drop=True).iterrows():
        rrg = fetch_symbol_full(pos["symbol"], df_bench_w,
                                setup=str(pos.get("setup", "") or ""), bear=_bear,
                                swing=swing_from_trade_type(pos.get("timeframe") or pos.get("trade_type")))
        if not rrg:
            rrg = {"rrg_quadrant": "n/a", "rrg_tradeable": False, "rrg_score": 0,
                   "rrg_trajectory": "n/a", "rrg_arrow": "•", "ltp": np.nan,
                   "atr14": np.nan, "dma50": np.nan, "wma30": np.nan, "swing_low": np.nan,
                   "ema20": np.nan, "sma200": np.nan, "sma200_slope": np.nan,
                   "close_5d_ago": np.nan, "days_to_earnings": None, "chandelier": np.nan,
                   "rs_ratio": np.nan, "rs_momentum": np.nan, "stage": 0,
                   "score_100pt": 0, "catalyst": "n/a", "rel_vol": 0.0,
                   "rsi14": 0.0, "vcp_valid": False}
        pnl_pct = ((rrg["ltp"] - pos["buy_price"]) / pos["buy_price"] * 100
                   if _numok(rrg["ltp"]) and pos["buy_price"] > 0 else 0.0)
        rec = {**pos.to_dict(), **rrg, "pnl_pct": pnl_pct}
        cls, reason = classify(rec)
        rec["classification"] = cls
        rec["trigger"] = reason
        # R-multiple for display (same guard as classify)
        _b, _s, _l = pos.get("buy_price"), pos.get("stoploss"), rrg.get("ltp")
        _rps = (_b - _s) if (_numok(_b) and _numok(_s)) else np.nan
        rec["r_mult"] = ((_l - _b) / _rps) if (_numok(_l) and _numok(_rps) and _rps >= MIN_RISK_FRAC * _b) else np.nan
        rows.append(rec)

    df = pd.DataFrame(rows)
    df["pnl_pct"]     = df["pnl_pct"].round(2)
    df["sl_dist_atr"] = ((df["ltp"] - df["stoploss"]) / df["atr14"]).round(2)
    return df


def render_pyramid_trim(df_precomputed: pd.DataFrame = None):
    """Render the full Pyramid/Trim page body (no st.set_page_config — the caller
    owns that). Safe to call inline inside the main Web Commander."""
    st.markdown('<div class="page-title">⚖️ Pyramid / Trim Manager</div>', unsafe_allow_html=True)
    st.caption(
        "Five-rung ladder — **ADD → HOLD → REDUCE → TRIM → EXIT** — best-of-each logic. "
        "**EXIT** (full) = structure/thesis broken (30-WMA / swing-low / Stage 4 / at-SL / −8% / dead-money). "
        "**TRIM** (partial) = harvest a winner (≥2R / target / over-extended / earnings-soon). "
        "**REDUCE** (soft) = RS/decay warning → tighten stop & don't add (never a sell). "
        "**ADD** = a leader (RRG) at a good location (pullback to EMA20). RRG is selection-only, never a forced exit."
    )

    if df_precomputed is not None:
        df = df_precomputed
        if df.empty:
            st.warning("No open positions found.")
            return
        ctrl_l, ctrl_r = st.columns([3, 1])
        with ctrl_l:
            st.write(f"**{len(df)} open positions** loaded from cache.")
        with ctrl_r:
            if st.button("🔄 Refresh RRG", width="stretch", key="pyr_refresh"):
                st.cache_data.clear()
                st.session_state.pop("pyramid_classifications", None)
                st.rerun()
    else:
        df_open = load_open_positions(DB_FILE)
        if df_open.empty:
            st.warning(f"No open positions found in `{os.path.basename(DB_FILE)}` "
                       f"(status='OPEN'). Add positions via the Journal page / Dhan sync first.")
            return

        ctrl_l, ctrl_r = st.columns([3, 1])
        with ctrl_l:
            st.write(f"**{len(df_open)} open positions** loaded from journal.")
        with ctrl_r:
            if st.button("🔄 Refresh RRG", width="stretch", key="pyr_refresh"):
                st.cache_data.clear()
                st.session_state.pop("pyramid_classifications", None)
                st.rerun()

        df_bench_w = fetch_bench_weekly()

        # Market-regime bear flag — SAME source Risk Shield uses (market_regime score
        # ≤ 5), so the catalyst-aware Chandelier multiplier matches between screens.
        _bear = False
        try:
            from market_regime import compute_regime as _creg
            _rscore = _creg(persist=False).get("score")
            _bear = (_rscore is not None and _rscore <= 5)
        except Exception:
            _bear = False

        rows = []
        progress = st.progress(0.0, text="Computing RRG for each position…")
        for i, pos in df_open.reset_index(drop=True).iterrows():
            progress.progress((i + 1) / max(1, len(df_open)),
                              text=f"[{i+1}/{len(df_open)}] {pos['symbol']}")
            rrg = fetch_symbol_full(pos["symbol"], df_bench_w,
                                    setup=str(pos.get("setup", "") or ""), bear=_bear,
                                    swing=swing_from_trade_type(pos.get("timeframe") or pos.get("trade_type")))
            if not rrg:
                rrg = {"rrg_quadrant": "n/a", "rrg_tradeable": False, "rrg_score": 0,
                       "rrg_trajectory": "n/a", "rrg_arrow": "•", "ltp": np.nan,
                       "atr14": np.nan, "dma50": np.nan, "wma30": np.nan, "swing_low": np.nan,
                       "ema20": np.nan, "sma200": np.nan, "sma200_slope": np.nan,
                       "close_5d_ago": np.nan, "days_to_earnings": None, "chandelier": np.nan,
                       "rs_ratio": np.nan, "rs_momentum": np.nan, "stage": 0,
                       "score_100pt": 0, "catalyst": "n/a", "rel_vol": 0.0,
                       "rsi14": 0.0, "vcp_valid": False}
            pnl_pct = ((rrg["ltp"] - pos["buy_price"]) / pos["buy_price"] * 100
                       if _numok(rrg["ltp"]) and pos["buy_price"] > 0 else 0.0)
            rec = {**pos.to_dict(), **rrg, "pnl_pct": pnl_pct}
            cls, reason = classify(rec)
            rec["classification"] = cls
            rec["trigger"] = reason
            # R-multiple for display (same guard as classify)
            _b, _s, _l = pos.get("buy_price"), pos.get("stoploss"), rrg.get("ltp")
            _rps = (_b - _s) if (_numok(_b) and _numok(_s)) else np.nan
            rec["r_mult"] = ((_l - _b) / _rps) if (_numok(_l) and _numok(_rps) and _rps >= MIN_RISK_FRAC * _b) else np.nan
            rows.append(rec)
        progress.empty()

        df = pd.DataFrame(rows)
        df["pnl_pct"]     = df["pnl_pct"].round(2)
        df["sl_dist_atr"] = ((df["ltp"] - df["stoploss"]) / df["atr14"]).round(2)

    cnt_add    = (df["classification"] == "ADD").sum()
    cnt_trim   = (df["classification"] == "TRIM").sum()
    cnt_reduce = (df["classification"] == "REDUCE").sum()
    cnt_exit   = (df["classification"] == "EXIT").sum()
    cnt_hold   = (df["classification"] == "HOLD").sum()

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Open", len(df))
    m2.metric("▲ Add", cnt_add, delta=f"{cnt_add}/{len(df)}")
    m3.metric("◑ Trim", cnt_trim, help="Partial profit-take/de-risk — trend intact (≥2R / target / over-extended / earnings).")
    m4.metric("◐ Reduce", cnt_reduce, help="RS/decay warning — tighten stop & don't add. NOT a sell.")
    m5.metric("⬇ Exit", cnt_exit, delta=f"-{cnt_exit}", delta_color="inverse",
              help="Full exit — structure/thesis broken (30-WMA / swing-low / Stage 4 / at-SL / −8% / dead-money).")
    m6.metric("━ Hold", cnt_hold)

    st.divider()

    st.subheader("⬇ EXIT (Full — structure / thesis broken)")
    st.caption("Positional: closed below 30-WMA (Stage-4). Swing: closed below swing low. "
               "Plus Stage 4, **Chandelier stop-out** (price below the catalyst-aware trail — "
               "same as Risk Shield), at-SL with P&L ≤ 0, thesis-broken (≤ −8%), or dead-money "
               "time-stop. **Close the whole position.** Worst first.")
    render_section("EXIT", df[df["classification"] == "EXIT"], "pnl_pct", ascending=True)

    st.subheader("◑ TRIM (Partial — harvest a winner)")
    st.caption("Trend intact, book part & ride the rest: **≥2R** (⅓) / **≥3R** (½), target hit, "
               "over-extended (≥4×ATR above 20-EMA), or earnings within 3 days. Best runners first.")
    render_section("TRIM", df[df["classification"] == "TRIM"], "r_mult", ascending=False)

    st.subheader("◐ REDUCE (Warning — tighten stop, don't add)")
    st.caption("RS LAGGING vs N500, below 50-DMA, or score/RS decay — PRICE is still intact, so this is "
               "**not** a sell. Tighten the stop toward the 30-WMA / swing low and stop pyramiding; "
               "let price pull the trigger.")
    render_section("REDUCE", df[df["classification"] == "REDUCE"], "pnl_pct", ascending=True)

    st.subheader("▲ ADD (Pyramid winners)")
    st.caption("A leader (RRG LEADING/WEAKENING + Score ≥ 60 + winning) **at a good location** — "
               "pullback to the 20-EMA, above a rising 200-DMA, not extended. Rank by P&L.")
    render_section("ADD", df[df["classification"] == "ADD"], "pnl_pct", ascending=False)

    st.subheader("━ HOLD (No action)")
    st.caption("All remaining positions (incl. leaders that are extended — wait for a pullback to add).")
    with st.expander(f"Show {cnt_hold} HOLD positions", expanded=False):
        render_section("HOLD", df[df["classification"] == "HOLD"], "score_100pt", ascending=False)

    st.divider()
    st.caption(
        f"_Computed {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')} · "
        f"bull_screener.screen_symbol (Score/Catalyst/JdK RRG) per holding · Benchmark ^CRSLDX · "
        f"ladder: EXIT (structure/time) → TRIM (R-ladder/target/over-ext/earnings) → REDUCE (RS/decay) → "
        f"ADD (leader + pullback location). RRG = selection only._"
    )
