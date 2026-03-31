import os
import time
from playwright.sync_api import sync_playwright

def run():
    user_data_dir = os.path.join(os.getcwd(), 'browser_data')
    os.makedirs(user_data_dir, exist_ok=True)

    print(f"🚀 Launching Antigravity Browser Controller (Debug Mode)...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False, 
            channel="chrome", 
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ],
            ignore_default_args=["--enable-automation"],
            no_viewport=True
        )
        
        page = browser.pages[0]
        
        print("🌍 Navigating to TradingView Chart...")
        page.goto("https://www.tradingview.com/chart/")
        
        print("⏳ Waiting 10s for page to load completely...")
        time.sleep(10)
        
        # 1. Take Screenshot
        page.screenshot(path="tv_chart_debug.png")
        print("📸 Screenshot saved to tv_chart_debug.png")

        # 2. Dump Text Content to find symbols
        print("📝 Dumping page text to analyze structure...")
        try:
            # Get all text
            body_text = page.inner_text("body")
            with open("page_text_dump.txt", "w", encoding="utf-8") as f:
                f.write(body_text)
            print("✅ Text dump saved to page_text_dump.txt")
            
            # Get HTML content of potential watchlist containers
            # Common clues: 'watchlist', 'symbol', 'ticker'
            html_dump = page.content()
            with open("page_html_dump.html", "w", encoding="utf-8") as f:
                f.write(html_dump)
            print("✅ HTML dump saved to page_html_dump.html")
            
        except Exception as e:
            print(f"❌ Dump failed: {e}")
            
        input("\n🛑 Press Enter to close browser...")
        browser.close()

if __name__ == "__main__":
    run()
