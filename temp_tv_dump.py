import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir='tv_user_data_v2', 
            headless=True, 
            executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe'
        )
        page = browser.pages[0] if browser.pages else await browser.new_page()
        await page.goto('https://in.tradingview.com/chart/')
        await page.wait_for_selector('[data-name="watchlists-button"]')
        
        # Ensure Watchlist panel is open
        wl_tab = page.locator("button[data-name='right-toolbar-watchlists']").first
        if await wl_tab.count() > 0:
            aria_pressed = await wl_tab.get_attribute('aria-pressed')
            if aria_pressed == 'false':
                await wl_tab.click(force=True)
                await page.wait_for_timeout(1000)
        
        # Click the Watchlist title trigger
        menu_trigger = page.locator('button[data-name="watchlists-button"], div[class*="widgetbar-widget-watchlist"] .title-button').first
        await menu_trigger.click(force=True)
        await page.wait_for_timeout(1500)
        
        # Dump the entire page HTML
        html = await page.content()
        with open('tv_dump_main_menu.html', 'w', encoding='utf-8') as f:
            f.write(html)
        await browser.close()

asyncio.run(main())
