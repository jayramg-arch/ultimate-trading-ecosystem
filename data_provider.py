"""
Centralized Data Provider — Rate-Limited, Cached Market Data Access.
All modules should import from here instead of calling yfinance directly.
"""
import yfinance as yf
import pandas as pd
import os
import json
import time
import hashlib
from datetime import datetime, timedelta
import threading

# ── CONFIGURATION ──
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "market_cache")
CACHE_TTL_INTRADAY = 900       # 15 minutes for intraday data
CACHE_TTL_DAILY = 3600         # 1 hour for daily data
CACHE_TTL_WEEKLY = 86400       # 24 hours for weekly data
MAX_CALLS_PER_SECOND = 4       # Rate limit for Yahoo Finance

# ── RATE LIMITER ──
_rate_lock = threading.Lock()
_last_call_time = 0.0

def _rate_limit():
    """Ensures we don't exceed MAX_CALLS_PER_SECOND to Yahoo Finance."""
    global _last_call_time
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_call_time
        min_interval = 1.0 / MAX_CALLS_PER_SECOND
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_call_time = time.time()


# ── CACHE HELPERS ──
def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)

def _cache_key(symbol, period, interval):
    raw = f"{symbol}_{period}_{interval}"
    return hashlib.md5(raw.encode()).hexdigest()

def _get_cache_ttl(period):
    if period in ["1d", "5d"]:
        return CACHE_TTL_INTRADAY
    elif period in ["1mo", "3mo", "6mo"]:
        return CACHE_TTL_DAILY
    else:
        return CACHE_TTL_WEEKLY

def _read_cache(key):
    """Returns cached DataFrame if valid, else None."""
    _ensure_cache_dir()
    meta_path = os.path.join(CACHE_DIR, f"{key}.meta.json")
    data_path = os.path.join(CACHE_DIR, f"{key}.csv")
    
    if not os.path.exists(meta_path) or not os.path.exists(data_path):
        return None
    
    try:
        with open(meta_path, "r") as f:
            meta = json.load(f)
        
        cached_at = datetime.fromisoformat(meta.get("cached_at", "2000-01-01"))
        ttl = meta.get("ttl", CACHE_TTL_DAILY)
        
        if (datetime.now() - cached_at).total_seconds() > ttl:
            return None  # Expired
        
        df = pd.read_csv(data_path, index_col=0, parse_dates=True)
        return df
    except:
        return None

def _write_cache(key, df, period):
    """Writes DataFrame to cache with metadata."""
    _ensure_cache_dir()
    meta_path = os.path.join(CACHE_DIR, f"{key}.meta.json")
    data_path = os.path.join(CACHE_DIR, f"{key}.csv")
    
    try:
        df.to_csv(data_path)
        meta = {
            "cached_at": datetime.now().isoformat(),
            "ttl": _get_cache_ttl(period),
            "period": period
        }
        with open(meta_path, "w") as f:
            json.dump(meta, f)
    except:
        pass  # Fail silently — cache is a nice-to-have, not critical


# ── PUBLIC API ──
def clean_symbol(symbol):
    """Standardize symbol for Yahoo Finance."""
    s = str(symbol).strip().upper().replace("NSE:", "").replace("BSE:", "")
    if s == "NIFTY": return "^NSEI"
    if s in ("BANKNIFTY", "NIFTYBANK"): return "^NSEBANK"
    for suffix in ['-EQ', '-BE', '-SM', '-ST', '-BZ']:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    return s


def fetch_ohlcv(symbol, period="6mo", interval="1d", use_cache=True):
    """
    Fetches OHLCV data with rate limiting and disk caching.
    
    Args:
        symbol: Stock symbol (e.g. 'RELIANCE', 'NSE:TCS', '^NSEI')
        period: yfinance period string ('1mo', '3mo', '6mo', '1y')
        interval: yfinance interval string ('1d', '1wk')
        use_cache: Whether to use disk cache (default True)
    
    Returns:
        pd.DataFrame with OHLCV columns, or empty DataFrame on failure.
    """
    ticker = clean_symbol(symbol)
    if not ticker.startswith("^"):
        ticker = f"{ticker}.NS"
    
    key = _cache_key(ticker, period, interval)
    
    # Check cache first
    if use_cache:
        cached = _read_cache(key)
        if cached is not None and not cached.empty:
            return cached
    
    # Rate-limited API call
    _rate_limit()
    
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        
        if data.empty:
            return pd.DataFrame()
        
        # Flatten MultiIndex columns from newer yfinance
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        # Cache the result
        if use_cache and not data.empty:
            _write_cache(key, data, period)
        
        return data
    except Exception as e:
        print(f"⚠️ DataProvider: Failed to fetch {symbol}: {e}")
        return pd.DataFrame()


def fetch_batch_ohlcv(symbols, period="6mo", interval="1d"):
    """
    Fetches OHLCV for multiple symbols in a single yfinance call.
    More efficient than calling fetch_ohlcv individually.
    
    Returns: dict of {clean_symbol: DataFrame}
    """
    clean_syms = []
    sym_map = {}
    for s in symbols:
        c = clean_symbol(s)
        t = f"{c}.NS" if not c.startswith("^") else c
        clean_syms.append(t)
        sym_map[t] = c
    
    _rate_limit()
    
    try:
        data = yf.download(clean_syms, period=period, interval=interval, 
                          group_by='ticker', progress=False, ignore_tz=True)
        
        if data.empty:
            return {}
        
        result = {}
        is_multi = len(clean_syms) > 1
        for ticker in clean_syms:
            try:
                df = data[ticker].copy() if is_multi else data.copy()
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                if not df.empty:
                    result[sym_map[ticker]] = df
            except:
                pass
        
        return result
    except Exception as e:
        print(f"⚠️ DataProvider: Batch fetch failed: {e}")
        return {}


def get_ltp(symbol):
    """Returns the latest closing price for a symbol."""
    data = fetch_ohlcv(symbol, period="5d", interval="1d")
    if data.empty:
        return 0.0
    return float(data['Close'].iloc[-1])


def clear_cache():
    """Clears all cached market data files."""
    _ensure_cache_dir()
    import glob
    files = glob.glob(os.path.join(CACHE_DIR, "*"))
    count = 0
    for f in files:
        try:
            os.remove(f)
            count += 1
        except:
            pass
    return count


if __name__ == "__main__":
    print("Testing Data Provider...")
    
    # Single fetch
    df = fetch_ohlcv("RELIANCE", period="1mo")
    print(f"RELIANCE: {len(df)} rows, LTP: {df['Close'].iloc[-1]:.2f}" if not df.empty else "RELIANCE: FAILED")
    
    # Batch fetch
    batch = fetch_batch_ohlcv(["TCS", "INFY", "HDFCBANK"], period="1mo")
    for sym, df in batch.items():
        print(f"{sym}: {len(df)} rows")
    
    print(f"\nCache location: {CACHE_DIR}")
