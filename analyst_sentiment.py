"""
analyst_sentiment.py — Aggregates ET + Moneycontrol per-stock analyst sentiment.

Combines results from et_scraper + mc_scraper into a single per-symbol verdict:
    BUY count / HOLD count / SELL count / OTHER count, plus the raw items
    so the UI can render headlines / brokerages.

Cached per-symbol to data/cache/analyst_sentiment_<SYMBOL>.json with 6h TTL.

Public API
----------
    get_for_symbol(symbol, force=False) -> dict
        {
          "symbol": "RELIANCE",
          "fetched_at": "...",
          "buy": 3, "hold": 1, "sell": 2, "other": 4,
          "consensus": "BUY"|"HOLD"|"SELL"|"MIXED"|"NONE",
          "items": [
             {"title", "url", "source", "brokerage", "action", "snippet", "kind"},
             ...
          ],
          "sources_ok": {"et": True, "mc": True},
        }

    get_for_symbols(symbols, force=False) -> dict[str, dict]
        Bulk fetch — useful when populating a HUNTER table column.

    health_check() -> dict
        Per-source status for the UI.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Dict, Iterable, List, Optional

import et_scraper as _et
import mc_scraper as _mc

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

CACHE_TTL_SECONDS = 6 * 60 * 60   # 6 hours


def _cache_path(symbol: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in (symbol or "x"))
    return os.path.join(CACHE_DIR, f"analyst_sentiment_{safe}.json")


def _read_cache(symbol: str) -> Optional[Dict]:
    p = _cache_path(symbol)
    if not os.path.exists(p):
        return None
    if time.time() - os.path.getmtime(p) > CACHE_TTL_SECONDS:
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(symbol: str, data: Dict) -> None:
    try:
        with open(_cache_path(symbol), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.debug("cache write failed for %s: %s", symbol, e)


def _consensus_label(strong_buy: int, buy: int, hold: int,
                       sell: int, strong_sell: int, other: int) -> str:
    """Map raw bucket counts → single consensus label.

    Hierarchy (most-actionable → least):
      STRONG_BUY  : ≥1 strong-buy AND no actionable sells
      BUY         : (buy + strong_buy) ≥ 60% of actionable AND > (sell + strong_sell)
      STRONG_SELL : ≥1 strong-sell AND no actionable buys
      SELL        : (sell + strong_sell) ≥ 60% of actionable AND > (buy + strong_buy)
      HOLD        : hold dominates and ≥ 50% of actionable
      MIXED       : actionable items but no clear winner
      NONE        : no actionable items
    """
    bullish    = strong_buy + buy
    bearish    = sell + strong_sell
    actionable = bullish + hold + bearish
    if actionable == 0:
        return "NONE"
    # STRONG_BUY needs at least one strong call and no opposing actionable sells
    if strong_buy >= 1 and bearish == 0:
        return "STRONG_BUY"
    # STRONG_SELL: strong call, no opposing buys
    if strong_sell >= 1 and bullish == 0:
        return "STRONG_SELL"
    # BUY: bullish dominates
    if bullish >= max(2, int(0.6 * actionable)) and bullish > bearish:
        return "BUY"
    # SELL: bearish dominates
    if bearish >= max(2, int(0.6 * actionable)) and bearish > bullish:
        return "SELL"
    # HOLD majority
    if hold >= max(2, int(0.5 * actionable)) and hold >= bullish and hold >= bearish:
        return "HOLD"
    return "MIXED"


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

def get_for_symbol(symbol: str, force: bool = False) -> Dict:
    """Aggregate ET + MC per-stock items + bucket counts + consensus label."""
    sym = (symbol or "").upper().replace(".NS", "").replace(".BO", "").strip()
    if not sym:
        return {
            "symbol": symbol, "fetched_at": "",
            "strong_buy": 0, "buy": 0, "hold": 0, "sell": 0, "strong_sell": 0,
            "other": 0, "consensus": "NONE", "items": [],
            "sources_ok": {"et": False, "mc": False},
        }

    if not force:
        cached = _read_cache(sym)
        if cached:
            return cached

    items: List[Dict] = []
    sources_ok = {"et": False, "mc": False}

    # ET — recos + topic page
    try:
        et_items = _et.fetch_news_for_stock(sym, limit=25)
        for it in et_items:
            items.append({**it, "_origin": "et"})
        sources_ok["et"] = True
    except FileNotFoundError as e:
        logger.warning("ET cookies missing: %s", e)
    except Exception as e:
        logger.warning("ET fetch failed for %s: %s", sym, e)

    # MC — news listing filter
    try:
        mc_items = _mc.fetch_news_for_stock(sym, limit=25)
        for it in mc_items:
            items.append({**it, "_origin": "mc"})
        sources_ok["mc"] = True
    except FileNotFoundError as e:
        logger.warning("MC cookies missing: %s", e)
    except Exception as e:
        logger.warning("MC fetch failed for %s: %s", sym, e)

    # Tally action buckets — re-extract action from title for consistency
    # (some items in the per-stock list don't have an `action` key directly)
    from et_scraper import _extract_action as _et_act, _extract_brokerage as _et_brk
    strong_buy = buy = hold = sell = strong_sell = other = 0
    for it in items:
        act = it.get("action") or _et_act(it.get("title", ""))
        if not it.get("brokerage"):
            it["brokerage"] = _et_brk(it.get("title", ""))
        it["action"] = act
        if act == "STRONG_BUY":
            strong_buy += 1
        elif act == "BUY":
            buy += 1
        elif act == "HOLD":
            hold += 1
        elif act == "SELL":
            sell += 1
        elif act == "STRONG_SELL":
            strong_sell += 1
        else:
            other += 1

    consensus = _consensus_label(strong_buy, buy, hold, sell, strong_sell, other)

    result = {
        "symbol":       sym,
        "fetched_at":   time.strftime("%Y-%m-%d %H:%M IST"),
        "strong_buy":   strong_buy,
        "buy":          buy,
        "hold":         hold,
        "sell":         sell,
        "strong_sell":  strong_sell,
        "other":        other,
        "consensus":    consensus,
        "items":        items,
        "sources_ok":   sources_ok,
    }
    _write_cache(sym, result)
    return result


def get_for_symbols(symbols: Iterable[str], force: bool = False) -> Dict[str, Dict]:
    """Bulk fetch — used by HUNTER to populate a Sentiment column."""
    out: Dict[str, Dict] = {}
    for sym in symbols:
        try:
            out[sym] = get_for_symbol(sym, force=force)
        except Exception as e:
            logger.warning("aggregate failed for %s: %s", sym, e)
            out[sym] = {
                "symbol": sym, "strong_buy": 0, "buy": 0, "hold": 0,
                "sell": 0, "strong_sell": 0, "other": 0,
                "consensus": "NONE", "items": [],
                "sources_ok": {"et": False, "mc": False},
                "error": str(e),
            }
    return out


def health_check() -> Dict:
    """For UI status panel — per-source health."""
    return {
        "et": _et.health_check(),
        "mc": _mc.health_check(),
    }


__all__ = ["get_for_symbol", "get_for_symbols", "health_check"]
