# nse_options_fetcher.py — NSE Options Chain Fetcher with Playwright cookie bridge
# Bypasses Akamai bot protection by using a real browser to get valid cookies,
# then transfers those to a requests session for fast subsequent API calls.
# Part of Weinstein Commander Web v4.0

import logging, time, json, requests
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)

_NSE_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com/option-chain",
    "X-Requested-With": "XMLHttpRequest",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}

# Module-level session cache
_session: Optional[requests.Session] = None
_session_ts: float = 0.0
_SESSION_TTL = 600  # re-warm every 10 minutes


def _build_session_playwright() -> Optional[requests.Session]:
    """
    Use Playwright (headless Chromium) to solve NSE's Akamai challenge,
    extract valid cookies, and return a requests.Session pre-loaded with them.
    Falls back to plain requests if Playwright is not available.
    """
    try:
        from playwright.sync_api import sync_playwright
        logger.info("Building NSE session via Playwright...")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=_NSE_HEADERS["User-Agent"],
                locale="en-US",
                viewport={"width": 1280, "height": 800},
            )
            page = ctx.new_page()
            # Step 1: visit homepage — Akamai sets challenge cookies here
            page.goto("https://www.nseindia.com", timeout=20000,
                      wait_until="domcontentloaded")
            time.sleep(2)
            # Step 2: visit option-chain page — picks up additional session cookies
            page.goto("https://www.nseindia.com/option-chain", timeout=20000,
                      wait_until="domcontentloaded")
            time.sleep(2)
            # Extract all cookies from the browser context
            pw_cookies = ctx.cookies()
            browser.close()

        # Build requests session with browser cookies
        sess = requests.Session()
        sess.headers.update(_NSE_HEADERS)
        for ck in pw_cookies:
            sess.cookies.set(ck["name"], ck["value"],
                             domain=ck.get("domain", ".nseindia.com"))
        logger.info("NSE Playwright session built — %d cookies", len(pw_cookies))
        return sess

    except ImportError:
        logger.warning("Playwright not installed — falling back to plain requests session")
        return _build_session_requests()
    except Exception as e:
        logger.warning("Playwright session failed (%s) — falling back", e)
        return _build_session_requests()


def _build_session_requests() -> requests.Session:
    """Plain requests session fallback (may fail Akamai challenge)."""
    sess = requests.Session()
    sess.headers.update(_NSE_HEADERS)
    try:
        sess.get("https://www.nseindia.com", timeout=12)
        time.sleep(1.0)
        sess.get("https://www.nseindia.com/option-chain", timeout=12)
        time.sleep(0.8)
    except Exception as e:
        logger.warning("Plain NSE session handshake: %s", e)
    return sess


def _get_session() -> requests.Session:
    """Return a valid NSE session, rebuilding if expired."""
    global _session, _session_ts
    if _session is None or (time.time() - _session_ts) > _SESSION_TTL:
        _session = _build_session_playwright()
        _session_ts = time.time()
    return _session


def force_refresh_session():
    """Force a new Playwright session on next call (call if getting empty data)."""
    global _session, _session_ts
    _session = None
    _session_ts = 0.0


def fetch_option_chain_raw(symbol: str = "NIFTY", max_retries: int = 2) -> Optional[Dict]:
    """
    Fetch raw NSE option chain JSON for an index symbol.
    Returns the full API response dict, or None on failure.
    """
    url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
    for attempt in range(max_retries):
        try:
            sess = _get_session()
            resp = sess.get(url, timeout=15)
            if resp.status_code == 200 and len(resp.content) > 100:
                data = resp.json()
                rows = data.get("records", {}).get("data", [])
                if rows:
                    logger.info("NSE %s chain fetched — %d rows", symbol, len(rows))
                    return data
                else:
                    logger.warning("NSE returned empty data for %s (attempt %d) — refreshing session", symbol, attempt + 1)
                    force_refresh_session()
            elif resp.status_code in (403, 429, 503):
                logger.warning("NSE HTTP %d for %s — refreshing session", resp.status_code, symbol)
                force_refresh_session()
                time.sleep(3 + attempt * 2)
            else:
                logger.warning("NSE HTTP %d, size=%d for %s", resp.status_code, len(resp.content), symbol)
                force_refresh_session()
        except Exception as e:
            logger.warning("fetch_option_chain_raw attempt %d: %s", attempt + 1, e)
            force_refresh_session()
            time.sleep(2)
    return None


def compute_max_pain(calls_oi: dict, puts_oi: dict) -> float:
    """Max Pain: strike where total writer loss is minimised."""
    strikes = sorted(set(calls_oi) | set(puts_oi))
    if not strikes:
        return 0.0
    pain = []
    for s in strikes:
        c = sum(max(s - k, 0) * oi for k, oi in calls_oi.items())
        p = sum(max(k - s, 0) * oi for k, oi in puts_oi.items())
        pain.append(c + p)
    return float(strikes[pain.index(min(pain))])


def parse_chain_summary(raw: Dict) -> Dict:
    """
    Parse raw NSE response into a summary dict for the dashboard.
    Returns: pcr_oi, pcr_vol, max_pain_strike, atm_iv, spot_price,
             total_call_oi, total_put_oi, strongest_call_strike,
             strongest_put_strike, expiry_dates
    """
    try:
        records  = raw.get("records", {})
        spot     = float(records.get("underlyingValue", 0))
        rows     = records.get("data", [])
        expiries = records.get("expiryDates", [])

        total_call_oi, total_put_oi = 0, 0
        total_call_vol, total_put_vol = 0, 0
        calls_oi_map, puts_oi_map = {}, {}
        calls_oi_by_strike, puts_oi_by_strike = {}, {}

        atm_strike = round(spot / 50) * 50  # round to nearest 50
        atm_iv = 0.0

        for row in rows:
            strike = float(row.get("strikePrice", 0))
            ce = row.get("CE", {})
            pe = row.get("PE", {})
            if ce:
                c_oi  = int(ce.get("openInterest", 0))
                c_vol = int(ce.get("totalTradedVolume", 0))
                total_call_oi  += c_oi
                total_call_vol += c_vol
                calls_oi_map[strike]       = c_oi
                calls_oi_by_strike[strike] = c_oi
                if abs(strike - atm_strike) < 100:
                    iv = float(ce.get("impliedVolatility", 0))
                    if iv > 0:
                        atm_iv = round(iv, 2)
            if pe:
                p_oi  = int(pe.get("openInterest", 0))
                p_vol = int(pe.get("totalTradedVolume", 0))
                total_put_oi  += p_oi
                total_put_vol += p_vol
                puts_oi_map[strike] = p_oi
                puts_oi_by_strike[strike] = p_oi

        pcr_oi  = round(total_put_oi  / total_call_oi,  2) if total_call_oi  else 0.0
        pcr_vol = round(total_put_vol / total_call_vol, 2) if total_call_vol else 0.0
        max_pain = compute_max_pain(calls_oi_map, puts_oi_map)

        strongest_call = max(calls_oi_by_strike, key=calls_oi_by_strike.get) if calls_oi_by_strike else 0
        strongest_put  = max(puts_oi_by_strike,  key=puts_oi_by_strike.get)  if puts_oi_by_strike  else 0

        return {
            "spot_price":            spot,
            "pcr_oi":                pcr_oi,
            "pcr_vol":               pcr_vol,
            "max_pain_strike":       max_pain,
            "atm_iv":                atm_iv,
            "total_call_oi":         total_call_oi,
            "total_put_oi":          total_put_oi,
            "strongest_call_strike": strongest_call,
            "strongest_put_strike":  strongest_put,
            "expiry_dates":          expiries,
            "fetched_at":            datetime.now().strftime("%H:%M:%S IST"),
        }
    except Exception as e:
        logger.error("parse_chain_summary: %s", e)
        return {}
