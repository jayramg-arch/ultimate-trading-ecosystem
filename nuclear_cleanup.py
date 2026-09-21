import sys
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import asyncio
from playwright.async_api import async_playwright
import os
import re
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STRIKE_USER_DATA = os.path.join(SCRIPT_DIR, "strike_user_data")
TV_USER_DATA = os.path.join(SCRIPT_DIR, "tv_user_data_v2")

# Pattern for script-generated watchlists (e.g. -11JUN26 or [Auto])
STALE_PATTERN = re.compile(r"(-\d{2}[A-Z]{3}\d{2})", re.IGNORECASE)

def get_stale_watchlists(all_watchlist_names):
    to_delete = []
    
    for name in all_watchlist_names:
        # Check if it has a dated stamp (e.g. -19JUN26)
        if STALE_PATTERN.search(name):
            to_delete.append(name)
        # Also delete anything matching [Auto]
        elif "[Auto]" in name:
            to_delete.append(name)
        # Also delete anything starting with known auto-prefixes
        elif any(name.startswith(p) for p in ["Bull_", "Rec_", "FINAL_"]):
            to_delete.append(name)
            
    return list(dict.fromkeys(to_delete))


async def dismiss_strike_modals(page, label=""):
    """Clear anything overlaying the page before we try to click through it.

    WHY (11-Aug-2026 auto-pilot): the very first dropdown click died with
        Locator.click: Timeout 30000ms exceeded
        <div class="rs-modal-wrapper"> intercepts pointer events
    for 30 seconds and took the whole Strike cleanup with it - so stale Strike
    watchlists were never purged while TradingView's cleanup ran fine. Strike
    puts a dialog over market-overview on load (announcement / session notice);
    Playwright's actionability check correctly refuses to click underneath it.

    Three escalating steps, because each fails differently:
      1. Escape          - closes a well-behaved dialog and fires its onClose
      2. Cancel / X      - some dialogs ignore Escape by design
      3. remove() in JS  - last resort for a backdrop left behind with no
                           handler; same pattern already used after deletes
                           further down this file.
    Never raises: a cleanup pass must not be the thing that fails the pipeline.
    """
    SEL = ".rs-modal-wrapper, .rs-modal-backdrop, .rs-modal-open"
    try:
        for attempt in range(3):
            try:
                if await page.locator(SEL).count() == 0:
                    return True
            except Exception:
                return True

            if attempt == 0:
                await page.keyboard.press("Escape")
            elif attempt == 1:
                for txt in ("Cancel", "Close", "Got it", "OK", "Dismiss"):
                    btn = page.locator(f".rs-modal-wrapper button:has-text('{txt}')").first
                    try:
                        if await btn.count() > 0:
                            await btn.click(force=True, timeout=3000)
                            break
                    except Exception:
                        pass
                x_btn = page.locator(".rs-modal-header-close, .rs-modal-wrapper [aria-label='Close']").first
                try:
                    if await x_btn.count() > 0:
                        await x_btn.click(force=True, timeout=3000)
                except Exception:
                    pass
            else:
                await page.evaluate(
                    "document.querySelectorAll("
                    "'.rs-modal-wrapper, .rs-modal-backdrop').forEach(el => el.remove());"
                    "document.body.classList.remove('rs-modal-open');"
                    "document.body.style.overflow = '';"
                )
            await page.wait_for_timeout(700)

        left = await page.locator(SEL).count()
        if left:
            print(f"      [!] {left} overlay(s) still present{(' ' + label) if label else ''} "
                  f"— clicking with force=True anyway.")
            return False
        return True
    except Exception as e:
        print(f"      [!] modal dismiss failed ({e}) — continuing.")
        return False


async def cleanup_strike():
    print("\n========================================")
    print("🚀 NUKING STALE WATCHLISTS ON STRIKE...")
    print("========================================")
    
    if not os.path.exists(STRIKE_USER_DATA):
        print("❌ Strike profile not found.")
        return

    async with async_playwright() as p:
        context = None
        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=os.path.normpath(os.path.abspath(STRIKE_USER_DATA)),
                headless=False,
                channel="chrome",
                args=[
                    "--start-maximized",
                    "--disable-gpu",
                    "--disable-software-rasterizer"
                ]
            )
            page = context.pages[0] if context.pages else await context.new_page()
            
            print("🌍 Navigating to Strike Market Overview...")
            await page.goto("https://web.strike.money/market-overview", timeout=60000)
            await page.wait_for_timeout(5000)

            # Check if logged out
            login_btn = page.locator("button:has-text('Login')")
            if await login_btn.count() > 0:
                print("⚠️ YOU ARE LOGGED OUT OF STRIKE!")
                print("⏳ Please log in manually in the browser window. Waiting 60 seconds...")
                await page.wait_for_timeout(60000)

            # Clear any dialog Strike put over market-overview on load. Without
            # this the click below waits 30s on an intercepting .rs-modal-wrapper
            # and the whole Strike pass is lost.
            await dismiss_strike_modals(page, "on load")

            # 1. Open Dropdown to scrape all watchlist names
            dropdown = page.locator(".rs-watchListDropdown .rs-picker-toggle, .rs-picker-toggle").first
            if await dropdown.count() > 0:
                # force=True skips the actionability wait: if an overlay survived
                # all three dismiss steps, fail in 10s with the page state we can
                # read, not after 30s of silent retrying.
                await dropdown.click(force=True, timeout=10000)
                await page.wait_for_timeout(2000)

                # Scrape all items
                options = await page.locator("div[role='option'], a[role='option'], .rs-picker-select-menu-item, li").all_inner_texts()

                clean_options = [re.sub(r'\s+', ' ', opt).strip() for opt in options]
                to_delete = get_stale_watchlists(clean_options)

                print(f"🎯 Found {len(to_delete)} stale watchlists to terminate.")

                # Close dropdown to reset state
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)

                to_delete = list(dict.fromkeys(to_delete)) # Remove duplicates while preserving order

                for wl_name in to_delete:
                    print(f"   🗑️ Executing Order 66 on: {wl_name}")
                    try:
                        # A delete-confirm dialog from the PREVIOUS iteration can
                        # linger; clear it before reopening the dropdown.
                        await dismiss_strike_modals(page, f"before {wl_name}")
                        # Open dropdown
                        await dropdown.click(force=True)
                        await page.wait_for_timeout(1500)

                        options_loc = page.locator("div[role='option'], a[role='option'], .rs-picker-select-menu-item, li")
                        count = await options_loc.count()

                        clicked = False
                        for i in range(count):
                            text = await options_loc.nth(i).inner_text()
                            if re.sub(r'\s+', ' ', text).strip() == wl_name:
                                await options_loc.nth(i).click(force=True)
                                clicked = True
                                break

                        if clicked:
                            await page.wait_for_timeout(2000)

                            # Force close any open dropdowns
                            await page.keyboard.press("Escape")
                            await page.wait_for_timeout(500)

                            # Click 3 dots
                            more_btn = page.locator("[class*='marketOverviewContainer_moreBtn'], [class*='moreBtn']")
                            if await more_btn.count() > 0:
                                await more_btn.first.click(force=True)
                                await page.wait_for_timeout(1000)

                                # Click Delete
                                delete_btn = page.locator("li:has-text('Delete Watchlist'), li[class*='deleteWatchlist']").last
                                if await delete_btn.count() > 0:
                                    await delete_btn.click(force=True)
                                    await page.wait_for_timeout(1000)

                                    confirm_btn = page.locator("button:has-text('Delete'), button:has-text('Confirm'), button:has-text('Yes')").last
                                    if await confirm_btn.count() > 0:
                                        await confirm_btn.click(force=True)
                                        print(f"      ✅ Vaporized {wl_name}")
                                        await page.wait_for_timeout(1000)

                                        # Nuke any stuck modals
                                        await page.evaluate("document.querySelectorAll('.rs-modal-wrapper, .rs-modal-backdrop').forEach(el => el.remove());")
                                        await page.wait_for_timeout(500)
                                    else:
                                        print(f"      ⚠️ No Confirm button found for {wl_name}")
                                        html = await page.evaluate("document.body.outerHTML")
                                        import urllib.parse
                                        safe_name = urllib.parse.quote(wl_name, safe="")
                                        with open(f"strike_confirm_failed_{safe_name}.html", "w", encoding="utf-8") as f:
                                            f.write(html)
                                        print(f"      📝 Saved HTML to strike_confirm_failed_{safe_name}.html")
                                        await page.keyboard.press("Escape")
                                else:
                                    print(f"      ⚠️ No Delete option in 3-dots menu for {wl_name}")
                                    # Dump the entire body HTML to see what the popup actually contains
                                    html = await page.evaluate("document.body.outerHTML")
                                    import urllib.parse
                                    safe_name = urllib.parse.quote(wl_name, safe="")
                                    with open(f"strike_failed_{safe_name}.html", "w", encoding="utf-8") as f:
                                        f.write(html)
                                    print(f"      📝 Saved HTML to strike_failed_{safe_name}.html")
                                    await page.keyboard.press("Escape")
                            else:
                                print(f"      ⚠️ No 3-dots moreBtn found for {wl_name}")
                        else:
                            print(f"      ⚠️ Couldn't click {wl_name} in dropdown.")
                            await page.keyboard.press("Escape")
                    except Exception as e:
                        print(f"      ❌ Failed on {wl_name}: {e}")
                        await page.evaluate("document.querySelectorAll('.rs-modal-wrapper, .rs-modal-backdrop').forEach(el => el.remove());")
            else:
                print("⚠️ Watchlist dropdown not found!")
        except Exception as e:
            print(f"❌ Error during Strike cleanup: {e}")
        finally:
            if context:
                await context.close()


async def cleanup_tradingview() -> dict:
    """Delete the script-generated (date-stamped / [Auto] / Bull_ Rec_ FINAL_) watchlists on
    TradingView. Returns {"seen": n, "stale": n, "deleted": n, "failed": [...], "skipped_today": n}
    so the pipeline phase can record real numbers - a cleanup that cannot report is a cleanup
    nobody can trust (Phase 0.5 ran for months reporting OK while deleting nothing).

    21-Sep-2026 REWRITE against the live TV DOM (read over CDP, every selector verified,
    one deletion exercised end to end):
      - open-check = the WATCHLIST widget's own width, not the widget-bar's. The bar is
        open whenever ANY tab (Alerts, Object tree...) shows, so the old test never clicked
        the toggle and `watchlists-button` was absent -> exit at the first locator (the
        debug screenshot at 16:30 showed the Alerts Log). `button[data-name='base']`
        TOGGLES the bar - click, re-check, click again if it collapsed.
      - the lists dialog opens on Shift+W (the shortcut TV prints on the "Open list..."
        item) - no menu walking. Fallback: watchlists-button -> div[role='menuitem']
        (it is `role`, not `data-role`, which is the second selector that had died).
      - dialog `div[data-name='watchlists-dialog']`; rows `div[class*='container-']`;
        the NAME is `div[class*='title-']` - the row's textContent has the symbol
        count appended ("Bull_Hunter-18SEP261"), so matching on it mis-names lists.
      - remove = `[data-name='remove-button']` (hover first) -> `div[data-name=
        'confirm-dialog']` -> its plain "Delete" button (no data-name). The dialog stays
        open after a delete, so the loop never reopens it.
      - TODAY'S stamp is never deleted. STALE_PATTERN matches every stamp including
        today's; Phase 0.5 was only safe because it runs before Phase 7 recreates the
        lists. The auto-pilot's 16:30 lists - the ones the live S4 GO alerts bind to -
        now survive a cleanup run at any time of day.
    """
    out = {"seen": 0, "stale": 0, "deleted": 0, "failed": [], "skipped_today": 0}
    print("========================================")
    print("NUKING STALE WATCHLISTS ON TRADINGVIEW...")
    print("========================================")

    if not os.path.exists(TV_USER_DATA):
        print("TradingView profile not found.")
        out["failed"].append("profile missing")
        return out

    today_stamp = "-" + datetime.now().strftime("%d%b%y").upper()
    dry = os.getenv("NUCLEAR_DRY_RUN", "0") == "1" or "--dry-run" in sys.argv
    if dry:
        print("   DRY RUN - nothing will be deleted")
    name_rx = lambda n: re.compile(r"^\s*" + re.escape(n) + r"\s*$")

    async with async_playwright() as p:
        context = None
        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=os.path.normpath(os.path.abspath(TV_USER_DATA)),
                headless=False,
                channel="chrome",
                args=["--start-maximized", "--disable-gpu", "--disable-software-rasterizer"],
            )
            page = context.pages[0] if context.pages else await context.new_page()

            print("Navigating to TradingView Chart...")
            await page.goto("https://in.tradingview.com/chart/")
            await page.wait_for_timeout(8000)

            # -- 1. the WATCHLIST widget must be showing (not merely the widget bar) --
            async def _wl_width() -> float:
                try:
                    return await page.evaluate(
                        "(() => { const e = document.querySelector(\"div[class*='widgetbar-widget-watchlist']\");"
                        " return e ? e.getBoundingClientRect().width : 0; })()")
                except Exception:
                    return 0.0

            for attempt in range(3):
                if await _wl_width() > 10:
                    break
                print("   Watchlist widget not showing - clicking the rail toggle (%d)..." % (attempt + 1))
                toggle = page.locator("button[data-name='base']").first
                if await toggle.count() == 0:
                    break
                await toggle.click()
                await page.wait_for_timeout(1500)
            if await _wl_width() <= 10:
                print("Could not bring the Watchlist widget up.")
                try:
                    await page.screenshot(path=os.path.join(SCRIPT_DIR, "debug_tv_menu_missing.png"))
                except Exception:
                    pass
                out["failed"].append("watchlist widget not showing")
                return out
            print("   Watchlist widget is showing.")

            # -- 2. open the lists dialog (Shift+W; menu as fallback) --
            dialog = page.locator("div[data-name='watchlists-dialog']").first
            await page.keyboard.press("Shift+W")
            await page.wait_for_timeout(1500)
            if await dialog.count() == 0:
                menu_btn = page.locator("button[data-name='watchlists-button']").first
                if await menu_btn.count() > 0:
                    await menu_btn.click(force=True)
                    await page.wait_for_timeout(1200)
                    item = page.locator("div[role='menuitem']").filter(has_text="Open list").first
                    if await item.count() > 0:
                        await item.click(force=True)
                        await page.wait_for_timeout(1500)
            if await dialog.count() == 0:
                print("   'Open list' dialog did not open.")
                out["failed"].append("dialog did not open")
                return out

            # -- 3. read the names --
            titles = dialog.locator("div[class*='container-'] div[class*='title-']")
            names = [t.strip() for t in await titles.all_inner_texts()]
            names = [n for n in names if n]
            out["seen"] = len(names)
            stale = get_stale_watchlists(names)
            keep_today = [n for n in stale if today_stamp in n.upper()]
            stale = [n for n in stale if today_stamp not in n.upper()]
            out["skipped_today"] = len(keep_today)
            out["stale"] = len(stale)
            print("%d lists on the account - %d stale - %d carry today's stamp (kept)"
                  % (len(names), len(stale), len(keep_today)))
            if not names:
                out["failed"].append("dialog opened but listed 0 rows")

            # -- 4. delete, one at a time, confirming each --
            for wl_name in stale:
                if dry:
                    print(f"   would delete: {wl_name}")
                    continue
                print(f"   deleting: {wl_name}")
                try:
                    row = dialog.locator("div[class*='container-']").filter(
                        has=page.locator("div[class*='title-']", has_text=name_rx(wl_name))).first
                    if await row.count() == 0:
                        print(f"      row not found for {wl_name}")
                        out["failed"].append(wl_name)
                        continue
                    await row.scroll_into_view_if_needed()
                    await row.hover()
                    await page.wait_for_timeout(300)
                    rm = row.locator("[data-name='remove-button']").first
                    if await rm.count() == 0:
                        print(f"      no Remove control on {wl_name}")
                        out["failed"].append(wl_name)
                        continue
                    await rm.click(force=True)
                    await page.wait_for_timeout(700)
                    confirm = page.locator("div[data-name='confirm-dialog'] button",
                                           has_text=re.compile(r"^\s*Delete\s*$")).first
                    if await confirm.count() > 0:
                        await confirm.click(force=True)
                    left = 1
                    for _ in range(10):
                        await page.wait_for_timeout(400)
                        left = await dialog.locator("div[class*='title-']", has_text=name_rx(wl_name)).count()
                        if left == 0:
                            break
                    if left == 0:
                        out["deleted"] += 1
                        print(f"      deleted {wl_name}")
                    else:
                        out["failed"].append(wl_name)
                        print(f"      {wl_name} still listed after Delete")
                    if await dialog.count() == 0:          # TV closed it - reopen and continue
                        await page.keyboard.press("Shift+W")
                        await page.wait_for_timeout(1500)
                except Exception as e:
                    out["failed"].append(wl_name)
                    print(f"      failed on {wl_name}: {e}")

            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
        except Exception as e:
            print(f"Error during TradingView cleanup: {e}")
            out["failed"].append(str(e))
        finally:
            if context:
                await context.close()
    print("   summary: seen %d - stale %d - deleted %d - failed %d - kept today %d"
          % (out["seen"], out["stale"], out["deleted"], len(out["failed"]), out["skipped_today"]))
    return out


async def main() -> dict:
    print("======================================================")
    print("  WEINSTEIN COMMANDER: NUCLEAR WATCHLIST CLEANUP")
    print("======================================================")
    print("Deletes auto-generated watchlists carrying a date stamp (e.g. -11JUN26),")
    print("[Auto], or a Bull_ / Rec_ / FINAL_ prefix - except today's stamp.")
    print("------------------------------------------------------\n")

    # 16-Sep-2026: Strike.Money lapsed (strike_automation archived); its profile is
    # gone and the step only printed "Strike profile not found" every run.
    out = await cleanup_tradingview()
    print("\nNUCLEAR CLEANUP COMPLETE.")
    return out


if __name__ == "__main__":
    asyncio.run(main())
