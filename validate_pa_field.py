"""
validate_pa_field.py — Per-detector effectiveness validator for the PA field.

Runs the v67.4.9 PA cascade (via pa_field_validator.compute_pa_detectors)
across an NSE universe (Nifty 100 / Nifty 500), measures forward returns at
catalyst-aware horizons (FWD_DAYS_BY_PA_STATE), computes alpha vs ^CRSLDX
benchmark, and produces a per-detector effectiveness report.

Honors the project's locked discipline (memory/validation_window_mismatch_warning.md):
every detector firing is measured on its own design horizon — never a single
30-day window for all states.

Usage
-----
    python validate_pa_field.py --universe nifty500 --period 5y
    python validate_pa_field.py --universe nifty100 --period 3y --max-symbols 50
    python validate_pa_field.py --universe nifty500 --period 5y --bootstrap 5000

Output
------
    PA_FIELD_VALIDATION_<UNIVERSE>_<TIMESTAMP>.md   (Markdown report)
    PA_FIELD_VALIDATION_<UNIVERSE>_<TIMESTAMP>.csv  (per-trade detail)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

import data_provider as dp
from pa_field_validator import (
    FWD_DAYS_BY_PA_STATE,
    compute_pa_detectors,
)

# All detectors we want to evaluate (column names in compute_pa_detectors output).
# Mapped to the FWD_DAYS_BY_PA_STATE key used for horizon lookup.
DETECTORS: dict[str, str] = {
    "pa_vcp_bo":          "VCP_BO",
    "pa_gap_up_bo":       "GAP_UP_BO",
    "pa_s2_launch":       "STAGE_2_LAUNCH",
    "pa_50sma_undercut":  "UNDERCUT_50SMA",
    "pa_hammer_at_200":   "HAMMER_AT_200SMA",
    "pa_hammer_at_50":    "HAMMER_AT_50SMA",
    "pa_outside_bull":    "OUTSIDE_BAR_BULL",
    "pa_ib_nr7":          "IB_NR7_COIL",
    "pa_pocket":          "POCKET_PIVOT",
    "pa_spring":          "SPRING",
    "pa_hammer":          "HAMMER_REVERSAL",
    "pa_bull_engulf":     "BULL_ENGULF",
    "pa_3bar_rev":        "THREE_BAR_REV",
    "pa_failed_bo":       "FAILED_BREAKOUT",
    "pa_distrib":         "DISTRIBUTION_DAY",
    "pa_shooting_star":   "SHOOTING_STAR_RESIST",
}

BENCHMARK_SYMBOL = "^CRSLDX"  # Nifty 500 — per project convention

# Bearish/warning states predict UNDERperformance. For these, the win
# condition is stock_ret < bench_ret, and the meaningful "predictive alpha"
# is sign-flipped: predictive_alpha = bench_ret - stock_ret.
# See memory/bull_market_base_rate_warning.md — bearish detectors otherwise
# look spuriously profitable in bull markets via the universe-wide base rate.
BEARISH_STATES: set[str] = {
    "FAILED_BREAKOUT",
    "DISTRIBUTION_DAY",
    "SHOOTING_STAR_RESIST",
    "BEAR_ENGULF",
}


def load_universe(name: str) -> list[str]:
    """Load symbol list for the named universe."""
    if name.lower() in ("n500", "nifty500"):
        path = "nifty500_symbols.json"
    elif name.lower() in ("n100", "nifty100"):
        # Use first 100 of nifty500 (good liquid proxy if no dedicated file)
        path = "nifty500_symbols.json"
    else:
        raise ValueError(f"Unknown universe: {name}")

    with open(path) as f:
        syms = json.load(f)

    if name.lower() in ("n100", "nifty100"):
        syms = syms[:100]

    # Strip .NS suffix — fetch_ohlcv normalizes
    return [s.replace(".NS", "").replace(".BO", "") for s in syms]


def fetch_benchmark(period: str) -> pd.DataFrame:
    """Fetch ^CRSLDX benchmark series."""
    print(f"[validator] Fetching benchmark {BENCHMARK_SYMBOL} ({period})...")
    bench = dp.fetch_ohlcv(BENCHMARK_SYMBOL, period=period, interval="1d")
    if bench is None or bench.empty:
        raise RuntimeError(f"Failed to fetch benchmark {BENCHMARK_SYMBOL}")
    print(f"[validator] Benchmark loaded: {len(bench)} bars, "
          f"{bench.index.min().date()} to {bench.index.max().date()}")
    return bench


@dataclass
class TradeRecord:
    symbol: str
    detector: str
    state: str
    entry_date: pd.Timestamp
    horizon: int
    entry_price: float
    exit_date: pd.Timestamp
    exit_price: float
    stock_ret_pct: float
    bench_ret_pct: float
    alpha_pct: float            # raw stock_ret - bench_ret
    predictive_alpha_pct: float # sign-flipped for bearish states (the metric to rank on)
    direction: str              # 'bullish' or 'bearish'
    regime: str                 # 'bull' or 'bear' — benchmark above/below 200d SMA at entry


def process_symbol(
    symbol: str,
    period: str,
    benchmark: pd.DataFrame,
    bench_sma200: pd.Series,
) -> list[TradeRecord]:
    """Compute detector firings for one symbol, return one TradeRecord per firing."""
    try:
        raw = dp.fetch_ohlcv(symbol, period=period, interval="1d")
    except Exception as e:
        return []
    if raw is None or raw.empty or len(raw) < 252:
        return []

    try:
        df = compute_pa_detectors(raw)
    except Exception as e:
        print(f"[validator] {symbol}: compute failed: {e}")
        return []

    close = df["Close"] if "Close" in df.columns else df["close"]
    if "Close" not in df.columns and "close" not in df.columns:
        return []

    bench_close = benchmark["Close"]

    records: list[TradeRecord] = []

    for det_col, state_name in DETECTORS.items():
        if det_col not in df.columns:
            continue
        horizon = FWD_DAYS_BY_PA_STATE.get(state_name, 30)
        firings = df[df[det_col].fillna(False).astype(bool)]
        for entry_date in firings.index:
            try:
                # Need at least `horizon` more bars
                entry_idx = df.index.get_loc(entry_date)
                if entry_idx + horizon >= len(df):
                    continue
                exit_idx = entry_idx + horizon
                exit_date = df.index[exit_idx]
                entry_price = float(close.iloc[entry_idx])
                exit_price = float(close.iloc[exit_idx])
                if entry_price <= 0 or pd.isna(entry_price) or pd.isna(exit_price):
                    continue
                stock_ret = (exit_price - entry_price) / entry_price * 100.0

                # Benchmark matched-window return
                # Use as-of join (nearest <= entry_date / exit_date in benchmark)
                try:
                    b_entry = bench_close.asof(entry_date)
                    b_exit = bench_close.asof(exit_date)
                except Exception:
                    continue
                if pd.isna(b_entry) or pd.isna(b_exit) or b_entry <= 0:
                    continue
                bench_ret = (b_exit - b_entry) / b_entry * 100.0
                alpha = stock_ret - bench_ret
                is_bearish = state_name in BEARISH_STATES
                predictive_alpha = -alpha if is_bearish else alpha
                direction = "bearish" if is_bearish else "bullish"

                # Regime classification: benchmark above/below its 200d SMA at entry
                try:
                    bsma = bench_sma200.asof(entry_date)
                except Exception:
                    bsma = float("nan")
                if pd.isna(bsma) or bsma <= 0 or pd.isna(b_entry):
                    regime = "unknown"
                else:
                    regime = "bull" if b_entry > bsma else "bear"

                records.append(TradeRecord(
                    symbol=symbol,
                    detector=det_col,
                    state=state_name,
                    entry_date=entry_date,
                    horizon=horizon,
                    entry_price=entry_price,
                    exit_date=exit_date,
                    exit_price=exit_price,
                    stock_ret_pct=stock_ret,
                    bench_ret_pct=bench_ret,
                    alpha_pct=alpha,
                    predictive_alpha_pct=predictive_alpha,
                    direction=direction,
                    regime=regime,
                ))
            except Exception:
                continue

    return records


def bootstrap_ci(values: np.ndarray, n: int = 5000, ci: float = 0.95,
                 seed: int = 42) -> tuple[float, float, float]:
    """Bootstrap CI for the mean. Returns (lower, upper, prob_positive)."""
    if len(values) == 0:
        return (float("nan"), float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    n_obs = len(values)
    means = np.empty(n)
    for i in range(n):
        sample = rng.choice(values, size=n_obs, replace=True)
        means[i] = sample.mean()
    lo = float(np.percentile(means, (1 - ci) / 2 * 100))
    hi = float(np.percentile(means, (1 + ci) / 2 * 100))
    prob_pos = float((means > 0).mean()) * 100.0
    return lo, hi, prob_pos


def aggregate_by_regime(records: list[TradeRecord], bootstrap_n: int) -> pd.DataFrame:
    """Per-(state, regime) aggregate. Returns long-format DataFrame."""
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame([{
        "state": r.state,
        "direction": r.direction,
        "regime": r.regime,
        "horizon": r.horizon,
        "pred_alpha": r.predictive_alpha_pct,
    } for r in records])

    out = []
    for (state, regime), grp in df.groupby(["state", "regime"]):
        pred_alphas = grp["pred_alpha"].to_numpy()
        n = len(pred_alphas)
        if n < 5:
            continue  # too few to report
        lo, hi, prob_pos = bootstrap_ci(pred_alphas, n=bootstrap_n)
        out.append({
            "state": state,
            "direction": grp["direction"].iloc[0],
            "regime": regime,
            "horizon_d": int(grp["horizon"].iloc[0]),
            "n_trades": n,
            "pred_alpha_pct": float(pred_alphas.mean()),
            "win_rate_pct": float((pred_alphas > 0).mean() * 100.0),
            "alpha_ci95_lo": lo,
            "alpha_ci95_hi": hi,
            "prob_alpha_pos_pct": prob_pos,
        })
    return pd.DataFrame(out)


def aggregate(records: list[TradeRecord], bootstrap_n: int) -> pd.DataFrame:
    """Per-state aggregate statistics."""
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame([{
        "state": r.state,
        "direction": r.direction,
        "horizon": r.horizon,
        "alpha": r.alpha_pct,
        "pred_alpha": r.predictive_alpha_pct,
        "stock_ret": r.stock_ret_pct,
        "bench_ret": r.bench_ret_pct,
    } for r in records])

    out = []
    for state, grp in df.groupby("state"):
        pred_alphas = grp["pred_alpha"].to_numpy()  # the metric to rank on
        raw_alphas = grp["alpha"].to_numpy()
        rets = grp["stock_ret"].to_numpy()
        n = len(pred_alphas)
        lo, hi, prob_pos = bootstrap_ci(pred_alphas, n=bootstrap_n)
        out.append({
            "state": state,
            "direction": grp["direction"].iloc[0],
            "horizon_d": int(grp["horizon"].iloc[0]),
            "n_trades": n,
            "pred_alpha_pct": float(pred_alphas.mean()),
            "pred_alpha_median_pct": float(np.median(pred_alphas)),
            "win_rate_pct": float((pred_alphas > 0).mean() * 100.0),
            "raw_alpha_pct": float(raw_alphas.mean()),
            "mean_ret_pct": float(rets.mean()),
            "alpha_ci95_lo": lo,
            "alpha_ci95_hi": hi,
            "prob_alpha_pos_pct": prob_pos,
        })
    return pd.DataFrame(out).sort_values("pred_alpha_pct", ascending=False)


def write_report(
    agg: pd.DataFrame,
    universe: str,
    period: str,
    n_symbols_ok: int,
    n_symbols_total: int,
    elapsed_s: float,
    bootstrap_n: int,
    output_path: str,
    regime_agg: Optional[pd.DataFrame] = None,
) -> None:
    """Write the markdown report mirroring BACKTEST_RESULTS_v2.docx style."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_trades = int(agg["n_trades"].sum()) if not agg.empty else 0

    lines = []
    lines.append(f"# PA Field Validation Report — {universe.upper()}")
    lines.append("")
    lines.append(f"**Generated:** {ts}")
    lines.append(f"**Universe:** {universe.upper()} ({n_symbols_ok}/{n_symbols_total} symbols loaded successfully)")
    lines.append(f"**Period:** {period} (catalyst-aware horizons per state)")
    lines.append(f"**Benchmark:** {BENCHMARK_SYMBOL}")
    lines.append(f"**Bootstrap iterations:** {bootstrap_n:,}")
    lines.append(f"**Total trades:** {total_trades:,}")
    lines.append(f"**Compute time:** {elapsed_s/60:.1f} min")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Per-State Predictive Effectiveness (sorted by predictive alpha)")
    lines.append("")
    lines.append("**Predictive alpha** is sign-aware: for bullish detectors, it's stock_ret − bench_ret. "
                 "For bearish detectors (predicting underperformance), it's bench_ret − stock_ret. "
                 "A positive predictive alpha means the detector's directional thesis paid off. "
                 "See memory/bull_market_base_rate_warning.md for why raw alpha alone misleads in bull markets.")
    lines.append("")

    if agg.empty:
        lines.append("**No trades generated.** Check universe and detector outputs.")
    else:
        lines.append("| State | Dir | Horizon (d) | N Trades | Pred Alpha % | Median % | Win Rate % | CI95 (lo, hi) | P>0 % | Raw α % |")
        lines.append("|---|:---:|---:|---:|---:|---:|---:|:---:|---:|---:|")
        for _, r in agg.iterrows():
            dir_icon = "🐻" if r['direction'] == 'bearish' else "🐂"
            lines.append(
                f"| **{r['state']}** | {dir_icon} | {r['horizon_d']} | {r['n_trades']:,} | "
                f"{r['pred_alpha_pct']:+.2f} | {r['pred_alpha_median_pct']:+.2f} | "
                f"{r['win_rate_pct']:.1f} | "
                f"({r['alpha_ci95_lo']:+.2f}, {r['alpha_ci95_hi']:+.2f}) | "
                f"{r['prob_alpha_pos_pct']:.0f} | "
                f"{r['raw_alpha_pct']:+.2f} |"
            )

    lines.append("")
    # Regime split section
    if regime_agg is not None and not regime_agg.empty:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Regime-Conditional Predictive Alpha")
        lines.append("")
        lines.append("Regime = benchmark close vs its 200-day SMA at entry date. "
                     "Bull = bench above 200d SMA; Bear = below. "
                     "Reveals whether detector edges hold across both regimes "
                     "or were artifacts of one regime only.")
        lines.append("")
        # Pivot to side-by-side bull / bear columns
        pivot = regime_agg.pivot_table(
            index=["state", "direction"], columns="regime",
            values=["n_trades", "pred_alpha_pct", "win_rate_pct"],
            aggfunc="first",
        )
        lines.append("| State | Dir | Bull N | Bull α % | Bull WR % | Bear N | Bear α % | Bear WR % |")
        lines.append("|---|:---:|---:|---:|---:|---:|---:|---:|")
        # Sort by mean of bull+bear pred alpha
        sort_key = []
        for idx in pivot.index:
            try:
                b_a = pivot.loc[idx, ("pred_alpha_pct", "bull")]
            except KeyError:
                b_a = float("nan")
            try:
                e_a = pivot.loc[idx, ("pred_alpha_pct", "bear")]
            except KeyError:
                e_a = float("nan")
            sort_key.append((idx, np.nanmean([b_a, e_a])))
        sort_key.sort(key=lambda x: -x[1] if not pd.isna(x[1]) else 999)
        for idx, _ in sort_key:
            state, direction = idx
            dir_icon = "🐻" if direction == "bearish" else "🐂"

            def get(col, regime):
                try:
                    v = pivot.loc[idx, (col, regime)]
                    return v if not pd.isna(v) else None
                except KeyError:
                    return None

            bull_n = get("n_trades", "bull")
            bull_a = get("pred_alpha_pct", "bull")
            bull_w = get("win_rate_pct", "bull")
            bear_n = get("n_trades", "bear")
            bear_a = get("pred_alpha_pct", "bear")
            bear_w = get("win_rate_pct", "bear")

            def fmt_n(x): return f"{int(x):,}" if x is not None else "—"
            def fmt_p(x): return f"{x:+.2f}" if x is not None else "—"
            def fmt_w(x): return f"{x:.1f}" if x is not None else "—"

            lines.append(
                f"| **{state}** | {dir_icon} | "
                f"{fmt_n(bull_n)} | {fmt_p(bull_a)} | {fmt_w(bull_w)} | "
                f"{fmt_n(bear_n)} | {fmt_p(bear_a)} | {fmt_w(bear_w)} |"
            )
        lines.append("")
        lines.append("**Reading:** if a detector's alpha is positive in BOTH regimes "
                     "(and CI doesn't straddle zero), it has regime-independent edge — "
                     "the strongest result. If alpha is positive in one regime and "
                     "negative or zero in the other, the edge is regime-conditional.")
        lines.append("")

    lines.append("## Interpretation Guide")
    lines.append("")
    lines.append("- **Mean Alpha:** stock return − benchmark return over horizon, averaged across all firings.")
    lines.append("- **Win Rate:** fraction of firings where alpha > 0.")
    lines.append("- **Alpha CI95:** bootstrap confidence interval for the mean alpha. If the interval excludes 0, the alpha is statistically distinguishable from random.")
    lines.append("- **P(α > 0):** probability the true mean alpha is positive, per bootstrap.")
    lines.append("- States with N < 30 should be read with care — small-sample noise.")
    lines.append("")
    lines.append("## Methodology Notes")
    lines.append("")
    lines.append("- One firing = one entry. Stock held for the state's design horizon (FWD_DAYS_BY_PA_STATE).")
    lines.append("- No SL/TP — raw signal alpha, not execution mechanics.")
    lines.append("- Forward window is **per-state** per the project's locked window-mismatch discipline.")
    lines.append("- Benchmark return measured over the same window as each stock trade.")
    lines.append("- No commission, no slippage modeled at this layer (use replay.py for that).")
    lines.append("- Multiple firings on the same symbol are independent — no position-overlap concurrency control.")
    lines.append("")
    lines.append("## Known Simplifications vs Dashboard")
    lines.append("")
    lines.append("- `dLockH` ≈ 20-bar rolling high shifted (vs dashboard's strict-trend locked high).")
    lines.append("- `stage2_up` proxy = `close > 30WMA AND 30WMA rising 4w` (vs full Weinstein stage classifier).")
    lines.append("- All other detectors verified faithful via v67.4.9/v1.1 cross-check on HDFCBANK.")
    lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default="nifty500", choices=["nifty100", "nifty500"])
    ap.add_argument("--period", default="5y", help="yfinance period: 1y, 2y, 3y, 5y, max")
    ap.add_argument("--max-symbols", type=int, default=0, help="0 = all")
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--output-prefix", default="PA_FIELD_VALIDATION")
    args = ap.parse_args()

    t0 = time.time()
    symbols = load_universe(args.universe)
    if args.max_symbols > 0:
        symbols = symbols[: args.max_symbols]
    print(f"[validator] Universe: {args.universe} — {len(symbols)} symbols")

    bench = fetch_benchmark(args.period)
    bench_close = bench["Close"]
    bench_sma200 = bench_close.rolling(200).mean()
    print(f"[validator] Benchmark 200d SMA computed for regime classification.")

    all_records: list[TradeRecord] = []
    n_ok = 0
    n_fail = 0
    for i, sym in enumerate(symbols, 1):
        recs = process_symbol(sym, args.period, bench, bench_sma200)
        if recs:
            n_ok += 1
            all_records.extend(recs)
        else:
            n_fail += 1
        if i % 25 == 0 or i == len(symbols):
            elapsed = time.time() - t0
            print(f"[validator] [{i:>3}/{len(symbols)}] ok={n_ok} fail={n_fail} "
                  f"trades={len(all_records):,} | {elapsed/60:.1f}m elapsed")

    print(f"\n[validator] Aggregating {len(all_records):,} trades...")
    agg = aggregate(all_records, bootstrap_n=args.bootstrap)
    regime_agg = aggregate_by_regime(all_records, bootstrap_n=args.bootstrap)
    elapsed = time.time() - t0

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = f"{args.output_prefix}_{args.universe}_{ts}.md"
    csv_path = f"{args.output_prefix}_{args.universe}_{ts}.csv"

    write_report(agg, args.universe, args.period, n_ok, len(symbols),
                 elapsed, args.bootstrap, md_path, regime_agg=regime_agg)

    # Per-trade detail CSV
    if all_records:
        df_trades = pd.DataFrame([{
            "symbol": r.symbol,
            "state": r.state,
            "direction": r.direction,
            "horizon_d": r.horizon,
            "entry_date": r.entry_date.date(),
            "exit_date": r.exit_date.date(),
            "entry_price": r.entry_price,
            "exit_price": r.exit_price,
            "stock_ret_pct": r.stock_ret_pct,
            "bench_ret_pct": r.bench_ret_pct,
            "alpha_pct": r.alpha_pct,
            "predictive_alpha_pct": r.predictive_alpha_pct,
            "regime": r.regime,
        } for r in all_records])
        df_trades.to_csv(csv_path, index=False)

    print(f"\n[validator] Done. {n_ok}/{len(symbols)} symbols, {len(all_records):,} trades, "
          f"{elapsed/60:.1f}m total.")
    print(f"[validator] Report: {md_path}")
    print(f"[validator] Trades: {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
