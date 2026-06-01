import sqlite3
import pandas as pd
from ai_reconcile_engine import normalize_symbol

DB_FILE = "trade_journal_v6.db"

oct_syms = [
    'Aditya Birla Nifty 200 Momentum 30 ETF',
    'ICICI Pru Nifty Fin Svc Ex-Bank ETF',
    'Lupin',
    'IREDA',
    'ICICI Pru Nifty FMCG ETF',
    'ICICI Pru Nifty 200 Quality 30 ETF',
    'Mirae Ast Nifty Smallcap 250 MQ 100 ETF'
]

def check_db_for_oct():
    conn = sqlite3.connect(DB_FILE)
    j_df = pd.read_sql("SELECT symbol, exit_date, exit_price, status, entry_date FROM journal", conn)
    conn.close()
    
    j_df['NormSym'] = j_df['symbol'].apply(normalize_symbol)
    
    print("--- Database Cross-Check for Oct 2025 Symbols ---")
    for sym in oct_syms:
        norm = normalize_symbol(sym)
        match = j_df[j_df['NormSym'] == norm]
        
        if match.empty:
            print(f"SYMBOL: {sym} (Norm: {norm}) -> NOT IN DATABASE")
        else:
            for _, row in match.iterrows():
                print(f"SYMBOL: {sym} -> FOUND in DB as '{row['symbol']}' | Status: {row['status']} | ExitDate: {row['exit_date']} | EntryDate: {row['entry_date']}")

if __name__ == "__main__":
    check_db_for_oct()
