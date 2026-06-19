# market_data_hub.py — Centralized Market Data Hub for Commander Web v4.0
# Covers: Global indices, Commodities, Currencies, Bonds, India VIX, FII/DII,
#         NSE breadth, Economic calendar, Options (PCR/Max Pain), Corporate actions

# =============================================================================
# SECTION 1 — IMPORTS & CONFIG
# =============================================================================

import os
import json
import time
import logging
import warnings
import requests
from datetime import datetime, timedelta, date
from functools import lru_cache
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np
import yfinance as yf
from dotenv import load_dotenv

# C1: route OHLCV through the unified data_provider when available.
try:
    import data_provider as _dp
    USE_DATA_PROVIDER = True
except Exception:
    _dp = None
    USE_DATA_PROVIDER = False

load_dotenv()

logger = logging.getLogger(__name__)

# Suppress yfinance/urllib3 noise
warnings.filterwarnings("ignore", category=FutureWarning)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

# ---------------------------------------------------------------------------
# Global market configuration
# ---------------------------------------------------------------------------

GLOBAL_INDICES = {
    "GIFT Nifty":  {"ticker": "^NSEI",      "note": "Indian proxy (use GIFT City API for actual)"},
    "Nifty 50":    {"ticker": "^NSEI",       "note": "NSE benchmark"},
    "S&P 500":     {"ticker": "^GSPC",       "note": "US large cap"},
    "NASDAQ 100":  {"ticker": "^NDX",        "note": "US tech"},
    "Dow Jones":   {"ticker": "^DJI",        "note": "US industrials"},
    "US VIX":      {"ticker": "^VIX",        "note": "US fear gauge"},
    "India VIX":   {"ticker": "^INDIAVIX",   "note": "India fear gauge"},
    "Nikkei 225":  {"ticker": "^N225",       "note": "Japan"},
    "Hang Seng":   {"ticker": "^HSI",        "note": "Hong Kong / China proxy"},
    "DAX":         {"ticker": "^GDAXI",      "note": "Germany / Europe"},
    "FTSE 100":    {"ticker": "^FTSE",       "note": "UK"},
}

COMMODITIES = {
    "Brent Crude":   {"ticker": "BZ=F",    "unit": "USD/bbl",  "india_impact": "Inflation/CAD"},
    "Gold":          {"ticker": "GC=F",    "unit": "USD/oz",   "india_impact": "Safe haven"},
    "Silver":        {"ticker": "SI=F",    "unit": "USD/oz",   "india_impact": "Industrial"},
    "Copper":        {"ticker": "HG=F",    "unit": "USD/lb",   "india_impact": "Growth proxy"},
    "Natural Gas":   {"ticker": "NG=F",    "unit": "USD/MMBtu","india_impact": "Fertiliser"},
}

CURRENCIES = {
    "USD/INR":   {"ticker": "USDINR=X",  "note": "Direct India impact"},
    "DXY":       {"ticker": "DX-Y.NYB",  "note": "Dollar strength"},
    "EUR/USD":   {"ticker": "EURUSD=X",  "note": "Global risk proxy"},
    "USD/JPY":   {"ticker": "USDJPY=X",  "note": "Risk-on/off signal"},
    "GBP/USD":   {"ticker": "GBPUSD=X",  "note": "UK / global"},
}

BONDS = {
    "US 10Y Yield":    {"ticker": "^TNX",    "note": "Global liquidity"},
    "US 2Y Yield":     {"ticker": "^IRX",    "note": "Fed rate proxy"},
    "India 10Y":       {"ticker": "^INBMK",  "note": "Domestic liquidity"},  # may not be on yf
}

# Phase-2A: sourced from sectors.db.sector_meta where available. Hardcoded
# fallback retains the same set of indices for environments without sectors.db.
_NSE_SECTORS_FALLBACK = {
    "Bank Nifty":   "^NSEBANK",
    "Nifty IT":     "^CNXIT",
    "Nifty Pharma": "^CNXPHARMA",
    "Nifty Auto":   "^CNXAUTO",
    "Nifty FMCG":   "^CNXFMCG",
    "Nifty Metal":  "^CNXMETAL",
    "Nifty Energy": "^CNXENERGY",
    "Nifty Realty": "^CNXREALTY",
    "Nifty Infra":  "^CNXINFRA",
    "Nifty PSE":    "^CNXPSE",
    "Nifty Media":  "^CNXMEDIA",
}

def _load_nse_sectors_yf():
    try:
        import sector_lookup as _sl
        m = _sl.get_sector_yf_map(include_broad=False)
        return m if m else _NSE_SECTORS_FALLBACK
    except Exception:
        return _NSE_SECTORS_FALLBACK

NSE_SECTORS_YF = _load_nse_sectors_yf()

# Module-level NSE session (initialized on first use; may be curl_cffi or requests)
_nse_session: Optional[Any] = None

# Module-level TTL cache store
_cache: Dict[str, Dict[str, Any]] = {}

# Directory of this file (for loading JSON assets)
_HERE = os.path.dirname(os.path.abspath(__file__))

# =============================================================================
# SECTION 2 — CORE FETCH FUNCTION
# =============================================================================

def fetch_market_data(
    tickers_dict: Dict[str, Dict],
    period: str = "5d",
    interval: str = "1d",
) -> Dict[str, Dict]:
    """
    Download OHLCV data for a dict of {name: {ticker, ...}} entries via yfinance.

    Returns
    -------
    Dict keyed by name, each value::

        {
            "ltp": float,
            "prev_close": float,
            "change_pct": float,
            "day_high": float,
            "day_low": float,
            "week52_high": float,
            "week52_low": float,
            "pct_vs_52h": float,   # how far below 52-week high (negative = below)
            "series": pd.Series,   # Close series for sparklines
        }

    Missing / errored tickers get NaN values rather than crashing the caller.
    """
    ticker_map = {v["ticker"]: k for k, v in tickers_dict.items()}
    unique_tickers = list(ticker_map.keys())
    results: Dict[str, Dict] = {}

    _nan_entry = lambda: {
        "ltp": float("nan"), "prev_close": float("nan"), "change_pct": float("nan"),
        "day_high": float("nan"), "day_low": float("nan"),
        "week52_high": float("nan"), "week52_low": float("nan"),
        "pct_vs_52h": float("nan"), "series": pd.Series(dtype=float),
    }

    if not unique_tickers:
        return results

    # C1: data_provider is per-symbol cached, so for a fixed-set call like
    # this (10 indices, 5 commodities, 5 currencies) sequential cached fetches
    # beat a fresh batch on every page load. yfinance batch is the fallback.
    raw = None
    if USE_DATA_PROVIDER and _dp is not None:
        raw = {}
        for t in unique_tickers:
            try:
                df_t = _dp.fetch_ohlcv(t, period=period, interval=interval)
                if not df_t.empty:
                    raw[t] = df_t
            except Exception as exc:
                logger.debug("data_provider miss for %s: %s", t, exc)
    if not raw:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                raw = yf.download(
                    unique_tickers, period=period, interval=interval,
                    group_by="ticker", auto_adjust=True, progress=False, threads=True,
                )
        except Exception as exc:
            logger.error("yf.download failed: %s", exc)
            for name in tickers_dict:
                results[name] = _nan_entry()
            return results

    # Also grab 52-week data
    raw_52w = None
    if USE_DATA_PROVIDER and _dp is not None:
        raw_52w = {}
        for t in unique_tickers:
            try:
                df_t = _dp.fetch_ohlcv(t, period="1y", interval="1d")
                if not df_t.empty:
                    raw_52w[t] = df_t
            except Exception:
                continue
    if not raw_52w:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                raw_52w = yf.download(
                    unique_tickers, period="52wk", interval="1d",
                    group_by="ticker", auto_adjust=True, progress=False, threads=True,
                )
        except Exception as exc:
            logger.warning("52-week yf.download failed: %s", exc)
            raw_52w = pd.DataFrame()

    # `raw` and `raw_52w` may be either a yfinance MultiIndex DataFrame or a
    # dict of {ticker: DataFrame} (data_provider path). The helper unifies access.
    def _slice(container, ticker):
        if container is None:
            return pd.DataFrame()
        if isinstance(container, dict):
            return container.get(ticker, pd.DataFrame()).copy()
        # DataFrame path
        if hasattr(container, "empty") and container.empty:
            return pd.DataFrame()
        try:
            if len(unique_tickers) == 1:
                return container.copy()
            if hasattr(container.columns, "get_level_values") and \
                    ticker in container.columns.get_level_values(0):
                return container[ticker].copy()
        except Exception:
            pass
        return pd.DataFrame()

    for ticker, name in ticker_map.items():
        try:
            df     = _slice(raw,     ticker)
            df_52w = _slice(raw_52w, ticker)

            if not df.empty:
                df.dropna(how="all", inplace=True)
            if df.empty:
                results[name] = _nan_entry()
                continue

            ltp        = float(df["Close"].iloc[-1])
            prev_close = float(df["Close"].iloc[-2]) if len(df) >= 2 else ltp
            change_pct = ((ltp - prev_close) / prev_close * 100) if prev_close else float("nan")
            day_high   = float(df["High"].iloc[-1])
            day_low    = float(df["Low"].iloc[-1])

            if not df_52w.empty:
                df_52w.dropna(how="all", inplace=True)
                week52_high = float(df_52w["High"].max()) if "High" in df_52w.columns else float("nan")
                week52_low  = float(df_52w["Low"].min())  if "Low"  in df_52w.columns else float("nan")
            else:
                week52_high = float("nan")
                week52_low  = float("nan")

            pct_vs_52h = ((ltp - week52_high) / week52_high * 100) if week52_high else float("nan")

            results[name] = {
                "ltp":         ltp,
                "prev_close":  prev_close,
                "change_pct":  round(change_pct, 2),
                "day_high":    day_high,
                "day_low":     day_low,
                "week52_high": week52_high,
                "week52_low":  week52_low,
                "pct_vs_52h":  round(pct_vs_52h, 2),
                "series":      df["Close"].dropna(),
            }
        except Exception as exc:
            logger.warning("fetch_market_data: error processing %s (%s): %s", name, ticker, exc)
            results[name] = _nan_entry()

    return results

# =============================================================================
# SECTION 3 — SPECIALIZED FETCHERS
# =============================================================================

def _cached(key: str, ttl_seconds: int, fn):
    """
    Simple in-memory TTL cache usable outside Streamlit (e.g. background scheduler).

    Parameters
    ----------
    key         : unique cache key string
    ttl_seconds : how long to keep the cached result
    fn          : zero-argument callable that produces the data

    Returns the cached value if still fresh, otherwise calls fn() and stores result.
    """
    now = time.time()
    if key in _cache and (now - _cache[key]["ts"]) < ttl_seconds:
        return _cache[key]["data"]
    data = fn()
    _cache[key] = {"ts": now, "data": data}
    return data


def _get_nse_session():
    """
    Return a session pre-warmed with NSE cookies.

    Uses curl_cffi (Chrome TLS fingerprint) to bypass Akamai Bot Manager.
    Falls back to requests.Session if curl_cffi is not installed.
    Reuses the module-level session if already initialised.
    """
    global _nse_session
    if _nse_session is not None:
        return _nse_session

    try:
        from curl_cffi import requests as cffi_req
        session = cffi_req.Session(impersonate="chrome131")
        try:
            session.get("https://www.nseindia.com", timeout=12)
            time.sleep(0.8)
            logger.info("NSE session initialised via curl_cffi (chrome131)")
        except Exception as exc:
            logger.warning("NSE curl_cffi cookie handshake failed: %s", exc)
        _nse_session = session
        return _nse_session
    except ImportError:
        pass

    # Fallback to standard requests
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.nseindia.com/",
    })
    try:
        session.get("https://www.nseindia.com", timeout=10)
        time.sleep(0.5)
        logger.info("NSE session initialised via requests (no curl_cffi)")
    except Exception as exc:
        logger.warning("NSE requests cookie handshake failed: %s", exc)
    _nse_session = session
    return _nse_session


# ---------------------------------------------------------------------------
# 3a. Global overview
# ---------------------------------------------------------------------------

def fetch_global_overview(ttl: int = 300) -> Dict:
    """
    Fetch all GLOBAL_INDICES, COMMODITIES, CURRENCIES, and BONDS in one call.

    Returns
    -------
    dict with keys: "indices", "commodities", "currencies", "bonds", "fetched_at"
    Cached for `ttl` seconds (default 5 minutes).
    """
    def _fetch():
        ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        return {
            "indices":     fetch_market_data(GLOBAL_INDICES),
            "commodities": fetch_market_data(COMMODITIES),
            "currencies":  fetch_market_data(CURRENCIES),
            "bonds":       fetch_market_data(BONDS),
            "fetched_at":  ist_now.strftime("%H:%M:%S IST"),
        }
    return _cached("global_overview", ttl, _fetch)


# ---------------------------------------------------------------------------
# 3b. FII / DII data
# ---------------------------------------------------------------------------

_FII_HISTORY_FILE = os.path.join(_HERE, "fii_history.json")


def _fii_load_history() -> List[Dict]:
    """Load accumulated FII/DII history from local JSON file."""
    try:
        if os.path.exists(_FII_HISTORY_FILE):
            with open(_FII_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("FII history load failed: %s", exc)
    return []


def _fii_save_history(records: List[Dict]) -> None:
    """Persist FII/DII history (last 60 trading days) to local JSON file."""
    try:
        # Keep last 60 entries, deduplicate by date
        seen = {}
        for r in records:
            seen[str(r.get("date", ""))[:10]] = r
        kept = sorted(seen.values(), key=lambda x: str(x.get("date", "")))[-60:]
        with open(_FII_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(kept, f, indent=2, default=str)
    except Exception as exc:
        logger.warning("FII history save failed: %s", exc)


def fetch_fii_dii_data(ttl: int = 3600) -> pd.DataFrame:
    """
    Fetch FII/DII provisional trade data from NSE API.

    NSE's fiidiiTradeReact endpoint returns only today's data in this format:
        [{"category": "FII/FPI", "date": "17-Apr-2026",
          "buyValue": "16034.88", "sellValue": "15351.68", "netValue": "683.2"},
         {"category": "DII", ...}]

    We parse today's values and merge with a local rolling history file
    so callers get up to 30 days of data even though the API is single-day.

    Returns
    -------
    pd.DataFrame with columns:
        date, fii_net, dii_net, fii_buy, fii_sell, dii_buy, dii_sell
    Sorted ascending by date.  Returns empty DataFrame on total failure.
    """
    def _fetch():
        today_rec = {}
        try:
            session = _get_nse_session()
            url = "https://www.nseindia.com/api/fiidiiTradeReact"
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            raw = resp.json()

            # API returns one row per category: "FII/FPI" and "DII"
            fii_row = next((r for r in raw if "FII" in r.get("category", "").upper()), None)
            dii_row = next((r for r in raw if "DII" in r.get("category", "").upper()), None)

            def _parse_val(row, key):
                if row is None:
                    return 0.0
                return float(str(row.get(key, "0")).replace(",", "") or 0)

            if fii_row or dii_row:
                raw_date = (fii_row or dii_row).get("date", "")
                parsed_date = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")
                if pd.notna(parsed_date):
                    fii_buy  = _parse_val(fii_row, "buyValue")
                    fii_sell = _parse_val(fii_row, "sellValue")
                    dii_buy  = _parse_val(dii_row, "buyValue")
                    dii_sell = _parse_val(dii_row, "sellValue")
                    today_rec = {
                        "date":     parsed_date.strftime("%Y-%m-%d"),
                        "fii_buy":  fii_buy,
                        "fii_sell": fii_sell,
                        "dii_buy":  dii_buy,
                        "dii_sell": dii_sell,
                        "fii_net":  round(_parse_val(fii_row, "netValue"), 2),
                        "dii_net":  round(_parse_val(dii_row, "netValue"), 2),
                    }
                    logger.info(
                        "FII/DII today: FII net ₹%.0fCr, DII net ₹%.0fCr",
                        today_rec["fii_net"], today_rec["dii_net"],
                    )

        except Exception as exc:
            logger.error("fetch_fii_dii_data API call failed: %s", exc)

        # Merge today into rolling history
        history = _fii_load_history()
        if today_rec:
            history.append(today_rec)
        _fii_save_history(history)

        if not history:
            return pd.DataFrame()

        df = pd.DataFrame(history)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date").drop_duplicates(subset=["date"])
        cols = ["date", "fii_net", "dii_net", "fii_buy", "fii_sell", "dii_buy", "dii_sell"]
        for col in cols:
            if col not in df.columns:
                df[col] = 0.0
        return df[cols].tail(30).reset_index(drop=True)

    return _cached("fii_dii", ttl, _fetch)


# ---------------------------------------------------------------------------
# 3c. F&O ban list
# ---------------------------------------------------------------------------

def fetch_fno_ban_list(ttl: int = 86400) -> List[str]:
    """
    Fetch the NSE F&O securities-in-ban-period list.

    Tries today's CSV from NSE archives, then falls back to yesterday.
    Returns a list of banned symbol strings (e.g. ["AARTIIND", "CANBK"]).
    Returns empty list on failure.
    """
    def _fetch():
        for delta in range(3):  # try today, yesterday, day before
            try_date = date.today() - timedelta(days=delta)
            date_str = try_date.strftime("%d%m%Y")
            url = (
                f"https://archives.nseindia.com/web/sites/default/files/"
                f"content/fo_ban_{date_str}.csv"
            )
            try:
                resp = requests.get(url, timeout=10,
                                    headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200 and resp.text.strip():
                    lines = [l.strip() for l in resp.text.splitlines() if l.strip()]
                    # First line is header, subsequent lines are symbols
                    symbols = [l.split(",")[0].strip() for l in lines[1:] if l]
                    symbols = [s for s in symbols if s and s != "Symbol"]
                    logger.info("F&O ban list fetched for %s: %d symbols", try_date, len(symbols))
                    return symbols
            except Exception as exc:
                logger.warning("F&O ban list attempt %s failed: %s", date_str, exc)
        return []

    return _cached("fno_ban_list", ttl, _fetch)


# ---------------------------------------------------------------------------
# 3c.1. GIFT Nifty (NSE IFSC, Gift City) — canonical pre-open indicator
# ---------------------------------------------------------------------------

def fetch_mf_monthly_flows(ttl: int = 86400) -> Dict:
    """Fetch the latest published monthly MF flow data from AMFI.

    AMFI publishes a monthly MCR (Monthly Cumulative Report) as an XLS file
    at ``portal.amfiindia.com/spages/am{MMM}{YYYY}repo.xls`` (lowercase
    3-letter month, 4-digit year). The "Sub Total - II — Growth/Equity
    Oriented Schemes (Open-Ended)" row gives the canonical industry-wide
    Equity MF net inflow in ₹ Cr — the closest available daily-pipeline
    proxy for "DII MF" activity (AMFI/SEBI don't publish a daily MF feed).

    Walks back up to 4 months until a published file is found
    (April when called in early May, May once AMFI publishes ~mid-June).

    Returns::

        {
            "period":              "Apr-2026",
            "equity_net_inflow_cr": 38440.20,
            "equity_sales_cr":      70302.06,
            "equity_redemptions_cr": 31861.86,
            "equity_aum_cr":        3574352.13,
            "as_of":                "2026-04-30",
            "source":               "AMFI MCR Report",
            "url":                  "...",
        }

    Returns ``{}`` on total failure.
    """
    import urllib.request as _ur
    from io import BytesIO

    _MONTHS = ["jan","feb","mar","apr","may","jun",
                "jul","aug","sep","oct","nov","dec"]

    def _fetch():
        today = date.today()
        # Walk back from "last month" up to 4 months in case the file
        # for the most recent month hasn't been published yet (AMFI
        # typically releases month-M data 1-2 weeks into month M+1).
        for back in range(1, 6):
            yr = today.year
            m  = today.month - back
            while m <= 0:
                m += 12; yr -= 1
            mmm = _MONTHS[m - 1]
            url = f"https://portal.amfiindia.com/spages/am{mmm}{yr}repo.xls"
            try:
                req = _ur.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with _ur.urlopen(req, timeout=15) as resp:
                    data = resp.read()
                if not data or len(data) < 10000:
                    continue
                df = pd.read_excel(BytesIO(data), sheet_name="MCR_Report",
                                    engine="xlrd", header=None)
                # Find the Open-Ended Equity sub-total row. The descriptive
                # label "Sub Total - II..." actually lives in column 1 (col 0
                # is the Sr code "A", "I", "i", etc). Row offsets shift between
                # months but this label is stable.
                target_idx = None
                for i, row in df.iterrows():
                    # Concatenate first few cells to be robust against
                    # AMFI shuffling label/code columns between months.
                    cells = " ".join(str(c) for c in row.tolist()[:3])
                    if "sub total - ii" in cells.lower():
                        target_idx = i; break
                if target_idx is None:
                    continue
                r = df.iloc[target_idx].tolist()
                # Column layout (verified from Apr-2026 file):
                #   0 Sr | 1 label | 2 schemes | 3 folios | 4 sales
                #   5 redemptions | 6 net | 7 aum eop | 8 aum avg | 9/10 etc
                def _to_f(x):
                    try: return round(float(x), 2)
                    except Exception: return None
                period_dt = datetime(yr, m, 1)
                # Last day of that month
                next_m = period_dt.replace(day=28) + timedelta(days=4)
                last_day = (next_m - timedelta(days=next_m.day)).date()
                logger.info("AMFI monthly flows: parsed %s row (%s)",
                            mmm.upper(), yr)
                return {
                    "period":               period_dt.strftime("%b-%Y"),
                    "equity_sales_cr":      _to_f(r[4]),
                    "equity_redemptions_cr": _to_f(r[5]),
                    "equity_net_inflow_cr":  _to_f(r[6]),
                    "equity_aum_cr":         _to_f(r[7]),
                    "as_of":                last_day.isoformat(),
                    "source":               "AMFI MCR Report (Sub Total II — "
                                              "Growth/Equity Open-Ended Schemes)",
                    "url":                  url,
                }
            except Exception as exc:
                logger.warning("AMFI %s%d fetch failed: %s", mmm, yr, exc)
                continue
        return {}

    return _cached("mf_monthly_flows", ttl, _fetch)


def fetch_fii_dii_fno_participants(ttl: int = 3600) -> Dict:
    """Fetch NSE's daily participant-wise F&O activity (FII + DII split
    across index/stock futures and options).

    Source: ``archives.nseindia.com/content/nsccl/fao_participant_vol_{ddmmyyyy}.csv``
    Tries today, then walks back up to 3 sessions until a 200 is returned.
    The CSV ships in *contracts* (not crore notional) — a contract net of
    +X means the participant is long X contracts on the day. That's the
    canonical institutional read; converting to Cr requires lot sizes and
    settlement prices and is more lossy than the contract figure itself.

    Returns a dict shaped for Gemini consumption::

        {
            "as_of":       "YYYY-MM-DD",
            "fii": {
                "idx_fut_net":   +/-int,   # Index Futures net longs
                "stk_fut_net":   +/-int,   # Stock Futures net longs
                "idx_opt_net":   +/-int,   # Index Options net (calls long - puts long - calls short + puts short)
                "stk_opt_net":   +/-int,
                "total_long":    int,
                "total_short":   int,
                "net":           +/-int,
                "bias":          "LONG" | "SHORT" | "FLAT",
            },
            "dii": { ...same shape... },
            "source": "NSE archive — fao_participant_vol",
        }

    Returns ``{}`` on total failure.
    """
    import csv as _csv
    from io import StringIO

    def _parse_row(headers, values):
        """Map a participant row into the net positions dict."""
        h = {k.strip(): i for i, k in enumerate(headers)}
        def _ival(col):
            try: return int(str(values[h[col]]).strip())
            except Exception: return 0
        idx_fut_long  = _ival("Future Index Long")
        idx_fut_short = _ival("Future Index Short")
        stk_fut_long  = _ival("Future Stock Long")
        stk_fut_short = _ival("Future Stock Short")
        # Options net = call_long + put_short - call_short - put_long
        # (i.e. directional long exposure: long calls and short puts add)
        idx_opt_net = (_ival("Option Index Call Long")
                        + _ival("Option Index Put Short")
                        - _ival("Option Index Call Short")
                        - _ival("Option Index Put Long"))
        stk_opt_net = (_ival("Option Stock Call Long")
                        + _ival("Option Stock Put Short")
                        - _ival("Option Stock Call Short")
                        - _ival("Option Stock Put Long"))
        total_long  = _ival("Total Long Contracts")
        total_short = _ival("Total Short Contracts")
        net = total_long - total_short
        bias = "LONG" if net > 0 else "SHORT" if net < 0 else "FLAT"
        return {
            "idx_fut_net": idx_fut_long - idx_fut_short,
            "stk_fut_net": stk_fut_long - stk_fut_short,
            "idx_opt_net": idx_opt_net,
            "stk_opt_net": stk_opt_net,
            "total_long":  total_long,
            "total_short": total_short,
            "net":         net,
            "bias":        bias,
        }

    def _fetch():
        session = _get_nse_session()
        for delta in range(4):
            try_date = date.today() - timedelta(days=delta)
            ds = try_date.strftime("%d%m%Y")
            url = (f"https://archives.nseindia.com/content/nsccl/"
                    f"fao_participant_vol_{ds}.csv")
            try:
                r = session.get(url, timeout=12)
                if r.status_code != 200 or len(r.text) < 200:
                    continue
                # The file has a quoted title line then a header row;
                # filter blank lines and parse with csv.reader.
                lines = [ln for ln in r.text.splitlines() if ln.strip()]
                # First non-title row should start with "Client Type"
                hdr_idx = next((i for i, ln in enumerate(lines)
                                 if ln.lower().startswith("client type")), None)
                if hdr_idx is None:
                    continue
                rdr = list(_csv.reader(StringIO("\n".join(lines[hdr_idx:]))))
                headers = rdr[0]
                rows = {row[0].strip(): row for row in rdr[1:] if row}
                fii_row = rows.get("FII"); dii_row = rows.get("DII")
                if not (fii_row and dii_row):
                    continue
                logger.info("FII/DII F&O participants fetched for %s", try_date)
                return {
                    "as_of":  try_date.strftime("%Y-%m-%d"),
                    "fii":    _parse_row(headers, fii_row),
                    "dii":    _parse_row(headers, dii_row),
                    "source": "NSE archive — fao_participant_vol",
                }
            except Exception as exc:
                logger.warning("fao_participant_vol %s failed: %s", ds, exc)
                continue
        return {}

    return _cached("fii_dii_fno_participants", ttl, _fetch)


def fetch_gift_nifty(ttl: int = 300) -> Dict:
    """Fetch the most recent GIFT Nifty session close + change %.

    Source: investing.com historical-data API (pair_id 8985). yfinance does
    not list a working GIFT Nifty symbol — SGXNIFTY is delisted, NIFTY_F1.NS
    returns 404, etc. — so we go direct.

    Returns a dict with keys: ``close, prev_close, change, change_pct,
    date, source``. All numeric fields are floats. Returns ``{}`` on failure.

    The pill on the Pre/Post-Market dashboard shows the most recent close
    against the prior close so the user has a continuous reading of overseas
    sentiment for the Nifty even outside cash-market hours.
    """
    import urllib.request as _ur

    def _fetch():
        try:
            today_iso = date.today().isoformat()
            start_iso = (date.today() - timedelta(days=12)).isoformat()
            url = (
                "https://api.investing.com/api/financialdata/historical/8985"
                f"?start-date={start_iso}&end-date={today_iso}"
                "&time-frame=Daily&add-missing-rows=false"
            )
            req = _ur.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 Chrome/131.0",
                "domain-id": "www",
                "Accept": "application/json",
            })
            with _ur.urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            rows = payload.get("data") or []
            if not rows:
                return {}
            # API returns newest-first
            latest = rows[0]
            prior  = rows[1] if len(rows) > 1 else None

            def _to_f(x):
                try: return float(str(x).replace(",", ""))
                except Exception: return 0.0

            close = _to_f(latest.get("last_close"))
            prev  = _to_f(prior.get("last_close")) if prior else 0.0
            chg   = round(close - prev, 2) if prev else 0.0
            pct   = round(chg / prev * 100, 2) if prev else _to_f(latest.get("change_precent"))
            return {
                "close":       round(close, 2),
                "prev_close":  round(prev, 2),
                "change":      chg,
                "change_pct":  pct,
                "date":        latest.get("rowDate", ""),
                "high":        _to_f(latest.get("last_max")),
                "low":         _to_f(latest.get("last_min")),
                "open":        _to_f(latest.get("last_open")),
                "source":      "investing.com (pair_id=8985)",
            }
        except Exception as exc:
            logger.warning("fetch_gift_nifty failed: %s", exc)
            return {}

    return _cached("gift_nifty", ttl, _fetch)


# ---------------------------------------------------------------------------
# 3d. NSE market breadth
# ---------------------------------------------------------------------------

# Fallback list of ~20 major NSE stocks if nifty500_symbols.json is absent
_FALLBACK_NSE_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "TITAN.NS",
    "BAJFINANCE.NS", "WIPRO.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "POWERGRID.NS",
]


def fetch_nse_breadth(ttl: int = 1800) -> Dict:
    """
    Compute market breadth metrics for Nifty 500 (or fallback list).

    Metrics returned
    ----------------
    above_sma50_pct, above_sma150_pct, above_sma200_pct,
    new_52w_high_count, new_52w_low_count,
    stage2_count  (price > SMA200 and SMA200 slope positive),
    advance_count, decline_count, total_stocks,
    calculated_at (ISO timestamp string)
    """
    def _fetch():
        symbols = load_nifty500_symbols()
        if not symbols:
            symbols = _FALLBACK_NSE_SYMBOLS
            logger.warning("Using fallback NSE symbol list (%d stocks)", len(symbols))

        metrics = {
            "above_sma50_pct": 0.0, "above_sma150_pct": 0.0, "above_sma200_pct": 0.0,
            "new_52w_high_count": 0, "new_52w_low_count": 0,
            "stage2_count": 0, "advance_count": 0, "decline_count": 0,
            "total_stocks": 0, "calculated_at": datetime.now().isoformat(),
        }

        # C1: data_provider in 50-symbol batches; falls back to one big yf call.
        raw = None
        if USE_DATA_PROVIDER and _dp is not None:
            raw = {}
            try:
                BATCH = 50
                for i in range(0, len(symbols), BATCH):
                    chunk = symbols[i:i + BATCH]
                    bd = _dp.fetch_batch_ohlcv(chunk, period="15mo", interval="1d")
                    for sym in chunk:
                        clean = _dp.clean_symbol(sym)
                        if clean in bd:
                            raw[sym] = bd[clean]
            except Exception as exc:
                logger.warning("data_provider breadth fetch failed: %s — yf fallback", exc)
                raw = None
        if not raw:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    # Use 15 months of DAILY data so rolling(50/150/200) have enough bars.
                    # 6-month weekly data (~26 bars) made all SMA50+ calculations NaN.
                    raw = yf.download(
                        symbols, period="15mo", interval="1d",
                        group_by="ticker", auto_adjust=True,
                        progress=False, threads=True,
                    )
            except Exception as exc:
                logger.error("fetch_nse_breadth download failed: %s", exc)
                return metrics

        above_50, above_150, above_200 = 0, 0, 0
        new_high, new_low = 0, 0
        stage2, adv, dec = 0, 0, 0
        valid = 0

        for sym in symbols:
            try:
                # raw can be either a yf MultiIndex DataFrame or a dict
                if isinstance(raw, dict):
                    df = raw.get(sym, pd.DataFrame()).copy()
                else:
                    df = (raw[sym].copy() if len(symbols) > 1 else raw.copy())
                if df.empty or "Close" not in df.columns:
                    continue
                df = df[["Close"]].dropna()
                if len(df) < 10:
                    continue

                close = df["Close"]
                ltp = close.iloc[-1]
                prev = close.iloc[-2] if len(close) >= 2 else ltp

                # Daily SMAs — standard Weinstein methodology
                sma50  = close.rolling(50).mean().iloc[-1]  if len(close) >= 50  else float("nan")
                sma150 = close.rolling(150).mean().iloc[-1] if len(close) >= 150 else float("nan")
                sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else float("nan")
                # B7 fix: 5-day slope (was 1-day). 1-day SMA200 changes are
                # dominated by the bar dropping out of the window — too noisy
                # to call a "rising" trend. 5 trading days ≈ 1 week, matching
                # the SMA-slope window used in the breadth_engine sector view.
                sma200_prev = close.rolling(200).mean().iloc[-6] if len(close) >= 206 else float("nan")

                # 52-week high/low: 252 trading days ≈ 52 calendar weeks
                hi_52w = close.tail(252).max()
                lo_52w = close.tail(252).min()

                valid += 1
                if not np.isnan(sma50)  and ltp > sma50:  above_50 += 1
                if not np.isnan(sma150) and ltp > sma150: above_150 += 1
                if not np.isnan(sma200) and ltp > sma200: above_200 += 1
                if ltp >= hi_52w: new_high += 1
                if ltp <= lo_52w: new_low += 1
                # Stage 2: above rising SMA200 (5-day slope, B7).
                if (not np.isnan(sma200) and not np.isnan(sma200_prev)
                        and ltp > sma200 and sma200 > sma200_prev):
                    stage2 += 1
                if ltp > prev: adv += 1
                elif ltp < prev: dec += 1
            except Exception as exc:
                logger.debug("Breadth calc skipped ticker: %s", exc)
                continue

        if valid:
            metrics.update({
                "above_sma50_pct":   round(above_50  / valid * 100, 1),
                "above_sma150_pct":  round(above_150 / valid * 100, 1),
                "above_sma200_pct":  round(above_200 / valid * 100, 1),
                "new_52w_high_count": new_high,
                "new_52w_low_count":  new_low,
                "stage2_count":       stage2,
                "stage2_pct":         round(stage2 / valid * 100, 1),
                "advance_count":      adv,
                "decline_count":      dec,
                "total_stocks":       valid,
            })
        return metrics

    return _cached("nse_breadth", ttl, _fetch)


# ---------------------------------------------------------------------------
# 3e-2. NSE sector performance (EOD change % for all major sectors)
# ---------------------------------------------------------------------------

def fetch_sector_performance(ttl: int = 1800) -> List[Dict]:
    """
    Fetch today's performance for all NSE sector indices via yfinance.

    Returns
    -------
    List of dicts sorted by change_pct descending (best sector first):
        [{"sector": str, "close": float, "change_pct": float, "ticker": str}, ...]
    Returns empty list on failure.
    """
    def _fetch():
        results = []
        tickers_list = list(NSE_SECTORS_YF.values())
        names_list   = list(NSE_SECTORS_YF.keys())
        # C1: per-sector parquet cache. 14 sectors × 1 cached read beats one
        # batch yf call when most sectors haven't moved cache buckets.
        raw = None
        if USE_DATA_PROVIDER and _dp is not None:
            raw = {}
            for t in tickers_list:
                try:
                    df_t = _dp.fetch_ohlcv(t, period="5d", interval="1d")
                    if not df_t.empty:
                        raw[t] = df_t
                except Exception:
                    continue
        if not raw:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    raw = yf.download(
                        tickers_list, period="2d", interval="1d",
                        group_by="ticker", auto_adjust=True,
                        progress=False, threads=True,
                    )
            except Exception as exc:
                logger.error("fetch_sector_performance download failed: %s", exc)
                return results

        for name, ticker in zip(names_list, tickers_list):
            try:
                if isinstance(raw, dict):
                    df = raw.get(ticker, pd.DataFrame()).copy()
                else:
                    df = (raw[ticker].copy() if len(tickers_list) > 1 else raw.copy())
                if df.empty:
                    continue
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = df[["Close"]].dropna()
                if len(df) >= 2:
                    close = round(float(df["Close"].iloc[-1]), 2)
                    prev  = round(float(df["Close"].iloc[-2]), 2)
                    chg_pct = round((close - prev) / prev * 100, 2) if prev else 0.0
                    results.append({
                        "sector":     name,
                        "ticker":     ticker,
                        "close":      close,
                        "change_pct": chg_pct,
                    })
            except Exception:
                continue

        # Sort best to worst
        results.sort(key=lambda x: x["change_pct"], reverse=True)
        logger.info("Sector performance fetched: %d sectors", len(results))
        return results

    return _cached("sector_performance", ttl, _fetch)


# ---------------------------------------------------------------------------
# 3e. Economic calendar (hardcoded / semi-dynamic)
# ---------------------------------------------------------------------------

_CALENDAR_PATH = os.path.join(_HERE, "economic_calendar.json")


def get_economic_calendar_status() -> Dict:
    """Return file metadata for the dashboard so it can flag staleness.

    {"exists": bool, "last_updated": "YYYY-MM-DD", "age_days": int|None,
     "stale": bool, "event_count": int, "future_count": int, "path": str}
    """
    info = {"exists": False, "last_updated": None, "age_days": None,
             "stale": True, "event_count": 0, "future_count": 0,
             "path": _CALENDAR_PATH}
    if not os.path.exists(_CALENDAR_PATH):
        return info
    info["exists"] = True
    try:
        with open(_CALENDAR_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        events = data.get("events", []) or []
        info["event_count"] = len(events)
        today_iso = date.today().isoformat()
        info["future_count"] = sum(1 for e in events
                                     if str(e.get("date", "")) >= today_iso)
        last_updated = data.get("last_updated")
        info["last_updated"] = last_updated
        if last_updated:
            try:
                age = (date.today() - date.fromisoformat(last_updated)).days
                info["age_days"] = age
                info["stale"]    = age > 30
            except Exception:
                info["stale"] = True
        else:
            info["stale"] = True
    except Exception as e:
        logger.warning("economic_calendar.json parse failed: %s", e)
    return info


def fetch_economic_calendar(ttl: int = 86400) -> List[Dict]:
    """
    Read user-maintained economic events from ``economic_calendar.json``.

    B13 fix: previous version generated approximate dates (e.g. "RBI MPC
    on the 7th of every Feb/Apr/Jun…") that were off by days from real
    schedules. The dashboard called this a calendar but the data was
    fabricated. Now reads from a single user-maintained JSON file.

    Each event is a dict::

        {
            "date":       "YYYY-MM-DD",
            "event":      str,
            "importance": "HIGH" | "MEDIUM" | "LOW",
            "previous":   str,
            "forecast":   str,
            "actual":     str,
            "source":     str,
        }

    Returns an empty list if the file is missing or unreadable.
    The dashboard separately surfaces ``get_economic_calendar_status()`` so
    the user sees a stale-file warning when ``last_updated`` is >30 days old.
    """
    def _fetch():
        if not os.path.exists(_CALENDAR_PATH):
            logger.warning(
                "%s missing — economic calendar empty until you create it. "
                "See the bundled template (`economic_calendar.json`) or run "
                "`market_data_hub.seed_economic_calendar()`.",
                os.path.basename(_CALENDAR_PATH),
            )
            return []
        try:
            with open(_CALENDAR_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error("economic_calendar.json read failed: %s", e)
            return []
        events = data.get("events", []) or []
        # Only keep events with a parseable ISO date
        clean = []
        for e in events:
            try:
                d = str(e.get("date", "")).strip()
                if not d:
                    continue
                date.fromisoformat(d)  # validate
                clean.append({
                    "date":       d,
                    "event":      str(e.get("event", "")),
                    "importance": str(e.get("importance", "LOW")).upper(),
                    "previous":   str(e.get("previous", "") or ""),
                    "forecast":   str(e.get("forecast", "") or ""),
                    "actual":     str(e.get("actual", "") or ""),
                    "source":     str(e.get("source", "") or ""),
                })
            except Exception:
                continue
        clean.sort(key=lambda x: x["date"])
        return clean

    return _cached("economic_calendar", ttl, _fetch)


def refresh_calendar_from_investing(days_ahead: int = 14) -> Dict:
    """Pull India economic events from investing.com and rewrite
    ``economic_calendar.json``.

    The calendar file was previously user-maintained, which is why the
    "Refresh Now" button never advanced the `last_updated` date and the
    Previous / Forecast / Actual columns stayed blank — there was no fetch
    logic, just a JSON read. This function fills that gap.

    Source: investing.com's AJAX endpoint
    ``/economic-calendar/Service/getCalendarFilteredData`` (country[]=14 for
    India, timeZone=8 for IST). Importance is mapped from the ``bull{1-3}``
    sentiment icon: 1=LOW, 2=MEDIUM, 3=HIGH. Previous / forecast / actual
    are scraped from the row cells when populated.

    Returns a dict with ``count`` (events written), ``path`` (file path),
    and ``error`` (set on failure).
    """
    import urllib.request as _ur
    import urllib.parse as _up
    import re as _re
    import html as _html

    try:
        today_iso = date.today().isoformat()
        end_iso   = (date.today() + timedelta(days=days_ahead)).isoformat()
        body = _up.urlencode({
            "country[]":      "14",       # India
            "dateFrom":       today_iso,
            "dateTo":         end_iso,
            "timeZone":       "8",        # GMT+5:30 (IST)
            "currentTab":     "custom",
            "submitFilters":  "1",
            "limit_from":     "0",
        }, doseq=True).encode("utf-8")
        req = _ur.Request(
            "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData",
            data=body,
            headers={
                "User-Agent":        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                      "AppleWebKit/537.36 Chrome/131.0",
                "X-Requested-With":  "XMLHttpRequest",
                "Accept":            "application/json, text/plain, */*",
                "Origin":            "https://www.investing.com",
                "Referer":           "https://www.investing.com/economic-calendar/",
                "Content-Type":      "application/x-www-form-urlencoded",
            },
        )
        with _ur.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        html_data = payload.get("data", "") or ""

        rows = _re.findall(
            r'<tr id="eventRowId_(\d+)"[^>]*data-event-datetime="([^"]+)"[^>]*>(.*?)</tr>',
            html_data, _re.DOTALL,
        )

        events: List[Dict] = []
        _IMP_MAP = {"1": "LOW", "2": "MEDIUM", "3": "HIGH"}
        for _rid, _dttm, _body in rows:
            try:
                _date_part = _dttm.split(" ")[0].replace("/", "-")
                _ev_m   = _re.search(r'>([^<]+)</a>', _body)
                _bull_m = _re.search(r'data-img_key="bull(\d+)"', _body)
                _cells  = _re.findall(
                    r'<td[^>]*class="[^"]*(event_actual|event_forecast|event_previous)[^"]*"[^>]*>([^<]*)</td>',
                    _body,
                )
                cell_map = {k: _html.unescape(v or "").strip() for k, v in _cells}
                events.append({
                    "date":       _date_part,
                    "event":      _html.unescape(_ev_m.group(1)).strip() if _ev_m else "",
                    "importance": _IMP_MAP.get(_bull_m.group(1) if _bull_m else "1", "LOW"),
                    "previous":   cell_map.get("event_previous", ""),
                    "forecast":   cell_map.get("event_forecast", ""),
                    "actual":     cell_map.get("event_actual", ""),
                    "source":     "investing.com",
                })
            except Exception:
                continue

        out = {
            "_doc": ["Auto-refreshed from investing.com/economic-calendar (country=India, "
                      "timezone=IST). Run market_data_hub.refresh_calendar_from_investing() "
                      "to repull."],
            "last_updated": date.today().isoformat(),
            "events":       sorted(events, key=lambda e: e.get("date", "")),
        }
        with open(_CALENDAR_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)

        # Invalidate the in-memory cache so the next fetch_economic_calendar()
        # call reads from disk.
        _cache.pop("economic_calendar", None)

        logger.info("Calendar refresh: wrote %d India events to %s",
                    len(events), _CALENDAR_PATH)
        return {"count": len(events), "path": _CALENDAR_PATH, "error": None}

    except Exception as exc:
        logger.error("refresh_calendar_from_investing failed: %s", exc)
        return {"count": 0, "path": _CALENDAR_PATH, "error": str(exc)}


def seed_economic_calendar(force: bool = False) -> str:
    """Create a starter economic_calendar.json if absent.

    Returns the path written; raises FileExistsError if the file already
    exists and force=False.
    """
    if os.path.exists(_CALENDAR_PATH) and not force:
        raise FileExistsError(_CALENDAR_PATH)
    today = date.today()
    starter = {
        "_doc": [
            "User-maintained economic events. Update `last_updated` when "
            "you refresh; the dashboard warns when older than 30 days."
        ],
        "last_updated": today.isoformat(),
        "events": [],
    }
    with open(_CALENDAR_PATH, "w", encoding="utf-8") as f:
        json.dump(starter, f, indent=2)
    return _CALENDAR_PATH


# ---------------------------------------------------------------------------
# 3f. India VIX history
# ---------------------------------------------------------------------------

def fetch_india_vix_history(ttl: int = 3600) -> pd.DataFrame:
    """
    Fetch 1 year of India VIX daily data and compute a rolling percentile rank.

    Returns
    -------
    pd.DataFrame with columns:
        Date, Close, percentile_rank (0-100, where today sits vs past year)
    Returns empty DataFrame on failure.
    """
    def _fetch():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tkr = yf.Ticker("^INDIAVIX")
                df = tkr.history(period="1y", interval="1d", auto_adjust=True)

            if df.empty:
                logger.warning("India VIX returned empty data")
                return pd.DataFrame()

            df = df[["Close"]].copy()
            df.index = pd.to_datetime(df.index)
            df.index.name = "Date"
            df = df.dropna().reset_index()

            if not df.empty:
                latest = df["Close"].iloc[-1]
                pct_rank = float((df["Close"] <= latest).sum() / len(df) * 100)
                df["percentile_rank"] = df["Close"].rank(pct=True) * 100
                logger.info("India VIX: %.2f (%.0f percentile of 1Y range)", latest, pct_rank)
            return df

        except Exception as exc:
            logger.error("fetch_india_vix_history failed: %s", exc)
            return pd.DataFrame()

    return _cached("india_vix_history", ttl, _fetch)


# ---------------------------------------------------------------------------
# 3g. NSE options summary (PCR, Max Pain, ATM IV)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 3g. NSE Options — market-state-aware fetch with disk fallback
# ---------------------------------------------------------------------------

def _ist_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def is_nse_market_open(now: Optional[datetime] = None) -> bool:
    """True if NSE equity/options market is in live session (Mon–Fri, 09:15–15:30 IST).

    Conservative: does not account for NSE holidays. Used to gate live-data
    fetches that fail off-hours; a False holiday will simply force a cache-miss
    on a day the market is actually closed too — no harm done.
    """
    n = now or _ist_now()
    if n.weekday() >= 5:           # Sat=5, Sun=6
        return False
    minutes = n.hour * 60 + n.minute
    return 9 * 60 + 15 <= minutes <= 15 * 60 + 30


_OPTIONS_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "cache"
)


def _options_cache_path(symbol: str) -> str:
    os.makedirs(_OPTIONS_CACHE_DIR, exist_ok=True)
    return os.path.join(_OPTIONS_CACHE_DIR, f"options_summary_{symbol.upper()}.json")


def _save_options_cache(symbol: str, data: Dict) -> None:
    """Persist a successful options summary so off-hours visits can show last live snapshot."""
    try:
        path = _options_cache_path(symbol)
        # Add a wall-clock timestamp so the UI can show "as of YYYY-MM-DD HH:MM IST"
        payload = dict(data)
        payload["_cached_at_utc"] = datetime.utcnow().isoformat() + "Z"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
    except Exception as e:
        logger.debug("options cache save failed for %s: %s", symbol, e)


def _load_options_cache(symbol: str) -> Dict:
    """Read the last persisted options summary, or return {} if none exists."""
    try:
        path = _options_cache_path(symbol)
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.debug("options cache load failed for %s: %s", symbol, e)
        return {}


def fetch_nse_options_summary(symbol: str = "NIFTY", ttl: int = 300) -> Dict:
    """
    Fetch option chain from NSE and compute key derivatives metrics.

    Parameters
    ----------
    symbol : "NIFTY" | "BANKNIFTY" | "FINNIFTY" etc.
    ttl    : cache TTL in seconds (default 5 min — options data moves fast)

    Returns
    -------
    dict::

        {
            "pcr_oi": float,              # Put/Call ratio by open interest
            "pcr_vol": float,             # Put/Call ratio by volume
            "max_pain_strike": float,     # strike where combined OI pain is minimum
            "atm_iv": float,              # implied volatility at ATM strike
            "total_call_oi": int,
            "total_put_oi": int,
            "strongest_call_strike": float,  # strike with highest call OI
            "strongest_put_strike": float,   # strike with highest put OI
            "spot_price": float,
            "fetched_at": str,
        }

    Returns empty dict on failure.
    """
    cache_key = f"nse_options_{symbol.upper()}"

    # ── Off-hours short-circuit: skip the live call, return last-known cached snapshot ──
    # NSE options data only updates 09:15–15:30 IST Mon–Fri. On weekends, holidays,
    # or off-hours the live endpoint either 404s or returns empty payloads. Both cases
    # surfaced as scary errors before this fix. Now we return the last persisted
    # successful snapshot, tagged with a clear "_market_closed" + "_source" so the UI
    # can render an "as-of HH:MM IST on YYYY-MM-DD" badge instead of an error.
    if not is_nse_market_open():
        cached = _load_options_cache(symbol)
        if cached:
            cached["_market_closed"] = True
            cached["_source"] = "disk-cache (market closed)"
            return cached
        # No cache yet: still return a marker so UI can show "weekly waiting" message
        # instead of a generic error.
        return {"_market_closed": True, "_source": "no-cache",
                "_message": "NSE markets are closed and no cached snapshot exists yet. "
                            "First successful fetch during 09:15–15:30 IST will be cached."}

    def _fetch():
        try:
            session = _get_nse_session()
            url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol.upper()}"
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            records = data.get("records", {})
            spot_price = float(records.get("underlyingValue", 0) or 0)
            chain_data = records.get("data", [])

            # If the chain is empty (market closed / Akamai blocked), bail early
            # so callers receive {} and can show the correct fallback message
            # instead of metric cards full of zeros.
            if not chain_data or spot_price == 0:
                logger.warning(
                    "fetch_nse_options_summary(%s): empty chain_data or zero spot — "
                    "market closed or session blocked.", symbol
                )
                # Try to surface the last good cached snapshot rather than nothing
                cached = _load_options_cache(symbol)
                if cached:
                    cached["_market_closed"] = False
                    cached["_source"] = "disk-cache (live empty)"
                    return cached
                return {"_message": "NSE returned an empty option chain — likely Akamai bot-block."}

            calls, puts = {}, {}
            for item in chain_data:
                strike = float(item.get("strikePrice", 0))
                if "CE" in item:
                    ce = item["CE"]
                    calls[strike] = {
                        "oi":  int(ce.get("openInterest", 0)    or 0),
                        "vol": int(ce.get("totalTradedVolume", 0) or 0),
                        "iv":  float(ce.get("impliedVolatility", 0) or 0),
                    }
                if "PE" in item:
                    pe = item["PE"]
                    puts[strike] = {
                        "oi":  int(pe.get("openInterest", 0)    or 0),
                        "vol": int(pe.get("totalTradedVolume", 0) or 0),
                        "iv":  float(pe.get("impliedVolatility", 0) or 0),
                    }

            total_call_oi  = sum(v["oi"]  for v in calls.values())
            total_put_oi   = sum(v["oi"]  for v in puts.values())
            total_call_vol = sum(v["vol"] for v in calls.values())
            total_put_vol  = sum(v["vol"] for v in puts.values())

            pcr_oi  = round(total_put_oi  / total_call_oi,  2) if total_call_oi  else 0.0
            pcr_vol = round(total_put_vol / total_call_vol, 2) if total_call_vol else 0.0

            strongest_call = max(calls, key=lambda s: calls[s]["oi"], default=0.0)
            strongest_put  = max(puts,  key=lambda s: puts[s]["oi"],  default=0.0)

            # ATM strike = closest to spot
            all_strikes = sorted(set(calls) | set(puts))
            atm_strike = min(all_strikes, key=lambda s: abs(s - spot_price), default=0.0)
            atm_iv = 0.0
            if atm_strike in calls and atm_strike in puts:
                atm_iv = round((calls[atm_strike]["iv"] + puts[atm_strike]["iv"]) / 2, 2)
            elif atm_strike in calls:
                atm_iv = calls[atm_strike]["iv"]
            elif atm_strike in puts:
                atm_iv = puts[atm_strike]["iv"]

            # Max Pain: strike where total value of expiring options is minimum
            max_pain_strike = _compute_max_pain(calls, puts, all_strikes)

            ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
            result = {
                "pcr_oi":               pcr_oi,
                "pcr_vol":              pcr_vol,
                "max_pain_strike":      max_pain_strike,
                "atm_iv":               atm_iv,
                "total_call_oi":        total_call_oi,
                "total_put_oi":         total_put_oi,
                "strongest_call_strike": strongest_call,
                "strongest_put_strike":  strongest_put,
                "spot_price":           spot_price,
                "fetched_at":           ist_now.strftime("%H:%M:%S IST"),
                "_market_closed":       False,
                "_source":              "live",
            }
            # Persist for off-hours visits
            _save_options_cache(symbol, result)
            return result

        except Exception as exc:
            logger.warning("fetch_nse_options_summary(%s) failed: %s — falling back to disk cache",
                           symbol, exc)
            cached = _load_options_cache(symbol)
            if cached:
                cached["_market_closed"] = False
                cached["_source"] = f"disk-cache (live error: {type(exc).__name__})"
                return cached
            return {"_message": f"Live fetch failed and no cached snapshot exists: {exc}"}

    return _cached(cache_key, ttl, _fetch)


def _compute_max_pain(calls: Dict, puts: Dict, strikes: List[float]) -> float:
    """Return the max-pain strike (minimum total option value at expiry)."""
    min_pain, pain_strike = float("inf"), 0.0
    for exp_price in strikes:
        call_pain = sum(max(exp_price - s, 0) * calls[s]["oi"] for s in calls)
        put_pain  = sum(max(s - exp_price, 0) * puts[s]["oi"]  for s in puts)
        total = call_pain + put_pain
        if total < min_pain:
            min_pain, pain_strike = total, exp_price
    return pain_strike


# ---------------------------------------------------------------------------
# 3h. Bulk & block deals
# ---------------------------------------------------------------------------

def fetch_bulk_block_deals(ttl: int = 3600) -> pd.DataFrame:
    """
    Download today's NSE bulk-deals CSV (falls back to yesterday on failure).

    Returns
    -------
    pd.DataFrame with columns:
        date, symbol, client, buy_sell, quantity, price
    Returns empty DataFrame if unavailable.
    """
    def _nse_get(url, timeout=12):
        """Try curl_cffi first, fall back to requests."""
        try:
            from curl_cffi import requests as cffi_req
            return cffi_req.get(url, impersonate="chrome131", timeout=timeout)
        except ImportError:
            return requests.get(url, timeout=timeout,
                                headers={"User-Agent": "Mozilla/5.0"})

    def _fetch():
        for delta in range(3):
            try_date = date.today() - timedelta(days=delta)
            date_str = try_date.strftime("%d%m%Y")
            url = (
                f"https://archives.nseindia.com/web/sites/default/files/"
                f"content/data/bulk_deals_{date_str}.csv"
            )
            try:
                resp = _nse_get(url)
                if resp.status_code == 200 and len(resp.text.strip()) > 50:
                    from io import StringIO
                    df = pd.read_csv(StringIO(resp.text))
                    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
                    # Normalise to expected columns
                    col_map = {
                        "symbol":        "symbol",
                        "client_name":   "client",
                        "buy_/_sell":    "buy_sell",
                        "quantity_traded": "quantity",
                        "trade_price_/_wght._avg._price": "price",
                    }
                    df = df.rename(columns=col_map)
                    df["date"] = try_date.isoformat()
                    keep = [c for c in ["date","symbol","client","buy_sell","quantity","price"] if c in df.columns]
                    return df[keep].reset_index(drop=True)
            except Exception as exc:
                logger.warning("bulk_deals attempt %s: %s", date_str, exc)
        return pd.DataFrame()

    return _cached("bulk_block_deals", ttl, _fetch)


# ---------------------------------------------------------------------------
# 3i. Corporate actions
# ---------------------------------------------------------------------------

def fetch_corporate_actions(ttl: int = 3600) -> pd.DataFrame:
    """
    Fetch upcoming corporate actions (dividends, splits, bonuses, rights)
    from NSE for the next 30 days.

    Returns
    -------
    pd.DataFrame with columns from NSE API response (varies).
    Returns empty DataFrame on failure.
    """
    def _fetch():
        try:
            session = _get_nse_session()
            today_str = date.today().strftime("%d-%m-%Y")
            end_str   = (date.today() + timedelta(days=30)).strftime("%d-%m-%Y")
            url = (
                "https://www.nseindia.com/api/corporates-corporateActions"
                f"?index=equities&from_date={today_str}&to_date={end_str}"
            )
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            raw = resp.json()

            if not raw:
                return pd.DataFrame()

            df = pd.DataFrame(raw)
            # Normalise column names
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            logger.info("Corporate actions fetched: %d records", len(df))
            return df.reset_index(drop=True)

        except Exception as exc:
            logger.error("fetch_corporate_actions failed: %s", exc)
            return pd.DataFrame()

    return _cached("corporate_actions", ttl, _fetch)


# =============================================================================
# SECTION 4 — PRE-MARKET SNAPSHOT
# =============================================================================

def build_premarket_snapshot() -> Dict:
    """
    Build the complete pre-market intelligence snapshot.

    Aggregates global markets, FII/DII flows, India VIX, NIFTY options,
    economic calendar, and F&O ban list into a single dict ready for
    the PRE-MARKET dashboard page.

    Intended call time: 8:30 AM IST (or on-demand via Streamlit button).

    Returns
    -------
    dict with keys:
        generated_at, global, fii_dii, vix, options, calendar, ban_list
    """
    logger.info("Building pre-market snapshot...")

    # FII/DII — last 3 sessions as clean dicts (DataFrames don't JSON well)
    _fii_clean = []
    _fii_yesterday_cr = 0
    _dii_yesterday_cr = 0
    try:
        _fii_df = fetch_fii_dii_data()
        if not _fii_df.empty:
            for _, row in _fii_df.tail(3).iterrows():
                _fii_clean.append({
                    "date": str(row.get("date", ""))[:10],
                    "fii_net": round(float(row.get("fii_net", 0)), 2),
                    "dii_net": round(float(row.get("dii_net", 0)), 2),
                })
            _fii_yesterday_cr = round(float(_fii_df["fii_net"].iloc[-1]), 2)
            _dii_yesterday_cr = round(float(_fii_df["dii_net"].iloc[-1]), 2)
    except Exception as _fii_e:
        logger.warning("FII/DII for pre-market snapshot: %s", _fii_e)

    # VIX — extract scalars from the DataFrame fetch_india_vix_history() returns
    _vix_data = {}
    try:
        _vix_df = fetch_india_vix_history()
        if isinstance(_vix_df, pd.DataFrame) and not _vix_df.empty:
            _vix_now  = round(float(_vix_df["Close"].iloc[-1]), 2)
            _vix_prev = round(float(_vix_df["Close"].iloc[-2]), 2) if len(_vix_df) >= 2 else _vix_now
            _vix_pct  = round(float(_vix_df["percentile_rank"].iloc[-1]), 1)
            _vix_data = {
                "current_vix":    _vix_now,
                "vix_percentile": _vix_pct,
                "vix_1d_chg":     round(_vix_now - _vix_prev, 2),
                "vix_1d_chg_pct": round((_vix_now - _vix_prev) / _vix_prev * 100, 2) if _vix_prev else 0,
                "level": ("LOW" if _vix_now < 15 else "HIGH" if _vix_now > 20 else "MODERATE"),
            }
    except Exception as _vix_e:
        logger.warning("VIX for pre-market snapshot: %s", _vix_e)

    # India key indices — needed so the Gemini brief can write real
    # BankNifty / Nifty support+resistance levels instead of "N/A".
    # Lighter than the postmarket version: just Nifty + BankNifty, daily bars.
    _pm_indices: Dict = {}
    try:
        for _name, _ticker in (("Nifty 50", "^NSEI"), ("BankNifty", "^NSEBANK")):
            try:
                _t = yf.download(_ticker, period="3mo", interval="1d",
                                  progress=False, auto_adjust=True)
                if isinstance(_t.columns, pd.MultiIndex):
                    _t.columns = _t.columns.get_level_values(0)
                if len(_t) >= 2:
                    _c  = float(_t["Close"].iloc[-1])
                    _p  = float(_t["Close"].iloc[-2])
                    _h  = float(_t["High"].iloc[-1])
                    _l  = float(_t["Low"].iloc[-1])
                    _pv = round((_h + _l + _c) / 3, 2)
                    _pm_indices[_name] = {
                        "close":       round(_c, 2),
                        "prev_close":  round(_p, 2),
                        "change_pct":  round((_c - _p) / _p * 100, 2) if _p else 0,
                        "pivot":       _pv,
                        "support1":    round(2 * _pv - _h, 2),
                        "support2":    round(_pv - (_h - _l), 2),
                        "resistance1": round(2 * _pv - _l, 2),
                        "resistance2": round(_pv + (_h - _l), 2),
                        # 20-day average volume so the brief can frame an
                        # honest "volume confirmation level" instead of N/A.
                        "vol_avg20":   int(_t["Volume"].tail(20).mean())
                                          if "Volume" in _t and not _t["Volume"].dropna().empty else None,
                    }
            except Exception as _ie:
                logger.warning("pre-market index %s failed: %s", _ticker, _ie)
    except Exception as _ie2:
        logger.warning("pre-market india_indices block failed: %s", _ie2)

    snapshot = {
        "generated_at":       datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
        "global":             fetch_global_overview(),
        "gift_nifty":         fetch_gift_nifty(),
        "india_indices":      _pm_indices,
        "fii_dii_last3":      _fii_clean,
        "fii_prev_session_cr": _fii_yesterday_cr,
        "dii_prev_session_cr": _dii_yesterday_cr,
        "vix":                _vix_data,
        "sectors":            fetch_sector_performance(),
        "options":            fetch_nse_options_summary("NIFTY"),
        "calendar":           fetch_economic_calendar(),
        "ban_list":           fetch_fno_ban_list(),
    }
    logger.info("Pre-market snapshot complete.")
    return snapshot


# =============================================================================
# SECTION 5 — POST-MARKET SNAPSHOT
# =============================================================================

def build_postmarket_snapshot() -> Dict:
    """
    Build the complete post-market analysis snapshot.

    Aggregates EOD global markets, provisional FII/DII flows, NSE breadth,
    bulk/block deals, corporate actions, and key India index data.

    Intended call time: 4:30 PM IST (or on-demand via Streamlit button).

    Returns
    -------
    dict with Gemini-friendly scalar/list values (no raw DataFrames).
    """
    logger.info("Building post-market snapshot...")

    # ── India key indices via yfinance ────────────────────────────────────────
    _india_indices = {}
    _idx_map = {
        "Nifty 50":       "^NSEI",
        "BankNifty":      "^NSEBANK",
        "Nifty Midcap150":"NIFTYMIDCAP150.NS",
        "Nifty IT":       "^CNXIT",
        "India VIX":      "^INDIAVIX",
    }
    import yfinance as _yf
    for name, ticker in _idx_map.items():
        try:
            # Fetch 1 year of daily data to compute 50/200 DMA and 52W high/low
            _t = _yf.download(ticker, period="1y", interval="1d",
                               progress=False, auto_adjust=True)
            if isinstance(_t.columns, pd.MultiIndex):
                _t.columns = _t.columns.get_level_values(0)
            if len(_t) >= 2:
                _close  = float(_t["Close"].iloc[-1])
                _prev   = float(_t["Close"].iloc[-2])
                _chg    = _close - _prev
                _chg_pct = round((_chg / _prev) * 100, 2)
                _high   = float(_t["High"].iloc[-1])
                _low    = float(_t["Low"].iloc[-1])
                _india_indices[name] = {
                    "close": round(_close, 2), "prev_close": round(_prev, 2),
                    "change": round(_chg, 2),  "change_pct": _chg_pct,
                    "high": round(_high, 2),   "low": round(_low, 2),
                }
                # Pivot, support, resistance
                _pivot = round((_high + _low + _close) / 3, 2)
                _india_indices[name]["pivot"] = _pivot
                _india_indices[name]["support1"] = round(2 * _pivot - _high, 2)
                _india_indices[name]["resistance1"] = round(2 * _pivot - _low, 2)
                # Moving averages + volume (skip for VIX — not meaningful)
                if "VIX" not in name:
                    _c = _t["Close"].dropna()
                    _sma50  = round(float(_c.rolling(50).mean().iloc[-1]), 2)  if len(_c) >= 50  else None
                    _sma200 = round(float(_c.rolling(200).mean().iloc[-1]), 2) if len(_c) >= 200 else None
                    _hi52w  = round(float(_c.tail(252).max()), 2)
                    _lo52w  = round(float(_c.tail(252).min()), 2)
                    if _sma50:  _india_indices[name]["sma50"]  = _sma50
                    if _sma200: _india_indices[name]["sma200"] = _sma200
                    _india_indices[name]["hi_52w"] = _hi52w
                    _india_indices[name]["lo_52w"] = _lo52w
                    if _sma50:  _india_indices[name]["above_sma50"]  = _close > _sma50
                    if _sma200: _india_indices[name]["above_sma200"] = _close > _sma200
                    # Volume: today vs 20-day average
                    if "Volume" in _t.columns:
                        _vol = _t["Volume"].dropna()
                        if len(_vol) >= 1 and float(_vol.iloc[-1]) > 0:
                            _vol_today = int(_vol.iloc[-1])
                            _vol_avg20 = float(_vol.tail(20).mean())
                            _india_indices[name]["volume"]        = _vol_today
                            _india_indices[name]["volume_avg20d"] = int(_vol_avg20)
                            _india_indices[name]["volume_ratio"]  = round(_vol_today / _vol_avg20, 2) if _vol_avg20 > 0 else 1.0
        except Exception as _ie:
            logger.warning("Post-market index fetch %s: %s", ticker, _ie)

    # ── FII/DII — convert DataFrame to clean dict list ────────────────────────
    _fii_dii_clean = []
    try:
        _fii_df = fetch_fii_dii_data()
        if not _fii_df.empty:
            _last5 = _fii_df.tail(5)
            for _, row in _last5.iterrows():
                _fii_dii_clean.append({
                    "date":     str(row.get("date", ""))[:10],
                    "fii_net":  round(float(row.get("fii_net", 0)), 2),
                    "dii_net":  round(float(row.get("dii_net", 0)), 2),
                    "fii_buy":  round(float(row.get("fii_buy", 0)), 2),
                    "fii_sell": round(float(row.get("fii_sell", 0)), 2),
                    "dii_buy":  round(float(row.get("dii_buy", 0)), 2),
                    "dii_sell": round(float(row.get("dii_sell", 0)), 2),
                })
            # Cumulative FII last 5 days
            _fii_5d = round(float(_fii_df["fii_net"].tail(5).sum()), 2)
            _dii_5d = round(float(_fii_df["dii_net"].tail(5).sum()), 2)
        else:
            _fii_5d = 0; _dii_5d = 0
    except Exception as _fe:
        logger.warning("FII/DII fetch for post-market: %s", _fe)
        _fii_5d = 0; _dii_5d = 0

    # ── Basic breadth from yfinance (fast, no full N500 scan) ─────────────────
    _breadth_basic = fetch_nse_breadth()

    # ── Sector performance ────────────────────────────────────────────────────
    _sectors = fetch_sector_performance()

    # ── Bulk deals: convert DataFrame to list of dicts ────────────────────────
    _bulk_clean = []
    try:
        _bulk_df = fetch_bulk_block_deals()
        if isinstance(_bulk_df, pd.DataFrame) and not _bulk_df.empty:
            for _, row in _bulk_df.head(10).iterrows():
                _bulk_clean.append({k: str(v) for k, v in row.items()})
    except Exception as exc:
        logger.warning("Bulk deals fetch failed: %s", exc)

    # ── Corporate actions: convert DataFrame to list of dicts ─────────────────
    _corp_clean = []
    try:
        _corp_df = fetch_corporate_actions()
        if isinstance(_corp_df, pd.DataFrame) and not _corp_df.empty:
            keep_cols = [c for c in ["symbol", "series", "faceVal", "subject", "exDate",
                                     "recDate", "purpose"] if c in _corp_df.columns]
            for _, row in _corp_df[keep_cols].head(15).iterrows():
                _corp_clean.append({k: str(v) for k, v in row.items()})
    except Exception as exc:
        logger.warning("Corporate actions fetch failed: %s", exc)

    # ── McClellan oscillator — needed for the "Breadth Analysis" section
    # of the post-market summary. Reads from the on-disk state written by
    # breadth_engine; falls back to a live compute if state is missing/stale.
    _mcclellan = {}
    try:
        _msi_path = os.path.join(_HERE, "mcclellan_state.json")
        if os.path.exists(_msi_path):
            with open(_msi_path, "r", encoding="utf-8") as _mf:
                _state = json.load(_mf) or {}
            _hist = _state.get("history", []) or []
            if _hist:
                _last = _hist[-1]
                _mcclellan = {
                    "oscillator": round(float(_last.get("mco", 0.0)), 2),
                    "summation":  round(float(_last.get("msi", _state.get("msi", 0.0))), 2),
                    "as_of":      str(_last.get("date") or _state.get("last_date") or ""),
                    "source":     "mcclellan_state.json",
                }
            elif "msi" in _state:
                _mcclellan = {
                    "oscillator": 0.0,
                    "summation":  round(float(_state.get("msi", 0.0)), 2),
                    "as_of":      str(_state.get("last_date") or ""),
                    "source":     "mcclellan_state.json (no history)",
                }
    except Exception as _msi_e:
        logger.warning("mcclellan readback failed: %s", _msi_e)

    # ── Top movers — pull top gainer + top loser from Nifty 50 so the
    # "Key Movers" section of the summary stops printing "Leader: N/A".
    _top_movers = {}
    try:
        _n50 = [
            "RELIANCE.NS","TCS.NS","HDFCBANK.NS","BHARTIARTL.NS","ICICIBANK.NS",
            "INFY.NS","SBIN.NS","HINDUNILVR.NS","ITC.NS","LT.NS",
            "KOTAKBANK.NS","AXISBANK.NS","BAJFINANCE.NS","MARUTI.NS","ASIANPAINT.NS",
            "TITAN.NS","SUNPHARMA.NS","ULTRACEMCO.NS","WIPRO.NS","ONGC.NS",
            "NESTLEIND.NS","POWERGRID.NS","NTPC.NS","HCLTECH.NS","TECHM.NS",
            "TATASTEEL.NS","JSWSTEEL.NS","TATAMOTORS.NS","M&M.NS","ADANIENT.NS",
            "ADANIPORTS.NS","COALINDIA.NS","BAJAJFINSV.NS","INDUSINDBK.NS","DRREDDY.NS",
            "CIPLA.NS","DIVISLAB.NS","EICHERMOT.NS","HEROMOTOCO.NS","APOLLOHOSP.NS",
            "BRITANNIA.NS","BPCL.NS","HINDALCO.NS","SHREECEM.NS","TATACONSUM.NS",
            "GRASIM.NS","SBILIFE.NS","HDFCLIFE.NS","PIDILITIND.NS","BAJAJ-AUTO.NS",
        ]
        # Prefer the Dhan-first data_provider; yfinance is a loud fallback.
        _cl = pd.DataFrame()
        if USE_DATA_PROVIDER and _dp is not None:
            try:
                _bd = _dp.fetch_batch_ohlcv(_n50, period="5d", interval="1d")
                if _bd:
                    _cols = {}
                    for _k, _df in _bd.items():
                        if "Close" in _df.columns:
                            _key = _k if (_k.endswith(".NS") or _k.startswith("^")) else f"{_k}.NS"
                            _cols[_key] = _df["Close"]
                    if _cols:
                        _cl = pd.DataFrame(_cols)
            except Exception as _mov_e:
                logger.warning("Key Movers via data_provider failed: %s", _mov_e)
        if _cl.empty:
            logger.info("Key Movers served by yfinance FALLBACK (data_provider empty)")
            _mov_raw = yf.download(_n50, period="2d", interval="1d",
                                    progress=False, auto_adjust=True, threads=True)
            _cl = (_mov_raw["Close"] if isinstance(_mov_raw.columns, pd.MultiIndex)
                    else _mov_raw[["Close"]])
        _pairs = []
        for _s in _n50:
            try:
                _col = _cl[_s].dropna() if _s in _cl.columns else None
                if _col is not None and len(_col) >= 2:
                    _today = float(_col.iloc[-1]); _yest = float(_col.iloc[-2])
                    if _yest:
                        _pairs.append((_s.replace(".NS",""),
                                         round((_today - _yest) / _yest * 100, 2),
                                         round(_today, 2)))
            except Exception:
                continue
        if _pairs:
            _pairs.sort(key=lambda x: x[1], reverse=True)
            _gain = _pairs[0]
            _loss = _pairs[-1]
            _top_movers = {
                "leader":     {"symbol": _gain[0], "change_pct": _gain[1], "close": _gain[2]},
                "drag":       {"symbol": _loss[0], "change_pct": _loss[1], "close": _loss[2]},
                "top5_gain":  [{"symbol": p[0], "change_pct": p[1]} for p in _pairs[:5]],
                "top5_loss":  [{"symbol": p[0], "change_pct": p[1]} for p in _pairs[-5:][::-1]],
                "universe":   "Nifty 50",
            }
    except Exception as _mv_e:
        logger.warning("top_movers compute failed: %s", _mv_e)

    snapshot = {
        "generated_at":      datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
        "global":            fetch_global_overview(),
        "gift_nifty":        fetch_gift_nifty(),
        "india_indices":     _india_indices,
        "sectors":           _sectors,
        "fii_dii_last5":     _fii_dii_clean,
        "fii_5d_net_cr":     _fii_5d,
        "dii_5d_net_cr":     _dii_5d,
        "fii_dii_fno":       fetch_fii_dii_fno_participants(),
        "mf_monthly_flows":  fetch_mf_monthly_flows(),
        "breadth":           _breadth_basic,
        "mcclellan":         _mcclellan,
        "top_movers":        _top_movers,
        "bulk_deals":        _bulk_clean,
        "corporate_actions": _corp_clean,
    }
    logger.info("Post-market snapshot complete (%d india indices, %d FII rows).",
                len(_india_indices), len(_fii_dii_clean))
    return snapshot


# =============================================================================
# SECTION 6 — NIFTY 500 SYMBOLS FILE GENERATOR
# =============================================================================

def generate_nifty500_symbols_file() -> List[str]:
    """
    Download the official Nifty 500 constituent CSV from NSE archives,
    convert symbols to Yahoo Finance format (append '.NS'), and persist
    the list to ``nifty500_symbols.json`` in the same directory as this file.

    Returns
    -------
    List of Yahoo Finance ticker strings, e.g. ["RELIANCE.NS", "TCS.NS", ...]
    Falls back to an empty list on network/parse failure.
    """
    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

        from io import StringIO
        df = pd.read_csv(StringIO(resp.text))

        # NSE CSV has a column called "Symbol"
        if "Symbol" not in df.columns:
            # Try case-insensitive match
            col_map = {c.strip(): c for c in df.columns}
            sym_col = next((col_map[c] for c in col_map if c.lower() == "symbol"), None)
            if sym_col is None:
                logger.error("Nifty500 CSV: 'Symbol' column not found. Columns: %s", list(df.columns))
                return []
            df = df.rename(columns={sym_col: "Symbol"})

        symbols_yf = [s.strip() + ".NS" for s in df["Symbol"].dropna().tolist()]
        symbols_yf = [s for s in symbols_yf if len(s) > 3]  # filter blanks

        out_path = os.path.join(_HERE, "nifty500_symbols.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(symbols_yf, fh, indent=2)

        logger.info("Saved %d Nifty 500 symbols to %s", len(symbols_yf), out_path)
        return symbols_yf

    except Exception as exc:
        logger.error("generate_nifty500_symbols_file failed: %s", exc)
        return []


def load_nifty500_symbols() -> List[str]:
    """
    Load the Nifty 500 symbol list from the local JSON cache.

    If the JSON file does not exist (first run), calls
    ``generate_nifty500_symbols_file()`` to download and create it.

    Returns
    -------
    List of Yahoo Finance ticker strings (e.g. ["RELIANCE.NS", ...]).
    Returns empty list only when both the file is missing AND the download fails.
    """
    json_path = os.path.join(_HERE, "nifty500_symbols.json")
    if os.path.isfile(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as fh:
                symbols = json.load(fh)
            if symbols and isinstance(symbols, list):
                logger.info("Loaded %d symbols from %s", len(symbols), json_path)
                return symbols
        except Exception as exc:
            logger.warning("Failed to read %s: %s — regenerating.", json_path, exc)

    # File missing or corrupt — regenerate
    return generate_nifty500_symbols_file()


# =============================================================================
# STREAMLIT CACHE WRAPPERS
# =============================================================================
# When running inside a Streamlit app, wrap the fetchers with @st.cache_data
# so results are cached per-session and the TTL is honoured by Streamlit's
# own cache machinery.  Import these wrapped versions in your Streamlit pages.
#
# Usage in a page file:
#
#   from market_data_hub import (
#       st_fetch_global_overview,
#       st_fetch_fii_dii_data,
#       st_fetch_nse_breadth,
#       st_build_premarket_snapshot,
#       st_build_postmarket_snapshot,
#   )
#
# The `ttl` argument on @st.cache_data controls how long Streamlit caches
# the result before calling the function again.

try:
    import streamlit as st

    @st.cache_data(ttl=300, show_spinner=False)
    def st_fetch_global_overview():
        """Streamlit-cached wrapper for fetch_global_overview (5 min TTL)."""
        return fetch_global_overview(ttl=0)  # bypass in-memory cache; let Streamlit handle it

    @st.cache_data(ttl=3600, show_spinner=False)
    def st_fetch_fii_dii_data():
        """Streamlit-cached wrapper for fetch_fii_dii_data (1 hr TTL)."""
        return fetch_fii_dii_data(ttl=0)

    @st.cache_data(ttl=86400, show_spinner=False)
    def st_fetch_fno_ban_list():
        """Streamlit-cached wrapper for fetch_fno_ban_list (daily TTL)."""
        return fetch_fno_ban_list(ttl=0)

    @st.cache_data(ttl=1800, show_spinner=False)
    def st_fetch_nse_breadth():
        """Streamlit-cached wrapper for fetch_nse_breadth (30 min TTL)."""
        return fetch_nse_breadth(ttl=0)

    @st.cache_data(ttl=86400, show_spinner=False)
    def st_fetch_economic_calendar():
        """Streamlit-cached wrapper for fetch_economic_calendar (daily TTL)."""
        return fetch_economic_calendar(ttl=0)

    @st.cache_data(ttl=3600, show_spinner=False)
    def st_fetch_india_vix_history():
        """Streamlit-cached wrapper for fetch_india_vix_history (1 hr TTL)."""
        return fetch_india_vix_history(ttl=0)

    @st.cache_data(ttl=300, show_spinner=False)
    def st_fetch_nse_options_summary(symbol: str = "NIFTY"):
        """Streamlit-cached wrapper for fetch_nse_options_summary (5 min TTL)."""
        return fetch_nse_options_summary(symbol=symbol, ttl=0)

    @st.cache_data(ttl=3600, show_spinner=False)
    def st_fetch_bulk_block_deals():
        """Streamlit-cached wrapper for fetch_bulk_block_deals (1 hr TTL)."""
        return fetch_bulk_block_deals(ttl=0)

    @st.cache_data(ttl=3600, show_spinner=False)
    def st_fetch_corporate_actions():
        """Streamlit-cached wrapper for fetch_corporate_actions (1 hr TTL)."""
        return fetch_corporate_actions(ttl=0)

    @st.cache_data(ttl=300, show_spinner=False)
    def st_build_premarket_snapshot():
        """Streamlit-cached pre-market snapshot builder (5 min TTL)."""
        return build_premarket_snapshot()

    @st.cache_data(ttl=300, show_spinner=False)
    def st_build_postmarket_snapshot():
        """Streamlit-cached post-market snapshot builder (5 min TTL)."""
        return build_postmarket_snapshot()

except ImportError:
    # Streamlit not available (e.g. running as a standalone script or in a
    # background scheduler).  The raw functions are used directly.
    pass


# =============================================================================
# QUICK SELF-TEST  (python market_data_hub.py)
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print("--- Global Overview (first 2 keys) ---")
    overview = fetch_global_overview()
    for section, items in list(overview.items())[:2]:
        print(f"  [{section}]")
        if isinstance(items, dict):
            for name, vals in list(items.items())[:2]:
                if isinstance(vals, dict):
                    ltp = vals.get("ltp", "N/A")
                    chg = vals.get("change_pct", "N/A")
                    print(f"    {name}: {ltp}  ({chg}%)")
    print("\n--- FII/DII (last 3 rows) ---")
    fii = fetch_fii_dii_data()
    if not fii.empty:
        print(fii.tail(3).to_string(index=False))
    else:
        print("  No data returned.")
    print("\n--- India VIX (last row) ---")
    vix = fetch_india_vix_history()
    if not vix.empty:
        print(vix.tail(1).to_string(index=False))
    print("\n--- F&O Ban List ---")
    ban = fetch_fno_ban_list()
    print(" ", ban[:10] if ban else "None")
    print("\nDone.")
