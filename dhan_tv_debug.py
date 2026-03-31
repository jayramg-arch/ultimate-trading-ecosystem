
import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("🌍 Navigating to https://tv.dhan.co/...")
        await page.goto("https://tv.dhan.co/", timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Take screenshot
        screenshot_path = os.path.join(os.getcwd(), "dhan_tv_login.png")
        await page.screenshot(path=screenshot_path)
        print(f"📸 Screenshot saved to {screenshot_path}")
        
        # Check for login fields
        html_content = await page.content()
        with open("dhan_tv_login_dump.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
