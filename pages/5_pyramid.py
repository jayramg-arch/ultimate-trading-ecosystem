"""Weinstein Commander — Pyramid / Trim Manager (v1.0).

Replaces the Pine Dashboard's deleted Alpha Screener feature for open-position
pyramiding and trimming decisions.

Inputs:
  - Open positions from trade_journal_v6.db (journal table, status='open')
  - Live LTPs from Dhan holdings (optional fallback to yfinance)
  - Per-symbol RRG signals via bull_screener.compute_weekly_indicators
    (JdK 1-pass, length=12, 5-bar smooth — Strike.Money-matched; produces
    RRG_Score (+2 if LEADING else 0), RRG_Tradeable (cell-level whitelist),
    RRG_Quadrant, RRG_Trajectory)

Classification rules (v1.1, post-audit 2026-05-21):
  TRIM (risk-off priority):
    - Quadrant = LAGGING (no validated edge in universe-wide backtest)
    - Price within 1.5x ATR of stoploss AND P&L <= 0
    - P&L <= -8% (thesis underwater)
    - Score <= 25 (setup decay, no catalyst firing)
    - Note: RRG_Tradeable=False was removed as TRIM trigger after backtest
      showed it inverted INSIDE the screener's already-filtered picks
  ADD:
    - Quadrant in (LEADING, WEAKENING) + Score >= 60 + P&L >= +5%
    - OR LEADING + P&L >= +8% (accelerating leader, score-agnostic)
  HOLD — everything else
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time
from datetime import datetime, date

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
from dotenv import load_dotenv

load_dotenv(override=True)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Pyramid / Trim — Weinstein Commander",
                    page_icon="⚖️", layout="wide")

# ── Imports: bull_screener for RRG + data_provider for OHLCV ──────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import bull_screener as bs
import data_provider as dp

DB_FILE = "trade_journal_v6.db"
BENCH   = "^CRSLDX"
ATR_LEN = 14


# ── Helpers ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_open_positions(db_path: str) -> pd.DataFrame:
    """Load all open positions from the trade journal."""
    if not os.path.exists(db_path):
        return pd.DataFrame()
    con = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            "SELECT id, symbol, entry_date, buy_price, quantity, stoploss, "
            "target, sector, trade_type, status FROM journal WHERE status = 'open'",
            con
        )
    finally:
        con.close()
    if df.empty:
        return df
    df["entry_date"] = pd.to_datetime(df["entry_date"], errors="coerce")
    df["days_held"] = (pd.Timestamp.now().normalize() - df["entry_date"]).dt.days
    df["buy_price"]  = pd.to_numeric(df["buy_price"], errors="coerce")
    df["stoploss"]   = pd.to_numeric(df["stoploss"], errors="coerce")
    df["quantity"]   = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=300, show_spinner=False)
def fetch_bench_weekly() -> pd.DataFrame:
    """Fetch + tail-extend ^CRSLDX weekly (same fix as bull_screener.py v1.5)."""
    df_w = bs._flatten_cols(dp.fetch_ohlcv(BENCH, period="3y", interval="1wk"))
    df_d = bs._flatten_cols(dp.fetch_ohlcv(BENCH, period="2y", interval="1d"))
    if not df_d.empty:
        res = df_d.resample("W-MON", closed="left", label="left").agg({
            "Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"
        }).dropna(subset=["Close"])
        if not res.empty and not df_w.empty:
            extra = res[res.index > df_w.index[-1]]
            if not extra.empty:
                df_w = pd.concat([df_w, extra])
    return df_w


def fetch_symbol_full(symbol: str, df_bench_w: pd.DataFrame) -> dict:
    """Run bull_screener's full per-symbol pipeline on `symbol`.

    Uses bs.screen_symbol(..., force_output=True, mkt_bull=True) so EVERY
    holding gets evaluated regardless of catalyst/turnover/regime filters
    that the screener normally applies during selection.

    Returns the full screener record (Score, Catalyst, RRG_*, Stage, VCP_*,
    Entry, SL_pct, T1_pct, Rel_Vol, RSI, JdK_*) plus locally-computed
    ltp and atr14 (needed for SL-distance classification). Empty dict on failure.
    """
    try:
        rec = bs.screen_symbol(symbol, df_bench_w,
                                force_output=True, mkt_bull=True)
    except Exception:
        rec = None
    if rec is None:
        return {}

    # Fetch daily bars again (cache-warm after screen_symbol → near-instant)
    # for current LTP + ATR14 used in SL-distance check.
    try:
        yf_sym = bs.to_yf(symbol)
        df_d = bs._flatten_cols(dp.fetch_ohlcv(yf_sym, period="6mo", interval="1d"))
    except Exception:
        df_d = pd.DataFrame()

    ltp = float(df_d["Close"].iloc[-1]) if not df_d.empty else np.nan
    atr14 = np.nan
    if not df_d.empty and len(df_d) >= ATR_LEN + 1:
        try:
            h, l, c = df_d["High"], df_d["Low"], df_d["Close"]
            tr = pd.concat([h - l,
                             (h - c.shift()).abs(),
                             (l - c.shift()).abs()], axis=1).max(axis=1)
            atr14 = float(tr.rolling(ATR_LEN).mean().iloc[-1])
        except Exception:
            pass

    return {
        "ltp":              ltp,
        "atr14":            atr14,
        # Full screener fields (renamed to snake_case for downstream consistency)
        "score_100pt":      int(rec.get("Score", 0)),
        "catalyst":         rec.get("Catalyst", "None"),
        "stage":            int(rec.get("Stage", 0)),
        "rrg_quadrant":     rec.get("RRG_Quadrant", "n/a"),
        "rrg_next":         rec.get("RRG_Next", "n/a"),
        "rrg_trajectory":   rec.get("RRG_Trajectory", "n/a"),
        "rrg_arrow":        rec.get("RRG_Arrow", "•"),
        "rrg_score":        int(rec.get("RRG_Score", 0)),
        "rrg_tradeable":    bool(rec.get("RRG_Tradeable", False)),
        "rs_ratio":         float(rec.get("JdK_RS_Ratio", 100.0)),
        "rs_momentum":      float(rec.get("JdK_RS_Momentum", 100.0)),
        "rel_vol":          float(rec.get("Rel_Vol", 0.0) or 0.0),
        "rsi14":            float(rec.get("RSI", 0.0) or 0.0),
        "vcp_valid":        bool(rec.get("VCP_Valid", False)),
        "screener_entry":   rec.get("Entry"),
        "screener_sl_pct":  rec.get("SL_pct"),
        "screener_t1_pct":  rec.get("T1_pct"),
        "screener_t2_pct":  rec.get("T2_pct"),
        "screener_t1_r":    rec.get("T1_R"),
        "screener_t2_r":    rec.get("T2_R"),
    }


def classify(row: dict) -> tuple[str, str]:
    """Return (classification, trigger_reason).

    Classification ∈ {ADD, TRIM, HOLD}. Uses full bull_screener 100-pt Score
    (catalyst + stage + RS + VCP composite) as the strength signal — not the
    binary RRG_Score proxy.
    """
    quad   = row.get("rrg_quadrant", "n/a")
    trd    = row.get("rrg_tradeable", False)
    score  = int(row.get("score_100pt", 0) or 0)
    catal  = row.get("catalyst", "None")
    pnl    = row.get("pnl_pct", 0.0)
    ltp    = row.get("ltp", np.nan)
    sl     = row.get("stoploss", np.nan)
    atr14  = row.get("atr14", np.nan)

    # ── TRIM checks (risk-off has priority) ──────────────────────────────
    # v1.1: Tradeable removed as TRIM trigger (inverted inside picks — see ADD notes).
    # Hard TRIM triggers are now pure risk-off (SL approach, P&L underwater, low Score)
    # plus the LAGGING quadrant (which the population-level data confirmed has no edge).
    if quad == "LAGGING":
        return "TRIM", f"{quad} — no edge in this quadrant"
    if not np.isnan(ltp) and not np.isnan(sl) and not np.isnan(atr14) and atr14 > 0:
        if (ltp - sl) <= 1.5 * atr14 and pnl <= 0:
            return "TRIM", f"SL approach: {(ltp-sl)/atr14:.1f}× ATR"
    if pnl <= -8.0:
        return "TRIM", f"P&L -{abs(pnl):.1f}% — thesis underwater"
    if score <= 25:
        return "TRIM", f"Score {score} — setup decay (no catalyst firing)"

    # ── ADD checks ───────────────────────────────────────────────────────
    # v1.1 (2026-05-20): Tradeable removed from ADD requirement.
    # Backtest finding: among screener picks, Tradeable=False subset had
    # +2.04% alpha vs +0.06% for Tradeable=True (Tradeable rule is INVERTED
    # inside the screener's already-filtered population — the catalyst+stage
    # filters already capture what Tradeable measures, and the remaining
    # Tradeable=False picks turned out to be the strongest LEADING bouncers).
    # Tradeable now shown as advisory column only, not a gate.
    #
    # Strong: full screener Score >= 60 AND winning + LEADING/WEAKENING quadrant.
    # (WEAKENING added — backtest showed it earns +1.74% alpha here, second best.)
    if quad in ("LEADING", "WEAKENING") and pnl >= 5.0 and score >= 60:
        traj = row.get("rrg_trajectory", "")
        return "ADD", f"Score {score} · {quad} {row.get('rrg_arrow','')} · {catal} · {traj}"
    # Conditional add: winning hard + LEADING — pyramid the leaders.
    if quad == "LEADING" and pnl >= 8.0:
        return "ADD", f"Score {score} · LEADING {row.get('rrg_arrow','')} winning · {catal}"

    # HOLD = everything else
    return "HOLD", f"Score {score} · {quad} {row.get('rrg_arrow','')} · {row.get('rrg_trajectory','')}"


def color_class(val: str) -> str:
    if val == "ADD":  return "background-color: #1e4620; color: #4ade80; font-weight: 600;"
    if val == "TRIM": return "background-color: #4a1d1d; color: #f87171; font-weight: 600;"
    if val == "HOLD": return "background-color: #2d2d2d; color: #d1d5db;"
    return ""


# ── UI ────────────────────────────────────────────────────────────────────────
st.title("⚖️ Pyramid / Trim Manager")
st.caption(
    "Decision tool for open positions. Uses JdK 2-pass RRG + bull_screener "
    "signals (validated against n=5,460 Nifty 500 backtest). "
    "Replaces the Pine Dashboard's deleted Alpha Screener."
)

# ── Load + control row ────────────────────────────────────────────────────────
df_open = load_open_positions(DB_FILE)
if df_open.empty:
    st.warning(f"No open positions found in `{DB_FILE}` (status='open'). "
                f"Add positions via the Journal page first.")
    st.stop()

ctrl_l, ctrl_r = st.columns([3, 1])
with ctrl_l:
    st.write(f"**{len(df_open)} open positions** loaded from journal.")
with ctrl_r:
    if st.button("🔄 Refresh RRG", width="stretch"):
        st.cache_data.clear()
        st.rerun()

# ── Compute RRG for each position ─────────────────────────────────────────────
df_bench_w = fetch_bench_weekly()

rows = []
progress = st.progress(0.0, text="Computing RRG for each position…")
for i, pos in df_open.iterrows():
    progress.progress((i + 1) / max(1, len(df_open)),
                       text=f"[{i+1}/{len(df_open)}] {pos['symbol']}")
    rrg = fetch_symbol_full(pos["symbol"], df_bench_w)
    if not rrg:
        rrg = {"rrg_quadrant": "n/a", "rrg_tradeable": False,
                "rrg_score": 0, "rrg_trajectory": "n/a", "rrg_arrow": "•",
                "ltp": np.nan, "atr14": np.nan, "rs_ratio": np.nan,
                "rs_momentum": np.nan, "stage": 0,
                "score_100pt": 0, "catalyst": "n/a",
                "rel_vol": 0.0, "rsi14": 0.0, "vcp_valid": False}
    pnl_pct = ((rrg["ltp"] - pos["buy_price"]) / pos["buy_price"] * 100
                if not np.isnan(rrg["ltp"]) and pos["buy_price"] > 0 else 0.0)
    rec = {
        **pos.to_dict(),
        **rrg,
        "pnl_pct": pnl_pct,
    }
    cls, reason = classify(rec)
    rec["classification"] = cls
    rec["trigger"]        = reason
    rows.append(rec)
progress.empty()

df = pd.DataFrame(rows)
df["pnl_pct"]      = df["pnl_pct"].round(2)
df["sl_dist_atr"]  = ((df["ltp"] - df["stoploss"]) / df["atr14"]).round(2)

# ── Summary header ────────────────────────────────────────────────────────────
cnt_add  = (df["classification"] == "ADD").sum()
cnt_trim = (df["classification"] == "TRIM").sum()
cnt_hold = (df["classification"] == "HOLD").sum()
tradeable_pct = (df["rrg_tradeable"].sum() / len(df) * 100) if len(df) else 0

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Open Positions", len(df))
m2.metric("▲ Add", cnt_add, delta=f"{cnt_add}/{len(df)}")
m3.metric("⬇ Trim", cnt_trim, delta=f"-{cnt_trim}", delta_color="inverse")
m4.metric("━ Hold", cnt_hold)
m5.metric("Net Tradeable", f"{tradeable_pct:.0f}%")

st.divider()


def render_section(label: str, subset: pd.DataFrame, sort_col: str, ascending: bool):
    if subset.empty:
        st.caption(f"_{label}_: none")
        return
    sorted_df = subset.sort_values(sort_col, ascending=ascending)
    display_cols = ["symbol", "classification", "days_held", "buy_price", "ltp",
                     "pnl_pct", "score_100pt", "catalyst", "rrg_quadrant",
                     "rrg_arrow", "rrg_trajectory", "rrg_tradeable",
                     "rs_ratio", "stage", "rel_vol", "vcp_valid",
                     "sl_dist_atr", "trigger"]
    cols_present = [c for c in display_cols if c in sorted_df.columns]
    styled = sorted_df[cols_present].style.applymap(
        color_class, subset=["classification"]
    ).format({
        "buy_price": "₹{:.2f}", "ltp": "₹{:.2f}",
        "pnl_pct": "{:+.2f}%", "rs_ratio": "{:.1f}",
        "sl_dist_atr": "{:.1f}× ATR",
        "score_100pt": "{:d}",
        "rel_vol": "{:.2f}×",
    })
    st.dataframe(styled, width="stretch", hide_index=True)


# ── Render sections ───────────────────────────────────────────────────────────
st.subheader("▲ ADD (Pyramid winners)")
st.caption("Tradeable + LEADING/IMPROVING + already +5% from entry. Rank by P&L.")
render_section("ADD", df[df["classification"] == "ADD"], "pnl_pct", ascending=False)

st.subheader("⬇ TRIM (Reduce exposure)")
st.caption("Untradeable, LAGGING, near SL, or thesis-broken (P&L ≤ −8%). Worst first.")
render_section("TRIM", df[df["classification"] == "TRIM"], "pnl_pct", ascending=True)

st.subheader("━ HOLD (No action)")
st.caption("All remaining positions. Watch RRG trajectory for next-bar shift.")
with st.expander(f"Show {cnt_hold} HOLD positions", expanded=False):
    render_section("HOLD", df[df["classification"] == "HOLD"], "score_100pt", ascending=False)

st.divider()
st.caption(
    f"_Computed {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')} · "
    f"Full bull_screener.screen_symbol (Score 0-100, Catalyst, JdK RRG) per holding · "
    f"Benchmark ^CRSLDX · ATR{ATR_LEN} for SL distance · force_output=True so every position evaluates._"
)
