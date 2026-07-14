"""Dhan MarketFeed WebSocket — live LTP overlay for the GM Trigger Board.

P0 rewrite (14-Jul-2026, architectural review): the original NEVER worked —
(a) it did `from dhan_ohlcv import _sym_to_secid, _client` at import time, when
    both module globals are still None (they're rebound lazily inside dhan_ohlcv;
    this module's names never saw the rebind), and
(b) even populated, `_sym_to_secid` values are META DICTS ({"security_id": …}),
    which the old code passed to `str(...)` as if they were raw security ids —
    subscriptions carried garbage ids and on_message compared ids against dict
    reprs, so no tick ever matched. The failure was masked downstream by
    `.fillna(CMP)` (prices froze at the snapshot, silently).

Fix: import the MODULE and resolve symbol→security_id at call time via
dhan_ohlcv.get_security_id() (which now also canonicalizes separator variants),
and keep an O(1) security_id→symbol reverse map for the tick handler.
"""
import threading
import time
import logging
from typing import Dict, List

try:
    from dhanhq import MarketFeed, DhanContext
except ImportError:
    MarketFeed = None
    DhanContext = None

import dhan_ohlcv as _do          # resolve lazily-initialized state at CALL time

logger = logging.getLogger(__name__)

_live_prices: Dict[str, float] = {}
_secid_to_sym: Dict[str, str] = {}      # reverse map for on_message (O(1))
_feed_instance = None
_feed_thread = None
_subscribed_symbols = set()
_feed_lock = threading.Lock()


def _canon(sym: str) -> str:
    """Bare canonical NSE ticker — same key form the board uses."""
    try:
        return _do.canonical_nse_symbol(sym)
    except Exception:
        return str(sym or "").strip().upper()


def on_message(ws, message):
    try:
        if isinstance(message, dict) and message.get("type") == "Ticker Data":
            sec_id = str(message.get("security_id", ""))
            ltp = float(message.get("LTP", 0.0))
            if sec_id and ltp > 0:
                sym = _secid_to_sym.get(sec_id)
                if sym:
                    _live_prices[sym] = ltp
    except Exception as e:
        logger.debug(f"MarketFeed parsing error: {e}")


def _run_feed():
    global _feed_instance
    try:
        if _feed_instance:
            _feed_instance.run_forever()
    except Exception as e:
        logger.error(f"MarketFeed thread crashed: {e}")


def subscribe_symbols(symbols: List[str]):
    global _feed_instance, _feed_thread, _subscribed_symbols

    if not MarketFeed:
        return

    with _feed_lock:
        new_symbols = {_canon(s) for s in symbols} - _subscribed_symbols
        if not new_symbols:
            return

        instruments = []
        for sym in sorted(new_symbols):
            sec_id = None
            try:
                sec_id = _do.get_security_id(sym)   # str, canonicalization-aware
            except Exception as e:
                logger.debug(f"MarketFeed: secid lookup failed for {sym}: {e}")
            if sec_id:
                instruments.append((MarketFeed.NSE, str(sec_id), MarketFeed.Ticker))
                _secid_to_sym[str(sec_id)] = sym
                _subscribed_symbols.add(sym)
            else:
                logger.warning(f"MarketFeed: no security id for {sym} — not subscribed")

        if not instruments:
            return

        if _feed_instance is None:
            try:
                # Initialize the authed Dhan client (auto-refreshed token) and
                # recover its credentials for the feed context; env fallback.
                cid = tok = None
                try:
                    cli = _do._get_client()
                    cid = getattr(cli, "client_id", None)
                    tok = getattr(cli, "access_token", None)
                except Exception as e:
                    logger.debug(f"MarketFeed: client recovery failed: {e}")
                if not cid or not tok:
                    import os
                    cid = cid or os.getenv("DHAN_CLIENT_ID")
                    tok = tok or os.getenv("DHAN_ACCESS_TOKEN")

                if cid and tok:
                    ctx = DhanContext(cid, tok)
                    _feed_instance = MarketFeed(
                        ctx,
                        instruments,
                        version="v2",
                        on_message=on_message
                    )
                    _feed_thread = threading.Thread(target=_run_feed, daemon=True)
                    _feed_thread.start()
                    logger.info(f"MarketFeed WebSocket started ({len(instruments)} instruments).")
                else:
                    logger.error("MarketFeed: no Dhan credentials available — feed not started")
            except Exception as e:
                logger.error(f"Failed to start MarketFeed: {e}")
        else:
            try:
                _feed_instance.subscribe_symbols(instruments)
            except Exception as e:
                logger.error(f"Failed to subscribe to MarketFeed: {e}")


def get_live_price(symbol: str) -> float:
    return _live_prices.get(_canon(symbol), 0.0)
