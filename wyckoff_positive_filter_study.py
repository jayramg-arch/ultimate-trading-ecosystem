# -*- coding: utf-8 -*-
"""wyckoff_positive_filter_study.py — does a Wyckoff DISTRIBUTION reading at signal
time predict BETTER forward alpha, well enough to select on?

PRE-REGISTERED in docs/PREREG_wyckoff_positive_filter.md before any significance was
computed. Read that first; the adoption rule there is binding and is not renegotiated
here.

WHY THIS EXISTS
---------------
July tested DISTRIBUTION as a GO **veto**. The vetoed cohort returned +5.60% against
+0.52% for the kept one, and I filed that as "null / backwards" and discarded it. That
was the wrong call twice over: a veto whose vetoed cohort OUTPERFORMS is a signal with
the sign inverted, and the mechanism was already written down — Wyckoff events fire at
high-volume pivot highs, which on a pre-qualified long universe is what a breakout looks
like. This asks whether it can be used in the direction the data pointed.

REPRODUCTION FIRST (8-Sep). Re-running wyckoff_veto_study.py gives July's numbers
exactly, and shows two things not reported then: the headline cell is n=26, below that
study's own n>=30 floor, and the edge decays monotonically with sample size
(+5.08pp @ n=26 -> +1.36 @ 47 -> +0.74 @ 189 -> +0.20 @ 228). That decay is the shape of
a small-sample artifact, so the PRIMARY here is the WIDE cut, not the dramatic one.

METHOD NOTES
------------
Point-in-time: the Wyckoff state is computed from bars <= the anchor only (the frame is
truncated before the detector runs), and the outcome is matched-horizon alpha over
[D, D+H]. Disjoint by construction — this is not the endogeneity that invalidated the
23-Jul GO-confirmation study.

Significance is SYMBOL-BLOCK bootstrapped on the EDGE (difference of means), never
trade-level. Established 13-Aug when a bar-level bootstrap overstated n, and again 8-Sep
when one recovery run gave three different answers under three resampling units.

Usage:
    python wyckoff_positive_filter_study.py [--details <run>_details.csv] [-n 10000]
Read-only. Touches no gate, no live file.
"""
from __future__ import annotations
import argparse
import sys

import numpy as np
import pandas as pd

import wcl_context as W
from wyckoff_veto_study import _load_frames, _state_asof, DETAILS_DEFAULT

ALPHA = "Alpha_Matched_pct"


def _edge_ci(d: pd.DataFrame, mask: pd.Series, n_boot: int = 10000, seed: int = 7):
    """Symbol-block bootstrap CI on the EDGE (selected mean − rejected mean).

    Blocks are symbols: a name contributes all of its trades or none, so two trades on
    one company are not counted as two independent pieces of evidence. Resampling the
    EDGE rather than each arm separately keeps the two cohorts paired inside a draw,
    which is what the adoption rule is actually about.
    """
    d = d[[ "Symbol", ALPHA ]].assign(sel=mask.values).dropna()
    syms = d["Symbol"].unique()
    groups = {s: g for s, g in d.groupby("Symbol")}
    k = len(syms)
    if k < 5:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    out = np.full(n_boot, np.nan)
    for i in range(n_boot):
        pick = rng.integers(0, k, k)
        blk = pd.concat([groups[syms[j]] for j in pick], copy=False)
        a, b = blk.loc[blk["sel"], ALPHA], blk.loc[~blk["sel"], ALPHA]
        if len(a) and len(b):
            out[i] = a.mean() - b.mean()
    out = out[~np.isnan(out)]
    if out.size < 100:
        return (np.nan, np.nan, np.nan)
    return (float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5)),
            float((out > 0).mean() * 100.0))


def _line(d, mask, label, n_boot):
    sel, rej = d[mask], d[~mask]
    if len(sel) == 0 or len(rej) == 0:
        return f"{label:30} n={len(sel):4d} — degenerate, no comparison possible"
    edge = sel[ALPHA].mean() - rej[ALPHA].mean()
    lo, hi, pp = _edge_ci(d, mask, n_boot)
    ci = "  CI95=[%+.2f,%+.2f] P(edge>0)=%4.1f%%" % (lo, hi, pp) if not np.isnan(lo) else "  CI n/a"
    return ("%-30s keep n=%3d (%4.1f%%) a=%+6.2f%% win=%4.1f%%  |  drop n=%3d a=%+6.2f%%  |  edge %+.2fpp%s"
            % (label, len(sel), len(sel) / len(d) * 100, sel[ALPHA].mean(),
               (sel[ALPHA] > 0).mean() * 100, len(rej), rej[ALPHA].mean(), edge, ci))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--details", default=DETAILS_DEFAULT)
    ap.add_argument("-n", type=int, default=10000)
    a = ap.parse_args()

    d = pd.read_csv(a.details)
    print("trades=%d  symbols=%d  anchors=%d" % (len(d), d["Symbol"].nunique(), d["as_of"].nunique()))
    frames = _load_frames(set(d["Symbol"]), quiet=True)
    print("frames resolved: %d/%d" % (len(frames), d["Symbol"].nunique()))

    bias, tier, age = [], [], []
    for _, r in d.iterrows():
        st = _state_asof(frames.get(r["Symbol"]), r["as_of"]) if r["Symbol"] in frames else None
        # wyckoff_state returns a DICT with keys bias / score_base / age_bars — not an
        # object. My first pass used getattr(st, "bias") and silently produced 0 resolved
        # states out of 464. It printed that count, which is the only reason it did not
        # become a confident number about nothing.
        bias.append(st.get("bias") if isinstance(st, dict) else None)
        tier.append(st.get("score_base", np.nan) if isinstance(st, dict) else np.nan)
        age.append(st.get("age_bars", np.nan) if isinstance(st, dict) else np.nan)
    d["wyk_bias"], d["wyk_tier"], d["wyk_age"] = bias, tier, age
    d = d[d["wyk_bias"].notna() & d[ALPHA].notna()].copy()

    print("trades with a resolved as-of state: %d" % len(d))
    print("baseline: mean alpha %+.2f%%  win %.1f%%" % (d[ALPHA].mean(), (d[ALPHA] > 0).mean() * 100))
    print("bias mix:", d["wyk_bias"].value_counts().to_dict())
    print()

    dist = d["wyk_bias"] == "DISTRIBUTION"
    print("=== SELECTING on DISTRIBUTION (positive filter) ===")
    print(_line(d, dist, "PRIMARY  any DISTRIBUTION", a.n))
    print(_line(d, dist & (d["wyk_tier"] <= -3), "  tier<=-3 (narrow)", a.n))
    print(_line(d, dist & (d["wyk_age"] <= 15), "  age<=15 (fresh)", a.n))
    print()

    # D — chronological halves. The sign must hold in both.
    print("=== D · CHRONOLOGICAL SPLIT (sign must hold in both halves) ===")
    anchors = sorted(d["as_of"].unique())
    cut = anchors[len(anchors) // 2]
    for lab, sub in (("IS  (early)", d[d["as_of"] < cut]), ("OOS (late)", d[d["as_of"] >= cut])):
        m = sub["wyk_bias"] == "DISTRIBUTION"
        if m.sum() and (~m).sum():
            e = sub.loc[m, ALPHA].mean() - sub.loc[~m, ALPHA].mean()
            print("%-12s n_sel=%3d  edge %+.2fpp   %s" % (lab, int(m.sum()), e, "ok" if e > 0 else "REVERSES"))
        else:
            print("%-12s degenerate" % lab)
    print()

    # ---- the pre-registered rule, evaluated mechanically ----
    sel, rej = d[dist], d[~dist]
    edge = sel[ALPHA].mean() - rej[ALPHA].mean()
    lo, hi, _pp = _edge_ci(d, dist, a.n)
    halves = []
    for sub in (d[d["as_of"] < cut], d[d["as_of"] >= cut]):
        m = sub["wyk_bias"] == "DISTRIBUTION"
        halves.append(sub.loc[m, ALPHA].mean() - sub.loc[~m, ALPHA].mean() if m.sum() and (~m).sum() else np.nan)
    A = len(sel) >= 100
    B = edge >= 1.0
    C = (not np.isnan(lo)) and (lo > 0 or hi < 0)
    D = all((not np.isnan(h)) and h > 0 for h in halves)
    E = len(sel) / len(d) >= 0.30
    print("--- ADOPTION RULE (docs/PREREG_wyckoff_positive_filter.md) ---")
    print("  A n>=100 ................. %4d        %s" % (len(sel), "PASS" if A else "FAIL"))
    print("  B edge>=+1.0pp ........... %+.2fpp     %s" % (edge, "PASS" if B else "FAIL"))
    print("  C symbol-block CI excl 0 . [%+.2f,%+.2f] %s" % (lo, hi, "PASS" if C else "FAIL"))
    print("  D both halves same sign .. %s  %s" % (["%+.2f" % h for h in halves], "PASS" if D else "FAIL"))
    print("  E retention>=30%% ......... %4.1f%%       %s" % (len(sel) / len(d) * 100, "PASS" if E else "FAIL"))
    print()
    print("  VERDICT: %s" % ("ADOPT as a positive selection filter" if all((A, B, C, D, E))
                             else "DO NOT ADOPT — see PREREG section 5 for the v2 path"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
