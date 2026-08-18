"""Circuit breaker for screener.in.

Why: screener.in throttles a burst by REFUSING the TCP connect, so every caller
pays the full connect timeout (15s per company page, 30s per universe page)
before falling back. A 50-name board rebuild serialises behind that and looks
frozen. On 18-Aug-2026 the site answered a single shell request in 0.3s while
the app timed out on every one of them - the site was never down.

So: after N consecutive connect failures, stop dialling for COOLDOWN_S and let
callers take their existing fallback path IMMEDIATELY. One probe is allowed
through when the cooldown lapses; a success closes the breaker.

This does NOT change any fallback behaviour - it only removes the wait.
"""
from __future__ import annotations

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

FAIL_THRESHOLD = int(os.getenv("SCREENER_BREAKER_FAILS", "3"))
COOLDOWN_S = float(os.getenv("SCREENER_BREAKER_COOLDOWN_S", "600"))

# --- burst gate -------------------------------------------------------------
# screener.in tolerates a steady trickle and refuses a burst. Cap concurrency
# and enforce a minimum gap between dials, process-wide.
MAX_CONCURRENT = int(os.getenv("SCREENER_MAX_CONCURRENT", "2"))
MIN_INTERVAL_S = float(os.getenv("SCREENER_MIN_INTERVAL_S", "0.7"))
_slots = threading.Semaphore(MAX_CONCURRENT)
_pace_lock = threading.Lock()
_last_dial = 0.0

# --- per-symbol memo ---------------------------------------------------------
# The board fetched CONCORDBIO four times in 34s. Cache the ANSWER, including
# a miss, so a failure is paid once per symbol per TTL instead of once per call.
MEMO_TTL_S = float(os.getenv("SCREENER_MEMO_TTL_S", "900"))
_memo: dict = {}
_memo_lock = threading.Lock()


class _Gate:
    """Context manager: paces dials and caps concurrency."""
    def __enter__(self):
        _slots.acquire()
        global _last_dial
        with _pace_lock:
            gap = time.time() - _last_dial
            if gap < MIN_INTERVAL_S:
                time.sleep(MIN_INTERVAL_S - gap)
            _last_dial = time.time()
        return self

    def __exit__(self, *exc):
        _slots.release()
        return False


def gate() -> "_Gate":
    return _Gate()


def memo_get(key: str):
    """(hit, value). A cached None is a real answer - do not re-dial."""
    with _memo_lock:
        e = _memo.get(key)
        if e and time.time() - e[0] < MEMO_TTL_S:
            return True, e[1]
    return False, None


def memo_put(key: str, value) -> None:
    with _memo_lock:
        _memo[key] = (time.time(), value)


_lock = threading.Lock()
_fails = 0
_open_until = 0.0
_probing = False


def allow() -> bool:
    """False = skip the call and use the fallback now. Never blocks."""
    global _probing
    with _lock:
        if _open_until <= 0.0 or time.time() >= _open_until:
            if _open_until > 0.0 and not _probing:
                _probing = True          # let exactly one request re-test
                logger.info("screener.in breaker: cooldown lapsed, probing")
            return True
        return False


def record_ok() -> None:
    global _fails, _open_until, _probing
    with _lock:
        if _open_until > 0.0:
            logger.info("screener.in breaker CLOSED (probe succeeded)")
        _fails = 0
        _open_until = 0.0
        _probing = False


def record_fail(exc: object = None) -> None:
    global _fails, _open_until, _probing
    with _lock:
        _probing = False
        _fails += 1
        if _fails >= FAIL_THRESHOLD and time.time() >= _open_until:
            _open_until = time.time() + COOLDOWN_S
            logger.warning(
                "screener.in breaker OPEN for %.0fs after %d consecutive failures "
                "(%s). Screener-sourced fields fall back until it closes.",
                COOLDOWN_S, _fails, type(exc).__name__ if exc else "timeout")


def state() -> str:
    with _lock:
        if _open_until > time.time():
            return f"OPEN ({_open_until - time.time():.0f}s left, {_fails} fails)"
        return "closed" if _fails == 0 else f"closed ({_fails} recent fails)"


def fetch_html(url: str, headers: dict, timeout: float = 15.0,
               log=None, tag: str = ""):
    """GET a screener.in page through breaker + burst gate + memo.

    Returns the response text, or None. A None is CACHED: the board asked for
    CONCORDBIO four times in 34s and paid the connect timeout every time.
    """
    import requests

    hit, val = memo_get(url)
    if hit:
        return val

    if not allow():
        memo_put(url, None)
        return None

    try:
        with gate():
            r = requests.get(url, headers=headers, timeout=timeout)
        record_ok()
        out = r.text if r.status_code == 200 else None
        if out is None and log is not None:
            log.warning("Screener HTTP %s for %s", r.status_code, tag or url)
    except Exception as e:
        record_fail(e)
        out = None
        if log is not None:
            log.warning("Screener company request failed for %s: %s", tag or url, e)

    memo_put(url, out)
    return out
