import pandas as pd
import os
import io
import json
from datetime import datetime
from dotenv import load_dotenv
from dhanhq import dhanhq
import sector_manager

# --- CONFIGURATION ---
CSV_PATH = "portfolio.csv"
IMPORT_FILE = "tv_import.txt"
PINE_PATH = "Weinstein & Swing Pro Dashboard v54.0.pine"
DEFAULT_SECTOR = "NSE:CNX500"

def normalize_ticker(t):
    """Standardizes ticker format: Removes NSE/BSE prefix, uppercase, stripped."""
    if not t: return ""
    return str(t).strip().upper().replace("NSE:", "").replace("BSE:", "")

def main():
    print("\n" + "="*60)
    print("🔄 MASTER PORTFOLIO SYNC (One-Click Update)")
    print("="*60)

    # ---------------------------------------------------------
    # STEP 1: LOAD TRADINGVIEW IMPORT DATA (IF AVAILABLE)
    # ---------------------------------------------------------
    tv_data = {} # {ticker: {'SL': float, 'Sector': str}}
    
    if os.path.exists(IMPORT_FILE):
        print(f"📂 Checking '{IMPORT_FILE}' for SL updates...")
        try:
            with open(IMPORT_FILE, "r", encoding="utf-8") as f:
                raw_data = f.read()

            if "PASTE_YOUR" not in raw_data and raw_data.strip():
                if "\\n" in raw_data: raw_data = raw_data.replace("\\n", "\n")
                
                tv_df = pd.read_csv(io.StringIO(raw_data))
                tv_df.columns = tv_df.columns.str.strip()
                
                if 'Ticker' in tv_df.columns:
                    for _, row in tv_df.iterrows():
                        t = normalize_ticker(row['Ticker'])
                        sl = float(row.get('SL', 0.0))
                        sec = row.get('Sector', '')
                        tv_data[t] = {'SL': sl, 'Sector': sec}
                    print(f"   ✅ Loaded {len(tv_data)} SL records from TradingView export.")
                else:
                    print("   ⚠️  'Ticker' column missing in import file. Skipping.")
            else:
                print("   ℹ️  Import file is empty or placeholder. Skipping SL import.")
        except Exception as e:
            print(f"   ❌ Error reading import file: {e}")
    else:
        print(f"   ⚠️  '{IMPORT_FILE}' not found. Skipping SL import.")

    # ---------------------------------------------------------
    # STEP 2: LOAD EXISTING MANUAL DATA (PRESERVE OLD SLs)
    # ---------------------------------------------------------
    existing_manual_data = {}
    if os.path.exists(CSV_PATH):
        try:
            old_df = pd.read_csv(CSV_PATH)
            for _, row in old_df.iterrows():
                t = normalize_ticker(row.get('Ticker', ''))
                if t:
                    existing_manual_data[t] = {
                        'SL': row.get('SL', 0.0),
                        'Sector': row.get('Sector', DEFAULT_SECTOR)
                    }
        except: pass

    # ---------------------------------------------------------
    # STEP 3: FETCH LIVE DHAN PORTFOLIO
    # ---------------------------------------------------------
    print("\n📡 Connecting to Dhan API...")
    load_dotenv()
    try:
        dhan = dhanhq(os.getenv("DHAN_CLIENT_ID"), os.getenv("DHAN_ACCESS_TOKEN"))
        response = dhan.get_holdings()
        if response['status'] != 'success':
            raise Exception(f"API Failed: {response}")
        dhan_data = response['data']
        print(f"   ✅ Fetched {len(dhan_data)} active positions.")
    except Exception as e:
        print(f"   ❌ FATAL: Could not fetch portfolio. {e}")
        return

    # ---------------------------------------------------------
    # STEP 4: MERGE & UPDATE
    # ---------------------------------------------------------
    print("\n⚙️  Merging Data (Dhan + TradingView SLs)...")
    merged_rows = []
    slot_num = 1
    
    for stock in dhan_data:
        raw_sym = stock.get('tradingSymbol', 'Unknown')
        norm_sym = normalize_ticker(raw_sym)
        ticker_fmt = f"NSE:{norm_sym}"
        
        # Base Data from Dhan
        qty = int(stock.get('totalQty', 0))
        entry = float(stock.get('avgCostPrice', 0.0))
        
        # Determine SL and Sector
        final_sl = 0.0
        final_sec = DEFAULT_SECTOR
        
        # Priority 1: New TradingView Import
        if norm_sym in tv_data:
            final_sl = tv_data[norm_sym]['SL']
            if tv_data[norm_sym]['Sector']:
                final_sec = tv_data[norm_sym]['Sector']
        # Priority 2: Existing Manual Data
        elif norm_sym in existing_manual_data:
            final_sl = existing_manual_data[norm_sym]['SL']
            final_sec = existing_manual_data[norm_sym]['Sector']
        
        # Auto-Fill Sector if missing
        if not final_sec or final_sec == DEFAULT_SECTOR or final_sec == "nan":
             # We can't easily auto-guess here without the sector_manager logic
             # But sector_manager has auto_fill_portfolio_csv...
             # Let's just set default for now, and let sector_manager fix it later?
             # Actually, we can use sector_manager lookup if we want.
             pass

        merged_rows.append({
            'Slot': slot_num,
            'Ticker': ticker_fmt,
            'Entry': round(entry, 2),
            'Qty': qty,
            'SL': final_sl,
            'Sector': final_sec
        })
        slot_num += 1
        
    # Save to CSV
    new_df = pd.DataFrame(merged_rows)
    new_df.to_csv(CSV_PATH, index=False)
    print(f"   ✅ Saved merged portfolio to '{CSV_PATH}'")

    # ---------------------------------------------------------
    # STEP 5: AUTO-FILL SECTORS (Using Sector Manager)
    # ---------------------------------------------------------
    print("\n🔍 Auto-Detecting Sectors...")
    sector_manager.auto_fill_portfolio_csv() 
    # This reads CSV, fills missing sectors, and saves back to CSV
    
    # ---------------------------------------------------------
    # STEP 6: UPDATE PINE SCRIPT
    # ---------------------------------------------------------
    print(f"\n📝 Updating Pine Script: {PINE_PATH}...")
    
    # Read fresh CSV (with sectors filled)
    final_df = pd.read_csv(CSV_PATH)
    
    # Generate Pine Code
    lines = []
    for i in range(1, 26):
        slot_data = final_df[final_df['Slot'] == i]
        tick, entry, sl, sec = "", 0.0, 0.0, "NSE:CNX500"
        
        if not slot_data.empty:
            row = slot_data.iloc[0]
            if pd.notna(row['Ticker']): tick = str(row['Ticker']).strip()
            if pd.notna(row['Entry']): entry = float(row['Entry'])
            if pd.notna(row['SL']): sl = float(row['SL'])
            if pd.notna(row['Sector']): sec = str(row['Sector']).strip()

        # Group Logic
        grp_var = "grpP1_5"
        if i == 1: lines.append(f'grpP1_5 = "1. Portfolio Slots 1-5"')
        elif i == 6: 
            lines.append(f'\n// --- GROUP 2: SLOTS 6-10 ---')
            lines.append(f'grpP6_10 = "2. Portfolio Slots 6-10"')
            grp_var = "grpP6_10"
        elif i == 11:
            lines.append(f'\n// --- GROUP 3: SLOTS 11-15 ---')
            lines.append(f'grpP11_15 = "3. Portfolio Slots 11-15"')
            grp_var = "grpP11_15"
        elif i == 16:
            lines.append(f'\n// --- GROUP 4: SLOTS 16-20 ---')
            lines.append(f'grpP16_20 = "4. Portfolio Slots 16-20"')
            grp_var = "grpP16_20"
        elif i == 21:
            lines.append(f'\n// --- GROUP 5: SLOTS 21-25 ---')
            lines.append(f'grpP21_25 = "5. Portfolio Slots 21-25"')
            grp_var = "grpP21_25"
            
        if i > 5 and i <= 10: grp_var = "grpP6_10"
        if i > 10 and i <= 15: grp_var = "grpP11_15"
        if i > 15 and i <= 20: grp_var = "grpP16_20"
        if i > 20: grp_var = "grpP21_25"

        lines.append(f'p{i}_tick = input.string("{tick}", title="Slot {i}", group={grp_var}, inline="p{i}", display=display.data_window)')
        lines.append(f'p{i}_ent  = input.float({entry}, title="Entry", group={grp_var}, inline="p{i}", display=display.data_window)')
        lines.append(f'p{i}_sl   = input.price({sl}, title="SL", group={grp_var}, inline="p{i}", display=display.data_window)')
        lines.append(f'p{i}_sec  = input.symbol("{sec}", title="Sector", group={grp_var}, inline="p{i}s", display=display.data_window)')
        lines.append("")

    new_code_block = "\n".join(lines)

    # Inject
    try:
        with open(PINE_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        
        start_marker = "// <PORTFOLIO_START>"
        end_marker = "// <PORTFOLIO_END>"
        
        s_idx = content.find(start_marker)
        e_idx = content.find(end_marker)
        
        if s_idx == -1 or e_idx == -1:
            print("   ❌ Error: Target markers not found in Pine Script.")
        else:
            new_content = content[:s_idx + len(start_marker)] + "\n" + new_code_block + "\n" + content[e_idx:]
            
            # DB Lookup Inject (Optional but good)
            db_s = "// <DB_LOOKUP_START>"
            db_e = "// <DB_LOOKUP_END>"
            dbs_idx = new_content.find(db_s)
            dbe_idx = new_content.find(db_e)
            
            if dbs_idx != -1 and dbe_idx != -1:
                map_code = sector_manager.generate_pine_sector_map()
                new_content = new_content[:dbs_idx] + map_code + new_content[dbe_idx + len(db_e):]
            
            with open(PINE_PATH, "w", encoding="utf-8") as f:
                f.write(new_content)
            print("   ✅ Pine Script Updated Successfully.")
            print("   👉 ACTION: Copy ALL code from valid file in VS Code -> Paste to TradingView.")
            
    except Exception as e:
        print(f"   ❌ Error editing Pine file: {e}")

    input("\n✅ SYNC COMPLETE. Press Enter to exit...")

if __name__ == "__main__":
    main()
