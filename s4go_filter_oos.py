"""s4go_filter_oos.py - walk-forward OOS validation of GO-as-a-SELECTION-filter (23 Jul 2026).

The in-sample finding: among catalyst picks (buy@close), GO-CONFIRMED beat GO-NEVER by
+4.68pp. This asks the honest question BEFORE wiring it anywhere: does that
discrimination persist OUT-OF-SAMPLE?

Method (mirrors walkforward_oos.py's convention): split the shared anchors
chronologically into in-sample (earlier is_frac) and out-of-sample (later). In each
window measure:
  (A) DISCRIMINATION - confirmed vs never buy@close mean/win/edge (does GO carry
      information about which catalyst picks work?), pooled + positional-vs-swing.
  (B) PORTFOLIO - per-anchor mean alpha of ALL catalyst picks vs GO-CONFIRMED-only
      (does filtering to confirmed names lift anchor-level alpha?). This is the
      selection CEILING; a live strategy that waits for confirmation also pays the
      entry wait-tax, so treat (B) as the upper bound of the filter's value.

Verdict: filter PASSES OOS if the confirmed-minus-never edge stays > 0 out-of-sample
(directionally, small-sample) AND the confirmed-only portfolio does not underperform
all-picks OOS. No zero-filling; anchors with no never-cohort are reported, not imputed.
Inputs are existing artifacts (no re-sim). Partial-endogeneity caveat as in
s4go_filter_value.py.
"""
import sys
import pandas as pd, numpy as np

BASELINE = "validation_runs/validation_20260722_135745_details.csv"
GO_RUN   = "validation_runs/validation_20260723_063652_details.csv"
IS_FRAC  = float(sys.argv[1]) if len(sys.argv) > 1 else 0.6


def fam(c):
    c = str(c)
    if c.startswith("POS-ACCUM"): return "POS-ACCUM"
    if c.startswith("POS") or c.startswith("WYC"): return "POS/WYC"
    if c.startswith("SWG"): return "SWG"
    if c.startswith("REV"): return "REV"
    return c


def load():
    b = pd.read_csv(BASELINE)
    b["am"] = pd.to_numeric(b["Alpha_Matched_pct"], errors="coerce")
    b = b[b["am"].notna()].copy()
    b["key"] = b["as_of"].astype(str) + "|" + b["Symbol"].astype(str)
    g = pd.read_csv(GO_RUN)
    g["key"] = g["as_of"].astype(str) + "|" + g["Symbol"].astype(str)
    g["go_fired"] = g["Status"].astype(str) != "no GO in window"
    gmap = g.groupby("key")["go_fired"].max()
    b["go_fired"] = b["key"].map(gmap)
    shared = sorted(set(b["as_of"]) & set(g["as_of"]))
    j = b[b["as_of"].isin(shared) & b["go_fired"].notna()].copy()
    j["go_fired"] = j["go_fired"].astype(bool)
    j["fam"] = j["Catalyst_used"].fillna(j["Catalyst"]).map(fam)
    j["posgrp"] = np.where(j["fam"].isin(["POS-ACCUM", "POS/WYC"]), "POSITIONAL", "SWING/OTHER")
    return j, shared


def window_report(name, jw):
    C, N = jw[jw["go_fired"]]["am"], jw[~jw["go_fired"]]["am"]
    print(f"\n-- {name}  anchors={jw['as_of'].nunique()}  picks={len(jw)} "
          f"(confirmed {len(C)} / never {len(N)}) --")
    if len(C) and len(N):
        edge = C.mean() - N.mean()
        wedge = C.gt(0).mean() * 100 - N.gt(0).mean() * 100
        print(f"  CONFIRMED  mean={C.mean():+.2f}%  win={C.gt(0).mean()*100:5.1f}%")
        print(f"  NEVER      mean={N.mean():+.2f}%  win={N.gt(0).mean()*100:5.1f}%")
        print(f"  EDGE       {edge:+.2f}pp mean | {wedge:+.1f}pp win")
    else:
        edge = None
        print("  (a cohort is empty - no edge computable)")
    print("  by group:")
    for grp, gg in jw.groupby("posgrp"):
        c, n = gg[gg["go_fired"]]["am"], gg[~gg["go_fired"]]["am"]
        e = f"{c.mean()-n.mean():+.2f}pp" if len(c) and len(n) else "n/a"
        print(f"    {grp:12} CONFIRMED {c.mean():+.2f}% (n={len(c):3d})  NEVER "
              f"{(n.mean() if len(n) else float('nan')):+.2f}% (n={len(n):3d})  edge {e}")
    # PORTFOLIO: per-anchor mean alpha, all vs confirmed-only
    allp = jw.groupby("as_of")["am"].mean()
    confp = jw[jw["go_fired"]].groupby("as_of")["am"].mean()
    print("  PORTFOLIO (per-anchor mean alpha):")
    print(f"    ALL-PICKS       mean_anchor={allp.mean():+.2f}%  hit={ (allp>0).mean()*100:5.1f}%  ({len(allp)} anchors)")
    print(f"    CONFIRMED-ONLY  mean_anchor={confp.mean():+.2f}%  hit={ (confp>0).mean()*100:5.1f}%  ({len(confp)} anchors)")
    print(f"    filter lift     {confp.mean()-allp.mean():+.2f}pp per-anchor")
    return edge, confp.mean() - allp.mean()


def main():
    j, shared = load()
    k = max(1, int(round(len(shared) * IS_FRAC)))
    is_anchors, oos_anchors = shared[:k], shared[k:]
    print("=" * 74)
    print(f"  GO-AS-FILTER - WALK-FORWARD OOS  (is_frac={IS_FRAC}, {len(shared)} shared anchors)")
    print("=" * 74)
    print(f"  IN-SAMPLE : {is_anchors[0]} -> {is_anchors[-1]}  ({len(is_anchors)} anchors)")
    print(f"  OUT-SAMPLE: {oos_anchors[0]} -> {oos_anchors[-1]}  ({len(oos_anchors)} anchors)")

    is_edge, is_lift = window_report("IN-SAMPLE", j[j["as_of"].isin(is_anchors)])
    oos_edge, oos_lift = window_report("OUT-OF-SAMPLE", j[j["as_of"].isin(oos_anchors)])

    print("\n" + "=" * 74)
    print("  VERDICT")
    if oos_edge is None:
        print("  [N/A] INCONCLUSIVE - OOS never-cohort empty; cannot measure discrimination.")
    elif oos_edge > 0 and (oos_lift is None or oos_lift >= 0):
        print(f"  [PASS] HOLDS OOS - confirmed-minus-never edge {oos_edge:+.2f}pp (IS {is_edge:+.2f}pp); "
              f"confirmed-only portfolio lift {oos_lift:+.2f}pp OOS.")
        print("     GO-confirmation carries selection information out-of-sample. Small-sample -")
        print("     directional, not statistically sealed. Wire as conviction/priority flag on")
        print("     POSITIONAL picks; re-check as anchors accumulate.")
    elif oos_edge > 0:
        print(f"  [MIXED] MIXED - discrimination positive OOS ({oos_edge:+.2f}pp) but confirmed-only "
              f"portfolio lift {oos_lift:+.2f}pp (<0). Information present, portfolio benefit not.")
    else:
        print(f"  [FAIL] FAILS OOS - edge flips to {oos_edge:+.2f}pp out-of-sample (IS {is_edge:+.2f}pp). "
              "In-sample discrimination did not persist; do NOT wire the filter.")
    print("  Caveat: partial endogeneity (never-trigger = never-momentum); the win-rate gap")
    print("  argues real discrimination, but the truly clean test is a forward run whose")
    print("  qualify step ALSO records go-confirmation live (future work).")


if __name__ == "__main__":
    main()
