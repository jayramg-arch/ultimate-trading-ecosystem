# -*- coding: utf-8 -*-
"""score_rv_band_confirm.py — the confirmatory test of the RV band as a DAILY
SELECTION filter, scored against the rule fixed in
docs/PREREG_rv_band_selection_layer.md BEFORE this sample was generated.

Two things this file must do that a naive scorer would not:

1. **Drop every anchor already examined in this thread.** The 464-trade run
   20260726_225547 was used to DISCOVER the effect (post-hoc tercile split), to TEST
   the band, and to PARTITION it by regime. Scoring it a fourth time is not
   confirmation. The exclusion is mechanical and is part of the test.
2. **Bootstrap by SYMBOL, at 99%.** Trade-level resampling is not acceptable (two
   trades on one name are not two pieces of evidence), and the band is the survivor
   of seven tests in this thread, so section 4 tightened the interval from 95% to 99%.

Usage:  python score_rv_band_confirm.py [--run 20260908_230157] [-n 10000]
Read-only.
"""
from __future__ import annotations
import argparse

import numpy as np
import pandas as pd

ALPHA = "Alpha_Matched_pct"
PRIOR = "validation_runs/validation_20260726_225547_details.csv"
BAND_LO, BAND_HI = 0.8, 1.5          # fixed from the INDEPENDENT 13-Aug sample
EDGES = [0, 0.5, 0.8, 1.0, 1.5, 2.5, 999]
NAMES = ["<0.5", "0.5-0.8", "0.8-1.0", "1.0-1.5", "1.5-2.5", "2.5+"]


def _blocks(d: pd.DataFrame, m_band: pd.Series, n_boot: int, seed: int = 13):
    """Symbol-block bootstrap on (band mean - all mean). Both arms come from the SAME
    resampled block set, so the comparison stays paired. Returns 95% AND 99% bounds —
    section 4 requires the 99% one to exclude zero."""
    w = d[["Symbol", ALPHA]].copy()
    w["band"] = m_band.values
    w = w.dropna(subset=[ALPHA])
    syms = w["Symbol"].unique()
    groups = {s: g for s, g in w.groupby("Symbol")}
    k = len(syms)
    if k < 5:
        return dict(lo95=np.nan, hi95=np.nan, lo99=np.nan, hi99=np.nan, pp=np.nan)
    rng = np.random.default_rng(seed)
    out = np.full(n_boot, np.nan)
    for i in range(n_boot):
        blk = pd.concat([groups[syms[j]] for j in rng.integers(0, k, k)], copy=False)
        x = blk.loc[blk["band"], ALPHA]
        if len(x) >= 3 and len(blk) >= 3:
            out[i] = x.mean() - blk[ALPHA].mean()
    out = out[~np.isnan(out)]
    if out.size < 100:
        return dict(lo95=np.nan, hi95=np.nan, lo99=np.nan, hi99=np.nan, pp=np.nan)
    return dict(lo95=float(np.percentile(out, 2.5)), hi95=float(np.percentile(out, 97.5)),
                lo99=float(np.percentile(out, 0.5)), hi99=float(np.percentile(out, 99.5)),
                pp=float((out > 0).mean() * 100.0))


def _arms(d: pd.DataFrame, label: str):
    band = (d["Rel_Vol"] >= BAND_LO) & (d["Rel_Vol"] <= BAND_HI)
    tot = len(d)
    print("=== %s ===" % label)
    for nm, m in (("no filter", pd.Series(True, index=d.index)), ("band 0.8-1.5", band)):
        s = d[m]
        if s.empty:
            print("   %-13s n=  0 — never fires" % nm)
            continue
        print("   %-13s n=%4d  keep %5.1f%%  mean %+6.2f%%  median %+6.2f%%  win %4.1f%%  "
              "deployment %+6.2f%%"
              % (nm, len(s), len(s) / tot * 100, s[ALPHA].mean(), s[ALPHA].median(),
                 (s[ALPHA] > 0).mean() * 100, s[ALPHA].mean() * len(s) / tot))
    print()
    return band


def _shape(d: pd.DataFrame, label: str):
    g = d.copy()
    g["b"] = pd.cut(g["Rel_Vol"], EDGES, labels=NAMES)
    cells = [(str(b), len(s), s[ALPHA].mean()) for b, s in g.groupby("b", observed=True)]
    print("=== F · SHAPE — %s ===" % label)
    best = max((c[2] for c in cells if c[1] >= 8), default=np.nan)
    for b, n, m in cells:
        print("   %-9s n=%4d  mean %+6.2f%%%s"
              % (b, n, m, "   <-- best" if n >= 8 and m == best else ""))
    usable = [c for c in cells if c[1] >= 8]
    peak = usable[int(np.argmax([c[2] for c in usable]))][0] if usable else None
    print("   peak bucket (n>=8): %s   humped required: 0.8-1.0 or 1.0-1.5" % peak)
    print()
    return peak


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="20260908_230157")
    ap.add_argument("-n", type=int, default=10000)
    a = ap.parse_args()

    d = pd.read_csv("validation_runs/validation_%s_details.csv" % a.run)
    d = d[d[ALPHA].notna() & d["Rel_Vol"].notna()].copy()

    print("--- INSTRUMENT CHECK (section 2) ---")
    w = d["forward_days_used"].dropna().astype(int).value_counts().to_dict()
    print("  forward windows %s%s" % (w, "" if 30 not in w else "   <-- some 30d rows"))
    prior = set(pd.read_csv(PRIOR)["as_of"].unique())
    seen = d[d["as_of"].isin(prior)]
    fresh = d[~d["as_of"].isin(prior)].copy()
    print("  anchors %d total | %d already examined (DROPPED) | %d FRESH"
          % (d["as_of"].nunique(), seen["as_of"].nunique(), fresh["as_of"].nunique()))
    print("  trades  %d total | %d dropped | %d scored" % (len(d), len(seen), len(fresh)))
    if fresh["as_of"].nunique() < 5:
        print("  *** too few fresh anchors to confirm anything. STOP.")
        return 1
    print()

    # Reference only — NOT the test. Printed so the drop is visible, not persuasive.
    _arms(seen, "REFERENCE · the 20 anchors already looked at (NOT the test)")

    band = _arms(fresh, "CONFIRMATORY · %d fresh anchors, never examined"
                 % fresh["as_of"].nunique())
    edge = fresh.loc[band, ALPHA].mean() - fresh[ALPHA].mean()
    ci = _blocks(fresh, band, a.n)
    print("   band - all = %+.2fpp   symbol-block CI95=[%+.2f, %+.2f]  CI99=[%+.2f, %+.2f]  "
          "P(band>all)=%.1f%%" % (edge, ci["lo95"], ci["hi95"], ci["lo99"], ci["hi99"], ci["pp"]))
    print()

    peak = _shape(fresh, "fresh anchors")

    print("=== D · CHRONOLOGICAL SPLIT of the fresh anchors ===")
    anchors = sorted(fresh["as_of"].unique())
    cut = anchors[len(anchors) // 2]
    halves = []
    for lab, sub in (("IS  (early)", fresh[fresh["as_of"] < cut]),
                     ("OOS (late)", fresh[fresh["as_of"] >= cut])):
        bm = (sub["Rel_Vol"] >= BAND_LO) & (sub["Rel_Vol"] <= BAND_HI)
        if bm.sum() >= 5 and len(sub) >= 10:
            e = sub.loc[bm, ALPHA].mean() - sub[ALPHA].mean()
            halves.append(e)
            print("   %-12s n_band=%4d of %4d   band-all %+.2fpp   %s"
                  % (lab, int(bm.sum()), len(sub), e, "ok" if e > 0 else "REVERSES"))
        else:
            halves.append(np.nan)
            print("   %-12s degenerate" % lab)
    print()

    dep_band = fresh.loc[band, ALPHA].mean() * band.sum() / len(fresh)
    dep_all = fresh[ALPHA].mean()
    A = int(band.sum()) >= 100
    B = edge >= 1.5
    C = (not np.isnan(ci["lo99"])) and (ci["lo99"] > 0 or ci["hi99"] < 0)
    D = all((not np.isnan(h)) and h > 0 for h in halves)
    E = dep_band > dep_all
    F = peak in ("0.8-1.0", "1.0-1.5")
    print("--- ADOPTION RULE (docs/PREREG_rv_band_selection_layer.md section 4) ---")
    print("  A n>=100 in band ......... %4d          %s" % (int(band.sum()), "PASS" if A else "FAIL"))
    print("  B edge >= +1.5pp ......... %+.2fpp       %s" % (edge, "PASS" if B else "FAIL"))
    print("  C CI99 excludes zero ..... [%+.2f,%+.2f]  %s" % (ci["lo99"], ci["hi99"], "PASS" if C else "FAIL"))
    print("  D both halves same sign .. %-14s %s" % (["%+.2f" % h for h in halves], "PASS" if D else "FAIL"))
    print("  E' deployment beats all .. %+.2f vs %+.2f  %s" % (dep_band, dep_all, "PASS" if E else "FAIL"))
    print("  F humped shape ........... peak %-8s %s" % (peak, "PASS" if F else "FAIL"))
    print()
    print("  VERDICT: %s"
          % ("ADOPT the band as a daily selection filter — hard-filter vs ranking input is "
             "a SEPARATE decision (section 5), and this does NOT license touching rv_floor"
             if all((A, B, C, D, E, F)) else
             "DO NOT ADOPT — 'the RV inverted U did not replicate out of sample'; no "
             "selection layer changes and rv_floor is untouched. Section 7 has the v2: "
             "test RV per-FAMILY, since POS-ACCUM wants contraction and POS-BO wants "
             "expansion, so mid-RV may simply be where accumulation names sit."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
