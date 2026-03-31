
import pandas as pd
import io
import os
import time

CSV_PATH = "portfolio.csv"
IMPORT_FILE = "tv_import.txt"

def import_tv_log():
    print("\n" + "="*60)
    print("📥 IMPORT TRADINGVIEW LOGS TO PORTFOLIO (FILE BASED)")
    print("="*60)
    
    # 1. Check if import file exists
    if not os.path.exists(IMPORT_FILE):
        print(f"⚠️  '{IMPORT_FILE}' not found. Creating it now...")
        with open(IMPORT_FILE, "w", encoding="utf-8") as f:
            f.write("PASTE_YOUR_TRADINGVIEW_CSV_DATA_HERE\n")
            f.write("(Replace this text with the data from Pine Logs)")
        
        print(f"✅ Created '{IMPORT_FILE}'.")
        print(f"👉 ACTION: Open '{IMPORT_FILE}', paste the CSV data from TradingView, save it, and run this script again.")
        return

    # 2. Read the file
    print(f"📖 Reading data from '{IMPORT_FILE}'...")
    with open(IMPORT_FILE, "r", encoding="utf-8") as f:
        raw_data = f.read()

    if "PASTE_YOUR" in raw_data or not raw_data.strip():
        print("❌ Error: File is empty or contains placeholder text.")
        print(f"👉 Please paste the TradingView log data into '{IMPORT_FILE}' and save.")
        return

    # 3. Process Data
    try:
        # Pre-process: Replace literal "\n" with actual newlines if present
        # Pine logs often come as a single string with \n chars
        if "\\n" in raw_data:
            print("ℹ️  Detected literal '\\n' characters. Formatting...")
            raw_data = raw_data.replace("\\n", "\n")

        # Parse CSV
        new_df = pd.read_csv(io.StringIO(raw_data))
        new_df.columns = new_df.columns.str.strip() # Clean headers

        if 'Ticker' not in new_df.columns or 'SL' not in new_df.columns:
            print(f"❌ Invalid Data Format in '{IMPORT_FILE}'. Missing 'Ticker' or 'SL' columns.")
            print("   (Ensure you copied the entire block from Pine Logs)")
            return

        print(f"✅ Found {len(new_df)} records in import file.")

        # Load Existing Portfolio
        if not os.path.exists(CSV_PATH):
            print(f"⚠️ {CSV_PATH} not found. Creating new...")
            current_df = pd.DataFrame(columns=['Slot', 'Ticker', 'Entry', 'Qty', 'SL', 'Sector'])
        else:
            current_df = pd.read_csv(CSV_PATH)
            
        print(f"ℹ️  Current Portfolio has {len(current_df)} records.")

        updated_count = 0
        added_count = 0
        
        # Helper to normalize
        # Matches: "NSE:RELIANCE" -> "RELIANCE", "RELIANCE" -> "RELIANCE"
        def norm(t):
            return str(t).strip().upper().replace("NSE:", "").replace("BSE:", "")

        for idx, row in new_df.iterrows():
            tv_ticker = row['Ticker']
            tv_sl = float(row.get('SL', 0.0))
            tv_entry = float(row.get('Entry', 0.0))
            tv_sec = row.get('Sector', '')
            
            clean_tv = norm(tv_ticker)
            
            # Find match in current_df
            match_index = -1
            for c_idx, c_row in current_df.iterrows():
                if norm(c_row['Ticker']) == clean_tv:
                    match_index = c_idx
                    break
            
            if match_index != -1:
                # Update Existing
                old_sl = float(current_df.at[match_index, 'SL'])
                
                # Update SL if changed (and not 0 unless intended?)
                if abs(old_sl - tv_sl) > 0.05: # Tolerance for float diff
                    current_df.at[match_index, 'SL'] = tv_sl
                    updated_count += 1
                    print(f"   🔄 Updated {tv_ticker}: SL {old_sl} -> {tv_sl}")
                    
                # Setup Sector if missing in master
                old_sec = str(current_df.at[match_index, 'Sector'])
                if (old_sec == 'nan' or not old_sec) and tv_sec:
                     current_df.at[match_index, 'Sector'] = tv_sec
                     updated_count += 1
            else:
                # Add New
                print(f"   ➕ Adding new: {tv_ticker}")
                new_row = {
                    'Slot': len(current_df) + 1,
                    'Ticker': tv_ticker, 
                    'Entry': tv_entry,
                    'Qty': 0, # Default
                    'SL': tv_sl,
                    'Sector': tv_sec if tv_sec else 'NSE:CNX500'
                }
                current_df = pd.concat([current_df, pd.DataFrame([new_row])], ignore_index=True)
                added_count += 1

        if updated_count > 0 or added_count > 0:
            current_df.to_csv(CSV_PATH, index=False)
            print("-" * 60)
            print(f"✅ SUCCESS: Updated {updated_count} rows, Added {added_count} new rows.")
            print(f"💾 Saved to '{CSV_PATH}'")
        else:
            print("-" * 60)
            print("✨ No changes needed. Portfolio is already in sync.")

    except Exception as e:
        print(f"\n❌ Error processing file: {e}")

if __name__ == "__main__":
    import_tv_log()
    input("\nPress Enter to exit...")
