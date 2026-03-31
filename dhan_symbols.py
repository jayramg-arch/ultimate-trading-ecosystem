import pandas as pd
import requests
from io import BytesIO

def get_nse_id_map():
    print("⏳ Downloading Dhan Scrip Master (This takes 5-10 seconds)...")
    try:
        url = "https://images.dhan.co/api-data/api-scrip-master.csv"
        response = requests.get(url)
        response.raise_for_status()
        
        # Load CSV
        df = pd.read_csv(BytesIO(response.content), low_memory=False)
        
        # Filter for NSE Equity only (Series 'EQ') to avoid noise
        # Note: Dhan column names are specific
        # SEM_EXM_EXCH_ID: 'NSE', SEM_INSTRUMENT_NAME: 'EQUITY'
        mask = (df['SEM_EXM_EXCH_ID'] == 'NSE') & (df['SEM_INSTRUMENT_NAME'] == 'EQUITY') & (df['SEM_SERIES'] == 'EQ')
        df_nse = df[mask].copy()
        
        # Create a Dictionary: {'RELIANCE': '1333', 'TCS': '11536'}
        # Clean whitespace just in case
        df_nse['SEM_TRADING_SYMBOL'] = df_nse['SEM_TRADING_SYMBOL'].str.strip()
        
        symbol_map = dict(zip(df_nse['SEM_TRADING_SYMBOL'], df_nse['SEM_SMST_SECURITY_ID']))
        
        print(f"✅ Loaded {len(symbol_map)} NSE Symbols.")
        return symbol_map
        
    except Exception as e:
        print(f"❌ Error fetching Symbols: {e}")
        return {}

if __name__ == "__main__":
    # Test it
    mapping = get_nse_id_map()
    print("Test Lookup for 'CRAFTSMAN':", mapping.get('CRAFTSMAN', 'Not Found'))