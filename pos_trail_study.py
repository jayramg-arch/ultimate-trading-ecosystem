"""pos_trail_study.py — positional trail: backtest (C) vs the live Chandelier (L).

Implements docs/PREREG_pos_trail.md. Entries, stops, recorded T1/T2, partials
(bull_screener.partial_qty_for — POS 25/25), breakeven after T1, 0.10%/leg, no time stop:
all frozen. Only the trail changes.

  C       replay's trail: highest close SINCE ENTRY − 4.5 × ATR14 (SMA), current bar
  L       live (risk_common.chandelier_exit, positional): 22-bar highest close − 4.5 × Wilder
          ATR(22), PRIOR bar, tighten-only, BREACHED rule (no level at/above the prior close)
  Lbear   L with +0.5× when ^CRSLDX was not bull (close>SMA200 & SMA50>SMA200) on the prior
          bar — reported only

  --placebo / --validate / --run   (run is marker-guarded; validate must pass first)
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

import exit_ladder_study as X
import swing_trail_study as S
import bull_screener as bs

OUT = X.OUT_DIR
MARKER = os.path.join(OUT, "_pos_trail_REAL_RUN_DONE.json")
VALID = os.path.join(OUT, "_pos_trail_VALIDATED.json")
WIN, K = 22, 4.5
BAR_R = 0.10
N_BOOT = 5000
FAMS = ("POS-BO", "POS-ACCUM")
MIN_N = 40


def simulate(df, pos, entry, sl, t1, t2, q1, q2, mode, bull=None):
    H, L, C = (df[c].values for c in ("High", "Low", "Close"))
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr_sma = tr.rolling(14).mean().values
    atr_w = tr.ewm(alpha=1 / WIN, adjust=False).mean().values
    hc_w = c.rolling(WIN).max().values
    r_unit = entry - sl
    qty, pnl, legs = 100.0, 0.0, 2
    stop, hc = sl, entry
    hit1 = hit2 = False
    days, reason = 0, ""
    end = min(pos + 1 + X.MAX_BARS, len(df))

    def sell(px, q):
        nonlocal pnl, qty
        q = min(q, qty)
        pnl += (px - entry) / entry * 100.0 * (q / 100.0)
        qty -= q

    for p in range(pos + 1, end):
        days = p - pos
        if mode == "C":
            a = atr_sma[p]
            if not np.isnan(a):
                stop = max(stop, hc - a * K)
        else:
            a, hcn = atr_w[p - 1], hc_w[p - 1]
            if not (np.isnan(a) or np.isnan(hcn)):
                k = K + (0.5 if (mode == "Lbear" and bull is not None and not bull[p - 1]) else 0.0)
                lvl = hcn - k * a
                if lvl < C[p - 1]:                    # BREACHED rule, as the live job
                    stop = max(stop, lvl)
        if L[p] <= stop and qty > 0:
            sell(stop, qty)
            reason = "SL hit" if stop == sl else "Trail SL"
            break
        if not hit1 and t1 and H[p] >= t1:
            sell(t1, q1); legs += 1; hit1 = True
            stop = max(stop, entry)
        if not hit2 and t2 and H[p] >= t2 and qty > 0:
            sell(t2, q2); legs += 1; hit2 = True
        hc = max(hc, C[p])
        if qty <= 1e-9:
            reason = "Targets"
            break
    if qty > 1e-9:
        sell(C[end - 1], qty)
        reason = reason or "Still open"
    pnl -= legs * X.COST
    return {"ret": pnl, "R": pnl / (r_unit / entry * 100.0), "days": days, "reason": reason}


def bull_flags(bench_close, index):
    b = bench_close.copy()
    b.index = pd.to_datetime(b.index).tz_localize(None) if getattr(b.index, "tz", None) else pd.to_datetime(b.index)
    s200, s50 = b.rolling(200).mean(), b.rolling(50).mean()
    ok = ((b > s200) & (s50 > s200)).reindex(index, method="ffill")
    return ok.fillna(True).values


def run_all(d, frames, bench):
    rows = []
    for _, r in d.iterrows():
        f = frames.get(r["Symbol"])
        if f is None:
            continue
        pos = f.index.searchsorted(r["ts"], side="right") - 1
        if pos < 30:
            continue
        rec_e = float(r["Entry_Close"])
        entry = float(f["Close"].iloc[pos])
        sl = entry * float(r["SL_price"]) / rec_e
        t1 = entry * float(r["T1_price"]) / rec_e if pd.notna(r["T1_price"]) else None
        t2 = entry * float(r["T2_price"]) / rec_e if pd.notna(r["T2_price"]) else None
        if not (0 < sl < entry):
            continue
        q1, q2 = bs.partial_qty_for(r["Catalyst_used"])
        bull = bull_flags(bench, f.index)
        rec = {"Symbol": r["Symbol"], "ts": r["ts"], "fam": r["Catalyst_used"], "rec_ret": r["Return_pct"]}
        for mode in ("C", "L", "Lbear"):
            o = simulate(f, pos, entry, sl, t1, t2, q1, q2, mode, bull)
            rec[f"{mode}_R"], rec[f"{mode}_ret"] = o["R"], o["ret"]
            rec[f"{mode}_why"], rec[f"{mode}_days"] = o["reason"], o["days"]
        rows.append(rec)
    return pd.DataFrame(rows)


def report(R, d, label, rng):
    print(f"\n==== {label} ====")
    out = {}
    for fam in FAMS:
        Rf = R[R["fam"] == fam]
        IS, OOS = S.split(Rf, d)
        print(f"\n  {fam}: IS {len(IS)} · OOS {len(OOS)}")
        print(f"  {'trail':7}{'IS meanR':>10}{'IS medR':>9}{'OOS meanR':>11}{'OOS medR':>10}{'trail-exit%':>12}{'days':>6}")
        for m in ("C", "L", "Lbear"):
            col = f"{m}_R"
            tr = (Rf[f"{m}_why"] == "Trail SL").mean() * 100
            print(f"  {m:7}{IS[col].mean():+10.3f}{IS[col].median():+9.3f}{OOS[col].mean():+11.3f}"
                  f"{OOS[col].median():+10.3f}{tr:12.1f}{Rf[f'{m}_days'].median():6.0f}")
        dIS = IS["L_R"].mean() - IS["C_R"].mean()
        dOOS = OOS["L_R"].mean() - OOS["C_R"].mean()
        dmed = Rf["L_R"].median() - Rf["C_R"].median()
        _, ci = S.boot_p(Rf, "L_R", "C_R", rng)
        thin = min(len(IS), len(OOS)) < MIN_N
        worse = (dIS <= -BAR_R and dOOS <= -BAR_R and dmed < 0 and ci[1] < 0)
        verdict = "THIN" if thin else ("LIVE MATERIALLY WORSE — do not align" if worse else "ALIGN (live not materially worse)")
        print(f"  L − C: IS {dIS:+.3f}R  OOS {dOOS:+.3f}R  Δmed {dmed:+.3f}R  CI95 [{ci[0]:+.3f}, {ci[1]:+.3f}]  → {verdict}")
        out[fam] = dict(dIS=dIS, dOOS=dOOS, dmed=dmed, ci=[float(ci[0]), float(ci[1])], verdict=verdict)
    return out


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    for f in ("placebo", "validate", "run"):
        g.add_argument("--" + f, action="store_true")
    a = ap.parse_args()
    rng = np.random.default_rng(37)
    if a.run:
        if os.path.exists(MARKER):
            sys.exit(f"REFUSED: already run ({MARKER}).")
        if not os.path.exists(VALID):
            sys.exit("REFUSED: run --validate first.")
    d, frames, bench = X.load(placebo=a.placebo, seed=7)
    d = d[d["Catalyst_used"].astype(str).str.upper().isin(FAMS)].copy()
    R = run_all(d, frames, bench)
    print(f"POS trades simulated {len(R)}  " + str(R["fam"].value_counts().to_dict()))
    if a.validate:
        err = (R["C_ret"] - R["rec_ret"]).abs()
        med, within = err.median(), (err <= 1.0).mean()
        ok = med <= 0.25 and within >= 0.95
        print(f"C vs recorded: median |err| {med:.3f}pp, within 1pp {within*100:.1f}% → {'VALID' if ok else 'FAIL'}")
        if ok:
            json.dump({"at": datetime.now().isoformat()}, open(VALID, "w"))
        return
    res = report(R, d, "PLACEBO" if a.placebo else "REAL RUN", rng)
    if a.run:
        R.to_csv(os.path.join(OUT, "_pos_trail_trades.csv"), index=False)
        json.dump({"at": datetime.now().isoformat(), **res}, open(MARKER, "w"))
        print("\nsaved; marker written.")


if __name__ == "__main__":
    main()
