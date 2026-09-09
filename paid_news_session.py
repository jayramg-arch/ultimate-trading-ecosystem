"""
paid_news_session.py — Persistent Playwright session for paywalled news scraping.

Architecture
------------
Maintains a dedicated Chrome user-data profile at `data/paid_news_profile/`
that you log in to ONCE (via setup_paid_news.py). Subsequent scrapes attach
to that profile and inherit your authenticated session — no cookie extraction,
no DPAPI conflicts, no expiry handling.

Cookies and session storage live in the profile dir (which is gitignored).
They never enter the codebase, never enter chat, never leave your machine.

Public API
----------
    open_session(headless=True) -> playwright context manager
        Yields a logged-in Browser context with your ET + MC sessions.

    fetch_html(url, *, wait_selector=None, scroll=True, timeout=30) -> str
        Convenience: open the URL in the persistent session, wait for it to
        settle, return the rendered HTML. Use this for one-off scrapes.

    is_logged_in_et() / is_logged_in_mc() -> bool
        Quick session-state checks. Returns False if the session expired
        (you'll need to re-run setup_paid_news.py to re-login).

Profile location
----------------
    {project_root}/data/paid_news_profile/

Threading model
---------------
Playwright's sync API is NOT thread-safe. The Streamlit app should call these
helpers from the main thread only. For background scraping, use a subprocess
that owns its own Playwright instance.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

PROFILE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data", "paid_news_profile"
)

# Realistic UA so paywalled sites don't serve a stripped-down "bot" version
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# Viewport — desktop layout so paywalled sites render full article content,
# not the mobile cut-down view.
DEFAULT_VIEWPORT = {"width": 1440, "height": 900}


def _ensure_profile_dir():
    os.makedirs(PROFILE_DIR, exist_ok=True)


@contextmanager
def open_session(headless: bool = True, slow_mo_ms: int = 0):
    """Open the persistent paid-news Playwright context.

    Yields the `context` object directly; create pages with
    `page = context.new_page()`.

    Parameters
    ----------
    headless : bool
        True for production scraping (no visible window). False for the
        one-time login wizard or for debugging extraction issues.
    slow_mo_ms : int
        Insert N ms between actions. Use 200–500 during the login wizard
        so the user can see what's happening; keep at 0 for production.
    """
    from playwright.sync_api import sync_playwright

    _ensure_profile_dir()

    with sync_playwright() as p:
        # launch_persistent_context = the magic that gives us a logged-in,
        # cookie-rich, plugin-aware Chromium that survives between runs.
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=headless,
            slow_mo=slow_mo_ms,
            user_agent=DEFAULT_UA,
            viewport=DEFAULT_VIEWPORT,
            # accept_downloads=False — we never need file downloads
            # ignore_https_errors=False — never downgrade security
            args=[
                "--disable-blink-features=AutomationControlled",  # less bot-y
                "--no-default-browser-check",
                "--no-first-run",
            ],
        )
        try:
            yield ctx
        finally:
            try:
                ctx.close()
            except Exception:
                pass


def fetch_html(url: str,
               wait_selector: Optional[str] = None,
               scroll: bool = True,
               timeout: int = 30) -> str:
    """Open `url` in the persistent session, return rendered HTML.

    Parameters
    ----------
    url : str
        Page URL to fetch.
    wait_selector : str, optional
        CSS selector to wait for before grabbing HTML. Use this when the
        article body is loaded via JS after page-ready. e.g. "article" or
        ".articleBody" or "div[data-testid='article-body']".
    scroll : bool
        Scroll to bottom (in 4 hops) before extracting. Many paid sites
        lazy-load article body / comments below the fold.
    timeout : int
        Max seconds to wait for selector + load.
    """
    with open_session(headless=True) as ctx:
        page = ctx.new_page()
        try:
            page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=timeout * 1000)
                except Exception as e:
                    logger.debug("wait_selector %r not found in %ds: %s",
                                 wait_selector, timeout, e)
            if scroll:
                # 4-hop scroll-to-bottom to trigger lazy-load
                for i in range(1, 5):
                    page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {i / 4});")
                    time.sleep(0.4)
            return page.content()
        finally:
            try:
                page.close()
            except Exception:
                pass


def _check_logged_in(ctx, probe_url: str, paywall_signal: str,
                     loggedin_signal: str) -> bool:
    """Generic logged-in probe.

    paywall_signal : substring that appears ONLY when paywall is showing
    loggedin_signal : substring that appears ONLY when user is authenticated
    """
    page = ctx.new_page()
    try:
        page.goto(probe_url, timeout=20_000, wait_until="domcontentloaded")
        time.sleep(2)
        html = page.content().lower()
        # Logged-in signal wins if both appear
        if loggedin_signal.lower() in html:
            return True
        if paywall_signal.lower() in html:
            return False
        # Ambiguous — assume not logged in (safer)
        return False
    except Exception as e:
        logger.warning("login probe failed for %s: %s", probe_url, e)
        return False
    finally:
        try:
            page.close()
        except Exception:
            pass


def is_logged_in_et() -> bool:
    """Probe Economic Times logged-in state.

    Visits the Prime page; logged-in users see article previews, free users
    see a "Subscribe to ET Prime" wall.
    """
    with open_session(headless=True) as ctx:
        return _check_logged_in(
            ctx,
            probe_url="https://economictimes.indiatimes.com/prime",
            paywall_signal="subscribe to et prime",
            loggedin_signal="my account",  # ET shows "My Account" link when logged in
        )


def is_logged_in_mc() -> bool:
    """Probe Moneycontrol Pro logged-in state."""
    with open_session(headless=True) as ctx:
        return _check_logged_in(
            ctx,
            probe_url="https://www.moneycontrol.com/news/",
            paywall_signal="subscribe to moneycontrol pro",
            loggedin_signal="my account",  # MC shows "My Account" when logged in
        )


__all__ = [
    "PROFILE_DIR",
    "open_session",
    "fetch_html",
    "is_logged_in_et",
    "is_logged_in_mc",
]
