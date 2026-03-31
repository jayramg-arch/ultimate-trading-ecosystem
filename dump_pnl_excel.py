import pandas as pd
import os

def dump_pnl_excel():
    path = "pnl-report.xls"
    if not os.path.exists(path):
        print(f"File {path} not found.")
        return
        
    print(f"--- Dumping {path} with read_excel ---")
    try:
        # P&L files from brokers like Dhan might need xlrd for .xls
        df = pd.read_excel(path)
        
        print(f"Shape: {df.shape}")
        
        # Print top 50 rows
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        
        print("\n--- Rows 0-50 ---")
        for i in range(min(50, len(df))):
            row_data = df.iloc[i].tolist()
            # Clean up row for display
            row_clean = [str(x)[:30] for x in row_data if str(x).lower() != 'nan']
            print(f"ROW {i}: {' | '.join(row_clean)}")
            
        # Search for October 2025 specifically
        print("\n--- Deep Search for October 2025 ---")
        for i in range(len(df)):
            row_str = " ".join(str(val) for val in df.iloc[i].values).lower()
            if "2025" in row_str and ("oct" in row_str or "10/" in row_str or "/10/" in row_str):
                row_data = df.iloc[i].tolist()
                row_clean = [str(x) for x in row_data if str(x).lower() != 'nan']
                print(f"MATCH FOUND AT ROW {i}: {' | '.join(row_clean)}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    dump_pnl_excel()
