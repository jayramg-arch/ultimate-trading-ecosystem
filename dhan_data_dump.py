
import asyncio
from playwright.async_api import async_playwright
import os
import json

SESSION_DIR = "dhan_session"

async def dump_data():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
            channel="chrome"
        )
        page = context.pages[0]
        await page.goto("https://web.dhan.co/index/home", timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Get storage
        storage = await page.evaluate("""() => {
            let ls = {};
            for (let i = 0; i < localStorage.length; i++) {
                ls[localStorage.key(i)] = localStorage.getItem(localStorage.key(i));
            }
            let ss = {};
            for (let i = 0; i < sessionStorage.length; i++) {
                ss[sessionStorage.key(i)] = sessionStorage.getItem(sessionStorage.key(i));
            }
            return {ls, ss};
        }""")
        
        # Get cookies
        cookies = await context.cookies()
        
        data = {
            "url": page.url,
            "localStorage": storage['ls'],
            "sessionStorage": storage['ss'],
            "cookies": cookies
        }
        
        with open("dhan_data_dump.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        print("✅ Data dumped to dhan_data_dump.json")
        await context.close()

if __name__ == "__main__":
    asyncio.run(dump_data())
