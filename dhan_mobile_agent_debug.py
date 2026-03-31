
import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        # Use a mobile device profile
        iphone = p.devices['iPhone 12']
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(**iphone)
        page = await context.new_page()
        
        print("🌍 Navigating to https://web.dhan.co/ with Mobile User Agent...")
        await page.goto("https://web.dhan.co/", timeout=60000)
        await page.wait_for_timeout(5000)
        
        await page.screenshot(path="dhan_mobile_agent_login.png")
        print("📸 Screenshot saved to dhan_mobile_agent_login.png")
        
        # Check for field
        html = await page.content()
        with open("dhan_mobile_agent_dump.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
