
import asyncio
from playwright.async_api import async_playwright
import os
import pyotp
import time
from dotenv import load_dotenv

# Load for credentials
load_dotenv(override=True)

async def main():
    client_id = os.getenv("DHAN_CLIENT_ID")
    totp_key = os.getenv("DHAN_TOTP_KEY")
    
    # Generate TOTP
    totp = pyotp.TOTP(totp_key)
    totp_code = totp.now()
    print(f"🕒 Generated TOTP: {totp_code}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("🌍 Navigating to https://web.dhan.co/...")
        await page.goto("https://web.dhan.co/", timeout=60000)
        await page.wait_for_timeout(3000)
        
        # Click "Show login with Mobile"
        print("🖱️ Clicking 'Show login with Mobile'...")
        try:
            await page.click("text=Show login with Mobile", timeout=5000)
        except:
            print("⚠️ 'Show login with Mobile' not found")
            
        await page.wait_for_timeout(2000)
        
        # Enter Client ID
        print(f"⌨️ Entering Client ID: {client_id}...")
        await page.fill("input[placeholder='Enter Your Mobile Number Here']", client_id)
        await page.click("button:has-text('Proceed')")

        await page.wait_for_timeout(3000)
        
        # Generate fresh TOTP just in case
        totp_code = totp.now()
        print(f"⌨️ Entering TOTP: {totp_code}...")
        try:
            inputs = await page.query_selector_all("input")
            if len(inputs) >= 6:
                for i, digit in enumerate(totp_code):
                    await inputs[i].fill(digit)
                    await page.wait_for_timeout(100)
            else:
                await page.keyboard.type(totp_code)
                
            await page.click("button:has-text('Proceed')")
            print("✅ TOTP entered and clicked Proceed")
        except Exception as e:
            print(f"❌ Failed to enter TOTP: {e}")

        await page.wait_for_timeout(5000)
        
        # Take screenshot of the next page
        screenshot_path = os.path.join(os.getcwd(), "dhan_after_totp.png")
        await page.screenshot(path=screenshot_path)
        print(f"📸 Screenshot saved to {screenshot_path}")
        
        # Check for success indicators
        content = await page.inner_text("body")
        if "PIN" in content:
            print("📍 Page is now asking for PIN!")
        elif "Dashboard" in content or "Funds" in content:
            print("🎉 SUCCESS! Logged in directly!")
        else:
            print("🤔 Unknown state. Check screenshot.")
            print(f"📄 Page text snippet: {content[:300]}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
