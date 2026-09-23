"""Structural volume profile and the AVWAP-BO anchor — the cash substitutes for the
options book.

WHY A SEPARATE MODULE (23-Sep-2026). The live LEVEL CHECK and the pre-registered test in
docs/PREREG_cash_levels.md must compute these the SAME way, or the thing measured is not
the thing shipped. That is the zero-drift rule this estate applies to every other signal,
and it matters more here because the parameters are pre-registered: changing one after
seeing a result is exactly what the pre-registration exists to prevent. Both callers
import from here; there is no second copy.

WHY NOT THE PANEL'S VALUE AREA. S5 prints a value area computed on the CHART timeframe.
On ANANDRATHI 75m that put VAH 0.3% above entry — an intraday band, not a structural
ceiling — and worse, an intraday profile cannot be reconstructed for a past date by any
feed wired here, so it could never be backtested. A 120-day DAILY profile can be, for
every name, over years.

PARAMETERS ARE PRE-REGISTERED. Do not tune them. If one turns out to matter that is a new
pre-registration, not an edit here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# --- pre-registered, docs/PREREG_cash_levels.md ------------------------------------
PROFILE_DAYS = 120      # lookback, trading days, ending on the bar BEFORE entry
PROFILE_BINS = 50       # price bins across the range
VALUE_AREA = 0.70       # share of volume around the POC
HVN_MULT = 1.5          # a bin is a high-volume node at >= this x mean bin volume
BO_HIGH_LOOKBACK = 20   # AVWAP-BO anchor: close was a 20-day high ...
BO_VOL_MULT = 1.5       # ... on volume >= 1.5x its 50-day average
BO_VOL_WINDOW = 50


def profile(df: pd.DataFrame) -> dict:
    """POC / VAH / VAL / HVNs from a daily frame. {} when there is not enough data.

    The frame must END on the last bar to be included — the caller does the slicing, so
    that a backtest can hand in bars strictly before the entry and get no lookahead.
    """
    if df is None or len(df) < 20:
        return {}
    d = df.tail(PROFILE_DAYS)
    hi, lo = float(d["High"].max()), float(d["Low"].min())
    if not np.isfinite(hi) or not np.isfinite(lo) or hi <= lo:
        return {}
    edges = np.linspace(lo, hi, PROFILE_BINS + 1)
    centres = (edges[:-1] + edges[1:]) / 2.0
    vol = np.zeros(PROFILE_BINS)

    # Each bar's volume is spread evenly across the bins its range covers. Cruder than a
    # tick profile and the same for every bar, which is what makes it reproducible.
    for h, l, v in zip(d["High"].to_numpy(float), d["Low"].to_numpy(float),
                       d["Volume"].to_numpy(float)):
        if not np.isfinite(v) or v <= 0 or not np.isfinite(h) or not np.isfinite(l):
            continue
        i0 = max(0, min(PROFILE_BINS - 1, int(np.searchsorted(edges, l, "right") - 1)))
        i1 = max(0, min(PROFILE_BINS - 1, int(np.searchsorted(edges, h, "right") - 1)))
        if i1 < i0:
            i0, i1 = i1, i0
        vol[i0:i1 + 1] += v / (i1 - i0 + 1)

    total = vol.sum()
    if total <= 0:
        return {}
    poc_i = int(vol.argmax())

    # Value area: start at the POC and keep taking the richer neighbour until 70% is held.
    lo_i = hi_i = poc_i
    held = vol[poc_i]
    while held < VALUE_AREA * total and (lo_i > 0 or hi_i < PROFILE_BINS - 1):
        below = vol[lo_i - 1] if lo_i > 0 else -1.0
        above = vol[hi_i + 1] if hi_i < PROFILE_BINS - 1 else -1.0
        if above >= below:
            hi_i += 1
            held += vol[hi_i]
        else:
            lo_i -= 1
            held += vol[lo_i]

    mean_bin = total / PROFILE_BINS
    hvns = [float(centres[i]) for i in range(PROFILE_BINS) if vol[i] >= HVN_MULT * mean_bin]
    return {"poc": float(centres[poc_i]), "vah": float(edges[hi_i + 1]),
            "val": float(edges[lo_i]), "hvns": hvns,
            "bars": int(len(d)), "src": "%dd daily profile" % len(d)}


def avwap_bo(df: pd.DataFrame) -> float | None:
    """Anchored VWAP from the most recent breakout day — what the breakout cohort paid.

    The cash analogue of the futures long basis: above price it is overhead supply from
    buyers who are underwater, below price it is a cohort in profit.
    """
    if df is None or len(df) < BO_VOL_WINDOW + 2:
        return None
    d = df.tail(PROFILE_DAYS * 2)
    close, vol = d["Close"].to_numpy(float), d["Volume"].to_numpy(float)
    high_n = pd.Series(close).rolling(BO_HIGH_LOOKBACK).max().to_numpy()
    vol_avg = pd.Series(vol).rolling(BO_VOL_WINDOW).mean().to_numpy()
    anchor = None
    for i in range(len(d) - 1, BO_VOL_WINDOW, -1):
        if (np.isfinite(high_n[i]) and np.isfinite(vol_avg[i]) and vol_avg[i] > 0
                and close[i] >= high_n[i] and vol[i] >= BO_VOL_MULT * vol_avg[i]):
            anchor = i
            break
    if anchor is None:
        return None
    seg = d.iloc[anchor:]
    tp = (seg["High"].to_numpy(float) + seg["Low"].to_numpy(float)
          + seg["Close"].to_numpy(float)) / 3.0
    v = seg["Volume"].to_numpy(float)
    if v.sum() <= 0:
        return None
    return float((tp * v).sum() / v.sum())


def structural_levels(symbol: str, pinned_date: str | None = None) -> dict:
    """The whole cash substitute set for one symbol. {} if the data cannot be had.

    pinned_date is passed straight through to data_provider, so the backtest calls this
    with the trade's as_of and gets exactly what the live path would have seen.
    """
    try:
        from data_provider import fetch_ohlcv
        df = fetch_ohlcv(symbol, period="1y", interval="1d", pinned_date=pinned_date)
    except Exception:
        return {}
    if df is None or df.empty:
        return {}
    out = profile(df)
    if out:
        bo = avwap_bo(df)
        if bo:
            out["avwap_bo"] = bo
    return out
