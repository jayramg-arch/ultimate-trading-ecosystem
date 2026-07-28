"""stopout_forensics.py — are the early stop-outs SHAKEOUTS or real failures?

Jay's question: "Stocks pull back. Are the 40% of trades stopping out in ~7 days
dying because of natural pullbacks? Our strategy should factor pullbacks in."

Testable rather than arguable. For every trade that hit its INITIAL stop, keep
watching to the end of the trade's own forward window and ask what would have
happened had the stop been wider:

  SHAKEOUT      — stopped, then recovered to a profit by window end
  REAL FAILURE  — stopped, and kept going down

Then the actionable part: for each candidate stop distance k (in ATR), how many of
today's stop-outs would have SURVIVED, and what would they have returned? That is the
distribution of "room required", which is what should set the stop — not a guess.

Read-only. No production code touched.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DETAILS = "validation_runs/validation_20260728_191035_details.csv"


def main():
    import data_provider as dp

    d = pd.read_csv(DETAILS)
    d = d[d["Alpha_Matched_pct"].notna()].copy()
    d["ts"] = pd.to_datetime(d["as_of"])
    d["fam"] = np.where(d["Catalyst_used"].str.upper().str.startswith("SWG"), "SWG", "POS")

    rows = []
    for sym, g in d.groupby("Symbol"):
        try:
            f = dp.fetch_ohlcv(sym, period="5y", interval="1d")
        except Exception:
            continue
        if f is None or len(f) < 60:
            continue
        h, l, c = f["High"], f["Low"], f["Close"]
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        atr_s = tr.rolling(14).mean()

        for _, r in g.iterrows():
            try:
                cut = f.loc[:r["ts"]]
                if len(cut) < 30:
                    continue
                pos = len(cut) - 1
                a = float(atr_s.iloc[pos])
                if not np.isfinite(a) or a <= 0:
                    continue
                ep = float(r["Entry_Close"])
                slp = float(r["SL_price"])
                fwd = int(r["forward_days_used"]) if pd.notna(r.get("forward_days_used")) else 30
                win = f.iloc[pos + 1: pos + 1 + fwd]
                if win.empty:
                    continue
                t1 = float(r["T1_price"]) if pd.notna(r.get("T1_price")) else None

                lows = win["Low"].to_numpy(float)
                highs = win["High"].to_numpy(float)
                closes = win["Close"].to_numpy(float)

                # when would a k-ATR stop have been hit? (k grid evaluated later)
                mae_atr = (ep - lows.min()) / a                 # deepest adverse excursion, in ATR
                end_ret = (closes[-1] - ep) / ep * 100          # hold-to-window-end return
                peak_ret = (highs.max() - ep) / ep * 100
                hit_t1_ever = bool(t1 and highs.max() >= t1)

                # disjoint split: dip measured in the first 7 bars, outcome AFTER it
                EARLY_N = 7
                early_mae = later_ret = np.nan
                if len(win) > EARLY_N:
                    early_mae = (ep - lows[:EARLY_N].min()) / a
                    ref = closes[EARLY_N - 1]
                    if ref > 0:
                        later_ret = (closes[-1] - ref) / ref * 100

                rows.append({
                    "fam": r["fam"], "cat": r["Catalyst_used"], "ts": r["ts"],
                    "sl_k": (ep - slp) / a,          # today's stop distance in ATR
                    "mae_atr": mae_atr,
                    "early_mae": early_mae, "later_ret": later_ret,
                    "stopped": bool(str(r.get("Exit_Reason", "")) == "SL hit"),
                    "end_ret": end_ret, "peak_ret": peak_ret,
                    "hit_t1_ever": hit_t1_ever,
                    "rec_ret": r["Return_pct"], "days": r["Days_Held"],
                })
            except Exception:
                pass

    R = pd.DataFrame(rows)
    print(f"trades analysed: {len(R)}\n")

    S = R[R["stopped"]]
    print(f"=== INITIAL-STOP COHORT: {len(S)}/{len(R)} ({len(S)/len(R)*100:.1f}%) ===")
    for fam in ("POS", "SWG"):
        s = S[S["fam"] == fam]
        if not len(s):
            continue
        shake = s[s["end_ret"] > 0]
        print(f"\n  {fam}  n={len(s)}  (median {s['days'].median():.0f} days to stop)")
        print(f"    SHAKEOUT  (recovered to profit by window end): {len(shake):4d}  {len(shake)/len(s)*100:5.1f}%")
        print(f"    REAL FAIL (still negative at window end)     : {len(s)-len(shake):4d}  {(1-len(shake)/len(s))*100:5.1f}%")
        print(f"    would have hit T1 at some point              : {s['hit_t1_ever'].mean()*100:5.1f}%")
        print(f"    hold-to-end return  mean {s['end_ret'].mean():+6.2f}%   median {s['end_ret'].median():+6.2f}%")
        print(f"    peak return reached mean {s['peak_ret'].mean():+6.2f}%")
        print(f"    stop distance today  median {s['sl_k'].median():.2f} xATR")
        print(f"    depth actually needed (MAE) median {s['mae_atr'].median():.2f} xATR, "
              f"75th {s['mae_atr'].quantile(.75):.2f}, 90th {s['mae_atr'].quantile(.90):.2f}")

    # ── NON-CIRCULAR version ────────────────────────────────────────────────────
    # The full-window MAE vs full-window outcome comparison is ENDOGENOUS: a losing
    # trade necessarily dug deep, so "deep drawdown predicts loss" is partly a
    # tautology. Here the drawdown is measured ONLY in the first `early_n` bars and
    # the outcome ONLY from bar `early_n` to the window end. Disjoint, so a real
    # shakeout (dips early, recovers later) is separable from a real failure.
    print("\n=== EARLY DIP vs LATER OUTCOME (disjoint windows — not circular) ===")
    print("  early dip = deepest excursion in the first 7 bars, in ATR")
    print("  later     = return from bar 7 to the end of the trade's own window")
    for fam in ("POS", "SWG"):
        sub = R[(R["fam"] == fam) & R["early_mae"].notna() & R["later_ret"].notna()]
        if not len(sub):
            continue
        print(f"\n  {fam}  n={len(sub)}   (stop today ~{sub['sl_k'].median():.2f} xATR)")
        print(f"    {'early dip':>14} {'n':>5} {'%ofbook':>8} {'later mean':>11} {'later med':>10} {'later win%':>11}")
        bins = [(0, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 4.0), (4.0, 99)]
        for lo_k, hi_k in bins:
            b = sub[(sub["early_mae"] > lo_k) & (sub["early_mae"] <= hi_k)]
            if not len(b):
                continue
            lbl = f"{lo_k:.1f}-{hi_k:.1f}" if hi_k < 99 else f">{lo_k:.1f}"
            print(f"    {lbl:>14} {len(b):5d} {len(b)/len(sub)*100:7.1f}% "
                  f"{b['later_ret'].mean():+10.2f}% {b['later_ret'].median():+9.2f}% "
                  f"{(b['later_ret']>0).mean()*100:10.1f}%")

    R.to_csv("validation_runs/_stopout_forensics.csv", index=False)
    print("\nsaved: validation_runs/_stopout_forensics.csv")


if __name__ == "__main__":
    main()
