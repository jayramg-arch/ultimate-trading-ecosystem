import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import json

# --- CONFIGURATION ---
SCAN_URL = "https://chartink.com/screener/weinstein-stage-2-hunter"
OUTPUT_FILENAME = "chartink_results.csv"
# ---------------------

def fetch_chartink_raw():
    print(f"🚀 Connecting to Chartink...")
    print(f"   Target: {SCAN_URL}")

    with requests.Session() as s:
        try:
            # 1. GET THE PAGE
            r_init = s.get(SCAN_URL)
            r_init.raise_for_status()
            soup = BeautifulSoup(r_init.text, 'html.parser')

            # A. Get CSRF Token
            csrf_token = soup.find('meta', {'name': 'csrf-token'})['content']

            # B. INTELLIGENT LOGIC EXTRACTION (The Fix)
            scan_condition = None
            
            # Method 1: Look for the hidden input field (Most reliable)
            hidden_input = soup.find('input', {'name': 'scan_clause'})
            if hidden_input and hidden_input.get('value'):
                scan_condition = hidden_input['value']
                print("   ✅ Logic found via Hidden Input Method.")

            # Method 2: Regex for Single Quotes (JS Variable)
            if not scan_condition:
                match_sq = re.search(r"scan_clause\s*=\s*'(.*?)';", r_init.text)
                if match_sq:
                    scan_condition = match_sq.group(1)
                    print("   ✅ Logic found via JS Variable (Single Quotes).")

            # Method 3: Regex for Double Quotes (Alternative JS formatting)
            if not scan_condition:
                match_dq = re.search(r'scan_clause\s*=\s*"(.*?)";', r_init.text)
                if match_dq:
                    scan_condition = match_dq.group(1)
                    print("   ✅ Logic found via JS Variable (Double Quotes).")

            # FAIL-SAFE: If all methods fail
            if not scan_condition:
                print("   ❌ CRITICAL: Could not extract scan logic automatically.")
                print("   -> Please paste the scan_clause manually in the script.")
                return False

        except Exception as e:
            print(f"❌ Error during setup: {e}")
            return False

        # 2. FETCH DATA
        payload = {
            'scan_clause': scan_condition, 
            '_token': csrf_token
        }
        
        headers = {
            'x-csrf-token': csrf_token,
            'referer': SCAN_URL,
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'x-requested-with': 'XMLHttpRequest'
        }

        print("📥 Downloading scan results...")
        try:
            r_post = s.post("https://chartink.com/screener/process", data=payload, headers=headers)
            r_post.raise_for_status()
            
            data = r_post.json()
            stock_list = data.get('data', [])
            
            if stock_list:
                df = pd.DataFrame(stock_list)
                
                # Standardize Symbol Column
                if 'nsecode' in df.columns:
                    df.rename(columns={'nsecode': 'Symbol'}, inplace=True)
                
                df.to_csv(OUTPUT_FILENAME, index=False)
                print(f"✅ Success! Saved {len(df)} stocks to {OUTPUT_FILENAME}")
                return True
            else:
                print(f"⚠️ Scan returned 0 results. (Double check if the market has data matching your criteria)")
                return False
                
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            return False

if __name__ == "__main__":
    fetch_chartink_raw()