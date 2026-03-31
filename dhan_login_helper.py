
import asyncio
from playwright.async_api import async_playwright
import os
import time

# Directory to store browser state
SESSION_DIR = "dhan_session"
STATE_FILE = os.path.join(SESSION_DIR, "state.json")

async def run_login_helper():
    if not os.path.exists(SESSION_DIR):
        os.makedirs(SESSION_DIR)
        
    async with async_playwright() as p:
        # Launch a persistence context so we keep the session
        print("🚀 Launching browser for one-time manual login...")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            channel="chrome",  # Use installed chrome for better trust
            args=["--start-maximized"],
            no_viewport=True
        )
        
        page = context.pages[0]
        print("🌍 Navigating to Dhan Login...")
        await page.goto("https://web.dhan.co/", timeout=60000)
        
        print("\n" + "="*50)
        print("⚠️  ACTION REQUIRED: PLEASE LOG IN MANUALLY IN THE OPEN BROWSER.")
        print("1. Enter your Mobile Number/Client ID.")
        print("2. Enter the SMS OTP sent to your phone.")
        print("3. Enter your PIN and TOTP.")
        print("4. Once you see your Dashboard (Funds/Orders), come back here.")
        print("="*50 + "\n")
        
        print("🕵️  Monitoring for successful login...")
        
        # Poll for successful login indicators (e.g., URL change or dashboard elements)
        while True:
            try:
                # Check if we are on the dashboard
                current_url = page.url
                if "dashboard" in current_url.lower() or "funds" in current_url.lower() or "holding" in current_url.lower():
                    print("✅ Successful login detected!")
                    break
                
                # Check for user profile icon as a fallback
                if await page.locator(".profile-icon, .user-name").is_visible():
                    print("✅ Profile icon detected! Login successful.")
                    break
            except:
                pass
            
            await asyncio.sleep(2)
            
        print("💾 Saving session state...")
        await context.storage_state(path=STATE_FILE)
        print(f"✨ Session state saved to {STATE_FILE}")
        
        print("🚪 Closing browser in 5 seconds...")
        await asyncio.sleep(5)
        await context.close()

if __name__ == "__main__":
    asyncio.run(run_login_helper())
