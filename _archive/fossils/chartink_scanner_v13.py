import requests
from bs4 import BeautifulSoup
import pandas as pd

# --- 🛠️ SCAN CATALOG (PASTE YOUR LOGIC STRINGS HERE) 🛠️ ---
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

# Generic URL (The script relies on the logic strings above, not the URL)
SCAN_REFERER = "https://chartink.com/screener/"
OUTPUT_FILENAME = "chartink_results.csv"
# -------------------------------------------------------------

def fetch_specific_scan(scan_name):
    """
    Runs a specific scan strategy chosen from the catalog.
    """
    print(f"\n🚀 Launching Scanner: {scan_name}...")
    
    if scan_name not in SCAN_CATALOG:
        print(f"❌ Error: Scan '{scan_name}' not found in Catalog.")
        return False

    scan_clause = SCAN_CATALOG[scan_name]
    
    with requests.Session() as s:
        try:
            # 1. Get CSRF Token
            r_init = s.get(SCAN_REFERER)
            r_init.raise_for_status()
            soup = BeautifulSoup(r_init.text, 'html.parser')
            csrf_token = soup.find('meta', {'name': 'csrf-token'})['content']
            
        except Exception as e:
            print(f"❌ Error fetching token: {e}")
            return False

        # 2. Prepare Data
        payload = {'scan_clause': scan_clause, '_token': csrf_token}
        headers = {
            'x-csrf-token': csrf_token, 
            'referer': SCAN_REFERER,
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }

        # 3. Fetch Results
        print("📥 Downloading results...")
        try:
            r_post = s.post("https://chartink.com/screener/process", data=payload, headers=headers)
            r_post.raise_for_status()
            data = r_post.json()
            stock_list = data.get('data', [])
            
            if stock_list:
                df = pd.DataFrame(stock_list)
                if 'nsecode' in df.columns:
                    df.rename(columns={'nsecode': 'Symbol'}, inplace=True)
                
                # Save with a specific name so we know which scan it was
                filename = f"chartink_{scan_name.replace(' ', '_')}.csv"
                df.to_csv(filename, index=False)
                
                # ALSO save as generic 'chartink_results.csv' for the Matcher to use
                df.to_csv(OUTPUT_FILENAME, index=False)
                
                print(f"✅ Success! Found {len(df)} stocks.")
                print(f"💾 Saved to: {filename} (and updated {OUTPUT_FILENAME})")
                return True
            else:
                print("⚠️ Scan returned 0 results.")
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False