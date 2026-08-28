"""Do the stock price-action rules transfer to ETFs? Measure before deciding.

Jay: "the candles are too wicky on ETFs... we cannot blindly use the stock rules."

The premise is plausible and the code confirms half of it already: pa_patterns.py has
NO ETF branch, so all 17 bull patterns run identically on a Nifty tracker and on a
midcap stock. S4's only ETF-specific rule is the NAV-premium veto.

What is NOT yet established is whether that actually distorts anything, so this
measures two things on daily bars:

  1. WICK GEOMETRY   — is an ETF candle really wickier than a stock candle, and does
                       it scale with liquidity (the mechanism would be a wide spread
                       on a thin book, which prints as wick rather than body).

  2. PATTERN FIRE RATE — the number that decides it. Several bull patterns read the
                       EXTREMES rather than the body, so if wick noise is real they
                       should fire measurably more often on ETFs for no better reason.
                       Those are the rules that would need re-tuning; the body- and
                       trend-based ones can be left alone.

Deliberately NOT measured here: whether those extra fires make money. That needs a
forward-return study, and claiming an edge conclusion off a fire-rate count would be
the "GO gate is a stopwatch" mistake again. This answers "do the rules behave
differently", which is the question actually asked.
"""
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

# This lives in docs_audit/, so only that directory is on sys.path by default.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import data_provider as dp
import etf_universe as eu

LOOKBACK = "2y"


def bars(sym):
    try:
        df = dp.fetch_ohlcv(sym, period=LOOKBACK, interval="1d")
    except Exception:
        return None
    if df is None or len(df) < 120:
        return None
    df = df.rename(columns=str.title)
    need = {"Open", "High", "Low", "Close", "Volume"}
    if not need.issubset(df.columns):
        return None
    # Dhan publishes a phantom 15:30 stub (O=H=L=C, volume 0) that would read as a
    # doji with no wick and dilute exactly the statistic under test.
    df = df[(df["Volume"] > 0) & (df["High"] > df["Low"])]
    return df.tail(400) if len(df) >= 120 else None


def geom(df):
    o, h, l, c = (df[x].astype(float) for x in ("Open", "High", "Low", "Close"))
    rng = (h - l)
    body = (c - o).abs()
    upper = h - np.maximum(c, o)
    lower = np.minimum(c, o) - l
    wick_frac = ((upper + lower) / rng)
    return {
        "wick%": float(wick_frac.median() * 100),
        "range%": float((rng / c).median() * 100),
        # a bar whose body is under a third of its range is mostly noise
        "noise_bars%": float((body / rng < 0.33).mean() * 100),
        # the shape that fakes a rejection: long upper wick, tiny body
        "spike_fade%": float(((upper / rng > 0.5) & (body / rng < 0.3)).mean() * 100),
        "n": len(df),
    }


def fires(df):
    """The wick-reading legs of the bull battery, in isolation.

    Each is the S4Core/pa_patterns formula reduced to its wick-sensitive core — the
    point is the RELATIVE fire rate between the two universes, not a re-implementation
    of the battery.
    """
    o, h, l, c, v = (df[x].astype(float) for x in ("Open", "High", "Low", "Close", "Volume"))
    rng = (h - l).replace(0, np.nan)
    body = (c - o).abs()
    upper = h - np.maximum(c, o)
    lower = np.minimum(c, o) - l
    rv = v / v.rolling(50).mean()
    sma50 = c.rolling(50).mean()
    sma200 = c.rolling(200).mean()
    lo10 = l.rolling(10).min()

    out = {}
    # SC / Power Play — pure wick geometry: close in the top quarter of the range
    out["SC (strong close)"] = float((((c - l) > (h - c) * 3) & (c > o) & (rv > 1.0)).mean() * 100)
    # Hammer at a moving average — long lower wick near support
    ham = (lower > body * 2) & (upper < body)
    out["Hammer @50"] = float((ham & ((l - sma50).abs() / c < 0.02)).mean() * 100)
    out["Hammer @200"] = float((ham & ((l - sma200).abs() / c < 0.02)).mean() * 100)
    # Spring / liquidity sweep — undercut the 10-day low, close back above it
    out["Spring/sweep"] = float(((l < lo10.shift()) & (c > lo10.shift())).mean() * 100)
    # bar_ok, S4's B gate — close green OR in the upper half of the range
    out["B gate (bar_ok)"] = float(((c >= o) | ((c - l) / rng >= 0.5)).mean() * 100)
    # NR7 — narrowest range of seven, a pure range test
    out["NR7"] = float((rng == rng.rolling(7).min()).mean() * 100)
    return out


def run(names, label):
    G, F, ok = [], [], []
    for s in names:
        df = bars(s)
        if df is None:
            continue
        G.append(geom(df)); F.append(fires(df)); ok.append(s)
    if not G:
        return None, []
    return (pd.DataFrame(G).median().round(2), pd.DataFrame(F).median().round(2)), ok


if __name__ == "__main__":
    etfs = list(eu.ETF_UNIVERSE.keys())
    tiers = {s: eu.ETF_UNIVERSE[s].get("liquidity_tier", "?") for s in etfs}

    stocks = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ITC", "LT", "SBIN", "AXISBANK",
              "MARUTI", "TITAN", "SUNPHARMA", "NESTLEIND", "COALINDIA", "TECHM",
              "CIPLA", "GLAXO", "RADICO", "SONACOMS", "APOLLOHOSP", "EICHERMOT"]

    print(f"Sampling {len(etfs)} ETFs and {len(stocks)} stocks, {LOOKBACK} of daily bars\n")
    (eg, ef), eok = run(etfs, "ETF")
    (sg, sf), sok = run(stocks, "STOCK")
    print(f"resolved: {len(eok)} ETFs, {len(sok)} stocks\n")

    print("── CANDLE GEOMETRY (median across symbols) ───────────────────")
    print(f"{'metric':22}{'ETF':>10}{'STOCK':>10}{'ratio':>9}")
    for k in eg.index:
        r = eg[k] / sg[k] if sg[k] else float("nan")
        print(f"{k:22}{eg[k]:>10}{sg[k]:>10}{r:>9.2f}")

    print("\n── WICK-READING PATTERN FIRE RATE (% of bars) ────────────────")
    print(f"{'pattern':22}{'ETF':>10}{'STOCK':>10}{'ratio':>9}")
    for k in ef.index:
        r = ef[k] / sf[k] if sf[k] else float("nan")
        print(f"{k:22}{ef[k]:>10}{sf[k]:>10}{r:>9.2f}")

    # Does it scale with liquidity? That is the mechanism test: if a thin book is the
    # cause, tier C should be wickier than tier A. If it does not scale, the cause is
    # something else and a liquidity-based rule would be treating the wrong thing.
    print("\n── BY LIQUIDITY TIER (the mechanism test) ────────────────────")
    print(f"{'tier':8}{'n':>4}{'wick%':>9}{'range%':>9}{'spike_fade%':>13}{'SC fires%':>11}")
    for t in ("A", "B", "C"):
        syms = [s for s in eok if tiers.get(s) == t]
        if not syms:
            continue
        g, f = [], []
        for s in syms:
            df = bars(s)
            if df is not None:
                g.append(geom(df)); f.append(fires(df))
        if not g:
            continue
        gm, fm = pd.DataFrame(g).median(), pd.DataFrame(f).median()
        print(f"{t:8}{len(syms):>4}{gm['wick%']:>9.1f}{gm['range%']:>9.2f}"
              f"{gm['spike_fade%']:>13.1f}{fm['SC (strong close)']:>11.1f}")
