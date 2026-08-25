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


_DISK_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "data", "etf_nav_cache.csv")
# Beyond this the cached premium is refused rather than used. A week is generous
# for a number that only has to separate 1% from 19%, and it still stops a table
# from a previous quarter being read as current.
_DISK_MAX_AGE_DAYS = 7


def _load_disk_cache():
    """Last good NAV table, or None when absent / too old to trust."""
    try:
        if not os.path.exists(_DISK_CACHE):
            return None
        age_days = (time.time() - os.path.getmtime(_DISK_CACHE)) / 86400.0
        if age_days > _DISK_MAX_AGE_DAYS:
            logger.warning("cached ETF NAV is %.1f days old - refusing it", age_days)
            return None
        return pd.read_csv(_DISK_CACHE)
    except Exception as e:
        logger.warning("ETF NAV disk cache unreadable: %s", e)
        return None


def _save_disk_cache(df) -> None:
    try:
        os.makedirs(os.path.dirname(_DISK_CACHE), exist_ok=True)
        df.to_csv(_DISK_CACHE, index=False)
    except Exception as e:
        logger.warning("ETF NAV disk cache not written: %s", e)


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
        # DISK FALLBACK (24-Aug-2026). Found the morning after this shipped: the
        # auto-pilot ran at 06:20, NSE was unreachable pre-market, and the gate
        # degraded to OFF -- so MON100 and MAFANG went onto the board at ~19.5%
        # premium, which is precisely what the gate exists to stop. A transient
        # outage silently disabling a safety check is the wrong failure direction.
        # NAV moves ONCE A DAY, so yesterday's number catches a structural 19.5%
        # exactly as well as today's; it is only useless for sub-1% readings, and
        # the cap is deliberately set where those do not matter.
        cached = _load_disk_cache()
        if cached is not None and not cached.empty:
            logger.warning("NSE ETF NAV fetch failed (%s) - using cached NAV from %s",
                           e, cached["NAV_Date"].iloc[0])
            _cache.update({"at": now, "df": cached,
                           "nav_date": cached["NAV_Date"].iloc[0]})
            return cached
        logger.warning("NSE ETF NAV fetch failed and no usable cache: %s", e)
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
    if not df.empty:
        _save_disk_cache(df)          # so a pre-market outage cannot disable the gate
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
