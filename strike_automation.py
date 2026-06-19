import sys
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import os
import time
import csv
import re
import sys
import argparse
from datetime import datetime


def _is_file_from_today(path):
    """True if `path` was last modified today — used to reject STALE LATEST_
    watchlist files so a prior run's picks are never uploaded as if fresh."""
    try:
        return datetime.fromtimestamp(os.path.getmtime(path)).date() == datetime.now().date()
    except Exception:
        return False


# ==========================================
# CONFIGURATION
# ==========================================
# BUG-FIX: Use script-directory-relative path (not CWD which changes under Streamlit)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Source of truth: Generated_Watchlists TXT files (same as TradingView)
# This ensures Strike.Money and TradingView ALWAYS get identical watchlists.
WATCHLIST_DIR = os.path.join(_SCRIPT_DIR, "Generated_Watchlists")

STRIKE_URL = "https://web.strike.money/"
RRG_URL = "https://web.strike.money/rrg"
WATCHLIST_URL = "https://web.strike.money/watchlist"
# BUG-FIX: Use _SCRIPT_DIR instead of os.getcwd()
USER_DATA_DIR = os.path.join(_SCRIPT_DIR, "strike_user_data")

# Watchlist Name Mapping (Base Names) — maps TXT base names to Strike watchlist names
# The TXT filename in Generated_Watchlists will be: {base_name}-{DDMMMYY}.txt
# These MUST match the base names used by watchlist_manager.py WATCHLIST_MAP values.
WATCHLIST_BASE_NAMES = [
    "Bull_EarlyBird",
    "Bull_Hunter",
    "Bull_Pullback",
    "Bull_StrongLeader",
    "Bull_Picks_All",
    "Rec_Climax_Bounce",
    "Rec_Early_Bird",
    "Rec_RS_Survivor",
    "Recovery_Picks_All",
    "Golden_Matcher_Picks",
    "XRay_Picks",
    "Portfolio"
]

# Legacy: kept for RRG scan compatibility (not used in watchlist upload)
INPUT_FILES = [
    "FINAL_Hunter_Picks.csv",
    "FINAL_Pullback_Picks.csv",
    "FINAL_EarlyBird_Picks.csv",
    "FINAL_Leader_Picks.csv",
    "FINAL_Recovery_RSLeaders.csv",
    "FINAL_Recovery_ClimaxBounce.csv",
    "FINAL_Recovery_EarlyBirds.csv"
]

def get_dated_name(base_name):
    """Returns 'Name-DDMMMYY', e.g., 'Hunter-09FEB26'"""
    date_str = datetime.now().strftime("%d%b%y").upper()
    return f"{base_name}-{date_str}"

async def delete_watchlist(page, wl_name):
    """
    Attempts to delete a watchlist by name. 
    Assumes logic: Select WL -> Click Settings/Delete if available.
    """
    print(f"      [DEBUG] Checking for existing watchlist to delete: {wl_name}")
    try:
        # 1. Open Dropdown
        dropdown = page.locator(".rs-watchListDropdown .rs-picker-toggle, .rs-picker-toggle").first
        if await dropdown.is_visible():
            await dropdown.click()
            await page.wait_for_timeout(1000)
            
            # 2. Check if WL exists in list
            import re
            # Strike appends " (N)" symbol counts. Match the name with or without the count suffix safely.
            wl_item = page.locator("div[role='option'], a[role='option'], .rs-picker-select-menu-item, li").filter(
                has_text=re.compile(rf"^\s*{re.escape(wl_name)}(?:\s*\(\d+\))?\s*$", re.IGNORECASE)
            ).first
            
            if await wl_item.is_visible():
                print(f"      [DEBUG] Watchlist '{wl_name}' found. Selecting to delete...")
                await wl_item.click()
                await page.wait_for_timeout(2000) # Wait for load
                
                # 3. Look for Delete Mechanism
                # First, ensure any dropdown is closed by hitting Escape
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
                
                print("      [DEBUG] Looking for 'More' options (three dots)...")
                more_btn = page.locator("[class*='marketOverviewContainer_moreBtn']")
                if await more_btn.count() > 0:
                    await more_btn.first.click(force=True)
                    await page.wait_for_timeout(1000)
                else:
                    print("      [DEBUG] 'More options' button not found. Assuming direct Delete button.")
                
                # Broad selector for the delete button
                delete_btn = page.locator("text='Delete Watchlist', text='Delete WatchList', text='Delete'").last
                
                if await delete_btn.count() > 0:
                    print("      [DEBUG] Found Delete button. Clicking...")
                    await delete_btn.click(force=True)
                    await page.wait_for_timeout(1000)
                    
                    # Confirm Delete Modal
                    confirm_btn = page.locator("button:has-text('Delete'), button:has-text('Confirm'), button:has-text('Yes')").last
                    if await confirm_btn.count() > 0:
                        await confirm_btn.click(force=True)
                        print(f"      [SUCCESS] Deleted watchlist: {wl_name}")
                        
                        # Wait for the Delete Watchlist modal to close
                        try:
                            await page.locator(".rs-modal-wrapper").first.wait_for(state="hidden", timeout=5000)
                        except Exception:
                            print("      [!] WARNING: Delete modal may still be open. Forcing close...")
                            await page.keyboard.press("Escape")
                            await page.wait_for_timeout(1000)
                            # Ultimate fallback: Nuke from DOM
                            await page.evaluate("""
                                document.querySelectorAll('.rs-modal-wrapper, .rs-modal-backdrop').forEach(el => el.remove());
                            """)
                            
                        await page.wait_for_timeout(1000)
                    else:
                        print("      [!] Delete confirmation not found. Cancelling.")
                        await page.keyboard.press("Escape")
                        await page.evaluate("""
                            document.querySelectorAll('.rs-modal-wrapper, .rs-modal-backdrop').forEach(el => el.remove());
                        """)
                else:
                    print("      [!] Could not find Delete button for active watchlist. Dumping HTML for debug...")
                    try:
                        with open(os.path.join(_SCRIPT_DIR, f"debug_strike_delete_fail.html"), "w", encoding="utf-8") as f:
                            f.write(await page.content())
                        await page.screenshot(path=os.path.join(_SCRIPT_DIR, f"debug_strike_delete_fail.png"))
                    except:
                        pass
            else:
                # Watchlist not in list, nothing to do
                # Close dropdown
                await page.keyboard.press("Escape")
        else:
            print("      [!] Dropdown not found for deletion.")
            
    except Exception as e:
        print(f"      [!] Error deleting watchlist {wl_name}: {e}")

async def cleanup_old_watchlists(page, base_name):
    """
    Scans the watchlist dropdown for any dated names (e.g., Hunter-10FEB26) 
    that match the base_name but are NOT from today, and deletes them.
    """
    print(f"      [DEBUG] Cleaning up old dated watchlists for {base_name}...")
    current_today_upper = get_dated_name(base_name).upper()
    
    # Relaxed pattern for "BaseName-DDMMMYY" anywhere in the string
    pattern = re.compile(rf"{re.escape(base_name)}-\d{{2}}[A-Z]{{3}}\d{{2}}", re.IGNORECASE)
    
    try:
        # 1. Open Dropdown
        dropdown = page.locator(".rs-watchListDropdown .rs-picker-toggle, .rs-picker-toggle").first
        if not await dropdown.is_visible():
            return
            
        await dropdown.click()
        await page.wait_for_timeout(1000)
        
        # 2. Get all menu items
        # Options are usually inside the picker-menu
        menu_items = page.locator(".rs-picker-select-menu-item, .rs-dropdown-item")
        count = await menu_items.count()
        
        to_delete = []
        for i in range(count):
            item_text = await menu_items.nth(i).inner_text()
            item_text = re.sub(r'\s+', ' ', item_text).strip()
            
            # If it matches pattern and is NOT today and is NOT the [Auto] legacy
            if pattern.search(item_text) and current_today_upper not in item_text.upper():
                to_delete.append(item_text)
            elif f"{base_name} [Auto]".upper() in item_text.upper():
                to_delete.append(item_text)
                
        # Close dropdown first (since delete_watchlist will open it again per item)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)
        
        if to_delete:
            print(f"      [DEBUG] Found {len(to_delete)} old watchlists to purge: {to_delete}")
            for wl in to_delete:
                await delete_watchlist(page, wl)
        else:
            print(f"      [DEBUG] No stale dated lists found for {base_name}.")
            
    except Exception as e:
        print(f"      [!] Error during pattern cleanup for {base_name}: {e}")

async def setup_rrg_dashboard(page):
    print("\n   [setup_rrg_dashboard] Starting Dashboard Setup...")
    
    try:
        # 1. Ensure we are on the right URL
        if "rrg" not in page.url:
            await page.goto("https://web.strike.money/rrg", wait_until="domcontentloaded")
            await page.wait_for_selector(".rrg_table_section", timeout=20000)

        # 2. Open Universe Picker
        print("      [DEBUG] Locating Universe Picker...")
        
        # Try finding the picker that is likely the Universe picker
        picker = page.locator(".rs-picker-toggle").filter(has_text="Indices").first
        if not await picker.is_visible():
             # Fallback: try finding any picker in the header
             picker = page.locator(".header .rs-picker-toggle").first
        
        if not await picker.is_visible():
            print("      [!] Universe picker NOT FOUND. Taking screenshot...")
            await page.screenshot(path="debug_no_picker.png")
            return

        print(f"      [DEBUG] Clicking Picker: {await picker.inner_text()}")
        await picker.click()
        
        # 3. Wait for Menu to Appear
        # The menu items are inside a listbox. We wait for that.
        menu_loc = page.locator("div[role='listbox']").last
        try:
             await menu_loc.wait_for(state="visible", timeout=5000)
             print("      [DEBUG] Picker Menu (Listbox) IS VISIBLE.")
        except:
             print("      [!] Picker Menu did NOT appear. Retrying click...")
             await picker.click(force=True)
             await menu_loc.wait_for(state="visible", timeout=5000)

        # 4. Find Options
        # Options are div[role="option"]
        options = menu_loc.locator("div[role='option']")
        count = await options.count()
        print(f"      [DEBUG] Found {count} options in menu.")
        
        if count == 0:
             print("      [!] No options found. Dumping HTML...")
             html_content = await menu_loc.inner_html()
             with open("debug_menu_dump_empty.html", "w", encoding="utf-8") as f:
                f.write(html_content)

        target_option = None
        
        for i in range(count):
            opt = options.nth(i)
            # The text might be in a span or div inside the option
            text = await opt.inner_text()
            print(f"         [Option {i}] {text.strip()}")
            
            text_lower = text.lower()
            if "nifty 500" in text_lower:
                target_option = opt
                break
            elif "stocks" in text_lower and not target_option:
                target_option = opt

        if target_option:
            print(f"      [DEBUG] Selecting: {await target_option.inner_text()}")
            await target_option.click()
            await page.wait_for_timeout(2000) 
            
            current_text = await picker.inner_text()
            print(f"      [DEBUG] Universe is now: {current_text}")
            
            if "Indices" in current_text and "Only" in current_text:
                 print("      [!] WARNING: Selection might have failed. Still showing Indices.")
        else:
            print("      [!] 'Nifty 500' or 'Stocks' option NOT FOUND.")
            await page.screenshot(path="debug_options_missing.png")

    except Exception as e:
        print(f"      [!] Error in setup_rrg_dashboard: {e}")
        import traceback
        traceback.print_exc()
        await page.screenshot(path="debug_setup_error.png")

async def extract_rrg_status(page, symbol):
    """
    On the RRG page, search for the symbol and extract the quadrant status 
    from the table row class.
    """
    try:
        # 1. Clear and Type into Search Box
        # Fixed selector: .sidebar .header .news-search input
        search_box = page.locator('.sidebar .header .news-search input')
        
        # Ensure search box is visible
        if not await search_box.is_visible():
            print("      [!] Search box not visible.")
            return "Error"

        await search_box.click()
        await search_box.fill("") # Clear first
        await search_box.type(symbol, delay=50) # Type slowly
        
        # Wait for the table to update
        # We assume the first row will change to the searched symbol
        await page.wait_for_timeout(1000) 

        # 2. Find the row corresponding to the symbol
        # The table updates. We look for a row where the text contains the symbol.
        # Selector for the first row in the table body: .rrg_table_section table tbody tr
        first_row = page.locator('.rrg_table_section table tbody tr').first
        
        if not await first_row.count():
            print(f"      [!] Row for {symbol} NOT FOUND. Capturing debug info...")
            await page.screenshot(path=f"debug_failed_{symbol}.png")
            with open(f"debug_failed_{symbol}.html", "w", encoding="utf-8") as f:
                f.write(await page.content())
            return "Not Found"

        # 3. Get Class Attribute
        # The class contains the status: "leading false", "weakening false", etc.
        class_attr = await first_row.get_attribute("class")
        if not class_attr:
            print(f"      [!] class_attr missing for {symbol}.")
            await page.screenshot(path=f"debug_failed_attr_{symbol}.png")
            return "Unknown"

        class_attr = class_attr.lower()
        if "leading" in class_attr: return "Leading"
        if "weakening" in class_attr: return "Weakening"
        if "lagging" in class_attr: return "Lagging"
        if "improving" in class_attr: return "Improving"
        
        return "Unknown"

    except Exception as e:
        print(f"      [!] Error extracting RRG for {symbol}: {e}")
        return "Error"

async def create_strike_csv_from_txt(txt_file, base_csv_path, chunk_size=49):
    """
    BUG-FIX: Read symbols from the Generated_Watchlists TXT file (same source as TradingView).
    TXT format: comma-separated NSE:SYMBOL entries (e.g. NSE:RELIANCE,NSE:TCS,...)
    Strike import needs plain symbols without the NSE: prefix, one per row with a 'Symbol' header.
    Automatically splits into multiple CSVs if symbol count exceeds chunk_size.
    Returns list of tuples: [(csv_path, sym_count, suffix), ...]
    """
    try:
        with open(txt_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        if not content:
            print(f"      [!] TXT file is empty: {txt_file}")
            return []

        # Parse comma-separated NSE:SYMBOL list
        raw_symbols = [s.strip() for s in content.split(',') if s.strip()]
        clean_symbols = [
            s.replace('NSE:', '').replace('BSE:', '').strip()
            for s in raw_symbols
            if s.replace('NSE:', '').replace('BSE:', '').strip()
        ]

        if not clean_symbols:
            print(f"      [!] No valid symbols parsed from: {txt_file}")
            return []

        chunks = [clean_symbols[i:i + chunk_size] for i in range(0, len(clean_symbols), chunk_size)]
        results = []

        for idx, chunk in enumerate(chunks):
            suffix = f"-{idx+1}" if len(chunks) > 1 else ""
            csv_path = base_csv_path.replace(".csv", f"{suffix}.csv")

            # Write temp CSV with 'Symbol' header for Strike import
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Symbol"])
                for s in chunk:
                    writer.writerow([s])

            results.append((csv_path, len(chunk), suffix))

        return results

    except Exception as e:
        print(f"      [!] Error reading TXT file {txt_file}: {e}")
        return []


async def upload_watchlists(page):
    """
    Auto-upload watchlists to Strike.Money.
    BUG-FIX: Now reads from Generated_Watchlists/*.txt (SAME source as TradingView)
    so both platforms always receive identical watchlists.
    """
    print("\n   [upload_watchlists] Starting Watchlist Sync (TXT Source Mode)...")
    print(f"      [INFO] Reading from: {WATCHLIST_DIR}")

    if not os.path.exists(WATCHLIST_DIR):
        print(f"      [!] Generated_Watchlists directory not found: {WATCHLIST_DIR}")
        print("      [!] Run 'Generate Watchlists' (Phase 5) before syncing to Strike.")
        return

    # 1. Ensure we are on the Watchlist Page
    if "watch-list" not in page.url and "dashboard" not in page.url:
        print("      [DEBUG] Navigating to Watchlist URL...")
        await page.goto(WATCHLIST_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

    # 2. Click Watchlist Tab if needed
    try:
        watchlist_tab = page.locator("div.rs-nav-item:has-text('Watchlist')")
        if await watchlist_tab.is_visible():
            classes = await watchlist_tab.get_attribute("class")
            if "active" not in classes:
                print("      [DEBUG] Clicking 'Watchlist' tab...")
                await watchlist_tab.click()
                await page.wait_for_timeout(3000)
    except Exception as e:
        print(f"      [!] Error checking tabs: {e}")

    date_suffix = datetime.now().strftime("%d%b%y").upper()

    for base_name in WATCHLIST_BASE_NAMES:
        # --- DELETION IS NOW HERE TO ALWAYS PURGE STALE LISTS, EVEN IF NO NEW PICKS ---
        await cleanup_old_watchlists(page, base_name)
        
        # Locate the dated TXT file (e.g. Hunter-22APR26.txt)
        txt_filename = f"{base_name}-{date_suffix}.txt"
        txt_path = os.path.join(WATCHLIST_DIR, txt_filename)

        # Fallback: LATEST_ static file if dated file missing — but ONLY if it
        # is FRESH (written today). STALE-WATCHLIST BUG FIX (19 Jun 2026): when
        # today's scan produced 0 picks the generator writes no dated/LATEST
        # file, so a stale LATEST_ from a prior run would otherwise be uploaded
        # under today's date — resurrecting last week's picks (e.g.
        # Rec_Climax_Bounce showed 3 symbols from 12 Jun). Never upload stale.
        if not os.path.exists(txt_path):
            fallback = os.path.join(WATCHLIST_DIR, f"LATEST_{base_name}.txt")
            if os.path.exists(fallback) and _is_file_from_today(fallback):
                print(f"      [WARN] Dated file not found ({txt_filename}), using FRESH LATEST fallback.")
                txt_path = fallback
            elif os.path.exists(fallback):
                _age_days = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(fallback))).days
                print(f"      [!] LATEST_{base_name}.txt is STALE ({_age_days}d old) — "
                      f"today's scan produced no picks. SKIPPING (will not upload "
                      f"prior-run symbols under today's date). The cleanup above "
                      f"already purged the old list.")
                continue
            else:
                print(f"      [!] No TXT file found for {base_name} (tried {txt_filename} and LATEST_{base_name}.txt). Skipping.")
                continue
        print(f"\n   >> Checking file: {os.path.basename(txt_path)}")

        # Build temp CSV from TXT
        base_csv_path = os.path.join(_SCRIPT_DIR, f"temp_strike_{base_name}.csv")
        chunks_info = await create_strike_csv_from_txt(txt_path, base_csv_path, chunk_size=49)

        if not chunks_info:
            print(f"      [!] No symbols to upload for {base_name}. Skipping.")
            continue

        for clean_csv_path, sym_count, suffix in chunks_info:
            wl_name = get_dated_name(base_name) + suffix
            print(f"\n   >> Processing: {wl_name} ({sym_count} symbols)")

            # We can delete any specifically conflicting watchlist, though cleanup_old_watchlists already ran
            await delete_watchlist(page, wl_name)

            await page.wait_for_timeout(1000)

            try:
                # 3. Open Watchlist Dropdown & Check/Create
                dropdown_toggle = page.locator(".rs-watchListDropdown .rs-picker-toggle, .rs-picker-toggle").first

                if await dropdown_toggle.is_visible():
                    print("      [DEBUG] Opening Watchlist Dropdown...")
                    await dropdown_toggle.click()
                    await page.wait_for_timeout(1000)

                    # Check if watchlist already exists
                    existing_wl = page.locator(f"text='{wl_name}'").first
                    if await existing_wl.is_visible():
                        print(f"      [DEBUG] Watchlist '{wl_name}' found. Selecting it...")
                        await existing_wl.click()
                        await page.wait_for_timeout(2000)
                    else:
                        print(f"      [DEBUG] Watchlist '{wl_name}' not found. Creating new...")

                        # Scroll to bottom to find "+ Create Watchlist"
                        menu = page.locator(".rs-picker-menu, .rs-dropdown-menu").last
                        if await menu.is_visible():
                            await menu.evaluate("el => el.scrollTop = el.scrollHeight")
                            await page.wait_for_timeout(500)

                        # Find Create button
                        create_item = page.locator("text='+Create Watchlist'").first
                        if not await create_item.is_visible():
                            create_item = page.locator("text='Create new watchlist'").first
                        if not await create_item.is_visible():
                            create_item = page.locator("text='+ Create Watchlist'").first

                        if await create_item.is_visible():
                            print("      [DEBUG] Clicking '+Create Watchlist'...")
                            await create_item.click()
                            await page.wait_for_timeout(1000)

                            name_input = page.locator("input[placeholder='Enter text here...']").first
                            if await name_input.is_visible():
                                await name_input.fill(wl_name)

                                create_confirm = page.locator("button:has-text('Create Watchlist')").last
                                if not await create_confirm.is_visible():
                                    create_confirm = page.locator("button:has-text('Create')").last

                                await create_confirm.click()
                                print(f"      [DEBUG] Clicked Create for: {wl_name}")
                                await page.wait_for_timeout(1500)
                                
                                # Check for "Watchlist already exists" error before waiting
                                error_msg = page.locator("text='Watchlist already exists'")
                                if await error_msg.is_visible():
                                    print("      [!] Watchlist already exists (Modal). Closing modal...")
                                    cancel_btn = page.locator("button:has-text('Cancel')").first
                                    if await cancel_btn.is_visible():
                                        await cancel_btn.click()
                                    else:
                                        await page.keyboard.press("Escape")
                                    await page.wait_for_timeout(1000)
                                    await dropdown_toggle.click()
                                    await page.wait_for_timeout(1000)
                                    await page.locator(f"text='{wl_name}'").first.click()
                                    await page.wait_for_timeout(2000)
                                else:
                                    # Wait for the Create Watchlist modal to close normally
                                    try:
                                        await page.locator(".rs-modal-wrapper").first.wait_for(state="hidden", timeout=3000)
                                    except Exception:
                                        print("      [!] WARNING: Create modal may still be open. Forcing close...")
                                        cancel_btn = page.locator(".rs-modal-wrapper button:has-text('Cancel')").first
                                        if await cancel_btn.is_visible():
                                            await cancel_btn.click()
                                        else:
                                            # RSuite close icon
                                            x_btn = page.locator(".rs-modal-header-close").first
                                            if await x_btn.is_visible():
                                                await x_btn.click()
                                            else:
                                                await page.keyboard.press("Escape")
                                        await page.wait_for_timeout(1000)
                                        # Ultimate fallback: Nuke from DOM
                                        await page.evaluate("""
                                            document.querySelectorAll('.rs-modal-wrapper, .rs-modal-backdrop').forEach(el => el.remove());
                                        """)
                            else:
                                print("      [!] Name input not found in Create Modal. Dumping debug info...")
                                await page.screenshot(path="debug_create_modal.png")
                                with open("debug_create_modal.html", "w", encoding="utf-8") as f:
                                    f.write(await page.content())
                        else:
                            print("      [!] '+Create Watchlist' item not found in dropdown.")
                else:
                    print("      [!] Watchlist dropdown toggle not found.")

                # 5. Click Import
                import_found = False
                for selector in [
                    "div:has-text('Import')",
                    ".marketOverviewContainer_importBtn__tSpvR",
                    "button:has-text('Import')"
                ]:
                    import_btn = page.locator(selector).nth(0)
                    if await import_btn.is_visible():
                        print(f"      [DEBUG] Clicking Import using selector: {selector}")
                        try:
                            await import_btn.click()
                            await page.wait_for_timeout(2000)

                            upload_btn = page.locator("button:has-text('Upload File'), div:has-text('Upload File')").first
                            if await upload_btn.is_visible():
                                import_found = True
                                print("      [DEBUG] Import Modal Opened!")
                                break
                            else:
                                print("      [DEBUG] Modal not detected. Retrying with force=True...")
                                await import_btn.click(force=True)
                                await page.wait_for_timeout(2000)
                                if await upload_btn.is_visible():
                                    import_found = True
                                    print("      [DEBUG] Import Modal Opened (after force click)!")
                                    break
                        except Exception as e:
                            print(f"      [!] Click failed for {selector}: {e}")

                if import_found:
                    # 6. Click Upload File inside Modal
                    upload_btn = page.locator("button:has-text('Upload File')").first
                    if not await upload_btn.is_visible():
                        upload_btn = page.locator("div:has-text('Upload File')").first

                    if await upload_btn.is_visible():
                        print("      [DEBUG] Found 'Upload File' button...")
                        async with page.expect_file_chooser() as fc_info:
                            await upload_btn.click()

                        file_chooser = await fc_info.value
                        await file_chooser.set_files(clean_csv_path)
                        print(f"      [SUCCESS] Uploaded {sym_count} symbols to '{wl_name}'")

                        await page.wait_for_timeout(4000)

                        # Close Modal
                        close_btn = page.locator("button:has-text('Done')").first
                        if await close_btn.is_visible():
                            await close_btn.click()
                        else:
                            # Try standard RSuite close button
                            x_btn = page.locator(".rs-modal-header-close").first
                            if await x_btn.is_visible():
                                await x_btn.click()
                            else:
                                await page.keyboard.press("Escape")
                                await page.wait_for_timeout(500)
                                await page.keyboard.press("Escape")
                                
                        # Wait for modal to actually close so it doesn't intercept the next loop
                        try:
                            await page.locator(".rs-modal-wrapper").first.wait_for(state="hidden", timeout=5000)
                        except:
                            print("      [!] WARNING: Modal may still be open, attempting force close...")
                            await page.keyboard.press("Escape")
                            await page.wait_for_timeout(1000)
                            # Ultimate fallback: Nuke from DOM
                            await page.evaluate("""
                                document.querySelectorAll('.rs-modal-wrapper, .rs-modal-backdrop').forEach(el => el.remove());
                            """)
                    else:
                        print("      [!] 'Upload File' button not found in Import modal.")
                        with open(os.path.join(_SCRIPT_DIR, f"debug_import_modal_{wl_name}.html"), "w", encoding="utf-8") as f:
                            f.write(await page.content())
                else:
                    print("      [!] 'Import' button not found or did not open modal.")
                    debug_path = os.path.join(_SCRIPT_DIR, f"debug_import_fail_{wl_name}.html")
                    if not os.path.exists(debug_path):
                        with open(debug_path, "w", encoding="utf-8") as f:
                            f.write(await page.content())

            except Exception as e:
                print(f"      [!] Error: {e}")
                await page.screenshot(path=os.path.join(_SCRIPT_DIR, f"debug_error_{wl_name}.png"))

            # Cleanup temp CSV
            if os.path.exists(clean_csv_path):
                try:
                    os.remove(clean_csv_path)
                except Exception as e:
                    print(f"      [!] Could not remove temp file (harmless): {e}")



async def run_rrg_scan(page):
    print("\n   [run_rrg_scan] Starting RRG Quadrant Check...")
    
    # 2. NAVIGATE TO RRG PAGE
    print(f">> Navigating to RRG Dashboard: {RRG_URL}")
    try:
        if "rrg" not in page.url:
            await page.goto(RRG_URL, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print(f"   [!] Navigation timeout (proceeding anyway): {e}")
    
    await page.wait_for_timeout(5000) # Give it time to render React
    
    # 3. SETUP UNIVERSE
    await setup_rrg_dashboard(page)

    # 3. PROCESS FILES
    files_to_process = {
        "FINAL_Hunter_Picks.csv": "FINAL_Hunter_Picks_RRG.csv",
        "FINAL_Leader_Picks.csv": "FINAL_Leader_Picks_RRG.csv",
        "FINAL_EarlyBird_Picks.csv": "FINAL_EarlyBird_Picks_RRG.csv",
        "FINAL_Pullback_Picks.csv": "FINAL_Pullback_Picks_RRG.csv",
        "FINAL_Recovery_RSLeaders.csv": "FINAL_Recovery_RSLeaders_RRG.csv",
        "FINAL_Recovery_ClimaxBounce.csv": "FINAL_Recovery_ClimaxBounce_RRG.csv",
        "FINAL_Recovery_EarlyBirds.csv": "FINAL_Recovery_EarlyBirds_RRG.csv"
    }

    for input_file, output_file in files_to_process.items():
        print(f"\n>> Processing: {input_file}")
        
        if not os.path.exists(input_file):
            print(f"❌ ERROR: Input file not found: {input_file}")
            continue

        try:
            # Read CSV
            with open(input_file, 'r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                fieldnames = reader.fieldnames
                rows = list(reader)
            
            # Check if RRG_Quadrant field needs to be added
            if 'RRG_Quadrant' not in fieldnames:
                fieldnames.append('RRG_Quadrant')

            # Open Output CSV
            with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                writer.writeheader()
                
                total_stocks = len(rows)
                count = 0
                
                for row in rows:
                    count += 1
                    symbol = row.get('Symbol')
                    
                    if not symbol:
                        # Write row as is if symbol missing
                        writer.writerow(row)
                        continue

                    print(f"   [{count}/{total_stocks}] {symbol}: ", end="", flush=True)
                    
                    quadrant = await extract_rrg_status(page, symbol)
                    
                    print(f"{quadrant}")
                    row['RRG_Quadrant'] = quadrant
                    writer.writerow(row)
                    
            print(f">> Saved results to {output_file}")

        except Exception as e:
            print(f"❌ ERROR processing {input_file}: {e}")

async def run_pipeline():
    # Parse Arguments
    parser = argparse.ArgumentParser(description='Strike Automation')
    parser.add_argument('--mode', type=str, default='rrg', help='Mode: rrg or watchlist')
    args, unknown = parser.parse_known_args()
    
    mode = args.mode.lower()

    print("="*60)
    print(f"🚀 STRIKE.MONEY AUTOMATION COMPANION (Mode: {mode.upper()})")
    print("="*60)

    # Create a local user data directory to save login session
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)

    async with async_playwright() as p:
        # Launch Persistent Context (Saves cookies/login)
        print(f">> Launching Chrome (User Data: {USER_DATA_DIR})...")
        
        try:
            browser = await p.chromium.launch_persistent_context(
                USER_DATA_DIR,
                headless=False,
                channel="chrome", # Try to use installed Chrome
                args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport=None # adaptive viewport
            )
        except Exception as e:
            print(f"Error launching Chrome: {e}")
            print("Falling back to standard Chromium...")
            browser = await p.chromium.launch_persistent_context(
                USER_DATA_DIR,
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )

        page = browser.pages[0] if browser.pages else await browser.new_page()

        # 1. LOGIN PHASE (Common)
        print(f"\n>> Navigating to {STRIKE_URL}")
        await page.goto(STRIKE_URL)
        
        print("\n" + "!"*60)
        print("WAITING FOR LOGIN (Auto-Detect)")
        print("Please log in to Strike.money in the browser window if not already logged in.")
        print("Script will proceed automatically once Dashboard is detected...")
        print("!"*60 + "\n")
        
        try:
            # Wait for the Login button to DISAPPEAR
            # This confirms the user is actually authenticated
            print(">> Waiting for user to authenticate...")
            
            # Wait up to 5 minutes for user to login manually
            import time
            start_time = time.time()
            logged_in = False
            print(">> Checking authentication state...")
            while time.time() - start_time < 300: # 5 minutes timeout
                login_btn_count = await page.locator("a:has-text('Login'), button:has-text('Login')").count()
                if login_btn_count > 0:
                    print(">> Please manually log in via the browser window... (Waiting)")
                    await page.wait_for_timeout(5000) # wait 5 secs before checking again
                else:
                    # Double check if we see user-specific elements like a profile icon or just no Login
                    print(">> LOGIN SUCCESSFUL! User is authenticated.")
                    logged_in = True
                    break
            
            if not logged_in:
                print(">> ABORTING: Login timed out after 5 minutes.")
                await browser.close()
                return
            await page.wait_for_timeout(4000) # Buffer after login redirect
        except Exception as e:
            print(f">> ERROR: Login detection timed out or failed: {e}")
            print(">> ABORTING: Strike.money requires you to be logged in to create watchlists.")
            print(">> Please run the script again and manually log in when the browser opens.")
            await browser.close()
            return

        print(">> Proceeding with Automation...\n")

        # 2. DISPATCH MODE
        if mode == "watchlist":
            await upload_watchlists(page)
        else:
            await run_rrg_scan(page)

        print("\n>> All tasks completed.")
        print(">> Closing browser in 5 seconds...")
        await asyncio.sleep(5)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_pipeline())
