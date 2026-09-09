#!/usr/bin/env python3
"""
setup_paid_news_cookies.py — Walk-through for cookie export from your normal Chrome.

Run:
    python setup_paid_news_cookies.py

Prints step-by-step instructions for using the free Cookie-Editor extension
to export ET + Moneycontrol cookies from your normal Chrome. After export,
the scrapers (et_scraper.py, mc_scraper.py) read the JSON files and inherit
your authenticated session.

Why this approach (vs. Playwright login wizard):
  - Chrome on Windows DPAPI-encrypts cookies; browser_cookie3 needs admin and
    may still fail on Chrome v127+ (App-Bound Encryption).
  - Playwright launch_persistent_context occasionally won't accept manual
    keyboard input on Windows ("can't type in the wizard window").
  - Cookie-Editor JSON export is bulletproof: 30 seconds per site, no
    automation flakiness.
"""

import os
import sys

from paid_news_cookies import (
    COOKIES_DIR,
    SITES,
    cookie_status,
    verify_session,
)


def _hr():
    print("─" * 72)


def _box(title):
    print()
    print("╔" + "═" * 70 + "╗")
    pad = (70 - len(title)) // 2
    print("║" + " " * pad + title + " " * (70 - pad - len(title)) + "║")
    print("╚" + "═" * 70 + "╝")
    print()


def main() -> int:
    _box("Commander Paid-News Cookie Setup")
    print(f"  Cookies dir: {COOKIES_DIR}")
    os.makedirs(COOKIES_DIR, exist_ok=True)

    print()
    print("  This walkthrough takes ~2 minutes. You will:")
    print("    1. Install the free Cookie-Editor Chrome extension")
    print("    2. Export ET cookies → save to data/paid_news_cookies/et.json")
    print("    3. Export MC cookies → save to data/paid_news_cookies/mc.json")
    print("    4. Confirm both files load cleanly")
    print()

    # ── STEP 1: Install Cookie-Editor ─────────────────────────────────
    _hr()
    print("  STEP 1 — Install Cookie-Editor extension")
    _hr()
    print()
    print("  Open this link in your normal Chrome:")
    print()
    print("    https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm")
    print()
    print("  Click 'Add to Chrome'. The extension icon (small cookie) appears")
    print("  in the toolbar. Pin it for convenience.")
    print()

    input("  Press Enter when Cookie-Editor is installed… ")

    # ── STEP 2: Export ET cookies ─────────────────────────────────────
    _hr()
    print("  STEP 2 — Export Economic Times cookies")
    _hr()
    print()
    et_path = os.path.join(COOKIES_DIR, "et.json")
    print("  In your normal Chrome:")
    print("    a) Open  https://economictimes.indiatimes.com/")
    print("    b) Make sure you are LOGGED IN (top-right shows 'My Account')")
    print("    c) Visit any Prime article — confirm full content (no paywall)")
    print("    d) Click the Cookie-Editor extension icon")
    print("    e) At the bottom, click 'Export' → 'Export as JSON'")
    print("       (Cookie-Editor copies the JSON to your clipboard)")
    print(f"    f) Save the clipboard content to:")
    print(f"         {et_path}")
    print()
    print("  Easiest way to save: open Notepad → paste → Save As →")
    print(f"  navigate to {COOKIES_DIR}\\ → filename: et.json → 'All files'")
    print()

    input("  Press Enter when et.json is saved… ")

    # ── STEP 3: Export MC cookies ─────────────────────────────────────
    _hr()
    print("  STEP 3 — Export Moneycontrol cookies")
    _hr()
    print()
    mc_path = os.path.join(COOKIES_DIR, "mc.json")
    print("  In your normal Chrome:")
    print("    a) Open  https://www.moneycontrol.com/")
    print("    b) Make sure you are LOGGED IN")
    print("    c) Visit any Pro article — confirm full content")
    print("    d) Click Cookie-Editor → Export → Export as JSON")
    print(f"    e) Save to:")
    print(f"         {mc_path}")
    print()

    input("  Press Enter when mc.json is saved… ")

    # ── STEP 4: Verify both files load ───────────────────────────────
    _hr()
    print("  STEP 4 — Verify cookie files")
    _hr()
    print()

    status = cookie_status()
    for site, info in status.items():
        label = info["label"]
        if not info["present"]:
            print(f"  ✗ {label:20s} NO FILE found at {info['file_path']}")
            continue
        n = info["cookie_count"]
        age = info["age_days"]
        fresh = "fresh" if info["fresh"] else "STALE"
        print(f"  ✓ {label:20s} {n:3d} cookies, {age}d old ({fresh})")

    # ── STEP 5: Live-fetch test ──────────────────────────────────────
    print()
    _hr()
    print("  STEP 5 — Live-fetch test (each site)")
    _hr()
    print()

    for site in ["et", "mc"]:
        if not status[site]["present"]:
            continue
        print(f"  Testing {SITES[site]['label']}…")
        result = verify_session(site)
        if result["error"]:
            print(f"    ✗ ERROR: {result['error']}")
        else:
            status_code = result["status"]
            paywalled = result["paywalled"]
            if status_code == 200 and not paywalled:
                print(f"    ✓ HTTP {status_code}, no paywall detected — session is LIVE")
            elif status_code == 200 and paywalled:
                print(f"    ✗ HTTP {status_code}, but paywall detected → cookies didn't authenticate")
                print(f"      Re-export the cookies (you may not have been logged in when exported)")
            else:
                print(f"    ⚠ HTTP {status_code} — unexpected response")
        print()

    _hr()
    print("  Setup complete.")
    print()
    print("  Next: the scrapers (et_scraper.py, mc_scraper.py) will use these")
    print("  cookies automatically. Re-run this wizard if/when you see paywall")
    print("  responses in HUNTER → Sentiment or X-Ray → News.")
    _hr()
    return 0


if __name__ == "__main__":
    sys.exit(main())
