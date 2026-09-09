#!/usr/bin/env python3
"""
run_v2_ablation.py — Ablate the 5 v2 candidate fixes against the v1 FINAL baseline.

Runs the 12-anchor walk-forward validation once with NO v2 flags (the v1 FINAL
baseline reproduction), then once with EACH v2 flag enabled in isolation.
Writes the aggregated results to validation_runs/v2_ablation_results.csv.

Acceptance criterion (per BACKTEST_RESULTS_v1.docx §7):
    Promote a v2 fix to FINAL only if BOTH:
      (a) hit-rate >= 91.7% (v1 baseline floor)
      (b) alpha lifts above 4.45 (v1 baseline)

Run:
    python run_v2_ablation.py
    python run_v2_ablation.py --top-n 15        # also test the Top-N=15 hypothesis
    python run_v2_ablation.py --cells tiebreak_rs_momentum,sector_cap_top_n
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import pandas as pd

import v2_fixes
import validation


V2_CELLS = [
    None,                            # baseline = v1 FINAL behavior (all flags off)
    "tiebreak_rs_momentum",          # cheapest fix; expected to recover Jan-15-26 alone
    "vcp_score_multiplier",
    "days_since_pivot_penalty",
    "sector_cap_top_n",
    "pos_accum_rsi_nullout",
]


def run_one(cell: str | None, top_n: int, months: int, universe: str) -> dict:
    v2_fixes.reset()
    label = "v1_FINAL_BASELINE" if cell is None else cell
    if cell is not None:
        v2_fixes.enable(cell)

    print()
    print("═" * 70)
    print(f"  ABLATION CELL: {label}")
    print(f"  active flags : {v2_fixes.active_flags() or '<none>'}")
    print("═" * 70)
    t0 = time.time()
    result = validation.run_validation(
        months_back=months,
        top_n=top_n,
        universe_name=universe,
    )
    agg = result.get("aggregate", {})
    return {
        "cell":          label,
        "alpha":         agg.get("anchor_avg_alpha_pct"),
        "hit_rate_pct":  agg.get("alpha_hit_rate_pct"),
        "winrate_pct":   agg.get("anchor_avg_winrate_pct"),
        "median_alpha":  agg.get("anchor_median_alpha_pct"),
        "n_picks":       agg.get("n_picks_total"),
        "avg_cands":     agg.get("avg_candidates_per_anchor"),
        "best_anchor":   agg.get("best_anchor_alpha"),
        "worst_anchor":  agg.get("worst_anchor_alpha"),
        "duration_s":    round(time.time() - t0, 1),
        "run_id":        result.get("run_id"),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cells", default=None,
                   help="Comma-separated subset of cells to run "
                        "(default: baseline + all 5 fixes)")
    p.add_argument("--top-n", type=int, default=10)
    p.add_argument("--months", type=int, default=12)
    p.add_argument("--universe", default="nifty500")
    p.add_argument("--out", default="validation_runs/v2_ablation_results.csv")
    args = p.parse_args()

    cells = V2_CELLS
    if args.cells:
        wanted = [c.strip() for c in args.cells.split(",") if c.strip()]
        cells = [None] + [c for c in wanted if c in V2_CELLS and c is not None]

    rows = []
    for cell in cells:
        try:
            rows.append(run_one(cell, args.top_n, args.months, args.universe))
        except Exception as e:
            print(f"  ❌ cell {cell!r} failed: {e}", flush=True)

    if not rows:
        print("No cells completed.", file=sys.stderr)
        return 1

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_csv(args.out, index=False)

    print()
    print("═" * 70)
    print("  V2 ABLATION SUMMARY")
    print("═" * 70)
    cols = ["cell", "alpha", "hit_rate_pct", "winrate_pct",
            "median_alpha", "n_picks", "duration_s", "run_id"]
    print(df[cols].to_string(index=False))
    print()

    # Highlight any winners (per acceptance criterion)
    base = df[df["cell"] == "v1_FINAL_BASELINE"].iloc[0]
    base_alpha = float(base["alpha"]) if base["alpha"] is not None else 0.0
    base_hit   = float(base["hit_rate_pct"]) if base["hit_rate_pct"] is not None else 0.0
    print(f"  v1 FINAL baseline: alpha={base_alpha} hit={base_hit}%")
    print()
    promotable = []
    for _, r in df.iterrows():
        if r["cell"] == "v1_FINAL_BASELINE":
            continue
        alpha = float(r["alpha"] or 0)
        hit   = float(r["hit_rate_pct"] or 0)
        if alpha > base_alpha and hit >= base_hit:
            promotable.append(r["cell"])
            print(f"  ✓ {r['cell']:<28s}  alpha={alpha} hit={hit}%   PROMOTE-CANDIDATE")
        else:
            print(f"  ✗ {r['cell']:<28s}  alpha={alpha} hit={hit}%")

    print()
    print(f"  Saved: {args.out}")
    if promotable:
        print(f"  Promotable v2 fixes: {', '.join(promotable)}")
        print("  Recommend: re-run with multiple promotable flags enabled together,")
        print("             then update v1 → v2 in chartink_replay.py and CLAUDE.md.")
    else:
        print("  No v2 fix beat the v1 FINAL baseline on both alpha AND hit-rate.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
