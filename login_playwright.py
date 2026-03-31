
import asyncio
from playwright.async_api import async_playwright
import os
import sys

# CONFIGURATION
USER_DATA_DIR = os.path.join(os.getcwd(), "tv_user_data")
TV_URL = "https://in.tradingview.com/"

async def login_session():
    print("🚀 Launching Browser for Login...")
    print(f"📂 User Data Dir: {USER_DATA_DIR}")
    
    async with async_playwright() as p:
        # Launch with persistent context to keep login
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        print("🌍 Navigating to TradingView Login...")
        await page.goto(TV_URL)
        
        print("\n" + "="*50)
        print("🛑 ACTION REQUIRED:")
        print("Please log in to your Premium TradingView account in the opened browser window.")
        print("Once you are logged in and can see your chart/layout, you can close the browser or press Enter here.")
        print("="*50 + "\n")
        
        # Keep the script running until user closes it manually or presses Enter
        await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(login_session())
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
