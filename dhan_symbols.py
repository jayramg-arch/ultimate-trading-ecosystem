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

_SECID_SYMBOL_CACHE = {}

def get_nse_secid_to_symbol():
    """Reverse map: {securityId(str) -> tradingSymbol} for ALL NSE instruments
    (equities AND ETFs — no EQ-series filter), since the Dhan trade-history API
    returns only securityId + customSymbol (full company name), never the ticker.
    Cached for the process lifetime.
    """
    if _SECID_SYMBOL_CACHE:
        return _SECID_SYMBOL_CACHE
    try:
        url = "https://images.dhan.co/api-data/api-scrip-master.csv"
        df = pd.read_csv(BytesIO(requests.get(url).content), low_memory=False)
        nse = df[df['SEM_EXM_EXCH_ID'] == 'NSE'].copy()
        nse['SEM_TRADING_SYMBOL'] = nse['SEM_TRADING_SYMBOL'].astype(str).str.strip()
        for _, r in nse.iterrows():
            _SECID_SYMBOL_CACHE[str(r['SEM_SMST_SECURITY_ID'])] = r['SEM_TRADING_SYMBOL']
    except Exception as e:
        print(f"❌ Error building securityId->symbol map: {e}")
    return _SECID_SYMBOL_CACHE


if __name__ == "__main__":
    # Test it
    mapping = get_nse_id_map()
    print("Test Lookup for 'CRAFTSMAN':", mapping.get('CRAFTSMAN', 'Not Found'))
    rev = get_nse_secid_to_symbol()
    print("Reverse lookup secId 11439:", rev.get('11439', 'Not Found'))