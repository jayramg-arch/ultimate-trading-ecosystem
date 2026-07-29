"""catalyst_breakdown.py — is the swing drag ONE catalyst or all of them?

Regime is exhausted as an explanation (swing_regime_partition.py: the mkt_bull gate is
already binding and swing is flat inside it). The next question is compositional: does
the swing book fail as a whole, or is one catalyst carrying the loss?

That matters because RETIRING a catalyst is a clean, low-overfit decision — one
yes/no on a named strategy — whereas tuning four catalysts' gates against the same 436
trades is the sweep-and-crown failure this desk keeps being bitten by.

Reported per catalyst, IS and OOS separately (never pooled — the standing lesson):
n · mean/median matched alpha · win% · profit factor · mean raw return · days held.

DECISION FRAME (stated before running, no threshold-fitting after):
  RETIRE candidate  = negative mean alpha in BOTH windows with n >= 50 in each
  KEEP              = positive in both
  UNRESOLVED        = disagrees between windows, or n too small to read
Small-n catalysts (SWG-BO n=5, SWG-GAP n=2 in this run) are reported but CANNOT be
judged — they are shown so the composition is visible, not to be acted on.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DETAILS = "validation_runs/validation_20260728_191035_details.csv"
IS_END = pd.Timestamp("2024-06-01")
MIN_N = 50


def _stats(g):
    a = g["Alpha_Matched_pct"]
    r = g["Return_pct"]
    pf_p, pf_n = r[r > 0].sum(), -r[r <= 0].sum()
    pf = (pf_p / pf_n) if pf_n > 0 else np.inf
    return dict(n=len(g), mean=a.mean(), med=a.median(), win=(a > 0).mean() * 100,
                pf=pf, raw=r.mean(), days=g["Days_Held"].mean(),
                sl=(g["Exit_Reason"] == "SL hit").mean() * 100)


def main():
    d = pd.read_csv(DETAILS)
    d = d[d["Alpha_Matched_pct"].notna()].copy()
    d["ts"] = pd.to_datetime(d["as_of"])
    d["fam"] = np.where(d["Catalyst_used"].str.upper().str.startswith("SWG"), "SWG", "POS")

    hdr = (f"  {'catalyst':12} {'n':>4} {'meanA':>7} {'medA':>7} {'win%':>6} "
           f"{'PF':>6} {'rawRet':>7} {'days':>6} {'SLhit%':>7}")
    for wname, w in (("IN-SAMPLE", d[d["ts"] < IS_END]), ("OUT-OF-SAMPLE", d[d["ts"] >= IS_END])):
        print(f"\n=== {wname} ===")
        print(hdr)
        for fam in ("SWG", "POS"):
            for cat, g in sorted(w[w["fam"] == fam].groupby("Catalyst_used")):
                s = _stats(g)
                print(f"  {cat:12} {s['n']:4d} {s['mean']:+7.2f} {s['med']:+7.2f} {s['win']:6.1f} "
                      f"{s['pf']:6.2f} {s['raw']:+7.2f} {s['days']:6.1f} {s['sl']:7.1f}")
            fg = w[w["fam"] == fam]
            if len(fg):
                s = _stats(fg)
                print(f"  {'  ' + fam + ' total':12} {s['n']:4d} {s['mean']:+7.2f} {s['med']:+7.2f} "
                      f"{s['win']:6.1f} {s['pf']:6.2f} {s['raw']:+7.2f} {s['days']:6.1f} {s['sl']:7.1f}")

    print("\n=== VERDICT PER CATALYST (both windows must agree) ===")
    for cat, g in sorted(d.groupby("Catalyst_used")):
        i = g[g["ts"] < IS_END]["Alpha_Matched_pct"]
        o = g[g["ts"] >= IS_END]["Alpha_Matched_pct"]
        ni, no = len(i), len(o)
        mi = i.mean() if ni else np.nan
        mo = o.mean() if no else np.nan
        if min(ni, no) < MIN_N:
            v = f"UNRESOLVED — n too small ({ni}/{no})"
        elif mi < 0 and mo < 0:
            v = "*** RETIRE CANDIDATE — negative in BOTH windows ***"
        elif mi > 0 and mo > 0:
            v = "KEEP — positive in both"
        else:
            v = "UNRESOLVED — windows disagree"
        print(f"  {cat:12} IS {mi:+6.2f}% (n={ni:3d})   OOS {mo:+6.2f}% (n={no:3d})   {v}")


if __name__ == "__main__":
    main()
