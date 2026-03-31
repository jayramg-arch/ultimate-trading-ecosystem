import os
import csv
import sys
import tkinter as tk
from tkinter import messagebox

import datetime

# ==========================================
# CONFIGURATION
# Folder to save generated watchlists
WATCHLIST_DIR = os.path.join(os.getcwd(), "Generated_Watchlists")

# Map Input CSVs to Output Base Names (Date will be appended)
WATCHLIST_MAP = {
    "FINAL_Hunter_Picks.csv": "Hunter",
    "FINAL_Pullback_Picks.csv": "Pullback",
    "FINAL_EarlyBird_Picks.csv": "EarlyBird",
    "FINAL_Leader_Picks.csv": "Leader"
}

def generate_tradingview_files(silent=False):
    """
    Reads the 4 Final CSVs and generates unified Watchlist files
    formatted as NSE:SYMBOL (Works for TV, and often usable elsewhere).
    """
    print("="*60)
    print("📺 GENERATING WATCHLISTS")
    print("="*60)

    # 1. Ensure Output Directory Exists
    if not os.path.exists(WATCHLIST_DIR):
        os.makedirs(WATCHLIST_DIR)
        print(f"Created directory: {WATCHLIST_DIR}")

    # Generate Date Suffix (e.g., -07FEB26)
    date_str = datetime.datetime.now().strftime("%d%b%y").upper()
    
    files_generated = 0
    
    for csv_file, base_name in WATCHLIST_MAP.items():
        csv_path = os.path.join(os.getcwd(), csv_file)
        
        # File Path: Hunter-07FEB26.txt
        txt_filename = f"{base_name}-{date_str}.txt"
        txt_path = os.path.join(WATCHLIST_DIR, txt_filename)

        if not os.path.exists(csv_path):
            print(f"⚠️ Skipped (Not Found): {csv_file}")
            continue

        try:
            with open(csv_path, 'r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                
                # Read all rows first
                rows = list(reader)
                
                # Check for Symbol column
                symbol_col = None
                if reader.fieldnames:
                    # Priority 1: Exact matches
                    for col in reader.fieldnames:
                        if col.lower() in ['symbol', 'nsecode', 'ticker']:
                            symbol_col = col
                            break
                    
                    # Priority 2: Matches with suffixes (e.g., Symbol_x, NSECode_y)
                    if not symbol_col:
                        for col in reader.fieldnames:
                            col_clean = col.lower().split('_')[0] if '_' in col else col.lower()
                            if col_clean in ['symbol', 'nsecode', 'ticker']:
                                symbol_col = col
                                break

                
                if not symbol_col:
                    print(f"❌ Error: No Symbol column in {csv_file}")
                    continue

                # Prepare Symbols List
                symbols_list = []
                for row in rows:
                    symbol = row.get(symbol_col, "").strip()
                    if symbol:
                        clean_symbol = symbol.replace("NSE:", "").replace("BSE:", "")
                        symbols_list.append(f"NSE:{clean_symbol}")

                # 1. Write Dated Version
                with open(txt_path, 'w', encoding='utf-8') as outfile:
                    outfile.write(",".join(symbols_list)) # Comma separated for TV Import

                # 2. Write Static Version (For Automation)
                static_filename = f"FINAL_{base_name}_Picks.txt"
                static_path = os.path.join(WATCHLIST_DIR, static_filename)
                with open(static_path, 'w', encoding='utf-8') as outfile:
                    outfile.write(",".join(symbols_list))
            
            print(f"✅ Generated: {txt_filename} & {static_filename} ({len(symbols_list)} symbols)")
            files_generated += 1

        except Exception as e:
            print(f"❌ Error processing {csv_file}: {e}")

    print("-" * 60)
    
    if files_generated > 0:
        msg = f"Successfully generated {files_generated} Watchlist files!\n\nLocation:\n{WATCHLIST_DIR}\n\nTo Import in TradingView:\n1. Open Watchlist Panel\n2. Click '...' -> Import List\n3. Select these .txt files."
        print(msg)
        if not silent:
            # Show Popup
            root = tk.Tk()
            root.withdraw() # Hide main window
            root.attributes("-topmost", True) # Make sure it's on top
            messagebox.showinfo("Watchlists Generated", msg)
            root.destroy()
    else:
        print("❌ No files were generated. Check if CSVs exist.")
        if not silent:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Error", "No Watchlists Generated.\nPlease run 'Auto-Pilot' first to create the source CSV lists.")
            root.destroy()

if __name__ == "__main__":
    generate_tradingview_files()
