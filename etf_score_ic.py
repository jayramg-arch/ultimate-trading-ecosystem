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
    ap.add_argument("--liquid-only", action="store_true",
                    help="Restrict to names that CLEAR the live liquidity gate "
                         "(LIQ_MIN_CR) at the anchor. This is the decisive test for "
                         "the Liquidity component: illiquid ETFs are already filtered "
                         "out before anything is recommended, so an edge that only "
                         "exists by comparing tradeable names against ones the system "
                         "would never surface is not an edge you can act on.")
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

    # The benchmark has to be fetched WITH the universe: score_rs needs it aligned
    # bar-for-bar, and a separate call can return a different index.
    close_df, vol_df = S._fetch_history(
        [f"{s}.NS" for s in syms] + [S.BENCHMARK_YF], period="5y")
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

    COMPONENTS = ["Liquidity", "Trend", "RS", "Rotation", "TOTAL"]
    bench = close_df["^CRSLDX"] if "^CRSLDX" in close_df.columns else (
        close_df[S.BENCHMARK_YF] if S.BENCHMARK_YF in close_df.columns else None)
    if bench is None:
        print("benchmark column missing - RS and Rotation cannot be scored")
        return 1
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
                comp = {}
                _t = S.score_trend(px)
                comp["Trend"] = float(_t[0])
                _vcol = col if vol_df is not None and col in vol_df.columns else None
                _v = vol_df[_vcol].loc[:a].dropna() if _vcol else pd.Series(dtype=float)
                _lq = S.score_liquidity(px, _v) if len(_v) else None
                comp["Liquidity"] = float(_lq[0]) if _lq else np.nan
                if args.liquid_only and (not _lq or float(_lq[1]) < S.LIQ_MIN_CR):
                    continue          # would never have reached a recommendation
                _r = S.score_rs(px, bench.loc[:a].dropna())
                comp["RS"] = float(_r[0])
                comp["Rotation"] = float(S.score_rotation(_r[3], _r[1], _r[2]))
                # The composite the screener actually publishes is the SUM of the
                # four. Recomputed here rather than read from a CSV so it is
                # point-in-time like its parts, and so a component that turns out to
                # carry the signal can be compared against the whole on one axis.
                comp["TOTAL"] = float(np.nansum([comp[k] for k in
                                                 ("Liquidity", "Trend", "RS", "Rotation")]))
                trend = comp["TOTAL"]
            except Exception as e:
                errs[type(e).__name__ + ": " + str(e)[:60]] =                     errs.get(type(e).__name__ + ": " + str(e)[:60], 0) + 1
                continue
            p0 = px.iloc[-1]
            pN = fwd[col].dropna()
            if not np.isfinite(p0) or p0 <= 0 or pN.empty:
                continue
            row = {"sym": s, "fwd": (float(pN.iloc[-1]) / p0 - 1.0) * 100.0}
            row.update(comp)
            scored.append(row)

        if len(scored) < 10:
            continue
        d = pd.DataFrame(scored)
        k = max(3, len(d) // 4)
        rec = {"anchor": a.date(), "n": len(d)}
        for cname in COMPONENTS:
            if cname not in d.columns or d[cname].notna().sum() < 10:
                continue
            dd = d[[cname, "fwd"]].dropna()
            if dd[cname].nunique() < 3:      # a constant score cannot rank anything
                continue
            rec["ic_" + cname] = stats.spearmanr(dd[cname], dd["fwd"]).correlation
            rec["sp_" + cname] = (dd.nlargest(k, cname)["fwd"].mean()
                                  - dd.nsmallest(k, cname)["fwd"].mean())
        rows.append(rec)

    if errs:
        print("scoring errors (symbol-anchor pairs skipped):")
        for k, v in sorted(errs.items(), key=lambda x: -x[1])[:5]:
            print("   %6d  %s" % (v, k))
        print()
    if not rows:
        print("no usable anchors")
        return 1
    # Per-component columns now, so there is no single "ic" to drop on. Keep any
    # anchor that scored at least one component -- dropping the row because ONE
    # component was unscoreable would silently shrink the sample for the others.
    R = pd.DataFrame(rows)
    R = R[[c for c in R.columns if c.startswith(("ic_", "sp_"))] + ["anchor", "n"]]

    def boot(v):
        """Resample ANCHORS, not observations -- rows inside one anchor share a
        market and are not independent."""
        rng = np.random.default_rng(7)
        m = [rng.choice(v, size=len(v), replace=True).mean() for _ in range(args.boot)]
        return np.percentile(m, 2.5), np.percentile(m, 97.5), float((np.array(m) > 0).mean())

    print(f"{'anchors used':<12}{len(R)}    horizon {args.horizon}d")
    print()
    print(f"{'component':<12}{'rank IC':>9}{'IC>0':>8}   {'spread':>8}   {'CI95 spread':>20}  {'P(>0)':>7}")
    print("-" * 74)
    out = {}
    for cname in COMPONENTS:
        ick, spk = "ic_" + cname, "sp_" + cname
        if ick not in R.columns:
            continue
        ic = R[ick].dropna()
        sp = R[spk].dropna()
        if ic.empty or sp.empty:
            continue
        lo, hi, pp = boot(sp.values)
        out[cname] = (ic.mean(), sp.mean(), lo, hi, pp)
        print(f"{cname:<12}{ic.mean():>+9.4f}{(ic > 0).mean()*100:>7.0f}%   "
              f"{sp.mean():>+7.2f}pp   [{lo:>+6.2f}, {hi:>+6.2f}]  {pp*100:>6.1f}%")
    print("-" * 74)
    winners = [c for c, v in out.items() if v[2] > 0]
    print()
    print("CI95 EXCLUDES ZERO:", ", ".join(winners) if winners else "none")
    print()
    print("Read per component, not pooled. A composite can be flat while one leg")
    print("carries signal and another cancels it -- which is the whole reason for")
    print("this run. A CI that includes zero means this sample cannot tell the")
    print("component apart from noise; it is not evidence of absence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
