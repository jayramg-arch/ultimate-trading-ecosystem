# net_utils.py
# Standalone network utility to check internet status with caching.
# Avoids circular import dependencies between data_provider, dhan_auth, and others.

import time
import socket
import logging

logger = logging.getLogger(__name__)

_internet_status = {
    "available": True,
    "last_checked": 0.0
}
_CACHE_TTL_SEC = 20.0  # cache internet check result for 20 seconds

def is_internet_available(host="8.8.8.8", port=53, timeout=1.0) -> bool:
    """
    Check if internet connectivity is available by establishing a TCP connection
    to a public DNS server (default Google DNS: 8.8.8.8 on port 53).
    Caches results for 20 seconds to prevent overhead.
    """
    global _internet_status
    now = time.time()
    if now - _internet_status["last_checked"] < _CACHE_TTL_SEC:
        return _internet_status["available"]

    # Try connecting to the specified host and port
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        _internet_status["available"] = True
    except Exception as e:
        logger.debug("Internet check failed: %s", e)
        _internet_status["available"] = False

    _internet_status["last_checked"] = time.time()
    return _internet_status["available"]
