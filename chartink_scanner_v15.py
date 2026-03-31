import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import os
import json
import time

# ==========================================
# 1. SCAN LOGIC CATALOG (Corrected for GUI)
# ==========================================
# ⚠️ DO NOT PASTE OLD CATALOG HERE.
# The GUI needs these numbers ("1", "2") to work.
# The logic below matches your Weinstein requirements exactly.

SCAN_CATALOG = {
    "1": {
        "name": "Stage 2 Hunter (Positional)",
        # Logic: Weekly SMA30 rising + Breakout + RS Strong
        "logic": "( {57960} ( weekly sma( weekly close , 30 ) > 4 weeks ago sma( weekly close , 30 ) and daily sma( daily close , 50 ) > daily sma( daily close , 150 ) and daily sma( daily close , 150 ) > daily sma( daily close , 200 ) and weekly close > weekly sma( weekly close , 30 ) and weekly close > weekly max( 52 , weekly high ) * 0.85 and daily close > daily ema( daily close , 20 ) and weekly volume > weekly sma( weekly volume , 20 ) * 1 and weekly close / rs:'nifty500' weekly close > weekly sma( weekly close / rs:'nifty500' weekly close , 30 ) and weekly rsi( 14 ) > 55 ) )",
        "filename": "chartink_results.csv" # Main output for Matcher
    },
    "2": {
        "name": "Stage 2 Pullback (Swing)",
        # Logic: Uptrend but dipping near 20EMA
        "logic": "( {57960} ( weekly close > weekly sma( weekly close , 30 ) and weekly sma( weekly close , 30 ) > 4 weeks ago sma( weekly close , 30 ) and daily close > daily sma( daily close , 150 ) and daily close > daily sma( daily close , 200 ) and daily close < daily ema( daily close , 20 ) and daily close > daily ema( daily close , 20 ) * 0.95 and daily rsi( 14 ) > 50 and daily rsi( 14 ) < 65 ) )",
        "filename": "chartink_results.csv" # Overwrites main for Matcher
    },
    "3": {
        "name": "Early Birds (Accumulation)",
        # Logic: Improving Quadrant (Momentum shift + Volume)
        "logic": "( {57960} ( weekly rsi( 14 ) > 50 and weekly macd line( 26 , 12 , 9 ) > weekly macd signal( 26 , 12 , 9 ) and daily close > daily sma( daily close , 50 ) and daily close < daily sma( daily close , 50 ) * 1.15 and daily volume > 100000 ) )",
        "filename": "Early_Birds.csv"
    },
    "4": {
        "name": "Strong Leaders (Momentum)",
        # Logic: Leading Quadrant (High RSI + High ADX)
        "logic": "( {57960} ( daily rsi( 14 ) > 60 and daily close > daily sma( daily close , 20 ) and daily adx( 14 ) > 25 and daily volume > daily sma( daily volume , 20 ) ) )",
        "filename": "Strong_Leaders.csv"
    }
}

# ==========================================
# 2. SCANNER ENGINE
# ==========================================
def run_scan(scan_key):
    # Sanitize input (strip whitespace/quotes)
    scan_key = str(scan_key).strip().replace("'", "").replace('"', "")
    
    if scan_key not in SCAN_CATALOG:
        print(f"❌ Invalid Option: '{scan_key}'")
        print("   (Expected: '1', '2', '3', or '4')")
        return

    scan_info = SCAN_CATALOG[scan_key]
    print(f"\n🚀 STARTING: {scan_info['name']}")
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "X-Requested-With": "XMLHttpRequest"
    })

    try:
        # 1. Get CSRF Token
        print("⏳ Connecting to Chartink...")
        r = session.get("https://chartink.com/screener/time-pass")
        soup = BeautifulSoup(r.text, 'html.parser')
        csrf_tag = soup.select_one('meta[name="csrf-token"]')
        
        if not csrf_tag:
            print("❌ Error: Could not fetch CSRF token. Site may be blocking script.")
            return
            
        csrf = csrf_tag['content']

        # 2. Fetch Data
        print("📥 Downloading Data...")
        payload = {'scan_clause': scan_info['logic'], '_token': csrf}
        r_post = session.post("https://chartink.com/screener/process", data=payload)
        
        try:
            data = r_post.json()
        except:
            print("❌ Error: Failed to parse response (Check your internet or URL).")
            return

        stock_list = data.get('data', [])

        if not stock_list:
            print("⚠️ Scan completed but returned 0 stocks (No matches found).")
            # Create empty CSV so Matcher doesn't crash
            pd.DataFrame(columns=['Symbol','Price','%Chg','Volume']).to_csv(scan_info['filename'], index=False)
            return

        # 3. Process & Save
        df = pd.DataFrame(stock_list)
        
        # Clean Columns
        rename_map = {'nsecode': 'Symbol', 'close': 'Price', 'per_chg': '%Chg', 'volume': 'Volume'}
        if 'nsecode' in df.columns:
            df.rename(columns=rename_map, inplace=True)
            cols = [c for c in rename_map.values() if c in df.columns]
            df = df[cols]

        filename = scan_info['filename']
        df.to_csv(filename, index=False)
        
        print(f"✅ SUCCESS: Found {len(df)} Stocks.")
        print(f"💾 Saved to: {filename}")
        
        # Display Top 5
        print("-" * 30)
        print(df.head(5).to_string(index=False))
        print("-" * 30)

    except Exception as e:
        print(f"❌ ERROR: {e}")

# ==========================================
# 3. MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("="*40)
    print("🔍 WEINSTEIN CHARTINK SCANNER v15")
    print("="*40)

    # CHECK FOR ARGUMENTS FROM GUI
    if len(sys.argv) > 1:
        # Arguments exist (e.g. "python scanner.py 1")
        choice = sys.argv[1]
        run_scan(choice)
        # Note: We do NOT use input() here, so the window can auto-close if you use /c in GUI
        # But currently GUI uses /k so you can see the result.
    
    else:
        # Manual Mode
        print("Select Scanner:")
        for k, v in SCAN_CATALOG.items():
            print(f" {k}. {v['name']}")
        
        choice = input("\n👉 Enter Option (1-4): ").strip()
        run_scan(choice)
        input("\nPress Enter to exit...")