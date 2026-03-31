import pandas as pd
import os

def find_common_stocks(screener_file, chartink_file, output_file='high_conviction_targets.csv'):
    print(f"🔍 Reading Screener file: {screener_file}...")
    print(f"🔍 Reading Chartink file: {chartink_file}...")

    try:
        df_screener = pd.read_csv(screener_file)
        df_chartink = pd.read_csv(chartink_file)
    except FileNotFoundError as e:
        print(f"❌ Error: Could not find file. {e}")
        return

    # --- STANDARDIZE COLUMN NAMES ---
    # We need to find which column holds the Symbol/Name in each file.
    
    # 1. Identify Screener Column (looks for 'NSE Code' first, then 'Name')
    screener_col = None
    if 'NSE Code' in df_screener.columns:
        screener_col = 'NSE Code'
    elif 'Name' in df_screener.columns:
        screener_col = 'Name'
        print("⚠️ Warning: Using 'Name' for Screener. Matches might be lower if Chartink uses Symbols.")
    else:
        # Fallback: take the first column
        screener_col = df_screener.columns[0]
    
    # 2. Identify Chartink Column (looks for 'NSE Code', 'Symbol', or 'Stock')
    chartink_col = None
    possible_chartink_cols = ['NSE Code', 'Symbol', 'Stock', 'Ticker']
    for col in possible_chartink_cols:
        if col in df_chartink.columns:
            chartink_col = col
            break
    if not chartink_col:
        chartink_col = df_chartink.columns[0] # Fallback

    print(f"   -> Matching Screener column '{screener_col}' with Chartink column '{chartink_col}'")

    # --- NORMALIZE DATA ---
    # Convert to uppercase and remove spaces to ensure "Infy" matches "INFY "
    df_screener['MATCH_KEY'] = df_screener[screener_col].astype(str).str.upper().str.strip()
    df_chartink['MATCH_KEY'] = df_chartink[chartink_col].astype(str).str.upper().str.strip()

    # --- PERFORM INTERSECTION ---
    # Inner Join: Keeps only rows where MATCH_KEY exists in BOTH
    common_df = pd.merge(df_screener, df_chartink, on='MATCH_KEY', how='inner', suffixes=('_Screener', '_Chartink'))

    # Clean up the helper column
    del common_df['MATCH_KEY']

    # --- SAVE ---
    if not common_df.empty:
        common_df.to_csv(output_file, index=False)
        print("\n" + "="*40)
        print(f"✅ FOUND {len(common_df)} COMMON STOCKS!")
        print(f"🎯 These are your Techno-Fundamental winners.")
        print(f"💾 Saved to: {output_file}")
        print("="*40)
        
        # Preview
        print(common_df.head())
    else:
        print("\n❌ No common stocks found.")
        print("   Hint: Ensure both files have a column with the NSE Symbol (e.g. 'INFY').")

if __name__ == "__main__":
    # REPLACE these filenames with your actual file names
    screener_csv = 'MASTER_scan_results.csv'  # Result from Script 1
    chartink_csv = 'chartink_results.csv'     # Result from Script 2
    
    find_common_stocks(screener_csv, chartink_csv)
    