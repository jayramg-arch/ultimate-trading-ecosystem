import os
import sqlite3
import pandas as pd
from ai_reconcile_engine import discover_missing_trades, backfill_trades, fetch_trade_history, process_trade_history, normalize_symbol, get_symbol_sector

DB_FILE = "trade_journal_v6.db"

def backfill_oct_dec_api():
    print("--- Discovery & Backfill from API History ---")
    
    # 1. Fetch Full History
    api_history = fetch_trade_history()
    if api_history.empty:
        print("API history empty.")
        return
        
    # 2. Process FIFO to get completed trades
    master_completed = process_trade_history(api_history)
    if master_completed.empty:
        print("No completed trades found in API history.")
        return
        
    # 3. Identify Missing Trades
    conn = sqlite3.connect(DB_FILE)
    j_df = pd.read_sql("SELECT symbol FROM journal", conn)
    journal_syms = set(j_df['symbol'].apply(normalize_symbol).unique())
    conn.close()
    
    missing = []
    print("\n--- Completed Trades Found in API ---")
    for _, row in master_completed.iterrows():
        norm = normalize_symbol(row['Symbol'])
        dt = row['Exit Date']
        # Filter for Oct / Dec 2025
        is_target_month = str(dt).startswith('2025-10') or str(dt).startswith('2025-12')
        
        if is_target_month:
            if norm not in journal_syms:
                missing.append({
                    'Symbol': norm,
                    'Name': row['Symbol'],
                    'ExitPrice': float(row['Exit Price']),
                    'Pnl': float(row['Realized P&L']),
                    'ExitDate': str(row['Exit Date']),
                    'EntryPrice': float(row['Entry Price']),
                    'Qty': float(row['Qty']),
                    'EntryDate': str(row['Entry Date'])
                })
                print(f"MISSING: {row['Symbol']} exited on {dt}")
            else:
                print(f"EXISTS: {row['Symbol']} exited on {dt}")
                
    # 4. Backfill
    if missing:
        print(f"\nBackfilling {len(missing)} trades...")
        count = backfill_trades(missing)
        print(f"Successfully backfilled {count} trades.")
    else:
        print("\nNo missing trades found for the target period.")

if __name__ == "__main__":
    backfill_oct_dec_api()
