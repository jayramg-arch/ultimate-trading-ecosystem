# -*- coding: utf-8 -*-
"""rv_regime_partition.py — does relative volume's relationship to forward alpha FLIP
with the market regime?

STATUS: EXPLORATORY / hypothesis-generating. Nothing is adopted on this. No gate changes
on this. It exists to reconcile two results that point opposite ways, and its output is a
hypothesis for a future pre-registered test, not a decision.

THE PUZZLE IT IS TRYING TO RESOLVE
----------------------------------
  DAILY   (464 trades, 20 anchors, 24 months, MIXED regimes)
          inverted U — 0.8-1.5 = +4.6%, both tails negative
  INTRADAY (1,729 PA-trigger bars, ONE 90-day BULL window)
          roughly monotone INCREASING — 1.5-2.5 is the best bucket

Both were measured carefully. They cannot both describe one relationship, so either the
populations differ (they do — qualified daily picks vs intraday trigger bars) or the
REGIME differs (it does — 24 mixed months vs one bull quarter), or both.

HYPOTHESIS, stated before running
---------------------------------
H — in a RISING tape, volume expansion is confirmation and higher RV is better; across
falling or mixed tapes, high RV increasingly marks exhaustion, producing the inverted U.
If true, the daily inverted U is an AVERAGE over regimes rather than a stable shape, and
the intraday monotone result is what the up-regime slice looks like.

FALSIFIER — if the RV/alpha shape looks the same in every regime bucket, regime is not the
reconciler and the two results differ for population reasons alone.

THE ENDOGENEITY THIS AVOIDS
---------------------------
26-Jul-2026: the direction partition in catalyst_regime_partition.py labels tape direction
by sign(Benchmark_Matched_pct) — the benchmark over the trade's MATCHED window. After the
horizon fix that window's LENGTH is days_held, which is an OUTCOME: fast stop-outs (7d) in
a falling market self-select into DOWN, long runners (72d) into UP. That partition cannot
be used for anything causal.

Here the regime is labelled STRICTLY EX-ANTE: the benchmark's trailing return over the
LOOKBACK days ENDING at the anchor, known before any trade is taken.

Usage:
    python rv_regime_partition.py [--details <run>_details.csv] [--lookback 60]
Read-only.
"""
from __future__ import annotations
import argparse

import numpy as np
import pandas as pd

import data_provider as dp

DETAILS_DEFAULT = "validation_runs/validation_20260726_225547_details.csv"
ALPHA = "Alpha_Matched_pct"
BENCH = "^CRSLDX"
EDGES = [0, 0.5, 0.8, 1.0, 1.5, 2.5, 999]
NAMES = ["<0.5", "0.5-0.8", "0.8-1.0", "1.0-1.5", "1.5-2.5", "2.5+"]


def _regime_map(anchors, lookback: int):
    """anchor -> trailing benchmark % return over `lookback` days ENDING at the anchor.
    Ex-ante by construction: every bar used precedes the anchor."""
    b = dp.fetch_ohlcv(BENCH, period="5y", interval="1d")
    if b is None or b.empty:
        return {}
    c = b["Close"].astype(float)
    idx = c.index.tz_localize(None) if getattr(c.index, "tz", None) is not None else c.index
    c.index = idx.normalize()
    out = {}
    for a in anchors:
        ts = pd.Timestamp(a).normalize()
        hist = c.loc[:ts]
        if len(hist) > lookback:
            out[a] = (hist.iloc[-1] / hist.iloc[-1 - lookback] - 1.0) * 100.0
    return out


def _shape(g, label, n_anchors):
    g = g.copy()
    g["b"] = pd.cut(g["Rel_Vol"], EDGES, labels=NAMES)
    cells = []
    for b, s in g.groupby("b", observed=True):
        cells.append((str(b), len(s), s[ALPHA].mean(), (s[ALPHA] > 0).mean() * 100))
    print("  %s  (%d anchors, %d trades)" % (label, n_anchors, len(g)))
    for b, n, m, w in cells:
        flag = "  <-- best" if cells and m == max(c[2] for c in cells) else ""
        print("     %-9s n=%3d  mean %+6.2f%%  win %4.1f%%%s" % (b, n, m, w, flag))
    # is it monotone increasing, or humped?
    ms = [c[2] for c in cells if c[1] >= 8]
    if len(ms) >= 4:
        peak = int(np.argmax(ms))
        shape = ("rising" if peak >= len(ms) - 2 else
                 "falling" if peak <= 1 else "HUMPED (inverted U)")
        print("     shape: %s   (peak in bucket %d of %d with n>=8)" % (shape, peak + 1, len(ms)))
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--details", default=DETAILS_DEFAULT)
    ap.add_argument("--lookback", type=int, default=60)
    a = ap.parse_args()

    d = pd.read_csv(a.details)
    d = d[d[ALPHA].notna() & d["Rel_Vol"].notna()].copy()
    anchors = sorted(d["as_of"].unique())
    rmap = _regime_map(anchors, a.lookback)
    d["regime_ret"] = d["as_of"].map(rmap)
    d = d[d["regime_ret"].notna()].copy()

    print("trades=%d  anchors=%d  regime = benchmark trailing %dd return AT the anchor (ex-ante)"
          % (len(d), d["as_of"].nunique(), a.lookback))
    ar = pd.Series(rmap).sort_values()
    print("anchor regime spread: min %+.1f%%  median %+.1f%%  max %+.1f%%"
          % (ar.min(), ar.median(), ar.max()))
    print()

    print("=== ALL REGIMES (the pooled result, for reference) ===")
    _shape(d, "pooled", d["as_of"].nunique())

    print("=== TWO-WAY SPLIT on the trailing benchmark return ===")
    med = d["regime_ret"].median()
    for lab, sub in (("WEAK tape  (trailing <= %+.1f%%)" % med, d[d["regime_ret"] <= med]),
                     ("STRONG tape (trailing >  %+.1f%%)" % med, d[d["regime_ret"] > med])):
        _shape(sub, lab, sub["as_of"].nunique())

    print("=== SIGN SPLIT (trailing return negative vs positive) ===")
    for lab, sub in (("FALLING tape (trailing < 0)", d[d["regime_ret"] < 0]),
                     ("RISING tape  (trailing >= 0)", d[d["regime_ret"] >= 0])):
        if sub["as_of"].nunique() >= 3:
            _shape(sub, lab, sub["as_of"].nunique())
        else:
            print("  %s — only %d anchors, not reported\n" % (lab, sub["as_of"].nunique()))

    print("NOTE: 20 anchors split two ways is ~10 anchors a side, and anchors are serially")
    print("correlated through regime. Read the SHAPE, not the magnitudes, and treat any")
    print("conclusion as a hypothesis for a pre-registered test on more anchors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
