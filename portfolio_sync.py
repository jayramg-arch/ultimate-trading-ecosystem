import pandas as pd
import os
import sector_manager  # <--- NEW IMPORT

# CONFIG
CSV_PATH = "portfolio.csv"
PINE_PATH = "Weinstein & Swing Pro Dashboard v53.12Pine code.pine"

def generate_pine_code(df):
    lines = []
    
    # Ensure we have 25 slots (pad if necessary)
    for i in range(1, 26):
        slot_data = df[df['Slot'] == i]
        
        # Defaults
        tick = ""
        entry = 0.0
        sl = 0.0
        sec = "NSE:CNX500"
        
        if not slot_data.empty:
            row = slot_data.iloc[0]
            if pd.notna(row['Ticker']) and str(row['Ticker']).strip() != "":
                tick = str(row['Ticker']).strip()
            if pd.notna(row['Entry']):
                entry = float(row['Entry'])
            if pd.notna(row['SL']):
                sl = float(row['SL'])
            # Use the sector from CSV (which is now auto-filled by sector_manager)
            if pd.notna(row['Sector']) and str(row['Sector']).strip() != "":
                sec = str(row['Sector']).strip()

        # Determine Group
        if i == 1:
            lines.append(f'grpP1_5 = "1. Portfolio Slots 1-5"')
        elif i == 6:
            lines.append(f'\n// --- GROUP 2: SLOTS 6-10 ---')
            lines.append(f'grpP6_10 = "2. Portfolio Slots 6-10"')
        elif i == 11:
            lines.append(f'\n// --- GROUP 3: SLOTS 11-15 ---')
            lines.append(f'grpP11_15 = "3. Portfolio Slots 11-15"')
        elif i == 16:
            lines.append(f'\n// --- GROUP 4: SLOTS 16-20 ---')
            lines.append(f'grpP16_20 = "4. Portfolio Slots 16-20"')
        elif i == 21:
            lines.append(f'\n// --- GROUP 5: SLOTS 21-25 ---')
            lines.append(f'grpP21_25 = "5. Portfolio Slots 21-25"')
            
        grp_var = "grpP1_5"
        if i > 5: grp_var = "grpP6_10"
        if i > 10: grp_var = "grpP11_15"
        if i > 15: grp_var = "grpP16_20"
        if i > 20: grp_var = "grpP21_25"

        lines.append(f'p{i}_tick = input.string("{tick}", title="Slot {i}", group={grp_var}, inline="p{i}", display=display.data_window)')
        lines.append(f'p{i}_ent  = input.float({entry}, title="Entry", group={grp_var}, inline="p{i}", display=display.data_window)')
        lines.append(f'p{i}_sl   = input.price({sl}, title="SL", group={grp_var}, inline="p{i}", display=display.data_window)')
        lines.append(f'p{i}_sec  = input.symbol("{sec}", title="Sector", group={grp_var}, inline="p{i}s", display=display.data_window)')
        lines.append("")

    return "\n".join(lines)

def sync_portfolio():
    # 1. AUTO-UPDATE SECTORS FIRST
    sector_manager.auto_fill_portfolio_csv()
    
    print(f"Reading portfolio from {CSV_PATH}...")
    try:
        df = pd.read_csv(CSV_PATH)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    print("Generating Pine Script code...")
    new_code_block = generate_pine_code(df)

    print(f"Updating Pine Script: {PINE_PATH}...")
    try:
        with open(PINE_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        
        start_marker = "// <PORTFOLIO_START>"
        end_marker = "// <PORTFOLIO_END>"
        
        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)
        
        if start_idx == -1 or end_idx == -1:
            print("ERROR: Markers not found in Pine Script file.")
            return

        # Keep markers, replace content between them
        new_content = content[:start_idx + len(start_marker)] + "\n" + new_code_block + "\n" + content[end_idx:]
        
        # --- NEW: INJECT DB LOOKUP ---
        # We also want to update the DB Lookup function in the Pine script
        db_start = "// <DB_LOOKUP_START>"
        db_end   = "// <DB_LOOKUP_END>"
        
        dbs_idx = new_content.find(db_start)
        dbe_idx = new_content.find(db_end)
        
        if dbs_idx != -1 and dbe_idx != -1:
            print("Injecting Sector DB Lookup into Pine Script...")
            map_code = sector_manager.generate_pine_sector_map()
            # Replace
            new_content = new_content[:dbs_idx] + map_code + new_content[dbe_idx + len(db_end):]
        else:
            print("⚠️ Warning: DB Lookup markers not found in Pine Script.")
        # -----------------------------

        with open(PINE_PATH, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        print("SUCCESS! Pine Script updated.")
        print("Action: Copy the code from VS Code and paste it into TradingView Pine Editor.")

    except Exception as e:
        print(f"Error writing Pine Script: {e}")

if __name__ == "__main__":
    sync_portfolio()
    input("\nPress Enter to exit...")
