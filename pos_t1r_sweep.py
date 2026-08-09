#!/usr/bin/env python3
"""POS T1_R x partial-size sweep — does the breakeven mechanic pay for the tail it costs?

THE QUESTION (Jay, 9-Aug-2026): "Swing had 2/3R. With that I was able to hit T1, move
SL to Entry, and trail from that point onwards." POS is set to 5R/10R and T1 is reached
in 2% of trades (5 of 203 over 24 months), so the partial, the move to breakeven and the
trail-from-there NEVER engage — every POS trade carries full initial risk for its whole
life, and 24 of 203 died on that untouched initial stop.

THE TENSION, stated up front so the result is read honestly: POS-only returned +1.05%
mean matched alpha on a MEDIAN of -2.96%. That is a big-winner-carried distribution, and
booking a third at 2-3R then capping the rest at breakeven clips exactly the right tail
that pays for the other 64%. Mechanically satisfying is not the same as expectancy-
positive. This measures which one wins.

METHOD
  control = the shipped 5R/10R config, POS-only, same 19 anchors
  variants = T1_R in {2, 3, 5} x t1_qty_pct in {33, 50}
  Everything else identical — same picks, same entries, same trail, same costs. Only the
  target distance and partial size move, so any difference is attributable.

SCORED IN R, not per-trade %. A % metric rewards wide stops for exposure they never
bought (r_multiples_not_percent). R = realized_pct / initial_risk_pct.

Reads the POS-only details CSV as the pick set so no re-screening is needed: the picks,
entries and stops are fixed inputs; only the exit simulation is re-run per cell.
"""
import os, sys, itertools
import pandas as pd, numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay as _rp

BASE = "validation_runs/validation_20260809_194851_details.csv"   # POS-only control run
T1_RS = (1.0, 1.5, 2.0, 2.5, 3.0, 5.0)
QTYS = (25,)


def _sim(df_d, entry_pos, entry_px, sl_px, t1_r, t2_r, q1, q2, fwd):
    """One trade under a given target config. Returns realized % and flags."""
    risk = entry_px - sl_px
    if risk <= 0:
        return None
    t1_px = entry_px + risk * t1_r
    t2_px = entry_px + risk * t2_r
    return _rp._simulate_one_trade(df_d, entry_pos, entry_px, sl_px, t1_px, t2_px,
                                   t1_qty_pct=q1, t2_qty_pct=q2, max_bars=fwd)


def main() -> int:
    if not os.path.exists(BASE):
        print(f"control run not found: {BASE}"); return 2
    picks = pd.read_csv(BASE)
    need = {"Symbol", "Entry_Close", "SL_price", "as_of", "forward_days_used"}
    missing = need - set(picks.columns)
    if missing:
        print(f"missing columns: {missing}"); return 2

    rows = []
    for t1_r, q1 in itertools.product(T1_RS, QTYS):
        t2_r = t1_r * 2.0                      # keep the 1:2 shape of 5R/10R
        recs = []
        for _, p in picks.iterrows():
            try:
                import data_provider as _dp
                df_d = _dp.fetch_ohlcv(str(p["Symbol"]), period="3y", interval="1d",
                                       use_cache=True, auto_adjust=True)
                if df_d is None or df_d.empty:
                    continue
                pos = df_d.index.searchsorted(pd.Timestamp(str(p["as_of"])), side="right") - 1
                if pos < 0:
                    continue
                e, s = float(p["Entry_Close"]), float(p["SL_price"])
                r = _sim(df_d, pos, e, s, t1_r, t2_r, q1, 100 - q1, int(p["forward_days_used"]))
                if not r or r.get("realized_pct") is None:
                    continue
                risk_pct = (e - s) / e * 100.0
                recs.append({"R": r["realized_pct"] / risk_pct if risk_pct > 0 else np.nan,
                             "hit_t1": bool(r.get("hit_t1")),
                             "reason": r.get("exit_reason")})
            except Exception:
                continue
        if not recs:
            continue
        d = pd.DataFrame(recs)
        rows.append({"T1_R": t1_r, "qty1%": q1, "n": len(d),
                     "meanR": round(d.R.mean(), 3), "medR": round(d.R.median(), 3),
                     "win%": round((d.R > 0).mean() * 100, 1),
                     "T1hit%": round(d.hit_t1.mean() * 100, 1),
                     "SLhit%": round((d.reason == "SL hit").mean() * 100, 1)})
        print(f"  done T1={t1_r}R qty={q1}%  n={len(d)}  meanR={rows[-1]['meanR']}")

    out = pd.DataFrame(rows).sort_values("meanR", ascending=False)
    print()
    print(out.to_string(index=False))
    ctrl = out[(out.T1_R == 5.0) & (out["qty1%"] == 33)]
    if len(ctrl):
        c = ctrl.iloc[0]
        print(f"{chr(10)}control (5R/33%): meanR {c.meanR}  medR {c.medR}  win {c['win%']}%")
        print("A variant only wins if it beats control on meanR AND does not worsen medR")
        print("by more than 0.25R — a mechanic that feels better but shortens the tail is")
        print("paying for comfort with expectancy.")
    out.to_csv("validation_runs/_pos_t1r_sweep.csv", index=False)
    print("saved: validation_runs/_pos_t1r_sweep.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
