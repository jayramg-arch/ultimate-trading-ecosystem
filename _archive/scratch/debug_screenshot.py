import os
import asyncio
from playwright.async_api import async_playwright

SESSION_DIR = "dhan_session"

async def debug_screenshot():
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            channel="chrome",
            no_viewport=True
        )
        page = browser.pages[0]
        
        try:
            print("🌍 Navigating to Home...")
            await page.goto("https://web.dhan.co/index/home", timeout=60000)
            print("⏳ Waiting 15s for full load...")
            await page.wait_for_timeout(15000)
            
            print("📸 Taking screenshot...")
            await page.screenshot(path="debug_home.png", full_page=True)
            
            # Print page HTML
            html = await page.content()
            with open("debug_home.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("📝 Saved debug_home.html")
            
            # Check for "API" link
            print("🔍 Searching for 'API'...")
            api_links = await page.evaluate(r"""() => {
                return Array.from(document.querySelectorAll('a, button, span')).filter(e => e.innerText.includes('API')).map(e => e.outerHTML);
            }""")
            print(f"🔗 Relevant Elements:\n{api_links}")

        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_screenshot())
