#!/usr/bin/env python3
"""Does the RV floor discard GOOD pullbacks? A/B on forward returns.

THE QUESTION (Jay, 13-Aug-2026): "some of the good pullback trades are being
discarded on grounds of low RV. RV will definitely be lower on pullbacks."

The first half is already measured and true - at-value bars print median RV 0.63
against 1.35 on breakout bars, so a 1.0 floor rejects 78% of them. But "the floor
rejects most of them" is NOT the same claim as "the floor rejects the GOOD ones".
This tests the second claim, which is the one that matters.

METHOD
  Universe : nifty500, daily bars.
  Context  : PULLBACK = above the 200-DMA, |close - EMA20| <= 1 ATR, and NOT at a
             new 20-day high. That is S4's own "at value" definition (ext <= 1.0
             ATR) plus a trend filter.
  Split    : each qualifying bar goes into a bucket by its RV.
  Outcome  : forward return over N sessions, and ALPHA against the same-window
             benchmark move - the matched-horizon convention this repo settled on
             (see the matched-horizon memory: benchmark the ACTUAL hold).
  Report   : mean/median alpha and win rate per bucket, with n.

WHAT WOULD CHANGE THE GATE
  If the RV >= 1.0 bucket materially outperforms RV < 1.0, the floor is doing
  real work and should stay. If the low-RV buckets match or beat it, the floor
  is discarding good trades and tier 2/3 are justified. If the DRY bucket
  (RV <= ~0.8) is the best of all, that argues for INVERTING the test on
  pullbacks rather than merely lowering it.

  This is a context/outcome study, not a full trade simulation - no stops, no
  slippage, no position sizing. It answers "is this population worth trading",
  not "what would the equity curve look like". Treat a positive result as
  permission to run the real s4go replay, not as a licence to ship.

    python pullback_rv_ab.py                 # 250 names, 3y, 20-day horizon
    python pullback_rv_ab.py --limit 120 --years 2 --horizon 10
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

_DIR = os.path.dirname(os.path.abspath(__file__))
BENCH = "^CRSLDX"
BUCKETS = [(0.0, 0.5), (0.5, 0.8), (0.8, 1.0), (1.0, 1.5), (1.5, 99.0)]


def _indicators(df: pd.DataFrame) -> pd.DataFrame:
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    out = pd.DataFrame(index=df.index)
    out["c"] = c
    out["ema20"] = c.ewm(span=20, adjust=False).mean()
    out["sma200"] = c.rolling(200).mean()
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    out["atr"] = tr.rolling(14).mean()
    # RV against the PRIOR bar's average, so a big bar cannot inflate its own baseline
    out["rv"] = v / v.rolling(50).mean().shift(1)
    out["hi20"] = h.rolling(20).max()
    return out


def run(limit: int | None, years: int, horizon: int) -> pd.DataFrame:
    import json
    import bull_screener as bs
    import data_provider as dp

    syms = [s.replace(".NS", "") for s in json.load(open(os.path.join(_DIR, "nifty500_symbols.json")))]
    if limit:
        syms = syms[:limit]

    bench = bs._flatten_cols(dp.fetch_ohlcv(BENCH, period=f"{years}y", interval="1d", use_cache=True))
    if bench is None or bench.empty:
        print("benchmark unavailable - cannot compute alpha, aborting")
        return pd.DataFrame()
    bc = bench["Close"]
    bfwd = (bc.shift(-horizon) / bc - 1.0) * 100.0     # benchmark move over the SAME window

    rows = []
    for i, s in enumerate(syms, 1):
        if i % 50 == 0:
            print(f"  {i}/{len(syms)}…", flush=True)
        try:
            df = bs._flatten_cols(dp.fetch_ohlcv(s, period=f"{years}y", interval="1d", use_cache=True))
            if df is None or len(df) < 260:
                continue
            ind = _indicators(df)
            fwd = (ind["c"].shift(-horizon) / ind["c"] - 1.0) * 100.0
            ext = (ind["c"] - ind["ema20"]) / ind["atr"]
            ctx = (
                (ind["c"] > ind["sma200"])                 # trend filter
                & (ext.abs() <= 1.0)                       # at value (S4's own threshold)
                & (df["High"] < ind["hi20"].shift(1))      # NOT making a new 20d high
            )
            b = bfwd.reindex(ind.index)
            sub = pd.DataFrame({"sym": s, "rv": ind["rv"], "fwd": fwd, "bench": b})[ctx]
            sub = sub.dropna()
            if len(sub):
                rows.append(sub)
        except Exception:
            continue

    if not rows:
        print("no qualifying bars")
        return pd.DataFrame()
    d = pd.concat(rows, ignore_index=True)
    d["alpha"] = d["fwd"] - d["bench"]
    return d


def report(d: pd.DataFrame, horizon: int) -> None:
    print(f"\n{'RV bucket':<14}{'n':>8}{'mean α':>9}{'med α':>8}{'win%':>7}{'mean fwd':>10}")
    print("  " + "-" * 54)
    for lo, hi in BUCKETS:
        m = d[(d["rv"] >= lo) & (d["rv"] < hi)]
        if len(m) < 50:
            print(f"  RV {lo:.1f}-{hi:<5.1f}{len(m):>8}   (too few to read)")
            continue
        print(f"  RV {lo:.1f}-{hi:<5.1f}{len(m):>8}{m['alpha'].mean():>9.2f}"
              f"{m['alpha'].median():>8.2f}{(m['alpha'] > 0).mean() * 100:>6.0f}%"
              f"{m['fwd'].mean():>10.2f}")
    below = d[d["rv"] < 1.0]
    above = d[d["rv"] >= 1.0]
    dry = d[d["rv"] <= 0.8]
    print("\n  THE GATE'S OWN QUESTION")
    print(f"    REJECTED by rv_floor 1.0 : n={len(below):>6}  mean α {below['alpha'].mean():+.2f}  win {(below['alpha']>0).mean()*100:.0f}%")
    print(f"    ADMITTED by rv_floor 1.0 : n={len(above):>6}  mean α {above['alpha'].mean():+.2f}  win {(above['alpha']>0).mean()*100:.0f}%")
    print(f"    edge of admitting        : {above['alpha'].mean() - below['alpha'].mean():+.2f}pp")
    print(f"    DRY (RV <= 0.8) only     : n={len(dry):>6}  mean α {dry['alpha'].mean():+.2f}  win {(dry['alpha']>0).mean()*100:.0f}%")
    # BLOCK bootstrap, resampling whole SYMBOLS. A bar-level bootstrap here is
    # dishonest: with a 20-session forward window on daily bars, consecutive rows
    # share ~95% of their outcome window, so effective n is nearer rows/horizon
    # than rows. Measured on the first run: bar-level gave [+0.04, +0.39] while
    # the symbol-block CI gave [+0.01, +0.42] - same sign, but the tight one was
    # claiming a precision the data does not have.
    rng = np.random.default_rng(11)
    diffs = []
    syms_u = d["sym"].unique()
    for _ in range(2000):
        pick = rng.choice(syms_u, len(syms_u), replace=True)
        m = d[d["sym"].isin(pick)]
        a = m[m["rv"] >= 1.0]["alpha"]; b = m[m["rv"] < 1.0]["alpha"]
        if len(a) > 30 and len(b) > 30:
            diffs.append(a.mean() - b.mean())
    if diffs:
        lo_ci, hi_ci = np.percentile(diffs, [2.5, 97.5])
        print(f"    symbol-block CI95 of that edge: [{lo_ci:+.2f}, {hi_ci:+.2f}]"
              f"  ->  {'floor is doing real work' if lo_ci > 0 else 'floor NOT justified by this test'}")
        print(f"    (effective n ~ rows/horizon = {len(d)//horizon:,}, not {len(d):,})")
    print(f"\n  horizon {horizon} sessions · alpha = stock fwd return - benchmark over the SAME window")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=250)
    ap.add_argument("--years", type=int, default=3)
    ap.add_argument("--horizon", type=int, default=20)
    a = ap.parse_args()
    d = run(a.limit, a.years, a.horizon)
    if d.empty:
        return 1
    report(d, a.horizon)
    out = os.path.join(_DIR, "validation_runs", f"pullback_rv_ab_h{a.horizon}.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    d.to_csv(out, index=False)
    print(f"  rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
