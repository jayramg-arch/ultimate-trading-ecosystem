"""sector_rotation.py — Week 4: Sector Rotation Overlay using RRG infrastructure.

Computes the JdK RRG quadrant for each NSE sector index (vs Nifty 500) at a
given as-of date, then exposes a filter that drops symbols whose sector is in
unfavorable quadrants.

Uses bull_screener.compute_weekly_indicators (the canonical RRG formula) on
the sector index's weekly series so there is zero signal drift between
stock-level and sector-level RRG calculations.

Modes (used by validation.py --sector_rotation):
    off    : pass-through, no filtering
    strict : keep only picks whose sector is LEADING
    soft   : keep picks whose sector is LEADING or IMPROVING

Public API:
    compute_sector_quadrants(as_of)        -> dict {sector_index: quadrant}
    filter_picks_by_rotation(picks, as_of, mode='strict') -> filtered picks
"""
from __future__ import annotations

from typing import Optional
import pandas as pd

import data_provider as _dp
import bull_screener as _bs
import sector_lookup as _sl


BENCH_YF = "^CRSLDX"   # Nifty 500
_SECTOR_QUAD_CACHE: dict[str, dict[str, str]] = {}  # {as_of_iso: {sector_index: quadrant}}


def _weekly_slice(yf_ticker: str, as_of: pd.Timestamp) -> pd.DataFrame:
    """Fetch ~3y weekly OHLC for a ticker and slice to <= as_of."""
    try:
        df = _bs._flatten_cols(_dp.fetch_ohlcv(yf_ticker, period="3y", interval="1wk"))
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    df = df[df.index <= pd.Timestamp(as_of)]
    return df


def compute_sector_quadrants(as_of) -> dict[str, str]:
    """Return {sector_index: quadrant} computed at as_of using the canonical formula."""
    key = pd.Timestamp(as_of).strftime("%Y-%m-%d")
    if key in _SECTOR_QUAD_CACHE:
        return _SECTOR_QUAD_CACHE[key]

    sectors_df = _sl.list_sectors()
    if sectors_df is None or sectors_df.empty:
        _SECTOR_QUAD_CACHE[key] = {}
        return {}

    bench_w = _weekly_slice(BENCH_YF, as_of)
    if bench_w.empty:
        _SECTOR_QUAD_CACHE[key] = {}
        return {}

    out: dict[str, str] = {}
    for _, row in sectors_df.iterrows():
        sec_idx = row.get("sector_index")
        if not sec_idx:
            continue
        yf_t = _sl.sector_to_yf(sec_idx)
        if not yf_t:
            continue
        sec_w = _weekly_slice(yf_t, as_of)
        if sec_w.empty or len(sec_w) < 35:
            continue
        try:
            rrg = _bs.compute_weekly_indicators(sec_w, bench_w)
        except Exception:
            continue
        q = (rrg or {}).get("rrg_quadrant", "n/a")
        out[sec_idx] = str(q).upper()

    _SECTOR_QUAD_CACHE[key] = out
    return out


_DEFAULT_TRADEABLE = {
    "strict": {"LEADING"},
    "soft":   {"LEADING", "IMPROVING"},
}


def filter_picks_by_rotation(picks: pd.DataFrame, as_of,
                              mode: str = "strict") -> tuple[pd.DataFrame, dict]:
    """Drop picks whose sector quadrant is not in the tradeable set.

    Returns (filtered_picks, diagnostic_dict).
    """
    mode = (mode or "off").lower()
    diag = {"mode": mode, "as_of": str(as_of),
            "n_in": int(len(picks)) if picks is not None else 0,
            "n_out": 0, "dropped_by_sector": {}, "kept_quadrants": {}}

    if mode == "off" or picks is None or picks.empty:
        diag["n_out"] = diag["n_in"]
        return picks, diag

    tradeable = _DEFAULT_TRADEABLE.get(mode, _DEFAULT_TRADEABLE["strict"])
    quads = compute_sector_quadrants(as_of)
    diag["sector_quadrants"] = quads

    sym_col = "Symbol" if "Symbol" in picks.columns else None
    if not sym_col:
        diag["n_out"] = diag["n_in"]
        return picks, diag

    def _sym_quad(sym: str) -> Optional[str]:
        idx = _sl.get_sector_index(sym)
        if not idx:
            return None
        return quads.get(idx)

    quad_col = picks[sym_col].astype(str).map(_sym_quad)
    mask = quad_col.isin(tradeable)
    filt = picks[mask].copy()

    for q, n in quad_col[~mask].fillna("UNKNOWN").value_counts().items():
        diag["dropped_by_sector"][str(q)] = int(n)
    for q, n in quad_col[mask].fillna("UNKNOWN").value_counts().items():
        diag["kept_quadrants"][str(q)] = int(n)
    diag["n_out"] = int(len(filt))
    return filt, diag


__all__ = ["compute_sector_quadrants", "filter_picks_by_rotation"]
