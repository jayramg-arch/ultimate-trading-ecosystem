"""add_premise_study.py — does pyramiding a winner pay, and does it beat a new position?

Implements docs/PREREG_add_premise.md. POS trades of validation_20260819_112959 replayed with
the live Chandelier (pos_trail_study mode "L"); the first bar where pyramid_logic's ADD rung
holds (rebuilt point-in-time; the Score clause dropped, as registered) buys an add leg at that
close. The add's stop = the position stop raised to the current Chandelier; the add has no
targets, rides the trail with the runner, and every add raises the whole position's stop.

Indicator definitions copied from pyramid_logic.load_open_positions: ATR14 = SMA of TR,
EMA20 span 20, c5 = close 5 sessions back, 200-DMA slope = 10-bar % change > 0.

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
import pa_patterns as pap
from rrg_engine import calculate_jdk_rrg
from rrg_cell_remeasure import quadrant

OUT = X.OUT_DIR
MARKER = os.path.join(OUT, "_add_premise_REAL_RUN_DONE.json")
VALID = os.path.join(OUT, "_add_premise_VALIDATED.json")
WIN, K = 22, 4.5
ADD_MAX_EXT_ATR = 2.0
BAR_R, MIN_N, N_BOOT = 0.10, 40, 5000
FAMS = ("POS-BO", "POS-ACCUM")


def weekly_quadrants(df, bench_close):
    """Series indexed by week label (W-FRI) -> quadrant; causal (SMA-based JdK)."""
    # Closes only (the placebo frames carry no Volume), same rule as
    # pa_patterns._confirmed_weekly_ohlcv: W-FRI, the forming week dropped.
    ws = df["Close"].resample("W-FRI").last().dropna()
    if len(ws) and df.index[-1].normalize() < ws.index[-1].normalize():
        ws = ws.iloc[:-1]
    b = bench_close.copy()
    b.index = pd.to_datetime(b.index).tz_localize(None) if getattr(b.index, "tz", None) else pd.to_datetime(b.index)
    wb = b.resample("W-FRI").last().dropna()
    rrg = calculate_jdk_rrg(ws, wb, mode="strike_cal")
    if rrg is None or rrg.empty:
        return pd.Series(dtype=object)
    rrg = rrg.dropna()
    return pd.Series([quadrant(r, m) for r, m in zip(rrg["RS_Ratio"], rrg["RS_Momentum"])], index=rrg.index)


def simulate(df, pos, entry, sl, t1, t2, q1, q2, quads, with_add, simple_trigger=False):
    idx = df.index
    H, L, C = (df[c].values for c in ("High", "Low", "Close"))
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr_w = tr.ewm(alpha=1 / WIN, adjust=False).mean().values
    hc_w = c.rolling(WIN).max().values
    atr14 = tr.rolling(14).mean().values
    ema20 = c.ewm(span=20, adjust=False).mean().values
    s200 = c.rolling(200).mean()
    slope = ((s200 - s200.shift(10)) / s200.shift(10) * 100).values
    s200 = s200.values
    r_unit = entry - sl
    qty, pnl, legs = 100.0, 0.0, 2
    stop = sl
    hit1 = hit2 = False
    add = None                       # dict(px, stop, day)
    add_out = None
    end = min(pos + 1 + X.MAX_BARS, len(df))
    qidx = quads.index if len(quads) else None

    def sell(px, q):
        nonlocal pnl, qty
        q = min(q, qty)
        pnl += (px - entry) / entry * 100.0 * (q / 100.0)
        qty -= q

    for p in range(pos + 1, end):
        a, hcn = atr_w[p - 1], hc_w[p - 1]
        if not (np.isnan(a) or np.isnan(hcn)):
            lvl = hcn - K * a
            if lvl < C[p - 1]:
                stop = max(stop, lvl)
        if L[p] <= stop and qty > 0:
            sell(stop, qty)
            if add is not None and add_out is None:
                add_out = (stop, p)
            break
        if not hit1 and t1 and H[p] >= t1:
            sell(t1, q1); legs += 1; hit1 = True
            stop = max(stop, entry)
        if not hit2 and t2 and H[p] >= t2 and qty > 0:
            sell(t2, q2); legs += 1; hit2 = True
        if qty <= 1e-9:
            break
        # ── ADD trigger at this bar's close (first add only) ──
        if with_add and add is None and p >= 6:
            pnl_pct = (C[p] / entry - 1.0) * 100.0
            if simple_trigger:
                fire = C[p] >= entry + r_unit
            else:
                q = None
                if qidx is not None:
                    k = qidx.searchsorted(idx[p], side="right") - 1
                    q = quads.iloc[k] if k >= 0 else None
                leader = ((q in ("LEADING", "WEAKENING") and pnl_pct >= 5.0) or
                          (q == "LEADING" and pnl_pct >= 8.0))
                ext = (C[p] - ema20[p]) / atr14[p] if atr14[p] and not np.isnan(atr14[p]) else np.nan
                loc = (not np.isnan(s200[p]) and C[p] > s200[p] and not np.isnan(slope[p]) and slope[p] > 0
                       and C[p] <= C[p - 5] * 1.10 and C[p] > ema20[p]
                       and not np.isnan(ext) and ext <= ADD_MAX_EXT_ATR)
                fire = leader and loc
            if fire:
                ch = hc_w[p] - K * atr_w[p]
                ch = ch if (not np.isnan(ch) and ch < C[p]) else -np.inf
                astop = max(stop, ch)
                if astop < C[p]:
                    add = {"px": C[p], "stop": astop, "day": p}
                    stop = astop                  # every add raises the WHOLE position's stop
    if qty > 1e-9:
        sell(C[end - 1], qty)
    if add is not None and add_out is None:
        add_out = (C[end - 1], end - 1)
    pnl -= legs * X.COST
    res = {"R": pnl / (r_unit / entry * 100.0), "ret": pnl}
    if add is not None:
        ex, exd = add_out
        aret = (ex - add["px"]) / add["px"] * 100.0 - 2 * X.COST
        arisk = (add["px"] - add["stop"]) / add["px"] * 100.0
        res.update(add_R=aret / arisk if arisk > 0 else np.nan, add_ret=aret,
                   add_days=exd - add["day"], add_after=add["day"] - pos,
                   add_ext=(add["px"] / entry - 1) * 100)
    return res


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
        quads = weekly_quadrants(f, bench)
        base = simulate(f, pos, entry, sl, t1, t2, q1, q2, quads, with_add=False)
        wa = simulate(f, pos, entry, sl, t1, t2, q1, q2, quads, with_add=True)
        sa = simulate(f, pos, entry, sl, t1, t2, q1, q2, quads, with_add=True, simple_trigger=True)
        rows.append({"Symbol": r["Symbol"], "ts": r["ts"], "fam": r["Catalyst_used"],
                     "base_R": base["R"], "base_ret": base["ret"],
                     "add_R": wa.get("add_R", np.nan), "add_after": wa.get("add_after", np.nan),
                     "add_days": wa.get("add_days", np.nan), "add_ext": wa.get("add_ext", np.nan),
                     "withadd_base_R": wa["R"], "simple_add_R": sa.get("add_R", np.nan)})
    return pd.DataFrame(rows)


def boot_mean(sub, col, rng):
    u, inv = np.unique(sub["Symbol"].values, return_inverse=True)
    v = sub[col].values
    sums, cnts = np.bincount(inv, weights=v), np.bincount(inv).astype(float)
    idx = rng.integers(0, len(u), size=(N_BOOT, len(u)))
    return np.percentile(sums[idx].sum(1) / cnts[idx].sum(1), [2.5, 97.5])


def boot_diff(a, acol, b, bcol, rng):
    both = pd.concat([a[["Symbol", acol]].rename(columns={acol: "v"}).assign(_g=1),
                      b[["Symbol", bcol]].rename(columns={bcol: "v"}).assign(_g=0)])
    syms = both["Symbol"].unique(); grp = {s: g for s, g in both.groupby("Symbol")}
    out = []
    for _ in range(N_BOOT):
        bb = pd.concat([grp[s] for s in rng.choice(syms, size=len(syms), replace=True)])
        x, y = bb.loc[bb["_g"] == 1, "v"], bb.loc[bb["_g"] == 0, "v"]
        if len(x) and len(y):
            out.append(x.mean() - y.mean())
    return np.percentile(out, [2.5, 97.5])


def report(R, d, label, rng):
    print(f"\n==== {label} ====   POS trades {len(R)} · adds fired {R['add_R'].notna().sum()} "
          f"({R['add_R'].notna().mean()*100:.0f}%) · simple-trigger adds {R['simple_add_R'].notna().sum()}")
    IS, OOS = S.split(R, d)
    A_IS, A_OOS = IS[IS["add_R"].notna()], OOS[OOS["add_R"].notna()]
    print(f"  add legs      IS n={len(A_IS)} mean {A_IS['add_R'].mean():+.3f}R med {A_IS['add_R'].median():+.3f}"
          f"   OOS n={len(A_OOS)} mean {A_OOS['add_R'].mean():+.3f}R med {A_OOS['add_R'].median():+.3f}")
    print(f"  new entries   IS n={len(IS)} mean {IS['base_R'].mean():+.3f}R med {IS['base_R'].median():+.3f}"
          f"   OOS n={len(OOS)} mean {OOS['base_R'].mean():+.3f}R med {OOS['base_R'].median():+.3f}")
    A = R[R["add_R"].notna()]
    ci1 = boot_mean(A, "add_R", rng) if len(A) else (np.nan, np.nan)
    thin = min(len(A_IS), len(A_OOS)) < MIN_N
    h1 = (not thin and A_IS["add_R"].mean() >= BAR_R and A_OOS["add_R"].mean() >= BAR_R and ci1[0] > 0)
    d_is = A_IS["add_R"].mean() - IS["base_R"].mean()
    d_oos = A_OOS["add_R"].mean() - OOS["base_R"].mean()
    dmed = A["add_R"].median() - R["base_R"].median()
    ci2 = boot_diff(A, "add_R", R, "base_R", rng) if len(A) else (np.nan, np.nan)
    h2 = (not thin and d_is >= BAR_R and d_oos >= BAR_R and dmed >= 0 and ci2[0] > 0)
    v1 = "THIN" if thin else ("PASS" if h1 else ("BACKWARDS" if (A_IS['add_R'].mean() <= -BAR_R and A_OOS['add_R'].mean() <= -BAR_R and ci1[1] < 0) else "FAIL"))
    v2 = "THIN" if thin else ("PASS" if h2 else "FAIL")
    print(f"\n  H1 adds pay:            pooled CI95 [{ci1[0]:+.3f}, {ci1[1]:+.3f}]  → {v1}")
    print(f"  H2 add beats new entry: IS {d_is:+.3f}R  OOS {d_oos:+.3f}R  Δmed {dmed:+.3f}  CI95 [{ci2[0]:+.3f}, {ci2[1]:+.3f}]  → {v2}")
    s = R["simple_add_R"].dropna()
    print(f"  reported: simple '+1R' trigger adds n={len(s)} mean {s.mean():+.3f}R med {s.median():+.3f}"
          f" · add fired median {A['add_after'].median():.0f} bars in, +{A['add_ext'].median():.1f}% up, held {A['add_days'].median():.0f} bars")
    return dict(H1=v1, H2=v2, ci1=list(map(float, ci1)), ci2=list(map(float, ci2)),
                d_is=float(d_is), d_oos=float(d_oos), n_is=len(A_IS), n_oos=len(A_OOS))


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    for f in ("placebo", "validate", "run"):
        g.add_argument("--" + f, action="store_true")
    a = ap.parse_args()
    rng = np.random.default_rng(43)
    if a.run:
        if os.path.exists(MARKER):
            sys.exit(f"REFUSED: already run ({MARKER}).")
        if not os.path.exists(VALID):
            sys.exit("REFUSED: run --validate first.")
    d, frames, bench = X.load(placebo=a.placebo, seed=7)
    d = d[d["Catalyst_used"].astype(str).str.upper().isin(FAMS)].copy()
    R = run_all(d, frames, bench)
    if a.validate:
        ref = pd.read_csv(os.path.join(OUT, "_pos_trail_trades.csv"))
        ref["ts"] = pd.to_datetime(ref["ts"])
        R = R.assign(ts=pd.to_datetime(R["ts"]))
        m = R.merge(ref[["Symbol", "ts", "L_ret"]], on=["Symbol", "ts"], how="inner")
        err = (m["base_ret"] - m["L_ret"]).abs()
        ok = len(m) >= 0.95 * len(R) and err.median() <= 0.25
        print(f"base vs positional-trail run L: matched {len(m)}/{len(R)}, median |err| {err.median():.4f}pp, "
              f"max {err.max():.3f}pp → {'VALID' if ok else 'FAIL'}")
        if ok:
            json.dump({"at": datetime.now().isoformat()}, open(VALID, "w"))
        return
    res = report(R, d, "PLACEBO" if a.placebo else "REAL RUN", rng)
    if a.run:
        R.to_csv(os.path.join(OUT, "_add_premise_trades.csv"), index=False)
        json.dump({"at": datetime.now().isoformat(), **res}, open(MARKER, "w"))
        print("\nsaved; marker written.")


if __name__ == "__main__":
    main()
