#!/usr/bin/env python3
"""
run_v2_ablation_filtered.py — Filtered-universe v2 ablation.

Same as run_v2_ablation.py but routes through validation.run_chartink_validation()
with use_fundamentals=True so the universe at each anchor is:
    Layer 1: Chartink replay (4 bull scans, deduped union)
  → Layer 2: matcher_replay conviction filter (min_conviction=6.0)
  → bull_screener picks Top-N

This mirrors the actual deployed Web Commander v4.0 pipeline (Chartink + Screener.in
two-layer filter) rather than raw Nifty100. Results from this driver answer
the question: "How does v1 FINAL perform on the universe we actually trade?"

Acceptance criterion (same as raw ablation):
    Promote a v2 fix to FINAL only if BOTH:
      (a) hit-rate >= filtered-baseline hit-rate
      (b) alpha lifts above filtered-baseline alpha

Run:
    python -X utf8 run_v2_ablation_filtered.py
    python -X utf8 run_v2_ablation_filtered.py --top-n 15
    python -X utf8 run_v2_ablation_filtered.py --cells tiebreak_rs_momentum,sector_cap_top_n
    python -X utf8 run_v2_ablation_filtered.py --min-conviction 5.0
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


def run_one(cell: str | None, top_n: int, months: int, universe: str,
            min_conviction: float) -> dict:
    v2_fixes.reset()
    label = "v1_FINAL_BASELINE_FILTERED" if cell is None else cell
    if cell is not None:
        v2_fixes.enable(cell)

    print()
    print("═" * 70)
    print(f"  ABLATION CELL: {label}")
    print(f"  active flags : {v2_fixes.active_flags() or '<none>'}")
    print(f"  pipeline     : Chartink replay → conviction>={min_conviction} → bull_screener")
    print("═" * 70)
    t0 = time.time()
    result = validation.run_chartink_validation(
        months_back=months,
        top_n=top_n,
        base_universe=universe,
        use_fundamentals=True,
        min_conviction=min_conviction,
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
    p.add_argument("--universe", default="nifty500",
                   help="Base universe FED INTO the Chartink replay layer "
                        "(after Chartink + conviction filtering, only a small "
                        "fraction of this universe survives at each anchor).")
    p.add_argument("--min-conviction", type=float, default=6.0,
                   help="Layer-2 conviction-score threshold (matcher production = 6.0).")
    p.add_argument("--out", default="validation_runs/v2_ablation_filtered_results.csv")
    args = p.parse_args()

    cells = V2_CELLS
    if args.cells:
        wanted = [c.strip() for c in args.cells.split(",") if c.strip()]
        cells = [None] + [c for c in wanted if c in V2_CELLS and c is not None]

    rows = []
    for cell in cells:
        try:
            rows.append(run_one(cell, args.top_n, args.months,
                                args.universe, args.min_conviction))
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
    print("  V2 ABLATION SUMMARY — FILTERED UNIVERSE")
    print("  (Chartink replay → matcher conviction filter → bull_screener)")
    print("═" * 70)
    cols = ["cell", "alpha", "hit_rate_pct", "winrate_pct",
            "median_alpha", "n_picks", "avg_cands", "duration_s", "run_id"]
    print(df[cols].to_string(index=False))
    print()

    base_label = "v1_FINAL_BASELINE_FILTERED"
    base_match = df[df["cell"] == base_label]
    if base_match.empty:
        print("  (No baseline row — cannot evaluate promotion candidates.)")
        print(f"  Saved: {args.out}")
        return 0
    base = base_match.iloc[0]
    base_alpha = float(base["alpha"]) if base["alpha"] is not None else 0.0
    base_hit   = float(base["hit_rate_pct"]) if base["hit_rate_pct"] is not None else 0.0
    print(f"  Filtered baseline: alpha={base_alpha} hit={base_hit}%   "
          f"(min_conviction={args.min_conviction})")
    print()

    promotable = []
    for _, r in df.iterrows():
        if r["cell"] == base_label:
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
        print(f"  Promotable v2 fixes (filtered universe): {', '.join(promotable)}")
        print("  Cross-check: a fix should ideally be promotable on BOTH the raw")
        print("               (run_v2_ablation.py) and filtered drivers before locking.")
    else:
        print("  No v2 fix beat the filtered baseline on both alpha AND hit-rate.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
