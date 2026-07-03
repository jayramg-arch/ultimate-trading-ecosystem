"""
data_provider.py — Centralized rate-limited, on-disk-cached market data.

Single chokepoint for OHLCV access. Modules should import from here instead
of calling yfinance directly so a yfinance brownout degrades one place,
not a half-dozen.

C1 upgrade (in place):
  • Parquet cache when pyarrow is available; CSV fallback otherwise. Both
    formats are read-compatible so flipping between them is non-breaking.
  • auto_adjust=True is now the default (matches every existing consumer).
  • clean_symbol strips .NS / .BO so "HDFCBANK.NS" no longer becomes
    "HDFCBANK.NS.NS" downstream.
  • Replaced bare excepts with logged exceptions so cache failures are
    visible.
  • New helpers: stats(), clear_expired(), latest_close().

Cache layout:  data/market_cache/<sha1>.parquet|csv  +  <sha1>.meta.json

Public API:
  clean_symbol(symbol)              -> str
  fetch_ohlcv(symbol, period, interval, use_cache, auto_adjust) -> DataFrame
  fetch_batch_ohlcv(symbols, period, interval, ...)              -> dict
  get_ltp(symbol)  / latest_close(symbol)                        -> float
  stats()                                                         -> dict
  clear_cache()                                                   -> int
  clear_expired()                                                 -> int
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Optional

import pandas as pd
import yfinance as yf
from net_utils import is_internet_available

try:
    import dhan_ohlcv as _dhan
    DHAN_OK = True
except Exception as _de:
    _dhan = None
    DHAN_OK = False
    logging.getLogger(__name__).debug("dhan_ohlcv import failed: %s", _de)


# Secondary provider — nselib hits NSE directly. Currently the working
# India-data fallback (nsepython 2.97 fails to parse NSE's current response
# shape — KeyError 'data' on equity_history). We try nselib first, then
# nsepython as a tertiary attempt in case it gets fixed upstream.
try:
    from nselib import capital_market as _nselib_cm
    NSELIB_OK = True
except Exception:
    _nselib_cm = None
    NSELIB_OK = False

try:
    import nsepython as _nse
    NSEPY_OK = True
except Exception:
    _nse = None
    NSEPY_OK = False

logger = logging.getLogger(__name__)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
# nselib emits its own ERROR-level logs ("Resource not available for Price Volume Data")
# whenever NSE returns no data — but data_provider already handles this via fallback.
# Silence nselib's noisy ERROR logs so the user doesn't see scary tracebacks during
# the AI Brief workflow when NSE is just temporarily empty (weekends, off-hours,
# rate-limit, etc). Real failures still surface via our own logger.debug calls.
logging.getLogger("nselib").setLevel(logging.CRITICAL)
logging.getLogger("nselib.capital_market").setLevel(logging.CRITICAL)
logging.getLogger("nselib.capital_market.get_func").setLevel(logging.CRITICAL)

# ── CONFIGURATION ────────────────────────────────────────────────────────────
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "market_cache")
CACHE_TTL_INTRADAY = 900       # 15 minutes
CACHE_TTL_DAILY    = 900       # 15 minutes (reduced from 1 hour to support intraday stitching)
CACHE_TTL_WEEKLY   = 86400     # 24 hours
MAX_CALLS_PER_SECOND = 4

# Parquet preferred when available (smaller, faster, lossless dtypes)
try:
    import pyarrow  # noqa: F401
    _PARQUET_OK = True
except Exception:
    _PARQUET_OK = False
_CACHE_FORMAT = "parquet" if _PARQUET_OK else "csv"

_DHAN_SUFFIXES = ("-EQ", "-BE", "-SM", "-ST", "-BZ")

# ── FEED VISIBILITY (19 Jun 2026) ──────────────────────────────────────────
# Policy: keep the yfinance/nselib fallback but make it LOUD. Every fetch is
# tagged with the source it actually used, the active feed is announced once at
# startup, and a missing paid feed (Dhan OFF) is surfaced — never silent.
_LAST_SOURCE: dict = {}     # clean_symbol -> "dhan"|"cache"|"yfinance"|"nselib"|"nsepython"|"none"
_SOURCE_COUNTS: dict = {}   # source -> count for this process
_BANNER_SHOWN = False


def _record_source(symbol: str, source: str) -> None:
    try:
        _LAST_SOURCE[clean_symbol(symbol)] = source
    except Exception:
        _LAST_SOURCE[str(symbol)] = source
    _SOURCE_COUNTS[source] = _SOURCE_COUNTS.get(source, 0) + 1


def get_last_source(symbol: str) -> str:
    """Data source used for the most recent fetch of `symbol` (visibility)."""
    try:
        return _LAST_SOURCE.get(clean_symbol(symbol), "unknown")
    except Exception:
        return _LAST_SOURCE.get(str(symbol), "unknown")


def get_source_counts() -> dict:
    """Per-source fetch counts for this process (diagnostics / Data_Source stamps)."""
    return dict(_SOURCE_COUNTS)


def dhan_feed_live() -> bool:
    """True only if Dhan is importable AND its auth has not failed this process.

    `DHAN_OK` alone reflects *import* success, not *feed* health — an expired
    token leaves DHAN_OK True while every fetch silently falls to yfinance. This
    consults dhan_ohlcv's process-level `_AUTH_FAILED` flag so callers can report
    the truth.
    """
    if not DHAN_OK or _dhan is None:
        return False
    try:
        return not getattr(_dhan, "_AUTH_FAILED", False)
    except Exception:
        return True


def feed_status_banner() -> str:
    """One-line summary of which feeds are wired in this process.

    Dhan is reported as AUTH-FAILED (not ON) once its token/auth has failed this
    process — `DHAN_OK` only means the module imported, not that the paid feed is
    actually serving data.
    """
    if not DHAN_OK:
        dhan_state = "OFF"
    elif not dhan_feed_live():
        dhan_state = "AUTH-FAILED"
    else:
        dhan_state = "ON"
    return (f"Dhan={dhan_state} | "
            f"nselib={'ON' if NSELIB_OK else 'OFF'} | "
            f"nsepython={'ON' if NSEPY_OK else 'OFF'} | "
            f"cache={_CACHE_FORMAT}")


def _show_banner_once() -> None:
    global _BANNER_SHOWN
    if _BANNER_SHOWN:
        return
    _BANNER_SHOWN = True
    msg = "[data_provider] FEED: " + feed_status_banner()
    logger.info(msg)
    if not DHAN_OK:
        warn = ("[data_provider] [!] Dhan API NOT available -- running on "
                "yfinance/nselib FALLBACK data. The PAID feed is OFF; results "
                "may differ from live trading data.")
        logger.warning(warn)
        print(warn)
    else:
        print(msg)

# ── E10: PINNED DATE (replay / as-of mode) ────────────────────────────────────
# When set, every fetch_ohlcv result is sliced to bars on/before this date so
# the entire downstream indicator stack (SMAs, RSI, ATR, Mansfield, VCP) sees
# the world as it looked at the pin. Default None = live mode.
_PINNED_DATE: Optional[str] = None  # "YYYY-MM-DD" or None


def set_pinned_date(date_str: Optional[str]) -> None:
    """Globally pin the data view to bars on/before `date_str` (ISO YYYY-MM-DD).
    Pass None to return to live mode."""
    global _PINNED_DATE
    if date_str is None:
        _PINNED_DATE = None
        logger.info("data_provider: pinned_date cleared — live mode")
        return
    try:
        # Validate
        from datetime import date as _date
        _date.fromisoformat(date_str)
    except Exception as e:
        raise ValueError(f"pinned_date must be ISO YYYY-MM-DD: {e}")
    _PINNED_DATE = date_str
    logger.info("data_provider: pinned_date set to %s", date_str)


def get_pinned_date() -> Optional[str]:
    """Current pinned date or None."""
    return _PINNED_DATE


def _apply_pin(df: pd.DataFrame, pinned_date: Optional[str]) -> pd.DataFrame:
    """Slice the frame to bars on/before pinned_date. No-op if None or empty."""
    if df is None or df.empty:
        return df
    pin = pinned_date or _PINNED_DATE
    if not pin:
        return df
    try:
        if not isinstance(df.index, pd.DatetimeIndex):
            return df
        # Compare as tz-naive to avoid mismatches with parquet round-trip
        idx = df.index
        if idx.tz is not None:
            idx = idx.tz_localize(None)
            df = df.copy()
            df.index = idx
        return df.loc[:pin]
    except Exception:
        return df


def _is_cache_valid_for_pin(key: str, df: pd.DataFrame, pinned_date: Optional[str]) -> bool:
    """Check if the cached dataframe covers the required history before pinned_date.
    Returns False if it starts after the pinned date or has insufficient lookback,
    unless it was cached with a deep historical period like 10y or max."""
    if df is None or df.empty:
        return False
    pin = pinned_date or _PINNED_DATE
    if not pin:
        return True
    try:
        if not isinstance(df.index, pd.DatetimeIndex):
            return False
        pinned_dt = pd.to_datetime(pin)
        # Sibling index might have timezone, strip for comparison
        min_date = df.index[0]
        if min_date.tz is not None:
            min_date = min_date.tz_localize(None)
        
        # If the cached data starts after the pinned date, it has ZERO bars before the pin.
        if min_date >= pinned_dt:
            return False
            
        # Check lookback
        days_before = (pinned_dt - min_date).days
        if days_before >= 365:
            return True
            
        # If days_before < 365, check if the metadata period is a deep period
        # (which means it's an IPO / newly listed stock, and we downloaded the max available).
        _, _, meta_p = _data_paths(key)
        if os.path.exists(meta_p):
            with open(meta_p, "r", encoding="utf-8") as f:
                meta = json.load(f)
            cached_period = meta.get("period", "")
            if cached_period in ("10y", "max"):
                return True
        return False
    except Exception:
        return False


# ── RATE LIMITER ─────────────────────────────────────────────────────────────
_rate_lock = threading.Lock()
_last_call_time = 0.0


def _rate_limit() -> None:
    """Token-bucket-lite throttle to avoid Yahoo Finance burst limits."""
    global _last_call_time
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_call_time
        min_interval = 1.0 / MAX_CALLS_PER_SECOND
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_call_time = time.time()


# ── CACHE INTERNALS ──────────────────────────────────────────────────────────
def _ensure_cache_dir() -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_key(symbol: str, period: str, interval: str, auto_adjust: bool) -> str:
    """Different auto_adjust settings produce different prices → different keys."""
    raw = f"{symbol}|{period}|{interval}|adj={int(auto_adjust)}"
    return hashlib.sha1(raw.encode()).hexdigest()


def _ttl_for(period: str, interval: str) -> int:
    if interval in ("1m", "5m", "15m", "30m", "60m", "1h"):
        return CACHE_TTL_INTRADAY
    if interval == "1wk" or period in ("2y", "5y", "10y", "max", "3y"):
        return CACHE_TTL_WEEKLY
    return CACHE_TTL_DAILY


def _content_stale_for_live(df: Optional[pd.DataFrame], interval: str,
                            pinned_date: Optional[str]) -> bool:
    """True when a cached frame's CONTENT is too old to serve in live mode.

    Cache-poisoning guard (2026-07-03): freshness must be judged by the data's
    last bar, not the file's timestamp — a stale frame can carry a fresh
    cached_at (see the fallback-copy bug). Live mode only: pinned/replay runs
    legitimately read old frames and are exempt.
    """
    if pinned_date is not None or _PINNED_DATE is not None:
        return False
    if df is None or getattr(df, "empty", True):
        return False
    if interval not in ("1d", "1wk"):
        return False
    try:
        last = pd.Timestamp(df.index[-1])
        if last.tzinfo is not None:
            last = last.tz_localize(None)
        age_days = (pd.Timestamp.now().normalize() - last.normalize()).days
    except Exception:
        return False
    return age_days > (5 if interval == "1d" else 12)


def _data_paths(key: str) -> tuple[str, str, str]:
    """Returns (parquet_path, csv_path, meta_path) regardless of which exists."""
    return (
        os.path.join(CACHE_DIR, f"{key}.parquet"),
        os.path.join(CACHE_DIR, f"{key}.csv"),
        os.path.join(CACHE_DIR, f"{key}.meta.json"),
    )


def _read_cache(key: str, ignore_ttl: bool = False) -> Optional[pd.DataFrame]:
    """Return cached DataFrame if fresh; else None. Reads either format."""
    _ensure_cache_dir()
    parquet_p, csv_p, meta_p = _data_paths(key)
    if not os.path.exists(meta_p):
        return None
    try:
        with open(meta_p, "r", encoding="utf-8") as f:
            meta = json.load(f)
        cached_at = datetime.fromisoformat(meta.get("cached_at", "2000-01-01"))
        ttl = int(meta.get("ttl", CACHE_TTL_DAILY))
        if not ignore_ttl and (datetime.now() - cached_at).total_seconds() > ttl:
            if not is_internet_available():
                logger.warning("[data_provider] Offline: serving EXPIRED cache for %s (TTL was %ds)", key, ttl)
            else:
                return None
    except Exception as e:
        logger.debug("cache meta read failed for %s: %s", key, e)
        return None

    if os.path.exists(parquet_p):
        try:
            return pd.read_parquet(parquet_p)
        except Exception as e:
            logger.warning("parquet read failed (%s) — falling through to CSV", e)
    if os.path.exists(csv_p):
        try:
            return pd.read_csv(csv_p, index_col=0, parse_dates=True)
        except Exception as e:
            logger.warning("csv read failed for %s: %s", key, e)
    return None


def _write_cache(key: str, df: pd.DataFrame, period: str, interval: str,
                  auto_adjust: bool) -> None:
    _ensure_cache_dir()
    parquet_p, csv_p, meta_p = _data_paths(key)
    try:
        if _CACHE_FORMAT == "parquet":
            df.to_parquet(parquet_p)
            fmt = "parquet"
        else:
            df.to_csv(csv_p)
            fmt = "csv"
        meta = {
            "cached_at":   datetime.now().isoformat(timespec="seconds"),
            "ttl":         _ttl_for(period, interval),
            "period":      period,
            "interval":    interval,
            "auto_adjust": auto_adjust,
            "rows":        len(df),
            "format":      fmt,
        }
        with open(meta_p, "w", encoding="utf-8") as f:
            json.dump(meta, f)
    except Exception as e:
        logger.warning("cache write failed for %s: %s", key, e)


# ── SYMBOL NORMALIZATION ─────────────────────────────────────────────────────
def clean_symbol(symbol: str) -> str:
    """Standardize an input symbol for Yahoo Finance.

    Idempotent: 'RELIANCE', 'NSE:RELIANCE', 'RELIANCE.NS', 'RELIANCE-EQ' all
    return 'RELIANCE'. Index aliases ('NIFTY', 'BANKNIFTY') resolve to '^NSEI'
    and '^NSEBANK'.
    """
    if not symbol:
        return ""
    s = str(symbol).strip().upper()
    if s.startswith("NSE:"):
        s = s[4:]
    elif s.startswith("BSE:"):
        s = s[4:]
    if s == "NIFTY": return "^NSEI"
    if s in ("BANKNIFTY", "NIFTYBANK"): return "^NSEBANK"
    if s == "NAM": return "NAM-INDIA"
    if s.endswith(".NS") or s.endswith(".BO"):
        s = s[:-3]
    for suf in _DHAN_SUFFIXES:
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    return s


def _to_yf_ticker(symbol: str) -> str:
    """clean_symbol → yfinance-ready ticker (adds .NS unless it's an index)."""
    s = clean_symbol(symbol)
    if not s:
        return ""
    if s.startswith("^") or s.endswith("=X") or s.endswith("=F"):
        return s
    return f"{s}.NS"


# ── nsepython secondary provider ─────────────────────────────────────────────
_PERIOD_TO_DAYS = {
    "1d": 5, "5d": 7, "1mo": 31, "3mo": 95, "6mo": 185,
    "1y": 370, "2y": 740, "3y": 1100, "5y": 1830, "10y": 3660,
    "ytd": 366, "max": 3650,
}


def _period_to_date_range(period: str) -> tuple[str, str]:
    """Translate a yfinance period string to (start_dd_mm_yyyy, end_dd_mm_yyyy).
    nsepython expects DD-MM-YYYY format."""
    from datetime import date, timedelta
    today = date.today()
    if period.endswith("d") and period[:-1].isdigit():
        days = int(period[:-1])
    else:
        days = _PERIOD_TO_DAYS.get(period, 185)
    start = today - timedelta(days=days)
    return start.strftime("%d-%m-%Y"), today.strftime("%d-%m-%Y")


def _norm_to_yf_shape(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce the OHLCV frame into yfinance's standard layout: Date index,
    columns ['Open', 'High', 'Low', 'Close', 'Volume'] as float64.

    Important: nselib emits dates as 'DD-MMM-YYYY' ('06-May-2026'); pandas'
    default to_datetime parser only handles ~3 in 20 of these. We try the
    explicit '%d-%b-%Y' format first, then fall back to the default parser.
    """
    out = df.copy()
    if "Date" in out.columns:
        parsed = pd.to_datetime(out["Date"], format="%d-%b-%Y", errors="coerce")
        # Some sources (yfinance, nsepython) use ISO-like dates that the
        # %d-%b-%Y parser rejects — try the default parser for those rows.
        if parsed.isna().any():
            fallback = pd.to_datetime(out["Date"], errors="coerce")
            parsed = parsed.fillna(fallback)
        out["Date"] = parsed
        out = out.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col in out.columns:
            # nselib formats numbers with Indian commas ("1,42,21,786") — strip them
            if out[col].dtype == object:
                out[col] = out[col].astype(str).str.replace(",", "", regex=False)
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _fetch_via_nselib(symbol: str, period: str, interval: str) -> pd.DataFrame:
    """Fallback fetch via nselib (NSE direct). Daily NSE equities only.

    nselib columns:
      Symbol, Series, Date, PrevClose, OpenPrice, HighPrice, LowPrice,
      LastPrice, ClosePrice, AveragePrice, TotalTradedQuantity, Turnover₹, No.ofTrades
    """
    if not NSELIB_OK or _nselib_cm is None:
        return pd.DataFrame()
    if interval != "1d":
        return pd.DataFrame()
    clean = clean_symbol(symbol)
    if not clean or clean.startswith("^"):
        return pd.DataFrame()
    start_str, end_str = _period_to_date_range(period)
    try:
        df = _nselib_cm.price_volume_data(
            symbol=clean, from_date=start_str, to_date=end_str
        )
    except Exception as e:
        logger.debug("nselib price_volume_data failed for %s: %s", clean, e)
        return pd.DataFrame()
    if df is None or df.empty or "ClosePrice" not in df.columns:
        return pd.DataFrame()
    rename = {
        "Date":                  "Date",
        "OpenPrice":             "Open",
        "HighPrice":             "High",
        "LowPrice":              "Low",
        "ClosePrice":            "Close",
        "TotalTradedQuantity":   "Volume",
    }
    cols_present = {k: v for k, v in rename.items() if k in df.columns}
    out = df.rename(columns=cols_present)[list(cols_present.values())]
    return _norm_to_yf_shape(out)


def _fetch_via_nsepython(symbol: str, period: str, interval: str) -> pd.DataFrame:
    """Tertiary fallback via nsepython. As of v2.97 the equity_history
    endpoint frequently returns a payload without a 'data' key (NSE rotated
    their API), so this is rarely the saviour — kept in case it gets fixed.
    """
    if not NSEPY_OK or _nse is None:
        return pd.DataFrame()
    if interval != "1d":
        return pd.DataFrame()
    clean = clean_symbol(symbol)
    if not clean or clean.startswith("^"):
        return pd.DataFrame()
    start_str, end_str = _period_to_date_range(period)
    try:
        df = _nse.equity_history(clean, "EQ", start_str, end_str)
    except Exception as e:
        logger.debug("nsepython equity_history failed for %s: %s", clean, e)
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    col_map = {
        "CH_TIMESTAMP":          "Date",
        "CH_OPENING_PRICE":      "Open",
        "CH_TRADE_HIGH_PRICE":   "High",
        "CH_TRADE_LOW_PRICE":    "Low",
        "CH_CLOSING_PRICE":      "Close",
        "CH_TOT_TRADED_QTY":     "Volume",
    }
    present = {k: v for k, v in col_map.items() if k in df.columns}
    if "CH_TIMESTAMP" not in df.columns or "CH_CLOSING_PRICE" not in df.columns:
        return pd.DataFrame()
    out = df.rename(columns=present)[list(present.values())]
    return _norm_to_yf_shape(out)


# ── PUBLIC API ───────────────────────────────────────────────────────────────
YF_DOWNLOAD_TIMEOUT_S = 30   # hard cap; yfinance has no reliable own timeout

def _yf_download_timeout(*args, _timeout: int = YF_DOWNLOAD_TIMEOUT_S, **kwargs):
    """yf.download wrapped in a daemon thread with a hard join timeout.

    yfinance can hang indefinitely on a stalled connection (the cause of the
    15-hour 'Downloading CNX500...' freeze). A daemon thread + join(timeout)
    returns control after `_timeout` seconds so the caller falls through to its
    fallback (nselib / cache) instead of blocking forever. The stuck thread is
    a daemon, so it never blocks process exit.
    """
    import threading
    box: dict = {}
    def _work():
        try:
            box["data"] = yf.download(*args, **kwargs)
        except Exception as e:                # noqa: BLE001
            box["err"] = e
    t = threading.Thread(target=_work, daemon=True)
    t.start()
    t.join(_timeout)
    if t.is_alive():
        raise TimeoutError(f"yf.download exceeded {_timeout}s — aborting (fallback will run)")
    if "err" in box:
        raise box["err"]
    return box.get("data")


def fetch_ohlcv(symbol: str,
                  period: str = "6mo",
                  interval: str = "1d",
                  use_cache: bool = True,
                  auto_adjust: bool = True,
                  pinned_date: Optional[str] = None) -> pd.DataFrame:
    """Fetch OHLCV with rate limiting + on-disk cache.

    Returns a DataFrame indexed by date with the standard yfinance columns
    (Open, High, Low, Close, Volume). Returns an empty DataFrame on failure.

    E10: when `pinned_date` (or the module-level `set_pinned_date()`) is set,
    the result is sliced to bars on/before that date — every downstream
    indicator then naturally reflects the as-of view.
    """
    effective_pin = pinned_date or _PINNED_DATE
    if effective_pin is not None:
        period = "10y"

    _show_banner_once()
    ticker = _to_yf_ticker(symbol)
    if not ticker:
        return pd.DataFrame()
    key = _cache_key(ticker, period, interval, auto_adjust)

    if use_cache:
        cached = _read_cache(key)
        if (_is_cache_valid_for_pin(key, cached, pinned_date)
                and not _content_stale_for_live(cached, interval, pinned_date)):
            _record_source(symbol, "cache")
            return _apply_pin(cached, pinned_date)
        # Fallback cache check: if key is missed (e.g. forced "10y" in pinned mode) or invalid for pin,
        # check other deep period cache keys since the TV loader caches deep data under them.
        for fallback_period in ("10y", "5y", "3y", "2y", "max"):
            if fallback_period == period:
                continue
            fallback_key = _cache_key(ticker, fallback_period, interval, auto_adjust)
            cached = _read_cache(fallback_key)
            if (_is_cache_valid_for_pin(fallback_key, cached, pinned_date)
                    and not _content_stale_for_live(cached, interval, pinned_date)):
                # CACHE-POISONING FIX (2026-07-03): serve the fallback frame but do
                # NOT re-write it under the requested key — the old `_write_cache`
                # here re-timestamped WEEKS-old data as fresh, so the stale frame
                # self-renewed on every TTL expiry and the network was never
                # consulted again (portfolio + golden-pick symbols were stuck on
                # 2026-06-24 bars for 9 days).
                _record_source(symbol, "cache")
                return _apply_pin(cached, pinned_date)


    # ── Try Dhan API (Primary Provider for Equities) ──────────────────────
    if is_internet_available():
        if DHAN_OK and _dhan is not None:
            try:
                clean = clean_symbol(symbol)
                if _dhan.get_security_meta(clean) is not None:
                    years_val = 10 if period == "10y" else 5
                    if interval == "1wk":
                        df_dhan = _dhan.fetch_weekly(clean, years=years_val)
                    elif interval == "1d":
                        df_dhan = _dhan.fetch_daily(clean, years=years_val)
                    else:
                        df_dhan = pd.DataFrame()
                    
                    if not df_dhan.empty:
                        if use_cache:
                            _write_cache(key, df_dhan, period, interval, auto_adjust)
                        _record_source(symbol, "dhan")
                        return _apply_pin(df_dhan, pinned_date)
                else:
                    logger.info("Dhan: no security_meta for %s — falling back to yfinance "
                                "(stale scrip master or unlisted symbol?)", symbol)
            except Exception as _dhan_err:
                logger.info("Dhan API fetch failed for %s: %s — falling back to yfinance",
                            symbol, _dhan_err)

        _rate_limit()
        try:
            data = _yf_download_timeout(ticker, period=period, interval=interval,
                                auto_adjust=auto_adjust, progress=False)
            if data is not None and not data.empty:
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                if "Close" in data.columns:
                    data = data.dropna(subset=["Close"])
                if not data.empty:
                    if use_cache:
                        _write_cache(key, data, period, interval, auto_adjust)
                    # Loud: paid feed was bypassed for an equity (index ^ symbols
                    # legitimately use yfinance and aren't flagged).
                    if DHAN_OK:
                        logger.info("fetch_ohlcv: %s served by yfinance FALLBACK "
                                    "(Dhan had no data)", symbol)
                    _record_source(symbol, "yfinance")
                    return _apply_pin(data, pinned_date)
        except Exception as e:
            logger.warning("fetch_ohlcv yfinance failed for %s: %s", symbol, e)

        # Secondary provider — nselib (NSE direct). Hits only when yfinance gave
        # us nothing AND it's a daily NSE-equity request.
        try:
            nse_data = _fetch_via_nselib(symbol, period, interval)
            if not nse_data.empty:
                logger.info("fetch_ohlcv: nselib recovered %d rows for %s",
                             len(nse_data), symbol)
                if use_cache:
                    _write_cache(key, nse_data, period, interval, auto_adjust)
                _record_source(symbol, "nselib")
                return _apply_pin(nse_data, pinned_date)
        except Exception as e:
            logger.debug("fetch_ohlcv nselib fallback failed for %s: %s", symbol, e)

        # Tertiary — nsepython. Currently broken for most symbols but cheap to try.
        try:
            nse_data = _fetch_via_nsepython(symbol, period, interval)
            if not nse_data.empty:
                logger.info("fetch_ohlcv: nsepython recovered %d rows for %s",
                             len(nse_data), symbol)
                if use_cache:
                    _write_cache(key, nse_data, period, interval, auto_adjust)
                _record_source(symbol, "nsepython")
                return _apply_pin(nse_data, pinned_date)
        except Exception as e:
            logger.debug("fetch_ohlcv nsepython fallback failed for %s: %s", symbol, e)
    else:
        logger.warning("[data_provider] Offline: skipping all network queries for %s", symbol)

    # Every provider returned empty (or offline) — attempt last-resort cache recovery
    try:
        expired_cached = _read_cache(key, ignore_ttl=True)
        if expired_cached is not None and not expired_cached.empty:
            logger.warning("[data_provider] fetch_ohlcv: Using expired cache for %s as last resort", symbol)
            _record_source(symbol, "cache")
            return _apply_pin(expired_cached, pinned_date)
    except Exception as _re:
        logger.debug("Last-resort cache read failed: %s", _re)

    logger.warning("fetch_ohlcv: NO data for %s from any provider or cache", symbol)
    _record_source(symbol, "none")
    return pd.DataFrame()


def fetch_batch_ohlcv(symbols, period: str = "6mo", interval: str = "1d",
                       use_cache: bool = True, auto_adjust: bool = True,
                       pinned_date: Optional[str] = None) -> dict:
    """Batch fetch. Per-symbol cache hits short-circuit the network call.

    Returns: {clean_symbol: DataFrame} for symbols that returned data.

    E10: pinned_date slices each per-symbol frame to bars on/before that date.
    Falls through to the module-level pin if the parameter is None.
    """
    effective_pin = pinned_date or _PINNED_DATE
    if effective_pin is not None:
        period = "10y"

    if not symbols:
        return {}

    # Build canonical → yf-ticker mapping; preserve clean keys for callers.
    sym_map: dict[str, str] = {}    # yf_ticker -> clean_symbol
    for s in symbols:
        t = _to_yf_ticker(s)
        if t:
            sym_map[t] = clean_symbol(s)

    cached_hits: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    if use_cache:
        for yf_t, clean in sym_map.items():
            key = _cache_key(yf_t, period, interval, auto_adjust)
            cached = _read_cache(key)
            if _is_cache_valid_for_pin(key, cached, pinned_date):
                cached_hits[clean] = _apply_pin(cached, pinned_date)
            else:
                # Fallback cache check for batch mode
                found_fallback = False
                for fallback_period in ("10y", "5y", "3y", "2y", "max"):
                    if fallback_period == period:
                        continue
                    fallback_key = _cache_key(yf_t, fallback_period, interval, auto_adjust)
                    cached_fb = _read_cache(fallback_key)
                    if _is_cache_valid_for_pin(fallback_key, cached_fb, pinned_date):
                        cached_hits[clean] = _apply_pin(cached_fb, pinned_date)
                        _write_cache(key, cached_fb, period, interval, auto_adjust)
                        found_fallback = True
                        break
                if not found_fallback:
                    missing.append(yf_t)
    else:
        missing = list(sym_map.keys())

    # Try resolving missing via Dhan API
    still_missing = []
    if is_internet_available():
        if DHAN_OK and _dhan is not None:
            for yf_t in missing:
                clean = sym_map[yf_t]
                if _dhan.get_security_meta(clean) is not None:
                    try:
                        years_val = 10 if period == "10y" else 5
                        if interval == "1wk":
                            df_dhan = _dhan.fetch_weekly(clean, years=years_val)
                        elif interval == "1d":
                            df_dhan = _dhan.fetch_daily(clean, years=years_val)
                        else:
                            df_dhan = pd.DataFrame()
                        
                        if not df_dhan.empty:
                            key = _cache_key(yf_t, period, interval, auto_adjust)
                            if use_cache:
                                _write_cache(key, df_dhan, period, interval, auto_adjust)
                            cached_hits[clean] = _apply_pin(df_dhan, pinned_date)
                            continue
                    except Exception as _dhan_err:
                        logger.debug("Dhan API batch fetch failed for %s: %s", clean, _dhan_err)
                still_missing.append(yf_t)
            missing = still_missing

        if missing:
            _rate_limit()
            try:
                data = _yf_download_timeout(
                    missing, period=period, interval=interval,
                    auto_adjust=auto_adjust, group_by="ticker",
                    progress=False, ignore_tz=True, threads=True,
                    _timeout=max(YF_DOWNLOAD_TIMEOUT_S, 60),   # batch: allow more time
                )
            except Exception as e:
                logger.warning("batch fetch failed: %s", e)
                data = None

            if data is not None and not data.empty:
                is_multi = len(missing) > 1
                for yf_t in missing:
                    try:
                        if isinstance(data.columns, pd.MultiIndex) and yf_t in data.columns.get_level_values(0):
                            df = data[yf_t].copy()
                        else:
                            df = data.copy()
                        if isinstance(df.columns, pd.MultiIndex):
                            # if somehow still multi-index, take level 0 (likely Price)
                            df.columns = df.columns.get_level_values(0)
                        df = df.dropna(how="all")
                        if "Close" in df.columns:
                            df = df.dropna(subset=["Close"])
                        if df.empty:
                            continue
                        clean = sym_map[yf_t]
                        if use_cache:
                            _write_cache(_cache_key(yf_t, period, interval, auto_adjust),
                                          df, period, interval, auto_adjust)
                        # Apply pin AFTER caching so the cache stores the full frame
                        cached_hits[clean] = _apply_pin(df, pinned_date)
                    except Exception as e:
                        logger.debug("batch slice failed for %s: %s", yf_t, e)
                        continue
    else:
        logger.warning("[data_provider] Offline: skipping all batch network queries")

    # Attempt last-resort cache recovery for any still missing symbols
    for yf_t in missing:
        clean = sym_map[yf_t]
        if clean not in cached_hits:
            try:
                key = _cache_key(yf_t, period, interval, auto_adjust)
                expired_cached = _read_cache(key, ignore_ttl=True)
                if expired_cached is not None and not expired_cached.empty:
                    logger.warning("[data_provider] fetch_batch_ohlcv: Using expired cache for %s as fallback", clean)
                    cached_hits[clean] = _apply_pin(expired_cached, pinned_date)
            except Exception:
                pass

    return cached_hits


def latest_close(symbol: str) -> float:
    """Latest closing price. Returns 0.0 on failure."""
    df = fetch_ohlcv(symbol, period="5d", interval="1d")
    if df.empty or "Close" not in df.columns:
        return 0.0
    try:
        return float(df["Close"].dropna().iloc[-1])
    except Exception:
        return 0.0


# ── LIVE LTP (T3.6, 20 Jun 2026) ────────────────────────────────────────────
# get_ltp now returns a LIVE Dhan last-traded-price during NSE market hours and
# the EOD close otherwise — instead of always the stale 5-day close. Cached ~45s
# so Streamlit reruns / alert loops don't hammer the quote endpoint. Falls back
# to latest_close on any failure (so behaviour never regresses).
import datetime as _dtmod
_LTP_CACHE: dict = {}                                   # clean_symbol -> (ltp, ts)
_LTP_TTL = float(os.getenv("LTP_CACHE_TTL_S", "45"))


def nse_market_open(now: Optional[datetime] = None) -> bool:
    """True during NSE trading hours (Mon-Fri 09:15-15:30 IST). Assumes the
    system clock is IST (the user trades NSE from India)."""
    now = now or datetime.now()
    if now.weekday() >= 5:           # Sat/Sun
        return False
    t = now.time()
    return _dtmod.time(9, 15) <= t <= _dtmod.time(15, 30)


def get_ltp(symbol: str) -> float:
    """Live LTP during NSE hours (Dhan quote/websocket), else latest EOD close. Cached ~45s.
    Never raises; falls back to latest_close on any failure."""
    key = clean_symbol(symbol)
    now = time.time()
    
    try:
        import dhan_marketfeed
        ws_px = dhan_marketfeed.get_live_price(symbol)
        if ws_px > 0:
            _record_source(symbol, "dhan-ws")
            _LTP_CACHE[key] = (ws_px, now)
            return ws_px
        # Not in WS yet, subscribe for next time
        dhan_marketfeed.subscribe_symbols([symbol])
    except Exception as e:
        logger.debug(f"dhan_marketfeed error: {e}")

    c = _LTP_CACHE.get(key)
    if c and (now - c[1]) < _LTP_TTL:
        return c[0]
    px = 0.0
    if DHAN_OK and _dhan is not None and not str(symbol).startswith("^") and nse_market_open():
        try:
            d = _dhan.fetch_ltp([symbol]) or {}
            px = float(d.get(key, 0.0) or 0.0)
            if px > 0:
                _record_source(symbol, "dhan-ltp")
        except Exception as e:
            logger.debug("get_ltp: Dhan LTP failed for %s: %s", symbol, e)
    if px <= 0:
        px = latest_close(symbol)    # EOD fallback (own source tagging via fetch_ohlcv)
    _LTP_CACHE[key] = (px, now)
    return px


def get_ltp_batch(symbols) -> dict:
    """Batch LTP — one Dhan quote call/websocket for all symbols during market hours, EOD
    fallback per symbol otherwise. Returns {clean_symbol: ltp}. Cached ~45s."""
    out, need = {}, []
    now = time.time()
    
    try:
        import dhan_marketfeed
        ws_missing = []
        for s in symbols:
            ws_px = dhan_marketfeed.get_live_price(s)
            if ws_px > 0:
                k = clean_symbol(s)
                out[k] = ws_px
                _record_source(s, "dhan-ws")
                _LTP_CACHE[k] = (ws_px, now)
            else:
                ws_missing.append(s)
        if ws_missing:
            dhan_marketfeed.subscribe_symbols(ws_missing)
            symbols = ws_missing
    except Exception as e:
        logger.debug(f"dhan_marketfeed error in batch: {e}")

    for s in symbols:
        k = clean_symbol(s)
        # Skip if already found via WS
        if k in out: continue
        c = _LTP_CACHE.get(k)
        if c and (now - c[1]) < _LTP_TTL:
            out[k] = c[0]
        else:
            need.append(s)
    live = {}
    if need and DHAN_OK and _dhan is not None and nse_market_open():
        try:
            live = _dhan.fetch_ltp([s for s in need if not str(s).startswith("^")]) or {}
        except Exception as e:
            logger.debug("get_ltp_batch: Dhan LTP failed: %s", e)
    for s in need:
        k = clean_symbol(s)
        px = float(live.get(k, 0.0) or 0.0)
        if px > 0:
            _record_source(s, "dhan-ltp")
        else:
            px = latest_close(s)
        out[k] = px
        _LTP_CACHE[k] = (px, now)
    return out


# ── CACHE MAINTENANCE ────────────────────────────────────────────────────────
def stats() -> dict:
    """Return cache health stats for the dashboard admin tab."""
    _ensure_cache_dir()
    files = os.listdir(CACHE_DIR) if os.path.exists(CACHE_DIR) else []
    metas = [f for f in files if f.endswith(".meta.json")]
    total_size = sum(os.path.getsize(os.path.join(CACHE_DIR, f))
                       for f in files
                       if os.path.isfile(os.path.join(CACHE_DIR, f)))
    oldest_age = None
    fresh = expired = 0
    for m in metas:
        try:
            with open(os.path.join(CACHE_DIR, m), "r", encoding="utf-8") as f:
                meta = json.load(f)
            cached_at = datetime.fromisoformat(meta.get("cached_at", "2000-01-01"))
            ttl = int(meta.get("ttl", CACHE_TTL_DAILY))
            age = (datetime.now() - cached_at).total_seconds()
            if age > ttl:
                expired += 1
            else:
                fresh += 1
            if oldest_age is None or age > oldest_age:
                oldest_age = age
        except Exception:
            continue
    return {
        "cache_dir":            CACHE_DIR,
        "format":               _CACHE_FORMAT,
        "parquet_available":    _PARQUET_OK,
        "nselib_available":     NSELIB_OK,
        "nsepython_available":  NSEPY_OK,
        "pinned_date":          _PINNED_DATE,    # E10: None = live mode
        "entry_count":          len(metas),
        "fresh":                fresh,
        "expired":              expired,
        "total_size_mb":        round(total_size / (1024 * 1024), 2),
        "oldest_age_hours":     round(oldest_age / 3600, 1) if oldest_age else None,
    }


def clear_cache() -> int:
    """Wipe the entire cache. Returns number of files removed."""
    _ensure_cache_dir()
    count = 0
    for f in os.listdir(CACHE_DIR):
        path = os.path.join(CACHE_DIR, f)
        try:
            if os.path.isfile(path):
                os.remove(path)
                count += 1
        except Exception as e:
            logger.warning("clear_cache could not remove %s: %s", path, e)
    return count


def clear_expired() -> int:
    """Remove only entries past their TTL. Returns number of files removed."""
    _ensure_cache_dir()
    removed = 0
    for f in os.listdir(CACHE_DIR):
        if not f.endswith(".meta.json"):
            continue
        meta_p = os.path.join(CACHE_DIR, f)
        try:
            with open(meta_p, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
            cached_at = datetime.fromisoformat(meta.get("cached_at", "2000-01-01"))
            ttl = int(meta.get("ttl", CACHE_TTL_DAILY))
            if (datetime.now() - cached_at).total_seconds() <= ttl:
                continue
        except Exception:
            pass

        # Remove all sibling files for this cache key
        key = f[:-len(".meta.json")]
        for ext in (".meta.json", ".parquet", ".csv"):
            sibling = os.path.join(CACHE_DIR, f"{key}{ext}")
            try:
                if os.path.exists(sibling):
                    os.remove(sibling)
                    removed += 1
            except Exception as e:
                logger.warning("clear_expired could not remove %s: %s", sibling, e)
    return removed


__all__ = [
    "clean_symbol", "fetch_ohlcv", "fetch_batch_ohlcv",
    "latest_close", "get_ltp", "stats", "clear_cache", "clear_expired",
    "set_pinned_date", "get_pinned_date",
    "CACHE_DIR",
]


if __name__ == "__main__":
    print("Testing Data Provider...")
    print(f"  cache format: {_CACHE_FORMAT}  (parquet available: {_PARQUET_OK})")
    df = fetch_ohlcv("RELIANCE", period="1mo")
    if df.empty:
        print("  RELIANCE: FAILED")
    else:
        print(f"  RELIANCE: {len(df)} rows, LTP: {df['Close'].iloc[-1]:.2f}")
    batch = fetch_batch_ohlcv(["TCS", "INFY", "HDFCBANK"], period="1mo")
    for sym, df in batch.items():
        print(f"  {sym}: {len(df)} rows")
    print(f"\n  Cache stats: {stats()}")
