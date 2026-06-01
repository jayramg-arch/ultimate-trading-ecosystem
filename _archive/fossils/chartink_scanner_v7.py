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
# ⚠️ ACTION REQUIRED: PASTE YOUR LINKS INSIDE THE QUOTES BELOW
MY_SCANS = {
    "1": {
        "name": "Stage 2 Hunter (Weekend/Positional)",
        "url": "https://chartink.com/screener/weinstein-stage-2-hunter" 
    },
    "2": {
        "name": "Stage 2 Pullback (Daily/Swing)",
        "url": "https://chartink.com/screener/stage-2-pullback"
    },
    "3": {
        "name": "Early Bird (RRG Improving -> Leading)",
        "url": "https://chartink.com/screener/early-bird-scanner"
    },
    "4": {
        "name": "Strong Leaders (RSI 60+ Momentum)",
        "url": "https://chartink.com/screener/strong-leaders"
    }
}

# ==========================================
# 2. SCANNER LOGIC
# ==========================================
print("\n" + "="*60)
print("🔍 CHARTINK ATLAS SCANNER (V7.0 - COMPLETE SUITE)")
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
if choice in MY_SCANS:
    target_url = MY_SCANS[choice]['url']
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
    
    # 1. GET CSRF TOKEN
    csrf_meta = soup.select_one('meta[name="csrf-token"]')
    if not csrf_meta:
        print("❌ Error: CSRF Token not found. Is the URL correct?")
        time.sleep(3)
        exit()
    csrf_token = csrf_meta['content']
    
    # 2. HUNT FOR SCAN LOGIC
    scan_clause = None
    
    match = re.search(r"scan_clause\s*=\s*['\"](.*?)['\"];", r.text)
    if match:
        scan_clause = match.group(1)
    
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
        time.sleep(3)
        exit()
        
    # 3. FETCH DATA
    print("🚀 Fetching Data from Backend...")
    payload = {'scan_clause': scan_clause, '_token': csrf_token}
    
    r_data = session.post("https://chartink.com/screener/process", data=payload)
    json_data = r_data.json()
    
    stock_list = json_data.get('data', [])
    
    if not stock_list:
        print("⚠️ Scan completed but returned 0 stocks.")
        time.sleep(2)
        exit()

    # 4. PREPARE DATA
    df = pd.DataFrame(stock_list)
    
    col_map = {'nsecode': 'Symbol', 'close': 'Price', 'per_chg': '%Chg', 'volume': 'Volume'}
    if 'nsecode' in df.columns:
        df.rename(columns=col_map, inplace=True)
        keep_cols = [c for c in col_map.values() if c in df.columns]
        df = df[keep_cols]

    # 5. MULTI-LOCATION SAVE STRATEGY
    timestamp = datetime.now().strftime('%H%M%S')
    filename = "chartink_results.csv"
    
    # Try current folder first, then Desktop
    paths_to_try = [
        ("Current Folder", filename),
        ("Current Folder (New Name)", f"chartink_results_{timestamp}.csv"),
        ("Desktop", os.path.join(os.path.expanduser("~"), "Desktop", f"chartink_results_{timestamp}.csv"))
    ]
    
    saved_path = ""
    print("\n💾 Attempting to save...")
    for loc_name, full_path in paths_to_try:
        try:
            df.to_csv(full_path, index=False)
            print(f"✅ SUCCESS: Saved to {loc_name}")
            print(f"   Path: {full_path}")
            saved_path = full_path
            break
        except Exception as e:
            print(f"⚠️ Failed to save in {loc_name}: {e}")

    if not saved_path:
        print("\n❌ CRITICAL: Could not save file anywhere.")
    else:
        print("-" * 40)
        print(df.head(5).to_string(index=False))
        print("-" * 40)

except Exception as e:
    print(f"\n❌ CRASH: {e}")

input("\nPress Enter to return to Commander...")