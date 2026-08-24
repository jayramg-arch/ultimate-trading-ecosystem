# -*- coding: utf-8 -*-
"""ETF NAV / premium-discount — the one ETF risk no chart can show.

WHY THIS EXISTS (24-Aug-2026). An ETF's market price can drift from the value of
what it actually holds. Buying a 2% premium is a 2% loss on day one, and no amount
of stage, RS, RRG, zone or trigger analysis will ever reveal it — every one of
those reads the PRICE, and the price is the thing that is wrong.

MEASURED on the 48-ETF universe the day this was written:

    median |premium| 0.25%   p75 0.77%   p90 1.34%
    over 1%: 9      over 2%: 3      over 5%: 3

So the risk is CONCENTRATED, not diffuse — most ETFs track fine and three do not:

    MON100     nav 274.21  ltp 327.98   +19.61%
    MASPTOP50  nav  66.63  ltp  79.60   +19.46%
    MAFANG     nav 172.45  ltp 205.87   +19.38%

All three are international. Indian funds hit SEBI's overseas-investment ceiling,
creation of new units was suspended, and without creation there is no arbitrage to
close the gap — so the premium is STRUCTURAL and persistent, not a spread that
mean-reverts by Friday. It can also collapse on a regulatory change that has
nothing to do with the Nasdaq. Two of those three were sitting on the GM board
when this was written, ranked partly on a price series the premium itself inflates.

⚠ THIS IS T-1 NAV, NOT LIVE iNAV. NSE publishes `navDate` one day behind the
quote (23-Aug NAV against a 24-Aug 16:00 price on the reference run). For a
structural 19% gap that is irrelevant. For a 0.3% reading on a day the underlying
moved 2%, the number is noise — which is exactly why the gate below is set where
only structural gaps trip it, and why `nav_date` is returned rather than hidden.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

_ENDPOINT = "https://www.nseindia.com/api/etf"
_REFERER = "https://www.nseindia.com/market-data/exchange-traded-funds-etf"
_CACHE_TTL_S = 3600          # NAV moves once a day; an hour is generous
_cache: Dict[str, object] = {"at": 0.0, "df": None, "nav_date": None}

# Above this, the board refuses to arm the name. 3.0 is chosen to sit ABOVE the
# p90 of a normal day (1.34%) and far below the structural cases (~19.5%), so it
# trips on instruments that are broken rather than on ones that are merely wide.
# An env override exists because a deliberate Nasdaq allocation at a known premium
# is a legitimate choice — it just must not happen by accident.
MAX_PREMIUM_PCT = float(os.getenv("ETF_MAX_PREMIUM_PCT", "3.0"))


def _session():
    """Reuse the project's Akamai-warming NSE session when it is importable, so
    there is one place that knows how to talk to NSE. Falls back to a local warm-up
    with the same headers rather than failing."""
    try:
        from nse_options import _get_session          # already handles ak_bmsc / nsit
        return _get_session()
    except Exception:
        import requests
        s = requests.Session()
        s.headers.update({
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0.0.0 Safari/537.36"),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": _REFERER,
        })
        try:
            s.get(_REFERER, timeout=20)
        except Exception:
            pass
        return s


def fetch_nav_table(force: bool = False) -> pd.DataFrame:
    """All NSE ETFs with NAV, LTP and premium %. Cached for an hour.

    Columns: Symbol, NAV, LTP, Premium_Pct, NAV_Date.
    Returns an EMPTY frame on any failure — never a partial or invented one, so a
    caller can tell 'no data' from 'no premium'."""
    now = time.time()
    if (not force and _cache["df"] is not None
            and now - float(_cache["at"]) < _CACHE_TTL_S):
        return _cache["df"]                                  # type: ignore[return-value]
    try:
        s = _session()
        r = s.get(_ENDPOINT, timeout=25)
        r.raise_for_status()
        payload = r.json()
    except Exception as e:
        logger.warning("NSE ETF NAV fetch failed: %s", e)
        return pd.DataFrame(columns=["Symbol", "NAV", "LTP", "Premium_Pct", "NAV_Date"])

    nav_date = str(payload.get("navDate") or "")
    rows = []
    for r_ in (payload.get("data") or []):
        sym = str(r_.get("symbol") or "").strip().upper()
        if not sym:
            continue
        try:
            nav = float(str(r_.get("nav")).replace(",", ""))
            ltp = float(str(r_.get("ltP")).replace(",", ""))
        except (TypeError, ValueError):
            continue
        if nav <= 0 or ltp <= 0:
            continue
        rows.append({"Symbol": sym, "NAV": round(nav, 4), "LTP": round(ltp, 4),
                     "Premium_Pct": round((ltp - nav) / nav * 100.0, 2),
                     "NAV_Date": nav_date})
    df = pd.DataFrame(rows)
    _cache.update({"at": now, "df": df, "nav_date": nav_date})
    logger.info("NSE ETF NAV: %d symbols, navDate %s", len(df), nav_date or "?")
    return df


def premium_map(force: bool = False) -> Dict[str, float]:
    """{SYMBOL: premium %}. Empty when the fetch failed."""
    df = fetch_nav_table(force=force)
    if df is None or df.empty:
        return {}
    return dict(zip(df["Symbol"], df["Premium_Pct"]))


def premium_for(symbol: str) -> Optional[float]:
    """Premium % for one symbol, or None when unknown.

    None means UNKNOWN and callers must treat it as such. Returning 0.0 for a
    missing symbol would read as 'trades at NAV', which is the most dangerous
    possible default for this particular measurement."""
    if not symbol:
        return None
    return premium_map().get(str(symbol).strip().upper())


def is_tradeable(symbol: str, max_premium_pct: float = None) -> tuple:
    """(ok, premium, reason). Unknown premium is ALLOWED — see below.

    An unknown premium does not block. NSE coverage is good but not total (48 of
    56 of the universe matched on the reference run), and blocking on absent data
    would silently delete the eight unmatched names with no way to tell that from
    a real rejection. The liquidity gate already stands in front of this one.
    """
    cap = MAX_PREMIUM_PCT if max_premium_pct is None else float(max_premium_pct)
    p = premium_for(symbol)
    if p is None:
        return True, None, "premium unknown"
    if abs(p) > cap:
        side = "premium" if p > 0 else "discount"
        return False, p, f"{abs(p):.1f}% {side} vs NAV (cap {cap:.1f}%)"
    return True, p, ""
