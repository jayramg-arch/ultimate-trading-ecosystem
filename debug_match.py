import pandas as pd
import os

def debug_files():
    screener_file = 'MASTER_scan_results.csv'
    chartink_file = 'chartink_results.csv' # Make sure this matches your actual filename!

    print("🕵️ DIAGNOSTIC MODE INITIALIZED...\n")

    # 1. CHECK SCREENER FILE
    if os.path.exists(screener_file):
        df_s = pd.read_csv(screener_file)
        print(f"✅ Loaded Screener File: {len(df_s)} rows")
        print(f"   Columns found: {list(df_s.columns)}")
        # Print first 5 symbols
        if 'Symbol' in df_s.columns:
            print(f"   First 5 Symbols: {df_s['Symbol'].head().tolist()}")
        else:
            print("   ❌ ERROR: No 'Symbol' column found in Screener file!")
    else:
        print(f"❌ ERROR: Could not find {screener_file}")

    print("-" * 30)

    # 2. CHECK CHARTINK FILE
    if os.path.exists(chartink_file):
        df_c = pd.read_csv(chartink_file)
        print(f"✅ Loaded Chartink File: {len(df_c)} rows")
        print(f"   Columns found: {list(df_c.columns)}")
        
        # Try to guess the symbol column
        symbol_col = None
        for col in df_c.columns:
            if col.lower() in ['symbol', 'nse code', 'stock', 'ticker']:
                symbol_col = col
                break
        
        if symbol_col:
            print(f"   First 5 Symbols (from '{symbol_col}'): {df_c[symbol_col].head().tolist()}")
        else:
            print("   ❌ ERROR: Could not identify a Symbol column in Chartink file!")
    else:
        print(f"❌ ERROR: Could not find {chartink_file}")

if __name__ == "__main__":
    debug_files()