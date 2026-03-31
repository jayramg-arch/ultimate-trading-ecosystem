
import asyncio
from playwright.async_api import async_playwright
import os

SESSION_DIR = "dhan_session"

async def click_navigation():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
            channel="chrome"
        )
        page = context.pages[0]
        await page.goto("https://web.dhan.co/index/home", timeout=60000)
        await page.wait_for_timeout(5000)
        
        print("👤 Clicking profile icon...")
        # The profile icon often has a class like .profile-icon or is the last item in the header
        try:
            # Try to find the profile icon by class or by position
            profile_btn = page.locator("header .profile-icon, header img.user-img, .profile-sec")
            await profile_btn.first.click()
            await page.wait_for_timeout(2000)
            await page.screenshot(path="debug_profile_menu.png")
            
            print("🔗 Searching for API link...")
            # Common text: "DhanHQ API", "Connect to API", "Access DhanHQ APIs"
            api_link = page.get_by_text("Access DhanHQ APIs", exact=False)
            if await api_link.is_visible():
                print("✅ API link found! Clicking...")
                await api_link.click()
                await page.wait_for_timeout(5000)
                await page.screenshot(path="dhan_api_page_resolved.png")
                
                # Capture the token if visible
                content = await page.content()
                with open("dhan_api_page_resolved.html", "w", encoding="utf-8") as f:
                    f.write(content)
            else:
                print("❌ API link not found in menu.")
                # Print all text in the menu for debugging
                menu_text = await page.inner_text("body")
                print(f"Menu content sample: {menu_text[:500]}")
                
        except Exception as e:
            print(f"❌ Error during navigation: {e}")
            await page.screenshot(path="debug_nav_fail.png")
            
        await context.close()

if __name__ == "__main__":
    asyncio.run(click_navigation())
