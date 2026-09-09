import sqlite3
import json
import os
from datetime import datetime

DB_FILE = "trade_journal_v6.db"

def migrate():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS MarketRegime (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE,
            score INTEGER,
            verdict TEXT,
            details TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS SectorMappings (
            symbol TEXT PRIMARY KEY,
            sector TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS AICache (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 1. Migrate Sector Mappings
    if os.path.exists("sector_db.json"):
        with open("sector_db.json", "r") as f:
            sectors = json.load(f)
            if isinstance(sectors, dict):
                for sym, sec in sectors.items():
                    c.execute('INSERT OR REPLACE INTO SectorMappings (symbol, sector) VALUES (?, ?)', (sym, str(sec)))
        print(f"Migrated {len(sectors)} sectors.")

    # 2. Migrate AI Cache
    if os.path.exists("ai_cache.json"):
        with open("ai_cache.json", "r") as f:
            cache = json.load(f)
            if isinstance(cache, dict):
                for k, v in cache.items():
                    c.execute('INSERT OR REPLACE INTO AICache (key, value) VALUES (?, ?)', (k, json.dumps(v)))
        print(f"Migrated {len(cache)} AI cache entries.")

    # 3. Migrate Regime State
    if os.path.exists("regime_state.json"):
        with open("regime_state.json", "r") as f:
            regime = json.load(f)
            # regime_state.json usually has "last" and "history" (list of dicts with date, score, verdict)
            history = regime.get("history", [])
            for entry in history:
                date = entry.get("date")
                score = entry.get("score")
                verdict = entry.get("verdict")
                details = json.dumps(entry)
                if date:
                    c.execute('INSERT OR REPLACE INTO MarketRegime (date, score, verdict, details) VALUES (?, ?, ?, ?)', 
                              (date, score, verdict, details))
            
            # Insert or update 'current' state logic could be mapped to today's date if needed,
            # but the history contains the latest usually.
        print("Migrated regime state.")

    conn.commit()
    conn.close()
    print("Migration to SQLite complete.")

if __name__ == "__main__":
    migrate()
