"""
sector_strength.py — Per-sector stage + momentum helper for the screener.

Replaces the bull_screener's hard-coded "+5 sector strength placeholder" with
a real bonus/penalty derived from each sector index's daily OHLCV. Honors
data_provider's pinned_date — when running a replay/validation, the sector
status is computed as-of the pin date, so the validation engine can measure
whether sector-rotation context actually adds alpha.

Public API:
  get_sector_status(sector_index) -> dict
  get_sector_score(sector_index)  -> int    # -5 .. +5

Status dict shape:
  {
    "sector_index":     str,        # e.g. "NSE:CNXIT"
    "yf_ticker":        str|None,   # e.g. "^CNXIT"  (resolved via fallback)
    "stage":            "Stage 2" | "Stage 4" | "Transitional" | "n/a",
    "monthly_pct":      float|None, # 21-bar return
    "weekly_pct":       float|None, # 5-bar return
    "sma150d_slope_pct": float|None,
  }
"""

from __future__ import annotations

import threading
from typing import Optional

import numpy as np
import pandas as pd


# ─── Memoized cache, keyed by (pinned_date or "live") ─────────────────────────
_lock        = threading.Lock()
_cache_key:  Optional[str]               = None
_cache_data: dict[str, dict]             = {}


def _current_key() -> str:
    try:
        import data_provider as _dp
        return _dp.get_pinned_date() or "live"
    except Exception:
        return "live"


def _refresh_cache() -> None:
    """Pull every sector's daily OHLCV via data_provider and compute status."""
    global _cache_key, _cache_data
    try:
        import data_provider as _dp
        import sector_lookup as _sl
    except Exception:
        return

    statuses: dict[str, dict] = {}
    # Iterate over every sector_meta entry that has either a direct yf_ticker
    # or a resolvable fallback chain. CNX500 (broad market) is included as
    # the implicit benchmark.
    try:
        sectors_df = _sl.list_sectors()
    except Exception:
        sectors_df = pd.DataFrame()
    if sectors_df.empty:
        _cache_key  = _current_key()
        _cache_data = {}
        return

    for _, row in sectors_df.iterrows():
        sector_index = row["sector_index"]
        yf_ticker = _sl.sector_to_yf(sector_index)   # follows fallback chain
        out = {
            "sector_index":      sector_index,
            "yf_ticker":         yf_ticker,
            "stage":             "n/a",
            "monthly_pct":       None,
            "weekly_pct":        None,
            "sma150d_slope_pct": None,
        }
        if not yf_ticker:
            statuses[sector_index] = out
            continue
        try:
            df = _dp.fetch_ohlcv(yf_ticker, period="9mo", interval="1d")
        except Exception:
            df = pd.DataFrame()
        if df is None or df.empty or "Close" not in df.columns or len(df) < 50:
            statuses[sector_index] = out
            continue

        close = df["Close"].astype(float).dropna()
        ltp   = float(close.iloc[-1])
        sma50  = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else float("nan")
        sma150 = float(close.rolling(150).mean().iloc[-1]) if len(close) >= 150 else float("nan")
        sma150_prev = (float(close.rolling(150).mean().iloc[-6])
                          if len(close) >= 155 else float("nan"))
        slope = (round((sma150 - sma150_prev) / sma150_prev * 100, 3)
                  if not (np.isnan(sma150) or np.isnan(sma150_prev) or sma150_prev == 0)
                  else float("nan"))

        # Stage classification (consistent with breadth_engine.get_sector_breadth
        # post-B5 fix: Stage 4 requires SMA150 slope < 0).
        is_stage2 = (not (np.isnan(sma50) or np.isnan(sma150) or np.isnan(slope))
                       and ltp > sma50 and ltp > sma150 and slope > 0)
        is_stage4 = (not (np.isnan(sma50) or np.isnan(sma150) or np.isnan(slope))
                       and ltp < sma50 and ltp < sma150 and slope < 0)
        stage = "Stage 2" if is_stage2 else "Stage 4" if is_stage4 else "Transitional"

        def _pct(bars):
            if len(close) > bars:
                prev = float(close.iloc[-(bars + 1)])
                return round((ltp - prev) / prev * 100, 2) if prev else None
            return None

        out["stage"]              = stage
        out["weekly_pct"]         = _pct(5)
        out["monthly_pct"]        = _pct(21)
        out["sma150d_slope_pct"]  = slope if not np.isnan(slope) else None
        statuses[sector_index]    = out

    _cache_key  = _current_key()
    _cache_data = statuses


def _ensure_fresh() -> None:
    with _lock:
        if _cache_key != _current_key() or not _cache_data:
            _refresh_cache()


def get_sector_status(sector_index: str) -> dict:
    """Return the computed status for a sector (loads/refreshes the cache)."""
    if not sector_index:
        return {"sector_index": "", "stage": "n/a"}
    _ensure_fresh()
    return _cache_data.get(sector_index,
                              {"sector_index": sector_index, "stage": "n/a"})


def get_sector_score(sector_index: str) -> int:
    """Translate a sector's status to a -5..+5 Score adjustment.

    REVERTED to ±5 from v1.4's ±8 widening (which was bundled into a
    multi-change v1.4 sweep that lost -1.02pp avg alpha on N500). The ±5
    range is the v1.2 behavior and is what's currently in production.

    Tier rules (concrete + auditable):
      Stage 2 AND monthly_pct > 0          : +5   (strong + momentum)
      Stage 2 AND monthly_pct <= 0         : +2   (Stage 2 holding, momentum cool)
      Transitional                         :  0
      Stage 4                              : -5
      Stage n/a (no data)                  :  0   (don't penalize on data miss)
    """
    s = get_sector_status(sector_index)
    stage = s.get("stage", "n/a")
    mpct  = s.get("monthly_pct")
    if stage == "Stage 4":
        return -5
    if stage == "Stage 2":
        if mpct is None:
            return 2
        return 5 if mpct > 0 else 2
    return 0


def refresh_now() -> None:
    """Force-recompute the cache. Useful after pinning/unpinning data_provider."""
    with _lock:
        _refresh_cache()


def stats() -> dict:
    """Diagnostics for the dashboard."""
    _ensure_fresh()
    by_stage: dict[str, int] = {}
    for s in _cache_data.values():
        by_stage[s.get("stage", "n/a")] = by_stage.get(s.get("stage", "n/a"), 0) + 1
    return {
        "as_of":     _cache_key,
        "n_sectors": len(_cache_data),
        "by_stage":  by_stage,
    }


__all__ = [
    "get_sector_status", "get_sector_score", "refresh_now", "stats",
]
