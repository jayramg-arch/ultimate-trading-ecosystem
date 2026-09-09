"""Dedicated backtest harness for bull_screener_v2 (Minervini SEPA).

Uses the same 12-anchor framework as validation.py + replay.py, but calls
bull_screener_v2.run_bull_screener directly with data_provider pinning so
each anchor sees historical-only data.
"""
from __future__ import annotations
import os, sys, time, json
from datetime import datetime
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import validation as _v
import replay as _r
import data_provider as _dp
import bull_screener_v2 as _bv2

FORWARD_DAYS = 30
UNIVERSE = "nifty500"

def main():
    anchors = _v.monthly_anchors(months_back=12,
                                   end_offset_days=max(FORWARD_DAYS + 5, 35))
    universe = _v.default_universe(UNIVERSE)
    print(f"Anchors: {len(anchors)}  Universe: {UNIVERSE} ({len(universe)} symbols)")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_rows = []
    detail_frames = []
    t0 = time.time()

    for i, anchor in enumerate(anchors, 1):
        print(f"[{i:2d}/{len(anchors)}] validating @ {anchor} ...", flush=True)
        _dp.set_pinned_date(anchor)
        try:
            picks = _bv2.run_bull_screener(symbols=universe,
                                              out_file=f"validation_runs/bv2_replay_{anchor}.csv",
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
            "picks_universe":   int(len(picks)),
            "picks_filtered":   int(len(picks)),
            "picks_with_data":  int(s.get("n_complete", 0)),
            "win_rate_pct":     s.get("win_rate_pct"),
            "avg_return_pct":   s.get("avg_return_pct"),
            "median_return_pct":s.get("median_return_pct"),
            "best_pct":         s.get("best_pct"),
            "worst_pct":        s.get("worst_pct"),
            "benchmark_pct":    bench_pct,
            "alpha_pct":        s.get("alpha_vs_bench"),
            "avg_max_dd_pct":   s.get("avg_max_drawdown_pct"),
            "worst_max_dd_pct": s.get("worst_max_drawdown_pct"),
            "risk_reward":      s.get("risk_reward_ratio"),
        })
        if not perf.empty and "Symbol" in picks.columns:
            combined = picks.merge(perf, on="Symbol", how="left")
            combined.insert(0, "as_of", anchor)
            detail_frames.append(combined)

    base = "validation_runs/"
    os.makedirs(base, exist_ok=True)
    sm = pd.DataFrame(summary_rows)
    sm.to_csv(f"{base}bv2_summary_{run_id}.csv", index=False)
    if detail_frames:
        det = pd.concat(detail_frames, ignore_index=True)
        det.to_csv(f"{base}bv2_details_{run_id}.csv", index=False)
    else:
        det = pd.DataFrame()

    # Aggregate
    valid = sm.dropna(subset=["alpha_pct"])
    n_picks = sum(int(r.get("picks_filtered",0)) for r in summary_rows)
    avg_alpha = float(valid["alpha_pct"].mean()) if not valid.empty else 0
    hit = float((valid["alpha_pct"] > 0).mean() * 100) if not valid.empty else 0
    print()
    print(f"VALIDATION COMPLETE  run_id={run_id}")
    print(f"Picks total: {n_picks}  Universe: {len(universe)}")
    print(f"Avg anchor alpha: {avg_alpha:.2f}%")
    print(f"Hit rate: {hit:.1f}%")
    print()
    if not sm.empty:
        cols = [c for c in ["as_of","picks_filtered","win_rate_pct","avg_return_pct",
                              "benchmark_pct","alpha_pct","avg_max_dd_pct"] if c in sm.columns]
        print(sm[cols].round(2).to_string(index=False))
    print(f"Saved: {base}bv2_summary_{run_id}.csv + bv2_details_{run_id}.csv")
    print(f"Duration: {time.time()-t0:.1f}s")

if __name__ == "__main__":
    main()
