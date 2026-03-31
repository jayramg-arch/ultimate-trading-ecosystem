import os
import time
import json
import re
from playwright.sync_api import sync_playwright

# List of symbols identified from the user's watchlist
SYMBOLS = [
    # Stocks
    "FEDERALBNK", "RELIANCE", "BHARTIARTL", "DATAPATTNS", 
    "AIAENG", "LT", "AXISBANK", "HCLTECH", "CUB", "HINDCOPPER",
    # ETFs
    "METALIETF", "HDFCLOWVOL", "HDFCMID150", "ITBEES",
    "HDFCNEXT50", "INFRAIETF", "CONSUMIETF", "HDFCSML250",
    "AUTOBEES", "HDFCNIFTY", "BANKBEES", "GOLDIETF", "SILVERIETF"
]

OUTPUT_FILE = "portfolio_data.json"

def run_scanner():
    user_data_dir = os.path.join(os.getcwd(), 'browser_data')
    
    results = {}
    
    print(f"🚀 Starting Portfolio Scanner for {len(SYMBOLS)} symbols...")
    
    with sync_playwright() as p:
        # Launch persistent context
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
        
        for symbol in SYMBOLS:
            print(f"\n🔍 Analyzing: {symbol} ...")
            try:
                # Navigate to the chart for this symbol
                url = f"https://www.tradingview.com/chart/?symbol=NSE:{symbol}"
                page.goto(url)
                
                # Wait for load - indicators take time to calculate and render labels
                print("   ⏳ Loading chart & indicators (8s)...")
                time.sleep(8) 
                
                # Extract text content
                page_text = page.inner_text("body")
                
                # Filter for the specific Dashboard text block
                # We look for the "Weinstein & Swing Pro Dashboard" signature or specific data patterns
                # Based on previous dump: "09-Jan-26: 1. RRG=..."
                
                # Simple extraction strategy: Find the block containing "Entry#"
                # We split by lines and look for relevant lines
                
                relevant_lines = []
                capture = False
                
                for line in page_text.split('\n'):
                    line = line.strip()
                    # Start capturing near the dashboard header or data
                    if "Weinstein & Swing Pro Dashboard" in line:
                         # This might appear multiple times, but let's capture context
                         pass
                    
                    # The data lines usually look like "Entry#1=..." or "RRG=..."
                    if "Entry#" in line or "RRG=" in line or "News::" in line:
                        relevant_lines.append(line)
                        print(f"   ✅ Found Data: {line[:50]}...")
                
                results[symbol] = relevant_lines
                
            except Exception as e:
                print(f"   ❌ Error scanning {symbol}: {e}")
                results[symbol] = {"error": str(e)}
        
        print("\n💾 Saving results...")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4)
            
        print(f"✅ Scanning Complete! Data saved to {OUTPUT_FILE}")
        
        browser.close()

if __name__ == "__main__":
    run_scanner()
