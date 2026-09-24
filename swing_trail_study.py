"""swing_trail_study.py — how wide should the swing trail be? (docs/PREREG_swing_trail.md)

Entries, initial stops and the house exit structure are frozen (T1 2R / T2 4R, 33/33,
breakeven after T1, 0.10%/leg, no time stop). Only the trail changes:

  C    the backtest's current trail — highest close SINCE ENTRY − 4.5 × ATR14 (SMA),
       updated with the current bar's ATR (replay._simulate_one_trade, reproduced exactly)
  Wk   the LIVE trail (risk_common.chandelier_exit, swing window) — highest close of the
       last 14 bars − k × ATR(14, Wilder), from the PRIOR bar's values, tighten-only

  --placebo  shuffled demeaned returns (reuses exit_ladder_study._placebo)
  --validate C must reproduce the recorded returns
  --run      the single real run (marker-guarded)
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

OUT = X.OUT_DIR
MARKER = os.path.join(OUT, "_swing_trail_REAL_RUN_DONE.json")
VALID = os.path.join(OUT, "_swing_trail_VALIDATED.json")
WIDTHS = (1.5, 2.5, 3.5, 4.5)
WIN = 14
BAR_R, MED_R = 0.10, 0.10
ALPHA_FW = 0.10
N_BOOT = 5000
FAMILY = "SWG-PB"


def simulate(df, pos, entry, sl, t1, t2, mode, k=None):
    """House structure, one trail. mode 'C' = replay's trail; 'W' = live Chandelier."""
    H, L, C = (df[c].values for c in ("High", "Low", "Close"))
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr_sma = tr.rolling(14).mean().values
    atr_w = tr.ewm(alpha=1 / WIN, adjust=False).mean().values
    hc_w = c.rolling(WIN).max().values
    r_unit = entry - sl
    q1, q2 = 33.0, 33.0
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
                stop = max(stop, hc - a * 4.5)
        else:
            a, hcn = atr_w[p - 1], hc_w[p - 1]
            if not (np.isnan(a) or np.isnan(hcn)):
                lvl = hcn - k * a
                # THE LIVE BREACHED RULE (Amendment 1, found by the placebo): a Chandelier
                # level at or above the prior close is reported BREACHED by the trail job
                # and never pushed to the broker. Without this, a pullback entry — whose
                # 14-bar high sits above the entry — got a stop ABOVE the market, filled at
                # a price that never traded.
                if lvl < C[p - 1]:
                    stop = max(stop, lvl)
        if L[p] <= stop and qty > 0:
            sell(stop, qty)
            reason = "SL hit" if stop == sl else "Trail SL"
            break
        if not hit1 and H[p] >= t1:
            sell(t1, q1); legs += 1; hit1 = True
            stop = max(stop, entry)
        if not hit2 and H[p] >= t2 and qty > 0:
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


def run_all(d, frames):
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
        t1 = entry * float(r["T1_price"]) / rec_e
        t2 = entry * float(r["T2_price"]) / rec_e
        if not (0 < sl < entry):
            continue
        rec = {"Symbol": r["Symbol"], "ts": r["ts"], "rec_ret": r["Return_pct"]}
        o = simulate(f, pos, entry, sl, t1, t2, "C")
        rec["C_R"], rec["C_ret"], rec["C_why"] = o["R"], o["ret"], o["reason"]
        for k in WIDTHS:
            o = simulate(f, pos, entry, sl, t1, t2, "W", k)
            rec[f"W{k}_R"], rec[f"W{k}_days"], rec[f"W{k}_why"] = o["R"], o["days"], o["reason"]
        rows.append(rec)
    return pd.DataFrame(rows)


def split(R, d):
    anchors = sorted(d["ts"].unique())
    n_is = int(round(len(anchors) * X.IS_FRAC))
    oos0 = anchors[n_is]
    cutoff = oos0 - pd.Timedelta(days=X.EMBARGO_DAYS)
    is_a = [a for a in anchors[:n_is] if a <= cutoff]
    return R[R["ts"].isin(is_a)], R[R["ts"] >= oos0]


def boot_p(sub, a, b, rng):
    diff = (sub[a] - sub[b]).values
    u, inv = np.unique(sub["Symbol"].values, return_inverse=True)
    sums, cnts = np.bincount(inv, weights=diff), np.bincount(inv).astype(float)
    idx = rng.integers(0, len(u), size=(N_BOOT, len(u)))
    m = sums[idx].sum(1) / cnts[idx].sum(1)
    return float((m <= 0).mean()), np.percentile(m, [2.5, 97.5])


def report(R, d, label, rng):
    IS, OOS = split(R, d)
    print(f"\n==== {label} ====  IS {len(IS)} · OOS {len(OOS)} trades ({FAMILY})")
    print(f"  {'trail':8}{'IS meanR':>10}{'IS medR':>9}{'OOS meanR':>11}{'OOS medR':>10}{'trail-exit%':>12}{'days':>6}")
    cols = ["C_R"] + [f"W{k}_R" for k in WIDTHS]
    for col in cols:
        why = col.replace("_R", "_why")
        tr = (R[why] == "Trail SL").mean() * 100 if why in R else float("nan")
        dcol = col.replace("_R", "_days")
        dd = R[dcol].median() if dcol in R else float("nan")
        print(f"  {col[:-2]:8}{IS[col].mean():+10.3f}{IS[col].median():+9.3f}{OOS[col].mean():+11.3f}"
              f"{OOS[col].median():+10.3f}{tr:12.1f}{dd:6.0f}")
    base = "W1.5_R"
    ps, rows = {}, []
    for k in WIDTHS[1:]:
        col = f"W{k}_R"
        di, do = IS[col].mean() - IS[base].mean(), OOS[col].mean() - OOS[base].mean()
        mdi = IS[col].median() - IS[base].median()
        mdo = OOS[col].median() - OOS[base].median()
        pi, _ = boot_p(IS, col, base, rng)
        po, _ = boot_p(OOS, col, base, rng)
        _, ci = boot_p(R, col, base, rng)
        size = di >= BAR_R and do >= BAR_R and mdi >= -MED_R and mdo >= -MED_R and ci[0] > 0
        rows.append(dict(k=k, dIS=di, dOOS=do, dmedIS=mdi, dmedOOS=mdo, ci=ci, size=size))
        ps[k] = max(pi, po)
    keys = sorted(ps, key=ps.get)
    alive, holm = True, {}
    for i, k in enumerate(keys):
        ok = alive and ps[k] <= ALPHA_FW / (len(keys) - i)
        holm[k] = ok
        alive = alive and ok
    print("\n  vs W1.5 (live): bar +0.10R IS and OOS, median not worse by 0.10R, CI excludes 0, Holm")
    winners = []
    for r_ in rows:
        passed = r_["size"] and holm[r_["k"]]
        if passed:
            winners.append(r_["k"])
        print(f"  W{r_['k']}: ΔIS {r_['dIS']:+.3f}R  ΔOOS {r_['dOOS']:+.3f}R  Δmed {r_['dmedIS']:+.3f}/{r_['dmedOOS']:+.3f}"
              f"  CI [{r_['ci'][0]:+.3f}, {r_['ci'][1]:+.3f}]  p {ps[r_['k']]:.3f}  → {'PASS' if passed else 'fail'}")
    # plateau: 4.5 may only win if 3.5 also passes
    if 4.5 in winners and 3.5 not in winners:
        winners.remove(4.5)
        print("  W4.5 passes alone at the grid edge → fails the plateau rule")
    chosen = max(winners, key=lambda k: dict((r["k"], r["dOOS"]) for r in rows)[k]) if winners else 1.5
    print(f"\n  → trail width to use: {chosen}×  ({'1.5× stays: nothing wider qualified' if not winners else 'a wider width qualified'})")
    return chosen, rows


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--placebo", action="store_true")
    g.add_argument("--validate", action="store_true")
    g.add_argument("--run", action="store_true")
    a = ap.parse_args()
    rng = np.random.default_rng(31)
    if a.run:
        if os.path.exists(MARKER):
            sys.exit(f"REFUSED: already run ({MARKER}).")
        if not os.path.exists(VALID):
            sys.exit("REFUSED: run --validate first.")
    d, frames, _b = X.load(placebo=a.placebo, seed=7)
    d = d[d["Catalyst_used"].astype(str).str.upper() == FAMILY].copy()
    R = run_all(d, frames)
    print(f"{FAMILY} trades simulated {len(R)}")
    if a.validate:
        err = (R["C_ret"] - R["rec_ret"]).abs()
        med, within = err.median(), (err <= 1.0).mean()
        ok = med <= 0.25 and within >= 0.95
        print(f"C vs recorded: median |err| {med:.3f}pp, within 1pp {within*100:.1f}% → {'VALID' if ok else 'FAIL'}")
        if ok:
            json.dump({"at": datetime.now().isoformat()}, open(VALID, "w"))
        return
    chosen, rows = report(R, d, "PLACEBO" if a.placebo else "REAL RUN", rng)
    if a.run:
        R.to_csv(os.path.join(OUT, "_swing_trail_trades.csv"), index=False)
        json.dump({"at": datetime.now().isoformat(), "chosen": chosen}, open(MARKER, "w"))
        print("saved; marker written.")


if __name__ == "__main__":
    main()
