
import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("🌍 Navigating to https://login.dhan.co/...")
        await page.goto("https://login.dhan.co/", timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Take screenshot
        screenshot_path = os.path.join(os.getcwd(), "dhan_login_direct.png")
        await page.screenshot(path=screenshot_path)
        print(f"📸 Screenshot saved to {screenshot_path}")
        
        # Dump HTML
        html_content = await page.content()
        with open("dhan_login_direct_dump.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("📄 HTML dump saved to dhan_login_direct_dump.html")
        
        # Try to find "Login with Mobile" button if not already on the mobile page
        try:
            btn = page.get_by_text("Show login with Mobile")
            if await btn.is_visible():
                print("🖱️ Clicking 'Show login with Mobile'...")
                await btn.click()
                await page.wait_for_timeout(2000)
                await page.screenshot(path="dhan_login_direct_mobile.png")
        except:
            pass
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
