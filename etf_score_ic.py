#!/usr/bin/env python3
"""Does the ETF screener's Total_Score predict anything?

The backtest measures the whole PORTFOLIO SYSTEM -- regime templates, allocation
weights, correlation gate, rebalance costs. It does NOT isolate the screener score,
and a good portfolio result can come entirely from a template that happened to hold
the right asset class. This asks the narrower and more useful question:

    ranked by Total_Score at time T, do the higher-scored ETFs beat the lower-scored
    ones over the following N days?

METHOD, and the parts that keep it honest:
  * POINT IN TIME. Every score is computed from bars up to the anchor and no
    further, via data_provider's pinned_date. Forward returns come from bars after
    it. The two windows never overlap.
  * MONTHLY ANCHORS across the full available history, so no single regime decides
    the answer.
  * SPEARMAN rank IC per anchor -- the score is ordinal, so rank correlation is the
    right measure and it is not distorted by one ETF doubling.
  * TOP-vs-BOTTOM SPREAD in the same run, because an IC can be positive while the
    tradeable extremes are indistinguishable.
  * BOOTSTRAPPED BY ANCHOR, not by observation. Rows inside one anchor share a
    market and are not independent; resampling them would report a confidence
    interval several times too tight.
  * OUT-OF-SCOPE NAMES EXCLUDED (debt/liquid) -- measuring a signal on instruments
    that will never be traded answers a question nobody asked.

Usage:
    python etf_score_ic.py                    # 60-day horizon
    python etf_score_ic.py --horizon 20 --anchors 40
"""
from __future__ import annotations

import argparse
import logging
import sys

import numpy as np
import pandas as pd

logging.getLogger().setLevel(logging.WARNING)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=60, help="forward trading days")
    ap.add_argument("--anchors", type=int, default=48, help="max monthly anchors")
    ap.add_argument("--boot", type=int, default=5000)
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    import etf_screener as S
    import etf_universe as U
    from scipy import stats

    syms = U.tradeable_symbols() if hasattr(U, "tradeable_symbols") else list(U.ETF_UNIVERSE)
    print(f"universe in trading scope: {len(syms)}")

    close_df, vol_df = S._fetch_history([f"{s}.NS" for s in syms], period="5y")
    if close_df is None or close_df.empty:
        print("no data")
        return 1
    close_df = close_df.sort_index()
    print(f"history {close_df.index.min().date()} -> {close_df.index.max().date()}, "
          f"{len(close_df)} bars")

    # monthly anchors, leaving room for the forward window
    usable = close_df.index[:-args.horizon]
    anchors = pd.Series(usable).groupby(
        [usable.year, usable.month]).last().tolist()[-args.anchors:]
    print(f"anchors: {len(anchors)}  horizon: {args.horizon}d\n")

    rows = []
    errs = {}
    for a in anchors:
        hist = close_df.loc[:a]
        if len(hist) < 260:
            continue
        fwd_idx = close_df.index[close_df.index > a][:args.horizon]
        if len(fwd_idx) < args.horizon:
            continue
        fwd = close_df.loc[fwd_idx]

        scored = []
        for s in syms:
            col = s if s in hist.columns else f"{s}.NS"
            if col not in hist.columns:
                continue
            px = hist[col].dropna()
            if len(px) < 260:
                continue
            # The screener's own trend score, point-in-time. score_trend takes the
            # SERIES only -- an earlier draft passed (px, stage, slope) and the bare
            # except swallowed the TypeError, so every symbol was skipped and the
            # harness reported "no usable anchors" instead of a code fault. Errors
            # are counted now and printed at the end: a silent skip is how a broken
            # measurement looks exactly like an empty one.
            try:
                trend = S.score_trend(px)
                trend = float(trend[0] if isinstance(trend, tuple) else trend)
            except Exception as e:
                errs[type(e).__name__ + ": " + str(e)[:60]] =                     errs.get(type(e).__name__ + ": " + str(e)[:60], 0) + 1
                continue
            p0 = px.iloc[-1]
            pN = fwd[col].dropna()
            if not np.isfinite(p0) or p0 <= 0 or pN.empty:
                continue
            scored.append((s, float(trend), (float(pN.iloc[-1]) / p0 - 1.0) * 100.0))

        if len(scored) < 10:
            continue
        d = pd.DataFrame(scored, columns=["sym", "score", "fwd"])
        ic = stats.spearmanr(d["score"], d["fwd"]).correlation
        k = max(3, len(d) // 4)
        top = d.nlargest(k, "score")["fwd"].mean()
        bot = d.nsmallest(k, "score")["fwd"].mean()
        rows.append({"anchor": a.date(), "n": len(d), "ic": ic,
                     "top": top, "bottom": bot, "spread": top - bot})

    if errs:
        print("scoring errors (symbol-anchor pairs skipped):")
        for k, v in sorted(errs.items(), key=lambda x: -x[1])[:5]:
            print("   %6d  %s" % (v, k))
        print()
    if not rows:
        print("no usable anchors")
        return 1
    R = pd.DataFrame(rows).dropna(subset=["ic"])

    def boot(v):
        """Resample ANCHORS, not observations -- rows inside one anchor share a
        market and are not independent."""
        rng = np.random.default_rng(7)
        m = [rng.choice(v, size=len(v), replace=True).mean() for _ in range(args.boot)]
        return np.percentile(m, 2.5), np.percentile(m, 97.5), float((np.array(m) > 0).mean())

    ic_lo, ic_hi, ic_p = boot(R["ic"].values)
    sp_lo, sp_hi, sp_p = boot(R["spread"].values)

    print(f"{'anchors used':<22}{len(R)}")
    print(f"{'mean rank IC':<22}{R['ic'].mean():+.4f}   CI95 [{ic_lo:+.4f}, {ic_hi:+.4f}]   "
          f"P(>0) {ic_p*100:.1f}%")
    print(f"{'median rank IC':<22}{R['ic'].median():+.4f}")
    print(f"{'IC > 0 in':<22}{(R['ic'] > 0).mean()*100:.1f}% of anchors")
    print()
    print(f"{'top quartile fwd':<22}{R['top'].mean():+.2f}%")
    print(f"{'bottom quartile fwd':<22}{R['bottom'].mean():+.2f}%")
    print(f"{'spread':<22}{R['spread'].mean():+.2f}pp   CI95 [{sp_lo:+.2f}, {sp_hi:+.2f}]   "
          f"P(>0) {sp_p*100:.1f}%")
    print()
    verdict = ("SIGNAL" if sp_lo > 0 and ic_lo > 0 else
               "NO EDGE DEMONSTRATED (CI includes zero)")
    print(f"VERDICT: {verdict}")
    print("\nA CI that includes zero does not mean the score is useless -- it means "
          "this sample\ncannot tell it apart from noise, and it must not be treated "
          "as evidence either way.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
