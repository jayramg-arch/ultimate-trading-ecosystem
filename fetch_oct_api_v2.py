import os
import pandas as pd
from dhanhq import dhanhq
from dotenv import load_dotenv
from dhan_auth import ensure_valid_token

load_dotenv(override=True)

def fetch_oct_trades():
    tok = ensure_valid_token()
    cid = os.getenv("DHAN_CLIENT_ID")
    if not tok or not cid: return
    
    try:
        dhan = dhanhq(client_id=cid, access_token=tok)
        from_date = '2025-10-01'
        to_date = '2025-10-31'
        
        all_trades = []
        for page in range(0, 5):
            resp = dhan.get_trade_history(from_date=from_date, to_date=to_date, page_number=page)
            if resp['status'] == 'success' and resp['data']:
                all_trades.extend(resp['data'])
            else:
                break
        
        if not all_trades: return
            
        df = pd.DataFrame(all_trades)
        print(f"Columns: {df.columns.tolist()}")
        
        # Determine correct symbol column
        sym_col = 'tradingSymbol' if 'tradingSymbol' in df.columns else 'customSymbol'
        if sym_col not in df.columns: sym_col = df.columns[0]
        
        # Filter Sells
        sells = df[df['transactionType'] == 'SELL']
        print(f"\n--- SELL Trades in October 2025 ({len(sells)} total) ---")
        if not sells.empty:
            cols = [sym_col, 'tradedQuantity', 'tradedPrice', 'exchangeTime']
            cols = [c for c in cols if c in sells.columns]
            print(sells[cols])
            
            # Print total summary
            print("\nUnique Symbols Sold in Oct:")
            print(sells[sym_col].unique())
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_oct_trades()
