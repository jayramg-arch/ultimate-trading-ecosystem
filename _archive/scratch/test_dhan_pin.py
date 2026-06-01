import asyncio
from playwright.async_api import async_playwright
import os
import pyotp
from dotenv import load_dotenv

load_dotenv(override=True)
CLIENT_ID = "9840715503"
TOTP_KEY = os.getenv("DHAN_TOTP_KEY")
PIN = "828582"

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating...")
        await page.goto("https://web.dhan.co/")
        
        print("Waiting for page load...")
        await page.wait_for_timeout(3000)
        
        try:
            await page.click("text=Show login with Mobile", timeout=3000)
        except:
            pass
            
        print(f"Entering client ID: {CLIENT_ID}")
        await page.fill("input[placeholder='Enter Your Mobile Number Here']", CLIENT_ID)
        await page.click("button:has-text('Proceed')")
        
        print("Waiting for PIN screen...")
        await page.wait_for_timeout(3000)
        
        # Take screenshot of PIN screen
        await page.screenshot(path="dhan_pin_screen.png")
        with open("dhan_pin_screen.html", "w", encoding="utf-8") as f:
            f.write(await page.content())
            
        # Try to enter PIN
        try:
            print(f"Entering PIN: {PIN}")
            # The PIN input is usually multiple boxes or a hidden input.
            # Let's try typing on the page or finding the specific input.
            await page.keyboard.type(PIN)
            
            print("Waiting for TOTP screen...")
            await page.wait_for_timeout(3000)
            
            await page.screenshot(path="dhan_totp_screen.png")
            with open("dhan_totp_screen.html", "w", encoding="utf-8") as f:
                f.write(await page.content())
                
        except Exception as e:
            print(f"Error entering PIN: {e}")
            
        await browser.close()
        print("Done")

asyncio.run(test())
