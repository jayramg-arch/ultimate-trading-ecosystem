import os
from dotenv import load_dotenv
from dhanhq import dhanhq
import pandas as pd
from datetime import datetime

# Load Environment Variables
load_dotenv('e:/Gemini/VS Code/.env')
client_id = os.getenv('DHAN_CLIENT_ID')
access_token = os.getenv('DHAN_ACCESS_TOKEN')

if not client_id or not access_token:
    print("Error: DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN not found.")
    exit()

try:
    dhan = dhanhq(client_id, access_token)
    print("Dhan Client Initialized.")
    
    # Check available methods relating to 'trade' or 'history'
    # methods = dir(dhan)
    # relevant = [m for m in methods if 'trade' in m.lower() or 'history' in m.lower() or 'ledger' in m.lower()]
    # print(f"Relevant Methods: {relevant}")
    
    # Try fetching trade history for FY25-26
    # From: 2025-04-01 To: Now
    from_date = '2025-04-01'
    to_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f"Fetching Trade History from {from_date} to {to_date}...")
    
    # Common method names in APIs: get_trade_history, get_order_history
    # Based on DhanHQ docs (mental model), it might be `get_trade_history`
    
    # We will try get_trade_history
    try:
        response = dhan.get_trade_history(
            from_date=from_date,
            to_date=to_date,
            page_number=0
        )
        print("Response Received.")
        # print(response)
        
        if response['status'] == 'success':
            data = response['data']
            print(f"Number of trades: {len(data)}")
            if len(data) > 0:
                df = pd.DataFrame(data)
                print(df[['customSymbol', 'exchangeSegment', 'transactionType', 'tradedQuantity', 'tradedPrice']].head())
            else:
                print("No trades found in this period.")
        else:
            print(f"API Error: {response}")
            
    except Exception as e:
        print(f"Error calling get_trade_history: {e}")
        
except Exception as e:
    print(f"Initialization Error: {e}")
