# -*- coding: utf-8 -*-
"""rv_band_study.py — is relative volume a BAND rather than a floor?

PRE-REGISTERED in docs/PREREG_rv_band.md before this file was written. The band, the
adoption rule, the retention trap and the scope limit are all fixed there. Read it first;
nothing here renegotiates it.

THE CLAIM UNDER TEST
--------------------
S4 gates volume with a one-sided floor, RV >= rv_floor. If the relationship between RV
and forward alpha is an inverted U — dead volume has no fuel, climax volume is exhaustion
— then a floor is the wrong SHAPE: it correctly rejects the left tail and then waves
through the right one.

WHY THE BAND IS 0.8-1.5 AND NOT SOMETHING FITTED
------------------------------------------------
Taken from the 13-Aug-2026 pullback study, an INDEPENDENT sample (74,267 at-value bars,
250 names, 3 years) whose buckets ran +0.84 / +1.05 / +1.15 / +1.30 / +1.00 across
0-0.5 / 0.5-0.8 / 0.8-1.0 / 1.0-1.5 / 1.5+. The band is its two peak buckets. It is NOT
tuned against the trades scored here. A band chosen by maximising alpha on the test set
would reproduce precisely the artifact that made the Wyckoff +5.60% cell meaningless.

THE TRAP (PREREG section 5)
---------------------------
A band cuts BOTH tails, so on the survivors it will beat a floor on mean alpha almost by
construction, while taking fewer trades. Mean alpha alone is therefore not evidence.
Retention is printed beside every mean, and the deployment view (mean x retention) is
printed too: a gate that lifts alpha 1pp while halving the trade count has produced the
same expectancy on a smaller book, which for this desk is a worse outcome.

Usage:
    python rv_band_study.py [--details <run>_details.csv] [-n 10000]
Read-only. Touches no gate, no live file.
"""
from __future__ import annotations
import argparse

import numpy as np
import pandas as pd

DETAILS_DEFAULT = "validation_runs/validation_20260726_225547_details.csv"
ALPHA = "Alpha_Matched_pct"
BAND_LO, BAND_HI = 0.8, 1.5      # PREREG section 2 - fixed from the 13-Aug sample
FLOOR = 1.0                      # what S4 does today


def _paired_ci(d: pd.DataFrame, m_a: pd.Series, m_b: pd.Series,
               n_boot: int = 10000, seed: int = 7):
    """Symbol-block bootstrap CI on (mean of cohort A - mean of cohort B).

    Blocks are symbols, so two trades on one name are one piece of evidence. Both arms
    are drawn from the SAME resampled block set, which keeps them paired - the question
    is whether the band beats the floor, not whether each differs from zero.
    """
    w = d[["Symbol", ALPHA]].copy()
    w["a"], w["b"] = m_a.values, m_b.values
    w = w.dropna(subset=[ALPHA])
    syms = w["Symbol"].unique()
    groups = {s: g for s, g in w.groupby("Symbol")}
    k = len(syms)
    if k < 5:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    out = np.full(n_boot, np.nan)
    for i in range(n_boot):
        blk = pd.concat([groups[syms[j]] for j in rng.integers(0, k, k)], copy=False)
        x, y = blk.loc[blk["a"], ALPHA], blk.loc[blk["b"], ALPHA]
        if len(x) >= 3 and len(y) >= 3:
            out[i] = x.mean() - y.mean()
    out = out[~np.isnan(out)]
    if out.size < 100:
        return (np.nan, np.nan, np.nan)
    return (float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5)),
            float((out > 0).mean() * 100.0))


def _arm(d, mask, label):
    s = d[mask]
    n, tot = len(s), len(d)
    if n == 0:
        return "%-26s n=  0  — never fires" % label
    keep = n / tot * 100.0
    return ("%-26s n=%3d  keep %4.1f%%  mean %+6.2f%%  median %+6.2f%%  win %4.1f%%  "
            "deployment %+6.2f%%"
            % (label, n, keep, s[ALPHA].mean(), s[ALPHA].median(),
               (s[ALPHA] > 0).mean() * 100, s[ALPHA].mean() * n / tot))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--details", default=DETAILS_DEFAULT)
    ap.add_argument("-n", type=int, default=10000)
    a = ap.parse_args()

    d = pd.read_csv(a.details)
    d = d[d[ALPHA].notna() & d["Rel_Vol"].notna()].copy()
    print("trades=%d  symbols=%d  anchors=%d" % (len(d), d["Symbol"].nunique(), d["as_of"].nunique()))
    print("Rel_Vol: min %.2f  p25 %.2f  median %.2f  p75 %.2f  max %.2f"
          % (d["Rel_Vol"].min(), d["Rel_Vol"].quantile(.25), d["Rel_Vol"].median(),
             d["Rel_Vol"].quantile(.75), d["Rel_Vol"].max()))
    print()

    none_m = pd.Series(True, index=d.index)
    floor_m = d["Rel_Vol"] >= FLOOR
    band_m = (d["Rel_Vol"] >= BAND_LO) & (d["Rel_Vol"] <= BAND_HI)

    print("=== ARMS  (deployment = mean x retention: what the BOOK earns, not the survivors) ===")
    print(_arm(d, none_m, "A  no gate"))
    print(_arm(d, floor_m, "B  floor  RV >= %.1f" % FLOOR))
    print(_arm(d, band_m, "C  band   %.1f-%.1f" % (BAND_LO, BAND_HI)))
    print()

    print("=== SHAPE  (is it really an inverted U?) ===")
    edges = [0, 0.5, 0.8, 1.0, 1.5, 2.5, 99]
    d["rvb"] = pd.cut(d["Rel_Vol"], edges, labels=["<0.5", "0.5-0.8", "0.8-1.0", "1.0-1.5", "1.5-2.5", "2.5+"])
    for b, g in d.groupby("rvb", observed=True):
        print("   %-9s n=%3d  mean %+6.2f%%  win %4.1f%%" % (b, len(g), g[ALPHA].mean(), (g[ALPHA] > 0).mean() * 100))
    print()

    edge = d.loc[band_m, ALPHA].mean() - d.loc[floor_m, ALPHA].mean()
    lo, hi, pp = _paired_ci(d, band_m, floor_m, a.n)
    print("=== C vs B ===")
    print("   band - floor = %+.2fpp   symbol-block CI95=[%+.2f, %+.2f]  P(band>floor)=%.1f%%"
          % (edge, lo, hi, pp))
    print()

    print("=== D · CHRONOLOGICAL SPLIT (the criterion that killed the Wyckoff filter) ===")
    anchors = sorted(d["as_of"].unique())
    cut = anchors[len(anchors) // 2]
    halves = []
    for lab, sub in (("IS  (early)", d[d["as_of"] < cut]), ("OOS (late)", d[d["as_of"] >= cut])):
        bm = (sub["Rel_Vol"] >= BAND_LO) & (sub["Rel_Vol"] <= BAND_HI)
        fm = sub["Rel_Vol"] >= FLOOR
        if bm.sum() >= 5 and fm.sum() >= 5:
            e = sub.loc[bm, ALPHA].mean() - sub.loc[fm, ALPHA].mean()
            halves.append(e)
            print("   %-12s n_band=%3d  n_floor=%3d  band-floor %+.2fpp   %s"
                  % (lab, int(bm.sum()), int(fm.sum()), e, "ok" if e > 0 else "REVERSES"))
        else:
            halves.append(np.nan)
            print("   %-12s degenerate" % lab)
    print()

    A = int(band_m.sum()) >= 100
    B = edge >= 1.0
    C = (not np.isnan(lo)) and (lo > 0 or hi < 0)
    D = all((not np.isnan(h)) and h > 0 for h in halves)
    E = band_m.mean() >= 0.40
    print("--- ADOPTION RULE (docs/PREREG_rv_band.md) ---")
    print("  A n>=100 ................. %4d          %s" % (int(band_m.sum()), "PASS" if A else "FAIL"))
    print("  B band-floor >= +1.0pp ... %+.2fpp       %s" % (edge, "PASS" if B else "FAIL"))
    print("  C CI excludes zero ....... [%+.2f,%+.2f]  %s" % (lo, hi, "PASS" if C else "FAIL"))
    print("  D both halves same sign .. %-14s %s" % (["%+.2f" % h for h in halves], "PASS" if D else "FAIL"))
    print("  E retention >= 40%% ....... %4.1f%%         %s" % (band_m.mean() * 100, "PASS" if E else "FAIL"))
    print()
    print("  VERDICT: %s" % ("ADOPT the band — then re-measure on INTRADAY bars per PREREG section 6, "
                             "which is a separate test; a daily result does not license editing rv_floor"
                             if all((A, B, C, D, E)) else
                             "DO NOT ADOPT — the one-sided floor stands; see PREREG section 7 for the v2"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
