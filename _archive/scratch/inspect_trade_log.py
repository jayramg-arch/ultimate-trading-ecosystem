import pandas as pd
import os

file_path = "List of trades-2025-26.html"

print(f"Checking file: {file_path}")
if not os.path.exists(file_path):
    print("File not found!")
    exit()

try:
    # Read HTML tables
    dfs = pd.read_html(file_path)
    print(f"Read successfully as HTML. Found {len(dfs)} tables.")
    
    for i, df in enumerate(dfs):
        print(f"\n--- Table {i} ---")
        print("Columns:", df.columns.tolist())
        print("Order Type unique:", df['Order Type'].unique())
        # Check if Quantity or Trade Value implies direction (negatives?)
        print("Quantity range:", df['Quantity'].min(), df['Quantity'].max())
        print("Trade Value range:", df['Trade Value'].min(), df['Trade Value'].max())
        print(df.head(10))
        
except Exception as e:
    print(f"Failed to read HTML: {e}")
