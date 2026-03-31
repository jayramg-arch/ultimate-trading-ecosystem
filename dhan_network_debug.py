
import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Intercept requests
        requests_log = []
        page.on("request", lambda request: requests_log.append(f"{request.method} {request.url}"))
        
        print("🌍 Navigating to https://web.dhan.co/...")
        await page.goto("https://web.dhan.co/", timeout=60000)
        await page.wait_for_timeout(3000)
        
        # Click "Show login with Mobile"
        print("🖱️ Clicking 'Show login with Mobile'...")
        try:
            await page.click("text=Show login with Mobile", timeout=5000)
        except:
            pass
            
        # Enter a dummy Client ID to trigger the next step
        print("⌨️ Entering Dummy Client ID...")
        await page.fill("input[placeholder='Enter Your Mobile Number Here']", "1234567890")
        await page.click("button:has-text('Proceed')")
        
        await page.wait_for_timeout(5000)
        
        # Print all intercepted login/auth requests
        print("\n📡 Intercepted Auth/Login Requests:")
        for req in requests_log:
            if "login" in req.lower() or "auth" in req.lower() or "api" in req.lower():
                print(req)
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
