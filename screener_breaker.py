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
