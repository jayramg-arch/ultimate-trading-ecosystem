import asyncio
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv

load_dotenv(override=True)
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating...")
        await page.goto("https://web.dhan.co/")
        await page.wait_for_timeout(3000)
        
        print("Waiting for page to load...")
        await page.wait_for_timeout(5000)
        await page.screenshot(path="dhan_test1.png")
        with open("dhan_dom1.html", "w", encoding="utf-8") as f:
            f.write(await page.content())
            
        await browser.close()
        print("Done")

asyncio.run(test())
