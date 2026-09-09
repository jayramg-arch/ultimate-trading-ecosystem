"""
ablation_runner.py — Per-feature lagging-indicator ablation.

For each lagging gate in chartink_replay, run a 12-anchor N500 validation with
that one gate dropped, all others kept at production settings. Compare alpha,
hit-rate, and win-rate against the production baseline.

Cells (8 total):
  1. hunter.disable_rsi
  2. hunter.disable_adx
  3. pullback.disable_rsi
  4. early_birds.disable_rsi
  5. early_birds.disable_macd
  6. strong_leaders.disable_rsi
  7. strong_leaders.disable_adx
  8. TUNED + structural_only (Hunter RSI=60, ADX=25, all scans price-action only)
"""

from __future__ import annotations

import sys, time
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

import pandas as pd

import chartink_replay as cr
import validation as v


PROD_THRESHOLDS = {
    ("hunter", "weekly_rsi_min"):           55,
    ("hunter", "daily_adx_min"):            20,
    ("strong_leaders", "daily_rsi_min"):    60,
    ("strong_leaders", "daily_adx_min"):    25,
}


def reset_to_production():
    """Restore production thresholds + zero out every disable_* / structural_only."""
    for (s, k), val in PROD_THRESHOLDS.items():
        cr.SCAN_PARAMS[s][k] = val
    for s in cr.SCAN_PARAMS:
        for k in list(cr.SCAN_PARAMS[s]):
            if k == "structural_only" or k.startswith("disable_"):
                cr.SCAN_PARAMS[s][k] = False


def run_one(label: str, mutator) -> dict:
    """Reset, apply mutator, run a 12-anchor validation, capture aggregate."""
    reset_to_production()
    mutator(cr.SCAN_PARAMS)
    print(f"\n{'='*68}\n  CELL: {label}\n{'='*68}", flush=True)
    t0 = time.time()
    res = v.run_chartink_validation(months_back=12, base_universe="nifty500",
                                       top_n=10)
    agg = res["aggregate"]
    out = {
        "cell":              label,
        "alpha":             agg.get("anchor_avg_alpha_pct"),
        "hit_rate_pct":      agg.get("alpha_hit_rate_pct"),
        "winrate_pct":       agg.get("anchor_avg_winrate_pct"),
        "median_alpha":      agg.get("anchor_median_alpha_pct"),
        "n_picks":           agg.get("n_picks_total"),
        "avg_candidates":    agg.get("avg_candidates_per_anchor"),
        "duration_s":        round(time.time() - t0, 1),
        "run_id":            res.get("run_id"),
    }
    print(f"\n>> {label}: alpha={out['alpha']}  hit={out['hit_rate_pct']}%  "
          f"win={out['winrate_pct']}  cands={out['avg_candidates']}", flush=True)
    return out


def main() -> int:
    cells = [
        ("PROD_BASELINE",      lambda P: None),
        ("hunter_drop_rsi",    lambda P: P["hunter"].update({"disable_rsi": True})),
        ("hunter_drop_adx",    lambda P: P["hunter"].update({"disable_adx": True})),
        ("pullback_drop_rsi",  lambda P: P["pullback"].update({"disable_rsi": True})),
        ("eb_drop_rsi",        lambda P: P["early_birds"].update({"disable_rsi": True})),
        ("eb_drop_macd",       lambda P: P["early_birds"].update({"disable_macd": True})),
        ("sl_drop_rsi",        lambda P: P["strong_leaders"].update({"disable_rsi": True})),
        ("sl_drop_adx",        lambda P: P["strong_leaders"].update({"disable_adx": True})),
        ("TUNED_structural",   lambda P: (
                P["hunter"].update({"weekly_rsi_min": 60, "daily_adx_min": 25}),
                # structural_only on every scan
                [P[s].update({"structural_only": True}) for s in P],
            )),
    ]

    rows: list[dict] = []
    for label, mut in cells:
        try:
            rows.append(run_one(label, mut))
        except Exception as e:
            print(f"\nCELL {label} failed: {e}", flush=True)
            rows.append({"cell": label, "error": str(e)})

    reset_to_production()

    df = pd.DataFrame(rows)
    out_path = "validation_runs/ablation_results.csv"
    df.to_csv(out_path, index=False)

    print(f"\n{'='*68}\n  ABLATION SUMMARY (sorted by alpha)\n{'='*68}")
    if "alpha" in df.columns:
        view = df.sort_values("alpha", ascending=False, na_position="last")
    else:
        view = df
    cols = [c for c in ["cell", "alpha", "hit_rate_pct", "winrate_pct",
                           "median_alpha", "n_picks", "avg_candidates"]
              if c in view.columns]
    print(view[cols].to_string(index=False))

    # Delta vs PROD_BASELINE for each cell
    if "alpha" in df.columns and (df["cell"] == "PROD_BASELINE").any():
        base = df.loc[df["cell"] == "PROD_BASELINE"].iloc[0]
        print(f"\n{'='*68}\n  DELTAS vs PROD_BASELINE\n{'='*68}")
        deltas = []
        for _, r in df.iterrows():
            if r["cell"] == "PROD_BASELINE":
                continue
            try:
                deltas.append({
                    "cell":          r["cell"],
                    "d_alpha":       round(r["alpha"]        - base["alpha"], 2),
                    "d_hit_rate":    round(r["hit_rate_pct"] - base["hit_rate_pct"], 1),
                    "d_winrate":     round(r["winrate_pct"]  - base["winrate_pct"], 1),
                    "d_candidates":  round(r["avg_candidates"] - base["avg_candidates"], 1),
                })
            except Exception:
                pass
        ddf = pd.DataFrame(deltas).sort_values("d_alpha", ascending=False)
        print(ddf.to_string(index=False))
        print(f"\nResults saved: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
