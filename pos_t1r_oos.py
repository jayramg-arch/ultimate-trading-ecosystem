#!/usr/bin/env python3
"""IS/OOS split on the POS T1_R sweep.

The sweep picked 1.5R as an interior maximum (+0.049R over the shipped 5R) using ALL
19 anchors — chosen and scored on the same data, which is selection, not evidence.
This re-runs each cell per trade, splits 60/40 CHRONOLOGICALLY on the anchor (never
mid-anchor), and asks whether the in-sample margin survives.

GATE: OOS must retain >= 50% of the IS margin over control, and OOS must not be worse
than control. A parameter that only wins in-sample is a parameter fitted to noise —
this is the same bar every other study in this repo had to clear, applied here because
I skipped it the first time.
"""
import os, sys
import pandas as pd, numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay as _rp
import data_provider as _dp

BASE = "validation_runs/validation_20260809_194851_details.csv"
T1_RS = (1.0, 1.5, 2.0, 2.5, 3.0, 5.0)
CONTROL = 5.0
QTY1 = 50


def main() -> int:
    picks = pd.read_csv(BASE)
    per_trade = []
    for t1_r in T1_RS:
        t2_r = t1_r * 2.0
        for _, p in picks.iterrows():
            try:
                df_d = _dp.fetch_ohlcv(str(p["Symbol"]), period="3y", interval="1d",
                                       use_cache=True, auto_adjust=True)
                if df_d is None or df_d.empty:
                    continue
                pos = df_d.index.searchsorted(pd.Timestamp(str(p["as_of"])), side="right") - 1
                if pos < 0:
                    continue
                e, s = float(p["Entry_Close"]), float(p["SL_price"])
                risk = e - s
                if risk <= 0:
                    continue
                r = _rp._simulate_one_trade(df_d, pos, e, s, e + risk * t1_r, e + risk * t2_r,
                                            t1_qty_pct=QTY1, t2_qty_pct=100 - QTY1,
                                            max_bars=int(p["forward_days_used"]))
                if not r or r.get("realized_pct") is None:
                    continue
                per_trade.append({"T1_R": t1_r, "as_of": str(p["as_of"]),
                                  "R": r["realized_pct"] / ((e - s) / e * 100.0)})
            except Exception:
                continue
        print(f"  simulated T1={t1_r}R")

    d = pd.DataFrame(per_trade)
    anchors = sorted(d.as_of.unique())
    k = int(len(anchors) * 0.6)
    cut = anchors[k]
    d["win"] = np.where(d.as_of < cut, "IS", "OOS")
    print(f"\nsplit at {cut} — {k} IS anchors / {len(anchors)-k} OOS anchors")

    piv = d.groupby(["T1_R", "win"]).R.agg(["count", "mean"]).round(3).unstack()
    print()
    print(piv.to_string())

    ctrl = d[d.T1_R == CONTROL].groupby("win").R.mean()
    print(f"\ncontrol {CONTROL}R  IS {ctrl.get('IS', float('nan')):+.3f}R   OOS {ctrl.get('OOS', float('nan')):+.3f}R")
    print(f"{'T1_R':>6} {'IS margin':>10} {'OOS margin':>11} {'retained':>9}  verdict")
    for t1 in T1_RS:
        if t1 == CONTROL:
            continue
        m = d[d.T1_R == t1].groupby("win").R.mean()
        is_m = m.get("IS", np.nan) - ctrl.get("IS", np.nan)
        oo_m = m.get("OOS", np.nan) - ctrl.get("OOS", np.nan)
        ret = (oo_m / is_m * 100) if is_m and is_m == is_m and abs(is_m) > 1e-9 else np.nan
        ok = (is_m > 0) and (oo_m > 0) and (ret >= 50)
        print(f"{t1:>6} {is_m:>+10.3f} {oo_m:>+11.3f} {ret:>8.0f}%  {'PASS' if ok else 'fail'}")
    d.to_csv("validation_runs/_pos_t1r_oos_trades.csv", index=False)
    print("\nsaved: validation_runs/_pos_t1r_oos_trades.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
