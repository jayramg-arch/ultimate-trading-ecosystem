#!/usr/bin/env python3
"""
screener_cookie_refresh.py  —  Screener.in Cookie Auto-Refresh  v1.0

Automates the Screener.in login + cookie extraction using Playwright,
then saves the refreshed SCREENER_COOKIE to .env so screener_fetcher.py
picks it up without any manual browser work.

Usage:
  python screener_cookie_refresh.py            # full refresh flow (browser visible)
  python screener_cookie_refresh.py --check    # validate current cookie only (no browser)
  python screener_cookie_refresh.py --headless # headless mode (no visible window)

.env requirements:
  SCREENER_EMAIL=your@email.com
  SCREENER_PASSWORD=yourpassword

Updated automatically:
  SCREENER_COOKIE=<cookie string used by screener_fetcher.py>

Setup:
  pip install playwright
  playwright install chromium
"""

import os
import sys
import asyncio
import time
import argparse
import logging

import requests
from dotenv import load_dotenv, set_key

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(override=True)

# ── Config ────────────────────────────────────────────────────────────────────
_DIR              = os.path.dirname(os.path.abspath(__file__))
ENV_PATH          = os.path.join(_DIR, ".env")
SESSION_DIR       = os.path.join(_DIR, "screener_session")

SCREENER_EMAIL    = os.getenv("SCREENER_EMAIL", "")
SCREENER_PASSWORD = os.getenv("SCREENER_PASSWORD", "")

LOGIN_URL         = "https://www.screener.in/login/"
# Dashboard validation — returns 200 when logged in, redirects (302) when expired
VALIDATE_URL      = "https://www.screener.in/dash/"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


# ── Cookie validation (no browser) ───────────────────────────────────────────
def is_cookie_valid(cookie_string: str) -> bool:
    """Test the cookie string against the Screener.in dashboard.
    Returns True if authenticated (HTTP 200 instead of redirecting)."""
    if not cookie_string:
        return False
    cookie_string = cookie_string.strip("'\"")
    if len(cookie_string) < 20:
        return False
    try:
        resp = requests.get(
            VALIDATE_URL,
            headers={
                "Cookie":    cookie_string,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer":    "https://www.screener.in/",
            },
            timeout=10,
            allow_redirects=False,
        )
        if resp.status_code == 200:
            return True
        return False
    except Exception as e:
        log.warning(f"  Cookie validation request failed: {e}")
        return False


# ── Playwright login + cookie extraction ──────────────────────────────────────
async def _extract_cookie_playwright(headless: bool = False) -> "str | None":
    """Launch Playwright, log in to Screener.in, and return the full Cookie header string."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.error(
            "❌  Playwright not installed.\n"
            "    Run:  pip install playwright && playwright install chromium"
        )
        return None

    if not SCREENER_EMAIL or not SCREENER_PASSWORD:
        log.error(
            "❌  SCREENER_EMAIL / SCREENER_PASSWORD not set in .env.\n"
            "    Add these lines to .env:\n"
            "      SCREENER_EMAIL=your@email.com\n"
            "      SCREENER_PASSWORD=yourpassword"
        )
        return None

    log.info(f"🌐  Launching browser (headless={headless}) ...")
    os.makedirs(SESSION_DIR, exist_ok=True)

    # Clear any stale automated Chrome processes before starting
    try:
        from kill_chrome import kill_automation_chrome
        kill_automation_chrome()
    except Exception as ce:
        log.warning(f"  Pre-run Chrome cleanup returned: {ce}")

    async with async_playwright() as p:
        # Persistent context: Playwright reuses cookies stored in SESSION_DIR
        # across runs, so if the session is still valid we skip the login form.
        try:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR,
                headless=headless,
                channel="chromium",
                no_viewport=not headless,
                args=["--disable-gpu", "--disable-software-rasterizer"]
            )
        except Exception:
            # Fallback: launch without channel override (uses bundled Playwright Chromium)
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR,
                headless=headless,
                no_viewport=not headless,
                args=["--disable-gpu", "--disable-software-rasterizer"]
            )

        page = browser.pages[0] if browser.pages else await browser.new_page()
        cookie_string = None

        try:
            log.info("  Navigating to screener.in/login ...")
            try:
                await page.goto(LOGIN_URL, timeout=30_000, wait_until="domcontentloaded")
            except Exception:
                log.warning("  ⚠️  Page load timeout — proceeding anyway ...")
            await page.wait_for_timeout(2_500)

            # ── Check if already logged in (persistent session still active) ──
            if "login" not in page.url.lower():
                log.info(f"  ✅  Session still active (landed on {page.url}) — no login needed")
            else:
                log.info("  🔑  Login form detected — filling credentials ...")
                try:
                    # Email / username field
                    for sel in ["input[name='username']", "input[type='email']", "#id_username"]:
                        if await page.locator(sel).count() > 0:
                            await page.locator(sel).first.fill(SCREENER_EMAIL)
                            break
                    # Password field
                    for sel in ["input[name='password']", "input[type='password']", "#id_password"]:
                        if await page.locator(sel).count() > 0:
                            await page.locator(sel).first.fill(SCREENER_PASSWORD)
                            break
                    # Submit
                    for sel in ["button[type='submit']", "input[type='submit']",
                                "button:has-text('Login')", "button:has-text('Sign in')"]:
                        if await page.locator(sel).count() > 0:
                            await page.locator(sel).first.click()
                            break
                except Exception as e:
                    log.error(f"  ❌  Error filling login form: {e}")
                    await page.screenshot(path=os.path.join(_DIR, "debug_screener_form_error.png"))
                    return None

                await page.wait_for_timeout(4_000)

                if "login" in page.url.lower():
                    log.error(
                        "  ❌  Login failed — credentials rejected or CAPTCHA blocked.\n"
                        "      Screenshot saved to debug_screener_login_fail.png\n"
                        "      Check SCREENER_EMAIL / SCREENER_PASSWORD in .env"
                    )
                    await page.screenshot(path=os.path.join(_DIR, "debug_screener_login_fail.png"))
                    return None

                log.info(f"  ✅  Login succeeded (landed on {page.url})")

            # ── Extract cookies ───────────────────────────────────────────────
            log.info("  Extracting session cookies ...")
            await page.wait_for_timeout(1_000)
            all_cookies = await browser.cookies()

            screener_cookies = {
                c["name"]: c["value"]
                for c in all_cookies
                if "screener.in" in c.get("domain", "")
            }

            if "sessionid" not in screener_cookies:
                log.error(
                    "  ❌  No sessionid cookie found.\n"
                    "      Screenshot saved to debug_screener_no_session.png"
                )
                await page.screenshot(path=os.path.join(_DIR, "debug_screener_no_session.png"))
                return None

            # Build the Cookie header string that screener_fetcher.py uses:
            #   "csrftoken=XXX; sessionid=YYY; ..."
            # Put csrftoken + sessionid first for clarity
            ordered = {}
            for key in ["csrftoken", "sessionid"]:
                if key in screener_cookies:
                    ordered[key] = screener_cookies.pop(key)
            ordered.update(screener_cookies)   # remaining cookies appended

            cookie_string = "; ".join(f"{k}={v}" for k, v in ordered.items())
            log.info(
                f"  🍪  Extracted {len(ordered)} cookies "
                f"(sessionid + {len(ordered)-1} supporting cookies)"
            )

        except Exception as e:
            log.error(f"  ❌  Playwright error during cookie extraction: {e}")
            try:
                await page.screenshot(path=os.path.join(_DIR, "debug_screener_error.png"))
            except Exception:
                pass
        finally:
            await browser.close()

    return cookie_string


def refresh_screener_cookie(headless: bool = False) -> "str | None":
    """Run the Playwright login flow and save the new cookie to .env.
    Returns the new cookie string, or None on failure."""
    cookie = asyncio.run(_extract_cookie_playwright(headless=headless))
    if cookie:
        set_key(ENV_PATH, "SCREENER_COOKIE", cookie)
        os.environ["SCREENER_COOKIE"] = cookie
        log.info(f"  ✅  SCREENER_COOKIE saved to .env ({len(cookie)} chars)")
        return cookie
    log.error(
        "\n  ❌  Auto-refresh failed.\n"
        "  Manual fallback:\n"
        "    1. Log in at https://www.screener.in\n"
        "    2. F12 → Network → first screener.in request → Request Headers → cookie:\n"
        "    3. Copy that value into .env as:  SCREENER_COOKIE=<value>"
    )
    return None


# ── Public interface ──────────────────────────────────────────────────────────
def ensure_valid_cookie(headless: bool = False) -> "str | None":
    """Return a valid Screener.in cookie, refreshing via Playwright if expired.

    Call this at the top of screener_fetcher.py before each fetch session:

        from screener_cookie_refresh import ensure_valid_cookie
        ensure_valid_cookie()   # updates .env + os.environ in place

    The refreshed cookie is automatically picked up by the existing
    COOKIE_STRING = os.getenv("SCREENER_COOKIE", "") line in screener_fetcher.py
    — just reload dotenv or call load_dotenv(override=True) after this.
    """
    load_dotenv(override=True)
    cookie = os.getenv("SCREENER_COOKIE", "").strip("'\"")

    print("=" * 60)
    print("  SCREENER COOKIE MANAGER  v1.0")
    print("=" * 60)

    if is_cookie_valid(cookie):
        log.info("  ✅  Current cookie is valid — no refresh needed")
        return cookie

    log.info("  🔄  Cookie expired or missing — launching browser refresh ...")
    return refresh_screener_cookie(headless=headless)


# ── CLI entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Screener.in Cookie Auto-Refresh")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate current cookie only (no browser launch)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser headlessly (no visible window)",
    )
    args = parser.parse_args()

    if args.check:
        load_dotenv(override=True)
        ck = os.getenv("SCREENER_COOKIE", "")
        if is_cookie_valid(ck):
            print("✅  Cookie is VALID")
        else:
            print("❌  Cookie is EXPIRED or MISSING")
            print("   Run:  python screener_cookie_refresh.py")
        sys.exit(0)

    result = ensure_valid_cookie(headless=args.headless)

    if result:
        print(f"\n✅  Cookie refreshed successfully (...{result[-20:]})")
        print("   screener_fetcher.py will use it automatically on next run.")
    else:
        print("\n❌  Automatic refresh failed — see manual steps above.")

    input("\nPress Enter to close...")
