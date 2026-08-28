"""Reconciling the eye with the median: are ETF wicks RARE-AND-HUGE rather than typical?

The daily study said ETF candles carry LESS wick than stock candles, and JUNIORBEES
prints a median upper wick of 0.6% of range — a candle with essentially no upper
shadow. That flatly contradicts what Jay sees on the chart, and when a measurement
contradicts the person looking at the thing, the measurement is usually answering a
different question.

Two candidates, both testable:

  1. THE TAIL. A median washes out outliers. The eye does not — it fixes on the three
     horrifying bars in a hundred, not the ninety-seven ordinary ones. So measure p90,
     p99 and the max, and count how often a bar's wick exceeds a multiple of its own
     recent range.

  2. THE TIMEFRAME. The daily study is the wrong chart: Jay trades and reads S4 on
     75m and 125m, which is where a thin book actually shows — a handful of trades in
     a 75-minute bucket can print a spike that a full session absorbs.

Whichever of these carries the effect is the one any ETF rule has to address, and if
it is the tail then a median-based tuning would have missed it entirely.
"""
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import data_provider as dp
import etf_universe as eu

try:
    import dhan_ohlcv as dh
except Exception:
    dh = None


def clean(df):
    if df is None or len(df) < 60:
        return None
    df = df.rename(columns=str.title)
    if not {"Open", "High", "Low", "Close"}.issubset(df.columns):
        return None
    if "Volume" in df.columns and float(df["Volume"].fillna(0).sum()) > 0:
        df = df[df["Volume"] > 0]
    df = df[df["High"] > df["Low"]]
    return df if len(df) >= 60 else None


def daily(sym):
    try:
        return clean(dp.fetch_ohlcv(sym, period="2y", interval="1d"))
    except Exception:
        return None


def intraday(sym, minutes=75):
    """75m/125m bars, resampled from Dhan 25m the same way the GM does it."""
    if dh is None:
        return None
    try:
        raw = dh.fetch_intraday(sym, interval=25)
        if raw is None or raw.empty:
            return None
        import pa_patterns as pap
        return clean(pap.resample_intraday(raw, minutes))
    except Exception:
        return None


def tail(df):
    o, h, l, c = (df[x].astype(float) for x in ("Open", "High", "Low", "Close"))
    rng = (h - l).replace(0, np.nan)
    upper = (h - np.maximum(c, o)) / rng
    lower = (np.minimum(c, o) - l) / rng
    wick = upper + lower
    # A wick measured against the bar's OWN range is bounded at 1, so it cannot show
    # "this bar is monstrous". Against the RECENT TYPICAL range it can.
    med_rng = (h - l).rolling(20).median()
    spike = ((h - l) / med_rng)
    return {
        "wick p50": float(wick.median() * 100),
        "wick p90": float(wick.quantile(0.90) * 100),
        "upper p90": float(upper.quantile(0.90) * 100),
        "upper p99": float(upper.quantile(0.99) * 100),
        "range vs 20d p99": float(spike.quantile(0.99)),
        "bars >3x range%": float((spike > 3).mean() * 100),
        "n": len(df),
    }


def med(rows):
    return pd.DataFrame(rows).median().round(2) if rows else None


if __name__ == "__main__":
    etfs = list(eu.ETF_UNIVERSE.keys())
    stocks = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ITC", "LT", "SBIN", "AXISBANK",
              "MARUTI", "TITAN", "SUNPHARMA", "NESTLEIND", "COALINDIA", "TECHM",
              "CIPLA", "GLAXO", "RADICO", "SONACOMS", "APOLLOHOSP", "EICHERMOT"]

    print("── DAILY: does the TAIL differ even though the median does not? ──")
    e = med([tail(d) for s in etfs if (d := daily(s)) is not None])
    st = med([tail(d) for s in stocks if (d := daily(s)) is not None])
    print(f"{'metric':20}{'ETF':>10}{'STOCK':>10}{'ratio':>9}")
    for k in e.index:
        r = e[k] / st[k] if st[k] else float("nan")
        print(f"{k:20}{e[k]:>10}{st[k]:>10}{r:>9.2f}")

    print("\n── 75-MINUTE: the chart the trades are actually read on ─────────")
    ei = [t for s in etfs[:22] if (d := intraday(s, 75)) is not None and (t := tail(d))]
    si = [t for s in stocks[:12] if (d := intraday(s, 75)) is not None and (t := tail(d))]
    if ei and si:
        e2, s2 = med(ei), med(si)
        print(f"resolved {len(ei)} ETFs / {len(si)} stocks")
        print(f"{'metric':20}{'ETF':>10}{'STOCK':>10}{'ratio':>9}")
        for k in e2.index:
            r = e2[k] / s2[k] if s2[k] else float("nan")
            print(f"{k:20}{e2[k]:>10}{s2[k]:>10}{r:>9.2f}")
    else:
        print(f"intraday unavailable (ETF {len(ei)} / stock {len(si)} resolved)")


def pairs_tail():
    """The decisive test for the trainer's advice: does the INDEX spike too?

    The median said ETFs are calm and the tail says they are occasionally violent, so
    the question that matters is whether the index carries the same violence. If it
    does not, reading the index is not a preference — it is the fix.
    """
    pr = [(k, v["benchmark_yf"]) for k, v in eu.ETF_UNIVERSE.items() if v.get("benchmark_yf")]
    E, I, kept = [], [], []
    for etf, idx in pr:
        de, di = daily(etf), daily(idx)
        if de is None or di is None:
            continue
        E.append(tail(de)); I.append(tail(di)); kept.append(etf)
    if not E:
        print("no matched pairs")
        return
    e, i = med(E), med(I)
    print(f"\n── ETF vs ITS OWN INDEX, tail metrics ({len(kept)} pairs) ────────")
    print(f"{'metric':20}{'ETF':>10}{'INDEX':>10}{'ratio':>9}")
    for k in e.index:
        r = e[k] / i[k] if i[k] else float("nan")
        print(f"{k:20}{e[k]:>10}{i[k]:>10}{r:>9.2f}")
