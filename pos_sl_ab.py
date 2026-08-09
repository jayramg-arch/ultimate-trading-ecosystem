#!/usr/bin/env python3
"""Structure-anchored initial stop vs the 4xATR default — POS book, scored in R.

WHY: fresh POS picks carry SL_pct of 10-12.7% (the 4xATR positional stop). With
targets at 2R/4R that puts the first partial ~24% above entry. If a structure-anchored
stop comes in tighter, every R target tightens with it — so the stop, not the target,
is what sets the whole scale of the trade.

CONTROL  = the shipped stop (SL_price from the POS-only run, 4xATR)
VARIANT  = replay._structural_sl — nearest structure below entry (zone distal via
           _location_at, else the recent swing low), capped at 3xATR, optional ATR floor

TARGETS MOVE WITH THE STOP. Both arms recompute T1/T2 at the shipped 2R/4R off their
OWN risk, because that is how bull_screener builds them. Holding targets fixed while
the stop moves would compare two different trades and flatter whichever arm got the
wider stop — the same error class as scoring stops in % instead of R.

Quantities are the shipped POS 25/25, so 50% rides the trail in both arms.

Reports IS/OOS on a 60/40 chronological split of the ANCHOR. A stop that only wins
in-sample is fitted to noise; the gate is >= 50% of the IS margin retained.
"""
import os, sys
import pandas as pd, numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay as _rp
import data_provider as _dp

BASE = "validation_runs/validation_20260809_194851_details.csv"   # POS-only
T1_R, T2_R = 2.0, 4.0          # shipped
Q1 = Q2 = 25                   # shipped POS partial sizes
FLOORS = (0.0, 1.0, 1.5)       # ATR floor on the structural stop; 0 = pure structure


def _run(df_d, pos, entry, sl, fwd):
    risk = entry - sl
    if risk <= 0:
        return None
    r = _rp._simulate_one_trade(df_d, pos, entry, sl,
                                entry + risk * T1_R, entry + risk * T2_R,
                                t1_qty_pct=Q1, t2_qty_pct=Q2, max_bars=fwd)
    if not r or r.get("realized_pct") is None:
        return None
    return {"R": r["realized_pct"] / (risk / entry * 100.0),
            "sl_pct": risk / entry * 100.0,
            "hit_t1": bool(r.get("hit_t1")),
            "sl_hit": r.get("exit_reason") == "SL hit"}


def main() -> int:
    picks = pd.read_csv(BASE)
    rows = []
    for _, p in picks.iterrows():
        try:
            sym, as_of = str(p["Symbol"]), str(p["as_of"])
            df_d = _dp.fetch_ohlcv(sym, period="3y", interval="1d",
                                   use_cache=True, auto_adjust=True)
            if df_d is None or df_d.empty:
                continue
            pos = df_d.index.searchsorted(pd.Timestamp(as_of), side="right") - 1
            if pos < 1:
                continue
            entry = float(p["Entry_Close"])
            fwd = int(p["forward_days_used"])
            base = _run(df_d, pos, entry, float(p["SL_price"]), fwd)
            if base:
                rows.append({"arm": "control 4xATR", "as_of": as_of, **base})
            # point-in-time location: bars that existed AT ENTRY only
            loc = {}
            try:
                loc = _rp._location_at(df_d.iloc[:pos + 1], entry) or {}
            except Exception:
                loc = {}
            for fl in FLOORS:
                try:
                    ssl = _rp._structural_sl(df_d, pos, entry, loc,
                                             atr_cap_mult=3.0, atr_floor_mult=fl)
                except Exception:
                    continue
                if not ssl or ssl <= 0 or ssl >= entry:
                    continue
                v = _run(df_d, pos, entry, float(ssl), fwd)
                if v:
                    rows.append({"arm": f"structural floor {fl}", "as_of": as_of, **v})
        except Exception:
            continue

    d = pd.DataFrame(rows)
    if d.empty:
        print("no rows"); return 2
    anchors = sorted(d.as_of.unique())
    cut = anchors[int(len(anchors) * 0.6)]
    d["win"] = np.where(d.as_of < cut, "IS", "OOS")

    g = d.groupby("arm").agg(n=("R", "size"), meanR=("R", "mean"), medR=("R", "median"),
                             slpct=("sl_pct", "median"), t1=("hit_t1", "mean"),
                             slhit=("sl_hit", "mean")).round(3)
    g["t1%"] = (g.pop("t1") * 100).round(1); g["slhit%"] = (g.pop("slhit") * 100).round(1)
    print(g.to_string())

    print(f"\nIS/OOS split at {cut}")
    piv = d.groupby(["arm", "win"]).R.mean().round(3).unstack()
    print(piv.to_string())
    ctl = d[d.arm == "control 4xATR"].groupby("win").R.mean()
    print(f"\n{'arm':<22}{'IS margin':>10}{'OOS margin':>12}{'retained':>10}  verdict")
    for arm in sorted(d.arm.unique()):
        if arm.startswith("control"):
            continue
        m = d[d.arm == arm].groupby("win").R.mean()
        i_m = m.get("IS", np.nan) - ctl.get("IS", np.nan)
        o_m = m.get("OOS", np.nan) - ctl.get("OOS", np.nan)
        ret = (o_m / i_m * 100) if i_m and abs(i_m) > 1e-9 else np.nan
        ok = (i_m > 0) and (o_m > 0) and (ret >= 50)
        print(f"{arm:<22}{i_m:>+10.3f}{o_m:>+12.3f}{ret:>9.0f}%  {'PASS' if ok else 'fail'}")
    d.to_csv("validation_runs/_pos_sl_ab.csv", index=False)
    print("\nsaved: validation_runs/_pos_sl_ab.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
