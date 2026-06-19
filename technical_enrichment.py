"""
technical_enrichment.py — Add canonical Weinstein/Minervini technical metrics
to a DataFrame of stocks.

Used by `brute_force_match_pro.py` to enrich the FINAL_*.csv files (Bull,
Recovery, All Combined, Golden Watchlist) with the same technical metrics
the Pine indicators + bull_screener compute, then derive a composite score
that blends fundamentals (Screener.in Conviction) with technicals.

Public API
----------
    enrich_dataframe(df, symbol_col='Symbol', bench='^CRSLDX',
                     progress_cb=None, raise_on_fail=False) -> pd.DataFrame
        Returns a new DataFrame with these added columns:
            Stage              : Weinstein 1/2/3/4 (or None)
            Mansfield_RS       : RS line × 100 vs benchmark
            Daily_RSI          : 14-period RSI
            Daily_ADX          : 14-period ADX
            Above_200DMA       : True if Close > SMA200
            Dist_52WH_pct      : % below 52-week high
            Vol_RelAvg         : volume / 20-day SMA
            EMA_Stack          : True if SMA50 > SMA150 > SMA200 (Minervini)
            Tech_Score         : 0-100 composite of the above
            Combined_Score     : 0-100 blend of Tech + Conviction (if present)

    calc_tech_score(row) -> int
        Compute the 0-100 technical score from an enriched row.

    calc_combined_score(row) -> float
        Blend Conviction (0-10 → 0-100) + Tech_Score (0-100), 50/50 weights.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Use the same data path as bull_screener / validation / breadth_engine
try:
    import data_provider as _dp
    _DP_OK = True
except Exception:
    _dp = None
    _DP_OK = False


# ─────────────────────────────────────────────────────────────────────
# Per-stock metric helpers
# ─────────────────────────────────────────────────────────────────────

def _flatten_cols(df):
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    # Some yfinance responses return duplicate Close columns — collapse.
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated(keep='first')]
    return df


def _safe_close(df: pd.DataFrame) -> Optional[pd.Series]:
    if df is None or df.empty or "Close" not in df.columns:
        return None
    s = df["Close"]
    if isinstance(s, pd.DataFrame):  # duplicate columns
        s = s.iloc[:, 0]
    return s.dropna()


def _calc_rsi(close: pd.Series, length: int = 14) -> Optional[float]:
    """Wilder's RSI. Returns last value or None if insufficient data."""
    if close is None or len(close) < length + 1:
        return None
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1/length, adjust=False, min_periods=length).mean()
    if avg_loss.iloc[-1] == 0:
        return 100.0
    rs = avg_gain.iloc[-1] / avg_loss.iloc[-1]
    return float(100 - (100 / (1 + rs)))


def _calc_adx(df: pd.DataFrame, length: int = 14) -> Optional[float]:
    """Wilder's ADX. Returns last value or None."""
    if df is None or len(df) < length * 2:
        return None
    h = df["High"]; l = df["Low"]; c = df["Close"]
    if isinstance(h, pd.DataFrame): h = h.iloc[:, 0]
    if isinstance(l, pd.DataFrame): l = l.iloc[:, 0]
    if isinstance(c, pd.DataFrame): c = c.iloc[:, 0]
    up_move = h.diff()
    dn_move = -l.diff()
    plus_dm = np.where((up_move > dn_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0.0)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()],
                   axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/length, adjust=False, min_periods=length).mean()
    plus_di  = 100 * (pd.Series(plus_dm, index=h.index)
                       .ewm(alpha=1/length, adjust=False, min_periods=length).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm, index=h.index)
                       .ewm(alpha=1/length, adjust=False, min_periods=length).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1/length, adjust=False, min_periods=length).mean()
    val = adx.iloc[-1]
    return None if pd.isna(val) else float(val)


def _calc_stage(close: pd.Series) -> Optional[int]:
    """Simplified Weinstein stage from daily closes.
       Stage 2: above SMA200 + SMA50 rising
       Stage 3: above SMA200 + SMA50 flat/falling
       Stage 4: below SMA200 + SMA50 falling
       Stage 1: everything else (basing / transition)
    """
    if close is None or len(close) < 210:
        return None
    sma200 = close.rolling(200).mean().iloc[-1]
    sma50  = close.rolling(50).mean()
    if pd.isna(sma200) or len(sma50.dropna()) < 6:
        return None
    sma50_now  = sma50.iloc[-1]
    sma50_prev = sma50.iloc[-6]
    last_close = close.iloc[-1]
    if pd.isna(sma50_now) or pd.isna(sma50_prev):
        return None
    rising = sma50_now > sma50_prev
    falling = sma50_now < sma50_prev
    if last_close > sma200 and rising:
        return 2
    if last_close > sma200 and not rising:
        return 3
    if last_close < sma200 and falling:
        return 4
    return 1


def _calc_mansfield_rs(close: pd.Series, bench_close: pd.Series,
                         lookback: int = 52) -> Optional[float]:
    """Mansfield RS ×100 = ((stock/bench) / SMA(stock/bench, lookback) - 1) × 100.
    Uses weekly resampling — robust to daily-frequency mismatches.
    """
    if close is None or bench_close is None:
        return None
    if len(close) < lookback + 5 or len(bench_close) < lookback + 5:
        return None
    # Align indexes — both should be DatetimeIndex
    df = pd.concat([close, bench_close], axis=1, join="inner").dropna()
    if len(df) < lookback + 5:
        return None
    df.columns = ["c", "b"]
    rp = df["c"] / df["b"]
    rp_sma = rp.rolling(lookback).mean()
    last_rp = rp.iloc[-1]
    last_sma = rp_sma.iloc[-1]
    if pd.isna(last_sma) or last_sma == 0:
        return None
    return float(((last_rp / last_sma) - 1.0) * 100)


def _calc_ema_stack(close: pd.Series) -> bool:
    """Minervini Trend Template stack: SMA50 > SMA150 > SMA200."""
    if close is None or len(close) < 200:
        return False
    sma50  = close.rolling(50).mean().iloc[-1]
    sma150 = close.rolling(150).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]
    if any(pd.isna(x) for x in (sma50, sma150, sma200)):
        return False
    return bool(sma50 > sma150 > sma200)


# ─────────────────────────────────────────────────────────────────────
# Per-symbol enrichment
# ─────────────────────────────────────────────────────────────────────

def enrich_symbol(symbol: str, bench_close: Optional[pd.Series] = None) -> Dict:
    """Fetch OHLCV for one symbol + compute the canonical metrics.

    Returns a dict (possibly with None values for failed metrics). Never raises.
    """
    out: Dict = {
        "Stage": None, "Mansfield_RS": None, "Daily_RSI": None,
        "Daily_ADX": None, "Above_200DMA": None, "Dist_52WH_pct": None,
        "Vol_RelAvg": None, "EMA_Stack": None,
    }
    if not _DP_OK or _dp is None:
        return out
    try:
        df = _flatten_cols(_dp.fetch_ohlcv(symbol, period="2y", interval="1d"))
        if df is None or df.empty:
            return out
        close = _safe_close(df)
        if close is None or len(close) < 210:
            return out
        out["Stage"]         = _calc_stage(close)
        out["Daily_RSI"]     = _calc_rsi(close, 14)
        out["Daily_ADX"]     = _calc_adx(df, 14)
        out["EMA_Stack"]     = _calc_ema_stack(close)

        sma200 = close.rolling(200).mean().iloc[-1]
        if not pd.isna(sma200):
            out["Above_200DMA"] = bool(close.iloc[-1] > sma200)

        # 52W high distance
        h52 = close.tail(252).max()
        if h52 > 0:
            out["Dist_52WH_pct"] = round(
                float((h52 - close.iloc[-1]) / h52 * 100), 2
            )

        # Volume relative to 20-day avg
        if "Volume" in df.columns:
            vol = df["Volume"]
            if isinstance(vol, pd.DataFrame): vol = vol.iloc[:, 0]
            vol = vol.dropna()
            if len(vol) >= 20:
                avg20 = vol.tail(20).mean()
                if avg20 > 0:
                    out["Vol_RelAvg"] = round(float(vol.iloc[-1] / avg20), 2)

        # Mansfield RS vs benchmark
        if bench_close is not None:
            out["Mansfield_RS"] = _calc_mansfield_rs(close, bench_close)
    except Exception as e:
        logger.debug("enrich_symbol(%s) failed: %s", symbol, e)
    return out


# ─────────────────────────────────────────────────────────────────────
# DataFrame-level enrichment + scoring
# ─────────────────────────────────────────────────────────────────────

def enrich_dataframe(df: pd.DataFrame,
                       symbol_col: str = "Symbol",
                       bench: str = "^CRSLDX",
                       progress_cb: Optional[Callable[[int, int, str], None]] = None,
                       ) -> pd.DataFrame:
    """Add Stage, Mansfield_RS, Daily_RSI, Daily_ADX, EMA_Stack, etc.,
       Tech_Score, and Combined_Score columns to df.

    Parameters
    ----------
    df : DataFrame with at least a Symbol column.
    symbol_col : the column name holding ticker strings (no .NS suffix needed).
    bench : benchmark Yahoo ticker for Mansfield RS (default Nifty 500).
    progress_cb : optional callable(idx, total, symbol) for progress reporting.

    Returns a NEW DataFrame (input not mutated).
    """
    if df is None or df.empty or symbol_col not in df.columns:
        return df

    out = df.copy()
    syms = out[symbol_col].dropna().astype(str).tolist()
    n = len(syms)

    # Fetch benchmark ONCE
    bench_close = None
    if _DP_OK and _dp is not None:
        try:
            bdf = _flatten_cols(_dp.fetch_ohlcv(bench, period="2y", interval="1d"))
            bench_close = _safe_close(bdf)
        except Exception as e:
            logger.warning("benchmark %s fetch failed: %s", bench, e)

    # Enrich each symbol
    enriched_rows = []
    for i, sym in enumerate(syms, 1):
        if progress_cb:
            try: progress_cb(i, n, sym)
            except Exception: pass
        enriched_rows.append(enrich_symbol(sym, bench_close))

    # Add columns (preserving row order)
    enrich_df = pd.DataFrame(enriched_rows, index=out.index[:n])
    for col in ["Stage", "Mansfield_RS", "Daily_RSI", "Daily_ADX",
                "Above_200DMA", "Dist_52WH_pct", "Vol_RelAvg", "EMA_Stack"]:
        out[col] = enrich_df[col].reindex(out.index)

    # Composite scores
    out["Tech_Score"]     = out.apply(calc_tech_score, axis=1)
    out["Combined_Score"] = out.apply(calc_combined_score, axis=1)

    return out


def calc_tech_score(row) -> int:
    """0-100 technical-only score from the enriched columns."""
    s = 0
    stage = row.get("Stage")
    if stage == 2: s += 15
    elif stage == 1: s += 5
    elif stage == 3: s -= 5
    elif stage == 4: s -= 15

    rs = row.get("Mansfield_RS")
    if rs is not None:
        if rs > 0:  s += 10
        if rs >= 10: s += 10

    rsi = row.get("Daily_RSI")
    if rsi is not None:
        if 50 <= rsi <= 70: s += 10
        elif 40 <= rsi < 50 or 70 < rsi <= 75: s += 5
        elif rsi > 80: s -= 5  # extreme overbought

    adx = row.get("Daily_ADX")
    if adx is not None:
        if adx >= 25: s += 10
        elif adx >= 20: s += 5

    # NOTE: use `== True`, NOT `is True`. enrich_dataframe builds these columns
    # via pd.DataFrame(...), so when every row succeeds the column becomes numpy
    # bool dtype and row.get() returns numpy.bool_ — and `np.bool_(True) is True`
    # is False, which silently dropped these +10/+10 terms from every Tech_Score
    # and skewed Combined_Score rankings. `== True` is True for both python bool
    # and numpy bool, and correctly False for None/NaN/False.
    if row.get("Above_200DMA") == True: s += 10   # noqa: E712
    if row.get("EMA_Stack") == True:    s += 10   # noqa: E712

    d52 = row.get("Dist_52WH_pct")
    if d52 is not None:
        if d52 <= 5:  s += 10
        elif d52 <= 10: s += 7
        elif d52 <= 15: s += 5
        elif d52 <= 25: s += 3

    vol = row.get("Vol_RelAvg")
    if vol is not None:
        if vol >= 1.5: s += 10
        elif vol >= 1.0: s += 5

    return max(0, min(100, int(s)))


def calc_combined_score(row) -> float:
    """0-100 blend: Conviction (0-10 → ×10) and Tech_Score (0-100), 50/50.

    Falls back gracefully:
      - No Conviction column → returns Tech_Score
      - No Tech_Score → returns Conviction × 10
      - Neither → returns 0
    """
    conv = row.get("Conviction")
    tech = row.get("Tech_Score")
    try:
        conv_n = float(conv) * 10 if conv not in (None, "", "N/A") else None
    except (TypeError, ValueError):
        conv_n = None
    try:
        tech_n = float(tech) if tech not in (None, "", "N/A") else None
    except (TypeError, ValueError):
        tech_n = None

    if conv_n is not None and tech_n is not None:
        return round(conv_n * 0.5 + tech_n * 0.5, 1)
    if conv_n is not None:
        return round(conv_n, 1)
    if tech_n is not None:
        return round(tech_n, 1)
    return 0.0


__all__ = [
    "enrich_symbol",
    "enrich_dataframe",
    "calc_tech_score",
    "calc_combined_score",
]
