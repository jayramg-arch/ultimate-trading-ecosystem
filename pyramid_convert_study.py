#!/usr/bin/env python3
"""Two slices vs convert for a v2 pyramid onto a v1 holding (docs/PREREG_pyramid_slices_vs_convert.md).

    python pyramid_convert_study.py --plumbing   event counts only (no outcome numbers)
    python pyramid_convert_study.py --run        THE run - once

v1 = the positional trades of bull validation run 20260819_112959, re-simulated on the
survivorship panel with the house positional exits; v2's cut = v2_house's eligibility + ensemble
rank, read on the Wednesday-rule decision days.
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import v2_house as vh            # noqa: E402

RUN = "20260819_112959"
OUT = os.path.join(HERE, "reports", "pyramid_convert")
V1_CAPITAL, V1_RISK, V1_CAP = 3_000_000.0, 0.005, 100_000.0
V2_EQUITY, V2_RISK, V2_CAP = 1_000_000.0, 0.001, 1_000_000.0 * 100_000 / 3_000_000
T1_R, T2_R, LEG = 3.0, 5.0, 0.25
BOOT, MIN_GAIN = 2000, 1.0


def v2_cut(p, f, g, ctx):
    """{decision day: (set in the buy cut, set eligible)} on the Wednesday rule."""
    C = p["Close"]
    days = C.index[(C.index >= vh.v2.START) & (C.index <= vh.v2.END)]
    dec = sorted(vh.decision_days(days, True))
    stocks = ctx["stocks"]
    out = {}
    for d in dec:
        cl = C.loc[d]
        el = (cl > g["sma100"].loc[d]) & ~g["gap90"].loc[d] & g["liq"].loc[d] & f["has"].loc[d]
        el = el.reindex(stocks).fillna(False).astype(bool)
        sc = vh._ens(g, d, list(el[el].index)) if el.any() else pd.Series(dtype=float)
        n = len(sc)
        cut = max(1, math.ceil(vh.H["top_pct"] * n)) if n else 0
        out[d] = (set(sc.index[:cut]), set(el[el].index))
    return dec, out


def sim_v1(df, e_idx, entry, stop0, atr22, stop_at=None):
    """v1 positional exits from bar e_idx+1. Returns a list of (bar, fraction of ORIGINAL shares,
    price) fills and the remaining fraction / stop / partial state at bar `stop_at` (the fork) if
    given: {"left", "stop", "t1", "t2"}."""
    O, H, L, C = df["Open"].values, df["High"].values, df["Low"].values, df["Close"].values
    R = entry - stop0
    stop, left, t1, t2 = stop0, 1.0, False, False
    fills, fork = [], None
    for i in range(e_idx + 1, len(C)):
        if not (C[i] == C[i]):
            continue
        if stop_at is not None and i == stop_at:          # state at the fork's close, after this bar
            pass
        if L[i] == L[i] and L[i] <= stop:
            px = min(O[i], stop) if O[i] == O[i] else stop
            fills.append((i, left, px))
            left = 0.0
        else:
            if not t1 and H[i] >= entry + T1_R * R:
                fills.append((i, LEG, entry + T1_R * R)); left -= LEG; t1 = True
            if not t2 and H[i] >= entry + T2_R * R:
                fills.append((i, LEG, entry + T2_R * R)); left -= LEG; t2 = True
            lv = vh.trail_level(pd.Series(C[e_idx:i + 1]), atr22[i])
            if lv == lv and lv > stop:
                stop = lv
        if stop_at is not None and i == stop_at:
            fork = {"left": left, "stop": stop, "t1": t1, "t2": t2, "fills": list(fills)}
        if left <= 1e-12:
            break
    return fills, fork, left


def run(plumbing: bool) -> int:
    p, f, g, ctx = vh.load_backtest()
    C = p["Close"]
    dec, cut = v2_cut(p, f, g, ctx)
    dec_idx = {d: k for k, d in enumerate(dec)}
    det = pd.read_csv(os.path.join(HERE, "validation_runs", "validation_%s_details.csv" % RUN))
    det = det[det["Catalyst"].astype(str).str.startswith("POS")].copy()
    ev, miss = [], {"not in panel": 0, "no overlap": 0, "bad stop": 0}
    for _, t in det.iterrows():
        s = str(t["Symbol"]).replace(".NS", "")
        if s not in C.columns:
            miss["not in panel"] += 1
            continue
        df = pd.DataFrame({k: p[k][s] for k in ("Open", "High", "Low", "Close")})
        idx = df.index
        e = pd.Timestamp(t["as_of"])
        e_pos = idx.searchsorted(e)
        if e_pos >= len(idx):
            miss["not in panel"] += 1
            continue
        entry, stop0 = float(t["Entry_Close"]), float(t["SL_price"])
        if not (entry > stop0 > 0):
            miss["bad stop"] += 1
            continue
        atr22 = ctx["atr22"][s].values
        fills, _f, left = sim_v1(df, e_pos, entry, stop0, atr22)
        last_bar = fills[-1][0] if left <= 1e-12 else len(idx) - 1
        # the first decision day after entry, v1 still holding, stock inside v2's cut
        od = next((d for d in dec if idx[e_pos] < d <= idx[last_bar] and s in cut[d][0]
                   and idx.get_loc(d) < last_bar), None)
        if od is None:
            miss["no overlap"] += 1
            continue
        o_pos = idx.get_loc(od)
        _x, fork, _l = sim_v1(df, e_pos, entry, stop0, atr22, stop_at=o_pos)
        if fork is None or fork["left"] <= 1e-12:
            miss["no overlap"] += 1
            continue
        ev.append({"symbol": s, "entry_date": idx[e_pos], "overlap": od, "o_pos": o_pos, "e_pos": e_pos,
                   "entry": entry, "stop0": stop0, "left": fork["left"], "fork": fork, "df": df, "atr22": atr22})
    print("POS v1 trades %d · overlap events %d · skipped %s" % (len(det), len(ev), miss))
    if plumbing:
        if ev:
            print("overlap dates %s .. %s" % (min(x["overlap"] for x in ev).date(), max(x["overlap"] for x in ev).date()))
        return 0
    rows = []
    for x in ev:
        df, s, o = x["df"], x["symbol"], x["o_pos"]
        Cc, Oo = df["Close"].values, df["Open"].values
        v0 = Cc[o]                                   # value per original share at the fork close
        # A: v1 rules carry on from the fork state
        fills, _f, left = sim_v1(df, x["e_pos"], x["entry"], x["stop0"], x["atr22"])
        after = [(i, fr, px) for i, fr, px in fills if i > o]
        endA = (after[-1][0] if left <= 1e-12 else len(Cc) - 1)
        valA = sum(fr * px for _i, fr, px in after) + (left * Cc[-1] if left > 1e-12 else 0.0)
        rA = valA / (x["left"] * v0) - 1
        # B: v2's exits on the same shares - out at the open after the first decision day outside the cut
        k0 = dec.index(x["overlap"])
        exitB = None
        for d in dec[k0 + 1:]:
            if s not in cut[d][0]:
                j = df.index.get_loc(d) + 1 if d in df.index else None
                if j is not None and j < len(Cc):
                    exitB = j
                break
        pxB = (Oo[exitB] if exitB is not None and Oo[exitB] == Oo[exitB] else Cc[-1]) if exitB is not None else Cc[-1]
        rB = pxB / v0 - 1
        # C: as B, cut to v2's target size at the next reset (every 2nd decision day), the excess
        # sold at that open and held as cash
        sh1 = min(V1_CAPITAL * V1_RISK / (x["entry"] - x["stop0"]), V1_CAP / x["entry"]) * x["left"]
        resetd = next((d for d in dec[k0 + 1:] if dec_idx[d] % 2 == 0), None)
        rC = rB
        if resetd is not None and resetd in df.index:
            j = df.index.get_loc(resetd) + 1
            if j < len(Cc) and (exitB is None or j < exitB):
                a20 = g["atr20"].at[resetd, s]
                tgt = min(V2_EQUITY * V2_RISK / a20, V2_CAP / Cc[j - 1]) if a20 == a20 and a20 > 0 else sh1
                keep = min(1.0, tgt / sh1) if sh1 > 0 else 1.0
                rC = keep * (pxB / v0 - 1) + (1 - keep) * (Oo[j] / v0 - 1 if Oo[j] == Oo[j] else 0.0)
        rows.append({"symbol": s, "overlap": x["overlap"].date(), "rA": rA * 100, "rB": rB * 100, "rC": rC * 100,
                     "daysA": endA - o, "daysB": ((exitB if exitB is not None else len(Cc) - 1) - o)})
    T = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    T.to_csv(os.path.join(OUT, "events.csv"), index=False)
    med = pd.Timestamp(T["overlap"].astype("datetime64[ns]").median())
    rng = np.random.default_rng(11)
    print("\nEvents %d (symbols %d) · overlap %s .. %s · halves split at %s" % (
        len(T), T.symbol.nunique(), T.overlap.min(), T.overlap.max(), med.date()))
    print("v1 shares from the overlap on, %% of their value at the overlap close:")
    for k, nm in (("rA", "A two slices (v1 rules)"), ("rB", "B convert, size kept"), ("rC", "C convert + v2 resize")):
        print("  %-26s mean %+6.2f  median %+6.2f  days held (mean) %s" % (
            nm, T[k].mean(), T[k].median(), "%.0f" % T["daysA" if k == "rA" else "daysB"].mean()))
    verdict = "TWO SLICES"
    for k, nm in (("rB", "B"), ("rC", "C")):
        dlt = T[k] - T["rA"]
        by = {s: g_.values for s, g_ in (T.assign(dl=dlt)).groupby("symbol")["dl"]}
        keys = list(by)
        bs = [np.concatenate([by[q] for q in rng.choice(keys, len(keys))]).mean() for _ in range(BOOT)]
        lo, hi = np.percentile(bs, [2.5, 97.5])
        h1 = dlt[T["overlap"].astype("datetime64[ns]") < med].mean()
        h2 = dlt[T["overlap"].astype("datetime64[ns]") >= med].mean()
        ok = dlt.mean() >= MIN_GAIN and lo > 0 and (h1 > 0) == (h2 > 0) and h1 > 0
        print("  %s - A: mean %+6.2f  CI [%+.2f, %+.2f]  halves %+.2f / %+.2f  better in %.0f%% of events  worst %+.1f"
              % (nm, dlt.mean(), lo, hi, h1, h2, (dlt > 0).mean() * 100, dlt.min()))
        if ok:
            verdict = "CONVERT (%s)" % nm
    print("\nVERDICT  %s" % verdict)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plumbing", action="store_true")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if not (a.plumbing or a.run):
        ap.print_help()
        return 0
    return run(a.plumbing)


if __name__ == "__main__":
    sys.exit(main())
