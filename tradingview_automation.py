import asyncio
from playwright.async_api import async_playwright
import os
import sys

# ==========================================
# CONFIGURATION
# ==========================================
WATCHLIST_DIR = os.path.join(os.getcwd(), "Generated_Watchlists")
TV_URL = "https://in.tradingview.com/chart/"
USER_DATA_DIR = os.path.join(os.getcwd(), "tv_user_data")

# Files to Import
TARGET_FILES = [
    "FINAL_Hunter_Picks.txt",
    "FINAL_Pullback_Picks.txt",
    "FINAL_EarlyBird_Picks.txt",
    "FINAL_Leader_Picks.txt"
]

async def run_sync():
    print("🚀 STARTING TRADINGVIEW WATCHLIST SYNC...")
    
    if not os.path.exists(WATCHLIST_DIR):
        print(f"❌ Error: Watchlist directory not found: {WATCHLIST_DIR}")
        return

    async with async_playwright() as p:
        # Launch with persistent context to keep login
        print(f"📂 User Data Dir: {USER_DATA_DIR}")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False, # Must be visible for file dialogs sometimes
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled", # Bypass detection
                "--no-sandbox",
            ],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        print("🌍 Navigating to TradingView Chart...")
        await page.goto(TV_URL)
        
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
            # Right toolbar 'Watchlist' icon
            watchlist_tab = page.locator("div[data-name='watchlist']")
            if await watchlist_tab.count() > 0:
                 # Check if it's active? Hard to tell, but clicking it is usually safe or toggles it.
                 # Better: Check if the widget is visible.
                 widget_header = page.locator("div[data-name='watchlist-symbol-list-header']")
                 if not await widget_header.is_visible():
                     print("   👉 Opening Watchlist Panel...")
                     await watchlist_tab.click()
                     await page.wait_for_timeout(1000)
        except Exception as e:
            print(f"   ⚠️ Could not focus watchlist panel: {e}")

        for filename in TARGET_FILES:
            file_path = os.path.join(WATCHLIST_DIR, filename)
            if not os.path.exists(file_path):
                print(f"⚠️ Skipping missing file: {filename}")
                continue
                
            print(f"📂 Processing: {filename}")
            
            try:
                # Strategy: Target the "List operations" button (ellipsis ...)
                
                # Strategy: Target the "List operations" button (ellipsis ...)
                
                print("   🔍 DEBUG: Scanning for Watchlist Header...")
                
                # HTML Dump for offline analysis
                try:
                    html_content = await page.content()
                    with open("debug_tv_source.html", "w", encoding="utf-8") as f:
                        f.write(html_content)
                    print("   📸 Saved page source to: debug_tv_source.html")
                except Exception as e:
                    print(f"   ⚠️ Could not save HTML dump: {e}")

                # Try finding by aria-label "List operations"
                # 1. Click the 'Watchlist Switcher' (Dropdown arrow next to list name)
                # Found via debug_snippet.html: data-name="watchlists-button"
                menu_trigger = page.locator("button[data-name='watchlists-button']").first
                
                if not await menu_trigger.count():
                     print("   ⚠️ specific 'watchlists-button' not found, trying generic header button...")
                     menu_trigger = page.locator("div[class*='widgetHeader'] button").first
                
                print("   Clicking Menu Trigger (Watchlist Switcher)...")
                await menu_trigger.click()
                await page.wait_for_timeout(1000)
                
                # 2. Click "Import list..." in the dropdown
                # Note: "Import list..." is usually at the bottom of the switch list menu
                print("   Selecting 'Import list...'")
                async with page.expect_file_chooser() as fc_info:
                    # Try explicit text first, then fallback
                    try:
                        await page.get_by_text("Import list", exact=False).click(timeout=5000)
                    except:
                        print("   ⚠️ 'Import list' text not found immediately. Scanning menu items...")
                        # Sometimes it might be in a submenu or named differently?
                        await page.locator("div[role='menuitem']").filter(has_text="Import list").click(timeout=5000)
                
                print("   Waiting for file chooser...")
                file_chooser = await fc_info.value
                await file_chooser.set_files(file_path)
                
                print(f"   ✅ Uploaded {filename}")
                await page.wait_for_timeout(2000)
                
                # Wait for system to process (it might ask to replace if exists? Usually it creates new or overwrites)
                await page.wait_for_timeout(2000) 
                
            except Exception as e:
                print(f"   ❌ Failed to import {filename}: {e}")
                print("   📸 Saving screenshot to debug...")
                try:
                    await page.screenshot(path=f"debug_error_{filename}.png")
                    print(f"      Saved: debug_error_{filename}.png")
                except:
                    pass
                # Recover
                await page.keyboard.press("Escape")
        
        print("🏁 Sync Complete!")
        
        # Check if running in pipeline mode (Auto-close)
        import sys
        if "--pipeline" in sys.argv:
            print("🤖 Pipeline Mode: Closing in 3 seconds...")
            await page.wait_for_timeout(3000)
            await context.close()
        else:
            # Manual Mode: Keep open
            print("👤 Manual Mode: Browser will remain open.")
            print("👉 Press Ctrl+C in this terminal to close browser and exit.")
            # Keep script running indefinitely until user kills it
            # We use a loop or just a long sleep or input inside an async compatible way?
            # input() is blocking. 
            # We can just wait indefinitely.
            await asyncio.Future() 

if __name__ == "__main__":
    try:
        asyncio.run(run_sync())
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
