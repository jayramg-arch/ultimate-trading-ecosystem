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
PINE_PATH = "Weinstein and Swing Pro Dashboard v67.4.12.pine"
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
                        tv_data[t] = {'SL': sl, 'Sector': sec, 'Date': row.get('Date', '')}
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
                        'Sector': row.get('Sector', DEFAULT_SECTOR), 'Date': str(row.get('Date', ''))
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
        final_date = 0
        
        # Priority 1: New TradingView Import
        if norm_sym in tv_data:
            final_sl = tv_data[norm_sym]['SL']
            if tv_data[norm_sym]['Sector']:
                final_sec = tv_data[norm_sym]['Sector']
            if 'Date' in tv_data[norm_sym] and tv_data[norm_sym]['Date'] and str(tv_data[norm_sym]['Date']).lower() != 'nan':
                final_date = tv_data[norm_sym]['Date']
        # Priority 2: Existing Manual Data
        elif norm_sym in existing_manual_data:
            final_sl = existing_manual_data[norm_sym]['SL']
            final_sec = existing_manual_data[norm_sym]['Sector']
            if 'Date' in existing_manual_data[norm_sym] and existing_manual_data[norm_sym]['Date'] and str(existing_manual_data[norm_sym]['Date']).lower() != 'nan':
                final_date = existing_manual_data[norm_sym]['Date']
        
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
            'Sector': final_sec, 'Date': final_date
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
    
    try:
        with open(PINE_PATH, "r", encoding="utf-8") as f:
            pine_content = f.read()
    except Exception as e:
        print(f"Error reading {PINE_PATH}: {e}")
        return

    import re
    # Try to extract existing values from the Pine script using regex
    existing_tsl = {}
    existing_t1 = {}
    existing_t2 = {}
    existing_dates = {}
    existing_sectors = {}
    
    # Parse existing values line by line
    tick_pattern = re.compile(r'p(\d+)_tick\s*=\s*input\.string\("([^"]*)"')
    tsl_pattern = re.compile(r'p(\d+)_tsl\s*=\s*input\.price\(([^,\)]+)')
    t1_pattern = re.compile(r'p(\d+)_t1\s*=\s*input\.price\(([^,\)]+)')
    t2_pattern = re.compile(r'p(\d+)_t2\s*=\s*input\.price\(([^,\)]+)')
    sec_pattern = re.compile(r'p(\d+)_sec\s*=\s*input\.string\("([^"]*)"')
    date_pattern = re.compile(r'p(\d+)_date\s*=\s*input\.time\(([^,\)]+)')

    slots_parsed = {}
    for line in pine_content.splitlines():
        m_tick = tick_pattern.search(line)
        if m_tick:
            slots_parsed.setdefault(int(m_tick.group(1)), {})["tick"] = m_tick.group(2).strip()
            continue
        m_tsl = tsl_pattern.search(line)
        if m_tsl:
            slots_parsed.setdefault(int(m_tsl.group(1)), {})["tsl"] = m_tsl.group(2).strip()
            continue
        m_t1 = t1_pattern.search(line)
        if m_t1:
            slots_parsed.setdefault(int(m_t1.group(1)), {})["t1"] = m_t1.group(2).strip()
            continue
        m_t2 = t2_pattern.search(line)
        if m_t2:
            slots_parsed.setdefault(int(m_t2.group(1)), {})["t2"] = m_t2.group(2).strip()
            continue
        m_sec = sec_pattern.search(line)
        if m_sec:
            slots_parsed.setdefault(int(m_sec.group(1)), {})["sec"] = m_sec.group(2).strip()
            continue
        m_date = date_pattern.search(line)
        if m_date:
            slots_parsed.setdefault(int(m_date.group(1)), {})["date"] = m_date.group(2).strip()
            continue

    # Map normalized ticker to existing values
    for slot_idx, data in slots_parsed.items():
        t = normalize_ticker(data.get("tick", ""))
        if t:
            if "tsl" in data: existing_tsl[t] = data["tsl"]
            if "t1" in data: existing_t1[t] = data["t1"]
            if "t2" in data: existing_t2[t] = data["t2"]
            if "date" in data: existing_dates[t] = data["date"]
            if "sec" in data: existing_sectors[t] = data["sec"]

    # Generate Pine Code
    lines = []
    for i in range(1, 21):
        slot_data = final_df[final_df['Slot'] == i]
        tick, entry, sl, sec = "", 0.0, 0.0, DEFAULT_SECTOR
        
        row = None
        if not slot_data.empty:
            row = slot_data.iloc[0]
            if pd.notna(row['Ticker']): tick = str(row['Ticker']).strip()
            if pd.notna(row['Entry']): entry = float(row['Entry'])
            if pd.notna(row['SL']): sl = float(row['SL'])
            if pd.notna(row['Sector']): sec = str(row['Sector']).strip()

        tick_norm = normalize_ticker(tick)
        
        # Default or extract existing values
        tsl_val = "0.0"
        t1_val = "0.0"
        t2_val = "0.0"
        date_val = "0"
        
        if tick_norm in existing_tsl: tsl_val = existing_tsl[tick_norm]
        if tick_norm in existing_t1: t1_val = existing_t1[tick_norm]
        if tick_norm in existing_t2: t2_val = existing_t2[tick_norm]
        if tick_norm in existing_dates: date_val = existing_dates[tick_norm]
        if tick_norm in existing_sectors and (not sec or sec == DEFAULT_SECTOR):
            sec = existing_sectors[tick_norm]
            
        if row is not None and 'Date' in row and pd.notna(row['Date']) and str(row['Date']).strip() and str(row['Date']).lower() != 'nan':
            try:
                dt_obj = datetime.strptime(str(row['Date']).strip(), "%Y-%m-%d")
                date_val = f'timestamp("{str(row["Date"]).strip()}")'
            except: pass

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
            
        if i <= 5: grp_var = "grpP1_5"
        elif i <= 10: grp_var = "grpP6_10"
        elif i <= 15: grp_var = "grpP11_15"
        else: grp_var = "grpP16_20"

        lines.append(f'p{i}_tick = input.string("{tick}", title="Slot {i}", group={grp_var}, inline="p{i}", display=display.data_window)')
        lines.append(f'p{i}_ent  = input.float({entry}, title="Entry", group={grp_var}, inline="p{i}", display=display.data_window)')
        lines.append(f'p{i}_sl   = input.price({sl}, title="SL", group={grp_var}, inline="p{i}", display=display.data_window)')
        lines.append(f'p{i}_tsl  = input.price({tsl_val}, title="Trail SL", group={grp_var}, inline="p{i}", display=display.data_window)')
        lines.append(f'p{i}_t1   = input.price({t1_val}, title="T1", group={grp_var}, inline="p{i}t", display=display.data_window)')
        lines.append(f'p{i}_t2   = input.price({t2_val}, title="T2", group={grp_var}, inline="p{i}t", display=display.data_window)')
        lines.append(f'p{i}_sec  = input.string("{sec}", title="Sector", group={grp_var}, inline="p{i}s", display=display.data_window)')
        lines.append(f'p{i}_date = input.time({date_val}, title="Date", group={grp_var}, inline="p{i}d", display=display.data_window)')
        lines.append("")

    new_code_block = "\n".join(lines)

    # Inject
    try:
        start_marker = "// <PORTFOLIO_START>"
        end_marker = "// <PORTFOLIO_END>"
        
        s_idx = pine_content.find(start_marker)
        e_idx = pine_content.find(end_marker)
        
        if s_idx == -1 or e_idx == -1:
            print("   ❌ Error: Target markers not found in Pine Script.")
        else:
            new_content = pine_content[:s_idx + len(start_marker)] + "\n" + new_code_block + "\n" + pine_content[e_idx:]
            
            # DB Lookup Inject (Optional but good)
            db_s = "// // // <DB_LOOKUP_START>"
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
