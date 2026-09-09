# -*- coding: utf-8 -*-
"""room_source_audit.py — WHICH of S4's overhead sources actually caps Room?

READ-ONLY. No gate, no Pine, no live file.

WHY THIS EXISTS
---------------
sr_age_audit.py tested the hypothesis that stale DAILY S/R levels cap Room, and
refuted it: 68% of the level pool is >6 months old, but the level that binds is fresh
or seasoned 84% of the time, and dropping stale levels frees room for 1 name in 55.

S4's `_ovh` is the nearest of SIX sources (S4 ~line 5205):
    supply-zone proximal · sr_above (M/W/D) · daily pivot res · weekly pivot res ·
    lastPH · the supply band
so the binding one may not be daily S/R at all. This ranks them.

WHAT IT DOES NOT DO
-------------------
It measures the GATE'S INPUTS on today's board, not outcomes. "Which source binds"
does not say whether that source SHOULD bind. Nothing here justifies removing a source
— that needs a forward test, and Room-source removal was already measured once
(pivot-ceiling ablation, filed) and did not pay.

Usage:  python room_source_audit.py [--universe gm_board_cache_Daily.csv] [--limit 60]
"""
from __future__ import annotations
import argparse
import math

import numpy as np
import pandas as pd

import data_provider as dp
import zone_engine as ze

TRADING_DAYS_PER_MONTH = 21.0


def _pivot_res(df: pd.DataFrame, px: float, pvL: int = 5, pvR: int = 5):
    """Nearest confirmed pivot HIGH above price, and its age in months."""
    h = df["High"].to_numpy(float)
    n = len(h)
    best, best_bar = None, None
    for b in range(pvL, n - pvR):
        hi = h[b]
        if hi <= px:
            continue
        if (all(hi > h[b - k] for k in range(1, pvL + 1))
                and all(hi >= h[b + k] for k in range(1, pvR + 1))):
            if best is None or hi < best:
                best, best_bar = hi, b
    age = (n - 1 - best_bar) / TRADING_DAYS_PER_MONTH if best_bar is not None else None
    return best, age


def _supply_above(df: pd.DataFrame, px: float, tf: str = "D"):
    """Nearest FRESH supply-zone proximal above price."""
    try:
        zones = ze.detect_zones(df, tf)
    except Exception:
        return None
    best = None
    for z in zones:
        if z.is_demand or z.tested:
            continue
        edge = min(z.proximal, z.distal)          # the underside of a supply zone
        if edge > px and (best is None or edge < best):
            best = edge
    return best


def _sr_above(df: pd.DataFrame, px: float, tf: str = "D"):
    """Nearest non-MTTWR S/R level above price on this timeframe."""
    try:
        levels = ze.detect_sr_levels(df, tf)
    except Exception:
        return None
    p = ze.SR_DEFAULTS
    mttwr = max(p["mttwr_n"], p["min_touch"] + 1)
    best = None
    for L in levels:
        if L["price"] > px and L["touches"] < mttwr:
            if best is None or L["price"] < best:
                best = L["price"]
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default="gm_board_cache_Daily.csv")
    ap.add_argument("--limit", type=int, default=60)
    a = ap.parse_args()

    u = pd.read_csv(a.universe)
    col = "Symbol" if "Symbol" in u.columns else u.columns[0]
    syms = [str(s).strip().upper() for s in u[col].dropna().unique()][:a.limit]
    print("universe: %s  (%d symbols)\n" % (a.universe, len(syms)))

    rows = []
    for s in syms:
        try:
            d = dp.fetch_ohlcv(s, period="3y", interval="1d")
            if d is None or len(d) < 200:
                continue
            d = d.rename(columns=str.title)
            w = d.resample("W-FRI").agg({"Open": "first", "High": "max", "Low": "min",
                                         "Close": "last", "Volume": "sum"}).dropna()
            px = float(d["Close"].iloc[-1])
            hh = d["High"].to_numpy(float); ll = d["Low"].to_numpy(float)
            cc = d["Close"].to_numpy(float)
            _, atr = ze._wilder_atr(hh, ll, cc, 14)
            atr14 = float(atr[-1]) if not math.isnan(atr[-1]) else float("nan")

            dpv, dpv_age = _pivot_res(d, px)
            wpv, _ = _pivot_res(w, px)
            src = {
                "supply zone": _supply_above(d, px, "D"),
                "S/R · D":     _sr_above(d, px, "D"),
                "S/R · W":     _sr_above(w, px, "W"),
                "pivot · D":   dpv,
                "pivot · W":   wpv,
            }
            src = {k: v for k, v in src.items() if v is not None and v > px}
            if not src:
                rows.append(dict(sym=s, source="NO CEILING", ovh=np.nan,
                                 dist_pct=np.nan, atrs=np.nan, pivd_age=dpv_age))
                continue
            k = min(src, key=lambda k: src[k])
            ovh = src[k]
            rows.append(dict(sym=s, source=k, ovh=ovh,
                             dist_pct=(ovh - px) / px * 100.0,
                             atrs=(ovh - px) / atr14 if atr14 == atr14 and atr14 > 0 else np.nan,
                             pivd_age=dpv_age))
        except Exception:
            pass

    if not rows:
        print("nothing resolved")
        return 1
    r = pd.DataFrame(rows)
    print("=== WHICH SOURCE CAPS ROOM (n=%d names) ===" % len(r))
    for k, g in r.groupby("source"):
        print("   %-12s n=%3d  %5.1f%%   median +%.1f%%   median %.2f x ATR"
              % (k, len(g), len(g) / len(r) * 100,
                 g["dist_pct"].median(), g["atrs"].median()))

    live = r[r["source"] != "NO CEILING"].dropna(subset=["atrs"])
    print("\n=== HOW MUCH ROOM, IN ATR (this is what 'no room' actually measures) ===")
    for lo, hi, lab in [(0, 1, "< 1 ATR"), (1, 2, "1-2 ATR"), (2, 4, "2-4 ATR"), (4, 99, "> 4 ATR")]:
        g = live[(live["atrs"] >= lo) & (live["atrs"] < hi)]
        print("   %-9s n=%3d  %5.1f%%" % (lab, len(g), len(g) / len(live) * 100))
    print("   median room: %.2f x ATR  (+%.1f%%)"
          % (live["atrs"].median(), live["dist_pct"].median()))

    print("\n=== IMPLIED R AT S4's STOP CAPS (room / stop distance) ===")
    for cap, lab in ((2.5, "SWING  2.5xATR"), (4.0, "POSITIONAL 4.0xATR")):
        rr = live["atrs"] / cap
        print("   %-18s median %.2fR   share >= 2R: %.0f%%   share < 1R: %.0f%%"
              % (lab, rr.median(), (rr >= 2).mean() * 100, (rr < 1).mean() * 100))

    print("\nNOTE: inputs, not outcomes. Which source binds is not evidence that it")
    print("should be removed — Room-source removal has been measured before and did")
    print("not pay. Read this as a diagnosis of WHERE the constraint comes from.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
