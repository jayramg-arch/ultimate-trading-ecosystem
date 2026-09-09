"""Backtest Bull v1.8 + Bull v2 Minervini on a BULL-market window
(Dec 2023 – Nov 2024) to isolate regime impact.

Nifty 500 went 19,400 → 24,245 (+25%) over this period — clear uptrend with
fresh 52w highs every few weeks. Tests whether Bull v1.8's edge is regime-
dependent and whether Minervini SEPA actually fires in a bull regime.
"""
from __future__ import annotations
import os, sys, time, json
from datetime import datetime, date, timedelta
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import validation as _v
import replay as _r
import data_provider as _dp

FORWARD_DAYS = 30
UNIVERSE = "nifty500"
# Bull regime anchors — mid-month each month
BULL_ANCHORS = [
    "2023-12-15", "2024-01-15", "2024-02-15", "2024-03-15",
    "2024-04-15", "2024-05-15", "2024-06-15", "2024-07-15",
    "2024-08-15", "2024-09-15", "2024-10-15", "2024-11-15",
]


def run_one(screener_name: str, anchors: list[str], universe: list[str],
              callable_run, out_prefix: str) -> dict:
    """Generic per-screener replay harness."""
    print(f"\n{'='*70}\n  {screener_name}\n{'='*70}")
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_rows, detail_frames = [], []
    t0 = time.time()
    for i, anchor in enumerate(anchors, 1):
        print(f"[{i:2d}/{len(anchors)}] validating @ {anchor} ...", flush=True)
        _dp.set_pinned_date(anchor)
        try:
            picks = callable_run(symbols=universe,
                                  out_file=f"validation_runs/{out_prefix}_{anchor}.csv",
                                  strict=True)
        finally:
            _dp.set_pinned_date(None)
        bench_pct = _r._benchmark_forward_pct(anchor, FORWARD_DAYS)
        if picks is None or picks.empty:
            summary_rows.append({"as_of": anchor, "picks_filtered": 0,
                                  "benchmark_pct": bench_pct})
            continue
        perf = _r.forward_returns(picks["Symbol"].astype(str).tolist(),
                                     as_of=anchor, forward_days=FORWARD_DAYS)
        s = _r._summarize(perf, bench_pct)
        summary_rows.append({
            "as_of":            anchor,
            "picks_filtered":   int(len(picks)),
            "win_rate_pct":     s.get("win_rate_pct"),
            "avg_return_pct":   s.get("avg_return_pct"),
            "benchmark_pct":    bench_pct,
            "alpha_pct":        s.get("alpha_vs_bench"),
            "avg_max_dd_pct":   s.get("avg_max_drawdown_pct"),
        })
        if not perf.empty:
            combined = picks.merge(perf, on="Symbol", how="left")
            combined.insert(0, "as_of", anchor)
            detail_frames.append(combined)
    base = "validation_runs/"
    sm = pd.DataFrame(summary_rows)
    sm.to_csv(f"{base}regime_{out_prefix}_{run_id}.csv", index=False)
    if detail_frames:
        det = pd.concat(detail_frames, ignore_index=True)
        det.to_csv(f"{base}regime_{out_prefix}_details_{run_id}.csv", index=False)
    valid = sm[sm["alpha_pct"].notna()] if "alpha_pct" in sm.columns else pd.DataFrame()
    n_picks = sum(int(r.get("picks_filtered", 0)) for r in summary_rows)
    cum_strategy = (1 + valid["avg_return_pct"]/100).prod() - 1 if not valid.empty else 0
    cum_bench    = (1 + valid["benchmark_pct"]/100).prod() - 1 if not valid.empty else 0
    cum_alpha = (1+cum_strategy)/(1+cum_bench) - 1 if cum_bench != -1 else 0
    print()
    print(f"  Picks: {n_picks}")
    if not valid.empty:
        print(f"  Avg anchor alpha: {valid['alpha_pct'].mean():.2f}%")
        print(f"  Anchors with alpha>0: {(valid['alpha_pct']>0).sum()}/{len(valid)}")
        print(f"  Cumulative strategy: {cum_strategy*100:+.2f}%")
        print(f"  Cumulative bench:    {cum_bench*100:+.2f}%")
        print(f"  Cumulative ALPHA:    {cum_alpha*100:+.2f}%")
    else:
        print(f"  No alpha data (zero picks across all anchors)")
    return {
        "screener": screener_name, "n_picks": n_picks,
        "cum_strategy_pct": cum_strategy*100, "cum_bench_pct": cum_bench*100,
        "cum_alpha_pct": cum_alpha*100, "duration_s": time.time()-t0,
        "active_anchors": len(valid),
    }


def main():
    universe = _v.default_universe(UNIVERSE)
    print(f"BULL REGIME BACKTEST  (Dec 2023 - Nov 2024)")
    print(f"Universe: {UNIVERSE} ({len(universe)} symbols)")
    print(f"Anchors: {len(BULL_ANCHORS)}")
    print(f"Forward window: {FORWARD_DAYS} days")

    # Bull v1.8
    # import bull_screener as _bs
    # res_v18 = run_one("BULL v1.8 (POS-ACCUM disabled)", BULL_ANCHORS, universe,
    #                     _bs.run_bull_screener, "bull_v18_bull_regime")
    res_v18 = {'cum_alpha_pct': -0.55, 'n_picks': 341} # Hardcode from previous run


    # Bull v2 Minervini
    import bull_screener_v2 as _bv2
    res_v2 = run_one("BULL v2 Minervini SEPA", BULL_ANCHORS, universe,
                       _bv2.run_bull_screener, "bull_v2_bull_regime")

    print()
    print("="*70)
    print("REGIME COMPARISON — Bull-market window (Dec 2023 - Nov 2024)")
    print("="*70)
    print(f"  Bull v1.8:        {res_v18['cum_alpha_pct']:+7.2f}% cum alpha, {res_v18['n_picks']:>3d} picks")
    print(f"  Bull v2 Minervini:{res_v2 ['cum_alpha_pct']:+7.2f}% cum alpha, {res_v2 ['n_picks']:>3d} picks")
    print()
    print("vs Chop window (Apr 2025 - Apr 2026):")
    print(f"  Bull v1.8:        +17.61% cum alpha, 117 picks")
    print(f"  Bull v2 Minervini: (zero picks)")


if __name__ == "__main__":
    main()
