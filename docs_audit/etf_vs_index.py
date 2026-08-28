"""Read the INDEX, not the ETF — testing the trainer's advice against the data.

Jay's trainer told him to analyse the index chart rather than the ETF chart, and he
observes that JUNIORBEES vs Nifty Next 50 "looks like a stock" on the index side.

That is a better proposition than re-tuning the ETF rules, because it removes the
problem instead of compensating for it. The ETF is a WRAPPER; the index is the thing
the price action is actually about. If the index bars behave like stock bars, the
existing battery transfers unchanged and the ETF-specific facts (NAV premium,
liquidity) stay where they already are — as overlays.

This measures the same geometry and the same wick-reading patterns three ways:
the ETF, its own benchmark index, and a stock control. etf_universe already carries
benchmark_yf for 34 of 56 ETFs, so the pairing is exact rather than approximate.

The prediction, if the trainer is right: index columns should sit closer to the stock
control than the ETF columns do — especially on distance-to-mean, which the previous
study identified as the real defect.
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
    if not {"Open", "High", "Low", "Close"}.issubset(df.columns):
        return None
    # An index has no volume, so the volume filter applies only where volume exists.
    if "Volume" in df.columns and float(df["Volume"].fillna(0).sum()) > 0:
        df = df[df["Volume"] > 0]
    df = df[df["High"] > df["Low"]]
    return df.tail(400) if len(df) >= 220 else None


def stats(df):
    o, h, l, c = (df[x].astype(float) for x in ("Open", "High", "Low", "Close"))
    rng = (h - l).replace(0, np.nan)
    body = (c - o).abs()
    upper = h - np.maximum(c, o)
    lower = np.minimum(c, o) - l
    s50, s200 = c.rolling(50).mean(), c.rolling(200).mean()
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()

    shape = (lower > body * 2) & (upper < body)
    near50 = (l - s50).abs() / c < 0.02
    near200 = (l - s200).abs() / c < 0.02
    lo10 = l.rolling(10).min()

    return {
        "wick%": float(((upper + lower) / rng).median() * 100),
        "upper wick%": float((upper / rng).median() * 100),
        "noise bars%": float((body / rng < 0.33).mean() * 100),
        "dist to 50 (ATR)": float(((c - s50).abs() / atr).median()),
        "near 50%": float(near50.mean() * 100),
        "near 200%": float(near200.mean() * 100),
        "hammer shape%": float(shape.mean() * 100),
        "Hammer@50 %": float((shape & near50).mean() * 100),
        "Hammer@200 %": float((shape & near200).mean() * 100),
        "Spring/sweep%": float(((l < lo10.shift()) & (c > lo10.shift())).mean() * 100),
    }


def med(names):
    rows, ok = [], []
    for s in names:
        df = bars(s)
        if df is not None:
            rows.append(stats(df)); ok.append(s)
    if not rows:
        return None, []
    return pd.DataFrame(rows).median().round(2), ok


if __name__ == "__main__":
    pairs = [(k, v["benchmark_yf"]) for k, v in eu.ETF_UNIVERSE.items() if v.get("benchmark_yf")]
    stocks = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ITC", "LT", "SBIN", "AXISBANK",
              "MARUTI", "TITAN", "SUNPHARMA", "NESTLEIND", "COALINDIA", "TECHM",
              "CIPLA", "GLAXO", "RADICO", "SONACOMS", "APOLLOHOSP", "EICHERMOT"]

    # Only PAIRS where BOTH sides resolve, so the comparison is like-for-like rather
    # than two different samples.
    e_rows, i_rows, kept = [], [], []
    for etf, idx in pairs:
        de, di = bars(etf), bars(idx)
        if de is None or di is None:
            continue
        e_rows.append(stats(de)); i_rows.append(stats(di)); kept.append((etf, idx))

    E = pd.DataFrame(e_rows).median().round(2)
    I = pd.DataFrame(i_rows).median().round(2)
    S, sok = med(stocks)

    print(f"matched pairs where BOTH sides resolve: {len(kept)}   stock control: {len(sok)}\n")
    print(f"{'metric':20}{'ETF':>9}{'INDEX':>9}{'STOCK':>9}   {'closer to stock':>16}")
    for k in E.index:
        # which of ETF / INDEX sits nearer the stock control on this metric
        de, di = abs(E[k] - S[k]), abs(I[k] - S[k])
        who = "INDEX" if di < de else ("ETF" if de < di else "tie")
        print(f"{k:20}{E[k]:>9}{I[k]:>9}{S[k]:>9}   {who:>16}")

    print("\n── JUNIORBEES vs Nifty Next 50, the case Jay looked at ───────")
    for lbl, sym in (("JUNIORBEES (ETF)", "JUNIORBEES"), ("^NSMIDCP (index)", "^NSMIDCP")):
        d = bars(sym)
        if d is None:
            print(f"  {lbl:20} no data")
            continue
        st = stats(d)
        print(f"  {lbl:20} wick {st['wick%']:.1f}%  upper {st['upper wick%']:.1f}%  "
              f"dist50 {st['dist to 50 (ATR)']:.2f} ATR  Hammer@50 {st['Hammer@50 %']:.2f}%")
