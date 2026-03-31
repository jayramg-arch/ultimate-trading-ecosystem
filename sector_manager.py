import json
import os
import pandas as pd
import yfinance as yf
import time

# CONFIG
DB_PATH = "sector_db.json"
CSV_PATH = "portfolio.csv"
DEFAULT_SECTOR = "NSE:CNX500"

# MAPPING: Yahoo Sector -> Nifty Index (Best Effort)
SECTOR_MAP = {
    "Financial Services": "NSE:BANKNIFTY",
    "Technology": "NSE:CNXIT",
    "Energy": "NSE:CNXENERGY",
    "Basic Materials": "NSE:CNXMETAL",
    "Consumer Cyclical": "NSE:CNXAUTO",  # Or Consumption
    "Consumer Defensive": "NSE:CNXFMCG",
    "Healthcare": "NSE:CNXPHARMA",
    "Utilities": "NSE:CNXINFRA",
    "Real Estate": "NSE:CNXREALTY",
    "Industrials": "NSE:CNXINFRA",
    "Communication Services": "NSE:CNXMEDIA" # Or Infra for Telecom
}

def load_db():
    if not os.path.exists(DB_PATH):
        return {}
    try:
        with open(DB_PATH, "r") as f:
            return json.load(f)
    except:
        return {}

def save_db(data):
    with open(DB_PATH, "w") as f:
        json.dump(data, f, indent=4)

def fetch_sector_online(ticker):
    """
    Fetches sector from Yahoo Finance for a given NSE ticker.
    Ticker format expected: NSE:RELIANCE -> RELIANCE.NS
    """
    clean_ticker = ticker.replace("NSE:", "").strip()
    
    # Check for Indices or ETFs which might fail in YF lookup or need special handling
    if "NIFTY" in clean_ticker or "SENSEX" in clean_ticker:
        return "NSE:NIFTY" # Generic for indices

    yf_ticker = f"{clean_ticker}.NS"
    
    try:
        print(f"🔍 Fetching sector for {yf_ticker}...")
        stock = yf.Ticker(yf_ticker)
        # Fast access to info
        info = stock.info 
        
        # Get Yahoo Sector
        y_sector = info.get('sector', '')
        
        if y_sector in SECTOR_MAP:
            return SECTOR_MAP[y_sector]
        
        # Fallback Logic based on Industry if needed
        # ...
        
        if y_sector:
            print(f"   Shape: {y_sector} (No direct map, using default)")
            return DEFAULT_SECTOR # Found a sector but no map
            
    except Exception as e:
        print(f"   ⚠️ Error fetching {yf_ticker}: {e}")
    
    return None

def update_sector_db_bulk(tickers):
    db = load_db()
    updated = False
    
    for t in tickers:
        t = t.strip().upper()
        if not t.startswith("NSE:"):
            t = "NSE:" + t
            
        if t not in db:
            # Try to fetch
            found_sector = fetch_sector_online(t)
            if found_sector:
                db[t] = found_sector
                print(f"✅ Mapped {t} -> {found_sector}")
                updated = True
                time.sleep(0.5) # Be polite to API
            else:
                # Mark as unknown so we don't retry endlessly? 
                # Or just leave it for next time.
                pass
    
    if updated:
        save_db(db)
        print("💾 Database saved.")
    else:
        print("db up to date.")

def auto_fill_portfolio_csv():
    print("\n[SECTOR MANAGER] Auto-filling Portfolio CSV...")
    
    if not os.path.exists(CSV_PATH):
        print("❌ No portfolio.csv found.")
        return

    try:
        df = pd.read_csv(CSV_PATH)
        db = load_db()
        
        # Identify tickers needing processing
        tickers_to_check = []
        
        for index, row in df.iterrows():
            ticker = str(row.get('Ticker', '')).strip().upper()
            if not ticker or ticker == 'NAN': continue
            
            # Normalize
            if not ticker.startswith("NSE:"):
                ticker = "NSE:" + ticker
                
            current_sector = str(row.get('Sector', '')).strip()
            
            # If sector is missing or default, we try to improve it
            if not current_sector or current_sector == 'nan' or current_sector == DEFAULT_SECTOR:
                tickers_to_check.append(ticker)

        # 1. Update DB for these tickers if needed
        if tickers_to_check:
            print(f"checking {len(set(tickers_to_check))} tickers...")
            update_sector_db_bulk(list(set(tickers_to_check)))
            # Reload DB after updates
            db = load_db()
            
        # 2. Apply to Dataframe
        updates_count = 0
        for index, row in df.iterrows():
            ticker = str(row.get('Ticker', '')).strip().upper()
            if not ticker or ticker == 'NAN': continue
             # Normalize
            if not ticker.startswith("NSE:"):
                ticker = "NSE:" + ticker
            
            current_sector = str(row.get('Sector', '')).strip()
            
            # Check DB
            if ticker in db:
                best_sector = db[ticker]
                # Only update if current is "bad" (empty or default) AND new one is different
                if (not current_sector or current_sector == 'nan' or current_sector == DEFAULT_SECTOR) and (current_sector != best_sector):
                    df.at[index, 'Sector'] = best_sector
                    updates_count += 1
        
        if updates_count > 0:
            df.to_csv(CSV_PATH, index=False)
            print(f"✅ Updated {updates_count} rows in {CSV_PATH} with sectors from database.")
        else:
            print("✨ Portfolio sectors are already up to date.")

    except Exception as e:
        print(f"❌ Error in auto-fill: {e}")

def generate_pine_sector_map():
    """
    Generates a Pine Script function that acts as a lookup table 
    derived from the JSON database.
    """
    db = load_db()
    
    lines = []
    lines.append("// <DB_LOOKUP_START>")
    lines.append("// This function is AUTO-GENERATED by sector_manager.py")
    lines.append("f_db_sector_lookup(string t) =>")
    lines.append("    string s = \"\"")
    lines.append("    // Ticker format in text is usually just the name (e.g. RELIANCE)")
    lines.append("    // We match against the DB keys which are NSE:RELIANCE")
    lines.append("    switch t")
    
    # Sort for stability
    for ticker_key in sorted(db.keys()):
        # db key = "NSE:RELIANCE", val = "NSE:CNXINFRA"
        # Pine ticker usually comes as "RELIANCE" or "NSE:RELIANCE". 
        # We will assume we pass the CLEAN ticker (RELIANCE) into the switch
        
        clean_tick = ticker_key.replace("NSE:", "").replace("BSE:", "").strip()
        sector_val = db[ticker_key]
        
        lines.append(f"        \"{clean_tick}\" => \"{sector_val}\"")
        
    lines.append("        => \"\"") # Default empty
    lines.append("    s")
    lines.append("// <DB_LOOKUP_END>")
    
    return "\n".join(lines)

def seed_fno_stocks():
    """
    Seeds the DB with common F&O stocks if they are missing.
    This ensures the user has a good base for analysis immediately.
    """
    fno_list = [
        # --- NIFTY 50 ---
        "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO",
        "BAJFINANCE", "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA",
        "COALINDIA", "DIVISLAB", "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK",
        "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK",
        "INFY", "JSWSTEEL", "KOTAKBANK", "LTIM", "LT", "M&M", "MARUTI", "NTPC", "NESTLEIND",
        "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM",
        "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO",
        
        # --- NIFTY NEXT 50 & F&O Liquid ---
        "ABB", "ACC", "ADANIENSOL", "ADANIGREEN", "ALKEM", "AMBUJACEM", "DMART", "BAJAJHLDNG",
        "BANKBARODA", "BERGEPAINT", "BHEL", "BOSCHLTD", "CANBK", "CHOLAFIN", "COLPAL", "DLF",
        "DABUR", "GAIL", "GODREJCP", "GODREJPROP", "HAVELLS", "HAL", "HINDPETRO", "ICICIGI",
        "ICICIPRULI", "IOC", "IRCTC", "IGL", "INDUSTOWER", "NAUKRI", "INDIGO", "JINDALSTEL",
        "JIOFIN", "LICI", "LUPIN", "MARICO", "MCDOWELL-N", "MOTHERSON", "MUTHOOTFIN", "NMDC",
        "OBEROIRLTY", "OFSS", "PIIND", "PAGEIND", "PIDILITIND", "PFC", "PNB", "RECLTD",
        "SHREECEM", "SHRIRAMFIN", "SIEMENS", "SRF", "SOLARINDS", "SBICARD", "TORNTPHARM",
        "TORNTPOWER", "TRENT", "UBL", "UNITDSPR", "VBL", "VEDL", "ZOMATO", "ZYDUSLIFE",

        # --- KEY MIDCAP F&O ---
        "AARTIIND", "ABBOTINDIA", "ABCAPITAL", "ABFRL", "ALKEM", "AMBER", "APLAPOLLO", "AUBANK",
        "AUROPHARMA", "BALKRISIND", "BALRAMCHIN", "BANDHANBNK", "BATAINDIA", "BSOFT",
        "BHARATFORG", "BSE", "CANFINHOME", "CASTROLIND", "CDSL", "CEA", "CHAMBLFERT", 
        "CUB", "COFORGE", "CONCOR", "COROMANDEL", "CROMPTON", "CUMMINSIND", "DEEPAKNTR",
        "DELHIVERY", "DIXON", "ESCORTS", "EXIDEIND", "FEDERALBNK", "GLENMARK", "GMRINFRA",
        "GNFC", "GODREJPROP", "GRANULES", "GUJGASLTD", "HOTEI", "IDFCFIRSTB", "IEX",
        "INDIAMART", "ISEC", "INDHOTEL", "IPCALAB", "JSL", "JWL", "KALYANKJIL", "KEI",
        "KPITTECH", "LALPATHLAB", "LAURUSLAB", "LICHSGFIN", "LODHA", "LUPIN", "MANAPPURAM",
        "MAZDOCK", "MCX", "METROPOLIS", "MFSL", "MGL", "MPHASIS", "MRF", "NATCOPHARM",
        "NATIONALUM", "NAVINFLUOR", "NBCC", "NHPC", "OBEROIRLTY", "OIL", "PERSISTENT",
        "PETRONET", "PHOENIXLTD", "POLYCAB", "POONAWALLA", "PRESTIGE", "RBLBANK", "RVNL",
        "SAIL", "SYNGENE", "TATACOMM", "TATAELXSI", "TATAPOWER", "RAMCOCEM", "TITAGARH",
        "TVSMOTOR", "UPL", "VOLTAS", "WHIRLPOOL", "YESBANK", "ZEEL"
    ]
    
    print("\n[SEEDING] Checking F&O coverage...")
    update_sector_db_bulk(fno_list)

if __name__ == "__main__":
    # Optional: ensure we have data
    seed_fno_stocks()
    auto_fill_portfolio_csv()

