import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://login.dhan.co/', timeout=30000)
        await page.wait_for_timeout(3000)
        
        # platform
        if await page.locator('text=Select your trading platform').first.is_visible():
            await page.click('.dhanWEb >> nth=0')
            await page.wait_for_timeout(2000)
            
        # mobile
        await page.fill('input[placeholder="Enter Your Mobile Number Here"]', '9840715503')
        await page.click('button:has-text("Proceed")')
        await page.wait_for_timeout(5000)
        
        content = await page.content()
        with open('dhan_after_mobile.html', 'w', encoding='utf-8') as f:
            f.write(content)
        await browser.close()

asyncio.run(run())
