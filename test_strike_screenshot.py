import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    USER_DATA_DIR = os.path.join(r"c:\Users\jayra\Documents\GeminiVSCode", 'strike_user_data')
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR, headless=True, args=['--no-sandbox', '--window-size=1920,1080']
        )
        page = await browser.new_page()
        print("Loading...")
        await page.goto('https://web.strike.money/watchlist', timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Open Dropdown
        dropdown = page.locator('.rs-watchListDropdown .rs-picker-toggle, .rs-picker-toggle').first
        if await dropdown.is_visible():
            await dropdown.click()
            await page.wait_for_timeout(2000)
            print("Dropdown clicked.")
        
        await page.screenshot(path='strike_login_check.png')
        print("Screenshot saved to strike_login_check.png")
        await browser.close()
asyncio.run(main())
