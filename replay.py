"""
replay.py — Run a screener as-of a historical date and grade the picks
against their next-N-day actual returns.

Why: the audit board's E10 item — "if I had run the bull screener on
2025-09-15, what would it have flagged, and how did those picks actually
perform 30 trading days later?" The answer turns the screener from an
opinion into a measurable backtest.

Public API:
  run_bull_replay(as_of, forward_days=30, symbols=None)  -> dict
  run_recovery_replay(as_of, forward_days=30)            -> dict
  forward_returns(symbols, as_of, forward_days=30)       -> DataFrame

Each replay returns:
  {
    "as_of":          "YYYY-MM-DD",
    "forward_days":   N,
    "ran_at":         "YYYY-MM-DDTHH:MM:SS",
    "duration_s":     float,
    "picks":          DataFrame,          # screener output as-of
    "performance":    DataFrame,          # forward-N-day returns per pick
    "summary":        dict,               # win rate, avg return, vs benchmark
    "benchmark_pct":  float | None,       # benchmark return over the same window
    "out_csv":        str,                # path to saved replay CSV
  }
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

import data_provider as _dp


HERE = os.path.dirname(os.path.abspath(__file__))
REPLAY_DIR = os.path.join(HERE, "replay_runs")
os.makedirs(REPLAY_DIR, exist_ok=True)

BENCHMARK_YF = "^CRSLDX"   # Nifty 500 — same denominator as live screeners


# ─── Date utilities ───────────────────────────────────────────────────────────
def _validate_date(s: str) -> str:
    """Accept YYYY-MM-DD; raise ValueError otherwise. Returns the same string."""
    from datetime import date as _date
    _date.fromisoformat(s)
    return s


def _add_trading_days(start_iso: str, n: int, df_bench: pd.DataFrame) -> Optional[str]:
    """Return the date N trading days after start_iso, using bench bar dates as
    the trading calendar. Returns None if not enough bars exist after start.
    """
    if df_bench is None or df_bench.empty:
        return None
    try:
        idx = df_bench.index
        if hasattr(idx, "tz") and idx.tz is not None:
            idx = idx.tz_localize(None)
        future = [d for d in idx if d.strftime("%Y-%m-%d") > start_iso]
        if len(future) < n:
            return None
        return future[n - 1].strftime("%Y-%m-%d")
    except Exception:
        return None


def _close_on_or_before(df: pd.DataFrame, iso_date: str) -> Optional[float]:
    if df is None or df.empty or "Close" not in df.columns:
        return None
    try:
        sliced = df.loc[:iso_date]
        if sliced.empty:
            return None
        return float(sliced["Close"].iloc[-1])
    except Exception:
        return None


# ─── Forward returns table ────────────────────────────────────────────────────
def forward_returns(symbols: list[str], as_of: str, forward_days: int = 30) -> pd.DataFrame:
    """For each symbol return: Symbol, Entry_Close, Forward_Close, Return_pct,
    Forward_Date, Max_Drawdown_pct, Max_Runup_pct, Status.

    v2.3 E-5: Max_Drawdown_pct = worst intra-period decline from entry close
    (negative number; 0 if price never went below entry). Max_Runup_pct = best
    intra-period gain from entry close. These measure the *quality* of returns —
    a +5% endpoint return that first visited -15% is very different from one
    that went smoothly upward.

    data_provider must be in LIVE mode (pin cleared) so we can see bars after as_of.
    """
    _validate_date(as_of)
    if _dp.get_pinned_date() is not None:
        raise RuntimeError("forward_returns: data_provider is pinned; clear it first")

    df_bench = _dp.fetch_ohlcv(BENCHMARK_YF, period="2y", interval="1d")
    forward_iso = _add_trading_days(as_of, forward_days, df_bench)

    rows = []
    for sym in symbols:
        df = _dp.fetch_ohlcv(sym, period="2y", interval="1d")
        entry = _close_on_or_before(df, as_of)
        exit_  = _close_on_or_before(df, forward_iso) if forward_iso else None
        if entry is None:
            rows.append({"Symbol": sym, "Entry_Close": None, "Forward_Close": None,
                          "Return_pct": None, "Forward_Date": forward_iso,
                          "Max_Drawdown_pct": None, "Max_Runup_pct": None,
                          "Status": "no entry data"})
            continue
        if exit_ is None:
            rows.append({"Symbol": sym, "Entry_Close": round(entry, 2),
                          "Forward_Close": None, "Return_pct": None,
                          "Forward_Date": forward_iso,
                          "Max_Drawdown_pct": None, "Max_Runup_pct": None,
                          "Status": "forward window not yet elapsed"})
            continue
        ret_pct = (exit_ - entry) / entry * 100 if entry > 0 else None

        # v2.3 E-5: compute intra-period max drawdown and max runup
        max_dd_pct = None
        max_runup_pct = None
        try:
            if df is not None and not df.empty and forward_iso and entry > 0:
                # Slice the forward window: bars after as_of up to forward_iso
                idx = df.index
                if hasattr(idx, "tz") and idx.tz is not None:
                    idx = idx.tz_localize(None)
                    df_copy = df.copy()
                    df_copy.index = idx
                else:
                    df_copy = df
                window = df_copy.loc[as_of:forward_iso]
                if len(window) > 1:
                    # Skip the entry bar (first bar), use bars after
                    window = window.iloc[1:]
                    if "Low" in window.columns and "High" in window.columns:
                        lowest = float(window["Low"].min())
                        highest = float(window["High"].max())
                        max_dd_pct = round((lowest - entry) / entry * 100, 2)
                        max_runup_pct = round((highest - entry) / entry * 100, 2)
        except Exception:
            pass

        rows.append({
            "Symbol":           sym,
            "Entry_Close":      round(entry, 2),
            "Forward_Close":    round(exit_, 2),
            "Return_pct":       round(ret_pct, 2) if ret_pct is not None else None,
            "Forward_Date":     forward_iso,
            "Max_Drawdown_pct": max_dd_pct,
            "Max_Runup_pct":    max_runup_pct,
            "Status":           "OK",
        })
    return pd.DataFrame(rows)


# ─── v2.6 (2026-05-21) — Realistic execution simulation ─────────────────────
# Adds bar-by-bar SL/T1/T2/trail tracking + Indian commission+slippage modeling.
# Used by validation harness when picks DataFrame has SL_pct/T1_pct/T2_pct cols.

COST_PER_LEG_DEFAULT = 0.10   # 0.10% per leg (STT + brokerage + slippage on liquid Nifty 500)

# v2.8 (2026-05-21): catalyst-aware forward windows.
# Why: a single 30-day forward window measures positional / accumulation /
# recovery setups over a fraction of their design horizon and produces
# meaningless SL-hit rates. Per CLAUDE.md: Swing = 8-12 weeks, Positional =
# 6-8 months. The numbers below are mid-points of those design horizons.
# This dict is the canonical mapping; validation.py reads it via _replay.FWD_DAYS_BY_CATALYST.
FWD_DAYS_BY_CATALYST: dict[str, int] = {
    # Positional (Stage 1->2 accumulation + breakouts) — 4-6 month evaluation
    "POS-BO":         120,
    "POS-ACCUM":      180,
    # Wyckoff base-builds — multi-month structures
    "WYC-SPRING":     120,
    "WYC-SOS":        120,
    "WYC-JAC":        120,
    "WYC-SPRING+SOS": 120,
    # Recovery / mean-reversion — 3 months to play out
    "REV-CB":          90,
    "REV-RS":          90,
    "REV-EARLY":       90,
    # Swing — short window, matches design
    "SWG-BO":          30,
    # SWG-PB: 60d (8-12wk per Jay's design). A pullback first has to COMPLETE,
    # then the swing runs — 30d cut it off mid-resolution (window mismatch).
    "SWG-PB":          60,
    "SWG-GAP":         30,
    "SWG-REV":         30,
}


def fwd_days_for_catalyst(cat: str | None, default: int = 30) -> int:
    if not cat:
        return default
    return FWD_DAYS_BY_CATALYST.get(str(cat).upper().strip(), default)

def _simulate_one_trade(df_d: pd.DataFrame, entry_idx_pos: int, entry_price: float,
                         sl_price: float, t1_price: Optional[float], t2_price: Optional[float],
                         t1_qty_pct: int, t2_qty_pct: int,
                         max_bars: int, trail_atr_mult: float = 4.5,
                         atr_len: int = 14, cost_pct: float = COST_PER_LEG_DEFAULT) -> dict:
    """Simulate one trade bar-by-bar. Returns {realized_pct, exit_reason, days_held,
    hit_sl, hit_t1, hit_t2, max_dd_pct, max_runup_pct}."""
    if df_d is None or df_d.empty or entry_idx_pos < 0 or entry_idx_pos >= len(df_d):
        return {"realized_pct": None, "exit_reason": "no entry", "days_held": 0,
                 "hit_sl": False, "hit_t1": False, "hit_t2": False,
                 "max_dd_pct": None, "max_runup_pct": None}

    # Bars AFTER the entry bar, capped at max_bars
    end_pos = min(entry_idx_pos + 1 + max_bars, len(df_d))
    window = df_d.iloc[entry_idx_pos + 1 : end_pos]
    if window.empty:
        return {"realized_pct": 0.0, "exit_reason": "no forward bars", "days_held": 0,
                 "hit_sl": False, "hit_t1": False, "hit_t2": False,
                 "max_dd_pct": 0.0, "max_runup_pct": 0.0}

    # Open position tracking — qty in % units (start 100%)
    qty_open = 100.0
    realized_pnl_pct = 0.0   # cumulative realized P&L as % of entry capital
    hit_sl = hit_t1 = hit_t2 = False
    hit_initial_sl = hit_trail_sl = False   # v2.9: distinguish initial SL (loss) from trail SL (often profit-protect)
    exit_reason = ""
    # Trailing stop — start = sl_price. Update via Chandelier-style ratchet.
    trail_sl = sl_price
    highest_close = entry_price
    # ATR for trail update
    h, l, c = df_d["High"], df_d["Low"], df_d["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr_series = tr.rolling(atr_len).mean()
    # Track DD + runup
    lowest_low = float("inf")
    highest_high = -float("inf")

    days_held = 0
    final_exit_price = None
    for i, (idx, row) in enumerate(window.iterrows()):
        days_held = i + 1
        bar_low  = float(row["Low"])
        bar_high = float(row["High"])
        bar_close = float(row["Close"])
        lowest_low = min(lowest_low, bar_low)
        highest_high = max(highest_high, bar_high)

        # Update trailing stop (Chandelier — only ratchets up)
        atr_now = float(atr_series.iloc[entry_idx_pos + 1 + i]) if entry_idx_pos + 1 + i < len(atr_series) else None
        if atr_now is not None and not np.isnan(atr_now):
            new_trail = highest_close - atr_now * trail_atr_mult
            trail_sl = max(trail_sl, new_trail)

        # Order priority on a single bar: SL → T1 → T2 (conservative — assume worst case if bar spans both)
        # If bar's low touched SL: full exit
        if bar_low <= trail_sl and qty_open > 0:
            exit_at = trail_sl
            pnl_pct_this = (exit_at - entry_price) / entry_price * 100 * (qty_open / 100.0)
            realized_pnl_pct += pnl_pct_this
            qty_open = 0
            hit_sl = True
            # v2.9: split — initial-SL is a true loss; trail-SL can be a profit exit
            if trail_sl == sl_price:
                hit_initial_sl = True
                exit_reason = "SL hit"
            else:
                hit_trail_sl = True
                exit_reason = "Trail SL"
            final_exit_price = exit_at
            break

        # If bar's high touched T1: partial exit
        if t1_price is not None and bar_high >= t1_price and not hit_t1 and qty_open > 0:
            exit_at = t1_price
            exit_qty = min(qty_open, float(t1_qty_pct))
            pnl_pct_this = (exit_at - entry_price) / entry_price * 100 * (exit_qty / 100.0)
            realized_pnl_pct += pnl_pct_this
            qty_open -= exit_qty
            hit_t1 = True
            # After T1, move trail to breakeven
            trail_sl = max(trail_sl, entry_price)

        # If bar's high touched T2: partial exit
        if t2_price is not None and bar_high >= t2_price and not hit_t2 and qty_open > 0:
            exit_at = t2_price
            exit_qty = min(qty_open, float(t2_qty_pct))
            pnl_pct_this = (exit_at - entry_price) / entry_price * 100 * (exit_qty / 100.0)
            realized_pnl_pct += pnl_pct_this
            qty_open -= exit_qty
            hit_t2 = True

        highest_close = max(highest_close, bar_close)

    # If still open at end of window, mark-to-market at final close
    if qty_open > 0:
        final_close = float(window["Close"].iloc[-1])
        pnl_pct_this = (final_close - entry_price) / entry_price * 100 * (qty_open / 100.0)
        realized_pnl_pct += pnl_pct_this
        if not exit_reason:
            exit_reason = "Time expiry"
        final_exit_price = final_close

    # Apply commission + slippage: 1 entry + (entry/exit cycles = 1 if all SL, more if T1/T2 hits)
    # Conservative: 1 entry leg + 1 final exit leg + 1 leg per partial fill
    n_legs = 2 + (1 if hit_t1 else 0) + (1 if hit_t2 else 0)
    cost_drag = n_legs * cost_pct
    realized_pnl_pct -= cost_drag

    max_dd_pct = round((lowest_low - entry_price) / entry_price * 100, 2) if lowest_low != float("inf") else 0.0
    max_runup_pct = round((highest_high - entry_price) / entry_price * 100, 2) if highest_high != -float("inf") else 0.0

    return {
        "realized_pct":  round(realized_pnl_pct, 2),
        "exit_reason":   exit_reason,
        "days_held":     days_held,
        "hit_sl":        hit_sl,           # v2.9: kept for back-compat (true for ANY stop hit)
        "hit_initial_sl": hit_initial_sl,  # v2.9: true loss — stopped at entry SL
        "hit_trail_sl":  hit_trail_sl,     # v2.9: trail caught — often profit-protect
        "hit_t1":        hit_t1,
        "hit_t2":        hit_t2,
        "final_exit_price": round(final_exit_price, 2) if final_exit_price else None,
        "max_dd_pct":    max_dd_pct,
        "max_runup_pct": max_runup_pct,
        "cost_drag_pct": round(cost_drag, 3),
    }


def forward_returns_with_exits(picks_df: pd.DataFrame, as_of: str,
                                  forward_days: int = 30,
                                  cost_pct: float = COST_PER_LEG_DEFAULT,
                                  use_catalyst_windows: bool = False) -> pd.DataFrame:
    """Bar-by-bar simulation with SL/T1/T2/trail + commission.

    picks_df must have columns: Symbol, Entry, SL_pct, T1_pct, T2_pct (optional T1_R, T2_R).

    v2.8 (2026-05-21): when `use_catalyst_windows=True`, each pick's forward
    window is determined by its `Catalyst` column via FWD_DAYS_BY_CATALYST,
    and the per-trade benchmark return is computed over the same horizon.
    Output rows include `forward_days_used` and `Benchmark_Matched_pct` so
    the caller can compute per-trade alpha = Return_pct - Benchmark_Matched_pct.
    """
    _validate_date(as_of)
    if _dp.get_pinned_date() is not None:
        raise RuntimeError("forward_returns_with_exits: data_provider is pinned; clear it first")
    if picks_df is None or picks_df.empty:
        return pd.DataFrame()

    # Fetch benchmark with enough horizon for the longest possible window
    longest = max([forward_days] + list(FWD_DAYS_BY_CATALYST.values())) if use_catalyst_windows else forward_days
    bench_period = "2y" if longest <= 250 else "3y"
    df_bench_raw = _dp.fetch_ohlcv(BENCHMARK_YF, period=bench_period, interval="1d")
    bench_idx = df_bench_raw.index.tz_localize(None) if hasattr(df_bench_raw.index, "tz") and df_bench_raw.index.tz is not None else df_bench_raw.index
    df_bench = df_bench_raw.copy(); df_bench.index = bench_idx

    has_targets = all(c in picks_df.columns for c in ["Entry", "SL_pct", "T1_pct"])
    if not has_targets:
        # Fall back to legacy close-to-close
        return forward_returns(picks_df["Symbol"].astype(str).tolist(), as_of, forward_days)

    def _bench_matched_return(as_of_str: str, fwd_days: int) -> Optional[float]:
        """Compute benchmark close-to-close return over `fwd_days` from as_of."""
        try:
            entry_idx_b = df_bench.index.searchsorted(pd.Timestamp(as_of_str), side="right") - 1
            exit_idx_b  = min(entry_idx_b + fwd_days, len(df_bench) - 1)
            if entry_idx_b < 0 or exit_idx_b <= entry_idx_b:
                return None
            entry_b = float(df_bench["Close"].iloc[entry_idx_b])
            exit_b  = float(df_bench["Close"].iloc[exit_idx_b])
            return round(100.0 * (exit_b - entry_b) / entry_b, 2) if entry_b > 0 else None
        except Exception:
            return None

    rows = []
    for _, pick in picks_df.iterrows():
        sym = str(pick["Symbol"])
        cat = str(pick.get("Catalyst", "")).upper().strip()

        # v2.8: choose forward window per pick
        if use_catalyst_windows:
            fwd = fwd_days_for_catalyst(cat, default=forward_days)
        else:
            fwd = forward_days

        try:
            df = _dp.fetch_ohlcv(sym, period=("3y" if fwd > 250 else "2y"), interval="1d")
        except Exception:
            df = pd.DataFrame()
        if df is None or df.empty:
            rows.append({"Symbol": sym, "Return_pct": None, "Exit_Reason": "no data",
                          "forward_days_used": fwd, "Catalyst_used": cat})
            continue
        # Locate entry bar index
        try:
            idx = df.index.tz_localize(None) if hasattr(df.index, "tz") and df.index.tz is not None else df.index
            df2 = df.copy(); df2.index = idx
            entry_pos = df2.index.searchsorted(pd.Timestamp(as_of), side="right") - 1
            if entry_pos < 0:
                rows.append({"Symbol": sym, "Return_pct": None, "Exit_Reason": "no entry bar",
                              "forward_days_used": fwd, "Catalyst_used": cat})
                continue
            entry_price = float(df2["Close"].iloc[entry_pos])
        except Exception as e:
            rows.append({"Symbol": sym, "Return_pct": None, "Exit_Reason": f"err: {e}",
                          "forward_days_used": fwd, "Catalyst_used": cat})
            continue

        sl_pct = float(pick.get("SL_pct", 3.0) or 3.0)
        t1_pct = pick.get("T1_pct")
        t2_pct = pick.get("T2_pct")
        sl_price = entry_price * (1 - sl_pct / 100)
        t1_price = entry_price * (1 + float(t1_pct) / 100) if t1_pct is not None and not pd.isna(t1_pct) else None
        t2_price = entry_price * (1 + float(t2_pct) / 100) if t2_pct is not None and not pd.isna(t2_pct) else None

        # Partial-take sizes by catalyst
        if cat.startswith("SWG-GAP") or cat == "SWG-REV":
            t1_qty = 50; t2_qty = 50
        elif cat.startswith("SWG"):
            t1_qty = 33; t2_qty = 33
        else:  # POS, WYC, REV
            t1_qty = 25; t2_qty = 25

        res = _simulate_one_trade(df2, entry_pos, entry_price, sl_price,
                                     t1_price, t2_price, t1_qty, t2_qty,
                                     max_bars=fwd, cost_pct=cost_pct)

        bench_matched = _bench_matched_return(as_of, fwd)
        alpha_matched = (round(res["realized_pct"] - bench_matched, 2)
                          if (res["realized_pct"] is not None and bench_matched is not None)
                          else None)

        rows.append({
            "Symbol":               sym,
            "Catalyst_used":        cat,
            "forward_days_used":    fwd,
            "Entry_Close":          round(entry_price, 2),
            "SL_price":             round(sl_price, 2),
            "T1_price":             round(t1_price, 2) if t1_price else None,
            "T2_price":             round(t2_price, 2) if t2_price else None,
            "Return_pct":           res["realized_pct"],
            "Benchmark_Matched_pct": bench_matched,
            "Alpha_Matched_pct":    alpha_matched,
            "Exit_Reason":          res["exit_reason"],
            "Days_Held":            res["days_held"],
            "Hit_SL":               res["hit_sl"],
            "Hit_Initial_SL":       res.get("hit_initial_sl", False),  # v2.9
            "Hit_Trail_SL":         res.get("hit_trail_sl",   False),  # v2.9
            "Hit_T1":               res["hit_t1"],
            "Hit_T2":               res["hit_t2"],
            "Final_Exit_Price":     res["final_exit_price"],
            "Max_Drawdown_pct":     res["max_dd_pct"],
            "Max_Runup_pct":        res["max_runup_pct"],
            "Cost_Drag_pct":        res["cost_drag_pct"],
            "Status":               "OK" if res["realized_pct"] is not None else "no result",
        })
    return pd.DataFrame(rows)


# ─── Summary ──────────────────────────────────────────────────────────────────
def _summarize(perf: pd.DataFrame, benchmark_pct: Optional[float]) -> dict:
    if perf is None or perf.empty:
        return {"n": 0, "n_complete": 0}
    complete = perf.dropna(subset=["Return_pct"])
    n_complete = len(complete)
    if n_complete == 0:
        return {"n": len(perf), "n_complete": 0,
                "note": "forward window not yet elapsed"}
    rets = complete["Return_pct"].astype(float)
    wins = (rets > 0).sum()

    result = {
        "n":                len(perf),
        "n_complete":       n_complete,
        "win_rate_pct":     round(wins / n_complete * 100, 1),
        "avg_return_pct":   round(float(rets.mean()), 2),
        "median_return_pct": round(float(rets.median()), 2),
        "best_pct":         round(float(rets.max()), 2),
        "worst_pct":        round(float(rets.min()), 2),
        "alpha_vs_bench":  (round(float(rets.mean()) - benchmark_pct, 2)
                              if benchmark_pct is not None else None),
        "benchmark_pct":    round(benchmark_pct, 2) if benchmark_pct is not None else None,
    }

    # v2.3 E-5: add drawdown quality metrics if available
    if "Max_Drawdown_pct" in complete.columns:
        dd = complete["Max_Drawdown_pct"].dropna()
        if len(dd) > 0:
            dd_vals = dd.astype(float)
            avg_dd = float(dd_vals.mean())
            result["avg_max_drawdown_pct"]   = round(avg_dd, 2)
            result["worst_max_drawdown_pct"] = round(float(dd_vals.min()), 2)
            # Risk-reward ratio: avg return ÷ avg |drawdown| (higher = better)
            if avg_dd < 0:
                result["risk_reward_ratio"]  = round(float(rets.mean()) / abs(avg_dd), 2)
            else:
                result["risk_reward_ratio"]  = None  # no drawdowns = no ratio needed
    if "Max_Runup_pct" in complete.columns:
        ru = complete["Max_Runup_pct"].dropna()
        if len(ru) > 0:
            result["avg_max_runup_pct"]  = round(float(ru.astype(float).mean()), 2)
            result["best_max_runup_pct"] = round(float(ru.astype(float).max()), 2)

    # v2.6: Risk-adjusted metrics (Sharpe, Sortino, Calmar) on per-pick returns
    # Returns are per-trade %; annualize assuming 30d holding period (12 trades/yr).
    try:
        rets_arr = rets.values
        if len(rets_arr) >= 2:
            mean_ret = float(np.mean(rets_arr))
            std_ret  = float(np.std(rets_arr, ddof=1))
            downside = rets_arr[rets_arr < 0]
            dsd      = float(np.std(downside, ddof=1)) if len(downside) >= 2 else 0.0
            # 12 trades/year annualization (assuming ~30d hold). Risk-free ~6.5%/yr = 0.54%/mo.
            rf_per_trade = 0.54
            ann_factor   = np.sqrt(12)
            if std_ret > 0:
                result["sharpe_ratio"]  = round(((mean_ret - rf_per_trade) / std_ret) * ann_factor, 2)
            if dsd > 0:
                result["sortino_ratio"] = round(((mean_ret - rf_per_trade) / dsd) * ann_factor, 2)
            # Calmar: annualized return / max DD (use worst max_dd_pct from picks)
            if "Max_Drawdown_pct" in complete.columns:
                worst_dd = complete["Max_Drawdown_pct"].astype(float).min()
                if worst_dd < 0:
                    ann_ret = mean_ret * 12  # rough annualization
                    result["calmar_ratio"] = round(ann_ret / abs(worst_dd), 2)
    except Exception:
        pass

    return result


def _benchmark_forward_pct(as_of: str, forward_days: int) -> Optional[float]:
    """% return of ^CRSLDX from as_of close to as_of+forward_days close.
    Requires data_provider in LIVE mode."""
    df = _dp.fetch_ohlcv(BENCHMARK_YF, period="2y", interval="1d")
    forward_iso = _add_trading_days(as_of, forward_days, df)
    if not forward_iso:
        return None
    a = _close_on_or_before(df, as_of)
    b = _close_on_or_before(df, forward_iso)
    if a is None or b is None or a <= 0:
        return None
    return (b - a) / a * 100


# ─── Bull screener replay ─────────────────────────────────────────────────────
def run_bull_replay(as_of: str, forward_days: int = 30,
                      symbols: Optional[list[str]] = None) -> dict:
    """Run the bull screener as-of `as_of`, then grade picks against their
    actual N-day forward returns.

    Returns the structured result dict (see module docstring).
    """
    _validate_date(as_of)
    t0 = time.time()
    out_name = f"replay_bull_{as_of}.csv"
    out_path = os.path.join(REPLAY_DIR, out_name)

    # Pin the data view, run the screener, then unpin so forward fetches see today.
    _dp.set_pinned_date(as_of)
    try:
        import bull_screener as _bs
        # strict=True: backtest replay needs only catalyst-firing rows for
        # forward-return analysis. Tracker mode (default since 2026-05-18) would
        # include non-firing rows and corrupt the win-rate / avg-return stats.
        picks = _bs.run_bull_screener(symbols=symbols, out_file=out_path, strict=True)
    finally:
        _dp.set_pinned_date(None)

    perf = pd.DataFrame()
    summary = {"n": 0, "n_complete": 0}
    bench_pct = _benchmark_forward_pct(as_of, forward_days)
    if picks is not None and not picks.empty and "Symbol" in picks.columns:
        perf = forward_returns(picks["Symbol"].astype(str).tolist(),
                                as_of=as_of, forward_days=forward_days)
        summary = _summarize(perf, bench_pct)
        # Persist combined picks + performance
        merged = picks.merge(perf, on="Symbol", how="left")
        merged.to_csv(out_path, index=False)

    return {
        "as_of":          as_of,
        "forward_days":   forward_days,
        "ran_at":         datetime.now().isoformat(timespec="seconds"),
        "duration_s":     round(time.time() - t0, 2),
        "picks":          picks if picks is not None else pd.DataFrame(),
        "performance":    perf,
        "summary":        summary,
        "benchmark_pct":  round(bench_pct, 2) if bench_pct is not None else None,
        "out_csv":        out_path,
    }


# ─── Recovery screener replay ─────────────────────────────────────────────────
def run_recovery_replay(as_of: str, forward_days: int = 30,
                          symbols: Optional[list[str]] = None) -> dict:
    """Run the recovery screener as-of `as_of`, grade picks N days forward.

    `symbols` lets the caller bypass the Chartink pre-filter CSVs (which only
    exist in their *current* state) — pass a fixed historical universe like
    Nifty 100 so the screener applies its technical/regime gates as-of-date
    on a stable basket.
    """
    _validate_date(as_of)
    t0 = time.time()
    out_name = f"replay_recovery_{as_of}.csv"
    out_path = os.path.join(REPLAY_DIR, out_name)

    _dp.set_pinned_date(as_of)
    try:
        import recovery_screener as _rs
        # strict=True: backtest replay needs only signal-firing rows (Signal>=1)
        # for forward-return analysis.
        picks = _rs.run_recovery_screener(symbols=symbols, out_file=out_path, strict=True)
    finally:
        _dp.set_pinned_date(None)

    perf = pd.DataFrame()
    summary = {"n": 0, "n_complete": 0}
    bench_pct = _benchmark_forward_pct(as_of, forward_days)
    if picks is not None and not picks.empty and "Symbol" in picks.columns:
        perf = forward_returns(picks["Symbol"].astype(str).tolist(),
                                as_of=as_of, forward_days=forward_days)
        summary = _summarize(perf, bench_pct)
        merged = picks.merge(perf, on="Symbol", how="left")
        merged.to_csv(out_path, index=False)

    return {
        "as_of":          as_of,
        "forward_days":   forward_days,
        "ran_at":         datetime.now().isoformat(timespec="seconds"),
        "duration_s":     round(time.time() - t0, 2),
        "picks":          picks if picks is not None else pd.DataFrame(),
        "performance":    perf,
        "summary":        summary,
        "benchmark_pct":  round(bench_pct, 2) if bench_pct is not None else None,
        "out_csv":        out_path,
    }


__all__ = ["run_bull_replay", "run_recovery_replay",
           "forward_returns", "REPLAY_DIR"]


def main() -> int:
    """CLI: python replay.py --as-of YYYY-MM-DD [--screener bull|recovery] [--forward N]"""
    import argparse, json
    p = argparse.ArgumentParser(description="Screener replay engine")
    p.add_argument("--as-of",     dest="as_of",     required=True)
    p.add_argument("--screener",  default="bull",
                    choices=["bull", "recovery"])
    p.add_argument("--forward",   type=int, default=30,
                    help="Trading days to look forward (default 30)")
    p.add_argument("--symbols",   default=None,
                    help="Comma-separated symbol list (bull only); "
                         "default = the screener's standard input")
    args = p.parse_args()

    syms = [s.strip() for s in args.symbols.split(",")] if args.symbols else None

    if args.screener == "bull":
        result = run_bull_replay(args.as_of, args.forward, symbols=syms)
    else:
        result = run_recovery_replay(args.as_of, args.forward)

    print("=" * 68)
    print(f"  REPLAY @ {result['as_of']}  (forward {result['forward_days']}d)")
    print("=" * 68)
    print(f"  picks: {len(result['picks'])}  duration: {result['duration_s']}s")
    print(f"  output CSV: {result['out_csv']}")
    print()
    print("  Summary:")
    print(json.dumps(result['summary'], indent=4))
    if result.get("benchmark_pct") is not None:
        print(f"  benchmark forward {args.forward}d: {result['benchmark_pct']:+.2f}%")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
