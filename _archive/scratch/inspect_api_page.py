
import asyncio
from playwright.async_api import async_playwright
import os

SESSION_DIR = "dhan_session"

async def inspect_api_page():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
            channel="chrome"
        )
        page = context.pages[0]
        print("🌍 Navigating to API page...")
        await page.goto("https://web.dhan.co/profile/api", timeout=60000)
        await page.wait_for_timeout(7000) # Give extra time for the token section to load
        
        # Save screenshot
        await page.screenshot(path="dhan_api_page.png", full_page=True)
        
        # Save HTML
        content = await page.content()
        with open("dhan_api_page.html", "w", encoding="utf-8") as f:
            f.write(content)
            
        print("✅ API page inspected. Check dhan_api_page.png and dhan_api_page.html")
        await context.close()

if __name__ == "__main__":
    asyncio.run(inspect_api_page())
