"""pos_bo_decay.py — POS-BO retains only 18% of its edge out of sample. Why?

POS-BO is the catalyst the whole system is built around, and the per-catalyst split
showed +5.61% IS -> +1.01% OOS (PF 3.77 -> 0.90, raw return going negative). That is a
far more consequential question than anything about swing.

THREE CANDIDATE EXPLANATIONS, and they are distinguishable:

  H1 REGIME       the 2022-24 tape was simply better; the edge is intact but the
                  environment changed. Tell: the benchmark's own return collapses by a
                  similar factor, and the decay shows up as a LEVEL shift tied to the
                  market rather than to the strategy.
  H2 OUTLIERS     the IS mean was carried by a handful of huge winners. Tell: IS
                  alpha is highly concentrated (top few trades = most of the gross),
                  while the MEDIAN barely differs between windows. Then "decay" is
                  mostly sampling noise in the tail.
  H3 REAL DECAY   the edge itself weakened: the median trade got worse, win rate fell,
                  payoff compressed — a broad deterioration, not a tail effect.

These are not mutually exclusive; the point is to see which one carries the drop.
Also reported: per-anchor time series (gradual slide vs step change), picks per anchor
(a thinner funnel can mean the gates are finding fewer/worse candidates), hold length
and exit mix.

Read-only. No production code touched.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DETAILS = "validation_runs/validation_20260728_191035_details.csv"
IS_END = pd.Timestamp("2024-06-01")
CAT = "POS-BO"


def _conc(s):
    """Share of total gross PROFIT contributed by the top k winners."""
    w = s[s > 0].sort_values(ascending=False)
    tot = w.sum()
    if tot <= 0 or not len(w):
        return {}
    return {k: (w.head(k).sum() / tot * 100) for k in (1, 3, 5, 10) if k <= len(w)}


def main():
    d = pd.read_csv(DETAILS)
    d = d[d["Alpha_Matched_pct"].notna()].copy()
    d["ts"] = pd.to_datetime(d["as_of"])
    g = d[d["Catalyst_used"] == CAT].copy()
    IS, OOS = g[g["ts"] < IS_END], g[g["ts"] >= IS_END]
    print(f"{CAT}: {len(g)} trades   IS n={len(IS)}  OOS n={len(OOS)}\n")

    print("=== H3 check — is the deterioration BROAD or tail-only? ===")
    hdr = f"  {'window':10} {'n':>4} {'meanA':>7} {'medA':>7} {'win%':>6} {'avgWin':>8} {'avgLoss':>8} {'payoff':>7} {'days':>6}"
    print(hdr)
    for nm, w in (("IN-SAMPLE", IS), ("OUT-SAMPLE", OOS)):
        r = w["Return_pct"]
        aw = r[r > 0].mean() if (r > 0).any() else 0.0
        al = abs(r[r <= 0].mean()) if (r <= 0).any() else 0.0
        print(f"  {nm:10} {len(w):4d} {w['Alpha_Matched_pct'].mean():+7.2f} "
              f"{w['Alpha_Matched_pct'].median():+7.2f} {(w['Alpha_Matched_pct']>0).mean()*100:6.1f} "
              f"{aw:+8.2f} {-al:+8.2f} {(aw/al if al>0 else np.inf):7.2f} {w['Days_Held'].mean():6.1f}")

    print("\n=== H2 check — how concentrated is each window's profit? ===")
    for nm, w in (("IN-SAMPLE", IS), ("OUT-SAMPLE", OOS)):
        c = _conc(w["Return_pct"])
        print(f"  {nm:10} " + "  ".join(f"top{k}={v:.0f}%" for k, v in c.items()))
    # drop the biggest winners and see whether the gap survives
    print("\n  mean alpha after removing the top-N winners (by return):")
    for k in (0, 1, 3, 5, 10):
        def trimmed(w):
            if k == 0:
                return w["Alpha_Matched_pct"].mean()
            idx = w["Return_pct"].nlargest(k).index
            return w.drop(idx)["Alpha_Matched_pct"].mean()
        ti, to = trimmed(IS), trimmed(OOS)
        print(f"    drop top {k:2d}:  IS {ti:+6.2f}%   OOS {to:+6.2f}%   gap {ti-to:+6.2f}pp")

    print("\n=== H1 check — what did the BENCHMARK do in each window? ===")
    for nm, w in (("IN-SAMPLE", IS), ("OUT-SAMPLE", OOS)):
        b = w["Benchmark_Matched_pct"]
        print(f"  {nm:10} benchmark over matched holds: mean {b.mean():+6.2f}%  median {b.median():+6.2f}%   "
              f"stock leg: mean {w['Return_pct'].mean():+6.2f}%")

    print("\n=== per-anchor series (gradual slide or step change?) ===")
    per = g.groupby(g["ts"].dt.strftime("%Y-%m")).agg(
        n=("Alpha_Matched_pct", "size"), alpha=("Alpha_Matched_pct", "mean"),
        med=("Alpha_Matched_pct", "median"), win=("Alpha_Matched_pct", lambda s: (s > 0).mean() * 100))
    for k, r in per.iterrows():
        bar = "#" * max(0, min(40, int(r["alpha"] * 2 + 10)))
        mark = " |IS" if pd.Timestamp(k + "-01") < IS_END else " |OOS"
        print(f"  {k}  n={int(r['n']):3d}  a={r['alpha']:+7.2f}%  med={r['med']:+7.2f}%  win={r['win']:5.1f}%  {bar}{mark}")

    print("\n=== funnel — are the gates finding fewer candidates? ===")
    for nm, w in (("IN-SAMPLE", IS), ("OOS", OOS)):
        na = w["ts"].nunique()
        print(f"  {nm:10} {len(w)} picks over {na} anchors = {len(w)/na:.1f} per anchor")

    print("\n=== exit mix ===")
    print(pd.crosstab(np.where(g["ts"] < IS_END, "IS", "OOS"), g["Exit_Reason"],
                      normalize="index").mul(100).round(1).to_string())


if __name__ == "__main__":
    main()
