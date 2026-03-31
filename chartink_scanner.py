import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import os
import time

# ==========================================
# 1. YOUR SAVED SCANNERS (CONFIGURE HERE)
# ==========================================
MY_SCANS = {
    "1": {
        "name": "Stage 2 Hunter (Breakout)",
        # ⬇️ PASTE YOUR HUNTER URL INSIDE THE QUOTES BELOW ⬇️
        "url": "https://chartink.com/screener/weinstein-stage-2-hunter" 
    },
    "2": {
        "name": "Stage 2 Pullback (Low Risk)",
        # ⬇️ PASTE YOUR PULLBACK URL INSIDE THE QUOTES BELOW ⬇️
        "url": "https://chartink.com/screener/stage-2-pullback"
    }
}

# ==========================================
# 2. SCANNER LOGIC
# ==========================================
print("\n" + "="*60)
print("🔍 CHARTINK MULTI-SCANNER (STEALTH MODE)")
print("="*60)

# --- SELECT SCANNER ---
print("Select a Scanner to run:")
for key, scan in MY_SCANS.items():
    # Only show if the user has actually saved a URL
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
        print(f"\n❌ Error: You haven't pasted the URL for '{MY_SCANS[choice]['name']}' in the script yet.")
        print("   Please open 'chartink_scanner.py' and paste the link in the configuration section.")
        new_link = input("   Or paste it here for this run: ").strip()
        if new_link: target_url = new_link
        else: exit()
elif choice == "3":
    target_url = input("👉 Paste Chartink URL: ").strip()
else:
    print("❌ Invalid Option.")
    exit()

# --- CONNECT & SCRAPE ---
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": target_url
})

try:
    print(f"\n⏳ Connecting to Chartink...")
    
    # 1. Get the Page
    r = session.get(target_url)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # 2. Extract CSRF Token
    csrf_meta = soup.select_one('meta[name="csrf-token"]')
    if not csrf_meta:
        print("❌ Error: Could not fetch CSRF token. The URL might be invalid.")
        exit()
    csrf_token = csrf_meta['content']
    
    # 3. Extract Scan Logic (Regex)
    script_content = r.text
    match = re.search(r"scan_clause\s*=\s*'(.*?)';", script_content)
    
    if not match:
        print("❌ Could not find scan logic. Ensure this is a valid Screener URL.")
        exit()
        
    scan_clause = match.group(1)
    
    # 4. Fetch Data
    print("🚀 Fetching Results...")
    payload = {'scan_clause': scan_clause, '_token': csrf_token}
    r_data = session.post("https://chartink.com/screener/process", data=payload)
    
    json_data = r_data.json()
    stock_list = json_data.get('data', [])
    
    if not stock_list:
        print("⚠️ Scan returned 0 results (No stocks found).")
        exit()
        
    # 5. Process & Save
    df = pd.DataFrame(stock_list)
    
    # Standardize Columns
    if 'nsecode' in df.columns:
        df.rename(columns={'nsecode': 'Symbol', 'close': 'Price', 'per_chg': '%Chg', 'volume': 'Volume'}, inplace=True)
        cols_to_keep = [c for c in ['Symbol', 'Price', '%Chg', 'Volume'] if c in df.columns]
        df = df[cols_to_keep]

    # Save to CSV
    filename = "chartink_results.csv"
    df.to_csv(filename, index=False)
    
    print(f"\n✅ SUCCESS: Found {len(df)} Stocks.")
    print(df.head(5).to_string(index=False))
    print(f"\n💾 Saved to: {filename}")

except Exception as e:
    print(f"\n❌ Error: {e}")

input("\nPress Enter to return to Commander...")