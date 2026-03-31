import os
import sys
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

# ==========================================
# 1. SCAN LOGIC CATALOG (FINAL)
# ==========================================
SCAN_CATALOG = {
    "1": {
        "name": "Stage 2 Hunter (Positional)",
        "logic": "( {57960} ( weekly sma( weekly close , 30 ) > 4 weeks ago sma( weekly close , 30 ) and weekly close > weekly sma( weekly close , 30 ) and daily close > daily sma( daily close , 50 ) and daily sma( daily close , 50 ) > daily sma( daily close , 150 ) and daily sma( daily close , 150 ) > daily sma( daily close , 200 ) and weekly close > weekly max( 52 , weekly high ) * 0.85 and daily ema( daily close , 20 ) <= daily sma( daily close , 50 ) * 1.06 and daily ema( daily close , 20 ) >= daily sma( daily close , 50 ) * 0.94 and daily volume < daily sma( daily volume , 50 ) and weekly rsi( 14 ) > 55 ) )",
        "filename": "Stage2_Hunter.csv"  # <--- UNIQUE NAME
    },
    "2": {
        "name": "Stage 2 Pullback (Swing)",
        "logic": "( {57960} ( daily close > daily sma( daily close , 50 ) and daily sma( daily close , 50 ) > daily sma( daily close , 150 ) and daily sma( daily close , 150 ) > daily sma( daily close , 200 ) and daily low <= daily ema( daily close , 20 ) * 1.015 and daily close >= daily ema( daily close , 20 ) * 0.985 and daily rsi( 14 ) >= 40 and daily rsi( 14 ) <= 60 and weekly rsi( 14 ) > 60 and daily volume < daily sma( daily volume , 50 ) * 0.75 and daily high - daily low < 1 day ago high - 1 day ago low ) )",
        "filename": "Stage2_Pullback.csv" # <--- UNIQUE NAME
    },
    "3": {
        "name": "Early Birds (Accumulation)",
        "logic": "( {57960} ( daily close > daily sma( daily close , 50 ) and daily close < daily sma( daily close , 50 ) * 1.15 and daily sma( daily close , 50 ) >= 5 days ago sma( daily close , 50 ) and weekly rsi( 14 ) > 50 and weekly volume > weekly sma( weekly volume , 10 ) * 2.0 and daily close > 1 day ago max( 20 , daily high ) ) )",
        "filename": "Early_Birds.csv"
    },
    "4": {
        "name": "Strong Leaders (Momentum)",
        "logic": "( {57960} ( daily rsi( 14 ) > 60 and daily adx( 14 ) > 25 and daily close > daily ema( daily close , 20 ) and daily ema( daily close , 20 ) > daily sma( daily close , 50 ) and daily sma( daily close , 50 ) > daily sma( daily close , 200 ) and daily volume > daily sma( daily volume , 20 ) ) )",
        "filename": "Strong_Leaders.csv"
    }
}

# ==========================================
# 2. SCANNER ENGINE
# ==========================================
def run_scan(scan_key, return_raw=False):
    scan_key = str(scan_key).strip().replace("'", "").replace('"', "")
    
    if scan_key not in SCAN_CATALOG:
        error_msg = f"❌ ERROR: Invalid Option '{scan_key}'"
        print(error_msg)
        return error_msg if return_raw else None

    scan_info = SCAN_CATALOG[scan_key]
    logic = scan_info['logic']

    # --- DYNAMIC VOLUME INJECTION ---
    # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    current_day = datetime.today().weekday()
    
    if scan_key == "3": # Early Birds (Uses Weekly Volume as a breakout trigger)
        if current_day <= 3: # Monday to Thursday
            print(f"📅 Day {current_day} (Early-Week): Injecting '1 week ago' volume logic for Early Birds.")
            # Swap current weekly volume with previous week's completed volume
            logic = logic.replace(
                "weekly volume > weekly sma( weekly volume , 10 ) * 2.0",
                "1 week ago weekly volume > 1 week ago weekly sma( weekly volume , 10 ) * 2.0"
            )
        else:
            print(f"📅 Day {current_day} (Late-Week/Weekend): Using Latest volume logic.")

    print(f"\n🚀 STARTING: {scan_info['name']}")
    
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"})

    try:
        print("⏳ Connecting to Chartink...")
        r = session.get("https://chartink.com/screener/time-pass")
        soup = BeautifulSoup(r.text, 'html.parser')
        csrf = soup.select_one('meta[name="csrf-token"]')['content']

        print("📥 Downloading Data...")
        payload = {'scan_clause': logic, '_token': csrf}
        r_post = session.post("https://chartink.com/screener/process", data=payload)
        data = r_post.json()
        
        df = pd.DataFrame(data.get('data', []))
        
        rename_map = {'nsecode': 'Symbol', 'close': 'Price', 'per_chg': '%Chg', 'volume': 'Volume'}
        if 'nsecode' in df.columns:
            df.rename(columns=rename_map, inplace=True)
            cols = [c for c in rename_map.values() if c in df.columns]
            df = df[cols]
        elif df.empty:
            df = pd.DataFrame(columns=['Symbol', 'Price', '%Chg', 'Volume'])

        filename = scan_info['filename']
        df.to_csv(filename, index=False)
        
        print(f"✅ SUCCESS: Saved to {filename} ({len(df)} stocks)")
        
        if return_raw:
            return df
            
    except Exception as e:
        print(f"❌ CRASH: {e}")
        if return_raw:
            return pd.DataFrame()

if __name__ == "__main__":
    print("="*40)
    print("🔍 CHARTINK SCANNER PRO")
    print("="*40)
    if len(sys.argv) > 1:
        run_scan(sys.argv[1])
    else:
        choice = input("\n👉 Enter Option (1-4): ").strip()
        run_scan(choice)
    
    input("\nPress Enter to exit...")