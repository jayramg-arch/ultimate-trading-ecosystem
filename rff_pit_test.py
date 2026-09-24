"""rff_pit_test.py — does the recovery fundamental gate survive point-in-time data?

Implements docs/PREREG_rff_pit.md EXACTLY. Written after the pre-registration and before
the replay finished. Input: a recovery replay run with RECOVERY_NO_FUNDAMENTALS=1 (the RFF
gate off, no live fundamentals), so every technically-qualified pick is present. Each
(symbol, anchor) then gets its point-in-time RFF from screener_history.

  --coverage   print how many picks get a PIT score, per anchor (no outcomes)
  --placebo    RFF_PIT shuffled within each anchor — any pass is a bug
  --run        the single real run (marker-guarded)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import screener_history as SH

_DIR = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(_DIR, "validation_runs")
MARKER = os.path.join(RUNS, "_rff_pit_REAL_RUN_DONE.json")
IS_FRAC, EMBARGO_DAYS = 0.6, 45
BAR_PP = 1.0
MIN_N = 40
N_BOOT = 5000


def load(run_id: str) -> pd.DataFrame:
    d = pd.read_csv(os.path.join(RUNS, f"validation_{run_id}_details.csv"))
    d = d[d["Alpha_Matched_pct"].notna()].copy()
    if "Signal" in d.columns:                       # CB-Watch is Signal 1 — a pre-signal
        d = d[pd.to_numeric(d["Signal"], errors="coerce").fillna(2) >= 2]
    d = d[d["Catalyst_used"].astype(str).str.upper() != "CB-WATCH"]
    d["ts"] = pd.to_datetime(d["as_of"])
    risk = (d["Entry_Close"] - d["SL_price"]) / d["Entry_Close"] * 100
    d["R"] = d["Return_pct"] / risk.where(risk > 0)
    cache = {}
    rows = []
    for _, r in d.iterrows():
        s = str(r["Symbol"])
        if s not in cache:
            html = SH.fetch_page(s)
            cache[s] = SH.parse_tables(html) if html else None
        t = cache[s]
        res = SH.rff_pit(t, r["ts"]) if t is not None else {"quality": "NO_PAGE", "passed": 0, "n_known": 0}
        rows.append((res["quality"], res["passed"], res["n_known"]))
    d["pit_quality"], d["pit_passed"], d["pit_known"] = zip(*rows)
    return d


def split(d):
    anchors = sorted(d["ts"].unique())
    n_is = int(round(len(anchors) * IS_FRAC))
    oos0 = anchors[n_is]
    cutoff = oos0 - pd.Timedelta(days=EMBARGO_DAYS)
    is_a = [a for a in anchors[:n_is] if a <= cutoff]
    return d[d["ts"].isin(is_a)], d[d["ts"] >= oos0]


def boot_diff(hi, lo, rng, col="Alpha_Matched_pct"):
    """Symbol-block bootstrap of mean(hi) − mean(lo)."""
    both = pd.concat([hi.assign(_g=1), lo.assign(_g=0)])
    syms = both["Symbol"].unique()
    grp = {s: g for s, g in both.groupby("Symbol")}
    out = []
    for _ in range(N_BOOT):
        pick = rng.choice(syms, size=len(syms), replace=True)
        b = pd.concat([grp[s] for s in pick])
        h, l = b[b["_g"] == 1][col], b[b["_g"] == 0][col]
        if len(h) and len(l):
            out.append(h.mean() - l.mean())
    return np.array(out)


def report(d, label, rng, cut=4):
    s = d[d["pit_quality"] == "OK"]
    hi, lo = s[s["pit_passed"] >= cut], s[s["pit_passed"] < cut]
    IS, OOS = split(s)
    print(f"\n==== {label} · cut ≥{cut} of 5 ====")
    print(f"  scored {len(s)} of {len(d)} picks · high {len(hi)} · low {len(lo)}")
    res = {}
    for lab, W in (("IS", IS), ("OOS", OOS), ("ALL", s)):
        h, l = W[W["pit_passed"] >= cut], W[W["pit_passed"] < cut]
        dm = h["Alpha_Matched_pct"].mean() - l["Alpha_Matched_pct"].mean()
        dmed = h["Alpha_Matched_pct"].median() - l["Alpha_Matched_pct"].median()
        dR = h["R"].mean() - l["R"].mean()
        res[lab] = dict(n_hi=len(h), n_lo=len(l), dmean=dm, dmed=dmed, dR=dR)
        print(f"  {lab:3} hi n={len(h):4} α {h['Alpha_Matched_pct'].mean():+6.2f}%  "
              f"lo n={len(l):4} α {l['Alpha_Matched_pct'].mean():+6.2f}%  "
              f"Δ {dm:+.2f}pp  Δmed {dmed:+.2f}  ΔR {dR:+.3f}")
    b = boot_diff(s[s["pit_passed"] >= cut], s[s["pit_passed"] < cut], rng)
    lo_ci, hi_ci = np.percentile(b, [2.5, 97.5])
    print(f"  pooled Δ CI95 [{lo_ci:+.2f}, {hi_ci:+.2f}]")
    thin = min(res["IS"]["n_hi"], res["IS"]["n_lo"], res["OOS"]["n_hi"], res["OOS"]["n_lo"]) < MIN_N
    passed = (not thin and res["IS"]["dmean"] >= BAR_PP and res["OOS"]["dmean"] >= BAR_PP
              and lo_ci > 0 and res["ALL"]["dmed"] >= 0)
    verdict = "THIN" if thin else ("PASS" if passed else "FAIL")
    print(f"  → {verdict}")
    fam = s["Catalyst_used"].astype(str).str.upper().str.replace(r"^(WYC).*", "WYC-*", regex=True)
    print("  per family (ALL, reported only):")
    for f, g in s.assign(fam=fam).groupby("fam"):
        h, l = g[g["pit_passed"] >= cut], g[g["pit_passed"] < cut]
        if len(h) and len(l):
            print(f"    {f:10} hi n={len(h):3} {h['Alpha_Matched_pct'].mean():+6.2f}%  "
                  f"lo n={len(l):3} {l['Alpha_Matched_pct'].mean():+6.2f}%  "
                  f"Δ {h['Alpha_Matched_pct'].mean() - l['Alpha_Matched_pct'].mean():+.2f}pp")
    return verdict, res, (lo_ci, hi_ci)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--coverage", action="store_true")
    g.add_argument("--placebo", action="store_true")
    g.add_argument("--run", action="store_true")
    a = ap.parse_args()
    rng = np.random.default_rng(29)
    d = load(a.run_id)
    if a.coverage:
        IS, OOS = split(d)
        for lab, W in (("IS", IS), ("OOS", OOS)):
            ok = (W["pit_quality"] == "OK").mean() * 100
            print(f"{lab}: {len(W)} picks, PIT-scored {ok:.1f}%")
        print(d.groupby("as_of")["pit_quality"].apply(lambda x: (x == "OK").mean() * 100).round(0).to_string())
        print(d["pit_quality"].value_counts().to_string())
        return
    if a.placebo:
        d = d.copy()
        d["pit_passed"] = d.groupby("as_of")["pit_passed"].transform(
            lambda x: x.sample(frac=1, random_state=5).values)
        report(d, "PLACEBO (RFF_PIT shuffled within anchor)", rng)
        return
    if os.path.exists(MARKER):
        sys.exit(f"REFUSED: already run ({MARKER}).")
    v, res, ci = report(d, "REAL RUN · primary", rng, cut=4)
    report(d, "REAL RUN · secondary (reported only)", rng, cut=5)
    d.to_csv(os.path.join(RUNS, "_rff_pit_trades.csv"), index=False)
    json.dump({"at": datetime.now().isoformat(), "run": a.run_id, "verdict": v},
              open(MARKER, "w"))
    print("\nsaved _rff_pit_trades.csv; marker written.")


if __name__ == "__main__":
    main()
