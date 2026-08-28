"""
sector_lookup.py — Read API for the unified sector DB (sectors.db).

Hot-path module used by the dashboard, screeners, rotation guard, and journal.
Holds an in-memory cache so a single process pays the SQL cost once.

Public API:
    get_sector(symbol)          -> dict | None
    get_sector_index(symbol)    -> str | None       # e.g. "NSE:CNXIT"
    get_sector_name(symbol)     -> str | None       # e.g. "Nifty IT"
    bulk_get(symbols)           -> pd.DataFrame
    sector_to_yf(sector_index)  -> str | None       # follows fallback if needed
    sector_meta(sector_index)   -> dict | None
    list_sectors()              -> pd.DataFrame
    refresh_cache()                                  # invalidate in-memory cache
    db_path                      property            # current DB path
"""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import closing
from typing import Iterable, Optional

import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sectors.db")

# Mirror of normalize_symbol from sector_manager so this module has no
# import-time dependency on it (avoids any circular references).
_DHAN_SUFFIXES = ("-EQ", "-BE", "-SM", "-ST", "-BZ")


def _normalize(raw: str) -> str:
    if not raw:
        return ""
    s = str(raw).strip().upper()
    if s.startswith("NSE:"):
        s = s[4:]
    elif s.startswith("BSE:"):
        s = s[4:]
    if s.endswith(".NS") or s.endswith(".BO"):
        s = s[:-3]
    for suf in _DHAN_SUFFIXES:
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    return s


# ─── In-memory cache ──────────────────────────────────────────────────────────
_lock = threading.RLock()
_cache_loaded = False
_stock_cache: dict[str, dict] = {}    # symbol -> row dict
_alias_cache: dict[str, str] = {}     # alias_symbol -> canonical_symbol
_meta_cache:  dict[str, dict] = {}    # sector_index -> meta dict


def _load_cache() -> None:
    """Load the entire sectors.db into memory. Called lazily on first access."""
    global _cache_loaded
    with _lock:
        if _cache_loaded:
            return
        if not os.path.exists(DB_PATH):
            _cache_loaded = True  # negative cache — empty maps
            return
        with closing(sqlite3.connect(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            for r in conn.execute("SELECT * FROM stock_sector"):
                _stock_cache[r["symbol"]] = dict(r)
            for r in conn.execute("SELECT * FROM alias"):
                _alias_cache[r["alias_symbol"]] = r["canonical_symbol"]
            for r in conn.execute("SELECT * FROM sector_meta"):
                _meta_cache[r["sector_index"]] = dict(r)
        _cache_loaded = True


def refresh_cache() -> None:
    """Drop the in-memory cache so next access re-reads the DB."""
    global _cache_loaded
    with _lock:
        _stock_cache.clear()
        _alias_cache.clear()
        _meta_cache.clear()
        _cache_loaded = False


# ─── Public read API ──────────────────────────────────────────────────────────
def get_sector(symbol: str) -> Optional[dict]:
    """Return a dict with sector_index, sector_name, source, yf_ticker, etc.
    or None if the symbol isn't in the DB.
    """
    _load_cache()
    s = _normalize(symbol)
    if not s:
        return None
    row = _stock_cache.get(s)
    if not row:
        canonical = _alias_cache.get(s)
        if canonical:
            row = _stock_cache.get(canonical)
    if not row:
        return None
    out = dict(row)
    meta = _meta_cache.get(out["sector_index"])
    if meta:
        out["display_name"]          = meta.get("display_name")
        out["yf_ticker"]              = meta.get("yf_ticker")
        out["fallback_sector_index"] = meta.get("fallback_sector_index")
        out["color_hex"]              = meta.get("color_hex")
    return out


def get_sector_index(symbol: str) -> Optional[str]:
    rec = get_sector(symbol)
    return rec["sector_index"] if rec else None


def _etf_sector_name(symbol: str) -> Optional[str]:
    """An ETF's sector is a property of what it HOLDS. Neither sectors.db (which maps
    stocks) nor TradingView (which classifies the wrapper, hence "Miscellaneous")
    answers that, so resolve it from etf_universe's own sub_category."""
    _SUB = {"SECTOR.AUTO": "Auto", "SECTOR.BANKING": "Bank Nifty",
            "SECTOR.PVT_BANK": "Bank Nifty", "SECTOR.PSU_BANK": "PSU Bank",
            "SECTOR.FIN_SERVICES": "Financial Services", "SECTOR.FMCG": "FMCG",
            "SECTOR.HEALTHCARE": "Pharma", "SECTOR.PHARMA": "Pharma",
            "SECTOR.IT": "Nifty IT", "SECTOR.METAL": "Metal",
            "SECTOR.OIL_GAS": "Oil & Gas", "SECTOR.REALTY": "Realty",
            "THEME.ENERGY": "Energy", "THEME.INFRA": "Infra",
            "THEME.CONSUMPTION": "Nifty India Consumption",
            "THEME.DEFENCE": "India Defence", "THEME.CPSE": "Nifty Commodities",
            "THEME.MFG": "Nifty Commodities", "THEME.DIGITAL": "Nifty IT",
            "THEME.EV": "Auto"}
    _CLS = {"BROAD_EQUITY": "Broad Market", "SMART_BETA": "Factor",
            "COMMODITY": "Commodity", "DEBT": "Debt", "INTERNATIONAL": "International"}
    try:
        import etf_universe as _eu
        m = _eu.ETF_UNIVERSE.get(str(symbol).upper().replace("NSE:", "").strip())
    except Exception:
        return None
    if not m:
        return None
    return _SUB.get(str(m.get("sub_category") or "")) or _CLS.get(str(m.get("asset_class") or ""))


def get_sector_name(symbol: str) -> Optional[str]:
    rec = get_sector(symbol)
    if rec:
        return rec["sector_name"]
    # sectors.db maps STOCKS; an ETF falls through to its basket's sector rather
    # than to None (which downstream renders as "Miscellaneous" / blank).
    return _etf_sector_name(symbol)


def bulk_get(symbols: Iterable[str]) -> pd.DataFrame:
    """Vectorized lookup. Returns a DataFrame with columns:
       Symbol, sector_index, sector_name, yf_ticker, source.
    Rows for unknown symbols are present with NaN for sector_*.
    """
    rows = []
    for sym in symbols:
        rec = get_sector(sym)
        if rec:
            rows.append({
                "Symbol":       _normalize(sym),
                "sector_index": rec["sector_index"],
                "sector_name":  rec["sector_name"],
                "yf_ticker":    rec.get("yf_ticker"),
                "source":       rec["source"],
            })
        else:
            rows.append({
                "Symbol":       _normalize(sym),
                "sector_index": None,
                "sector_name":  None,
                "yf_ticker":    None,
                "source":       None,
            })
    return pd.DataFrame(rows)


def sector_to_yf(sector_index: str) -> Optional[str]:
    """Resolve a sector_index to its Yahoo ticker, following fallback chains.

    Example: 'BSE:CG' has yf_ticker=None, fallback='NSE:CNXINFRA' →
             returns '^CNXINFRA'.
    """
    _load_cache()
    seen = set()
    cur = sector_index
    while cur and cur not in seen:
        seen.add(cur)
        meta = _meta_cache.get(cur)
        if not meta:
            return None
        if meta.get("yf_ticker"):
            return meta["yf_ticker"]
        cur = meta.get("fallback_sector_index")
    return None


def sector_meta(sector_index: str) -> Optional[dict]:
    _load_cache()
    meta = _meta_cache.get(sector_index)
    return dict(meta) if meta else None


def list_sectors() -> pd.DataFrame:
    """All sector_meta rows + symbol counts."""
    _load_cache()
    counts: dict[str, int] = {}
    for row in _stock_cache.values():
        counts[row["sector_index"]] = counts.get(row["sector_index"], 0) + 1
    rows = []
    for idx, meta in _meta_cache.items():
        rows.append({
            "sector_index":  idx,
            "display_name":  meta["display_name"],
            "yf_ticker":     meta["yf_ticker"],
            "fallback":      meta["fallback_sector_index"],
            "stock_count":   counts.get(idx, 0),
            "color_hex":     meta["color_hex"],
            "is_broad":      bool(meta["is_broad_market"]),
        })
    df = pd.DataFrame(rows).sort_values("stock_count", ascending=False).reset_index(drop=True)
    return df


def get_sector_yf_map(include_broad: bool = False) -> dict[str, str]:
    """Return {display_name: yf_ticker} for sector_meta rows that have a yf_ticker.

    Used by breadth_engine and market_data_hub to replace their hardcoded
    NSE_SECTORS_YF dicts with values from sectors.db.

    Parameters
    ----------
    include_broad : bool
        If False (default), excludes is_broad_market=1 rows (e.g. CNX500).
    """
    _load_cache()
    out: dict[str, str] = {}
    for idx, meta in _meta_cache.items():
        if not include_broad and meta.get("is_broad_market"):
            continue
        # Resolve via fallback chain so sectors with no direct yf still map.
        yf_t = sector_to_yf(idx)
        if not yf_t:
            continue
        name = meta.get("display_name") or idx
        out[name] = yf_t
    return out


def stats() -> dict:
    """Quick stats for the dashboard admin panel."""
    _load_cache()
    by_source: dict[str, int] = {}
    for row in _stock_cache.values():
        by_source[row["source"]] = by_source.get(row["source"], 0) + 1
    last = max((r["updated_at"] for r in _stock_cache.values() if r.get("updated_at")),
               default=None)
    return {
        "total_symbols": len(_stock_cache),
        "total_sectors": len(_meta_cache),
        "total_aliases": len(_alias_cache),
        "by_source":     by_source,
        "last_update":   last,
        "db_path":       DB_PATH,
        "db_exists":     os.path.exists(DB_PATH),
    }


__all__ = [
    "get_sector", "get_sector_index", "get_sector_name", "bulk_get",
    "sector_to_yf", "sector_meta", "list_sectors", "stats", "refresh_cache",
    "get_sector_yf_map", "DB_PATH",
]
