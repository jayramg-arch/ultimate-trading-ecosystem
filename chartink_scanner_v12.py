import requests
from bs4 import BeautifulSoup
import pandas as pd

# --- 🛠️ USER CONFIGURATION (PASTE HERE) 🛠️ ---
# Paste the long string you copied from the Network Tab inside the quotes below.
# I have put a placeholder here - DELETE IT and paste your actual code.
MY_SCAN_CLAUSE = "( {57960} (  weekly sma(  weekly close , 30 ) >  4 weeks ago sma(  weekly close , 30 ) and  daily sma(  daily close , 50 ) >  daily sma(  daily close , 150 ) and  daily sma(  daily close , 150 ) >  daily sma(  daily close , 200 ) and  weekly close >  weekly sma(  weekly close , 30 ) and  weekly close >  weekly max( 52 ,  weekly high ) *  0.85 and  daily close >  daily ema(  daily close , 20 ) and  weekly volume >  weekly sma(  weekly volume , 20 ) *  1 and  weekly close / rs:'nifty500' weekly close >  weekly sma(  weekly close / rs:'nifty500' weekly close , 30 ) and  weekly close / rs:'nifty500' weekly close >  weekly sma(  weekly close / rs:'nifty500' weekly close , 4 ) and  weekly rsi( 14 ) >  55 and  daily adx( 14 ) >  20 and  weekly close >  20 ) ) " 

# URL just for reference (The script uses the code above, not the URL logic)
SCAN_REFERER = "https://chartink.com/screener/weinstein-stage-2-hunter"
OUTPUT_FILENAME = "chartink_results.csv"
# -----------------------------------------------

def fetch_chartink_manual():
    print(f"🚀 Connecting to Chartink...")
    
    with requests.Session() as s:
        try:
            # 1. Get CSRF Token (Permission)
            r_init = s.get(SCAN_REFERER)
            r_init.raise_for_status()
            soup = BeautifulSoup(r_init.text, 'html.parser')
            csrf_token = soup.find('meta', {'name': 'csrf-token'})['content']
            
        except Exception as e:
            print(f"❌ Error fetching CSRF token: {e}")
            return False

        # 2. Prepare Data
        payload = {
            'scan_clause': MY_SCAN_CLAUSE, 
            '_token': csrf_token
        }
        
        headers = {
            'x-csrf-token': csrf_token,
            'referer': SCAN_REFERER,
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }

        # 3. Fetch Results
        print("📥 Downloading scan results...")
        try:
            r_post = s.post("https://chartink.com/screener/process", data=payload, headers=headers)
            r_post.raise_for_status()
            
            data = r_post.json()
            stock_list = data.get('data', [])
            
            if stock_list:
                df = pd.DataFrame(stock_list)
                if 'nsecode' in df.columns:
                    df.rename(columns={'nsecode': 'Symbol'}, inplace=True)
                
                df.to_csv(OUTPUT_FILENAME, index=False)
                print(f"✅ Success! Saved {len(df)} stocks to {OUTPUT_FILENAME}")
                return True
            else:
                print("⚠️ Scan returned 0 results.")
                return False
                
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            return False

if __name__ == "__main__":
    fetch_chartink_manual()