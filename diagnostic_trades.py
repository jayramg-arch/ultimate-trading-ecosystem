import pandas as pd
import sqlite3
import os
from ai_reconcile_engine import parse_html_trades, normalize_symbol

DB_FILE = "trade_journal_v6.db"

def run_diagnostic():
    print("--- 1. Parsing MHTML Trade Logs ---")
    log_df = parse_html_trades()
    if log_df.empty:
        print("No trades found in logs.")
        return

    # Filter for Oct and Dec 2025
    oct_trades = log_df[log_df['exchangeTime'].dt.strftime('%Y-%m') == '2025-10']
    dec_trades = log_df[log_df['exchangeTime'].dt.strftime('%Y-%m') == '2025-12']

    print(f"Found {len(oct_trades)} trades in Oct 2025.")
    print(f"Found {len(dec_trades)} trades in Dec 2025.")

    print("\n--- Oct 2025 Trades in Logs ---")
    print(oct_trades[['exchangeTime', 'Symbol', 'transactionType', 'tradedQuantity', 'tradedPrice']])

    print("\n--- Dec 2025 Trades in Logs ---")
    print(dec_trades[['exchangeTime', 'Symbol', 'transactionType', 'tradedQuantity', 'tradedPrice']])

    print("\n--- 2. Checking Database for these trades ---")
    if not os.path.exists(DB_FILE):
        print(f"Database {DB_FILE} not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    db_df = pd.read_sql("SELECT symbol, exit_date, exit_price, status FROM journal", conn)
    conn.close()

    db_df['NormSym'] = db_df['symbol'].apply(normalize_symbol)
    
    # Check Oct/Dec matches
    print("\n--- Cross-Check Results ---")
    for _, log_row in pd.concat([oct_trades, dec_trades]).iterrows():
        if log_row['transactionType'] == 'SELL':
            norm_sym = normalize_symbol(log_row['Symbol'])
            match = db_df[db_df['NormSym'] == norm_sym]
            
            status_text = "MISSING"
            if not match.empty:
                db_exit_date = str(match.iloc[0]['exit_date'])
                if db_exit_date == str(log_row['exchangeTime'].date()):
                    status_text = "FOUND (MATCHED)"
                else:
                    status_text = f"FOUND (MISMATCH DATE: {db_exit_date})"
            
            print(f"[{log_row['exchangeTime'].strftime('%Y-%m-%d')}] {log_row['Symbol']} - {status_text}")

if __name__ == "__main__":
    run_diagnostic()
