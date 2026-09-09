"""nse_ohlcv.py — NSE India direct OHLCV fetcher via nselib.

Provides historical equity + index data going back several years, beyond
yfinance's ~2-year truncation for Indian symbols. Free, no API key.

Used by data_provider.py as a fallback when yfinance returns insufficient bars.

WARNING: NSE India can be flaky / rate-limited. Caller should cache aggressively.
"""
from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from nselib import capital_market as _cm

logger = logging.getLogger(__name__)

# Symbol aliases — map yfinance-style to nselib-style
_INDEX_ALIASES = {
    "^CRSLDX":  "NIFTY 500",
    "CNX500":   "NIFTY 500",
    "NIFTY500": "NIFTY 500",
    "^NSEI":    "NIFTY 50",
    "^NSEBANK": "NIFTY BANK",
}


def _clean_symbol(sym: str) -> str:
    """Strip yfinance suffixes."""
    s = sym.strip().upper()
    for suffix in (".NS", ".BO", ".NSE", "-EQ"):
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    return s


def _fmt_date(d: str) -> str:
    """Convert ISO YYYY-MM-DD to nselib DD-MM-YYYY."""
    return date.fromisoformat(d).strftime("%d-%m-%Y")


def fetch_daily(symbol: str,
                  from_date: Optional[str] = None,
                  to_date: Optional[str] = None,
                  years: int = 5) -> pd.DataFrame:
    """Fetch daily OHLCV from NSE India. Returns DataFrame indexed by date.

    Args:
        symbol: ticker (e.g., 'RELIANCE' or '^CRSLDX'). Yfinance suffixes stripped.
        from_date / to_date: ISO 'YYYY-MM-DD'. Defaults: last `years` years.
        years: lookback if from_date not given.
    """
    if to_date is None:
        to_date = date.today().isoformat()
    if from_date is None:
        from_date = (date.today() - timedelta(days=365 * years)).isoformat()

    s = _clean_symbol(symbol)
    is_index = s in _INDEX_ALIASES or symbol.startswith("^")
    nse_name = _INDEX_ALIASES.get(s, s)

    try:
        if is_index:
            df = _cm.index_data(index=nse_name,
                                  from_date=_fmt_date(from_date),
                                  to_date=_fmt_date(to_date))
        else:
            df = _cm.price_volume_and_deliverable_position_data(
                symbol=nse_name,
                from_date=_fmt_date(from_date),
                to_date=_fmt_date(to_date),
            )
    except Exception as e:
        logger.warning(f"nselib fetch failed for {symbol}: {e}")
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    # Normalize column names → standard OHLCV
    out = pd.DataFrame()
    if is_index:
        out["Open"]   = pd.to_numeric(df["OPEN_INDEX_VAL"], errors="coerce")
        out["High"]   = pd.to_numeric(df["HIGH_INDEX_VAL"], errors="coerce")
        out["Low"]    = pd.to_numeric(df["LOW_INDEX_VAL"], errors="coerce")
        out["Close"]  = pd.to_numeric(df["CLOSE_INDEX_VAL"], errors="coerce")
        # nselib uses TRADED_QTY for index volume
        out["Volume"] = pd.to_numeric(df.get("TRADED_QTY", 0), errors="coerce").fillna(0)
        out.index = pd.to_datetime(df["TIMESTAMP"], format="%d-%b-%Y", errors="coerce")
    else:
        # Symbol col may have BOM prefix; clean numeric cols
        # Strip commas (nselib formats large numbers with commas)
        def _num(col):
            return pd.to_numeric(df[col].astype(str).str.replace(",", "", regex=False), errors="coerce")
        out["Open"]   = _num("OpenPrice")
        out["High"]   = _num("HighPrice")
        out["Low"]    = _num("LowPrice")
        out["Close"]  = _num("ClosePrice")
        out["Volume"] = _num("TotalTradedQuantity")
        out.index = pd.to_datetime(df["Date"], format="%d-%b-%Y", errors="coerce")

    out.index.name = "Date"
    out = out.dropna(subset=["Close"]).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out


def fetch_weekly(symbol: str, years: int = 5) -> pd.DataFrame:
    df_d = fetch_daily(symbol, years=years)
    if df_d.empty:
        return df_d
    return df_d.resample("W-MON", closed="left", label="left").agg({
        "Open":  "first", "High": "max", "Low": "min",
        "Close": "last", "Volume": "sum",
    }).dropna(subset=["Close"])


if __name__ == "__main__":
    for sym in ["RELIANCE", "TCS", "GESHIP", "^CRSLDX"]:
        print(f"\n--- {sym} ---")
        df = fetch_daily(sym, years=5)
        if df.empty:
            print(f"  no data")
        else:
            print(f"  {len(df)} bars  {df.index[0].date()} -- {df.index[-1].date()}")
            print(df.tail(3).round(2))
