import asyncio
from playwright.async_api import async_playwright
import os
import sys
import time
import re

# ==========================================
# CONFIGURATION
# ==========================================
WATCHLIST_DIR = os.path.join(os.getcwd(), "Generated_Watchlists")
TV_URL = "https://in.tradingview.com/chart/"
# Versioning to v2 to bypass existing profile corruption
USER_DATA_DIR = os.path.join(os.getcwd(), "tv_user_data_v2")

import datetime

# Files to Import
# We use base names. The script will append DATE suffix (e.g., Hunter-10FEB26.txt)
TARGET_BASES = [
    "Hunter",
    "Pullback",
    "EarlyBird",
    "Leader"
]

def cleanup_singleton_lock():
    """Nuclear Cleanup: Removes all stale locks, ports, and SQLite journal files that trigger TargetClosedError."""
    print("🧹 Starting Nuclear Profile Cleanup...")
    
    # 1. Direct targets (Root level)
    root_locks = ["SingletonLock", "SingletonCookie", "SingletonSocket", "DevToolsActivePort"]
    for lock in root_locks:
        path = os.path.join(USER_DATA_DIR, lock)
        if os.path.exists(path):
            try:
                os.remove(path)
                print(f"   🗑️ Root Lock Removed: {lock}")
            except: pass

    # 2. Recursive cleanup for Journals and WALs (Common crash culprits in Chromium)
    # We look for files ending in -journal, -wal, -shm, or named LOCK
    crash_patterns = ["-journal", "-wal", "-shm", "LOCK"]
    cleaned_count = 0
    
    try:
        for root, dirs, files in os.walk(USER_DATA_DIR):
            for file in files:
                if any(file.endswith(p) or file == p for p in crash_patterns):
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        cleaned_count += 1
                    except:
                        pass
        if cleaned_count > 0:
            print(f"   🧼 Deep Clean: Removed {cleaned_count} stagnant artifact files.")
    except Exception as e:
        print(f"   ⚠️ Recursive cleanup notice: {e}")

async def run_sync():
    print("🚀 STARTING TRADINGVIEW WATCHLIST SYNC...")
    
    if not os.path.exists(WATCHLIST_DIR):
        print(f"❌ Error: Watchlist directory not found: {WATCHLIST_DIR}")
        return

    # 0. Clean up locks before starting
    cleanup_singleton_lock()

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with async_playwright() as p:
                # Launch with persistent context to keep login
                print(f"📂 User Data Dir: {USER_DATA_DIR} (Attempt {attempt+1}/{max_retries})")
                
                # Use absolute paths and ensure they are normalized for Windows
                clean_user_dir = os.path.normpath(os.path.abspath(USER_DATA_DIR))
                
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=clean_user_dir,
                    headless=False,
                    channel="chrome", # Switching to real Chrome for better auth/persistence
                    args=[
                        "--start-maximized",
                        "--disable-blink-features=AutomationControlled",
                        # Removed --no-sandbox as it can sometimes trigger Guest mode on Windows
                        "--disable-dev-shm-usage",
                        "--disable-gpu", 
                        "--disable-software-rasterizer",
                    ],
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    no_viewport=True,
                    timeout=60000 
                )
                
                # Verify we aren't in a guest/temporary state
                print(f"✅ Browser session active (Profile: {os.path.basename(clean_user_dir)})")
                print("⚠️  PLEASE LOG IN TO TRADINGVIEW NOW IF NOT ALREADY LOGGED IN.")
                print("⚠️  This is a one-time login for the new stable profile (v2).")
                
                # If we got here, launch succeeded
                await process_sync(context)
                return # Exit successfully

        except Exception as e:
            print(f"⚠️ Launch attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                print("🔄 Retrying in 3 seconds...")
                await asyncio.sleep(3)
                cleanup_singleton_lock() # Try cleaning locks again
            else:
                print("❌ All launch attempts failed. Please ensure no hidden Chrome processes are running.")
                raise e

async def dismiss_modals(page):
    """Aggressively closes any TradingView popups or modals that block the UI."""
    modal_selectors = [
        "button[data-name='close']",
        ".tv-dialog__close",
        "[data-role='modal-container'] button:has-text('Close')",
        "button[aria-label='Close']",
        ".js-dialog__close"
    ]
    for selector in modal_selectors:
        try:
            close_btn = page.locator(selector).first
            if await close_btn.is_visible():
                print(f"      🧹 Closing modal using: {selector}")
                await close_btn.click()
                await page.wait_for_timeout(500)
        except:
            pass

async def wait_for_login(page, context):
    """Pauses and waits for the user to log in manually. Injects Proceed/Reset buttons for override."""
    print("🕵️  Detecting Login Status...")
    start_time = time.time()
    max_wait = 360 # Increased to 6 mins
    
    while (time.time() - start_time) < max_wait:
        # 0. RE-INJECT SAFETY RESET (If missing)
        try:
            await page.evaluate("""() => {
                if (document.getElementById('ai-control-panel')) return;
                
                const container = document.createElement('div');
                container.id = 'ai-control-panel';
                container.style = 'position: fixed; top: 10px; right: 10px; z-index: 999999;';
                
                const resetBtn = document.createElement('button');
                resetBtn.id = 'ai-reset-btn';
                resetBtn.innerHTML = 'RESET AUTH (Emergency)';
                resetBtn.style = 'padding: 8px 12px; background: rgba(244,67,54,0.3); color: white; border: 1px solid white; border-radius: 4px; cursor: pointer; font-size: 10px; font-weight: bold; font-family: sans-serif; opacity: 0.6;';
                resetBtn.onmouseover = () => { resetBtn.style.opacity = '1.0'; resetBtn.style.background = '#f44336'; };
                resetBtn.onmouseout = () => { resetBtn.style.opacity = '0.6'; resetBtn.style.background = 'rgba(244,67,54,0.3)'; };
                resetBtn.onclick = () => { 
                    resetBtn.innerHTML = '🔄 RESETTING...'; 
                    window.location.href = 'https://in.tradingview.com/logout/';
                    resetBtn.dataset.clicked = 'true'; 
                };
                
                container.appendChild(resetBtn);
                document.body.appendChild(container);
            }""")
        except:
            pass

        # 0.5 DIAGNOSTIC: Print URL and Title
        try:
            url = page.url
            title = await page.title()
            print(f"      [DEBUG] Current URL: {url[:60]}... | Title: {title[:30]}")
        except:
            pass

        # 1. Reset Override (User clicked the red button)
        reset_click = page.locator("#ai-reset-btn[data-clicked='true']").first
        if await reset_click.count() > 0:
            print("🔄 Reset Requested. Clearing cookies and redirecting...")
            await context.clear_cookies()
            await page.evaluate("localStorage.clear(); sessionStorage.clear();")
            await page.goto("https://www.tradingview.com/chart/")
            await page.evaluate("document.getElementById('ai-reset-btn').dataset.clicked = 'false'; document.getElementById('ai-reset-btn').innerHTML = 'RESET AUTH (Emergency)';")
            continue

        # 2. Automatic Login Detection (User Profile Icon or Chart Layout)
        # Check for core layout areas that only fully load on the chart view when authenticated
        user_menu = page.locator("button[data-name='user-menu'], button[data-name='header-toolbar-user-menu'], .layout__area--right, .layout__area--left, div[class*='chart-gui-wrapper'], div[data-name='legend']").first
        if await user_menu.is_visible():
            print("✅ Login Detected (Workspace/User Menu Visible)! Proceeding automatically...")
            await page.evaluate("document.getElementById('ai-control-panel')?.remove()")
            await dismiss_modals(page)
            return True
        
        # 4. Check for Sign-in indicators
        sign_in = page.locator("button:has-text('Sign in'), .header-signin-button").first
        if await sign_in.is_visible():
             print("⏳ Sign-in button detected. Please log in to your Premium account.")
        else:
             # Check for common "Basic Plan" or "Sign in" modals (like the one in user screenshot)
             modal_check = page.locator("text='Sort your symbols better', text='30-day free trial'").first
             if await modal_check.count() > 0:
                  print("⚠️  Upgrade/Login modal detected. Clearing...")
                  await dismiss_modals(page)
             else:
                  print("⏳ Waiting for login... or use the red 'RESET' button to re-auth.")
                
        await asyncio.sleep(4)
    
    print("❌ Login detection timed out after 6 minutes.")
    return False

async def process_sync(context):
    """The main logic of the sync process after browser launch."""
    try:
        page = context.pages[0] if context.pages else await context.new_page()
        
        print("🌍 Navigating to TradingView Chart...")
        await page.goto(TV_URL)
        
        # 1. AUTH SAFEGUARD: Wait for user to log in
        authenticated = await wait_for_login(page, context)
        if not authenticated:
            print("❌ Authentication failed or timed out. Exiting sync.")
            return

        # Wait for load - adjust selector if needed (e.g., legend or chart canvas)
        try:
            await page.wait_for_selector(".layout__area--right", timeout=15000)
            print("✅ Chart Loaded.")
        except:
            print("⚠️ Timeout waiting for chart (might still be ok)...")

        # Give a moment for dynamic widgets
        await page.wait_for_timeout(3000)

        # Ensure Watchlist Widget is Open
        print("👀 Checking if Watchlist Panel is open...")
        try:
            # Check if the watchlist widget is visible
            # The widgetbar pages wrapper width is a good indicator
            pages_wrap = page.locator("div[data-name='widgetbar-pages-with-tabs']")
            
            is_open = False
            if await pages_wrap.count() > 0:
                box = await pages_wrap.bounding_box()
                if box and box['width'] > 10:
                    is_open = True
            
            if not is_open:
                print("   👉 Panel seems closed. Opening Watchlist Panel...")
                # Click the toggle button in the toolbar
                # Found via debug snippet: data-name="base"
                toggle_btn = page.locator("button[data-name='base']").first
                if await toggle_btn.count() > 0:
                     await toggle_btn.click()
                     await page.wait_for_timeout(1500)
                else:
                     print("   ⚠️ specific 'base' toggle button not found, scanning toolbar...")
                     await page.locator("button[data-tooltip='Watchlist, details and news']").click()
                     await page.wait_for_timeout(1500)
            else:
                print("   ✅ Watchlist Panel is already open.")
                
        except Exception as e:
            print(f"   ⚠️ Error checking watchlist panel: {e}")

        # Generate Date Suffix to match watchlist_manager.py
        # e.g., 09FEB26
        date_suffix = datetime.datetime.now().strftime("%d%b%y").upper()
        
        for base_name in TARGET_BASES:
            # Construct filename: Hunter-09FEB26.txt
            filename = f"{base_name}-{date_suffix}.txt"
            file_path = os.path.join(WATCHLIST_DIR, filename)
            
            if not os.path.exists(file_path):
                print(f"⚠️ Skipping missing file: {filename}")
                continue
                
            # --- CLEANUP OLD VERSIONS ---
            # Scan for old dated lists (e.g. Hunter-09FEB26) and delete them
            print(f"🧹 Cleanup: Checking for old versions of '{base_name}'...")
            
            try:
                # Open Menu
                menu_trigger = page.locator("button[data-name='watchlists-button']").first
                if not await menu_trigger.count():
                     menu_trigger = page.locator("div[class*='widgetHeader'] button").first
                
                await menu_trigger.click()
                await page.wait_for_timeout(1000)
                
                # Get all items text
                items = page.locator("div[data-role='list-item']")
                count = await items.count()
                
                # We need to collect targets first to avoid DOM mutations while iterating
                targets_to_delete = []
                
                for i in range(count):
                    text = await items.nth(i).text_content()
                    text = text.strip() if text else ""
                    
                    # Logic: exact start match with base name AND contains a date format AND NOT today
                    # e.g., "Hunter-" in "Hunter-09FEB26"
                    if text.startswith(f"{base_name}-"):
                        # Check if it is NOT today's list
                        if text != f"{base_name}-{date_suffix}":
                            print(f"      Found old list: '{text}' (Current: {date_suffix})")
                            targets_to_delete.append(text)
                
                # Close menu to reset state before deletion loop
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
                
                # Delete identified targets
                for old_list in targets_to_delete:
                    print(f"      🗑️ Deleting old list: '{old_list}'...")
                    
                    # Open Menu
                    if not await menu_trigger.count(): # Re-locate if needed
                        menu_trigger = page.locator("button[data-name='watchlists-button']").first
                    await menu_trigger.click()
                    await page.wait_for_timeout(1000)
                    
                    # Find and click the item
                    item = page.locator("div[data-role='list-item']").filter(has_text=old_list).first
                    if await item.count() > 0:
                        await item.click()
                        await page.wait_for_timeout(3000)
                        
                        # Now delete active
                        if not await menu_trigger.count():
                            menu_trigger = page.locator("button[data-name='watchlists-button']").first
                        await menu_trigger.click()
                        await page.wait_for_timeout(500)
                        
                        await page.locator("div[data-role='menuitem']").filter(has_text="Delete list").click()
                        await page.locator("button[name='yes']").click()
                        await page.wait_for_timeout(1000)
                        print(f"      ✅ Deleted: {old_list}")
                    else:
                        print(f"      ⚠️ Could not find '{old_list}' to delete.")
                        await page.keyboard.press("Escape")
                        
            except Exception as e:
                print(f"   ⚠️ Cleanup warning: {e}")
                await page.keyboard.press("Escape")

            print(f"📂 Processing: {filename}")
            
            try:
                # Strategy:
                # 1. Open Menu and Scan for ALL identical names (e.g. 3 copies of "Hunter-10FEB26")
                # 2. Iterate and delete them one by one until none remain.
                # 3. Then Upload.
                
                watchlist_name = f"{base_name}-{date_suffix}" # Current target
                
                # Pattern for ANY dated version (e.g. Hunter-10FEB26)
                cleanup_pattern = re.compile(rf"^{re.escape(base_name)}-\d{{1,2}}[A-Za-z]{{3}}\d{{2}}$", re.I)
                
                print(f"   🔍 Check & Delete: Scanning for ALL dated versions of '{base_name}-*'...")
                
                loop_retries = 0
                # We use a loop because DOM refreshes after each deletion
                while True:
                    # NEW: Menu Open Retry Logic
                    menu_opened = False
                    for click_attempt in range(3):
                        # Open Menu if not open
                        menu_trigger = page.locator("button[data-name='watchlists-button']").first
                        if not await menu_trigger.count():
                             menu_trigger = page.locator("div[class*='widgetHeader'] button").first
                        
                        # Check if menu is visible using data-qa-id 
                        menu_inner = page.locator("div[data-qa-id='menu-inner']").first
                        if not await menu_inner.is_visible():
                            print(f"      📂 Menu not visible. Clicking trigger (Attempt {click_attempt+1})...")
                            await menu_trigger.click()
                            await page.wait_for_timeout(1000)
                        
                        # Get all text again
                        items = page.locator("div[data-role='menuitem']")
                        count = await items.count()
                        
                        if count > 0:
                            menu_opened = True
                            break
                        else:
                            print(f"      ⚠️ Menu empty or not opened (Attempt {click_attempt+1}). Retrying...")
                            await page.keyboard.press("Escape")
                            await page.wait_for_timeout(1000)

                    if not menu_opened:
                        print("      🛑 CRITICAL: Could not open watchlist menu after multiple attempts.")
                        print("      Assuming all versions are cleared and Proceeding to UPLOAD as a fallback...")
                        break # Break while True to go to upload

                    found_count = 0
                    # PRIORITY 1: Check if Active List ITSELF is the target (or a duplicate of it)
                    # If so, delete it immediately. Do not scan dropdown yet.
                    
                    raw_current_text = await menu_trigger.text_content()
                    current_text = " ".join(raw_current_text.split()) if raw_current_text else ""
                    print(f"      👀 Current Active: '{current_text}'")
                    
                    if cleanup_pattern.match(current_text):
                        print(f"      🗑️ Active list matches pattern '{base_name}-*'. Deleting active instance...")
                        # Perform delete on active
                        if not await menu_trigger.count():
                                menu_trigger = page.locator("button[data-name='watchlists-button']").first
                        
                        # Ensure menu is closed before clicking Kebab? 
                        # Actually Kebab is in the header, independent of the switcher menu.
                        # But if switcher is open, it might overlay? 
                        # Let's close switcher to be safe.
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(500)
                        
                        # Search for "Delete list" in Kebab Menu ("...")
                        # Try multiple selectors
                        kebab = page.locator("button[data-name='header-toolbar-more']").first
                        if not await kebab.count():
                            kebab = page.locator("div[data-name='header-toolbar-more']").first
                        if not await kebab.count():
                            kebab = page.locator("button[aria-label='List operations']").first
                        if not await kebab.count():
                            kebab = page.locator("div[aria-label='List operations']").first
                        
                        if await kebab.count():
                            await kebab.click()
                            found_kebab = True
                        else:
                            # FALLBACK: Right-click the Watchlist Name itself (menu_trigger)
                            print("      ⚠️ Kebab missing. Trying RIGHT-CLICK on 'titleRow' text...")
                            
                            # Target the specific title text span inside the button
                            title_span = page.locator("span[class*='titleRow-']").first
                            if await title_span.count():
                                await title_span.click(button="right")
                                found_kebab = True # Treated as opening a menu
                            else:
                                if not await menu_trigger.count():
                                    menu_trigger = page.locator("button[data-name='watchlists-button']").first
                                await menu_trigger.click(button="right")
                                found_kebab = True
                        
                        if found_kebab:
                            await page.wait_for_timeout(1000)
                            
                            # Try to find Delete button
                            # Note: In context menu it might be "Delete list" or just "Delete"
                            del_item = page.locator("div[data-role='menuitem']").filter(has_text="Delete")
                            if await del_item.count():
                                    await del_item.first.click()
                                    await page.locator("button[name='yes']").click()
                                    print("      ✅ Deleted active duplicate.")
                                    await page.wait_for_timeout(2000)
                                    continue # RESTART LOOP -> Check next one
                            else:
                                    print("      ❌ 'Delete' option not found in Kebab/Context menu.")
                                    
                                    # Debug: Check menu-inner directly
                                    print("      📋 Checking 'data-name=menu-inner' explicitly:")
                                    k_menu = page.locator("div[data-name='menu-inner']").first
                                    if not await k_menu.count():
                                         k_menu = page.locator("div[class*='menuWrap']").first
                                    
                                    if await k_menu.count():
                                        # Dump generic because menu structure varies
                                        html = await k_menu.inner_html()
                                        print(f"         Menu HTML Dump: {html[:200]}...") # Truncate for log
                                        with open("debug_kebab_dump.html", "w", encoding="utf-8") as f:
                                            f.write(html)
                                        print("      📸 Saved 'debug_kebab_dump.html'")
                                        
                                        # Also iterate items from HERE
                                        items = k_menu.locator("div[data-role='menuitem']")
                                        count = await items.count()
                                        print(f"      📋 Found {count} items in menu-inner:")
                                        for i in range(count):
                                            txt = await items.nth(i).text_content()
                                            print(f"         - '{txt.strip()}'")
                                    print("      ⚠️ Header/Context deletion failed.")
                                    
                                    print("      ⚠️ Header/Context deletion failed.")
                                    
                                    # STRATEGY 2: OPEN "MANAGE LISTS" DIALOG
                                    # User reports using "Open list..." at bottom of dropdown to manage/delete.
                                    print("      📂 Opening 'Open list...' dialog to find Trash Can...")
                                    
                                    # 1. Open Dropdown
                                    if not await page.locator("div[data-role='menuitem']").first.is_visible():
                                         if not await menu_trigger.count():
                                             menu_trigger = page.locator("button[data-name='watchlists-button']").first
                                         await menu_trigger.click()
                                         # await page.wait_for_timeout(1000) # Wait for menu
                                    
                                    # 2. Find "Open list..." button (usually last item)
                                    # It might be in a separate footer or just a menu item
                                    open_list_btn = page.locator("div[data-name='open-list-dialog-button']").first
                                    if not await open_list_btn.count():
                                        open_list_btn = page.locator("div[data-role='menuitem']").filter(has_text="Open list").first
                                    
                                    if await open_list_btn.count():
                                        await open_list_btn.click()
                                        await page.wait_for_timeout(2000) # Wait for dialog
                                        
                                        # 3. Find row using Pattern Scanning (since data-title match is harder with regex in CSS)
                                        print(f"      👀 Scanning dialog for rows matching '{base_name}-*'...")
                                        
                                        rows = page.locator("div[data-role='list-item'][data-title]")
                                        row_count = await rows.count()
                                        target_row = None
                                        
                                        for r_idx in range(row_count):
                                            row_title = await rows.nth(r_idx).get_attribute("data-title")
                                            if row_title and cleanup_pattern.match(row_title):
                                                target_row = rows.nth(r_idx)
                                                watchlist_name = row_title # Update for logging
                                                break
                                        
                                        if target_row and await target_row.count():
                                            print(f"      🎯 Found row: '{watchlist_name}'. Hovering to reveal trash can...")
                                            await target_row.hover()
                                            await page.wait_for_timeout(1000)
                                            
                                            # 4. Find Trash Can (Remove button) using data-name
                                            # Found in dump: data-name="remove-button"
                                            remove_btn = target_row.locator("[data-name='remove-button']").first
                                            
                                            if await remove_btn.count():
                                                # Use force=True because hover visibility check often fails
                                                print("      ❌ Found Trash Can. Force Clicking...")
                                                await remove_btn.click(force=True)
                                                
                                                # Confirm deletion
                                                await page.wait_for_timeout(1000)
                                                confirm_btn = page.locator("button[name='yes']").first
                                                if await confirm_btn.count() and await confirm_btn.is_visible():
                                                    print("      ✅ Confirming deletion...")
                                                    await confirm_btn.click()
                                                
                                                print("      ✅ Deleted via 'Open list' manager!")
                                                await page.wait_for_timeout(2000) # Settle delay
                                                
                                                # Close dialog if it didn't auto-close
                                                # (Deleting active list might close it, deleting inactive might not)
                                                close_btn = page.locator("button[data-qa-id='close']").first
                                                if await close_btn.count() and await close_btn.is_visible():
                                                    await close_btn.click()
                                                else:
                                                    await page.keyboard.press("Escape")
                                                
                                                await page.wait_for_timeout(2000) # Final UI settle
                                                continue # Main loop
                                            else:
                                                 print("      ❌ Trash can icon (data-name='remove-button') not found on row.")
                                        else:
                                            print(f"      ❌ Could not find row with data-title='{watchlist_name}'")
                                    else:
                                        print("      ❌ Could not find 'Open list...' button in dropdown.")
                                    
                                    print("      🛑 CRITICAL: Failed to delete via Manager. ABORTING.")
                                    return
                            
                    # PRIORITY 2: If active is NOT the target, scan dropdown for duplicates
                    print(f"      🔍 Active list is safe ('{current_text}'). Scanning dropdown for copies...")
                    
                    # Open Menu to scan
                    if not await page.locator("div[data-role='menuitem']").first.is_visible():
                         await menu_trigger.click()
                         # Check if menu appeared, etc (logic from before)
                         try:
                             menu_inner = page.locator("div[data-qa-id='menu-inner']").first
                             await expect(menu_inner).to_be_visible(timeout=3000)
                         except:
                             await page.wait_for_timeout(1000)

                    items = page.locator("div[data-role='menuitem']")
                    count = await items.count()
                    
                    
                    # Store previously checked count to stop infinite scroll if no new items
                    last_item_count = 0
                    
                    found_copies = 0
                    target_to_switch = None
                    
                    # SCROLL LOOP: Try scanning up to 5 "pages" of scroll
                    for scroll_attempt in range(5):
                        print(f"      👀 Scanning dropdown (Attempt {scroll_attempt+1}/5)...")
                        
                        items = page.locator("div[data-role='menuitem']")
                        count = await items.count()
                        
                        # Optimization: If count matches last scan and we scrolled, maybe we reached end?
                        # But items might replace each other in virtualization, so text content matters more.
                        
                        target_to_switch = None
                        
                        for i in range(count):
                            item = items.nth(i)
                            # Get text logic...
                            label_span = item.locator("span[class*='label-']")
                            if await label_span.count():
                                    raw_text = await label_span.first.text_content()
                            else:
                                    raw_text = await item.text_content()
                            text = " ".join(raw_text.split()) if raw_text else ""
                            
                            if cleanup_pattern.match(text):
                                # Verify not "Create new list..."
                                if "Create" in text or "Import" in text:
                                    continue
                                
                                found_copies += 1
                                target_to_switch = item
                                print(f"      🎯 Found duplicate in dropdown (Index {i}): '{text}'")
                                break # Found one to switch to, break inner loop
                        
                        if target_to_switch:
                            break # Break outer scroll loop
                        
                        # If not found, SCROLL DOWN
                        print("      📜 No duplicate in current view. Scrolling down...")
                        # Hover over the last item to ensure focus, then wheel
                        if count > 0:
                            await items.last.hover()
                            await page.mouse.wheel(0, 500) # Scroll down 500 pixels
                            await page.wait_for_timeout(1000) # Wait for load
                        else:
                            break # Empty list?
                    
                    if target_to_switch:
                        try:
                            print(f"      Switching to duplicate...")
                            await target_to_switch.click()
                            await page.wait_for_timeout(3000)
                            continue # RESTART LOOP
                        except Exception as e:
                            print(f"      ⚠️ Failed to switch: {e}")
                            break
                    
                    # PRIORITY 3: No active match, no dropdown match -> Done.
                    if found_copies == 0:
                        print("      ✨ No copies found (scanned with scroll). Ready to upload.")
                        await page.keyboard.press("Escape")
                        break

                    
                # --- UPLOAD SECTION ---
                print("   Clicking Menu Trigger (Watchlist Switcher)...")
                # Wait for menu to be closed or open?
                # We need to click "Import list". 
                # If we just deleted, the menu might be closed or open depending on the deletion flow.
                # Let's just standardly open it.
                
                if not await menu_trigger.count():
                     menu_trigger = page.locator("button[data-name='watchlists-button']").first
                     
                # Ensure menu is open before clicking "Upload list"
                upload_item = page.locator("div[data-role='menuitem']").filter(has_text="Upload list").first
                if not await upload_item.is_visible():
                     print("      📂 Menu closed. Opening...")
                     await menu_trigger.click()
                     await page.wait_for_timeout(1000)
                     # Re-locate upload_item after opening
                     upload_item = page.locator("div[data-role='menuitem']").filter(has_text="Upload list").first
                
                if not await upload_item.is_visible():
                    print("      ❌ 'Upload list' item not visible in menu. (Are you logged in?)")
                    await page.screenshot(path="debug_menu_error.png")
                    raise Exception("Upload list menu item not found.")

                print("   Selecting 'Upload list...'")
                # Dismiss modals one last time before clicking upload
                await dismiss_modals(page)
                
                try:
                    async with page.expect_file_chooser(timeout=15000) as fc_info:
                        # Robust click on "Upload list"
                        await upload_item.click(force=True)
                except:
                    print("      ⚠️ File chooser didn't appear. Trying an alternative click approach...")
                    await dismiss_modals(page)
                    async with page.expect_file_chooser(timeout=10000) as fc_info:
                        await page.keyboard.press("Enter") # Sometimes Enter on focused item works better
                
                print("   Waiting for file chooser...")
                file_chooser = await fc_info.value
                await file_chooser.set_files(file_path)
                
                print(f"   ✅ Uploaded {filename}")
                await page.wait_for_timeout(2000)
                
            except Exception as e:
                print(f"   ❌ Failed to import {base_name}: {e}")
                print("   📸 Saving screenshot to debug...")
                try:
                    await page.screenshot(path=f"debug_error_{base_name}.png")
                    print(f"      Saved: debug_error_{base_name}.png")
                except:
                    pass
                # Recover
                await page.keyboard.press("Escape")
        
        print("🏁 Sync Complete!")
        
        # Check if running in pipeline mode (Auto-close)
        if "--pipeline" in sys.argv:
            print("🤖 Pipeline Mode: Closing in 3 seconds...")
            await page.wait_for_timeout(3000)
            await context.close()
        else:
            # Manual Mode: Keep open
            print("👤 Manual Mode: Browser will remain open.")
            print("👉 Press Ctrl+C in this terminal to close browser and exit.")
            await asyncio.Future() 

    except Exception as e:
        print(f"❌ Critical Error in sync process: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(run_sync())
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
