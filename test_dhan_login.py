import asyncio
import os
import pyotp
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv(override=True)
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
PIN = os.getenv("DHAN_PIN")
TOTP_KEY = os.getenv("DHAN_TOTP_KEY")

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://web.dhan.co/")
        
        try:
            await (await page.wait_for_selector("text=Show login with Mobile", timeout=5000)).click()
        except:
            pass
            
        await page.wait_for_timeout(2000)
        
        # Enter client ID
        print("Entering Client ID:", CLIENT_ID)
        await page.fill("input[placeholder='Enter Your Mobile Number Here']", CLIENT_ID)
        await page.click("button:has-text('Proceed')")
        
        await page.wait_for_timeout(3000)
        
        # Now we are at the OTP page
        totp = pyotp.TOTP(TOTP_KEY.replace(" ", "")).now()
        print("Entering TOTP:", totp)
        
        # Focus on the first OTP input
        await page.click("input[type='tel']")
        await page.keyboard.type(totp)
        
        await page.wait_for_timeout(3000)
        
        await page.screenshot(path="dhan_step5.png")
        with open("dhan_step5.html", "w", encoding="utf-8") as f:
            f.write(await page.content())
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test())
