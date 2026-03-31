import pandas as pd
import os

def inspect(file_path):
    print(f"\n--- {file_path} ---")
    try:
        dfs = pd.read_html(file_path)
        print(f"Found {len(dfs)} tables")
        for i, df in enumerate(dfs):
            print(f"Table {i} Columns: {df.columns.tolist()}")
            print(df.head(5))
    except Exception as e:
        print(f"Error: {e}")

inspect("Exchange Transactions.html")
inspect("List of trades-2025-26.html")
