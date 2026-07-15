"""Dhan MarketFeed WebSocket — live LTP overlay for the GM Trigger Board.

Rewrite #2 (14-Jul-2026, RS-P1): the first rewrite targeted the NEW dhanhq SDK
(`from dhanhq import MarketFeed, DhanContext`) — but the installed dhanhq is
2.0.x, which exports NEITHER. The guarded import silently set MarketFeed=None
and the overlay stayed dead. This version uses the API that actually exists in
the venv (verified 14-Jul-2026):

    from dhanhq import marketfeed
    feed = marketfeed.DhanFeed(client_id, access_token, instruments, version="v2")
    feed.run_forever()          # connects (asyncio, blocking-ish setup)
    tick = feed.get_data()      # poll parsed ticks

The DhanFeed object is asyncio-based and MUST live entirely inside one thread
(its event loop is thread-bound), so the whole lifecycle — construct, connect,
poll — runs in a single daemon thread. Public interface unchanged:
subscribe_symbols(list) + get_live_price(sym), keyed by canonical bare ticker.

New symbols after the feed started: the feed thread is restarted with the union
(avoids guessing 2.0.x's incremental-subscribe signature); the board passes the
full universe on every call, so in practice this happens at most once.
"""
import threading
import time
import logging
from typing import Dict, List

try:
    from dhanhq import marketfeed as _mf
except Exception:
    _mf = None

import dhan_ohlcv as _do          # resolve lazily-initialized state at CALL time

logger = logging.getLogger(__name__)

_live_prices: Dict[str, float] = {}
_secid_to_sym: Dict[str, str] = {}      # reverse map for tick handling (O(1))
_feed_thread = None
_feed_generation = 0                    # bumped to signal an old thread to exit
_subscribed_symbols = set()
_feed_lock = threading.Lock()


def _canon(sym: str) -> str:
    """Bare canonical NSE ticker — same key form the board uses."""
    try:
        return _do.canonical_nse_symbol(sym)
    except Exception:
        return str(sym or "").strip().upper()


def _feed_worker(instruments, cid, tok, generation):
    """Own the DhanFeed for its whole life (asyncio loop is thread-bound)."""
    try:
        feed = _mf.DhanFeed(cid, tok, instruments, version="v2")
        feed.run_forever()                       # connect + subscribe
        logger.info(f"MarketFeed connected ({len(instruments)} instruments).")
        while generation == _feed_generation:    # exit when superseded
            try:
                tick = feed.get_data()
            except Exception as e:
                logger.debug(f"MarketFeed get_data error: {e}")
                time.sleep(1.0)
                continue
            if not tick:
                continue
            try:
                if isinstance(tick, dict) and tick.get("type") == "Ticker Data":
                    sec_id = str(tick.get("security_id", ""))
                    ltp = float(tick.get("LTP", 0.0) or 0.0)
                    if sec_id and ltp > 0:
                        sym = _secid_to_sym.get(sec_id)
                        if sym:
                            _live_prices[sym] = ltp
            except Exception as e:
                logger.debug(f"MarketFeed tick parse error: {e}")
        try:
            feed.disconnect()
        except Exception:
            pass
        logger.info("MarketFeed worker exited (superseded).")
    except Exception as e:
        logger.error(f"MarketFeed worker crashed: {e}")


def subscribe_symbols(symbols: List[str]):
    global _feed_thread, _feed_generation, _subscribed_symbols

    if _mf is None:
        logger.debug("MarketFeed unavailable (dhanhq.marketfeed import failed)")
        return

    with _feed_lock:
        want = {_canon(s) for s in symbols if s}
        new_symbols = want - _subscribed_symbols
        if not new_symbols:
            return

        for sym in sorted(new_symbols):
            try:
                sec_id = _do.get_security_id(sym)     # str, canonicalization-aware
            except Exception as e:
                sec_id = None
                logger.debug(f"MarketFeed: secid lookup failed for {sym}: {e}")
            if sec_id:
                _secid_to_sym[str(sec_id)] = sym
                _subscribed_symbols.add(sym)
            else:
                logger.warning(f"MarketFeed: no security id for {sym} — not subscribed")

        instruments = [(_mf.NSE, sid, _mf.Ticker) for sid in _secid_to_sym.keys()]
        if not instruments:
            return

        # Credentials from the authed client (auto-refreshed token); env fallback.
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
        if not cid or not tok:
            logger.error("MarketFeed: no Dhan credentials — feed not started")
            return

        # (Re)start the worker with the full instrument union. The generation
        # bump tells any previous worker to exit after its next poll.
        _feed_generation += 1
        _feed_thread = threading.Thread(
            target=_feed_worker,
            args=(instruments, cid, tok, _feed_generation),
            daemon=True, name=f"dhan-marketfeed-g{_feed_generation}")
        _feed_thread.start()
        logger.info(f"MarketFeed worker g{_feed_generation} started "
                    f"({len(instruments)} instruments).")


def get_live_price(symbol: str) -> float:
    return _live_prices.get(_canon(symbol), 0.0)
