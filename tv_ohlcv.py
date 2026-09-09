"""tv_ohlcv.py — TradingView OHLCV fetcher (via tvDatafeed).

Primary deep-history data source. Anonymous mode gives ~1500 bars (~6y) for
both equities AND indices on NSE. With TV premium credentials in .env, more
bars + real-time updates become available.

.env (optional):
    TV_USERNAME=...
    TV_PASSWORD=...
"""
from __future__ import annotations
import os, logging
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

# Symbol aliases — map yfinance-style to TV-style
_TV_ALIASES = {
    "^CRSLDX":  ("CNX500",   "NSE"),
    "CNX500":   ("CNX500",   "NSE"),
    "NIFTY500": ("CNX500",   "NSE"),
    "^NSEI":    ("NIFTY",    "NSE"),
    "^NSEBANK": ("BANKNIFTY","NSE"),
}

_tv = None

def _get_tv():
    global _tv
    if _tv is not None:
        return _tv
    from tvDatafeed import TvDatafeed
    user = os.getenv("TV_USERNAME", "").strip() or None
    pw   = os.getenv("TV_PASSWORD", "").strip() or None
    # Silence the noisy "no login" warning
    logging.getLogger("tvDatafeed.main").setLevel(logging.ERROR)
    _tv = TvDatafeed(username=user, password=pw)
    return _tv


def _clean_symbol(sym: str) -> tuple[str, str]:
    """Return (TV symbol, exchange). Strips yfinance suffixes."""
    s = sym.strip().upper()
    if s in _TV_ALIASES:
        return _TV_ALIASES[s]
    for suffix in (".NS", ".BO", ".NSE", "-EQ"):
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    exchange = "BSE" if sym.upper().endswith(".BO") else "NSE"
    return s, exchange


def fetch_daily(symbol: str, n_bars: int = 1500) -> pd.DataFrame:
    """Fetch daily OHLCV from TradingView."""
    from tvDatafeed import Interval
    tv_sym, exchange = _clean_symbol(symbol)
    try:
        tv = _get_tv()
        df = tv.get_hist(symbol=tv_sym, exchange=exchange,
                          interval=Interval.in_daily, n_bars=n_bars)
    except Exception as e:
        logger.warning(f"tvDatafeed daily fetch failed for {symbol} ({tv_sym}@{exchange}): {e}")
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    # tvDatafeed returns timestamps with time-of-day; we want pure dates.
    # BUG FIX 2026-05-20: passing index= with normalized timestamps caused
    # pandas to re-align data against new index, producing all-NaN. Use .values
    # to break alignment, then set the normalized index separately.
    out = pd.DataFrame({
        "Open":   df["open"].values,
        "High":   df["high"].values,
        "Low":    df["low"].values,
        "Close":  df["close"].values,
        "Volume": df["volume"].values,
    }, index=pd.to_datetime(df.index).normalize())
    out.index.name = "Date"
    out = out.sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out


def fetch_weekly(symbol: str, n_bars: int = 1500) -> pd.DataFrame:
    """Fetch weekly directly from TV — more accurate than resampling daily."""
    from tvDatafeed import Interval
    tv_sym, exchange = _clean_symbol(symbol)
    try:
        tv = _get_tv()
        df = tv.get_hist(symbol=tv_sym, exchange=exchange,
                          interval=Interval.in_weekly, n_bars=n_bars)
    except Exception as e:
        logger.warning(f"tvDatafeed weekly fetch failed for {symbol}: {e}")
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    out = pd.DataFrame({
        "Open":   df["open"].values,
        "High":   df["high"].values,
        "Low":    df["low"].values,
        "Close":  df["close"].values,
        "Volume": df["volume"].values,
    }, index=pd.to_datetime(df.index).normalize())
    out.index.name = "Date"
    out = out.sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out


if __name__ == "__main__":
    for sym in ["RELIANCE", "TCS", "GESHIP", "^CRSLDX"]:
        print(f"\n--- {sym} ---")
        df = fetch_daily(sym, n_bars=1500)
        if df.empty:
            print(f"  no data")
        else:
            print(f"  daily:  {len(df)} bars  {df.index[0].date()} -- {df.index[-1].date()}")
        dw = fetch_weekly(sym, n_bars=500)
        if not dw.empty:
            print(f"  weekly: {len(dw)} bars  {dw.index[0].date()} -- {dw.index[-1].date()}")
