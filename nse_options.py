"""
nse_options.py  –  NSE Option Chain Data Module
─────────────────────────────────────────────────
Strategy
--------
Option A (primary):  NSE two-step session
  1. GET nseindia.com/         → warms Akamai cookie in session
  2. GET nseindia.com/api/...  → returns full JSON option chain

Option B (fallback): nsepython library (pip install nsepython)
  Used automatically if Option A raises an exception.

Caches results to reports/nse_oc_{symbol}.json with a 5-min TTL so
the Streamlit page re-renders instantly on repeated loads.

Public API
----------
get_option_chain(symbol, expiry_index=0) → dict
    {
        "symbol":       str,
        "spot":         float,
        "expiry":       str,          # e.g. "24-Apr-2025"
        "expiries":     list[str],
        "pcr":          float,        # total_pe_oi / total_ce_oi
        "max_pain":     float,        # strike where writer pain is minimised
        "total_ce_oi":  int,
        "total_pe_oi":  int,
        "timestamp":    str,
        "chain_df":     pd.DataFrame, # one row per strike, see columns below
        "source":       "nse_session" | "nsepython" | "cache",
        "error":        str | None,
    }

chain_df columns
----------------
strike, CE_OI, CE_chgOI, CE_LTP, CE_IV, CE_Vol,
        PE_OI, PE_chgOI, PE_LTP, PE_IV, PE_Vol
"""

import json
import logging
import os
import time
from pathlib import Path
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)

_DIR       = Path(os.path.dirname(os.path.abspath(__file__)))
_CACHE_DIR = _DIR / "reports"
_CACHE_TTL = 300   # seconds (5 min)

# ── Browser-like headers required to pass Akamai ────────────────────────────
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         "https://www.nseindia.com/",
    "Connection":      "keep-alive",
    "DNT":             "1",
    "Sec-Fetch-Dest":  "empty",
    "Sec-Fetch-Mode":  "cors",
    "Sec-Fetch-Site":  "same-origin",
}

# ── Session cache (in-process) ───────────────────────────────────────────────
_session_obj   = None
_session_built = 0.0
_SESSION_TTL   = 270   # renew session before Akamai 5-min window


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_session():
    """
    Build a warm NSE session capable of bypassing Akamai bot-detection.

    Three approaches tried in order:

    A) curl_cffi (preferred)
       Impersonates Chrome's exact TLS fingerprint — Akamai cannot
       distinguish it from a real browser.
       Install: pip install curl_cffi

    B) requests + 3-step warmup (fallback)
       Works when Akamai is in lenient mode; fails on full JS-challenge.

    Both approaches visit two NSE pages before the API call:
      1. nseindia.com            → base Akamai cookie (ak_bmsc / bm_sz)
      2. nseindia.com/option-chain → NSE session cookie (nseappid / nsit)
      3. (API call)              → returns real data
    """
    global _session_obj, _session_built

    now = time.monotonic()
    if _session_obj and (now - _session_built) < _SESSION_TTL:
        return _session_obj

    # ── Approach A: curl_cffi — Chrome TLS impersonation ────────────────────
    try:
        from curl_cffi import requests as cffi_requests  # type: ignore
        s = cffi_requests.Session(impersonate="chrome120")
        s.get("https://www.nseindia.com", timeout=12)
        time.sleep(1.0)
        s.get("https://www.nseindia.com/option-chain", timeout=12)
        time.sleep(0.6)
        _session_obj   = s
        _session_built = now
        logger.info("NSE session warmed via curl_cffi (Chrome120 TLS)")
        return s
    except ImportError:
        logger.info("curl_cffi not installed — falling back to requests. "
                    "For reliable NSE data: pip install curl_cffi")
    except Exception as exc:
        logger.warning("curl_cffi session failed: %s — trying requests", exc)

    # ── Approach B: requests + 3-step warmup ────────────────────────────────
    import requests as _requests
    s = _requests.Session()
    s.headers.update(_HEADERS)
    try:
        s.get("https://www.nseindia.com", timeout=12)
        time.sleep(1.2)
        s.get("https://www.nseindia.com/option-chain", timeout=12)
        time.sleep(0.8)
        _session_obj   = s
        _session_built = now
        logger.info("NSE session warmed via requests (3-step)")
    except Exception as exc:
        logger.warning("requests warmup failed: %s", exc)
        _session_obj   = s
        _session_built = now
    return s


def _cache_path(symbol: str) -> Path:
    return _CACHE_DIR / f"nse_oc_{symbol.upper()}.json"


def _load_cache(symbol: str) -> dict | None:
    """Return cached data dict if fresher than TTL, else None."""
    p = _cache_path(symbol)
    if not p.exists():
        return None
    try:
        raw  = json.loads(p.read_text(encoding="utf-8"))
        age  = time.time() - raw.get("_cached_at", 0)
        if age < _CACHE_TTL:
            df   = pd.DataFrame(raw.pop("_chain_rows", []))
            raw["chain_df"] = df
            raw["source"]   = "cache"
            return raw
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        logger.warning("Cache load failed for %s: %s", symbol, exc)
    return None


def _save_cache(symbol: str, result: dict) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    storable = {k: v for k, v in result.items() if k != "chain_df"}
    storable["_chain_rows"] = result["chain_df"].to_dict(orient="records") \
        if isinstance(result.get("chain_df"), pd.DataFrame) else []
    storable["_cached_at"]  = time.time()
    try:
        _cache_path(symbol).write_text(json.dumps(storable, default=str), encoding="utf-8")
    except Exception as exc:
        logger.warning("Cache write failed: %s", exc)


_INDICES = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"}


def _api_url(symbol: str, variant: int = 0) -> str:
    """The chain URL for `symbol`. variant 1 is the fallback route.

    MEASURED 1-Sep-2026: option-chain-indices returns a hard 404 - it is RETIRED, so
    every NIFTY/BANKNIFTY request had been failing permanently rather than
    intermittently, and would have gone on failing during market hours too. NSE replaced
    the per-segment routes with option-chain-v3?type=Indices|Equity.

    Equities keep the old route as primary because it still answers, with v3 as the
    fallback, so the day that one is retired this degrades instead of breaking.
    """
    sym = symbol.upper()
    seg = "Indices" if sym in _INDICES else "Equity"
    v3 = f"https://www.nseindia.com/api/option-chain-v3?type={seg}&symbol={sym}"
    if sym in _INDICES:
        return v3                                   # the old indices route is a 404
    if variant:
        return v3
    return f"https://www.nseindia.com/api/option-chain-equities?symbol={sym}"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _calc_max_pain(df: pd.DataFrame) -> float:
    """
    Max Pain = strike where total writer loss is minimised.
    For each candidate strike S (as expiry price):
      writer_pain(S) = sum_K[ max(S-K,0)*CE_OI[K] + max(K-S,0)*PE_OI[K] ]
    """
    strikes   = df["strike"].values
    ce_oi     = df["CE_OI"].values
    pe_oi     = df["PE_OI"].values
    min_pain  = float("inf")
    max_pain_strike = float(strikes[len(strikes) // 2]) if len(strikes) else 0.0

    for s in strikes:
        pain = sum(max(s - k, 0) * c + max(k - s, 0) * p
                   for k, c, p in zip(strikes, ce_oi, pe_oi))
        if pain < min_pain:
            min_pain        = pain
            max_pain_strike = float(s)

    return max_pain_strike


def _parse_nse_json(raw: dict, expiry_index: int, symbol: str) -> dict:
    """Parse NSE option chain JSON → standardised result dict."""
    records  = raw.get("records", {})
    expiries = records.get("expiryDates", [])

    if not expiries:
        # NAME THE LIKELY CAUSE. An empty chain after hours is NSE gating the endpoint,
        # not a refused session - measured 1-Sep-2026, when contract-info returned live
        # data over the SAME session while the chain returned {}. Telling the user to
        # rebuild the session at 22:00 sends them to retry something that cannot work
        # until the market opens.
        _hrs = _is_market_hours()
        return {"error": (
            "NSE returned an empty chain (no expiry dates). "
            + ("The session cookie may not have been accepted — click Fetch Chain again "
               "to rebuild the session, or run: pip install nsepython"
               if _hrs else
               "This is OUTSIDE market hours, when NSE stops serving the option chain — "
               "the session is probably fine. Try again between 09:15 and 15:30 IST.")
        ), "chain_df": pd.DataFrame(),
                # None, NOT 0. These feed drawn support/resistance levels; a
                # max_pain of 0 is a price line below every stop on the chart and is
                # indistinguishable from a real one. A missing value must stay missing.
                "symbol": symbol, "spot": None, "pcr": None, "max_pain": None,
                "total_ce_oi": None, "total_pe_oi": None, "expiry": "", "expiries": [],
                "timestamp": ""}

    expiry_index = min(expiry_index, len(expiries) - 1)
    target       = expiries[expiry_index]
    spot         = float(records.get("underlyingValue", 0))

    rows = []
    for entry in records.get("data", []):
        if entry.get("expiryDate") != target:
            continue
        strike = float(entry.get("strikePrice", 0))
        ce     = entry.get("CE", {})
        pe     = entry.get("PE", {})
        rows.append({
            "strike":    strike,
            "CE_OI":     int(ce.get("openInterest",         0)),
            "CE_chgOI":  int(ce.get("changeinOpenInterest", 0)),
            "CE_LTP":    float(ce.get("lastPrice",          0)),
            "CE_IV":     float(ce.get("impliedVolatility",  0)),
            "CE_Vol":    int(ce.get("totalTradedVolume",     0)),
            "PE_OI":     int(pe.get("openInterest",         0)),
            "PE_chgOI":  int(pe.get("changeinOpenInterest", 0)),
            "PE_LTP":    float(pe.get("lastPrice",          0)),
            "PE_IV":     float(pe.get("impliedVolatility",  0)),
            "PE_Vol":    int(pe.get("totalTradedVolume",     0)),
        })

    df = pd.DataFrame(rows).sort_values("strike").reset_index(drop=True) \
        if rows else pd.DataFrame()

    # An empty frame means the chain did not arrive, so every derived figure below is
    # unknown - not zero. The old `max(total_ce, 1)` divided by ONE when there was no
    # call OI, turning "no data" into a confident PCR of 0.000.
    total_ce = int(df["CE_OI"].sum()) if not df.empty else None
    total_pe = int(df["PE_OI"].sum()) if not df.empty else None
    pcr      = (round(total_pe / total_ce, 3)
                  if total_ce and total_pe is not None and total_ce > 0 else None)
    mp       = _calc_max_pain(df) if not df.empty else None

    return {
        "symbol":      symbol.upper(),
        "spot":        spot,
        "expiry":      target,
        "expiries":    expiries,
        "pcr":         pcr,
        "max_pain":    mp,
        "total_ce_oi": total_ce,
        "total_pe_oi": total_pe,
        "timestamp":   records.get("timestamp", datetime.now().strftime("%d-%b-%Y %H:%M")),
        "chain_df":    df,
        "error":       None,
    }


# ---------------------------------------------------------------------------
# Option A — NSE session
# ---------------------------------------------------------------------------

def _is_market_hours() -> bool:
    """True if current IST time is within NSE trading hours on a weekday."""
    try:
        import pytz
        from datetime import datetime as _dt
        ist = pytz.timezone("Asia/Kolkata")
        now = _dt.now(ist)
        if now.weekday() >= 5:          # Saturday=5, Sunday=6
            return False
        mins = now.hour * 60 + now.minute
        return (9 * 60 + 10) <= mins <= (15 * 60 + 35)
    except Exception as exc:
        logger.warning("Market hours check failed: %s — assuming open", exc)
        return True                     # assume open if pytz unavailable


# ---------------------------------------------------------------------------
# Option 0 (PRIMARY) — Dhan
# ---------------------------------------------------------------------------
# Dhan serves the chain OUTSIDE market hours; NSE returns {} (measured 1-Sep-2026 at
# 22:00: Dhan 57 KB with spot, OI and greeks, NSE empty from both of its routes). It is
# also authenticated rather than cookie-scraped, so there is no session to be refused,
# and it is already this project's primary source for market data.

_DHAN_MIN_GAP_S = 3.1          # Dhan allows 1 option-chain request / 3s and rejects the rest
_dhan_last_call = [0.0]
_dhan_expiry_cache: dict = {}


def _dhan_gate() -> None:
    """Sleep until Dhan's option-chain rate limit will accept another request.

    The bundle builder walks ~30 F&O names in a loop. Without this, most of them come
    back rejected and the symptom is indistinguishable from "not an F&O name".
    """
    import time
    wait = _DHAN_MIN_GAP_S - (time.time() - _dhan_last_call[0])
    if wait > 0:
        time.sleep(wait)
    _dhan_last_call[0] = time.time()


def _fetch_via_dhan(symbol: str, expiry_index: int) -> dict:
    """Fetch from Dhan and return NSE's dict shape, so callers need no changes."""
    import dhan_auth
    import dhan_ohlcv

    sym = symbol.upper()
    meta = dhan_ohlcv.get_security_meta(sym) or {}
    sid = meta.get("security_id")
    if not sid:
        raise ValueError(f"no Dhan security id for {sym}")
    seg = "IDX_I" if sym in _INDICES else "NSE_EQ"

    # Refuse BEFORE spending a rate-limited request. Dhan answers a cash-only name with
    # "Invalid SecurityId" after a full 3-second slot; the scrip master already on disk
    # knows the answer for free. Empty set = master unreadable, so ask Dhan rather than
    # declaring the whole board optionless.
    if seg == "NSE_EQ":
        fno = dhan_ohlcv.get_fno_underlyings()
        if fno and sym not in fno:
            raise ValueError(f"{sym} has no stock options (not in the F&O list)")

    cl = dhan_auth.get_dhan_client()

    # Expiries change monthly; one fetch per symbol per process keeps the request count
    # off the same 1-per-3s budget the chain call needs.
    key = (sym, seg)
    expiries = _dhan_expiry_cache.get(key)
    if expiries is None:
        _dhan_gate()
        el = cl.expiry_list(under_security_id=int(sid), under_exchange_segment=seg)
        node = (el or {}).get("data") or {}
        expiries = node.get("data") if isinstance(node, dict) else node
        # MUST BE A LIST. For a name with no F&O series Dhan answers status=failure with
        # data.data = {"813": "Invalid SecurityId"} - a DICT - and iterating a dict
        # yields its KEYS, so the old code produced ["813"] and then asked for the chain
        # at expiry "813". That still ended in "no options", but by accident, after
        # spending one of Dhan's 1-per-3s requests on a call that could never work.
        if (el or {}).get("status") != "success" or not isinstance(expiries, list):
            expiries = []
        expiries = [str(x) for x in expiries]
        _dhan_expiry_cache[key] = expiries
    if not expiries:
        raise ValueError(f"{sym} has no listed expiries (not an F&O name)")

    target = expiries[min(expiry_index, len(expiries) - 1)]
    # ONE RETRY, with a wider gap. Measured on a 23-name board walk: 21 succeeded and
    # TVSMOTOR and BAJFINANCE came back empty - both of which returned a full chain when
    # called on their own moments later. So the failure is Dhan shedding load under a
    # sustained loop, not bad data, and without a retry those names silently read
    # "no options" on the panel while genuinely having a live chain.
    # Only on the empty/raise path, so the normal case is unchanged.
    data = None
    for attempt in (0, 1):
        try:
            _dhan_gate()
            resp = cl.option_chain(under_security_id=int(sid),
                                    under_exchange_segment=seg, expiry=target)
            node = (resp or {}).get("data") or {}
            d = node.get("data") if isinstance(node, dict) else None
            if d and d.get("oc"):
                data = d
                break
        except Exception as exc:
            if attempt:
                raise
            logger.info("%s chain attempt 1 failed (%s) - retrying once", sym, exc)
        if not attempt:
            import time as _t
            _t.sleep(_DHAN_MIN_GAP_S)          # widen the gap before the second try
    if not data:
        raise ValueError(f"Dhan returned no chain for {sym} {target} after 2 attempts")

    spot = float(data.get("last_price") or 0)
    rows = []
    for k, leg in sorted((data.get("oc") or {}).items(), key=lambda kv: float(kv[0])):
        ce = leg.get("ce") or {}
        pe = leg.get("pe") or {}

        def _i(d, a, b=None):
            """oi_change is DERIVED here - Dhan gives oi and previous_oi, where NSE hands
            over changeinOpenInterest directly. Same column, different route."""
            try:
                v = float(d.get(a) or 0)
                return int(v - float(d.get(b) or 0)) if b else int(v)
            except (TypeError, ValueError):
                return 0

        rows.append({
            "strike":   float(k),
            "CE_OI":    _i(ce, "oi"),        "CE_chgOI": _i(ce, "oi", "previous_oi"),
            "CE_LTP":   float(ce.get("last_price") or 0),
            "CE_IV":    float(ce.get("implied_volatility") or 0),
            "CE_Vol":   _i(ce, "volume"),
            "PE_OI":    _i(pe, "oi"),        "PE_chgOI": _i(pe, "oi", "previous_oi"),
            "PE_LTP":   float(pe.get("last_price") or 0),
            "PE_IV":    float(pe.get("implied_volatility") or 0),
            "PE_Vol":   _i(pe, "volume"),
        })

    df = pd.DataFrame(rows)
    total_ce = int(df["CE_OI"].sum()) if not df.empty else None
    total_pe = int(df["PE_OI"].sum()) if not df.empty else None
    # None, not 0, on anything that could not be computed - these become drawn price
    # levels, and a max pain of 0 is a line below every stop that looks entirely real.
    return {
        "symbol": sym, "spot": spot or None, "expiry": target, "expiries": expiries,
        "pcr": (round(total_pe / total_ce, 3) if total_ce and total_pe is not None else None),
        "max_pain": (_calc_max_pain(df) if not df.empty else None),
        "total_ce_oi": total_ce, "total_pe_oi": total_pe,
        "timestamp": datetime.now().strftime("%d-%b-%Y %H:%M"),
        "chain_df": df, "error": None, "source": "dhan",
    }


def _fetch_via_session(symbol: str, expiry_index: int) -> dict:
    sess = _get_session()
    # NSE checks X-Requested-With to distinguish browser AJAX from direct hits
    api_headers = {**_HEADERS, "X-Requested-With": "XMLHttpRequest"}

    # Try the primary route, then the v3 route. The retry fires ONLY on empty-with-200:
    # an HTML body means the session cookie is not valid and a second URL cannot help,
    # and a non-200 raises before we get here. Empty-with-200 is the one failure where a
    # different route plausibly answers - it is the shape the retired indices endpoint
    # produced before it became a hard 404.
    data = None
    for variant in (0, 1):
        url = _api_url(symbol, variant)
        resp = sess.get(url, headers=api_headers, timeout=15)
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type", "")
        if "text/html" in ct:
            raise ValueError("NSE returned HTML instead of JSON — session cookie not valid")
        d = resp.json()
        if d:
            data = d
            break
        if variant == 0:
            logger.info("%s: %s returned {} — trying the v3 route", symbol, url)

    # Empty from BOTH routes is NSE gating the chain, which it does outside market hours.
    if not data:
        raise ValueError("NSE returned empty response ({}) from both routes")

    result = _parse_nse_json(data, expiry_index, symbol)
    result["source"] = "nse_session"
    return result


# ---------------------------------------------------------------------------
# Option B — nsepython fallback
# ---------------------------------------------------------------------------

def _fetch_via_nsepython(symbol: str, expiry_index: int) -> dict:
    from nsepython import nse_optionchain_scrapper  # type: ignore
    raw    = nse_optionchain_scrapper(symbol.upper())
    result = _parse_nse_json(raw, expiry_index, symbol)
    result["source"] = "nsepython"
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_option_chain(symbol: str = "NIFTY", expiry_index: int = 0) -> dict:
    """
    Fetch and parse the option chain for *symbol*.

    Parameters
    ----------
    symbol       : "NIFTY", "BANKNIFTY", "FINNIFTY", or any NSE equity ticker
    expiry_index : 0 = nearest expiry, 1 = next expiry, etc.

    Returns a result dict (see module docstring).
    Always returns a dict even on failure (check result["error"]).
    """
    # ── Fresh cache (< TTL) ──────────────────────────────────────────────────
    cached = _load_cache(symbol)
    if cached and cached.get("expiry_index_used") == expiry_index:
        logger.debug("Option chain for %s served from fresh cache", symbol)
        return cached

    result = None
    market_open = _is_market_hours()

    # ── Option 0 (PRIMARY): Dhan ─────────────────────────────────────────────
    # BEFORE the market-closed branch below, which returns stale cache and skips every
    # live fetch. That was right when NSE was the only source - NSE has nothing to give
    # after hours - but Dhan does (measured 1-Sep-2026 22:00: Dhan 57 KB, NSE {}), so
    # short-circuiting first would make the one working source unreachable for eighteen
    # hours a day. Authenticated, so there is no cookie to be refused either.
    try:
        result = _fetch_via_dhan(symbol, expiry_index)
        logger.info("Option chain for %s fetched via Dhan (%d rows)",
                    symbol, len(result.get("chain_df", [])))
        result["expiry_index_used"] = expiry_index
        _save_cache(symbol, result)
        return result
    except Exception as exc_d:
        logger.info("Dhan option chain unavailable for %s: %s", symbol, exc_d)

    # ── If market closed, serve stale cache rather than hitting NSE ──────────
    if not market_open and cached:
        cached["source"]         = "cache (market closed)"
        cached["_market_closed"] = True
        logger.info("Market closed — returning stale cache for %s", symbol)
        return cached

    # ── Option A: NSE session (curl_cffi → requests) ─────────────────────────
    try:
        result = _fetch_via_session(symbol, expiry_index)
        logger.info("Option chain for %s fetched via NSE session (%d rows)",
                    symbol, len(result.get("chain_df", [])))
    except Exception as exc_a:
        logger.warning("Option A (NSE session) failed for %s: %s", symbol, exc_a)

        # ── Option B: nsepython ──────────────────────────────────────────────
        try:
            result = _fetch_via_nsepython(symbol, expiry_index)
            logger.info("Option chain for %s fetched via nsepython (%d rows)",
                        symbol, len(result.get("chain_df", [])))
        except Exception as exc_b:
            logger.error("Option B (nsepython) also failed for %s: %s", symbol, exc_b)

            # ── All live fetches failed: determine reason ────────────────────
            if not market_open:
                err_msg = (
                    "NSE option chain is only published during market hours "
                    "(Mon–Fri 09:15–15:30 IST). No cached data available yet — "
                    "fetch during a trading session to populate the cache."
                )
            else:
                err_msg = (
                    f"Session A: {exc_a} | nsepython: {exc_b}. "
                    "Try: pip install curl_cffi  or  pip install nsepython"
                )

            result = {
                # None, NOT 0 - the same rule as the parse path. max_pain and the writer
                # strikes are DRAWN as price levels, so a zero here is a confident line
                # below every stop that looks exactly like a real one. Missing is not
                # zero, at every exit or at none.
                "symbol":         symbol.upper(),
                "spot":           None,
                "expiry":         "",
                "expiries":       [],
                "pcr":            None,
                "max_pain":       None,
                "total_ce_oi":    None,
                "total_pe_oi":    None,
                "timestamp":      "",
                "chain_df":       pd.DataFrame(),
                "source":         "failed",
                "error":          err_msg,
                "_market_closed": not market_open,
            }

    # 10 May 2026 fix: even when Option A or B returns "successfully" with
    # empty expiries (e.g. evening / weekend / Akamai degraded response),
    # fall back to last-good cache rather than surfacing the scary
    # "session cookie not accepted" error. Distinguishes "ran today, market
    # closed, no live data" from "session truly broken".
    if result is not None:
        result["expiry_index_used"] = expiry_index
        empty_data = (
            (result.get("error") and "no expiry dates" in str(result.get("error")).lower())
            or (not result.get("expiries"))
        )
        if empty_data:
            if cached:
                cached["source"]         = "cache (live fetch returned empty)"
                cached["_market_closed"] = not market_open
                cached["expiry_index_used"] = expiry_index
                logger.info(
                    "Live fetch returned empty for %s — serving last-good "
                    "cache (market_open=%s)", symbol, market_open
                )
                return cached
            # No cache + empty live = explicit off-hours / cold-start message
            result["error"] = (
                "NSE returned no option chain data. "
                + ("Markets are CLOSED (Mon–Fri 09:15–15:30 IST) — "
                   "open this tab during a trading session to populate the "
                   "cache; subsequent off-hours visits will show the last "
                   "snapshot."
                   if not market_open
                   else "Live fetch returned empty even though market should "
                        "be open. Try refreshing in 30s. If persistent, the "
                        "Akamai session may need rebuilding: click Fetch Chain "
                        "again, or run `pip install --upgrade curl_cffi`.")
            )
            result["_market_closed"] = not market_open
            return result
        # Successful fetch with real data → cache it
        if result.get("error") is None:
            _save_cache(symbol, result)

    return result


def get_pcr(symbol: str = "NIFTY", expiry_index: int = 0) -> float:
    return get_option_chain(symbol, expiry_index).get("pcr", 0.0)


def get_max_pain(symbol: str = "NIFTY", expiry_index: int = 0) -> float:
    return get_option_chain(symbol, expiry_index).get("max_pain", 0.0)


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "NIFTY"
    print(f"Fetching option chain for {sym}…")
    r = get_option_chain(sym)
    if r["error"]:
        print(f"ERROR: {r['error']}")
    else:
        print(f"Source    : {r['source']}")
        print(f"Spot      : {r['spot']:,.2f}")
        print(f"Expiry    : {r['expiry']}")
        print(f"PCR       : {r['pcr']:.3f}")
        print(f"Max Pain  : {r['max_pain']:,.0f}")
        print(f"Total CE OI: {r['total_ce_oi']:,}")
        print(f"Total PE OI: {r['total_pe_oi']:,}")
        print(f"Timestamp : {r['timestamp']}")
        if not r["chain_df"].empty:
            print(f"\nTop 5 CE strikes by OI:")
            print(r["chain_df"].nlargest(5, "CE_OI")[["strike","CE_OI","CE_LTP","CE_IV"]].to_string(index=False))
