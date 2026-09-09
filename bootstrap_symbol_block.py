# -*- coding: utf-8 -*-
"""Symbol-block bootstrap for a validation details CSV.

WHY THIS EXISTS (8 Sep 2026, Jay: "re-run the recovery bootstrap with symbol-block
resampling"). Resampling TRADES treats every row as independent evidence. They are not:
trades on one symbol share a company, a sector, and often overlapping outcome windows,
so trade-level resampling understates the variance and produces a confidence interval
that is too narrow. That was established on 13-Aug-2026, when a bar-level bootstrap gave
[+0.04, +0.39] on a sample whose effective n was rows/horizon rather than rows.

It matters here because the SAME recovery run has been quoted two ways in one session:
the run's own bootstrap reported CI95 [-1.60, -0.29] with P(alpha>0) = 0.2%, and a
trade-level resample of the identical data gave [-1.76, +0.06] with 3.2%. One excludes
zero and the other does not. Neither resamples the unit that is actually independent.

METHOD. Draw N symbols WITH replacement from the symbols present, take all of that
symbol's trades each time, and recompute the mean. A symbol contributes as one block, so
a name with six trades cannot inflate the sample the way six independent draws would.

Usage:
    python bootstrap_symbol_block.py validation_runs/<run>_details.csv [--col Alpha_Matched_pct]
                                     [--exclude-label CB-Watch] [--by Signal_Label] [-n 10000]

Read-only. Touches no run, no gate, no live file.
"""
from __future__ import annotations
import argparse
import numpy as np
import pandas as pd


def symbol_block_ci(df: pd.DataFrame, col: str, sym_col: str = "Symbol",
                    n: int = 10000, seed: int = 7):
    """Return (mean, ci_lo, ci_hi, prob_positive_pct, n_trades, n_symbols).

    Blocks are symbols. Each resample draws len(symbols) symbols with replacement and
    pools their trades, so both the number of trades and their clustering vary the way
    they would across alternative universes.
    """
    d = df[[sym_col, col]].dropna()
    if d.empty:
        return (np.nan,) * 4 + (0, 0)
    groups = [g[col].to_numpy(dtype=float) for _, g in d.groupby(sym_col)]
    k = len(groups)
    if k < 5:
        return (float(d[col].mean()), np.nan, np.nan, np.nan, len(d), k)
    rng = np.random.default_rng(seed)
    means = np.empty(n, dtype=float)
    for i in range(n):
        pick = rng.integers(0, k, k)
        vals = np.concatenate([groups[j] for j in pick])
        means[i] = vals.mean()
    return (float(d[col].mean()), float(np.percentile(means, 2.5)),
            float(np.percentile(means, 97.5)), float((means > 0).mean() * 100.0),
            len(d), k)


def _row(label: str, r) -> str:
    m, lo, hi, pp, nt, ns = r
    if np.isnan(lo):
        return "%-34s n=%-4d sym=%-4d mean=%+.2f%%   (too few symbols to resample)" % (label, nt, ns, m)
    verdict = "EXCLUDES zero" if hi < 0 or lo > 0 else "straddles zero"
    return ("%-34s n=%-4d sym=%-4d mean=%+.2f%%  CI95=[%+.2f, %+.2f]  P(a>0)=%.1f%%  %s"
            % (label, nt, ns, m, lo, hi, pp, verdict))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("details")
    ap.add_argument("--col", default="Alpha_Matched_pct")
    ap.add_argument("--sym", default="Symbol")
    ap.add_argument("--by", default=None, help="also break out by this column")
    ap.add_argument("--exclude-label", action="append", default=[],
                    help="drop rows whose --by value matches (repeatable)")
    ap.add_argument("-n", type=int, default=10000)
    a = ap.parse_args()

    d = pd.read_csv(a.details)
    if a.col not in d.columns:
        print("column %r not in %s" % (a.col, a.details))
        return 1

    print("SYMBOL-BLOCK BOOTSTRAP  ·  %s  ·  %s  ·  n=%d" % (a.details, a.col, a.n))
    print("blocks are SYMBOLS, so trades on one name count as one piece of evidence")
    print("=" * 108)
    print(_row("ALL", symbol_block_ci(d, a.col, a.sym, a.n)))

    if a.exclude_label and a.by and a.by in d.columns:
        keep = d[~d[a.by].isin(a.exclude_label)]
        print(_row("EXCLUDING " + ",".join(a.exclude_label), symbol_block_ci(keep, a.col, a.sym, a.n)))

    if a.by and a.by in d.columns:
        print("-" * 108)
        for v, g in sorted(d.groupby(a.by), key=lambda kv: -len(kv[1])):
            print(_row(str(v), symbol_block_ci(g, a.col, a.sym, a.n)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
