# -*- coding: utf-8 -*-
"""sr_age_audit.py — how OLD are the daily S/R levels that cap Room?

READ-ONLY. Touches no gate, no Pine, no live file. Written to test a premise before
designing anything, per the standing rule.

THE PREMISE UNDER TEST
----------------------
S4's Room row reports "no room" because the nearest overhead obstacle sits close to
price, and the complaint is that the obstacle is usually a DAILY S/R level. Research
Jay gathered says a daily resistance level is potent for 1-4 weeks, standard for 1-3
months, soft at 3-6, and beyond 6 months is a psychological speed bump rather than
real supply.

The engine has NO time factor at all. Its only age-like mechanism is `pool=40`, a
CAPACITY bound: when a 41st level appears the oldest FIRST-touch is evicted. And that
pool was deliberately RAISED from 16 to 40 (S4 line 1308) precisely so older levels
would stay reachable — the opposite of a decay rule.

So: measure the age distribution of the levels that actually cap Room before adding
anything.

AGE IS DERIVED, NOT INSTRUMENTED
--------------------------------
`detect_sr_levels` does not emit age (it tracks last-touch bar internally as `Lb` but
does not return it). Rather than edit the engine mid-session, age is recovered from the
OUTPUT plus the frame: for each returned level, find every confirmed pivot whose extreme
sits inside the level's merge tolerance, and take the LAST one. That is the same
definition the engine merges on, so it reproduces `Lb` without touching the engine.

Usage:
    python sr_age_audit.py [--universe gm_board_cache_Daily.csv] [--limit 60]
"""
from __future__ import annotations
import argparse
import math

import numpy as np
import pandas as pd

import data_provider as dp
import zone_engine as ze

TRADING_DAYS_PER_MONTH = 21.0
# The doc's schedule, verbatim, so the buckets are its buckets and not ones fitted here.
BANDS = [(0, 1, "FRESH   <1mo"), (1, 3, "SEASONED 1-3mo"),
         (3, 6, "AGED     3-6mo"), (6, 999, "STALE    >6mo")]


def _band(months: float) -> str:
    for lo, hi, name in BANDS:
        if lo <= months < hi:
            return name
    return BANDS[-1][2]


def _pivots(df: pd.DataFrame, pvL: int, pvR: int):
    h = df["High"].to_numpy(float)
    l = df["Low"].to_numpy(float)
    n = len(h)
    ph, pl = [], []
    for b in range(pvL, n - pvR):
        hi, lo = h[b], l[b]
        if (all(hi > h[b - k] for k in range(1, pvL + 1))
                and all(hi >= h[b + k] for k in range(1, pvR + 1))):
            ph.append((b, hi))
        if (all(lo < l[b - k] for k in range(1, pvL + 1))
                and all(lo <= l[b + k] for k in range(1, pvR + 1))):
            pl.append((b, lo))
    return ph, pl


def _last_touch_bar(df, level_px, ph, pl, atr, tol_atr):
    """The newest confirmed pivot sitting inside this level's merge tolerance —
    the same test `_merge` clusters on, so this reproduces the engine's Lb."""
    best = -1
    for b, v in list(ph) + list(pl):
        a = atr[b] if b < len(atr) and not math.isnan(atr[b]) else 0.0
        if a > 0 and abs(v - level_px) <= tol_atr * a and b > best:
            best = b
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default="gm_board_cache_Daily.csv")
    ap.add_argument("--limit", type=int, default=60)
    a = ap.parse_args()

    try:
        u = pd.read_csv(a.universe)
        col = "Symbol" if "Symbol" in u.columns else u.columns[0]
        syms = [str(s).strip().upper() for s in u[col].dropna().unique()][:a.limit]
    except Exception as e:
        print("could not read %s: %s" % (a.universe, e))
        return 1
    print("universe: %s  (%d symbols)" % (a.universe, len(syms)))

    p = ze.SR_DEFAULTS
    rows, capped, failed = [], [], 0
    for s in syms:
        try:
            df = dp.fetch_ohlcv(s, period="3y", interval="1d")
            if df is None or len(df) < 120:
                failed += 1
                continue
            df = df.rename(columns=str.title)
            levels = ze.detect_sr_levels(df, "D")
            if not levels:
                continue
            hh = df["High"].to_numpy(float); ll = df["Low"].to_numpy(float)
            cc = df["Close"].to_numpy(float)
            _, atr = ze._wilder_atr(hh, ll, cc, 14)
            ph, pl = _pivots(df, p["pvL"], p["pvR"])
            n = len(df)
            px = float(cc[-1])
            mttwr_eff = max(p["mttwr_n"], p["min_touch"] + 1)

            near = None
            for L in levels:
                lb = _last_touch_bar(df, L["price"], ph, pl, atr, p["tol_atr"])
                if lb < 0:
                    continue
                months = (n - 1 - lb) / TRADING_DAYS_PER_MONTH
                rows.append(dict(sym=s, price=L["price"], touches=L["touches"],
                                 grade=L["grade"], role=L["role"], months=months,
                                 band=_band(months)))
                # what Room would use: nearest NON-MTTWR level ABOVE price
                if L["role"] == "RESISTANCE" and L["touches"] < mttwr_eff and L["price"] > px:
                    if near is None or L["price"] < near["price"]:
                        near = dict(sym=s, price=L["price"], months=months,
                                    band=_band(months), touches=L["touches"],
                                    dist_pct=(L["price"] - px) / px * 100.0)
            if near:
                capped.append(near)
        except Exception:
            failed += 1

    if not rows:
        print("no levels resolved — nothing to report")
        return 1
    d = pd.DataFrame(rows)
    c = pd.DataFrame(capped)

    print("\n=== ALL daily levels (%d levels across %d names, %d fetch failures) ==="
          % (len(d), d["sym"].nunique(), failed))
    for b in [x[2] for x in BANDS]:
        g = d[d["band"] == b]
        print("   %-16s n=%4d  %5.1f%%" % (b, len(g), len(g) / len(d) * 100))
    print("   oldest level: %.1f months   median: %.1f months"
          % (d["months"].max(), d["months"].median()))

    print("\n=== THE LEVEL THAT CAPS ROOM (nearest non-MTTWR resistance above price) ===")
    if c.empty:
        print("   none resolved")
        return 0
    for b in [x[2] for x in BANDS]:
        g = c[c["band"] == b]
        if len(g):
            print("   %-16s n=%3d  %5.1f%%   median distance +%.1f%%"
                  % (b, len(g), len(g) / len(c) * 100, g["dist_pct"].median()))
    stale = c[c["months"] >= 6]
    print("\n   %d of %d names (%.1f%%) are capped by a level last touched >6 months ago"
          % (len(stale), len(c), len(stale) / len(c) * 100))
    print("   those sit a median +%.1f%% above price" % (stale["dist_pct"].median() if len(stale) else float("nan")))

    print("\n=== IF STALE (>6mo) DAILY LEVELS WERE DROPPED, what caps Room instead? ===")
    freed = 0
    for s, g in d[(d["role"] == "RESISTANCE")].groupby("sym"):
        cur = c[c["sym"] == s]
        if cur.empty or cur.iloc[0]["months"] < 6:
            continue
        alt = g[(g["months"] < 6) & (g["price"] > cur.iloc[0]["price"])]
        if len(alt):
            nxt = alt["price"].min()
            freed += 1
            if freed <= 8:
                print("   %-12s capped %.2f (%.1fmo) -> next non-stale %.2f  (+%.1f%% more room)"
                      % (s, cur.iloc[0]["price"], cur.iloc[0]["months"], nxt,
                         (nxt - cur.iloc[0]["price"]) / cur.iloc[0]["price"] * 100))
    print("   %d names would move to a higher, non-stale ceiling" % freed)
    print("\nNOTE: this measures the GATE's inputs, not outcomes. Whether dropping stale")
    print("levels improves trades is a separate question and needs its own test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
