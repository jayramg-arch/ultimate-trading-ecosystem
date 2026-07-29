"""beta_adjusted_alpha.py — how much of the "alpha" is just beta?

THE QUESTION. Every alpha number this system reports is RAW excess return:
`alpha = stock_return - benchmark_return` over the matched hold. It contains no beta
adjustment. But Stage-2 breakout names are high-beta by construction, so in a rising
tape they should outperform the index MECHANICALLY, with no skill involved.

The POS-BO decay diagnostic made this concrete:
    IN-SAMPLE   benchmark +4.17%   stock leg +9.78%   -> "alpha" +5.61%
    OUT-SAMPLE  benchmark -1.59%   stock leg -0.58%   -> "alpha" +1.01%
If the picks carry beta ~1.5, then +4.17% of market alone predicts ~+6.3% of stock
return before any selection skill — which would account for MOST of the in-sample
"alpha", and would mean the headline number is largely leverage on a bull market.

THE TEST. Jensen-style, with beta estimated STRICTLY EX-ANTE:
    beta_i    = cov(r_stock, r_bench) / var(r_bench) over the 250 trading days
                ENDING AT THE ANCHOR (no data from the holding period touches it)
    alpha_adj = stock_return - beta_i * benchmark_return   (both matched-horizon)
Raw alpha is the special case beta = 1. If beta-adjusted alpha collapses while raw
alpha does not, the edge was leverage. If it survives, the selection is real.

WHAT WOULD FALSIFY THE "IT IS ALL BETA" STORY: beta-adjusted alpha staying materially
positive in-sample, AND the IS/OOS gap narrowing (because the gap itself is largely the
market's own swing from +4.17% to -1.59%, amplified by beta).

KNOWN LIMITS, STATED UP FRONT:
- No risk-free rate. Proper Jensen alpha is (Rp-Rf) - beta(Rm-Rf); omitting Rf biases
  alpha by (beta-1)*Rf. Over a ~41-day hold at ~6.5%/yr that is roughly 0.35pp at
  beta 1.5 — real but second-order, and it makes these numbers slightly OPTIMISTIC.
- Trailing beta is an estimate; realised beta during the trade can differ, especially
  for a stock breaking out.
- Beta is estimated on the same universe/period as the picks, so it inherits the run's
  survivorship caveat.
Read-only. No production code touched.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DETAILS = "validation_runs/validation_20260728_191035_details.csv"
BENCH = "^CRSLDX"
IS_END = pd.Timestamp("2024-06-01")
BETA_WIN = 250
MIN_OVERLAP = 120


def main():
    import data_provider as dp

    d = pd.read_csv(DETAILS)
    d = d[d["Alpha_Matched_pct"].notna() & d["Benchmark_Matched_pct"].notna()].copy()
    d["ts"] = pd.to_datetime(d["as_of"])
    d["fam"] = np.where(d["Catalyst_used"].str.upper().str.startswith("SWG"), "SWG", "POS")

    bdf = dp.fetch_ohlcv(BENCH, period="10y", interval="1d")
    br = bdf["Close"].pct_change()

    betas = []
    for sym, g in d.groupby("Symbol"):
        try:
            f = dp.fetch_ohlcv(sym, period="10y", interval="1d")
        except Exception:
            f = None
        sr = f["Close"].pct_change() if f is not None and len(f) > 60 else None
        for _, r in g.iterrows():
            b = np.nan
            if sr is not None:
                try:
                    j = pd.concat([sr, br], axis=1, join="inner").dropna()
                    j = j.loc[:r["ts"]].tail(BETA_WIN)          # EX-ANTE: ends at the anchor
                    if len(j) >= MIN_OVERLAP:
                        s, m = j.iloc[:, 0].to_numpy(), j.iloc[:, 1].to_numpy()
                        v = m.var()
                        if v > 0:
                            b = float(np.cov(s, m)[0, 1] / v)
                except Exception:
                    pass
            betas.append(b)
    d["beta"] = betas
    d = d[d["beta"].notna() & np.isfinite(d["beta"])].copy()
    # guard against degenerate estimates from thin/illiquid history
    d = d[(d["beta"] > -1.0) & (d["beta"] < 4.0)]
    d["alpha_adj"] = d["Return_pct"] - d["beta"] * d["Benchmark_Matched_pct"]

    print(f"trades with usable ex-ante beta: {len(d)}")
    print(f"beta distribution: median {d['beta'].median():.2f}  "
          f"mean {d['beta'].mean():.2f}  p25 {d['beta'].quantile(.25):.2f}  "
          f"p75 {d['beta'].quantile(.75):.2f}\n")

    def blk(w, name):
        raw = w["Alpha_Matched_pct"].mean()
        adj = w["alpha_adj"].mean()
        print(f"  {name:26} n={len(w):4d}  beta {w['beta'].median():4.2f}  "
              f"bench {w['Benchmark_Matched_pct'].mean():+6.2f}%  "
              f"RAW alpha {raw:+6.2f}%  BETA-ADJ {adj:+6.2f}%  "
              f"({adj-raw:+6.2f}pp)  adj-median {w['alpha_adj'].median():+6.2f}%")
        return raw, adj

    print("=== WHOLE BOOK ===")
    for nm, w in (("ALL", d), ("IN-SAMPLE", d[d["ts"] < IS_END]), ("OUT-SAMPLE", d[d["ts"] >= IS_END])):
        blk(w, nm)

    print("\n=== BY FAMILY ===")
    for fam in ("POS", "SWG"):
        f = d[d["fam"] == fam]
        print(f"  -- {fam} --")
        r_is, a_is = blk(f[f["ts"] < IS_END], "IN-SAMPLE")
        r_oo, a_oo = blk(f[f["ts"] >= IS_END], "OUT-SAMPLE")
        print(f"     IS->OOS gap:  RAW {r_is-r_oo:+.2f}pp   BETA-ADJ {a_is-a_oo:+.2f}pp"
              f"   (gap explained by beta: {(1-(a_is-a_oo)/(r_is-r_oo))*100:.0f}%)"
              if (r_is - r_oo) != 0 else "")

    print("\n=== POS-BO (the headline catalyst) ===")
    p = d[d["Catalyst_used"] == "POS-BO"]
    for nm, w in (("IN-SAMPLE", p[p["ts"] < IS_END]), ("OUT-SAMPLE", p[p["ts"] >= IS_END])):
        blk(w, nm)

    print("\n=== VERDICT ===")
    pi = p[p["ts"] < IS_END]
    po = p[p["ts"] >= IS_END]
    if len(pi) and len(po):
        r_gap = pi["Alpha_Matched_pct"].mean() - po["Alpha_Matched_pct"].mean()
        a_gap = pi["alpha_adj"].mean() - po["alpha_adj"].mean()
        share = (1 - a_gap / r_gap) * 100 if r_gap else np.nan
        print(f"  POS-BO IS->OOS gap: RAW {r_gap:+.2f}pp -> BETA-ADJ {a_gap:+.2f}pp "
              f"({share:.0f}% of the 'decay' was beta)")
        print(f"  POS-BO beta-adjusted alpha:  IS {pi['alpha_adj'].mean():+.2f}%   "
              f"OOS {po['alpha_adj'].mean():+.2f}%")
        if pi["alpha_adj"].mean() > 0 and po["alpha_adj"].mean() > 0:
            print("  -> SELECTION SURVIVES beta adjustment in BOTH windows.")
        elif pi["alpha_adj"].mean() > 0:
            print("  -> Selection positive IS, NOT out of sample after beta adjustment.")
        else:
            print("  -> The raw 'alpha' was largely LEVERAGE, not selection.")


if __name__ == "__main__":
    main()
