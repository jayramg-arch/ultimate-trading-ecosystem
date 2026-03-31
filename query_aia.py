import sqlite3
import pandas as pd

conn = sqlite3.connect("trade_journal_v6.db")
df = pd.read_sql("SELECT * FROM journal WHERE symbol = 'AIAENG'", conn)
conn.close()
print(df.to_dict('records'))
