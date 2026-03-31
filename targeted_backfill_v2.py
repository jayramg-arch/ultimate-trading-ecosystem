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
    if not tok or not cid: 
        print("Auth failed.")
        return pd.DataFrame()
    
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
        # Robust Symbol Resolution
        if 'tradingSymbol' in df.columns:
            df['Symbol'] = df['tradingSymbol']
        elif 'customSymbol' in df.columns:
            df['Symbol'] = df['customSymbol']
        elif 'symbol' in df.columns:
            df['Symbol'] = df['symbol']
        else:
            df['Symbol'] = df.iloc[:, 0] # Fallback to first col
            
        df['exchangeTime'] = pd.to_datetime(df['exchangeTime'])
        return df.sort_values('exchangeTime')
    except Exception as e:
        print(f"Error in fetch: {e}")
        return pd.DataFrame()

def run_targeted_backfill():
    print("--- Targeted Discovery: Oct & Dec 2025 ---")
    
    # 1. Fetch Sells in target months
    print("Fetching SELL trades for Oct 2025...")
    trades_oct = fetch_trades_range('2025-10-01', '2025-10-31')
    print(f"Oct trades count: {len(trades_oct)}")
    
    print("Fetching SELL trades for Dec 2025...")
    trades_dec = fetch_trades_range('2025-12-01', '2025-12-31')
    print(f"Dec trades count: {len(trades_dec)}")
    
    sell_trades = pd.concat([trades_oct, trades_dec])
    if sell_trades.empty:
        print("No trades found in target months.")
        return
        
    sells_only = sell_trades[sell_trades['transactionType'] == 'SELL'].copy()
    if sells_only.empty:
        print("No SELL trades found in target months.")
        return
        
    print(f"Found {len(sells_only)} SELL transactions.")
    
    # 2. Check Journal
    conn = sqlite3.connect(DB_FILE)
    j_df = pd.read_sql("SELECT symbol FROM journal", conn)
    journal_syms = set(j_df['symbol'].apply(normalize_symbol).unique())
    conn.close()
    
    # 3. Process Symbols
    missing = []
    # We need full history for these symbols to find the entry price
    print("\nFetching full history to reconcile entry data...")
    full_hist = fetch_trades_range('2023-01-01', '2026-02-17')
    if full_hist.empty:
        print("Could not fetch full history for reconciliation.")
        return
        
    # Process the whole thing using FIFO matching from your engine
    completed_api = process_trade_history(full_hist)
    
    for _, log_trade in sells_only.iterrows():
        sym = log_trade['Symbol']
        norm = normalize_symbol(sym)
        exit_dt = log_trade['exchangeTime'].date()
        
        if norm in journal_syms:
            print(f"ALREADY IN DB: {sym} (Norm: {norm})")
            continue
            
        # Find the match in the completed trades list
        match = completed_api[
            (completed_api['Symbol'].apply(normalize_symbol) == norm) & 
            (completed_api['Exit Date'] == exit_dt)
        ]
        
        if not match.empty:
            m = match.iloc[-1]
            missing.append({
                'Symbol': norm,
                'Name': sym,
                'ExitPrice': float(m['Exit Price']),
                'Pnl': float(m['Realized P&L']),
                'ExitDate': str(m['Exit Date']),
                'EntryPrice': float(m['Entry Price']),
                'Qty': float(m['Qty']),
                'EntryDate': str(m['Entry Date'])
            })
            print(f"FOUND MISSING: {sym} (Norm: {norm}) Exited {exit_dt} | Pnl: {m['Realized P&L']}")
        else:
            print(f"WARNING: Could not match {sym} on {exit_dt} in history (Possible Buy was very old?)")

    # 4. Backfill
    if missing:
        print(f"\nBackfilling {len(missing)} trades into {DB_FILE}...")
        count = backfill_trades(missing)
        print(f"Successfully backfilled {count} trades.")
    else:
        print("\nNo new missing trades identified for backfill.")

if __name__ == "__main__":
    run_targeted_backfill()
