import pandas as pd
from ai_reconcile_engine import parse_html_trades

print("Looking for MHTML files and parsing codes...")
df = parse_html_trades()

if df.empty:
    print("No trades found in MHTML/HTML files.")
else:
    print(f"Found {len(df)} trades in files.")
    print(df.head(20))
    print("\nSummary of transactions:")
    print(df['transactionType'].value_counts())
    print("\nUnique Symbols:")
    print(df['Symbol'].unique())
