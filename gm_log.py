"""gm_log — shared rotating logger for the Golden Matcher module.

P1 of the 14-Jul-2026 architectural review: the GM region had ~20 bare
`except Exception: pass` blocks, so an error rendered identically to "no
trigger" — the worst failure mode for a trading decision surface. Every
swallowed exception now lands here (same safe fallbacks, but RECORDED).

Usage:  from gm_log import gm_log
        gm_log.warning(f"{symbol}: PA detection failed: {e}")

Deliberately minimal (solo-trader scale): stdlib logging, one rotating file,
no handlers stacked twice on Streamlit reruns.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "gm_errors.log")

gm_log = logging.getLogger("golden_matcher")

# Guard against duplicate handlers — Streamlit re-imports/reruns must not stack
# handlers (classic symptom: every line logged N times after N reruns).
if not any(isinstance(h, RotatingFileHandler)
           and getattr(h, "baseFilename", "") == _LOG_FILE
           for h in gm_log.handlers):
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        _h = RotatingFileHandler(_LOG_FILE, maxBytes=2_000_000, backupCount=3,
                                 encoding="utf-8")
        _h.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        gm_log.addHandler(_h)
        gm_log.setLevel(logging.INFO)
        gm_log.propagate = False        # don't spam the Streamlit console
    except Exception:
        pass                            # logging must never break the app
