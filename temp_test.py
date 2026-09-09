from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe', user_data_dir='tv_user_data_v2')
    page = browser.contexts[0].pages[0] if browser.contexts[0].pages else browser.contexts[0].new_page()
    page.goto('https://in.tradingview.com/chart/')
    page.wait_for_selector('[data-name=\"watchlists-button\"]')
    header = page.locator('[class*=\"widgetbar-widget-watchlist\"] [data-name=\"widgetbar-widget-header\"]').first
    print(header.inner_html())

