import os
import csv
import sys
import tkinter as tk
from tkinter import messagebox
import sqlite3

import datetime

# ==========================================
# CONFIGURATION
# BUG-L5: use the script's own directory — not CWD (which changes under Streamlit)
_WL_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WATCHLIST_DIR = os.path.join(_WL_SCRIPT_DIR, "Generated_Watchlists")

# Map Input CSVs to Output Base Names (Date will be appended)
WATCHLIST_MAP = {
    # -- 5 BULL WATCHLISTS --
    "FINAL_Hunter_Picks.csv":    "Bull_Hunter",
    "FINAL_Pullback_Picks.csv":  "Bull_Pullback",
    "FINAL_EarlyBird_Picks.csv": "Bull_EarlyBird",
    "FINAL_Leader_Picks.csv":    "Bull_StrongLeader",
    "FINAL_COMBINED_BULL_PICKS.csv": "Bull_Picks_All",
    
    # -- 4 RECOVERY WATCHLISTS --
    "FINAL_Recovery_RSLeaders.csv":      "Rec_RS_Survivor",
    "FINAL_Recovery_ClimaxBounce.csv":   "Rec_Climax_Bounce",
    "FINAL_Recovery_EarlyBirds.csv":     "Rec_Early_Bird",
    "FINAL_COMBINED_RECOVERY_PICKS.csv": "Recovery_Picks_All",
    # NOTE: Recovery_Screener_Results.csv is the RAW scan LOG (all ~76 scanned
    # candidates, most with Signal=0 / Signal_Label=None). It is deliberately
    # NOT exported to a TV watchlist — pushing non-firing candidates was noise.
    # The curated FIRING-only list is FINAL_RECOVERY_CATALYST_WATCHLIST.csv
    # below (Phase 4.75). The raw file stays on disk for the Web Commander
    # Recovery tab + diagnostics.

    # -- BULL SCREENER (catalyst-scored output of bull_screener.py) --
    # A10: previously the bull screener wrote results that never made it into
    # any watchlist export. Adding both the default and custom result files.
    "Bull_Screener_Results.csv":         "Bull_Screener",
    "Bull_Screener_Custom_Results.csv":  "Bull_Screener_Custom",
    # Catalyst-first broad scan (run_pipeline Phase 4.7) — separate watchlist,
    # does NOT overwrite FINAL_WATCHLIST.csv or Bull_Screener_Results.csv.
    "FINAL_CATALYST_WATCHLIST.csv":      "Catalyst_Watchlist",
    # Recovery catalyst companion (run_pipeline Phase 4.75) — firing REV/WYC
    # signals only, RFF-gated inside the recovery engine.
    "FINAL_RECOVERY_CATALYST_WATCHLIST.csv": "Recovery_Catalyst_Watchlist",

    # -- OTHER / SPECIAL --
    "FINAL_XRay_Picks.csv":   "XRay_Picks",
    "FINAL_WATCHLIST.csv":         "Golden_Matcher_Picks",
    # Consolidated Trigger-Board union (run_pipeline Phase 4.8): the deduped set of
    # all 5 board watchlists — synced as ONE list (Strike auto-splits it at 49).
    "FINAL_GOLDEN_MATCHER.csv":     "Golden_Matcher_Board",
    "Portfolio_Stocks.csv":        "Portfolio_Current",
    "portfolio.csv":               "portfolio"
}


def generate_tradingview_files(silent=False):
    """
    Reads the Final CSVs and generates unified Watchlist files
    formatted as NSE:SYMBOL (Works for TV, and often usable elsewhere).
    """
    print("=" * 60)
    print("[WL] GENERATING WATCHLISTS")
    print("=" * 60)

    # 1. Ensure Output Directory Exists
    if not os.path.exists(WATCHLIST_DIR):
        os.makedirs(WATCHLIST_DIR)
        print(f"Created directory: {WATCHLIST_DIR}")
    # Removed the deletion of old files to preserve historical watchlists for backtesting

    # Generate Date Suffix (e.g., -07FEB26)
    date_str = datetime.datetime.now().strftime("%d%b%y").upper()
    
    files_generated = 0
    
    for csv_file, base_name in WATCHLIST_MAP.items():
        csv_path = os.path.join(_WL_SCRIPT_DIR, csv_file)  # BUG-L5: absolute, not CWD
        
        # File Path: Hunter-07FEB26.txt
        txt_filename = f"{base_name}-{date_str}.txt"
        txt_path = os.path.join(WATCHLIST_DIR, txt_filename)

        if not os.path.exists(csv_path):
            print(f"[SKIP] Not Found: {csv_file}")
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
                    print(f"[ERROR] No Symbol column in {csv_file}")
                    continue

                # Prepare Symbols List
                symbols_list = []
                for row in rows:
                    symbol = row.get(symbol_col, "").strip()
                    if symbol:
                        clean_symbol = symbol.replace("NSE:", "").replace("BSE:", "").replace(".NS", "").replace(".BO", "")
                        symbols_list.append(f"NSE:{clean_symbol}")

                if not symbols_list:
                    print(f"[WARN] No symbols found for {base_name}. Skipping TXT generation.")
                    continue

                # 1. Write Dated Version
                with open(txt_path, 'w', encoding='utf-8') as outfile:
                    outfile.write(",\n".join(symbols_list)) # Comma and newline separated for TV Import

                # 2. Write Static Version (For Automation) — BUG-L5: cleaner name
                static_filename = f"LATEST_{base_name}.txt"
                static_path = os.path.join(WATCHLIST_DIR, static_filename)
                with open(static_path, 'w', encoding='utf-8') as outfile:
                    outfile.write(",\n".join(symbols_list))
            
            print(f"[OK] Generated: {txt_filename} & {static_filename} ({len(symbols_list)} symbols)")
            files_generated += 1

        except Exception as e:
            print(f"[ERROR] Processing {csv_file}: {e}")

    # Generate Portfolio Watchlist from Journal DB
    try:
        db_path = os.path.join(_WL_SCRIPT_DIR, "trade_journal_v6.db")  # BUG-L5: absolute
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT symbol FROM journal WHERE status='OPEN'")
            rows = cursor.fetchall()
            conn.close()
            
            portfolio_symbols = []
            for row in rows:
                if row[0]:
                    clean_sym = row[0].strip().upper().replace("NSE:", "").replace("BSE:", "")
                    portfolio_symbols.append(f"NSE:{clean_sym}")
            
            if portfolio_symbols:
                portfolio_symbols = list(set(portfolio_symbols)) # remove duplicates
                pf_txt_filename = f"Portfolio-{date_str}.txt"
                pf_txt_path = os.path.join(WATCHLIST_DIR, pf_txt_filename)
                with open(pf_txt_path, 'w', encoding='utf-8') as outfile:
                    outfile.write(",\n".join(portfolio_symbols))
                
                pf_static_path = os.path.join(WATCHLIST_DIR, "LATEST_Portfolio.txt")
                with open(pf_static_path, 'w', encoding='utf-8') as outfile:
                    outfile.write(",\n".join(portfolio_symbols))
                    
                print(f"[OK] Generated: {pf_txt_filename} & LATEST_Portfolio.txt ({len(portfolio_symbols)} symbols)")
                files_generated += 1
    except Exception as e:
        print(f"[ERROR] Processing Journal DB for Portfolio: {e}")

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
        print("[ERROR] No files were generated. Check if CSVs exist.")
        if not silent:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Error", "No Watchlists Generated.\nPlease run 'Auto-Pilot' first to create the source CSV lists.")
            root.destroy()

if __name__ == "__main__":
    generate_tradingview_files()
