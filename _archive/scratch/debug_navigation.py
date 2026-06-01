
import asyncio
import os
from playwright.async_api import async_playwright

SESSION_DIR = "dhan_session"

async def debug_navigation():
    print("🚀 Starting Navigation Debug...")
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            channel="chrome",
            no_viewport=True,
        )
        page = browser.pages[0]
        
        try:
            print("🌍 Navigating to Home...")
            await page.goto("https://web.dhan.co/index/home", timeout=60000)
            await page.wait_for_timeout(5000)
            
            # 1. Click Profile Icon
            print("👤 Clicking Profile Icon...")
            # Try multiple selectors for profile
            profile_selectors = [".user-icon", ".user-name", "div.rightNav img"]
            clicked = False
            for selector in profile_selectors:
                try:
                    await page.click(selector, timeout=5000)
                    print(f"✅ Clicked using: {selector}")
                    clicked = True
                    break
                except: continue
                
            if not clicked:
                print("❌ Failed to click profile icon. Taking emergency screenshot...")
                await page.screenshot(path="debug_profile_fail.png")
                return

            await page.wait_for_timeout(2000)
            
            # 2. Look for API Link
            print("🔍 Searching for 'Get Trading & Data APIs'...")
            # Use text selector
            api_link = page.get_by_text("Get Trading & Data APIs")
            if await api_link.count() > 0:
                print("✅ Found API link! Clicking...")
                await api_link.first.click()
                await page.wait_for_timeout(5000)
                print(f"📍 Current URL: {page.url}")
                await page.screenshot(path="debug_api_page.png")
                
                # Check for token in DOM
                content = await page.content()
                if "ey" in content:
                    tokens = [t for t in content.split() if t.startswith("ey") and len(t) > 200]
                    if tokens:
                        print(f"💎 FOUND TOKEN IN DOM: {tokens[0][:30]}...")
                    else:
                        print("🟡 'ey' found but no valid token string match.")
                else:
                    print("❌ No token string 'ey' found on API page.")
            else:
                print("❌ API link not found in dropdown. Taking screenshot of dropdown...")
                await page.screenshot(path="debug_dropdown_content.png")

        except Exception as e:
            print(f"🚨 Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_navigation())
