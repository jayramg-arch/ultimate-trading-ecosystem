"""wyckoff_veto_study.py — does a Wyckoff DISTRIBUTION reading at signal time
predict worse forward alpha?

PRE-REGISTERED before any result was inspected (28-Jul-2026). Written this way
deliberately: this desk's largest documented statistical liability is uncorrected
multiple testing (98 validation runs, 4 alpha-selected sweeps, 3 A/Bs whose winners
became defaults, zero Bonferroni/FDR/PBO). A veto invented after staring at cuts of
the same 464 trades would be indistinguishable from noise-fitting.

THE QUESTION
------------
`wcl_context.wyckoff_state()` gives a bias (ACCUMULATION / DISTRIBUTION / NEUTRAL),
a tier (+4..-4) and an age. WCL currently only GRADES with it (confluence, the board's
Overall, Kelly size). The proposal is to let a fresh distribution reading VETO a
trade outright. This script measures whether that is justified.

DESIGN — why this is clean where the GO-confirmation study was not
------------------------------------------------------------------
The 23-Jul confirmation study was endogenous: it detected confirmation inside
[D, D+40] while measuring returns over [D, D+H] — overlapping windows, so "it
rallied" caused both. Here the Wyckoff state is computed STRICTLY from bars <= the
anchor date and the outcome is the already-computed matched-horizon alpha over
[D, D+H]. Disjoint by construction. Point-in-time is enforced by truncating each
symbol's frame at the anchor date before the detector runs.

PRIMARY HYPOTHESIS (one, stated up front)
-----------------------------------------
H1: picks whose Wyckoff reading at the anchor is DISTRIBUTION with tier <= -3
    (SOW / UT / LPSY) and age <= 15 bars have LOWER mean matched-horizon alpha
    than picks without it.

ADOPTION RULE (stated before seeing the answer — do not renegotiate after)
-------------------------------------------------------------------------
Adopt the veto ONLY if ALL of:
  A. n_vetoed >= 30 trades (below that the cell is noise; cf. the 4-16 name cells
     that produced the retracted GO-filter claim).
  B. Vetoed cohort mean alpha is at least 2.0pp WORSE than the kept cohort.
  C. The sign holds in BOTH halves of a chronological split (no window where the
     vetoed cohort is better).
  D. The veto does not remove more than 20% of all picks (a filter that kills a
     fifth of the book needs a far higher bar than a marginal one).
Anything less: report it and do NOT wire it. "No edge" is a valid, publishable result.

SECONDARY VARIANTS (pre-declared, reported in full, NOT cherry-picked)
----------------------------------------------------------------------
  V1 any DISTRIBUTION bias (tier <= -1)
  V2 decayed score_comp < 0 (the value that actually feeds the context total)
  V3 tier <= -3 with a looser age <= 30
All are reported whether they help or not, so the reader can see the whole
family and discount accordingly.

Usage:  python wyckoff_veto_study.py [--details <csv>] [--tf daily]
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

import wcl_context as W

DETAILS_DEFAULT = "validation_runs/validation_20260726_225547_details.csv"


def _load_frames(symbols, quiet=False):
    """One full daily history per unique symbol; sliced per-anchor later."""
    import data_provider as dp
    out = {}
    for i, s in enumerate(sorted(symbols), 1):
        try:
            df = dp.fetch_ohlcv(s, period="5y", interval="1d")
            if df is not None and len(df) >= 260:
                out[s] = df
        except Exception:
            pass
        if not quiet and i % 25 == 0:
            print(f"  fetched {i}/{len(symbols)} …", file=sys.stderr)
    return out


def _state_asof(df, as_of):
    """Wyckoff state using ONLY bars <= as_of. Truncating the frame is exactly
    point-in-time for a bar-based detector — no look-ahead is possible."""
    try:
        cut = df.loc[:pd.Timestamp(as_of)]
    except Exception:
        return None
    if len(cut) < 120:
        return None
    return W.wyckoff_state(cut)


def _report(d, mask, label):
    v, k = d[mask], d[~mask]
    if len(v) == 0:
        return f"{label:34} n=0 — never fires"
    edge = v["Alpha_Matched_pct"].mean() - k["Alpha_Matched_pct"].mean()
    return (f"{label:34} vetoed n={len(v):3d} ({len(v)/len(d)*100:4.1f}%) "
            f"a={v['Alpha_Matched_pct'].mean():+6.2f}% win={(v['Alpha_Matched_pct']>0).mean()*100:4.1f}%  |  "
            f"kept n={len(k):3d} a={k['Alpha_Matched_pct'].mean():+6.2f}% "
            f"win={(k['Alpha_Matched_pct']>0).mean()*100:4.1f}%  |  edge {edge:+.2f}pp")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--details", default=DETAILS_DEFAULT)
    args = ap.parse_args()

    d = pd.read_csv(args.details)
    d = d[d["Alpha_Matched_pct"].notna()].copy()
    print(f"trades={len(d)}  symbols={d['Symbol'].nunique()}  anchors={d['as_of'].nunique()}")

    frames = _load_frames(d["Symbol"].unique())
    print(f"frames resolved: {len(frames)}/{d['Symbol'].nunique()}")

    tier, age, bias = [], [], []
    for _, r in d.iterrows():
        st = _state_asof(frames.get(r["Symbol"]), r["as_of"]) if r["Symbol"] in frames else None
        tier.append(st["score_base"] if st else np.nan)
        age.append(st["age_bars"] if st else np.nan)
        bias.append(st["bias"] if st else None)
    d["wyk_tier"], d["wyk_age"], d["wyk_bias"] = tier, age, bias

    d = d[d["wyk_bias"].notna()].copy()
    print(f"trades with a resolved as-of Wyckoff state: {len(d)}")
    print(f"baseline: mean alpha {d['Alpha_Matched_pct'].mean():+.2f}%  "
          f"win {(d['Alpha_Matched_pct']>0).mean()*100:.1f}%\n")
    print("bias mix at signal time:", d["wyk_bias"].value_counts().to_dict(), "\n")

    primary = (d["wyk_tier"] <= -3) & (d["wyk_age"] <= 15)
    variants = [
        ("PRIMARY tier<=-3 & age<=15", primary),
        ("V1 any DISTRIBUTION", d["wyk_bias"] == "DISTRIBUTION"),
        ("V2 decayed comp < 0", (d["wyk_tier"] < 0) & (d["wyk_age"] <= 60)),
        ("V3 tier<=-3 & age<=30", (d["wyk_tier"] <= -3) & (d["wyk_age"] <= 30)),
    ]
    for lab, m in variants:
        print(_report(d, m, lab))

    # Adoption rule, evaluated mechanically on the PRIMARY only.
    v, k = d[primary], d[~primary]
    print("\n--- ADOPTION RULE (primary) ---")
    A = len(v) >= 30
    B = (len(v) > 0) and (v["Alpha_Matched_pct"].mean() <= k["Alpha_Matched_pct"].mean() - 2.0)
    D_ = len(v) / len(d) <= 0.20
    print(f"  A n>=30 .................. {len(v):4d}      {'PASS' if A else 'FAIL'}")
    print(f"  B edge <= -2.0pp ......... "
          f"{(v['Alpha_Matched_pct'].mean()-k['Alpha_Matched_pct'].mean()) if len(v) else float('nan'):+6.2f}pp  "
          f"{'PASS' if B else 'FAIL'}")
    ds = d.sort_values("as_of")
    half = len(ds) // 2
    C = True
    for nm, part in (("early", ds.iloc[:half]), ("late", ds.iloc[half:])):
        pm = (part["wyk_tier"] <= -3) & (part["wyk_age"] <= 15)
        pv, pk = part[pm], part[~pm]
        e = (pv["Alpha_Matched_pct"].mean() - pk["Alpha_Matched_pct"].mean()) if len(pv) else float("nan")
        print(f"  C {nm:5} split ........... n={len(pv):3d} edge {e:+6.2f}pp")
        if not (len(pv) > 0 and e < 0):
            C = False
    print(f"  C sign holds both halves .. {'PASS' if C else 'FAIL'}")
    print(f"  D removes <=20% .......... {len(v)/len(d)*100:5.1f}%    {'PASS' if D_ else 'FAIL'}")
    print(f"\n  VERDICT: {'ADOPT' if (A and B and C and D_) else 'DO NOT WIRE'}")


if __name__ == "__main__":
    main()
