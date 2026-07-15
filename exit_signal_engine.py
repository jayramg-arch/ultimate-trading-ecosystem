#!/usr/bin/env python3
"""
exit_signal_engine.py  —  Commander Exit Signal Engine  v1.0
MISS-1: Watchdog scanner for open positions.

Scans all open positions from the trade journal and flags stocks that have
triggered one of three exit conditions:

  STOP-LOSS    : LTP <= StopLoss (or within 1 ATR buffer)
  TARGET       : LTP >= Target
  STAGE-DECAY  : Weinstein Stage has deteriorated (Stage 2 → Stage 3/4 or
                 Stage 1 → Stage 4 while below 30W SMA with negative slope)
  RS-FADE      : Mansfield RS has gone negative (positive RS turned negative)

Outputs:
  Exit_Signals.csv    — stocks requiring action
  Prints a summary to console

Usage:
  python exit_signal_engine.py                 # scan all open positions
  python exit_signal_engine.py --silent         # no prompts
"""

import os
import sys
import sqlite3
import argparse
import logging
import warnings

import numpy as np
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from datetime import datetime

warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("peewee").setLevel(logging.CRITICAL)

# C1: route OHLCV through the unified data_provider when available.
try:
    import data_provider as _dp
    USE_DATA_PROVIDER = True
except Exception:
    _dp = None
    USE_DATA_PROVIDER = False

load_dotenv(override=True)

# ── Paths ─────────────────────────────────────────────────────────────────────
_DIR     = os.path.dirname(os.path.abspath(__file__))
DB_FILE  = os.path.join(_DIR, "trade_journal_v6.db")
OUT_FILE = os.path.join(_DIR, "Exit_Signals.csv")

# ── Config ────────────────────────────────────────────────────────────────────
SL_BUFFER_ATR  = 1.0   # warn if within 1 ATR of stop-loss
CNX500_YF      = "^CRSLDX"
LOOKBACK_DAYS  = 400   # daily history for stage/RS calculation


# ── E5: Trail-stop / partial-exit recommender ────────────────────────────────
# Translates an Exit_Reason flag into a concrete action: how much to trim,
# where to move the SL, and which trailing stop to use thereafter.
#
# Rules (deliberately mechanical so they're auditable):
#   R-multiple reached       Action
#   ────────────────────     ────────────────────────────────────────────
#   ≥ 1.0R, < 2.0R           Move SL → breakeven (lock zero loss)
#   ≥ 2.0R, < 3.0R           Trim 33% + move SL → entry + 0.5R
#   ≥ 3.0R                   Trim 50% + Chandelier trail (22-bar high − 3×ATR)
#   Stage-3 topping flag     Trim 25% defensively + move SL → entry
#   Stage-4 breakdown flag   Full exit (qty 100%, no trail)
#   SL breached              Full exit
#   RS fade alone            Tighten SL to last-week low
#
# Output: list[dict] with {action, qty_pct, new_sl, trail_method, reason}.
def recommend_actions(buy_price: float, stop_loss: float, ltp: float,
                       atr: float, stage: int | None,
                       mansfield_rs: float | None,
                       df_d: pd.DataFrame | None = None,
                       sl_breached: bool = False) -> list[dict]:
    """Build a list of suggested actions from the position's current state.

    v2.3 E-2: When the market regime is bearish (via v2_fixes), R-multiple
    thresholds shift lower, Stage 3 trims escalate, and positions below
    entry in extreme bear regimes trigger full exits.

    Empty list = "no action; continue holding".
    """
    out: list[dict] = []
    if buy_price <= 0 or stop_loss <= 0 or ltp <= 0:
        return out
    risk_per_share = max(buy_price - stop_loss, 0.01)
    r_mult = (ltp - buy_price) / risk_per_share

    # v2.3 E-2: read regime overrides
    try:
        import v2_fixes as _v2
        _regime = _v2.get_exit_regime_overrides()
    except Exception:
        _regime = {"active": False, "regime_score": None, "r_shift": 0.0,
                   "stage3_trim_pct": 25, "exit_below_entry_in_bear": False}
    r_shift = _regime.get("r_shift", 0.0)
    stage3_trim = _regime.get("stage3_trim_pct", 25)
    exit_below_entry = _regime.get("exit_below_entry_in_bear", False)
    _regime_tag = ""
    if _regime.get("active") and _regime.get("regime_score") is not None:
        _regime_tag = f" [regime={_regime['regime_score']}/10]"

    # Hard exits first — they win over trims/trails.
    if sl_breached:
        out.append({
            "action":       "EXIT_FULL",
            "qty_pct":      100,
            "new_sl":       None,
            "trail_method": None,
            "reason":       f"SL breached -- exit at market.{_regime_tag}",
        })
        return out

    if stage == 4:
        out.append({
            "action":       "EXIT_FULL",
            "qty_pct":      100,
            "new_sl":       None,
            "trail_method": None,
            "reason":       f"Stage 4 breakdown -- trend broken; exit fully.{_regime_tag}",
        })
        return out

    # v2.3 E-2: in extreme bear regime, positions below entry = full exit
    if exit_below_entry and ltp < buy_price:
        out.append({
            "action":       "EXIT_FULL",
            "qty_pct":      100,
            "new_sl":       None,
            "trail_method": None,
            "reason":       (f"Position below entry in Bear regime "
                            f"(regime={_regime.get('regime_score', '?')}/10) "
                            f"-- exit fully to preserve capital."),
        })
        return out

    # R-multiple ladder (v2.3: thresholds shift by r_shift in bear regime)
    r_threshold_3 = 3.0 - r_shift
    r_threshold_2 = 2.0 - r_shift
    r_threshold_1 = 1.0 - r_shift

    if r_mult >= r_threshold_3:
        # Chandelier trail: highest high of last 22 bars - 3xATR
        chandelier = None
        if df_d is not None and not df_d.empty and "High" in df_d.columns and atr > 0:
            try:
                chandelier = float(df_d["High"].rolling(22).max().iloc[-1] - 3.0 * atr)
                chandelier = max(chandelier, buy_price + 0.5 * risk_per_share)
            except Exception:
                chandelier = None
        out.append({
            "action":       "TRIM_AND_TRAIL",
            "qty_pct":      50,
            "new_sl":       round(chandelier, 2) if chandelier else None,
            "trail_method": "Chandelier (22-bar high - 3xATR)",
            "reason":       f"At {r_mult:.1f}R (threshold {r_threshold_3:.1f}R) "
                            f"-- book half, trail the rest with Chandelier.{_regime_tag}",
        })
    elif r_mult >= r_threshold_2:
        new_sl = round(buy_price + 0.5 * risk_per_share, 2)
        out.append({
            "action":       "TRIM_PARTIAL",
            "qty_pct":      33,
            "new_sl":       new_sl,
            "trail_method": "Static SL at entry + 0.5R",
            "reason":       f"At {r_mult:.1f}R (threshold {r_threshold_2:.1f}R) "
                            f"-- trim 1/3, lock 0.5R on the rest.{_regime_tag}",
        })
    elif r_mult >= r_threshold_1:
        out.append({
            "action":       "MOVE_TO_BREAKEVEN",
            "qty_pct":      0,
            "new_sl":       round(buy_price, 2),
            "trail_method": "Breakeven",
            "reason":       f"At {r_mult:.1f}R (threshold {r_threshold_1:.1f}R) "
                            f"-- risk-free trade; move SL to breakeven.{_regime_tag}",
        })

    # Stage-3 topping -> defensive trim *in addition* to the R-rule above
    # v2.3 E-2: trim escalates from 25% to stage3_trim_pct in bear regime
    if stage == 3:
        out.append({
            "action":       "TRIM_DEFENSIVE",
            "qty_pct":      stage3_trim,
            "new_sl":       round(buy_price, 2),
            "trail_method": "Static SL at entry",
            "reason":       f"Stage 3 topping -- trim {stage3_trim}% and tighten to entry.{_regime_tag}",
        })

    # RS fade (if no R-multiple action triggered) -> tighten SL
    # v2.3 E-2: in bear regime, RS fade also triggers a 33% trim
    if (mansfield_rs is not None and mansfield_rs < 0
            and df_d is not None and not df_d.empty
            and "Low" in df_d.columns and len(df_d) >= 5):
        try:
            last_week_low = float(df_d["Low"].iloc[-5:].min())
            if last_week_low > stop_loss and last_week_low < ltp:
                if r_shift > 0 and not out:
                    # Bear regime: RS fade is more dangerous -> trim + tighten
                    out.append({
                        "action":       "TRIM_AND_TIGHTEN",
                        "qty_pct":      33,
                        "new_sl":       round(last_week_low, 2),
                        "trail_method": "5-day low",
                        "reason":       (f"Mansfield RS fading in bear regime "
                                        f"-- trim 33% and tighten SL.{_regime_tag}"),
                    })
                elif not out:
                    out.append({
                        "action":       "TIGHTEN_SL",
                        "qty_pct":      0,
                        "new_sl":       round(last_week_low, 2),
                        "trail_method": "5-day low",
                        "reason":       f"Mansfield RS fading -- tighten SL to last-week low.{_regime_tag}",
                    })
        except Exception:
            pass

    return out


# ── Helpers ───────────────────────────────────────────────────────────────────
def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _yf(symbol: str) -> str:
    s = str(symbol).strip().upper().replace("NSE:", "").replace("BSE:", "")
    for suf in ["-EQ", "-BE", "-SM", "-ST", "-BZ", ".NS"]:
        if s.endswith(suf):
            s = s[: -len(suf)]
    return f"{s}.NS"


def _weinstein_stage(df_w: pd.DataFrame) -> int:
    """Quick Weinstein stage from weekly data."""
    if len(df_w) < 35:
        return 0
    c    = df_w["Close"]
    sma  = c.rolling(30).mean()
    slope = sma - sma.shift(4)
    thresh = sma * 0.0005
    above = bool(c.iloc[-1] > sma.iloc[-1])
    sl, th = float(slope.iloc[-1]), float(thresh.iloc[-1])
    if sl > th and above:    return 2
    if sl < -th and not above: return 4
    if above:                return 1
    return 3


def _mansfield_rs(df_w: pd.DataFrame, df_cnx_w: pd.DataFrame) -> float:
    """Mansfield RS, ×100 textbook scale — aligned with bull_screener and
    recovery_screener (was ×10 — caused magnitude mismatch in dashboard vs
    Exit_Signals.csv even though sign-based gates still worked)."""
    sc = df_w["Close"].rename("s")
    mc = df_cnx_w["Close"].rename("m")
    m  = pd.merge(sc, mc, left_index=True, right_index=True, how="inner")
    # B6 fix: 52-week warm-up (was 27) — aligns with bull_screener / recovery_screener.
    if len(m) < 52:
        return np.nan
    rs_line  = m["s"] / m["m"]
    sma26    = rs_line.rolling(26).mean()
    mansfield = (rs_line / sma26.replace(0, np.nan) - 1) * 100
    return float(mansfield.iloc[-1]) if not mansfield.empty else np.nan


def _atr14(df_d: pd.DataFrame) -> float:
    h, l, c = df_d["High"], df_d["Low"], df_d["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return float(tr.ewm(span=14, adjust=False).mean().iloc[-1])


# ── Load open positions ───────────────────────────────────────────────────────
def load_open_positions() -> pd.DataFrame:
    """Return open positions from trade journal DB."""
    if not os.path.exists(DB_FILE):
        print(f"⚠️  DB not found: {DB_FILE}")
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql("SELECT * FROM journal WHERE status='OPEN'", conn)
        conn.close()
        col_map = {
            "symbol": "Symbol", "stoploss": "StopLoss", "target": "Target",
            "buy_price": "BuyPrice", "quantity": "Quantity", "entry_date": "EntryDate",
        }
        df.rename(columns=col_map, inplace=True)
        for c in ["StopLoss", "Target", "BuyPrice", "Quantity"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        return df
    except Exception as e:
        print(f"❌ DB error: {e}")
        return pd.DataFrame()


# ── Core scan ─────────────────────────────────────────────────────────────────
def scan_position(row: pd.Series, df_cnx_d: pd.DataFrame, df_cnx_w: pd.DataFrame) -> dict:
    sym   = str(row.get("Symbol", "")).strip().upper()
    bp    = float(row.get("BuyPrice", 0) or 0)
    sl    = float(row.get("StopLoss", 0) or 0)
    tgt   = float(row.get("Target", 0) or 0)
    yf_s  = _yf(sym)

    result = {
        "Symbol": sym, "BuyPrice": bp, "StopLoss": sl, "Target": tgt,
        "LTP": None, "ATR14": None,
        "Weinstein_Stage": None, "Mansfield_RS": None,
        "R_Multiple": None,                  # E5: current R-multiple
        "Exit_Flag": "OK", "Exit_Reasons": [],
        "Recommendations": [],               # E5: actionable trim/trail steps
    }

    try:
        import data_provider as dp
        df_d = _flatten(dp.fetch_ohlcv(sym, period=f"{LOOKBACK_DAYS}d", interval="1d", use_cache=True, auto_adjust=True))
        if df_d.empty or len(df_d) < 30:
            result["Exit_Flag"] = "DATA_ERROR"
            result["Exit_Reasons"].append("Insufficient daily data")
            return result

        df_w = _flatten(dp.fetch_ohlcv(sym, period="3y", interval="1wk", use_cache=True, auto_adjust=True))

        ltp  = float(df_d["Close"].iloc[-1])
        atr  = _atr14(df_d)
        stage = _weinstein_stage(df_w) if not df_w.empty else 0
        rs    = _mansfield_rs(df_w, df_cnx_w) if not df_w.empty else np.nan

        result["LTP"]             = round(ltp, 2)
        result["ATR14"]           = round(atr, 2)
        result["Weinstein_Stage"] = stage
        result["Mansfield_RS"]    = round(rs, 3) if not np.isnan(rs) else None

        reasons = []

        # ── STOP-LOSS check ──────────────────────────────────────────────────
        if sl > 0:
            if ltp <= sl:
                reasons.append(f"🔴 SL BREACHED (LTP={ltp:.2f} ≤ SL={sl:.2f})")
            elif atr > 0 and (ltp - sl) <= atr * SL_BUFFER_ATR:
                reasons.append(f"🟠 SL NEAR (within {SL_BUFFER_ATR}×ATR: LTP={ltp:.2f}, SL={sl:.2f}, ATR={atr:.2f})")

        # ── TARGET check ─────────────────────────────────────────────────────
        if tgt > 0 and ltp >= tgt:
            reasons.append(f"🟢 TARGET HIT (LTP={ltp:.2f} ≥ T1={tgt:.2f}) — consider booking / trailing")

        # ── STAGE DECAY check ────────────────────────────────────────────────
        # Stage 4 = breakdown (exit). Stage 3 = topping (review/trim, not exit).
        if stage == 4:
            reasons.append(f"🔴 STAGE 4 BREAKDOWN: trend broken — exit candidate")
        elif stage == 3:
            reasons.append(f"🟠 STAGE 3 TOPPING: distribution risk — review / trim")
        elif stage == 0:
            reasons.append("⚠️ STAGE UNKNOWN: insufficient weekly data")

        # ── RS FADE check ────────────────────────────────────────────────────
        if result["Mansfield_RS"] is not None and result["Mansfield_RS"] < 0:
            reasons.append(f"🟠 RS FADE: Mansfield RS = {result['Mansfield_RS']:.2f} (negative vs CNX500)")

        if reasons:
            result["Exit_Flag"]    = "ACTION"
            result["Exit_Reasons"] = reasons
        else:
            result["Exit_Reasons"] = ["✅ All clear"]

        # ── E5: build actionable trim/trail recommendations ─────────────────
        if bp > 0 and sl > 0 and ltp > 0:
            risk_per_share = max(bp - sl, 0.01)
            r_mult = round((ltp - bp) / risk_per_share, 2)
            result["R_Multiple"] = r_mult
            sl_breached = sl > 0 and ltp <= sl
            recs = recommend_actions(
                buy_price=bp, stop_loss=sl, ltp=ltp, atr=atr,
                stage=stage, mansfield_rs=result["Mansfield_RS"],
                df_d=df_d, sl_breached=sl_breached,
            )
            result["Recommendations"] = recs
            if recs and result["Exit_Flag"] != "ACTION":
                # If only the recommender fired (e.g. price hit 1R) flag for review
                result["Exit_Flag"] = "ACTION"
                result["Exit_Reasons"].append(
                    "📌 " + recs[0]["reason"]
                )

    except Exception as e:
        result["Exit_Flag"]    = "ERROR"
        result["Exit_Reasons"] = [str(e)]

    return result


# ── Main ──────────────────────────────────────────────────────────────────────
def run_exit_scan(silent: bool = False) -> pd.DataFrame:
    # Bug #1 fix (10 May 2026): honour the silent contract — when called from
    # Streamlit dashboard (E-6) we don't want banner / progress lines polluting
    # the server console. Redirect stdout to a sink for the duration of the
    # call. Errors still surface via the returned DataFrame and logging.error.
    import contextlib, io as _io
    _stdout_sink = contextlib.redirect_stdout(_io.StringIO()) if silent \
                   else contextlib.nullcontext()
    with _stdout_sink:
        return _run_exit_scan_impl(silent=silent)


def _run_exit_scan_impl(silent: bool = False) -> pd.DataFrame:
    print("=" * 68)
    print("  COMMANDER EXIT SIGNAL ENGINE  v1.0")
    print(f"  {datetime.now().strftime('%A %d %b %Y  %H:%M')}")
    print("=" * 68)

    df_pos = load_open_positions()
    if df_pos.empty:
        print("  No open positions found in journal.")
        return pd.DataFrame()

    total = len(df_pos)
    print(f"\n  Open positions: {total}")

    # Download CNX500 for Mansfield RS denominator (C1: cached via data_provider)
    print("  Downloading CNX500 market data...")
    try:
        import data_provider as dp
        df_cnx_d = _flatten(dp.fetch_ohlcv(CNX500_YF, period="2y", interval="1d", use_cache=True, auto_adjust=True))
        df_cnx_w = _flatten(dp.fetch_ohlcv(CNX500_YF, period="3y", interval="1wk", use_cache=True, auto_adjust=True))
    except Exception as e:
        print(f"  ⚠️ CNX500 download failed: {e} — RS checks will be skipped")
        df_cnx_d = df_cnx_w = pd.DataFrame()

    print(f"\n  Scanning {total} positions...\n")
    results = []
    for idx, (_, row) in enumerate(df_pos.iterrows(), 1):
        sym = str(row.get("Symbol", "?"))
        print(f"  [{idx:2d}/{total}]  {sym:<16} ...", end=" ", flush=True)
        r = scan_position(row, df_cnx_d, df_cnx_w)
        flag = r["Exit_Flag"]
        icon = "🔴" if flag == "ACTION" else ("⚠️" if flag == "ERROR" else "✅")
        print(f"{icon}  {' | '.join(r['Exit_Reasons'][:2])}")
        r["Exit_Reasons"] = " | ".join(r["Exit_Reasons"])
        results.append(r)
        import time
        time.sleep(0.4)

    # Stringify Recommendations for CSV portability before saving
    def _recs_to_str(recs):
        if not recs: return ""
        return " | ".join(
            f"[{r['action']}] qty={r['qty_pct']}% sl={r.get('new_sl','—')} — {r['reason']}"
            for r in recs
        )
    df_out = pd.DataFrame(results)
    if "Recommendations" in df_out.columns:
        df_out["Recommendations_Str"] = df_out["Recommendations"].apply(_recs_to_str)
    df_out.to_csv(OUT_FILE, index=False)

    # Summary
    action = df_out[df_out["Exit_Flag"] == "ACTION"]
    print(f"\n{'=' * 68}")
    print(f"  SUMMARY: {len(action)} of {total} positions need attention")
    if not action.empty:
        print(f"\n  {'Symbol':<14} {'LTP':>8} {'R':>5} {'Stage':>5} {'RS':>6}  Action")
        print("  " + "-" * 70)
        for _, r in action.iterrows():
            ltp_s = f"{r['LTP']:.2f}" if r["LTP"] else "N/A"
            rs_s  = f"{r['Mansfield_RS']:.2f}" if r["Mansfield_RS"] is not None else "N/A"
            r_s   = f"{r['R_Multiple']:+.1f}R" if r.get("R_Multiple") is not None else "—"
            recs = r.get("Recommendations") or []
            primary = recs[0] if recs else None
            action_str = (f"{primary['action']} qty={primary['qty_pct']}%"
                           if primary else r["Exit_Reasons"][:30])
            print(f"  {r['Symbol']:<14} {ltp_s:>8} {r_s:>5} "
                  f"{str(r['Weinstein_Stage'] or '?'):>5} {rs_s:>6}  {action_str}")
    print(f"\n  Full results → {OUT_FILE}")
    print("=" * 68)

    # RS-P1 (14-Jul-2026): a stop hit / stage decay used to produce ZERO
    # notification — the CSV sat unread until someone opened the COMMAND page.
    # Push ACTION rows to Telegram (same env vars the scheduler uses). Guarded:
    # alerting must never break the scan.
    if not action.empty:
        try:
            import requests as _rq
            _tok = os.getenv("TELEGRAM_BOT_TOKEN", "")
            _chat = os.getenv("TELEGRAM_CHAT_ID", "")
            if _tok and _chat:
                _lines = [f"🚨 <b>EXIT SIGNALS</b> — {len(action)} position(s) need attention"]
                for _, r in action.head(12).iterrows():
                    _recs = r.get("Recommendations") or []
                    _act = (f"{_recs[0]['action']} qty={_recs[0]['qty_pct']}%"
                            if _recs else str(r.get("Exit_Reasons", ""))[:60])
                    _ltp = r.get("LTP")
                    _ltp_s = f"{_ltp:.1f}" if (_ltp is not None and _ltp == _ltp) else "n/a"
                    _lines.append(f"• <b>{r['Symbol']}</b> (LTP {_ltp_s}, "
                                  f"Stage {r.get('Weinstein_Stage') or '?'}) — {_act}")
                _rq.post(f"https://api.telegram.org/bot{_tok}/sendMessage",
                         json={"chat_id": _chat, "text": "\n".join(_lines)[:4000],
                               "parse_mode": "HTML"}, timeout=10)
                print("  📨 Telegram alert sent.")
            else:
                logging.getLogger(__name__).info("exit alerts: no Telegram creds — skipped")
        except Exception as _te:
            print(f"  ⚠ Telegram alert failed: {_te}")

    if not silent:
        input("\nPress Enter to close...")

    return df_out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Commander Exit Signal Engine")
    parser.add_argument("--silent", action="store_true", help="No interactive prompts")
    args = parser.parse_args()
    run_exit_scan(silent=args.silent)
