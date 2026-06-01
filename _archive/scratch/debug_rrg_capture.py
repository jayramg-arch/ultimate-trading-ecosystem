import asyncio
from playwright.async_api import async_playwright
import os

USER_DATA_DIR = os.path.join(os.getcwd(), "strike_user_data")

async def capture_dropdown():
    async with async_playwright() as p:
        print(">> Launching Browser...")
        # Use a new context to avoid lock if previous didn't close fully, but wait a bit first
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

        print(">> Capturing Snapshot...")
        await page.screenshot(path="debug_rrg_dropdown.png")
        with open("debug_rrg_dropdown.html", "w", encoding="utf-8") as f:
            f.write(await page.content())
            
        print(">> Saved debug_rrg_dropdown.html and png.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_dropdown())
