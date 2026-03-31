
import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("🌍 Navigating to https://login.dhan.co/...")
        await page.goto("https://login.dhan.co/", timeout=60000)
        await page.wait_for_timeout(3000)
        
        # Click "Dhan" icon
        print("🖱️ Clicking 'Dhan' icon...")
        await page.click("text=Dhan")
        await page.wait_for_timeout(3000)
        
        # Check if we see "Show login with Mobile"
        if await page.get_by_text("Show login with Mobile").is_visible():
            print("🖱️ Clicking 'Show login with Mobile'...")
            await page.click("text=Show login with Mobile")
            await page.wait_for_timeout(2000)

        # Take screenshot of the form
        await page.screenshot(path="dhan_login_form_check.png")
        
        # Look for "PIN" or "Password" in the text of the page
        body_text = await page.inner_text("body")
        print(f"📄 Page text snippet: {body_text[:500]}...")
        
        if "PIN" in body_text or "Password" in body_text:
            print("✨ FOUND PIN or Password reference in page text!")
        else:
            print("❌ No PIN/Password reference found in main text.")

        # Try to find all links and buttons
        elements = await page.query_selector_all("a, button, span")
        for el in elements:
            text = await el.inner_text()
            if text and ("PIN" in text or "Password" in text or "OTP" in text):
                print(f"🔗 Found element: [{text}]")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
