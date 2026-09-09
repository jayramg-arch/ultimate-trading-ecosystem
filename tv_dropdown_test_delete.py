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
        
        menu_trigger = page.locator('button[data-name="watchlists-button"], div[class*="widgetbar-widget-watchlist"] .title-button').first
        if await menu_trigger.count() > 0:
            await menu_trigger.click(force=True)
            await page.wait_for_timeout(2000)
            
            # Find the "Open list" option using regex to ignore dots
            open_list_opt = page.locator("div[data-role='menuitem'], div[role='option'], .item-text").filter(has_text="Open list").first
            if await open_list_opt.count() > 0:
                print("Found 'Open list' option! Clicking...")
                await open_list_opt.click(force=True)
                await page.wait_for_timeout(2000)
                
                # Check what dialog opened
                dialog = page.locator("div[data-name='watchlists-dialog'], div[data-dialog-name='manage-watchlists']").first
                if await dialog.count() == 0:
                    dialog = page.locator("div[role='dialog']").first
                    
                if await dialog.count() > 0:
                    print("Dialog opened!")
                    
                    rows = dialog.locator("div[role='row'], div[data-role='list-item']")
                    if await rows.count() == 0:
                        rows = dialog.locator("div[class*='item-']")
                        
                    count = await rows.count()
                    print(f"Found {count} rows in dialog:")
                    
                    for i in range(min(count, 30)):
                        text = await rows.nth(i).inner_text()
                        print(f"  - {text.strip().replace(chr(10), ' | ')}")
                else:
                    print("Could not find dialog after clicking.")
                    
                await page.screenshot(path="tv_dialog_test.png")
            else:
                print("Could not find 'Open list' option.")
        else:
            print("Could not find menu trigger.")

asyncio.run(main())
