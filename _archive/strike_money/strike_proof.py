import asyncio
from playwright.async_api import async_playwright
import re
import os

async def main():
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    USER_DATA_DIR = os.path.join(_SCRIPT_DIR, "strike_user_data")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=True,
            args=['--no-sandbox', '--window-size=1920,1080']
        )
        page = await browser.new_page()
        print("Navigating to Strike...")
        await page.goto('https://web.strike.money/watchlist', timeout=60000)
        await page.wait_for_timeout(5000)
        
        # 1. Open Dropdown
        dropdown = page.locator('.rs-watchListDropdown .rs-picker-toggle, .rs-picker-toggle').first
        if await dropdown.is_visible():
            await dropdown.click()
            await page.wait_for_timeout(1000)
            
            # 2. Try to click 'Bull_Pullback-10JUN26'
            wl_name = 'Bull_Pullback-10JUN26'
            wl_item = page.locator("div[role='option'], a[role='option'], .rs-picker-select-menu-item, li").filter(
                has_text=re.compile(rf"^\s*{re.escape(wl_name)}(?:\s*\(\d+\))?\s*$", re.IGNORECASE)
            ).first
            
            if await wl_item.is_visible():
                print(f"Found {wl_name} in dropdown. Clicking it...")
                await wl_item.click()
                await page.wait_for_timeout(4000)
                
                # Take screenshot of the loaded watchlist
                await page.screenshot(path="strike_proof_1_loaded.png")
                
                # Try finding the ... button using our NEW selector
                more_btn = page.locator("[class*='marketOverviewContainer_moreBtn']").first
                if await more_btn.is_visible():
                    print("Found 3-dots button! Clicking it...")
                    await more_btn.click()
                    await page.wait_for_timeout(2000)
                    
                    # Take screenshot of the opened menu
                    await page.screenshot(path="strike_proof_2_menu_opened.png")
                    
                    delete_btn = page.locator("text='Delete Watchlist', text='Delete'").first
                    if await delete_btn.is_visible():
                        print("SUCCESS! Found Delete Watchlist button.")
                        # We won't actually click delete to be safe, just proving we found it
                    else:
                        print("FAILED: Delete Watchlist not in menu.")
                else:
                    print("FAILED: 3-dots button not found.")
            else:
                print(f"FAILED: {wl_name} not found in dropdown.")
        else:
            print("FAILED: Dropdown not found.")
        
        await browser.close()

asyncio.run(main())
