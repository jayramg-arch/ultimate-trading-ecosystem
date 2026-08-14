#!/usr/bin/env python3
"""Does a fundamental gate SEPARATE winners from losers? Partition, don't assert.

THE QUESTION (13 Aug 2026). The scanner-filter map (docs/25) showed the bull family
gated by RFF - a survival test - while the Bull scans Jay wrote are a growth standard,
and proposed swapping Catalyst and Pullback onto BFF. That proposal is COHERENT but it
was never MEASURED: no forward-return test in this repo partitions on any fundamental
field. This does.

METHOD
  Take a completed validation run's per-trade details, which carry matched-horizon
  alpha (the honest convention - benchmark over the ACTUAL hold, see the
  matched-horizon memory). Split the trades by fundamental score at the anchor and
  compare mean alpha, win rate and the chronological IS/OOS halves.

  Recovery runs already carry RFF_Base / RFF_Total per pick, so that partition is
  free. Bull runs carry neither score, so the BFF side needs point-in-time
  fundamentals - fundamental_replay.fundamentals_as_of() supplies them (yfinance
  quarterly statements ARE point-in-time; asking today for 2025-Q1 returns what was
  actually reported then).

WHY THE STATS ARE SHAPED THIS WAY
  Bootstrap resamples whole SYMBOLS, not rows. Forward windows of 90-180 days on
  overlapping anchors mean two rows for the same name share most of their outcome
  window, so a row-level bootstrap claims a precision the data does not have - the
  same correction already applied in pullback_rv_ab.py.

  The chronological split is reported ALWAYS, because an in-sample-only separation is
  how every over-fit gate in this repo first looked.

    python fundamental_gate_partition.py                      # newest run, RFF
    python fundamental_gate_partition.py --run <path_details.csv>
    python fundamental_gate_partition.py --split 5            # RFF >= 5 vs <= 4
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd

try:
    if (sys.stdout.encoding or "").lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_DIR = os.path.dirname(os.path.abspath(__file__))


def _cohorts(m, col, split):
    return m[m[col] >= split]["a"], m[m[col] < split]["a"]


def _line(label, A, B):
    if len(A) < 5 or len(B) < 5:
        print(f"  {label:<34} too few to read (n={len(A)}/{len(B)})")
        return
    print(f"  {label:<34} hi n={len(A):<4} {A.mean():+6.2f} win {(A > 0).mean() * 100:3.0f}%"
          f"   |   lo n={len(B):<4} {B.mean():+6.2f} win {(B > 0).mean() * 100:3.0f}%"
          f"   |   edge {A.mean() - B.mean():+.2f}pp")


def _add_bff_column(d):
    """Compute BFF point-in-time per (symbol, anchor) and add it as BFF_Base.

    Bull validation details carry NO fundamental column — unlike recovery runs,
    which store RFF_Base — so the bull side has to be reconstructed. Sourced from
    screener.in's own #quarters/#ratios history via fundamental_replay.bff_as_of,
    NOT from compute_bff, which reads today's page and would leak look-ahead into
    every historical row.

    Rows whose history does not reach the anchor stay NaN and drop out of the
    partition rather than scoring as weak — a missing fundamental must never
    look like a failing one.
    """
    import fundamental_replay as fr

    pairs = d[["Symbol", "as_of"]].drop_duplicates()
    print(f"  computing point-in-time BFF for {len(pairs)} symbol-anchor pairs "
          f"({d['Symbol'].nunique()} symbols, cached per symbol)…")
    cache, n_ok = {}, 0
    for i, (_, r) in enumerate(pairs.iterrows(), 1):
        if i % 50 == 0:
            print(f"    {i}/{len(pairs)}  ({n_ok} resolved)", flush=True)
        sym, anc = str(r["Symbol"]), str(r["as_of"])[:10]
        try:
            b = fr.bff_as_of(sym, anc)
            sc = b.get("score")
        except Exception:
            sc = None
        if sc is not None:
            n_ok += 1
        cache[(sym, anc)] = sc
    d["BFF_Base"] = [cache.get((str(s), str(a)[:10])) for s, a in zip(d["Symbol"], d["as_of"])]
    print(f"  resolved {n_ok}/{len(pairs)} pairs "
          f"({len(d) - d['BFF_Base'].isna().sum()}/{len(d)} trades carry a score)")
    return d


def run(path, col, split, n_boot=3000):
    d = pd.read_csv(path)
    if col == "BFF_Base" and col not in d.columns:
        d = _add_bff_column(d)
    if col not in d.columns:
        print(f"{os.path.basename(path)} has no {col} column — nothing to partition.")
        print(f"  available: {[c for c in d.columns if 'RFF' in c or 'BFF' in c] or 'none'}")
        return 1
    if "Alpha_Matched_pct" not in d.columns:
        print("no Alpha_Matched_pct — run validation with --catalyst_windows.")
        return 1

    d["a"] = pd.to_numeric(d["Alpha_Matched_pct"], errors="coerce")
    d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d.dropna(subset=["a", col])

    # The forward-window gate. A wall of 30s means the run measured 90-180d setups
    # over 30 days and nothing below can be trusted (catalyst_column_convention).
    if "forward_days_used" in d.columns:
        w = d["forward_days_used"].value_counts().to_dict()
        print(f"  forward windows: {w}")
        if set(w) == {30}:
            print("  ⛔ every trade used a 30-day window — invalid for these setups. Stop.")
            return 1

    print(f"\n{os.path.basename(path)} — {len(d)} trades, {d['as_of'].nunique()} anchors")
    print(f"  overall: mean {d.a.mean():+.2f}  median {d.a.median():+.2f}  "
          f"win {(d.a > 0).mean() * 100:.0f}%")

    print(f"\nBY {col}")
    for v, g in d.groupby(col):
        if len(g) >= 10:
            print(f"  {col} {v:.0f}   n={len(g):>4}  mean {g.a.mean():+6.2f}  "
                  f"median {g.a.median():+6.2f}  win {(g.a > 0).mean() * 100:4.0f}%")
    rho = d[[col, "a"]].corr(method="spearman").iloc[0, 1]
    print(f"  Spearman rho vs alpha: {rho:+.3f}")

    print(f"\nSPLIT AT {col} >= {split}")
    A, B = _cohorts(d, col, split)
    _line("pooled", A, B)

    rng = np.random.default_rng(7)
    syms = d["Symbol"].unique()
    diffs = []
    for _ in range(n_boot):
        m = d[d["Symbol"].isin(rng.choice(syms, len(syms), replace=True))]
        a, b = _cohorts(m, col, split)
        if len(a) > 20 and len(b) > 20:
            diffs.append(a.mean() - b.mean())
    if diffs:
        lo, hi = np.percentile(diffs, [2.5, 97.5])
        print(f"  symbol-block CI95 of the edge: [{lo:+.2f}, {hi:+.2f}]  →  "
              f"{'SEPARATES' if lo > 0 else 'not significant'}")

    anch = sorted(d["as_of"].unique())
    cut = anch[int(len(anch) * 0.6)]
    _line(f"IN-SAMPLE  <{cut}", *_cohorts(d[d.as_of < cut], col, split))
    _line(f"OUT-SAMPLE >={cut}", *_cohorts(d[d.as_of >= cut], col, split))

    p = (d.groupby("as_of")
           .apply(lambda g: pd.Series({"hi": g[g[col] >= split].a.mean(),
                                       "lo": g[g[col] < split].a.mean()}),
                  include_groups=False).dropna())
    if len(p):
        print(f"\n  per-ANCHOR (what a portfolio experiences): {len(p)} anchors with both cohorts"
              f"\n    hi {p.hi.mean():+.2f}  lo {p.lo.mean():+.2f}  "
              f"hi beats lo in {int((p.hi > p.lo).sum())}/{len(p)}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None, help="path to a *_details.csv (default: newest)")
    ap.add_argument("--col", default="RFF_Base", help="fundamental column to partition on")
    ap.add_argument("--split", type=float, default=5.0, help="hi cohort is >= this")
    a = ap.parse_args()
    path = a.run
    if not path:
        c = sorted(glob.glob(os.path.join(_DIR, "validation_runs", "validation_*_details.csv")),
                   key=os.path.getmtime)
        if not c:
            print("no validation *_details.csv found")
            return 1
        path = c[-1]
    return run(path, a.col, a.split)


if __name__ == "__main__":
    raise SystemExit(main())
