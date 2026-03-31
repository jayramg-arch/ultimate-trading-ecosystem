import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import os
import time

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
print("🔍 CHARTINK DEEP SCANNER (V2.0)")
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

# --- CONNECT WITH "HUMAN" HEADERS ---
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://chartink.com/",
    "Origin": "https://chartink.com",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
})

try:
    print(f"\n⏳ Connecting to Chartink...")
    r = session.get(target_url)
    
    # DEBUG: Check if we actually got the page
    if r.status_code != 200:
        print(f"❌ Server returned Status Code: {r.status_code}")
        exit()

    soup = BeautifulSoup(r.text, 'html.parser')
    
    # 1. EXTRACT CSRF TOKEN
    csrf_meta = soup.select_one('meta[name="csrf-token"]')
    if not csrf_meta:
        print("❌ Error: Could not find CSRF Token.")
        print("   (Saving debug file...)")
        with open("debug_chartink_error.html", "w", encoding="utf-8") as f:
            f.write(r.text)
        print("   👉 Open 'debug_chartink_error.html' to see what page we loaded.")
        exit()
        
    csrf_token = csrf_meta['content']
    
    # 2. EXTRACT SCAN LOGIC (FLEXIBLE REGEX)
    # This regex now looks for either ' OR " quotes
    script_content = r.text
    match = re.search(r"scan_clause\s*=\s*['\"](.*?)['\"];", script_content)
    
    if not match:
        print("❌ Error: Could not find 'scan_clause'.")
        print("   (Saving debug file...)")
        with open("debug_chartink_error.html", "w", encoding="utf-8") as f:
            f.write(r.text)
        print("   👉 Open 'debug_chartink_error.html' to see what went wrong.")
        exit()
        
    scan_clause = match.group(1)
    
    # 3. FETCH DATA
    print("🚀 Fetching Data from Backend...")
    payload = {'scan_clause': scan_clause, '_token': csrf_token}
    
    # Important: The process URL needs specific headers
    session.headers.update({
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    })
    
    r_data = session.post("https://chartink.com/screener/process", data=payload)
    
    try:
        json_data = r_data.json()
    except:
        print("❌ Error: Backend returned non-JSON response.")
        print(r_data.text[:500])
        exit()
        
    stock_list = json_data.get('data', [])
    
    if not stock_list:
        print("⚠️ Scan completed but found 0 stocks.")
        exit()

    # 4. SAVE TO CSV
    df = pd.DataFrame(stock_list)
    
    # Clean Columns
    col_map = {'nsecode': 'Symbol', 'close': 'Price', 'per_chg': '%Chg', 'volume': 'Volume'}
    if 'nsecode' in df.columns:
        df.rename(columns=col_map, inplace=True)
        # Keep only relevant columns if they exist
        keep_cols = [c for c in col_map.values() if c in df.columns]
        df = df[keep_cols]

    filename = "chartink_results.csv"
    df.to_csv(filename, index=False)
    
    print(f"\n✅ SUCCESS: Found {len(df)} Stocks.")
    print(df.head(5).to_string(index=False))
    print(f"\n💾 Saved to: {filename}")

except Exception as e:
    print(f"\n❌ CRASH: {e}")

input("\nPress Enter to exit...")