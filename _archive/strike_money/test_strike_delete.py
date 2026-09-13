import asyncio
from playwright.async_api import async_playwright
import re

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=r'c:\Users\jayra\Documents\GeminiVSCode\strike_user_data',
            headless=False,
            args=[
                "--start-maximized",
                "--disable-gpu",
                "--disable-software-rasterizer"
            ]
        )
        page = browser.pages[0] if browser.pages else await browser.new_page()
        await page.goto('https://web.strike.money/watchlist', timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Try finding the ... button for the ACTIVE watchlist
        more_btn = page.locator("[class*='marketOverviewContainer_moreBtn'], [class*='moreBtn']").first
        if await more_btn.is_visible():
            print("Found more_btn!")
            await more_btn.click()
            await page.wait_for_timeout(2000)
            
            # Check what is inside the menu
            menu_html = await page.evaluate("() => document.body.innerHTML")
            with open("test_strike_menu_opened.html", "w", encoding="utf-8") as f:
                f.write(menu_html)
                
            delete_btn = page.locator("li:has-text('Delete Watchlist'), li:has-text('Delete WatchList'), li:has-text('Delete'), li[class*='deleteWatchlist']").last
            if await delete_btn.is_visible():
                print("Found Delete Watchlist button!")
                # NOT clicking it, just proving we found it
            else:
                print("Delete Watchlist NOT found")
        else:
            print("more_btn NOT found")
            with open("test_strike_menu_failed.html", "w", encoding="utf-8") as f:
                f.write(await page.content())
        
        await browser.close()

asyncio.run(main())
