"""One index, many wrappers: how separable are they, and is the winner stable?

Jay: "One index has multiple ETFs from different fund houses. When you perform the
analysis on the index, how will you route it to the right ETF?"

The fan-out is material — 11 underlyings carry 27 of the 56 ETFs, gold alone has five.
So index-first needs an answer here or it is not a usable architecture.

The claim this tests is that ROUTING IS NOT PART OF THE SIGNAL. The index answers
"should I be in this basket now"; the wrapper answers "through which instrument", and
that second question is about execution cost, not about the chart. If it is also
mostly STATIC, it can be precomputed and refreshed on a slow cadence rather than
resolved on every signal — which is what makes the whole thing cheap.

Two things decide that:

  1. SEPARABILITY — within a group, is one wrapper clearly better on liquidity, or are
     they close? If the leader dominates, routing is a lookup. If they are close, the
     tie-break has to be real.

  2. VOLATILITY OF THE INPUTS — turnover moves slowly (a fund's franchise does not
     change week to week). PREMIUM does not: it is a market price and it is the one
     input that must be checked at ENTRY rather than precomputed. If premium can flip
     the ranking, the precomputed answer needs an entry-time override.
"""
import os
import sys
import warnings

import pandas as pd

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import etf_universe as eu

try:
    import etf_quality as eq
except Exception as e:
    print("etf_quality unavailable:", e)
    eq = None


def groups():
    g = {}
    for sym, meta in eu.ETF_UNIVERSE.items():
        key = meta.get("underlying") or meta.get("benchmark_yf") or "?"
        g.setdefault(key, []).append(sym)
    return {k: v for k, v in g.items() if len(v) > 1}


if __name__ == "__main__":
    G = groups()
    print(f"{len(G)} underlyings with more than one wrapper\n")

    rows = []
    for und, syms in sorted(G.items()):
        print(f"── {und} ({len(syms)}) " + "─" * max(0, 44 - len(und)))
        print(f"   {'symbol':14}{'issuer':9}{'tier':>5}{'turnover Cr':>13}{'premium %':>11}{'grade':>7}")
        best_liq, best_sym = -1.0, None
        for s in sorted(syms):
            q = eq.quality(s) if eq else None
            m = eu.ETF_UNIVERSE[s]
            t = (q or {}).get("turnover_cr")
            p = (q or {}).get("premium_pct")
            gr = (q or {}).get("grade") or "—"
            ts = f"{t:.1f}" if t is not None else "—"
            ps = f"{p:+.2f}" if p is not None else "—"
            print(f"   {s:14}{str(m.get('issuer'))[:8]:9}{str(m.get('liquidity_tier')):>5}"
                  f"{ts:>13}{ps:>11}{gr:>7}")
            if t is not None and t > best_liq:
                best_liq, best_sym = t, s
            rows.append({"underlying": und, "symbol": s, "turnover": t, "premium": p})
        # How dominant is the leader? A big gap means routing is a lookup.
        ts_ = sorted([r["turnover"] for r in rows if r["underlying"] == und
                      and r["turnover"] is not None], reverse=True)
        if len(ts_) >= 2 and ts_[1] > 0:
            print(f"   -> leader {best_sym} at {ts_[0]:.1f}Cr, runner-up {ts_[1]:.1f}Cr "
                  f"({ts_[0]/ts_[1]:.1f}x)")
        elif ts_:
            print(f"   -> only one wrapper carries turnover data ({best_sym})")
        print()

    df = pd.DataFrame(rows)
    have = df.dropna(subset=["turnover"])
    print("── SEPARABILITY ────────────────────────────────────────────")
    if not have.empty:
        gaps = []
        for und, sub in have.groupby("underlying"):
            t = sorted(sub["turnover"], reverse=True)
            if len(t) >= 2 and t[1] > 0:
                gaps.append((und, t[0] / t[1]))
        if gaps:
            gaps.sort(key=lambda x: -x[1])
            print(f"   leader-vs-runner-up turnover ratio, {len(gaps)} groups:")
            for u, r in gaps:
                print(f"     {u:22}{r:>8.1f}x")
            dom = sum(1 for _, r in gaps if r >= 3)
            print(f"\n   {dom} of {len(gaps)} groups have a leader >=3x the runner-up")
    print(f"\n   premium available for {df['premium'].notna().sum()} of {len(df)} wrappers")
    print(f"   turnover available for {df['turnover'].notna().sum()} of {len(df)} wrappers")
