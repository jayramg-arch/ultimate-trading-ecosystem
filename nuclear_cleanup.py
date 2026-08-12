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


async def cleanup_tradingview():
    print("========================================")
    print("🚀 NUKING STALE WATCHLISTS ON TRADINGVIEW...")
    print("========================================")
    
    if not os.path.exists(TV_USER_DATA):
        print("❌ TradingView profile not found.")
        return

    async with async_playwright() as p:
        context = None
        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=os.path.normpath(os.path.abspath(TV_USER_DATA)),
                headless=False,
                channel="chrome",
                args=[
                    "--start-maximized",
                    "--disable-gpu",
                    "--disable-software-rasterizer"
                ]
            )
            page = context.pages[0] if context.pages else await context.new_page()
            
            print("🌍 Navigating to TradingView Chart...")
            await page.goto("https://in.tradingview.com/chart/")
            await page.wait_for_timeout(8000)

            # Ensure Watchlist panel is open
            try:
                pages_wrap = page.locator("div[data-name='widgetbar-pages-with-tabs']")
                is_open = False
                if await pages_wrap.count() > 0:
                    box = await pages_wrap.bounding_box()
                    if box and box['width'] > 10:
                        is_open = True
                
                if not is_open:
                    print("   👉 Watchlist panel seems closed. Opening Watchlist Panel...")
                    # Click the toggle button in the toolbar (data-name="base")
                    toggle_btn = page.locator("button[data-name='base']").first
                    if await toggle_btn.count() > 0:
                        await toggle_btn.click()
                        await page.wait_for_timeout(2000)
                    else:
                        # Fallback using tooltip/label
                        fallback_btn = page.locator("button[data-tooltip*='Watchlist' i], button[aria-label*='Watchlist' i]").first
                        if await fallback_btn.count() > 0:
                            await fallback_btn.click()
                            await page.wait_for_timeout(2000)
                else:
                    print("   ✅ Watchlist Panel is already open.")
            except Exception as e:
                print(f"   ⚠️ Error checking watchlist panel: {e}")

            for iteration in range(3):
                # Open Dropdown
                menu_trigger = page.locator("button[data-name='watchlists-button'], div[class*='widgetbar-widget-watchlist'] .title-button").first
                if await menu_trigger.count() > 0:
                    await menu_trigger.click(force=True)
                    await page.wait_for_timeout(2000)

                    # Click 'Open list' to see ALL watchlists
                    open_list_opt = page.locator("div[data-role='menuitem'], div[role='option'], .item-text").filter(has_text="Open list").first
                    if await open_list_opt.count() > 0:
                        await open_list_opt.click(force=True)
                        await page.wait_for_timeout(2000)

                        dialog = page.locator("div[data-name='watchlists-dialog'], div[data-dialog-name='manage-watchlists']").first
                        if await dialog.count() == 0:
                            dialog = page.locator("div[role='dialog']").first

                        if await dialog.count() > 0:
                            rows = dialog.locator("div[role='row'], div[data-role='list-item']")
                            if await rows.count() == 0:
                                rows = dialog.locator("div[class*='item-']")

                            count = await rows.count()
                            all_rows = []

                            for i in range(count):
                                row = rows.nth(i)
                                text = await row.inner_text()
                                all_rows.append(text.split('\n')[0].strip())

                            stale_rows = get_stale_watchlists(all_rows)

                            if not stale_rows:
                                print("🎯 Found 0 stale watchlists. All clean!")
                                break # Exit the retry loop
                            else:
                                print(f"🎯 Iteration {iteration+1}: Found {len(stale_rows)} stale watchlists to terminate.")
                                for wl_name in stale_rows:
                                    row_locator = "div[role='row'], div[data-role='list-item'], div[class*='item-']"
                                    row = dialog.locator(row_locator).filter(has_text=re.compile(rf"^\s*{re.escape(wl_name)}\s*$")).first
                                    if await row.count() == 0:
                                        row = dialog.locator(row_locator).filter(has_text=wl_name).first
                                    if await row.count() > 0:
                                        try:
                                            await row.scroll_into_view_if_needed()
                                            await page.wait_for_timeout(500)
                                        except:
                                            pass
                                        box = await row.bounding_box()
                                        if box:
                                            await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                                            await page.wait_for_timeout(500)

                                            # After hovering, the delete button (an 'X' or trash icon) should appear
                                            delete_btn = row.locator("[data-name='remove-button'], [aria-label*='elete' i], [title*='elete' i], [aria-label*='emove' i]").last
                                            if await delete_btn.count() == 0:
                                                # Fallback to the last element that looks like an action icon
                                                delete_btn = row.locator("[data-role='list-item-action']").last

                                            if await delete_btn.count() > 0:
                                                await delete_btn.click(force=True)
                                                await page.wait_for_timeout(1000)

                                                confirm_btn = page.locator("button[data-name='submit-button'], button:has-text('Yes'), button:has-text('Delete')").first
                                                if await confirm_btn.count() > 0 and await confirm_btn.is_visible():
                                                    await confirm_btn.click(force=True)
                                                    print(f"      ✅ Vaporized {wl_name} (with confirmation)")
                                                    await page.wait_for_timeout(1500)
                                                else:
                                                    print(f"      ✅ Vaporized {wl_name}")
                                                    await page.wait_for_timeout(1000)
                                            else:
                                                print(f"      ⚠️ Could not find the Delete icon on hover for {wl_name}")
                                        else:
                                            print(f"      ⚠️ Row for {wl_name} has no bounding box (possibly virtualized out of view).")
                                    else:
                                        print(f"      ⚠️ Could not find row for {wl_name} in the dialog. It might be scrolled out of view.")
                        else:
                            print("      ⚠️ 'Open list' dialog not found.")
                    else:
                        print("      ⚠️ 'Open list' option not found in advanced menu.")
                else:
                    print("⚠️ TradingView advanced menu button not found!")
                    try:
                        await page.screenshot(path=os.path.join(SCRIPT_DIR, "debug_tv_menu_missing.png"))
                        print("📸 Saved debug screenshot to debug_tv_menu_missing.png")
                    except Exception as se:
                        print(f"Failed to capture screenshot: {se}")

                # Close dialog if still open before next iteration
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(1000)
        except Exception as e:
            print(f"❌ Error during TradingView cleanup: {e}")
        finally:
            if context:
                await context.close()


async def main():
    print("======================================================")
    print("☢️  WEINSTEIN COMMANDER: NUCLEAR WATCHLIST CLEANUP  ☢️")
    print("======================================================")
    print("This script will hunt down and vaporize any auto-generated")
    print("watchlists containing date stamps (e.g. -11JUN26), [Auto],")
    print("or starting with Bull_ / Rec_ / FINAL_.")
    print("------------------------------------------------------\n")
    
    await cleanup_strike()
    await cleanup_tradingview()
    print("\n✅ NUCLEAR CLEANUP COMPLETE.")

if __name__ == "__main__":
    asyncio.run(main())
