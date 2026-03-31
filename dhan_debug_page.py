
import asyncio
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv

# Load for credentials
load_dotenv(override=True)

async def main():
    client_id = os.getenv("DHAN_CLIENT_ID")
    dhan_pin = os.getenv("DHAN_PIN")
    
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
            print("⚠️ 'Show login with Mobile' not found, maybe already there?")
            
        await page.wait_for_timeout(2000)
        
        # Enter Client ID
        print(f"⌨️ Entering Client ID: {client_id}...")
        try:
            await page.fill("input[placeholder='Enter Your Mobile Number Here']", client_id)
            await page.click("button:has-text('Proceed')")
        except:
            print("⚠️ Failed to enter Client ID, trying alternative...")
            # Maybe the selector changed
            await page.type("input", client_id)
            await page.keyboard.press("Enter")

        await page.wait_for_timeout(3000)
        
        # Enter PIN
        print(f"⌨️ Entering PIN: {dhan_pin}...")
        try:
            # Try to find any input fields for the PIN
            inputs = await page.query_selector_all("input")
            if len(inputs) >= 6:
                print(f"✅ Found {len(inputs)} input boxes. Entering PIN digit by digit...")
                for i, digit in enumerate(dhan_pin[:6]):
                    await inputs[i].fill(digit)
                    await page.wait_for_timeout(100)
            else:
                print("⚠️ Less than 6 inputs found. Trying to type PIN directly...")
                await page.keyboard.type(dhan_pin)
                
            await page.click("button:has-text('Proceed')")
            print("✅ PIN entered and clicked Proceed")
        except Exception as e:
            print(f"❌ Failed to enter PIN: {e}")
            await page.screenshot(path="debug_pin_fail.png")

        await page.wait_for_timeout(5000)
        
        # Take screenshot of the next page (TOTP?)
        screenshot_path = os.path.join(os.getcwd(), "dhan_totp_page.png")
        await page.screenshot(path=screenshot_path)
        print(f"📸 Screenshot saved to {screenshot_path}")
        
        # Dump HTML
        html_content = await page.content()
        with open("dhan_totp_page_dump.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("📄 HTML dump saved to dhan_totp_page_dump.html")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
