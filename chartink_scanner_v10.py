import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

# --- CONFIGURATION ---
# The URL of your specific scan
SCAN_URL = "https://chartink.com/screener/weinstein-stage-2-hunter"
OUTPUT_FILENAME = "chartink_results.csv"
# ---------------------

def fetch_chartink_raw():
    print(f"🚀 Connecting to Chartink...")
    print(f"   Target: {SCAN_URL}")

    with requests.Session() as s:
        # 1. GET THE PAGE TO STEAL THE LOGIC
        # We need to visit the page to get two things:
        #  a) The CSRF Token (Permission)
        #  b) The Scan Clause (The Logic/Math for "Stage 2")
        try:
            r_init = s.get(SCAN_URL)
            r_init.raise_for_status()
            soup = BeautifulSoup(r_init.text, 'html.parser')

            # A. Get CSRF Token
            csrf_token = soup.find('meta', {'name': 'csrf-token'})['content']

            # B. Get Scan Clause (The Hidden Logic)
            # Chartink hides the logic inside a JavaScript variable named 'scan_clause'
            # We use Regex to find it inside the page text.
            script_content = r_init.text
            match = re.search(r"scan_clause\s*=\s*'(.*?)';", script_content)
            
            if match:
                # We found the logic!
                scan_condition = match.group(1)
                print("   ✅ Successfully extracted scan logic from the page.")
            else:
                # Fallback: Sometimes it is hidden in a different way
                print("   ⚠️ Could not auto-extract logic. Trying generic fallback...")
                # You can manually paste the condition below if auto-detection fails repeatedly
                scan_condition = "( {33492} ( [0] 15 minute close > [1] 15 minute close ) )"

        except Exception as e:
            print(f"❌ Error during setup: {e}")
            return False

        # 2. PREPARE THE DATA PACKET
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

        # 3. ASK SERVER FOR RESULTS
        print("📥 Downloading scan results...")
        try:
            # Note: The data endpoint is always /screener/process
            r_post = s.post("https://chartink.com/screener/process", data=payload, headers=headers)
            r_post.raise_for_status()
            
            data = r_post.json()
            
            stock_list = data.get('data', [])
            if stock_list:
                df = pd.DataFrame(stock_list)
                
                # CLEANUP: Keep only useful columns if desired, or keep all raw data
                # Typically we want 'nsecode' or 'symbol'
                if 'nsecode' in df.columns:
                    df.rename(columns={'nsecode': 'Symbol'}, inplace=True)
                    
                
                # Save Raw Data
                df.to_csv(OUTPUT_FILENAME, index=False)
                print(f"✅ Success! Saved {len(df)} stocks to {OUTPUT_FILENAME}")
                return True
            else:
                print("⚠️ Scan returned 0 results (Market might be closed or no matches).")
                return False
                
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            return False

if __name__ == "__main__":
    fetch_chartink_raw()