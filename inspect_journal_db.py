import sqlite3
import pandas as pd

DB_FILE = "trade_journal_v6.db"

def inspect_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        # Get everything to see symbols
        df = pd.read_sql("SELECT symbol, stoploss, target, status FROM journal", conn)
        conn.close()
        print("--- Database Content (All) ---")
        print(df)
        
        print("\n--- Specific Check ---")
        matches = df[df['symbol'].str.contains('METAL|NIFTY', na=False, case=False)]
        print(matches)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_db()
