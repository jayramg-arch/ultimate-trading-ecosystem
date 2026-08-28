"""Why do hammer-at-MA patterns fire 2.5-6x more on ETFs when ETF candles are LESS wicky?

The wick study returned the opposite of the stated premise: ETF bars carry a smaller
wick fraction than stock bars (49.5% vs 55.9%), fewer noise bars, fewer spike-and-fade
shapes — and the liquidity-tier test ran BACKWARDS, with the most liquid tier the
wickiest. So thin books are not manufacturing wick noise.

Yet two patterns fire far more often on ETFs: Hammer@50 (2.5x) and Hammer@200 (6.25x).

Those tests have TWO legs — a hammer SHAPE, and PROXIMITY to the moving average. This
separates them. If the shape rate is flat and the proximity rate is not, the cause is
that an index tracker hugs its own average: a diversified basket cannot gap away from
its mean the way a single stock can on news. Then any "pattern AT a moving average"
rule fires much more often on an ETF and therefore MEANS much less — a different defect
from wick noise, needing a different fix.
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


def bars(sym):
    try:
        df = dp.fetch_ohlcv(sym, period="2y", interval="1d")
    except Exception:
        return None
    if df is None or len(df) < 220:
        return None
    df = df.rename(columns=str.title)
    if not {"Open", "High", "Low", "Close", "Volume"}.issubset(df.columns):
        return None
    df = df[(df["Volume"] > 0) & (df["High"] > df["Low"])]
    return df.tail(400) if len(df) >= 220 else None


def split(df):
    o, h, l, c = (df[x].astype(float) for x in ("Open", "High", "Low", "Close"))
    body = (c - o).abs()
    upper = h - np.maximum(c, o)
    lower = np.minimum(c, o) - l
    s50, s200 = c.rolling(50).mean(), c.rolling(200).mean()

    shape = (lower > body * 2) & (upper < body)          # the hammer, anywhere
    near50 = (l - s50).abs() / c < 0.02                  # the proximity leg alone
    near200 = (l - s200).abs() / c < 0.02
    # how far price sits from its own mean, in ATR — the underlying quantity
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    dist50 = ((c - s50).abs() / atr)

    return {
        "hammer shape%": float(shape.mean() * 100),
        "near 50-SMA%": float(near50.mean() * 100),
        "near 200-SMA%": float(near200.mean() * 100),
        "|dist| to 50 (ATR)": float(dist50.median()),
        "both @50%": float((shape & near50).mean() * 100),
    }


def med(names):
    rows = []
    for s in names:
        df = bars(s)
        if df is not None:
            rows.append(split(df))
    return pd.DataFrame(rows).median().round(2), len(rows)


if __name__ == "__main__":
    etfs = list(eu.ETF_UNIVERSE.keys())
    stocks = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ITC", "LT", "SBIN", "AXISBANK",
              "MARUTI", "TITAN", "SUNPHARMA", "NESTLEIND", "COALINDIA", "TECHM",
              "CIPLA", "GLAXO", "RADICO", "SONACOMS", "APOLLOHOSP", "EICHERMOT"]

    e, ne = med(etfs)
    s, ns = med(stocks)
    print(f"ETFs resolved {ne}, stocks {ns}\n")
    print(f"{'':22}{'ETF':>10}{'STOCK':>10}{'ratio':>9}")
    for k in e.index:
        r = e[k] / s[k] if s[k] else float("nan")
        print(f"{k:22}{e[k]:>10}{s[k]:>10}{r:>9.2f}")
    print("\nRead: if 'hammer shape%' is ~1.0x and 'near N-SMA%' is >>1.0x, the extra")
    print("fires come from PROXIMITY, not from wicks — a tracker hugs its own mean.")
