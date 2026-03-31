import pandas as pd
import os

def dump_pnl_report():
    path = "pnl-report.xls"
    if not os.path.exists(path):
        print(f"File {path} not found.")
        return
        
    print(f"--- Dumping {path} ---")
    try:
        # P&L reports from Dhan are HTML-based XLS
        dfs = pd.read_html(path)
        df = dfs[0]
        
        print(f"Shape: {df.shape}")
        # Print top 100 rows
        pd.set_option('display.max_columns', None)
        pd.set_option('display.max_rows', 100)
        pd.set_option('display.width', 1000)
        
        # Look for headers. Sometimes the first few rows are metadata.
        print("\nFirst 100 rows:")
        print(df.head(100))
        
        # Filter for rows that contain "2025"
        print("\n--- Searching for October/2025 in P&L Report ---")
        for idx, row in df.iterrows():
            row_str = " ".join(str(val) for val in row.values)
            if "2025" in row_str and ("Oct" in row_str or "10/" in row_str or "/10/" in row_str):
                print(f"ROW {idx}: {row_str}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    dump_pnl_report()
