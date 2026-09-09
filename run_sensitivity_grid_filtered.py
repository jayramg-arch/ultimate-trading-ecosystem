#!/usr/bin/env python3
"""
run_sensitivity_grid_filtered.py — Filtered-universe 3×3 sensitivity grid.

Same as run_sensitivity_grid.py but routes through validation.run_chartink_validation()
with use_fundamentals=True. The Hunter RSI/ADX threshold sweep happens inside
the Chartink replay layer, so the grid measures sensitivity on the actual
deployed pipeline (Chartink + Screener.in conviction filter), not raw Nifty100.

Pass criterion: FINAL (RSI=60, ADX=25) must remain at or near the joint optimum
on (alpha, hit-rate) under the filtered universe. If a neighboring cell beats
it materially (>0.3 alpha AND >= same hit-rate), re-locate the FINAL — but only
if the same neighbor also wins on the raw grid (cross-universe robustness).

Run:
    python -X utf8 run_sensitivity_grid_filtered.py
    python -X utf8 run_sensitivity_grid_filtered.py --rsi-grid 50,55,60,65,70 --adx-grid 15,20,25,30,35
    python -X utf8 run_sensitivity_grid_filtered.py --min-conviction 5.0
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import pandas as pd

import chartink_replay as cr
import validation


def run_cell(rsi: int, adx: int, top_n: int, months: int, universe: str,
             min_conviction: float) -> dict:
    cr.SCAN_PARAMS["hunter"]["weekly_rsi_min"] = rsi
    cr.SCAN_PARAMS["hunter"]["daily_adx_min"]  = adx

    print()
    print("═" * 60)
    print(f"  CELL: Hunter RSI={rsi}, ADX={adx}   (filtered universe)")
    print("═" * 60)
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
        "rsi":          rsi,
        "adx":          adx,
        "alpha":        agg.get("anchor_avg_alpha_pct"),
        "hit_rate_pct": agg.get("alpha_hit_rate_pct"),
        "winrate_pct":  agg.get("anchor_avg_winrate_pct"),
        "median_alpha": agg.get("anchor_median_alpha_pct"),
        "n_picks":      agg.get("n_picks_total"),
        "avg_cands":    agg.get("avg_candidates_per_anchor"),
        "duration_s":   round(time.time() - t0, 1),
        "run_id":       result.get("run_id"),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--rsi-grid", default="55,60,65",
                   help="Comma-separated Hunter weekly_rsi_min values")
    p.add_argument("--adx-grid", default="20,25,30",
                   help="Comma-separated Hunter daily_adx_min values")
    p.add_argument("--top-n", type=int, default=10)
    p.add_argument("--months", type=int, default=12)
    p.add_argument("--universe", default="nifty500",
                   help="Base universe FED INTO the Chartink replay layer.")
    p.add_argument("--min-conviction", type=float, default=6.0,
                   help="Layer-2 conviction-score threshold (matcher production = 6.0).")
    p.add_argument("--out", default="validation_runs/sensitivity_grid_filtered.csv")
    args = p.parse_args()

    rsi_grid = [int(v) for v in args.rsi_grid.split(",")]
    adx_grid = [int(v) for v in args.adx_grid.split(",")]

    # Snapshot original config to restore at the end.
    orig_rsi = cr.SCAN_PARAMS["hunter"]["weekly_rsi_min"]
    orig_adx = cr.SCAN_PARAMS["hunter"]["daily_adx_min"]

    rows = []
    try:
        for rsi in rsi_grid:
            for adx in adx_grid:
                try:
                    rows.append(run_cell(rsi, adx, args.top_n, args.months,
                                         args.universe, args.min_conviction))
                except Exception as e:
                    print(f"  ❌ cell RSI={rsi} ADX={adx} failed: {e}")
    finally:
        cr.SCAN_PARAMS["hunter"]["weekly_rsi_min"] = orig_rsi
        cr.SCAN_PARAMS["hunter"]["daily_adx_min"]  = orig_adx
        print(f"\n  [reset] Hunter RSI={orig_rsi}, ADX={orig_adx}")

    if not rows:
        print("No cells completed.", file=sys.stderr)
        return 1

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_csv(args.out, index=False)

    print()
    print("═" * 70)
    print("  SENSITIVITY GRID — FILTERED UNIVERSE — alpha by (RSI, ADX)")
    print("  (Chartink replay → matcher conviction filter → bull_screener)")
    print("═" * 70)
    pivot_alpha = df.pivot(index="rsi", columns="adx", values="alpha")
    pivot_hit   = df.pivot(index="rsi", columns="adx", values="hit_rate_pct")
    print("\n  Alpha (anchor avg):")
    print(pivot_alpha.to_string(float_format=lambda v: f"{v:6.2f}"))
    print("\n  Hit rate (%):")
    print(pivot_hit.to_string(float_format=lambda v: f"{v:5.1f}"))

    # Identify joint optimum vs FINAL (RSI=60, ADX=25)
    final_row = df[(df["rsi"] == 60) & (df["adx"] == 25)]
    if not final_row.empty:
        f = final_row.iloc[0]
        f_alpha = float(f["alpha"] or 0)
        f_hit   = float(f["hit_rate_pct"] or 0)
        print()
        print(f"  v1 FINAL (RSI=60, ADX=25): alpha={f_alpha} hit={f_hit}%   "
              f"(min_conviction={args.min_conviction})")
        threats = df[
            (df["alpha"] > f_alpha + 0.3) &
            (df["hit_rate_pct"] >= f_hit) &
            ~((df["rsi"] == 60) & (df["adx"] == 25))
        ]
        if threats.empty:
            print("  ✓ FINAL holds on filtered universe: no neighbor beats by >0.3 alpha "
                  "at >= same hit-rate.")
        else:
            print(f"  ⚠️  {len(threats)} neighbor(s) materially beat FINAL — re-evaluate:")
            print(threats.to_string(index=False))
            print("  Note: only re-locate if the same neighbor also wins on the raw grid.")

    print(f"\n  Saved: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
