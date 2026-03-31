
import asyncio
from playwright.async_api import async_playwright

SESSION_DIR = "dhan_session"

async def log_all_headers():
    print("🚀 Launching browser to log headers...")
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
            channel="chrome"
        )
        page = browser.pages[0]

        async def intercept(request):
            if "dhan.co" in request.url:
                print(f"\n--- Request to: {request.url[:100]} ---")
                for k, v in request.headers.items():
                    if len(v) > 50:
                        print(f"  {k}: {v[:50]}... (len: {len(v)})")

        page.on("request", intercept)
        
        try:
            print("🌍 Navigating to Home...")
            await page.goto("https://web.dhan.co/index/home")
            await page.wait_for_timeout(10000)
            
            print("🌍 Navigating to API...")
            await page.goto("https://web.dhan.co/profile/api")
            await page.wait_for_timeout(10000)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(log_all_headers())
