import os
import sqlite3
import pandas as pd
from dhanhq import dhanhq
from dotenv import load_dotenv
from dhan_auth import ensure_valid_token
from ai_reconcile_engine import normalize_symbol, process_trade_history, backfill_trades

load_dotenv(override=True)
DB_FILE = "trade_journal_v6.db"

def fetch_trades_range(from_date, to_date):
    tok = ensure_valid_token()
    cid = os.getenv("DHAN_CLIENT_ID")
    if not tok or not cid: return pd.DataFrame()
    
    try:
        dhan = dhanhq(client_id=cid, access_token=tok)
        all_trades = []
        for page in range(0, 10):
            resp = dhan.get_trade_history(from_date=from_date, to_date=to_date, page_number=page)
            if resp['status'] == 'success' and resp['data']:
                all_trades.extend(resp['data'])
            else:
                break
        if not all_trades: return pd.DataFrame()
        df = pd.DataFrame(all_trades)
        df['Symbol'] = df['tradingSymbol'].fillna(df.get('customSymbol', '')).fillna(df.get('symbol', ''))
        df['exchangeTime'] = pd.to_datetime(df['exchangeTime'])
        return df.sort_values('exchangeTime')
    except:
        return pd.DataFrame()

def run_targeted_backfill():
    print("--- Targeted Discovery: Oct & Dec 2025 ---")
    
    # We need a bit wider range to catch the 'BUY' side for FIFO
    # History starts from 2023 or whenever the oldest trade could be
    # But for a quick backfill of those specific sells, we need the sells + their original buys
    
    # 1. Fetch Sells in target months
    print("Fetching SELL trades for target months...")
    trades_oct = fetch_trades_range('2025-10-01', '2025-10-31')
    trades_dec = fetch_trades_range('2025-12-01', '2025-12-31')
    
    sell_trades = pd.concat([trades_oct, trades_dec])
    if sell_trades.empty:
        print("No trades found in target months.")
        return
        
    sells_only = sell_trades[sell_trades['transactionType'] == 'SELL']
    if sells_only.empty:
        print("No SELL trades found in target months.")
        return
        
    print(f"Found {len(sells_only)} SELL transactions.")
    
    # 2. For each sold symbol, we need to find the original BUY date/price
    # We'll fetch a wider history for those specific symbols
    missing = []
    conn = sqlite3.connect(DB_FILE)
    j_df = pd.read_sql("SELECT symbol FROM journal", conn)
    journal_syms = set(j_df['symbol'].apply(normalize_symbol).unique())
    conn.close()
    
    for _, sell in sells_only.iterrows():
        sym = sell['Symbol']
        norm = normalize_symbol(sym)
        
        if norm in journal_syms:
            print(f"SKIP: {sym} (Found in DB)")
            continue
            
        print(f"RECONCILING: {sym} (Sold on {sell['exchangeTime'].date()})")
        # Search for BUY in the last 2 years
        hist = fetch_trades_range('2023-01-01', str(sell['exchangeTime'].date()))
        if hist.empty: continue
        
        # FIFO match for this symbol
        comp = process_trade_history(hist)
        if not comp.empty:
            # Look for the last completion of this symbol
            match = comp[comp['Symbol'].apply(normalize_symbol) == norm]
            if not match.empty:
                last_m = match.iloc[-1]
                missing.append({
                    'Symbol': norm,
                    'Name': sym,
                    'ExitPrice': float(last_m['Exit Price']),
                    'Pnl': float(last_m['Realized P&L']),
                    'ExitDate': str(last_m['Exit Date']),
                    'EntryPrice': float(last_m['Entry Price']),
                    'Qty': float(last_m['Qty']),
                    'EntryDate': str(last_m['Entry Date'])
                })
                print(f"PREPPED: {sym} (Profit: {last_m['Realized P&L']})")

    # 3. Backfill
    if missing:
        print(f"\nBackfilling {len(missing)} trades...")
        count = backfill_trades(missing)
        print(f"Successfully backfilled {count} trades.")
    else:
        print("\nNo new missing trades identified to backfill.")

if __name__ == "__main__":
    run_targeted_backfill()
