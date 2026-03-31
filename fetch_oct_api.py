import os
import pandas as pd
from dhanhq import dhanhq
from dotenv import load_dotenv
from dhan_auth import ensure_valid_token
import datetime

load_dotenv(override=True)

def fetch_oct_trades():
    tok = ensure_valid_token()
    cid = os.getenv("DHAN_CLIENT_ID")
    if not tok or not cid: 
        print("Dhan Auth Failed.")
        return
    
    try:
        dhan = dhanhq(client_id=cid, access_token=tok)
        # Search for Oct 2025
        from_date = '2025-10-01'
        to_date = '2025-10-31'
        
        all_trades = []
        print(f"Fetching trades from {from_date} to {to_date}...")
        
        for page in range(0, 10): # Most likely only a few pages
            resp = dhan.get_trade_history(from_date=from_date, to_date=to_date, page_number=page)
            if resp['status'] == 'success' and resp['data']:
                all_trades.extend(resp['data'])
            else:
                break
        
        if not all_trades:
            print("No trades found in October 2025 via API.")
            return
            
        df = pd.DataFrame(all_trades)
        print(f"Found {len(df)} transactions in October 2025.")
        
        # Display Sells specifically
        sells = df[df['transactionType'] == 'SELL']
        print(f"\n--- SELL Trades in October 2025 ({len(sells)} total) ---")
        if not sells.empty:
            print(sells[['exchangeTime', 'tradingSymbol', 'tradedQuantity', 'tradedPrice']])
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_oct_trades()
