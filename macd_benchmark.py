"""macd_benchmark — put a generic MACD crossover through the SAME harness as the screener.

WHY (Jay, 5-Aug-2026): "A very generic MACD crossover strategy without any filters gives
47.56% returns on Nifty and around 30% on a stock like Reliance. Our complex strategy
seems much inferior to a notoriously weak generic strategy."

The headline numbers are not comparable, and that is the point of this file rather than
an argument about it:

  * 47.56% is a TOTAL RETURN on ONE instrument. The screener's +0.80% is MEAN PER-TRADE
    MATCHED ALPHA — excess over BUYING THE INDEX for the same holding period, after
    0.10%/leg costs. Different units, different questions.
  * A long-only trend strategy in a bull decade posts a positive total return almost
    regardless of skill. The question is whether it beat the index it could have bought
    instead. That is what alpha measures and what a total return hides.

So: same anchors, same universe, same pinned point-in-time data, same bar-by-bar exit
simulator, same costs, same matched-horizon benchmark. Whatever comes out is directly
comparable to the screener's number, because it is produced by the same functions.

Deliberately UNFILTERED, exactly as described: MACD(12,26,9) line crossing above signal.
No stage gate, no RS, no volume, no pattern battery. If it wins on these terms, that is
a real finding and the complexity has a case to answer.
"""
from __future__ import annotations

import argparse
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

import data_provider as _dp
import replay as _replay

ATR_STOP_MULT = 2.5      # same family as the screener's SWG stop, so exits are comparable
T1_R, T2_R = 2.0, 4.0


def macd_picks(symbols, as_of: str, max_names: int = 0) -> pd.DataFrame:
    """Names whose MACD line crossed ABOVE its signal on the anchor bar."""
    rows = []
    _dp.set_pinned_date(as_of)
    try:
        for s in symbols:
            try:
                d = _dp.fetch_ohlcv(s, period="2y", interval="1d", use_cache=True, auto_adjust=True)
                if d is None or len(d) < 120:
                    continue
                c = d["Close"].astype(float)
                macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
                sig = macd.ewm(span=9, adjust=False).mean()
                # The cross must happen ON the anchor bar — no look-ahead, no "recently".
                if not (macd.iloc[-1] > sig.iloc[-1] and macd.iloc[-2] <= sig.iloc[-2]):
                    continue
                h, l = d["High"].astype(float), d["Low"].astype(float)
                tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
                atr = float(tr.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1])
                px = float(c.iloc[-1])
                if not np.isfinite(atr) or atr <= 0 or px <= 0:
                    continue
                sl_pct = ATR_STOP_MULT * atr / px * 100.0
                rows.append(dict(Symbol=s, Entry=px, SL_pct=sl_pct,
                                 T1_pct=T1_R * sl_pct, T2_pct=T2_R * sl_pct,
                                 T1_R=T1_R, T2_R=T2_R,
                                 # SWG window (60d) — a MACD cross is a swing signal, and
                                 # this is the same mapping the screener's swing book gets.
                                 Catalyst="SWG-MACD",
                                 Score=float(macd.iloc[-1] - sig.iloc[-1])))
            except Exception:
                continue
    finally:
        _dp.set_pinned_date(None)
    df = pd.DataFrame(rows)
    if max_names and len(df) > max_names:
        df = df.sort_values("Score", ascending=False).head(max_names)
    return df


def run(anchors, universe, top_n: int = 0, catalyst_windows: bool = True) -> pd.DataFrame:
    out = []
    for i, a in enumerate(anchors, 1):
        picks = macd_picks(universe, a, max_names=top_n)
        if picks.empty:
            print(f"[{i:2d}/{len(anchors)}] {a}  no cross", flush=True)
            continue
        perf = _replay.forward_returns_with_exits(picks, a, forward_days=60,
                                                  use_catalyst_windows=catalyst_windows)
        if perf is None or perf.empty:
            continue
        perf["as_of"] = a
        out.append(perf)
        alp = perf.get("Alpha_Matched_pct")
        print(f"[{i:2d}/{len(anchors)}] {a}  n={len(perf):3d}  "
              f"mean α {alp.mean():+.2f}%" if alp is not None else "", flush=True)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def report(df: pd.DataFrame, label="MACD(12,26,9) crossover, unfiltered") -> None:
    if df is None or df.empty:
        print("no trades")
        return
    a = df["Alpha_Matched_pct"].dropna()
    r = df["Return_pct"].dropna()
    print(f"\n=== {label} ===")
    print(f"trades              {len(df)}")
    print(f"mean matched alpha  {a.mean():+.2f}%      median {a.median():+.2f}%")
    print(f"mean raw return     {r.mean():+.2f}%      median {r.median():+.2f}%")
    print(f"win rate (alpha>0)  {100*(a>0).mean():.1f}%")
    if "forward_days_used" in df:
        print(f"forward windows     {dict(df.forward_days_used.value_counts())}")
    if "Exit_Reason" in df:
        print("\nby exit reason:")
        g = df.groupby("Exit_Reason")["Alpha_Matched_pct"].agg(["count", "mean"]).round(2)
        print(g.to_string())
    # A total return quoted without its benchmark is the thing that started this.
    if "Benchmark_Matched_pct" in df:
        b = df["Benchmark_Matched_pct"].dropna()
        print(f"\nthe index over the SAME holds: mean {b.mean():+.2f}%  "
              f"— raw return {r.mean():+.2f}% minus that IS the alpha above")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=24)
    ap.add_argument("--universe", default="nifty500")
    ap.add_argument("--top_n", type=int, default=0, help="0 = every cross (truly unfiltered)")
    ap.add_argument("--out", default="validation_runs/_macd_bench.csv")
    a = ap.parse_args()

    # Reuse validation's OWN anchor and universe builders — if these drift the two runs
    # stop being comparable, which is the entire point of this file.
    import validation as V
    universe = V.default_universe(a.universe)
    anchors = V.monthly_anchors(months_back=a.months)
    print(f"anchors {len(anchors)}  universe {len(universe)}")
    df = run(anchors, universe, top_n=a.top_n)
    if not df.empty:
        df.to_csv(a.out, index=False)
        print(f"\nper-trade -> {a.out}")
    report(df)
