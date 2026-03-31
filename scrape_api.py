
import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            "dhan_session", 
            headless=True, 
            channel="chrome"
        )
        page = browser.pages[0]
        print("🌍 Navigating to API page...")
        await page.goto("https://web.dhan.co/profile/api")
        await page.wait_for_timeout(10000)
        
        # Scrape content
        content = await page.content()
        with open("api_page_source.html", "w", encoding="utf-8") as f:
            f.write(content)
        
        await page.screenshot(path="api_page_debug.png")
        print("✅ Saved source and screenshot.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
