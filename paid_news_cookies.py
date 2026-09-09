"""
paid_news_cookies.py — Load ET + Moneycontrol session cookies from JSON files.

Architecture
------------
Cookies are exported ONCE from your normal Chrome (where you're already
logged in to ET + Moneycontrol Pro) using the free "Cookie-Editor" extension.
The exported JSON files live at:

    data/paid_news_cookies/et.json
    data/paid_news_cookies/mc.json

Each file is a JSON array of cookie objects in Cookie-Editor's standard
export format:

    [
      {"name": "ssoid",  "value": "...", "domain": ".indiatimes.com", ...},
      {"name": "userid", "value": "...", "domain": ".indiatimes.com", ...},
      ...
    ]

The loader normalises the shape and builds a `requests.Session` with the
right cookies + a realistic User-Agent. Subsequent fetches inherit the
authenticated session.

Why this approach
-----------------
- Chrome on Windows DPAPI-encrypts its cookie store; browser_cookie3 needs
  admin and may still fail on Chrome v127+ (App-Bound Encryption).
- Playwright's launch_persistent_context occasionally won't accept keyboard
  input on some Windows configurations (the "can't type in the wizard window"
  failure mode).
- This approach uses your normal Chrome for login, then a one-line JSON
  export. Bulletproof, no automation flakiness, easy to refresh.

Refresh cycle
-------------
ET and MC sessions typically last weeks/months. When a session expires
(scraper returns paywall content), re-export the JSON files. Takes ~30 sec.

Public API
----------
    get_session(site: str) -> requests.Session
        site: "et" or "mc". Returns a requests.Session with cookies loaded.
        Raises FileNotFoundError if the JSON file isn't there.

    is_session_fresh(site: str, max_age_days: int = 30) -> bool
        Did you export this session recently? Used for stale-session warnings.

    cookie_status() -> dict
        For UI: per-site {present, fresh, age_days, cookie_count}.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

COOKIES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data", "paid_news_cookies"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    # NB: dropped "br" (Brotli) from Accept-Encoding — requests doesn't
    # auto-decompress Brotli without the `brotli` package installed, and MC
    # serves Brotli when offered. Sticking to gzip+deflate (which requests
    # handles natively) keeps the scraper working without an extra dep.
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
}

# Sites we support
SITES = {
    "et": {
        "label":      "Economic Times",
        "json_file":  "et.json",
        "test_url":   "https://economictimes.indiatimes.com/prime",
        "paywall_signal": "subscribe to et prime",
        "domains_ok": (".indiatimes.com", "economictimes.indiatimes.com",
                        ".economictimes.indiatimes.com"),
    },
    "mc": {
        "label":      "Moneycontrol",
        "json_file":  "mc.json",
        "test_url":   "https://www.moneycontrol.com/news/business/stocks/",
        "paywall_signal": "subscribe to moneycontrol pro",
        "domains_ok": (".moneycontrol.com", "www.moneycontrol.com",
                        ".pro.moneycontrol.com", "moneycontrol.com"),
    },
}


def _ensure_dir():
    os.makedirs(COOKIES_DIR, exist_ok=True)


def _file_path(site: str) -> str:
    if site not in SITES:
        raise KeyError(f"Unknown site '{site}'. Use one of: {list(SITES)}")
    return os.path.join(COOKIES_DIR, SITES[site]["json_file"])


def _load_raw_cookies(site: str) -> List[Dict]:
    path = _file_path(site)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Cookie file not found: {path}\n"
            f"Export {SITES[site]['label']} cookies via Cookie-Editor extension "
            f"and save to that path. See setup_paid_news_cookies.py for the walkthrough."
        )
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(
            f"{path} should be a JSON array of cookie objects (Cookie-Editor format)."
        )
    return data


def _normalise_cookie(c: Dict) -> Dict:
    """Map Cookie-Editor / EditThisCookie / Chrome devtools shapes → requests-compatible."""
    return {
        "name":   c.get("name") or c.get("Name"),
        "value":  c.get("value") or c.get("Value"),
        "domain": c.get("domain") or c.get("Domain") or "",
        "path":   c.get("path") or c.get("Path") or "/",
        # secure / httpOnly / sameSite are advisory in requests; we keep the cookie
        # only if it has name + value
    }


def get_session(site: str) -> requests.Session:
    """Build a requests.Session pre-loaded with the site's auth cookies."""
    raw_cookies = _load_raw_cookies(site)
    sess = requests.Session()
    sess.headers.update(DEFAULT_HEADERS)
    n_loaded = 0
    for c in raw_cookies:
        nc = _normalise_cookie(c)
        if not nc["name"] or nc["value"] in (None, ""):
            continue
        try:
            sess.cookies.set(
                name=nc["name"], value=str(nc["value"]),
                domain=nc["domain"] or None, path=nc["path"]
            )
            n_loaded += 1
        except Exception as e:
            logger.debug("skip cookie %r for %s: %s", nc["name"], site, e)
    logger.info("loaded %d cookies for %s", n_loaded, site)
    return sess


def is_session_fresh(site: str, max_age_days: int = 30) -> bool:
    """True if the cookie file was exported within `max_age_days`."""
    path = _file_path(site)
    if not os.path.exists(path):
        return False
    mtime = os.path.getmtime(path)
    age_days = (time.time() - mtime) / 86400.0
    return age_days <= max_age_days


def cookie_status() -> Dict[str, Dict]:
    """Per-site status for UI rendering."""
    out: Dict[str, Dict] = {}
    for site, meta in SITES.items():
        path = _file_path(site)
        present = os.path.exists(path)
        n = 0
        age_days: Optional[float] = None
        if present:
            try:
                raw = _load_raw_cookies(site)
                n = sum(1 for c in raw if c.get("name") and c.get("value"))
                age_days = (time.time() - os.path.getmtime(path)) / 86400.0
            except Exception:
                pass
        out[site] = {
            "label":         meta["label"],
            "present":       present,
            "cookie_count":  n,
            "age_days":      round(age_days, 1) if age_days is not None else None,
            "fresh":         present and (age_days or 999) <= 30,
            "file_path":     path,
        }
    return out


def verify_session(site: str, timeout: int = 15) -> Dict:
    """Hit the site's test URL and check whether we see paywall or article content.

    Returns a dict: {site, url, status, paywalled, snippet, error}
    """
    meta = SITES[site]
    out = {"site": site, "url": meta["test_url"], "status": None,
           "paywalled": None, "snippet": "", "error": None}
    try:
        sess = get_session(site)
        resp = sess.get(meta["test_url"], timeout=timeout, allow_redirects=True)
        out["status"] = resp.status_code
        body = resp.text or ""
        # Trim to a small snippet for UI display
        out["snippet"] = body[:400].replace("\n", " ")
        out["paywalled"] = meta["paywall_signal"].lower() in body.lower()
    except FileNotFoundError as e:
        out["error"] = str(e)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


__all__ = [
    "COOKIES_DIR",
    "SITES",
    "get_session",
    "is_session_fresh",
    "cookie_status",
    "verify_session",
]
