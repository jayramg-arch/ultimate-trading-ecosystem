import sqlite3
import pandas as pd

def verify_db():
    conn = sqlite3.connect("trade_journal_v6.db")
    df = pd.read_sql("SELECT symbol, exit_date, exit_price, status FROM journal WHERE exit_date LIKE '2025-10-%'", conn)
    conn.close()
    
    print("--- October 2025 Trades in Database ---")
    if df.empty:
        print("No trades found for October 2025.")
    else:
        print(df)

if __name__ == "__main__":
    verify_db()
