import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import json
import time
import os

# ==========================================
# 1. CONFIGURATION
# ==========================================
MY_SCANS = {
    "1": {
        "name": "Stage 2 Hunter (Breakout)",
        # ⬇️ PASTE URL BELOW ⬇️
        "url": "https://chartink.com/screener/weinstein-stage-2-hunter" 
    },
    "2": {
        "name": "Stage 2 Pullback (Low Risk)",
        # ⬇️ PASTE URL BELOW ⬇️
        "url": "https://chartink.com/screener/stage-2-pullback"
    }
}

# ==========================================
# 2. SCANNER LOGIC
# ==========================================
print("\n" + "="*60)
print("🔍 CHARTINK ATLAS SCANNER (V4.0 - ROBUST)")
print("="*60)

# --- SELECT SCANNER ---
print("Select a Scanner to run:")
for key, scan in MY_SCANS.items():
    if "PASTE" not in scan['url']:
        print(f" {key}. {scan['name']}")
    else:
        print(f" {key}. {scan['name']} (⚠️ URL Not Configured)")
print(" 3. Paste a new URL manually")

choice = input("\n👉 Enter Option (1-3): ").strip()

target_url = ""
if choice in MY_SCANS:
    target_url = MY_SCANS[choice]['url']
    if "PASTE" in target_url:
        print(f"❌ Error: URL not configured for Option {choice}.")
        target_url = input("   Paste it here now: ").strip()
elif choice == "3":
    target_url = input("👉 Paste Chartink URL: ").strip()
else:
    print("❌ Invalid Option.")
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
        exit()
    csrf_token = csrf_meta['content']
    
    # 2. HUNT FOR SCAN LOGIC (The "Atlas" Fix)
    scan_clause = None
    
    # Method A: Try the "Old Style" Regex
    match = re.search(r"scan_clause\s*=\s*['\"](.*?)['\"];", r.text)
    if match:
        print("✅ Detected Legacy Scanner.")
        scan_clause = match.group(1)
    
    # Method B: Try the "New Atlas" JSON
    if not scan_clause:
        scanner_tag = soup.select_one('scanner')
        if scanner_tag and scanner_tag.has_attr(':scan-json'):
            print("✅ Detected Atlas Scanner (New Gen).")
            try:
                json_str = scanner_tag[':scan-json']
                scan_data = json.loads(json_str)
                scan_clause = scan_data.get('atlas_query')
            except Exception as e:
                print(f"⚠️ Failed to parse Atlas JSON: {e}")

    if not scan_clause:
        print("❌ CRITICAL: Could not find scan logic in page.")
        exit()
        
    # 3. FETCH DATA
    print("🚀 Fetching Data from Backend...")
    payload = {'scan_clause': scan_clause, '_token': csrf_token}
    
    r_data = session.post("https://chartink.com/screener/process", data=payload)
    json_data = r_data.json()
    
    stock_list = json_data.get('data', [])
    
    if not stock_list:
        print("⚠️ Scan completed but returned 0 stocks.")
        exit()

    # 4. SAVE TO CSV (ANTI-LOCK MECHANISM)
    df = pd.DataFrame(stock_list)
    
    # Clean Columns
    col_map = {'nsecode': 'Symbol', 'close': 'Price', 'per_chg': '%Chg', 'volume': 'Volume'}
    if 'nsecode' in df.columns:
        df.rename(columns=col_map, inplace=True)
        keep_cols = [c for c in col_map.values() if c in df.columns]
        df = df[keep_cols]

    filename = "chartink_results.csv"
    
    # --- NEW: RETRY LOGIC FOR LOCKED FILES ---
    while True:
        try:
            df.to_csv(filename, index=False)
            break # Success, exit loop
        except PermissionError:
            print(f"\n❌ ERROR: '{filename}' is open in Excel!")
            print("👉 Please CLOSE the Excel file and press Enter to save...")
            input() # Wait for user
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")
            exit()
            
    print(f"\n✅ SUCCESS: Found {len(df)} Stocks.")
    print(df.head(5).to_string(index=False))
    print(f"\n💾 Saved to: {filename}")

except Exception as e:
    print(f"\n❌ CRASH: {e}")

input("\nPress Enter to return to Commander...")