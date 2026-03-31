import os
import pandas as pd
import numpy as np
import json
from dotenv import load_dotenv
from dhanhq import dhanhq
from datetime import datetime

# CONFIG
CSV_PATH = "portfolio.csv"
DEFAULT_SECTOR = "NSE:CNX500"

# 1. SETUP
load_dotenv()
try:
    dhan = dhanhq(os.getenv("DHAN_CLIENT_ID"), os.getenv("DHAN_ACCESS_TOKEN"))
except:
    print("❌ Error: Check .env file")
    exit()

print("\n" + "="*60)
print("🏥 PORTFOLIO SYNC & AUDIT")
print("="*60)

# 2. READ EXISTING MANUAL DATA (To preserve SL and Sector)
existing_data = {} # Key: Ticker (with NSE:), Value: {SL, Sector}
if os.path.exists(CSV_PATH):
    try:
        df_old = pd.read_csv(CSV_PATH)
        # Normalize headers just in case
        df_old.columns = df_old.columns.str.strip()
        
        for _, row in df_old.iterrows():
            ticker = str(row.get('Ticker', '')).strip().upper()
            if ticker:
                existing_data[ticker] = {
                    'SL': row.get('SL', 0.0),
                    'Sector': row.get('Sector', DEFAULT_SECTOR)
                }
        print(f"ℹ️  Loaded {len(existing_data)} existing records from {CSV_PATH}")
    except Exception as e:
        print(f"⚠️  Could not read existing CSV: {e}")

# 3. FETCH LIVE DATA
print("⏳ Fetching live positions from Dhan...")
try:
    response = dhan.get_holdings()
    if response['status'] != 'success':
        print(f"❌ API Error: {response}")
        exit()
        
    data = response['data']
    if not data:
        print("⚠️ Portfolio is Empty on Broker.")
        # Proceeding is optional, but usually we want to clear the file or warn
    
    # 4. PROCESS & MERGE
    merged_list = []
    
    seen_tickers = set()

    # Slot Counter
    slot_num = 1
    
    for stock in data:
        raw_sym = stock.get('tradingSymbol', 'Unknown')
        # Ensure NSE: prefix format
        ticker = f"NSE:{raw_sym}"
        avg_price = stock.get('avgCostPrice', 0.0)
        qty = stock.get('totalQty', 0)
        
        # Merge Logic
        sl = 0.0
        sector = DEFAULT_SECTOR
        
        if ticker in existing_data:
            # Preserve manual values
            sl = existing_data[ticker]['SL']
            sector = existing_data[ticker]['Sector']
            # If Sector was empty in CSV, set default
            if pd.isna(sector) or str(sector).strip() == "":
                sector = DEFAULT_SECTOR
        
        merged_list.append({
            'Slot': slot_num,
            'Ticker': ticker,
            'Entry': round(avg_price, 2),
            'Qty': int(qty),
            'SL': sl,
            'Sector': sector
        })
        
        seen_tickers.add(ticker)
        slot_num += 1

    # 5. SAVE ENHANCED CSV
    # Create DataFrame
    df_new = pd.DataFrame(merged_list)
    
    # Save
    df_new.to_csv(CSV_PATH, index=False)
    
    print("-" * 60)
    print("-" * 60)
    print(f"✅ UPDATED '{CSV_PATH}' with {len(merged_list)} positions (incl. Qty).")
    
    # 6. FETCH & SAVE FUND BALANCE
    print("💰 Fetching Fund Balance...")
    try:
        funds = dhan.get_fund_limits()
        if funds['status'] == 'success':
            f_data = funds['data']
            # Depending on structure, usually 'availCredits' or 'availableCash'
            avail_cash = f_data.get('availabelBalance', f_data.get('withdrawableBalance', f_data.get('availCredits', 0.0)))
            
            acc_info = {
                "AvailableCash": round(float(avail_cash), 2),
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            with open("account_info.json", "w") as f:
                json.dump(acc_info, f, indent=4)
                
            print(f"✅ Account Balance: {avail_cash}")
    except Exception as fe:
        print(f"⚠️ Could not fetch funds: {fe}")

    print("-" * 60)
    print("NEXT STEPS:")
    print("1. Open 'portfolio.csv' in Excel.")
    print("2. Manually enter STOP LOSS (SL) and SECTOR for any new stocks.")
    print("3. Run 'portfolio_sync.py' (or check the GUI) to push to TradingView.")

except Exception as e:
    print(f"❌ Error: {e}")

input("\nPress Enter to exit...")