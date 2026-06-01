import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import json
import time
import os
import sys
from datetime import datetime

# ==========================================
# 1. CONFIGURATION
# ==========================================
MY_SCANS = {
    "1": {
        "name": "Stage 2 Hunter (Weekend/Positional)",
        "url": "https://chartink.com/screener/weinstein-stage-2-hunter",
        "filter_mode": "MOMENTUM",
        "filename": "Stage2_Hunter.csv"  # <--- Custom Filename
    },
    "2": {
        "name": "Stage 2 Pullback (Daily/Swing)",
        "url": "https://chartink.com/screener/stage-2-pullback",
        "filter_mode": "VOLUME",
        "filename": "Stage2_Pullback.csv" # <--- Custom Filename
    },
    "3": {
        "name": "Early Bird (RRG Improving -> Leading)",
        "url": "https://chartink.com/screener/early-bird-scanner",
        "filter_mode": "ACCUMULATION",
        "filename": "Early_Birds.csv"     # <--- Custom Filename
    },
    "4": {
        "name": "Strong Leaders (RSI 60+ Momentum)",
        "url": "https://chartink.com/screener/strong-leaders",
        "filter_mode": "STRENGTH",
        "filename": "Strong_Leaders.csv"  # <--- Custom Filename
    }
}

# ==========================================
# 2. FILTERING ENGINE
# ==========================================
def filter_and_rank(df, mode):
    """Reduces the raw list to the Top Candidates."""
    print(f"\n📊 Processing {len(df)} raw results...")
    
    # Basic Cleanup
    df = df[df['Price'] > 40].copy()
    if 'Volume' in df.columns:
        df = df[df['Volume'] > 50000].copy()
    
    # Ranking Logic
    if mode == "ACCUMULATION": 
        # Early Birds: High Volume, Price not yet exploded
        df = df[df['%Chg'] < 10] 
        df = df.sort_values(by='Volume', ascending=False)
        print("   👉 Strategy: Ranked by VOLUME (Accumulation)")
        
    elif mode == "STRENGTH": 
        # Leaders: Highest % Change
        df = df.sort_values(by='%Chg', ascending=False)
        print("   👉 Strategy: Ranked by STRENGTH (% Change)")

    elif mode == "MOMENTUM": 
        # Hunter: Momentum
        df = df.sort_values(by='%Chg', ascending=False)
        print("   👉 Strategy: Ranked by MOMENTUM")
        
    else: 
        # Default/Pullback
        df = df.sort_values(by='Volume', ascending=False)
        print("   👉 Strategy: Ranked by LIQUIDITY")

    # Shortlist Top 15 (Slightly larger list for RRG Analysis)
    top_n = 15 if len(df) > 15 else len(df)
    return df.head(top_n)

# ==========================================
# 3. MAIN SCRIPT
# ==========================================
print("\n" + "="*60)
print("🔍 CHARTINK INTELLIGENT SCANNER (V9.0 - NAMED EXPORT)")
print("="*60)

# --- SELECT SCANNER ---
print("Select a Scanner to run:")
for key, scan in MY_SCANS.items():
    if "PASTE" not in scan['url']:
        print(f" {key}. {scan['name']}")
    else:
        print(f" {key}. {scan['name']} (⚠️ URL Not Configured)")
print(" 5. Paste a new URL manually")

choice = input("\n👉 Enter Option (1-5): ").strip()

target_url = ""
filter_mode = "VOLUME"
base_filename = "Chartink_Manual_Scan.csv" # Default for manual

if choice in MY_SCANS:
    target_url = MY_SCANS[choice]['url']
    filter_mode = MY_SCANS[choice].get('filter_mode', 'VOLUME')
    base_filename = MY_SCANS[choice].get('filename', 'Chartink_Result.csv')
    
    if "PASTE" in target_url:
        print(f"❌ Error: URL not configured for Option {choice}.")
        target_url = input("   Paste it here now: ").strip()
elif choice == "5":
    target_url = input("👉 Paste Chartink URL: ").strip()
else:
    print("❌ Invalid Option.")
    time.sleep(2)
    exit()

if not target_url: exit()

# --- CONNECT ---
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest"
})

try:
    print(f"\n⏳ Connecting to Chartink...")
    r = session.get(target_url)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # CSRF
    csrf_meta = soup.select_one('meta[name="csrf-token"]')
    if not csrf_meta:
        print("❌ Error: CSRF Token not found.")
        time.sleep(3)
        exit()
    csrf_token = csrf_meta['content']
    
    # LOGIC
    scan_clause = None
    match = re.search(r"scan_clause\s*=\s*['\"](.*?)['\"];", r.text)
    if match: scan_clause = match.group(1)
    
    if not scan_clause:
        scanner_tag = soup.select_one('scanner')
        if scanner_tag and scanner_tag.has_attr(':scan-json'):
            try:
                json_str = scanner_tag[':scan-json']
                scan_data = json.loads(json_str)
                scan_clause = scan_data.get('atlas_query')
            except: pass

    if not scan_clause:
        print("❌ CRITICAL: Could not find scan logic.")
        exit()
        
    # FETCH
    print("🚀 Fetching Data from Backend...")
    payload = {'scan_clause': scan_clause, '_token': csrf_token}
    
    r_data = session.post("https://chartink.com/screener/process", data=payload)
    json_data = r_data.json()
    stock_list = json_data.get('data', [])
    
    if not stock_list:
        print("⚠️ Scan completed but returned 0 stocks.")
        exit()

    # PROCESS
    df = pd.DataFrame(stock_list)
    col_map = {'nsecode': 'Symbol', 'close': 'Price', 'per_chg': '%Chg', 'volume': 'Volume'}
    if 'nsecode' in df.columns:
        df.rename(columns=col_map, inplace=True)
        keep_cols = [c for c in col_map.values() if c in df.columns]
        df = df[keep_cols]

    # APPLY FILTER
    final_df = filter_and_rank(df, filter_mode)

    # SAVE WITH CUSTOM NAME
    timestamp = datetime.now().strftime('%H%M%S')
    
    # Create the timestamped fallback name just in case
    name_part, ext_part = os.path.splitext(base_filename)
    timestamp_filename = f"{name_part}_{timestamp}{ext_part}"
    
    paths_to_try = [
        ("Current Folder", base_filename),
        ("Current Folder (Backup)", timestamp_filename),
        ("Desktop", os.path.join(os.path.expanduser("~"), "Desktop", base_filename))
    ]
    
    saved_path = ""
    print(f"\n💾 Saving as '{base_filename}'...")
    
    for loc_name, full_path in paths_to_try:
        try:
            final_df.to_csv(full_path, index=False)
            print(f"✅ SUCCESS: Saved to {loc_name}")
            print(f"   Path: {full_path}")
            saved_path = full_path
            break
        except Exception as e:
            pass

    if saved_path:
        print("\n" + "="*40)
        print(f"🏆 TOP CANDIDATES ({filter_mode})")
        print("="*40)
        print(final_df.head(5).to_string(index=False))
        print("-" * 40)

except Exception as e:
    print(f"\n❌ CRASH: {e}")

input("\nPress Enter to return to Commander...")