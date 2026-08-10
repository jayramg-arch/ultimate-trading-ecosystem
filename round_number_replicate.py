#!/usr/bin/env python3
"""Round-number entry effect — does it REPLICATE across independent samples?

The first cut (s4go_pivot_round_ab.py, 261 GO-gated trades) showed entries near round
numbers stopping out more, monotonic in roundness: R100 76.1% / R50 74.0% / R10 67.7% /
R5 68.1% at a 0.50% band. Suggestive, but one cut with n=46 in the cleanest cell.

An OOS split of that same 261 would just halve an already-thin sample. Replication on a
SEPARATE sample is the stronger test and is what Jay's own confluence rule asks for: the
same claim, measured somewhere it was not fitted.

SAMPLES (independent by construction — different entry rule, different trade population):
  S1  s4go GO-gated entries   (buy-stop/retest at the GO bar)   n=261
  S2  buy@close baseline      (entry at the anchor close)       n=464
  S3  POS-only re-baseline    (subset lineage of S2, reported but NOT counted as
                               independent — it shares anchors and picks with S2)

Read S1 vs S2. If the direction and the monotonicity both survive, it is real enough to
justify a properly-gated study. If only one shows it, it is noise.

Metric is ENTRY EXECUTION — initial-SL-hit rate and hold length — not positional alpha,
because Osler measures a 15-minute bounce and BHJ a 24-hour one while these trades hold
30-180 days. Bootstrap CI on the stop-out-rate DIFFERENCE, since that is the headline.
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
RUNS = os.path.join(HERE, "validation_runs")

ROUND_TIERS = [(100.0, "R100"), (50.0, "R50"), (10.0, "R10"), (5.0, "R5")]
MIN_PX = 20.0
BAND = 0.50          # % — the band the first cut read cleanest at
N_BOOT = 10000
RNG = np.random.default_rng(20260810)     # fixed: this must reproduce


def dists(px):
    out = {t: np.nan for _s, t in ROUND_TIERS}
    if not px or px != px or px < MIN_PX:
        return out
    for step, tag in ROUND_TIERS:
        nearest = round(px / step) * step
        if nearest > 0:
            out[tag] = abs(px - nearest) / px * 100.0
    return out


def load(path, px_col):
    d = pd.read_csv(path)
    d = d[d.get("Status", "OK").astype(str).isin(["OK", "nan"]) | d.get("Status").isna()] \
        if "Status" in d.columns else d
    d = d[pd.to_numeric(d[px_col], errors="coerce").notna()].copy()
    d["px"] = pd.to_numeric(d[px_col], errors="coerce")
    dd = d["px"].map(dists)
    for _s, t in ROUND_TIERS:
        d[f"d_{t}"] = [x[t] for x in dd]
    if "Hit_Initial_SL" in d.columns:
        d["initSL"] = d["Hit_Initial_SL"].astype(str).str.lower().isin(["true", "1", "1.0"])
    else:
        d["initSL"] = d["Exit_Reason"].astype(str).eq("SL hit")
    d["hold"] = pd.to_numeric(d.get("Days_Held"), errors="coerce")
    return d


def boot_diff(at, off):
    """Bootstrap the stop-out-rate DIFFERENCE (near - away), percentage points."""
    a = at.to_numpy(dtype=float); b = off.to_numpy(dtype=float)
    if len(a) < 5 or len(b) < 5:
        return np.nan, np.nan, np.nan
    obs = (a.mean() - b.mean()) * 100
    ds = np.empty(N_BOOT)
    for i in range(N_BOOT):
        ds[i] = (RNG.choice(a, len(a), replace=True).mean()
                 - RNG.choice(b, len(b), replace=True).mean()) * 100
    return obs, float(np.percentile(ds, 2.5)), float(np.percentile(ds, 97.5))


def report(name, d):
    print(f"\n{'='*74}\n  {name}   n={len(d)}\n{'='*74}")
    print(f"  {'tier':6} {'n_near':>7} {'n_away':>7} {'SL_near':>8} {'SL_away':>8} "
          f"{'diff_pp':>8} {'CI95':>18} {'hold_near':>10} {'hold_away':>10}")
    rows = []
    for _s, t in ROUND_TIERS:
        c = f"d_{t}"
        at = d[d[c] <= BAND]; off = d[d[c] > BAND]
        if len(at) < 5 or len(off) < 5:
            print(f"  {t:6} {len(at):7d} {len(off):7d}   — too few"); continue
        obs, lo, hi = boot_diff(at["initSL"], off["initSL"])
        sig = "*" if (lo > 0 or hi < 0) else " "
        print(f"  {t:6} {len(at):7d} {len(off):7d} {at['initSL'].mean()*100:7.1f}% "
              f"{off['initSL'].mean()*100:7.1f}% {obs:+7.1f}{sig} "
              f"[{lo:+6.1f},{hi:+6.1f}] {at['hold'].mean():9.1f}d {off['hold'].mean():9.1f}d")
        rows.append((t, obs, lo, hi))
    mono = [r[1] for r in rows]
    if len(mono) == 4:
        ok = mono[0] >= mono[1] >= mono[2] and mono[0] >= mono[3]
        print(f"\n  monotonic in roundness (R100 >= R50 >= R10/R5)? {'YES' if ok else 'no'}"
              f"   [{', '.join(f'{m:+.1f}' for m in mono)}]")
    return rows


def main():
    print("ROUND-NUMBER ENTRY EFFECT — replication across independent samples")
    print(f"band = {BAND}% of price · metric = initial-SL-hit rate · bootstrap n={N_BOOT}")
    print("* = 95% CI excludes zero")

    s1p = os.path.join(RUNS, "_round_number_partition.csv")
    out = {}
    if os.path.exists(s1p):
        out["S1"] = report("S1  s4go GO-gated entries", load(s1p, "Entry_Price"))
    else:
        print("\n  S1 missing — run s4go_pivot_round_ab.py first")
    out["S2"] = report("S2  buy@close baseline 20260726_225547 (INDEPENDENT)",
                       load(os.path.join(RUNS, "validation_20260726_225547_details.csv"), "Entry_Close"))
    out["S3"] = report("S3  POS-only 20260809_194851 (shares lineage with S2 — not independent)",
                       load(os.path.join(RUNS, "validation_20260809_194851_details.csv"), "Entry_Close"))

    print(f"\n{'='*74}\n  VERDICT\n{'='*74}")
    if "S1" in out and out["S1"] and out["S2"]:
        d1 = {t: v for t, v, _l, _h in out["S1"]}
        d2 = {t: v for t, v, _l, _h in out["S2"]}
        agree = [t for t in d1 if t in d2 and np.sign(d1[t]) == np.sign(d2[t]) and abs(d1[t]) > 1]
        print(f"  tiers agreeing in SIGN across the two independent samples: "
              f"{agree if agree else 'none'}")
        print("  S1: " + ", ".join(f"{t}{v:+.1f}pp" for t, v in d1.items()))
        print("  S2: " + ", ".join(f"{t}{v:+.1f}pp" for t, v in d2.items()))
    print("\n  A tier only counts as replicated if BOTH samples move the same way AND at")
    print("  least one CI excludes zero. Anything else is one noisy cut, and the current")
    print("  +1 confluence weight for round-number proximity stays untouched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
