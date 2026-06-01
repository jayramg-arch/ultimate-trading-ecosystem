import asyncio
from playwright.async_api import async_playwright
import os

USER_DATA_DIR = os.path.join(os.getcwd(), "strike_user_data_debug")

async def debug_dropdown():
    async with async_playwright() as p:
        print(">> Launching Browser...")
        browser = await p.chromium.launch_persistent_context(
            USER_DATA_DIR, headless=False, args=["--disable-blink-features=AutomationControlled", "--start-maximized"]
        )
        page = browser.pages[0]
        
        print(">> Navigating to RRG...")
        await page.goto("https://web.strike.money/rrg", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        print(">> Opening Picker...")
        picker = page.locator(".sidebar .select .rs-picker-toggle")
        await picker.click()
        await page.wait_for_timeout(2000)

        print(">> Fetching Options...")
        options = page.locator(".rs-picker-menu-item")
        count = await options.count()
        print(f"Found {count} options:")
        
        for i in range(count):
            text = await options.nth(i).inner_text()
            print(f" - '{text}'")
            
        print(">> Done.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_dropdown())
