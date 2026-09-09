# -*- coding: utf-8 -*-
"""score_nonign_ladder.py — read the GRADED ladder for the positive form of
roleMismatch, from a single instrumented control run.

WHY A LADDER AND NOT A THRESHOLD ARM
------------------------------------
`--nonign_min N` gates, but Rev_N / Con_N / NonIgn_Score are emitted on EVERY trade
whether the gate is armed or not. So one control run shows the whole shape, and a
threshold is only worth a treat arm if the shape has more than two usable levels.

That is not a hypothetical safeguard. The reversal-COUNT axis was measured first and
turned out non-monotone on the control arm (0/1/2/3 -> -1.18 / +1.33 / -1.25 / +1.42),
so grading it collapses to the binary rule already tested and every level above 1 is
worse. Running an arm per threshold would have spent an hour discovering that.

WHAT "RESOLUTION" MEANS HERE, fixed before the numbers are read
--------------------------------------------------------------
The ladder has resolution only if BOTH hold:
  * at least THREE levels carry n >= 25, and
  * the level means are ordered (monotone in the score) across those levels.
Anything else is a binary cut wearing a graded label, and the honest report is that
there is nothing to grade.

Usage:  python score_nonign_ladder.py --run <id> [--min-n 25]
Read-only.
"""
from __future__ import annotations
import argparse

import numpy as np
import pandas as pd

ALPHA = "Alpha_Matched_pct"
PRIOR = "validation_runs/validation_20260908_191448_details.csv"   # the 18 anchors already looked at
MIN_N_DEFAULT = 25


def _ladder(d: pd.DataFrame, col: str, label: str, min_n: int):
    print("=== %s ===" % label)
    rows = []
    for k, g in d.groupby(col):
        rows.append((int(k), len(g), g[ALPHA].mean(), g[ALPHA].median(),
                     (g[ALPHA] > 0).mean() * 100))
    for k, n, mu, med, w in rows:
        mark = "" if n >= min_n else "   (thin)"
        print("   %s=%d  n=%4d  mean %+7.2f%%  median %+7.2f%%  win %4.1f%%%s"
              % (col, k, n, mu, med, w, mark))
    usable = [r for r in rows if r[1] >= min_n]
    means = [r[2] for r in usable]
    mono = (len(means) >= 3
            and (all(b >= a for a, b in zip(means, means[1:]))
                 or all(b <= a for a, b in zip(means, means[1:]))))
    print("   levels with n>=%d: %d   monotone across them: %s"
          % (min_n, len(usable), "YES" if mono else "NO"))

    # FRAGILITY (added 9 Sep 2026, after the n>=25 rule passed a cell whose entire
    # ordering rested on 5 rows). A cell can clear a count floor and still be one
    # outlier wide, so each level is re-read with its top TWO alphas dropped. If the
    # ordering does not survive that, it is not a ladder.
    trimmed = []
    for k, g in d.groupby(col):
        if len(g) >= min_n:
            s = g[ALPHA].sort_values(ascending=False)
            trimmed.append((int(k), len(g), s.iloc[2:].mean() if len(s) > 4 else np.nan))
    if trimmed:
        print("   top-2-trimmed means: %s"
              % "  ".join("%s=%d %+.2f%%" % (col, k, m) for k, _, m in trimmed))
        tm = [m for _, _, m in trimmed if m == m]
        mono_t = (len(tm) >= 3
                  and (all(b >= a for a, b in zip(tm, tm[1:]))
                       or all(b <= a for a, b in zip(tm, tm[1:]))))
        print("   ordering survives trimming: %s" % ("YES" if mono_t else "NO"))
        mono = mono and mono_t
    print("   RESOLUTION: %s" % ("yes — a graded threshold is worth testing"
                                 if (len(usable) >= 3 and mono) else
                                 "NO — this is a binary cut wearing a graded label"))
    print()
    return rows, (len(usable) >= 3 and mono)


def _thresholds(d: pd.DataFrame, col: str, label: str):
    tot = len(d)
    base = d[ALPHA].mean()
    print("=== thresholds on %s — %s ===" % (col, label))
    print("   (deployment = mean x retention: what the BOOK earns, not the survivors)")
    print("   %-10s %-6s %-8s %-9s %-9s %-9s" % ("gate", "n", "keep", "mean", "edge", "deploy"))
    for th in range(1, int(d[col].max()) + 1):
        m = d[col] >= th
        if m.sum() < 5:
            print("   >=%-8d %-6d degenerate" % (th, int(m.sum())))
            continue
        mu = d.loc[m, ALPHA].mean()
        print("   >=%-8d %-6d %6.1f%%  %+7.2f%%  %+7.2fpp  %+7.2f%%"
              % (th, int(m.sum()), m.mean() * 100, mu, mu - base, mu * m.mean()))
    print("   %-10s %-6d %6.1f%%  %+7.2f%%  %8s  %+7.2f%%"
          % ("off (all)", tot, 100.0, base, "-", base))
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--min-n", type=int, default=MIN_N_DEFAULT)
    a = ap.parse_args()

    d = pd.read_csv("validation_runs/validation_%s_details.csv" % a.run)
    need = {"NonIgn_Score", "Rev_N", "Con_N"}
    missing = need - set(d.columns)
    if missing:
        print("*** run %s predates the instrumentation (missing %s). Re-run the control "
              "arm; the ladder cannot be recovered from an older CSV." % (a.run, sorted(missing)))
        return 1
    d = d[d[ALPHA].notna()].copy()
    for c in ("NonIgn_Score", "Rev_N", "Con_N"):
        d[c] = d[c].fillna(0).astype(int)

    print("--- INSTRUMENT ---")
    print("  trades %d  anchors %d" % (len(d), d["as_of"].nunique()))
    w = d["forward_days_used"].dropna().astype(int).value_counts().to_dict()
    print("  forward windows %s" % w)
    print("  score coverage: NonIgn_Score present on %d of %d rows"
          % (d["NonIgn_Score"].notna().sum(), len(d)))
    print("  CONTRACTION share: %d of %d trades carry Con_N>0 (%.1f%%)"
          % ((d["Con_N"] > 0).sum(), len(d), (d["Con_N"] > 0).mean() * 100))
    print()

    # The contraction half is the ONLY thing that makes this score different from the
    # reversal count already ruled out. If it never fires, the whole exercise is moot
    # and that must be said before any alpha is read.
    if (d["Con_N"] > 0).mean() < 0.02:
        print("*** CONTRACTION effectively never fires on a trigger bar. The graded score")
        print("    is then just the reversal count, which was already measured as")
        print("    non-monotone. There is nothing here to grade — stop.")
        print()

    _, res_ni = _ladder(d, "NonIgn_Score", "LADDER · non-ignition evidence (reversal + contraction)", a.min_n)
    _ladder(d, "Rev_N", "for reference · reversal only (the axis already ruled out)", a.min_n)
    _ladder(d, "Con_N", "for reference · contraction only (the new half)", a.min_n)
    _thresholds(d, "NonIgn_Score", "all anchors")

    prior = set(pd.read_csv(PRIOR)["as_of"].unique()) if PRIOR else set()
    fresh = d[~d["as_of"].isin(prior)]
    if fresh["as_of"].nunique() >= 5:
        print("=== FRESH ANCHORS ONLY (%d anchors, %d trades) ==="
              % (fresh["as_of"].nunique(), len(fresh)))
        _ladder(fresh, "NonIgn_Score", "ladder on fresh anchors", max(8, a.min_n // 2))
        _thresholds(fresh, "NonIgn_Score", "fresh anchors")

    print("--- READ ---")
    print("  %s" % ("The ladder has resolution: pick the threshold from the SHAPE, register it, "
                    "and run one treat arm."
                    if res_ni else
                    "No resolution. The graded positive form reduces to the same binary cut as "
                    "--role_mismatch, which was already tested and did not clear its bar. "
                    "Do NOT run a threshold arm; report that there is nothing to grade."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
