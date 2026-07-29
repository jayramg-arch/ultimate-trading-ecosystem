"""swing_regime_partition.py — is swing's weakness a REGIME mismatch?

The standing diagnosis (never acted on): SWG-PB is a momentum-CONTINUATION setup, so it
should work in confirmed uptrends and fail in corrections. That is a mechanism, not a
parameter — which is why it is worth testing and a gate sweep is not.

HYPOTHESIS (single, stated before running):
  H: swing matched-horizon alpha is materially higher when the MARKET REGIME AT ENTRY
     is BULL, and gating on it would improve the swing book.

REGIME IS MEASURED EX-ANTE. Benchmark (^CRSLDX) state at the anchor date only:
  BULL    close > 200DMA AND 50DMA > 200DMA
  NEUTRAL close > 200DMA but 50DMA <= 200DMA (or the mirror)
  BEAR    close < 200DMA AND 50DMA < 200DMA
No outcome information touches the label — this is the trap from 26-Jul, where "DOWN
tape" was derived from the trade's own benchmark window and became endogenous once the
window length was the trade's actual hold.

DECISION RULE (fixed before running):
  A. IS gap    — BULL minus non-BULL alpha >= 1.0pp for SWG
  B. OOS holds — the same sign out of sample
  C. NOT UNIVERSAL — POS must show a SMALLER gap than SWG. If both families gain
     equally, this is market timing (a fact about the tape), not a swing-specific fix,
     and gating swing on it would be arbitrary.
  D. Enough trades on BOTH sides to mean anything (>= 30 each).
Fail any -> the regime hypothesis is not supported and swing needs a different diagnosis.

A NOTE ON WHAT MAY ALREADY BE TRUE: bull_screener has carried a hard `mkt_bull` gate on
SWG-PB since 2-Jul-2026. If that gate is binding, most SWG picks will ALREADY be in BULL
regime and the partition will show little variation — which is itself the answer (the
fix is already applied and swing is weak anyway).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DETAILS = "validation_runs/validation_20260728_191035_details.csv"
BENCH = "^CRSLDX"
IS_END = pd.Timestamp("2024-06-01")


def _regime_series(bdf):
    c = bdf["Close"]
    sma50, sma200 = c.rolling(50).mean(), c.rolling(200).mean()
    out = pd.Series("UNKNOWN", index=c.index, dtype=object)
    above = c > sma200
    golden = sma50 > sma200
    out[above & golden] = "BULL"
    out[(~above) & (~golden)] = "BEAR"
    out[(above & ~golden) | (~above & golden)] = "NEUTRAL"
    out[sma200.isna()] = "UNKNOWN"
    return out


def _blk(d, label):
    if not len(d):
        print(f"  {label:22} n=0")
        return None
    print(f"  {label:22} n={len(d):4d}  alpha {d['Alpha_Matched_pct'].mean():+6.2f}%  "
          f"med {d['Alpha_Matched_pct'].median():+6.2f}%  win {(d['Alpha_Matched_pct']>0).mean()*100:5.1f}%  "
          f"raw ret {d['Return_pct'].mean():+6.2f}%")
    return d["Alpha_Matched_pct"].mean()


def main():
    import data_provider as dp

    d = pd.read_csv(DETAILS)
    d = d[d["Alpha_Matched_pct"].notna()].copy()
    d["ts"] = pd.to_datetime(d["as_of"])
    d["fam"] = np.where(d["Catalyst_used"].str.upper().str.startswith("SWG"), "SWG", "POS")

    bdf = dp.fetch_ohlcv(BENCH, period="10y", interval="1d")
    reg = _regime_series(bdf)

    def regime_at(ts):
        i = reg.index.searchsorted(pd.Timestamp(ts))
        i = min(max(i - 1, 0), len(reg) - 1)     # last CLOSED bar at/before the anchor
        return reg.iloc[i]

    d["regime"] = d["ts"].map(regime_at)
    print(f"trades={len(d)}   regime mix at entry: {d['regime'].value_counts().to_dict()}\n")

    print("=== Is the existing mkt_bull gate already binding? ===")
    print(pd.crosstab(d["Catalyst_used"], d["regime"]).to_string(), "\n")

    gaps = {}
    for fam in ("SWG", "POS"):
        f = d[d["fam"] == fam]
        print(f"=== {fam} ===")
        for wname, w in (("ALL", f), ("IN-SAMPLE", f[f["ts"] < IS_END]), ("OUT-SAMPLE", f[f["ts"] >= IS_END])):
            print(f"  -- {wname} --")
            b = _blk(w[w["regime"] == "BULL"], "BULL at entry")
            nb = _blk(w[w["regime"] != "BULL"], "NOT-BULL at entry")
            if b is not None and nb is not None:
                gaps[(fam, wname)] = (b - nb, (w["regime"] == "BULL").sum(), (w["regime"] != "BULL").sum())
                print(f"  {'GAP (bull - notbull)':22} {b - nb:+6.2f}pp")
        print()

    print("=== DECISION (prereg) ===")
    gs_is = gaps.get(("SWG", "IN-SAMPLE"))
    gs_oos = gaps.get(("SWG", "OUT-SAMPLE"))
    gp_is = gaps.get(("POS", "IN-SAMPLE"))
    if not (gs_is and gs_oos and gp_is):
        print("  insufficient data in one or more cells -> NOT SUPPORTED")
        return
    A = gs_is[0] >= 1.0
    B = np.sign(gs_oos[0]) == np.sign(gs_is[0]) and gs_oos[0] > 0
    C = gs_is[0] > gp_is[0]
    D = min(gs_is[1], gs_is[2]) >= 30
    print(f"  A. SWG IS gap >= 1.0pp .......... {gs_is[0]:+.2f}pp   {'PASS' if A else 'FAIL'}")
    print(f"  B. OOS same sign & positive ..... {gs_oos[0]:+.2f}pp   {'PASS' if B else 'FAIL'}")
    print(f"  C. bigger than POS's gap ........ SWG {gs_is[0]:+.2f} vs POS {gp_is[0]:+.2f}   {'PASS' if C else 'FAIL'}")
    print(f"  D. >=30 trades each side ........ {gs_is[1]}/{gs_is[2]}   {'PASS' if D else 'FAIL'}")
    print(f"\n  VERDICT: {'REGIME GATE SUPPORTED' if (A and B and C and D) else 'NOT SUPPORTED — swing needs a different diagnosis'}")


if __name__ == "__main__":
    main()
