import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
import os
import json
import time

# ==========================================
# 1. SCAN LOGIC CATALOG (Atlas Strings)
# ==========================================
# These are the raw logic strings for the Weinstein Scanners.
SCAN_CATALOG = {
    # 1. THE BREAKOUT (Standard Stage 2)
    "Stage 2 Hunter": "( {57960} (  weekly sma(  weekly close , 30 ) >  4 weeks ago sma(  weekly close , 30 ) and  daily sma(  daily close , 50 ) >  daily sma(  daily close , 150 ) and  daily sma(  daily close , 150 ) >  daily sma(  daily close , 200 ) and  weekly close >  weekly sma(  weekly close , 30 ) and  weekly close >  weekly max( 52 ,  weekly high ) *  0.85 and  daily close >  daily ema(  daily close , 20 ) and  weekly volume >  weekly sma(  weekly volume , 20 ) *  1 and  weekly close / rs:'nifty500' weekly close >  weekly sma(  weekly close / rs:'nifty500' weekly close , 30 ) and  weekly close / rs:'nifty500' weekly close >  weekly sma(  weekly close / rs:'nifty500' weekly close , 4 ) and  weekly rsi( 14 ) >  55 and  daily adx( 14 ) >  20 and  weekly close >  20 ) ) ", 
    
    # 2. THE PULLBACK (Low Risk Entry near 20 EMA)
    "Stage 2 Pullback": "( {57960} (  weekly close >  weekly sma(  weekly close , 30 ) and  weekly rsi( 14 ) >  55 and  daily low <  daily ema(  daily close , 20 ) *  1.015 and  daily close >  daily ema(  daily close , 20 ) and  daily volume <  daily sma(  daily volume , 10 ) ) )",
    
    # 3. THE BOTTOM FISHING (Stage 1 to 2 transition)
    "Stage 2 Early Birds": "( {57960} (  weekly rsi( 14 ) >  50 and  daily close >  daily sma(  daily close , 50 ) and  daily close <  daily sma(  daily close , 50 ) *  1.15 and  daily volume >  100000 and  weekly macd line( 26 , 12 , 9 ) >  weekly macd signal( 26 , 12 , 9 ) ) ) ",
    
    # 4. THE MOMENTUM (High Relative Strength)
    "Stage 2 Strong Leaders": "( {57960} (  daily rsi( 14 ) >  60 and  daily close >  daily sma(  daily close , 20 ) and  daily adx( 14 ) >  25 and  daily volume >  daily sma(  daily volume , 20 ) ) ) "
}

# ==========================================
# 2. SCANNER ENGINE
# ==========================================
def run_scan(scan_key):
    if scan_key not in SCAN_CATALOG:
        print(f"❌ Invalid Option: {scan_key}")
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
        csrf = soup.select_one('meta[name="csrf-token"]')['content']

        # 2. Fetch Data
        print("📥 Downloading Data...")
        payload = {'scan_clause': scan_info['logic'], '_token': csrf}
        r_post = session.post("https://chartink.com/screener/process", data=payload)
        
        data = r_post.json()
        stock_list = data.get('data', [])

        if not stock_list:
            print("⚠️ No stocks found matching criteria.")
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
        
        # If it's Hunter or Pullback, show top 5
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
    print("🔍 WEINSTEIN CHARTINK SCANNER v14")
    print("="*40)

    # CHECK FOR ARGUMENTS FROM GUI
    if len(sys.argv) > 1:
        # Arguments exist (e.g. "python scanner.py 1")
        # Run automatically without asking user
        choice = sys.argv[1]
        run_scan(choice)
        # No input() here so it closes automatically when done (or GUI keeps it open)
    
    else:
        # No arguments (User ran it manually)
        # Show Menu
        print("Select Scanner:")
        for k, v in SCAN_CATALOG.items():
            print(f" {k}. {v['name']}")
        
        choice = input("\n👉 Enter Option (1-4): ").strip()
        run_scan(choice)
        input("\nPress Enter to exit...")