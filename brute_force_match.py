import pandas as pd
import os

def brute_force_intersection():
    """
    SMART MATCH V3: Handles 'Symbol_x' renaming collisions.
    """
    file1 = 'MASTER_scan_results.csv'  # Screener File
    file2 = 'chartink_results.csv'     # Chartink File
    output_file = 'FINAL_WATCHLIST.csv'

    print(f"\n🚀 Starting Smart Matcher V3...")

    if not os.path.exists(file1) or not os.path.exists(file2):
        print("❌ Error: Missing input files.")
        return None

    try:
        df1 = pd.read_csv(file1, dtype=str) 
        df2 = pd.read_csv(file2, dtype=str)
    except Exception as e:
        print(f"❌ Error reading CSVs: {e}")
        return None

    # --- 1. IDENTIFY SYMBOL COLUMNS ---
    def find_symbol_col(df):
        candidates = ['Symbol', 'nsecode', 'NSE Code', 'Ticker', 'Stock']
        for col in candidates:
            match = next((c for c in df.columns if c.lower() == col.lower()), None)
            if match: return match
        return None

    col1 = find_symbol_col(df1)
    col2 = find_symbol_col(df2)

    if not col1 or not col2:
        print(f"❌ Error: Could not find 'Symbol' column.")
        return None

    # --- 2. NORMALIZE & MERGE ---
    # Create Match Keys
    df1['MATCH_KEY'] = df1[col1].astype(str).str.upper().str.strip()
    df2['MATCH_KEY'] = df2[col2].astype(str).str.upper().str.strip()

    # Perform Merge
    # We use suffixes to handle if both files have 'Symbol'
    merged_df = pd.merge(df1, df2, on='MATCH_KEY', how='inner', suffixes=('_Screener', '_Chartink'))

    # --- 3. FIX COLUMN RENAMING (The Fix) ---
    # If 'Symbol' existed in both, it is now 'Symbol_Screener'. We need to get it back.
    target_symbol_col = f"{col1}_Screener"
    
    if col1 not in merged_df.columns:
        if target_symbol_col in merged_df.columns:
            # Rename 'Symbol_Screener' back to 'Symbol'
            merged_df.rename(columns={target_symbol_col: col1}, inplace=True)
        else:
            # Fallback: Just use the Match Key as the Symbol
            merged_df[col1] = merged_df['MATCH_KEY']

    # --- 4. CLEANUP & SAVE ---
    if 'MATCH_KEY' in merged_df.columns:
        del merged_df['MATCH_KEY']
        
    if not merged_df.empty:
        # Reorder to put Symbol first
        cols = [col1] + [c for c in merged_df.columns if c != col1]
        merged_df = merged_df[cols]
        
        merged_df.to_csv(output_file, index=False)
        print("\n" + "="*40)
        print(f"🏆 SUCCESS! Found {len(merged_df)} common stocks.")
        print(f"   Common Symbols: {merged_df[col1].tolist()}")
        print(f"💾 Saved to: {output_file}")
        print("="*40)
        return output_file
    else:
        print("\n❌ FAILED. Zero common stocks found.")
        return None

if __name__ == "__main__":
    brute_force_intersection()