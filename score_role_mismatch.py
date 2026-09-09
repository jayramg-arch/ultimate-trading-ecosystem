# -*- coding: utf-8 -*-
"""score_role_mismatch.py — apply the pre-registered adoption rule A-F to the
roleMismatch A/B arms.

PRE-REGISTERED in docs/PREREG_role_mismatch.md before the arms were run. Nothing here
renegotiates that document; it only evaluates it. Read section 3 first — the instrument
caveat bounds what a PASS can claim.

Usage:  python score_role_mismatch.py --control <id> --treat <id> [-n 10000]
Read-only.
"""
from __future__ import annotations
import argparse, glob, json, os

import numpy as np
import pandas as pd

ALPHA = "Alpha_Matched_pct"
PRIOR = "validation_runs/validation_20260908_191448_details.csv"   # the 18 anchors already looked at


def _load(rid: str):
    det = pd.read_csv("validation_runs/validation_%s_details.csv" % rid)
    meta = {}
    for p in glob.glob("validation_runs/validation_%s_*.json" % rid):
        try:
            meta.update(json.load(open(p)))
        except Exception:
            pass
    return det, meta


def _agg(meta: dict) -> dict:
    a = meta.get("aggregate")
    return a if isinstance(a, dict) else meta


def _blocks(a: pd.DataFrame, b: pd.DataFrame, n_boot: int, seed: int = 11):
    """Symbol-block bootstrap on (mean treat - mean control). Blocks are SYMBOLS, so two
    trades on one name are one piece of evidence, and both arms are drawn from the SAME
    resampled block set."""
    syms = sorted(set(a["Symbol"]) | set(b["Symbol"]))
    ga = {s: g[ALPHA].dropna().values for s, g in a.groupby("Symbol")}
    gb = {s: g[ALPHA].dropna().values for s, g in b.groupby("Symbol")}
    k = len(syms)
    if k < 5:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    out = np.full(n_boot, np.nan)
    for i in range(n_boot):
        pick = [syms[j] for j in rng.integers(0, k, k)]
        la = [ga[s] for s in pick if s in ga]
        lb = [gb[s] for s in pick if s in gb]
        if not la or not lb:
            continue
        xa, xb = np.concatenate(la), np.concatenate(lb)
        if len(xa) >= 3 and len(xb) >= 3:
            out[i] = xb.mean() - xa.mean()
    out = out[~np.isnan(out)]
    if out.size < 100:
        return (np.nan, np.nan, np.nan)
    return (float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5)),
            float((out > 0).mean() * 100.0))


def _stats(d: pd.DataFrame, base_n: int):
    f = d[d[ALPHA].notna()]
    if f.empty:
        return dict(n=0, mean=np.nan, med=np.nan, win=np.nan, keep=0.0, dep=np.nan)
    return dict(n=len(f), mean=f[ALPHA].mean(), med=f[ALPHA].median(),
                win=(f[ALPHA] > 0).mean() * 100,
                keep=len(f) / base_n * 100 if base_n else np.nan,
                dep=f[ALPHA].mean() * len(f) / base_n if base_n else np.nan)


def _report(lab, c, t, n_boot):
    base = len(c[c[ALPHA].notna()])
    sc, st = _stats(c, base), _stats(t, base)
    print("=== %s ===" % lab)
    for nm, s in (("control", sc), ("treat  ", st)):
        print("   %s n=%3d  keep %5.1f%%  mean %+6.2f%%  median %+6.2f%%  win %4.1f%%  deployment %+6.2f%%"
              % (nm, s["n"], s["keep"], s["mean"], s["med"], s["win"], s["dep"]))
    edge = st["mean"] - sc["mean"]
    lo, hi, pp = _blocks(c[c[ALPHA].notna()], t[t[ALPHA].notna()], n_boot)
    print("   treat - control = %+.2fpp   symbol-block CI95=[%+.2f, %+.2f]  P(treat>control)=%.1f%%"
          % (edge, lo, hi, pp))
    print()
    return dict(edge=edge, lo=lo, hi=hi, sc=sc, st=st, base=base)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--control", required=True)
    ap.add_argument("--treat", required=True)
    ap.add_argument("-n", type=int, default=10000)
    # Which ablation flag this pair is testing. The instrument check has to verify the
    # arms actually differ on the knob under test, not merely that they differ.
    ap.add_argument("--flag", default="role_mismatch",
                    help="meta key that must be off in control and on in treat "
                         "(role_mismatch | nonign_min)")
    a = ap.parse_args()

    c, mc = _load(a.control)
    t, mt = _load(a.treat)

    # ── INSTRUMENT GATE (PREREG section 5) — checked BEFORE any result is read ──
    print("--- INSTRUMENT CHECK ---")
    rc, rt = _agg(mc).get(a.flag), _agg(mt).get(a.flag)
    _off = (rc in (False, 0, None))
    _on = (rt is True) or (isinstance(rt, int) and not isinstance(rt, bool) and rt > 0)
    ok_flag = _off and _on
    print("  flags: control %s=%s  treat %s=%s   %s"
          % (a.flag, rc, a.flag, rt, "ok" if ok_flag else "SUSPECT"))
    # QUALIFY MODE. Added after it silently invalidated a full A/B pair: --qualify
    # defaults to "armed", a different population (12x the picks, no catalyst labels,
    # so forward windows fall through to per-pattern horizons). Both arms must match
    # each other AND the control this test extends.
    qc, qt = _agg(mc).get("qualify"), _agg(mt).get("qualify")
    print("  qualify: control=%s  treat=%s   %s"
          % (qc, qt, "ok" if qc == qt == "catalyst" else "*** MISMATCH / NOT catalyst — DISCARD"))
    for nm, d in (("control", c), ("treat", t)):
        if "forward_days_used" in d.columns:
            w = d["forward_days_used"].dropna().astype(int).value_counts().to_dict()
            print("  %-7s forward windows %s%s"
                  % (nm, w, "" if 30 not in w else "   <-- 30d DEFAULT PRESENT"))
    ngc, ngt = int(c["GO_Date"].notna().sum()), int(t["GO_Date"].notna().sum())
    bite = (ngc - ngt) / ngc * 100 if ngc else 0.0
    print("  GOs: control %d  treat %d   gate blocked %d = %.1f%% of control GOs"
          % (ngc, ngt, ngc - ngt, bite))
    if ngc == ngt:
        print("  *** THE GATE EMITTED NOTHING — a broken instrument, not a null. STOP.")
        return 1
    print()

    pooled = _report("POOLED · all %d anchors" % c["as_of"].nunique(), c, t, a.n)

    fresh = None
    if os.path.exists(PRIOR):
        seen = set(pd.read_csv(PRIOR)["as_of"].unique())
        cf, tf = c[~c["as_of"].isin(seen)], t[~t["as_of"].isin(seen)]
        if cf["as_of"].nunique() >= 3:
            fresh = _report("FRESH ONLY · %d anchors never examined in this thread"
                            % cf["as_of"].nunique(), cf, tf, a.n)
        else:
            print("FRESH ONLY: %d unseen anchors — too few to report\n" % cf["as_of"].nunique())

    # ── D · chronological split ──
    print("=== D · CHRONOLOGICAL SPLIT ===")
    anchors = sorted(c["as_of"].unique())
    cut = anchors[len(anchors) // 2]
    halves = []
    for lab, cs, ts in (("IS  (early)", c[c["as_of"] < cut], t[t["as_of"] < cut]),
                        ("OOS (late)", c[c["as_of"] >= cut], t[t["as_of"] >= cut])):
        cv, tv = cs[ALPHA].dropna(), ts[ALPHA].dropna()
        if len(cv) >= 5 and len(tv) >= 5:
            e = tv.mean() - cv.mean()
            halves.append(e)
            print("   %-12s n_c=%3d n_t=%3d   treat-control %+.2fpp   %s"
                  % (lab, len(cv), len(tv), e, "ok" if e > 0 else "REVERSES"))
        else:
            halves.append(np.nan)
            print("   %-12s degenerate" % lab)
    print()

    A = bite >= 15.0
    B = pooled["edge"] >= 1.0
    C = (not np.isnan(pooled["lo"])) and (pooled["lo"] > 0 or pooled["hi"] < 0)
    D = all((not np.isnan(h)) and h > 0 for h in halves)
    E = pooled["st"]["dep"] > pooled["sc"]["dep"]
    F = (fresh is not None) and fresh["edge"] > 0
    print("--- ADOPTION RULE (docs/PREREG_role_mismatch.md section 7) ---")
    print("  A gate bites >= 15%% ....... %5.1f%%        %s" % (bite, "PASS" if A else "FAIL"))
    print("  B edge >= +1.0pp ......... %+.2fpp       %s" % (pooled["edge"], "PASS" if B else "FAIL"))
    print("  C CI excludes zero ....... [%+.2f,%+.2f]  %s" % (pooled["lo"], pooled["hi"], "PASS" if C else "FAIL"))
    print("  D both halves same sign .. %-14s %s" % (["%+.2f" % h for h in halves], "PASS" if D else "FAIL"))
    print("  E' deployment beats ctrl . %+.2f vs %+.2f  %s"
          % (pooled["st"]["dep"], pooled["sc"]["dep"], "PASS" if E else "FAIL"))
    print("  F holds on FRESH anchors . %s          %s"
          % (("%+.2fpp" % fresh["edge"]) if fresh else "n/a   ", "PASS" if F else "FAIL"))
    print()
    print("  VERDICT: %s"
          % ("ADOPT — but see PREREG section 3: this cell measures a PATTERN-ROLE filter, "
             "not the role-vs-location tag, and does not license promoting S4's role tag "
             "from display to gate"
             if all((A, B, C, D, E, F)) else
             "DO NOT ADOPT — role_mismatch stays off; see PREREG section 9 for the v2 "
             "(per-pattern forward alpha: is 'ignition' carrying information, or is it a "
             "label wrapped around POWER_PLAY and POCKET_PIVOT?)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
