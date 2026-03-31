import pandas as pd
import os
import sys

# ==========================================
# CONFIGURATION
# ==========================================
MASTER_FILE = 'MASTER_scan_results.csv'

# Now we have ALL 4 Targets
TARGETS = [
    {
        "tech_file": "Stage2_Hunter.csv",     # From Chartink Option 1
        "output_file": "FINAL_Hunter_Picks.csv",
        "name": "Stage 2 Hunter"
    },
    {
        "tech_file": "Stage2_Pullback.csv",   # From Chartink Option 2
        "output_file": "FINAL_Pullback_Picks.csv",
        "name": "Stage 2 Pullback"
    },
    {
        "tech_file": "Early_Birds.csv",       # From Chartink Option 3
        "output_file": "FINAL_EarlyBird_Picks.csv",
        "name": "Early Birds"
    },
    {
        "tech_file": "Strong_Leaders.csv",    # From Chartink Option 4
        "output_file": "FINAL_Leader_Picks.csv",
        "name": "Strong Leaders"
    }
]

# ==========================================
# CONVICTION LOGIC
# ==========================================
def calculate_conviction_score(row):
    """Calculates a conviction score (1-10) based on fundamentals."""
    score = 5.0 # Base
    
    try:
        # 1. Profit Growth (fundamental)
        # Note: The CSV has newline characters in headers
        pg = float(str(row.get('Profit growth\n                    %', 0)).replace(',', '') or 0)
        if pg > 50: score += 2.5
        elif pg > 20: score += 1.5
        
        # 2. Sales Growth
        sg = float(str(row.get('Sales growth\n                    %', 0)).replace(',', '') or 0)
        if sg > 20: score += 1.0
        
        # 3. ROE
        roe = float(str(row.get('ROE\n                    %', 0)).replace(',', '') or 0)
        if roe > 20: score += 1.0
        
        # 4. Market Cap Bias (Small/Mid cap often higher conviction for swing)
        mcap = float(str(row.get('Mar Cap\n                    Rs.Cr.', 0)).replace(',', '') or 0)
        if 1000 < mcap < 20000: score += 0.5
        
    except:
        pass
        
    return round(min(10.0, score), 1)

# ==========================================
# MATCHING LOGIC
# ==========================================
def perform_match(return_raw=False):
    print("="*60)
    print("✨ GOLDEN MATCHER PRO: 4-WAY INTERSECTION")
    print("="*60)

    if not os.path.exists(MASTER_FILE):
        print(f"❌ CRITICAL: '{MASTER_FILE}' not found.")
        return {} if return_raw else None

    df_fund = pd.read_csv(MASTER_FILE, dtype=str)
    
    # Identify Fund Symbol Column
    col_fund = next((c for c in df_fund.columns if c.lower() in ['symbol', 'nsecode', 'name']), None)
    if not col_fund:
        print("❌ Error: No Symbol column in Master File.")
        return {} if return_raw else None
    
    df_fund['MATCH_KEY'] = df_fund[col_fund].astype(str).str.upper().str.strip()

    results_dict = {}

    # ==========================================
    # PREPARATION: CLEANUP OLD FILES
    # ==========================================
    import datetime
    import glob
    
    today_str = datetime.datetime.now().strftime("%d%b%y") # e.g., 08Feb26
    
    # Define Simplified Names Mapping
    name_map = {
        "FINAL_Hunter_Picks.csv": f"Hunters-{today_str}.csv",
        "FINAL_Pullback_Picks.csv": f"Pullbacks-{today_str}.csv",
        "FINAL_EarlyBird_Picks.csv": f"EarlyBirds-{today_str}.csv",
        "FINAL_Leader_Picks.csv": f"Leaders-{today_str}.csv"
    }

    folders = ["Strike", "TV"]
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
        else:
            # Clean existing CSVs to avoid confusion
            files = glob.glob(os.path.join(folder, "*.csv"))
            for f in files:
                try: os.remove(f)
                except: pass

    for target in TARGETS:
        tech_file = target['tech_file']
        out_file = target['output_file'] # Original full name
        start_name = target['name'] # "Stage 2 Hunter"
        
        # Determine Short Name for Export
        export_name = name_map.get(out_file, out_file.replace("FINAL_", "").replace("_Picks", "") + f"-{today_str}.csv")

        if not os.path.exists(tech_file):
            continue # Silent skip if file not generated yet

        df_tech = pd.read_csv(tech_file, dtype=str)
        if df_tech.empty: continue

        col_tech = next((c for c in df_tech.columns if c.lower() in ['symbol', 'nsecode']), None)
        if not col_tech: continue

        df_tech['MATCH_KEY'] = df_tech[col_tech].astype(str).str.upper().str.strip()

        # MATCH
        merged = pd.merge(df_fund, df_tech, on='MATCH_KEY', how='inner')
        
        if not merged.empty:
            # RESTORE CONSISTENT SYMBOL COLUMN BEFORE PROCESSING
            # After merge, we might have Symbol_x or NSECode_x
            actual_sym_col = next((c for c in merged.columns if c.lower() == 'symbol'), 
                                next((c for c in merged.columns if c.lower() == 'nsecode'),
                                next((c for c in merged.columns if c.lower().endswith('_x')), 
                                next((c for c in merged.columns if c.lower().endswith('_y')), None))))
            
            if actual_sym_col and actual_sym_col != 'Symbol':
                # If both Symbol_x and Symbol_y exist, prioritize _x but clean up others
                merged.rename(columns={actual_sym_col: 'Symbol'}, inplace=True)
            
            # Ensure we have a column named exactly 'Symbol'
            if 'Symbol' not in merged.columns:
                # Last ditch effort: find the first column that has a similar name
                potential = [c for c in merged.columns if 'sym' in c.lower() or 'code' in c.lower()]
                if potential:
                    merged.rename(columns={potential[0]: 'Symbol'}, inplace=True)

            # Drop duplicate-looking columns to keep CSV clean (e.g., Symbol_y)
            for col in merged.columns:
                if col != 'Symbol' and (col.lower().startswith('symbol_') or col.lower().startswith('nsecode_')):
                    del merged[col]

            # ENRICH WITH AI CONVICTION
            merged['Conviction'] = merged.apply(calculate_conviction_score, axis=1)
            
            # Fetch AI Catalyst for TOP picks (limit to avoid slowness)
            merged = merged.sort_values(by='Conviction', ascending=False)
            
            from ai_grading_engine import _fetch_technicals
            catalysts = []
            print(f"   ⚙️ Hybrid Engine Catalyst Analysis for {start_name} Top Picks...")
            for i, r in merged.iterrows():
                sym_val = r.get('Symbol', r.get('NSECode', 'Unknown'))
                techs = _fetch_technicals(sym_val)
                cat = techs.get('catalyst', 'NONE') if techs else 'NONE'
                # If the quant pattern couldn't figure it out, label it purely structurally.
                catalysts.append(cat)
            merged['Hybrid_Catalyst'] = catalysts
            
            # ── WEEKLY STAGE GATE ──
            # Reject stocks in weekly Stage 3/4 (price below weekly 30 SMA)
            print(f"   🛡️  Running Weekly Stage Gate for {start_name}...")
            weekly_pass = []
            try:
                import yfinance as yf
                for _, row in merged.iterrows():
                    sym = str(row.get('Symbol', '')).replace("NSE:", "").replace("BSE:", "").strip()
                    if not sym:
                        weekly_pass.append("N/A")
                        continue
                    try:
                        wdata = yf.download(f"{sym}.NS", period="1y", interval="1wk", progress=False)
                        if wdata.empty or len(wdata) < 30:
                            weekly_pass.append("PASS")  # Insufficient data, give benefit of doubt
                            continue
                        if isinstance(wdata.columns, pd.MultiIndex):
                            wdata.columns = wdata.columns.get_level_values(0)
                        weekly_close = float(wdata['Close'].iloc[-1])
                        weekly_sma30 = float(wdata['Close'].rolling(30).mean().iloc[-1])
                        if weekly_close >= weekly_sma30:
                            weekly_pass.append("PASS")
                        else:
                            weekly_pass.append("FAIL")
                    except:
                        weekly_pass.append("PASS")  # Fail open rather than blocking all
                merged['Weekly_Stage_Gate'] = weekly_pass
                
                # Filter out FAIL stocks
                rejected = merged[merged['Weekly_Stage_Gate'] == 'FAIL']
                if not rejected.empty:
                    rej_syms = rejected.get('Symbol', pd.Series()).tolist()
                    print(f"   ⛔ Weekly Stage Gate REJECTED {len(rejected)} stocks: {', '.join(str(s) for s in rej_syms[:5])}")
                merged = merged[merged['Weekly_Stage_Gate'] != 'FAIL'].drop(columns=['Weekly_Stage_Gate'])
            except Exception as e:
                print(f"   ⚠️ Weekly Gate Error: {e} (proceeding without filter)")
        
        # CLEANUP
        if 'MATCH_KEY' in merged.columns: del merged['MATCH_KEY']

        if "Symbol" not in merged.columns:
            print(f"⚠️ Warning: 'Symbol' column missing in {start_name}. Skipping specific exports.")
            merged.to_csv(out_file, index=False)
            continue

        # 1. SAVE FULL DATA (Root, Original Format, STANDARD NAME)
        df_root = merged.copy()
        df_root.to_csv(out_file, index=False)
        print(f"✅ {start_name}: Saved FULL DATA -> {out_file}")

        # 2. SAVE FOR STRIKE (Strike/ Folder, Symbol Only, No Prefix, DATED NAME)
        df_strike = merged[['Symbol']].copy()
        df_strike['Symbol'] = df_strike['Symbol'].astype(str).apply(lambda x: x.replace("NSE:", "").replace("BSE:", "").strip())
        strike_path = os.path.join("Strike", export_name)
        df_strike.to_csv(strike_path, index=False)
        print(f"   📂 Strike Export -> {strike_path}")

        # 3. SAVE FOR TRADINGVIEW (TV/ Folder, Symbol Only, With NSE: Prefix, DATED NAME)
        df_tv = merged[['Symbol']].copy()
        df_tv['Symbol'] = df_tv['Symbol'].astype(str).apply(lambda x: f"NSE:{x.strip()}" if not str(x).strip().startswith("NSE:") else x)
        tv_path = os.path.join("TV", export_name)
        df_tv.to_csv(tv_path, index=False)
        print(f"   📂 TV Export -> {tv_path}")
        
        if not merged.empty:
            results_dict[start_name] = merged

    print("\n🏁 Matching Complete.")
    
    if return_raw:
        return results_dict
    
    # Only pause if interactive
    # input("\nPress Enter to exit...") # Removed to avoid blocking bot

if __name__ == "__main__":
    perform_match()
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    perform_match()