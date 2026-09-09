#!/usr/bin/env python3
"""
setup_paid_news.py — One-time interactive login wizard for ET + Moneycontrol.

Run this ONCE to authenticate:

    python setup_paid_news.py

A real Chromium window opens (NOT headless) pointed at the dedicated paid-news
profile. You log in to Economic Times and Moneycontrol like you normally would
in your browser. When you close the window, the session is saved.

After that, the scrapers (et_scraper.py, mc_scraper.py) attach to the same
profile and inherit your authenticated session. No cookie extraction, no
DPAPI fights, no expiry handling.

Re-run this script if either site invalidates your session (rare — usually
months between forced re-logins).
"""

from __future__ import annotations

import sys
import time

from paid_news_session import open_session, PROFILE_DIR, is_logged_in_et, is_logged_in_mc


def _print_step(n, title):
    print()
    print("=" * 70)
    print(f"  STEP {n} — {title}")
    print("=" * 70)


def _wait_for_user(prompt):
    print()
    input(prompt + " [press Enter when done] ")


def main() -> int:
    print()
    print("╔" + "═" * 68 + "╗")
    print("║  Commander Paid-News Setup Wizard                                  ║")
    print("║  One-time login to Economic Times + Moneycontrol                   ║")
    print("╚" + "═" * 68 + "╝")
    print()
    print(f"  Profile dir: {PROFILE_DIR}")
    print()
    print("  This will open a real Chromium window. Log in to BOTH sites in")
    print("  that window — the session is saved to the profile dir above and")
    print("  re-used by all subsequent scrapes (no need to log in again).")
    print()
    print("  The window is COMPLETELY ISOLATED from your main Chrome — it has")
    print("  its own cookies, its own history, its own extensions. Nothing")
    print("  here touches your normal browsing.")
    print()

    _wait_for_user("Ready to start?")

    # Open the persistent context with a real visible window
    with open_session(headless=False, slow_mo_ms=100) as ctx:
        page = ctx.new_page()

        # ── STEP 1: Economic Times ─────────────────────────────────────
        _print_step(1, "Economic Times login")
        print("  • A Chromium window is open. If it shows 'about:blank',")
        print("    click the address bar and type:")
        print("        https://economictimes.indiatimes.com/")
        print("  • Log in with your Times Internet credentials (top-right 'Sign In').")
        print("  • Verify you see 'My Account' / your name in the header.")
        print("  • Open https://economictimes.indiatimes.com/prime and confirm")
        print("    a Prime article shows full content (not a paywall).")
        print("  • Then return here and press Enter.")

        # Best-effort auto-navigation. If it hangs, the user navigates manually
        # via the address bar — which works just as well.
        try:
            page.goto("https://economictimes.indiatimes.com/",
                      timeout=15_000, wait_until="commit")
        except Exception as e:
            print(f"  (Auto-nav skipped: {type(e).__name__}. Type the URL "
                  f"manually in the open window.)")

        _wait_for_user("Logged in to Economic Times?")

        # ── STEP 2: Moneycontrol ───────────────────────────────────────
        _print_step(2, "Moneycontrol login")
        print("  • Same flow: in the open window, type the URL manually if needed:")
        print("        https://www.moneycontrol.com/")
        print("  • Log in with your Moneycontrol Pro credentials.")
        print("  • Verify 'My Account' / your name in the header.")
        print("  • Open any Pro article and confirm you can read it fully.")
        print("  • Then return here and press Enter.")

        try:
            page.goto("https://www.moneycontrol.com/",
                      timeout=15_000, wait_until="commit")
        except Exception as e:
            print(f"  (Auto-nav skipped: {type(e).__name__}. Type the URL "
                  f"manually in the open window.)")

        _wait_for_user("Logged in to Moneycontrol?")

        # ── STEP 3: Verify both sessions ───────────────────────────────
        _print_step(3, "Verifying sessions")
        page.close()

    # Re-open in headless mode and probe both sites
    print()
    print("  Probing ET session...")
    et_ok = is_logged_in_et()
    print(f"    Economic Times: {'✓ LOGGED IN' if et_ok else '✗ NOT DETECTED (probe heuristic — may still work)'}")

    print("  Probing MC session...")
    mc_ok = is_logged_in_mc()
    print(f"    Moneycontrol:   {'✓ LOGGED IN' if mc_ok else '✗ NOT DETECTED (probe heuristic — may still work)'}")

    print()
    print("=" * 70)
    if et_ok and mc_ok:
        print("  ✓ Setup complete. Both sessions persisted.")
        print("  ✓ Scrapers (et_scraper.py, mc_scraper.py) can now attach.")
    elif et_ok or mc_ok:
        print("  ⚠ One session detected, the other ambiguous.")
        print("  ⚠ The scraper will tell you definitively when it tries to fetch.")
        print("  ⚠ If a real fetch fails, re-run this wizard for the missing site.")
    else:
        print("  ⚠ Neither session detected by the heuristic probe.")
        print("  ⚠ This DOES NOT mean login failed — the probe just couldn't find")
        print("    the expected 'My Account' string (sites change layouts).")
        print("  ⚠ Try a real scrape via et_scraper.py / mc_scraper.py to confirm.")
        print("    If it fails with a paywall response, re-run this wizard.")
    print("=" * 70)
    print()
    print(f"  Profile saved at: {PROFILE_DIR}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
