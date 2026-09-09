import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=r"C:\Users\jayra\.gemini\antigravity-ide\brain\f358e766-718f-41a9-8262-2ed4304eec1e\tv_user_data_v2",
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.pages[0] if browser.pages else await browser.new_page()
        
        print("Navigating...")
        await page.goto("https://www.tradingview.com/chart", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        # Click menu trigger
        menu_trigger = page.locator('button[data-name="watchlists-button"], div[class*="widgetbar-widget-watchlist"] .title-button').first
        if await menu_trigger.count() > 0:
            await menu_trigger.click(force=True)
            await page.wait_for_timeout(2000)
            
            # Press arrow down to focus
            await page.keyboard.press("ArrowDown")
            
            all_items = set()
            unchanged = 0
            last_len = -1
            
            print("Scrolling through virtualized dropdown...")
            while unchanged < 3:
                items = page.locator("div[data-role='menuitem'], div[role='option'], span.label-hlEa5N5c, .item-text")
                count = await items.count()
                for i in range(count):
                    text = await items.nth(i).inner_text()
                    all_items.add(text.strip().replace('\n', ' '))
                
                for _ in range(5):
                    await page.keyboard.press("ArrowDown")
                await page.wait_for_timeout(500)
                
                if len(all_items) == last_len:
                    unchanged += 1
                else:
                    unchanged = 0
                    last_len = len(all_items)
                    
            print(f"\nFOUND {len(all_items)} UNIQUE MENU ITEMS:")
            for item in sorted(list(all_items)):
                print(f"  '{item}'")
        else:
            print("Could not find dropdown trigger.")

asyncio.run(main())
