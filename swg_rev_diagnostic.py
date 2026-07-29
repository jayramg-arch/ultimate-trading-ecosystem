"""swg_rev_diagnostic.py — why does SWG-REV lose money?

MY STATED PREMISE WAS WRONG AND THIS SCRIPT EXISTS TO REPLACE IT.
I said "SWG-REV stops out 69% of the time, so it is catching falling knives". But
SWG-PB stops out **78%** out-of-sample and is PROFITABLE (+0.52% alpha), while SWG-REV
stops out **68.9%** and loses (-0.44%). The stop-out RATE is therefore not the
discriminator — a diagnosis built on it would have been treating the wrong symptom.

The real puzzle, from the per-catalyst split:
    SWG-REV OOS  win 29.7%  PF 0.60      <- HIGHER win rate
    SWG-PB  OOS  win 27.7%  PF 0.88      <- LOWER win rate, BETTER profit factor
SWG-REV wins MORE OFTEN and still loses. That can only be a PAYOFF ASYMMETRY: its
winners are too small relative to its losers. This script decomposes exactly that.

Measured per catalyst, IS and OOS:
  • average win vs average loss, and the payoff ratio (the thing PF is made of)
  • expectancy split into its two terms, so the loss is attributable
  • max runup on LOSERS (did they ever go green before dying?)
  • max runup vs realised return on WINNERS (are winners being cut short?)
  • T1 / T2 hit rates
  • stop distance in ATR at entry
  • VOLATILITY EXPANSION: realised ATR over the hold / ATR at entry. A reversal setup
    fires in falling, high-volatility conditions; if volatility keeps expanding after
    entry then an ATR-at-entry stop is systematically too tight FOR THIS CATALYST even
    when the same stop works elsewhere.
Read-only. No production code touched.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DETAILS = "validation_runs/validation_20260728_191035_details.csv"
IS_END = pd.Timestamp("2024-06-01")
CATS = ("SWG-REV", "SWG-PB")


def main():
    import data_provider as dp

    d = pd.read_csv(DETAILS)
    d = d[d["Alpha_Matched_pct"].notna()].copy()
    d["ts"] = pd.to_datetime(d["as_of"])
    d = d[d["Catalyst_used"].isin(CATS)].copy()

    rows = []
    for sym, g in d.groupby("Symbol"):
        try:
            f = dp.fetch_ohlcv(sym, period="10y", interval="1d")
        except Exception:
            continue
        if f is None or len(f) < 60:
            continue
        h, l, c = f["High"], f["Low"], f["Close"]
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        for _, r in g.iterrows():
            try:
                cut = f.loc[:r["ts"]]
                if len(cut) < 30:
                    continue
                pos = len(cut) - 1
                a0 = float(atr.iloc[pos])
                ep = float(r["Entry_Close"])
                if not np.isfinite(a0) or a0 <= 0 or ep <= 0:
                    continue
                held = int(r["Days_Held"]) if pd.notna(r.get("Days_Held")) else 0
                held = max(held, 1)
                win = f.iloc[pos + 1: pos + 1 + held]
                if win.empty:
                    continue
                # realised ATR during the hold vs ATR at entry
                atr_hold = float(atr.iloc[pos + 1: pos + 1 + held].mean())
                rows.append({
                    "cat": r["Catalyst_used"], "ts": r["ts"],
                    "alpha": r["Alpha_Matched_pct"], "ret": r["Return_pct"],
                    "runup": r["Max_Runup_pct"], "dd": r["Max_Drawdown_pct"],
                    "days": r["Days_Held"], "exit": r["Exit_Reason"],
                    "t1": bool(r.get("Hit_T1")), "t2": bool(r.get("Hit_T2")),
                    "sl_k": (ep - float(r["SL_price"])) / a0,
                    "vol_exp": (atr_hold / a0) if np.isfinite(atr_hold) else np.nan,
                })
            except Exception:
                pass

    R = pd.DataFrame(rows)
    print(f"trades: {len(R)}  ({R['cat'].value_counts().to_dict()})")

    for wname, W in (("IN-SAMPLE", R[R["ts"] < IS_END]), ("OUT-OF-SAMPLE", R[R["ts"] >= IS_END])):
        print(f"\n{'='*72}\n{wname}")
        for cat in CATS:
            g = W[W["cat"] == cat]
            if len(g) < 5:
                print(f"\n  {cat}: n={len(g)} — too few to read")
                continue
            w = g[g["ret"] > 0]["ret"]
            l = g[g["ret"] <= 0]["ret"]
            aw, al = (w.mean() if len(w) else 0.0), (abs(l.mean()) if len(l) else 0.0)
            pr = (aw / al) if al > 0 else np.inf
            wr = len(w) / len(g)
            print(f"\n  {cat}   n={len(g)}   alpha {g['alpha'].mean():+.2f}%   win {wr*100:.1f}%")
            print(f"    avg WIN  {aw:+6.2f}%  (n={len(w)})     avg LOSS {-al:+6.2f}%  (n={len(l)})")
            print(f"    payoff ratio (avgWin/avgLoss) .... {pr:5.2f}")
            print(f"    expectancy = {wr:.3f}x{aw:+.2f} - {1-wr:.3f}x{al:.2f} = {wr*aw - (1-wr)*al:+.2f}%")
            lo = g[g["ret"] <= 0]
            print(f"    LOSERS: max runup before dying ... mean {lo['runup'].mean():+.2f}%  "
                  f"median {lo['runup'].median():+.2f}%   ({(lo['runup'] > 2).mean()*100:.0f}% went >2% green first)")
            wi = g[g["ret"] > 0]
            if len(wi):
                print(f"    WINNERS: runup {wi['runup'].mean():+.2f}% vs realised {wi['ret'].mean():+.2f}%  "
                      f"-> gave back {wi['runup'].mean() - wi['ret'].mean():.2f}pp")
            print(f"    T1 hit {g['t1'].mean()*100:5.1f}%   T2 hit {g['t2'].mean()*100:5.1f}%   "
                  f"stop {g['sl_k'].median():.2f} xATR   days {g['days'].mean():.1f}")
            print(f"    VOL EXPANSION (ATR during hold / ATR at entry) ... "
                  f"median {g['vol_exp'].median():.3f}   ({(g['vol_exp'] > 1.0).mean()*100:.0f}% expanded)")

    print(f"\n{'='*72}\nEXIT MIX")
    print(pd.crosstab(R["cat"], R["exit"], normalize="index").mul(100).round(1).to_string())


if __name__ == "__main__":
    main()
