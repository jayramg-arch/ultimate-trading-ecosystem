import sqlite3
import json

def get_schema():
    conn = sqlite3.connect('trade_journal_v6.db')
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'")
    schema = [row[0] for row in cursor.fetchall() if row[0]]
    print(schema)

if __name__ == '__main__':
    get_schema()
