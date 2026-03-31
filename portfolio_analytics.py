
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from dhanhq import dhanhq
from dotenv import load_dotenv
import os
import sqlite3
import datetime
import json
from bs4 import BeautifulSoup

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="Commander Analytics",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load Env
load_dotenv(override=True)
API_KEY = os.getenv("DHAN_ACCESS_TOKEN")
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DB_FILE = "trade_journal_v6.db"
CSV_PATH = "portfolio.csv"

# --- 2. GLOBAL STYLING (MATCHING COMMANDER WEB) ---
st.markdown("""
<style>
    /* GLOBAL DARK THEME & FONTS */
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');

    .stApp {
        background-image: linear-gradient(rgba(5, 10, 20, 0.95), rgba(5, 10, 20, 0.98));
        font-family: 'Inter', sans-serif;
        color: #e0f2f1;
    }
    
    /* HEADERS */
    h1, h2, h3 {
        font-family: 'Rajdhani', sans-serif !important;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    h1 {
        background: linear-gradient(to right, #00F260, #0575E6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        margin-bottom: 0px;
    }

    /* CARD CONTAINERS */
    div[data-testid="stMetric"], div.stContainer {
        background: rgba(12, 18, 28, 0.6);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    
    /* METRICS */
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem !important;
        color: #aaa !important;
        font-family: 'Rajdhani';
        letter-spacing: 1px;
    }
    [data-testid="stMetricValue"] {
        font-family: 'Rajdhani' !important;
        font-weight: 700;
        font-size: 2rem !important;
        color: #fff !important;
    }
    
    /* TABLES */
    div[data-testid="stDataFrame"] {
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 8px;
    }

    /* --- CUSTOM BUTTON TABS --- */
    /* UNSELECTED TABS: Glowing Amber Outline */
    div[data-testid="stHorizontalBlock"]:has(#analytics-tabs-marker) [data-testid="stBaseButton-secondary"] {
        background: transparent !important;
        border: 2px solid #FDC830 !important;
        color: #FDC830 !important;
        box-shadow: 0 0 10px rgba(253, 200, 48, 0.2) !important;
        text-shadow: 0 0 5px rgba(253, 200, 48, 0.3) !important;
    }

    /* SELECTED TABS: Fully Amber Gradient */
    div[data-testid="stHorizontalBlock"]:has(#analytics-tabs-marker) [data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #FDC830 0%, #F37335 100%) !important;
        color: #000 !important;
        border: none !important;
        box-shadow: 0 0 20px rgba(253, 200, 48, 0.6) !important;
        font-weight: 800 !important;
    }

</style>
""", unsafe_allow_html=True)

# --- 3. DATA FETCHING ---
def format_inr(number):
    """Formats number with Indian Rupee style commas (Lakhs/Crores)."""
    try:
        if number is None or pd.isna(number): return "₹0"
        val = float(number)
        is_negative = val < 0
        val = abs(val)
        
        s = "{:.2f}".format(val)
        parts = s.split(".")
        main_part = parts[0]
        decimal_part = parts[1]
        
        # Indian Numbering System: Last 3 digits, then groups of 2
        if len(main_part) <= 3:
            res = main_part
        else:
            last_three = main_part[-3:]
            remaining = main_part[:-3]
            res = ""
            while len(remaining) > 2:
                res = "," + remaining[-2:] + res
                remaining = remaining[:-2]
            res = remaining + res + "," + last_three
            
        final_str = f"₹{'-' if is_negative else ''}{res}"
        if decimal_part != "00":
            final_str += f".{decimal_part}"
        return final_str
    except:
        return str(number)

def normalize_symbol(symbol):
    """Strips standard noise (Ltd, Limited, NSE, BSE, etc.) for robust matching."""
    if not symbol or pd.isna(symbol): return "UNKNOWN"
    s = str(symbol).strip().upper()
    # Remove exchanges
    s = s.replace("| NSE", "").replace("| BSE", "").replace("NSE:", "").replace("BSE:", "").replace(" NSE", "").replace(" BSE", "")
    # Remove legal suffixes
    for suffix in [" LIMITED", " LTD", " IND", " IN", " CORP", " CORPORATION"]:
        if s.endswith(suffix):
            s = s[:-len(suffix)].strip()
    # Remove extra dots/commas
    s = s.replace(".", "").replace(",", "").strip()
    return s

def color_pnl(val):
    """Dynamic coloring for P&L values."""
    color = '#00F260' if val >= 0 else '#FF5252'
    return f'color: {color}; font-weight: bold'

def identify_sector(sym, sector_map):
    """Identifies sector using holdings map or local database."""
    # 1. Check current holdings
    if sym in sector_map and sector_map[sym] != "Unknown":
        return sector_map[sym]
    # 2. Check local JSON DB
    return get_symbol_sector(sym)

@st.cache_data(ttl=60)
def fetch_portfolio_data():
    """Fetches Live Data (Dhan) + Context (Journal/CSV)"""
    
    # A. CONNECT TO DHAN
    dhan = None
    if API_KEY and CLIENT_ID:
        try:
            dhan = dhanhq(client_id=CLIENT_ID, access_token=API_KEY)
        except: pass
    
    holdings_df = pd.DataFrame()
    balance = 0.0
    
    if dhan:
        # 1. HOLDINGS
        resp = dhan.get_holdings()
        if resp['status'] == 'success':
            holdings_df = pd.DataFrame(resp['data'])
            
        # 2. BALANCE
        f_resp = dhan.get_fund_limits()
        if f_resp['status'] == 'success':
            d = f_resp['data']
            balance = float(d.get('availabelBalance', 
                             d.get('withdrawableBalance', 
                             d.get('availCredits', 0.0))))
    
    # B. READ CONTEXT (Journal + CSV)
    journal_df = pd.DataFrame()
    if os.path.exists(DB_FILE):
        try:
            conn = sqlite3.connect(DB_FILE)
            # Fetch entry_price for P&L reconciliation
            journal_df = pd.read_sql("SELECT symbol, sector, timeframe, trade_quality, stoploss, target, rationale, entry_price FROM journal", conn)
            conn.close()
            # Normalize Symbols
            journal_df['symbol'] = journal_df['symbol'].str.replace('NSE:', '').str.strip()
        except Exception as e: 
            # Entry price might not exist in old DB versions
            try:
                conn = sqlite3.connect(DB_FILE)
                journal_df = pd.read_sql("SELECT symbol, sector, timeframe, trade_quality, stoploss, target, rationale FROM journal", conn)
                journal_df['entry_price'] = 0.0
                conn.close()
                journal_df['symbol'] = journal_df['symbol'].str.replace('NSE:', '').str.strip()
            except: pass
        
    csv_df = pd.DataFrame()
    if os.path.exists(CSV_PATH):
        try:
            csv_df = pd.read_csv(CSV_PATH)
            # Normalize
            csv_df['Ticker'] = csv_df['Ticker'].astype(str).str.replace('NSE:', '').str.strip()
        except: pass
        
    return holdings_df, balance, journal_df, csv_df

@st.cache_data(ttl=300)
def load_pnl_report():
    """Loads pnl_report.xls if present and extracts Realized P&L."""
    if not os.path.exists("pnl-report.xls"):
        return None
        
    try:
        # 1. Read without header to find the correct row
        df_scan = pd.read_excel("pnl-report.xls", header=None)
        
        header_row = -1
        # Scan first 20 rows for header keywords
        for i, row in df_scan.head(20).iterrows():
            row_vals = row.astype(str).values
            # Check for key columns
            if 'Security Name' in row_vals and 'Realised P&L' in row_vals:
                header_row = i
                break
        
        if header_row != -1:
            # 2. Re-read with correct header
            df = pd.read_excel("pnl-report.xls", header=header_row)
            
            # Filter for valid rows (where 'Security Name' is not null)
            if 'Security Name' in df.columns:
                df = df[df['Security Name'].notna()]
                # Also filter out recurring headers
                df = df[df['Security Name'] != 'Security Name'].copy()
                
            # Ensure key columns are numeric
            numeric_cols = ['Realised P&L', 'Avg. Buy Price', 'Avg. Sell Price', 'Buy Value', 'Sell Value']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                 
            return df
        else:
            # Fallback to previous hardcoded attempt if scan fails (unlikely)
            return None
            
    except Exception as e:
        # st.error(f"Error reading pnl-report.xls: {e}") # Suppress to avoid UI clutter if file is bad
        return None
    return None

@st.cache_data(ttl=300)
def parse_verified_trade_html():
    """Parses all suitable *.html files in the directory (Dhan Exports) for verified executions."""
    html_files = [f for f in os.listdir(".") if f.lower().endswith(".html") and ("trades" in f.lower() or "journal" in f.lower())]
    
    all_parsed = []
    for file_path in html_files:
        try:
            with open(file_path, "r", encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
                
            table = soup.find('table')
            if not table: continue
            
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 6: continue
                
                # 1. Date (Cell 0)
                dt_str = cells[0].get_text(strip=True)
                # 2. Symbol and Type (Cell 1)
                sym_cell = cells[1]
                img = sym_cell.find('img')
                txn_type = "UNKNOWN"
                if img and img.get('src'):
                    if 'buy.svg' in img.get('src'): txn_type = "BUY"
                    elif 'sell.svg' in img.get('src'): txn_type = "SELL"
                
                sym_text = sym_cell.get_text(separator=" ", strip=True)
                # Clean symbol: Remove | NSE BSE and extra spaces
                sym_clean = sym_text.replace("|", "").replace("NSE", "").replace("BSE", "").strip()
                # Remove extra spaces inside
                sym_clean = " ".join(sym_clean.split())
                
                # 3. Quantity (Cell 3 or 4 - usually 4 in journals)
                # Let's try to detect based on content if possible, or use 4
                qty_str = cells[4].get_text(strip=True).replace(",", "")
                try: qty = float(qty_str)
                except: qty = 0
                    
                # 4. Price (Cell 5)
                price_str = cells[5].get_text(strip=True).replace(",", "")
                try: price = float(price_str)
                except: price = 0.0
                    
                all_parsed.append({
                    'exchangeTime': pd.to_datetime(dt_str) if dt_str else None,
                    'Symbol': sym_clean,
                    'transactionType': txn_type,
                    'tradedQuantity': qty,
                    'tradedPrice': price
                })
        except: continue
        
    if not all_parsed: return pd.DataFrame()
    return pd.DataFrame(all_parsed).sort_values('exchangeTime')

@st.cache_data(ttl=300)
def parse_global_transaction_report_excel():
    """Parses Dhan_GlobalTransction_Report_*.xlsx for supplemental trade data."""
    xl_files = [f for f in os.listdir(".") if f.lower().endswith(".xlsx") and "globaltransction" in f.lower() and not f.startswith("~$")]
    
    all_trades = []
    for file_path in xl_files:
        try:
            # Inspection showed Row 4 (0-indexed) is the header
            df = pd.read_excel(file_path, header=4)
            
            # Clean column names (strip spaces)
            df.columns = [str(c).strip() for c in df.columns]
            
            # Identify columns
            col_date = 'Date' if 'Date' in df.columns else df.columns[0]
            col_scrip = 'Scrip Name' if 'Scrip Name' in df.columns else df.columns[1]
            col_buy_qty = 'Buy Qty.' if 'Buy Qty.' in df.columns else 'Unnamed: 4'
            col_buy_val = 'Buy Value' if 'Buy Value' in df.columns else 'Unnamed: 5'
            col_sell_qty = 'Sell Qty.' if 'Sell Qty.' in df.columns else 'Unnamed: 6'
            col_sell_val = 'Sell Value' if 'Sell Value' in df.columns else 'Unnamed: 7'

            valid_rows = df.dropna(subset=[col_date, col_scrip])
            
            for _, row in valid_rows.iterrows():
                # Skip header repetitions if any
                if str(row[col_date]).lower() == 'date': continue
                
                dt = pd.to_datetime(row[col_date], errors='coerce')
                if pd.isna(dt): continue
                
                scrip = str(row[col_scrip]).replace("NSE", "").replace("BSE", "").strip()
                if not scrip or scrip.lower() == 'nan': continue
                scrip = " ".join(scrip.split())
                
                # Check for Buy
                buy_qty = float(row.get(col_buy_qty, 0))
                buy_val = float(row.get(col_buy_val, 0))
                if buy_qty > 0:
                    all_trades.append({
                        'exchangeTime': dt,
                        'Symbol': scrip,
                        'transactionType': 'BUY',
                        'tradedQuantity': buy_qty,
                        'tradedPrice': buy_val / buy_qty if buy_qty > 0 else 0
                    })
                
                # Check for Sell
                sell_qty = float(row.get(col_sell_qty, 0))
                sell_val = float(row.get(col_sell_val, 0))
                if sell_qty > 0:
                    all_trades.append({
                        'exchangeTime': dt,
                        'Symbol': scrip,
                        'transactionType': 'SELL',
                        'tradedQuantity': sell_qty,
                        'tradedPrice': sell_val / sell_qty if sell_qty > 0 else 0,
                        'isin': row.get('isin', '') # Excel might not have it, but we'll try
                    })
        except Exception as e:
            continue
            
    if not all_trades: return pd.DataFrame()
    return pd.DataFrame(all_trades).sort_values('exchangeTime')

@st.cache_data(ttl=300)
def fetch_trade_history():
    """Fetches Trade History for FY25-26 from Dhan."""
    dhan = None
    if API_KEY and CLIENT_ID:
        try:
            dhan = dhanhq(client_id=CLIENT_ID, access_token=API_KEY)
        except: return pd.DataFrame()
    
    if not dhan: return pd.DataFrame()
    
    # Range: Fetch further back to capture older entry prices (e.g., 2023)
    from_date = '2023-01-01'
    to_date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    all_trades = []
    page = 0
    while True:
        try:
            resp = dhan.get_trade_history(from_date=from_date, to_date=to_date, page_number=page)
            if resp['status'] == 'success':
                data = resp['data']
                if not data: break
                all_trades.extend(data)
                page += 1
            else:
                break
        except:
            break
            
    if not all_trades: return pd.DataFrame()
    
    df = pd.DataFrame(all_trades)
    
    # Standardize columns
    df = df.rename(columns={
        'customSymbol': 'Symbol',
        'isin': 'isin' # already there
    })
    
    # Ensure datetime
    df['exchangeTime'] = pd.to_datetime(df['exchangeTime'])
    
    # Clean symbol in API too (just in case)
    if 'Symbol' in df.columns:
        df['Symbol'] = df['Symbol'].astype(str).str.strip()
    
    return df.sort_values('exchangeTime')

def process_trade_history(trade_df, journal_df=None, holdings_df=None):
    """
    Processes Raw Trade Log into Completed Trades (FIFO Matching).
    Matches SELL orders with preceding BUY orders to calculate Realized P&L.
    
    Fallbacks for Carry-Forward (missing API history):
    1. Local Journal (journal_df)
    2. Current Holdings Average Cost (holdings_df)
    """
    if trade_df.empty: return pd.DataFrame()
    
    # Create fallback maps for ISIN/Symbol
    isin_name_map = {}
    if holdings_df is not None and not holdings_df.empty:
        isin_name_map = dict(zip(holdings_df['isin'], holdings_df['Symbol']))

    # Sort chronological
    df = trade_df.sort_values('exchangeTime')
    
    inventory = {} # Key (ISIN or Symbol) -> List of {qty, price, date}
    completed_trades = []
    
    for _, row in df.iterrows():
        isin = row.get('isin', '')
        sym = row.get('Symbol', 'Unknown')
        # Use ISIN as primary key, fallback to Symbol
        key = isin if isin and isin != 'nan' else sym
        
        qty = row.get('tradedQuantity', 0)
        price = row.get('tradedPrice', 0.0)
        date = row['exchangeTime']
        txn_type = str(row.get('transactionType', 'UNKNOWN')).upper()
        
        display_name = isin_name_map.get(isin, sym)
        
        if key not in inventory: inventory[key] = []
        
        if txn_type == 'BUY':
            inventory[key].append({'qty': qty, 'price': price, 'date': date})
            
        elif txn_type == 'SELL':
            remaining_sell_qty = qty
            
            # 1. Match with existing inventory (Trades since Jan 2023)
            while remaining_sell_qty > 0 and inventory[key]:
                buy_record = inventory[key][0]
                matched_qty = min(remaining_sell_qty, buy_record['qty'])
                pnl = (price - buy_record['price']) * matched_qty
                
                completed_trades.append({
                    'Symbol': display_name,
                    'Qty': matched_qty,
                    'Entry Date': buy_record['date'].date(),
                    'Entry Price': buy_record['price'],
                    'Exit Date': date.date(),
                    'Exit Price': price,
                    'Realized P&L': pnl,
                    'ROI%': ((price - buy_record['price']) / buy_record['price']) * 100 if buy_record['price'] > 0 else 0,
                    'Matched': 'FIFO (API)'
                })
                
                remaining_sell_qty -= matched_qty
                buy_record['qty'] -= matched_qty
                if buy_record['qty'] <= 0: inventory[key].pop(0)
            
            # 2. If still has quantity, it's a CARRY-FORWARD
            if remaining_sell_qty > 0:
                entry_price = 0
                match_source = "UNMATCHED"
                
                # A. Try Journal Fallback
                if journal_df is not None and not journal_df.empty:
                    # Look for sym in journal
                    j_match = journal_df[journal_df['symbol'] == sym]
                    if not j_match.empty:
                        # Assuming journal has a column for cost or entry
                        # Let's check for 'avg_price' or 'entry'
                        entry_price = j_match.iloc[0].get('entry_price', 0)
                        if entry_price > 0: match_source = "Matched (Journal)"
                
                # B. Try Holdings Fallback (if partial exit)
                if entry_price <= 0 and holdings_df is not None and not holdings_df.empty:
                    h_match = holdings_df[holdings_df['Symbol'] == sym]
                    if not h_match.empty:
                        entry_price = h_match.iloc[0].get('Avg', 0)
                        if entry_price > 0: match_source = "Matched (Holding Avg)"

                if entry_price > 0:
                    pnl = (price - entry_price) * remaining_sell_qty
                    completed_trades.append({
                        'Symbol': display_name,
                        'Qty': remaining_sell_qty,
                        'Entry Date': 'PRE-FETCH',
                        'Entry Price': entry_price,
                        'Exit Date': date.date(),
                        'Exit Price': price,
                        'Realized P&L': pnl,
                        'ROI%': ((price - entry_price) / entry_price) * 100 if entry_price > 0 else 0,
                        'Matched': match_source
                    })
                else:
                    completed_trades.append({
                        'Symbol': display_name,
                        'Qty': remaining_sell_qty,
                        'Entry Date': 'UNKNOWN',
                        'Entry Price': 0,
                        'Exit Date': date.date(),
                        'Exit Price': price,
                        'Realized P&L': 0,
                        'ROI%': 0,
                        'Matched': 'ERROR (No Entry Found)'
                    })

    return pd.DataFrame(completed_trades)

# --- 4. PROCESSING ---
def processed_data():
    hdf, cash, jdf, cdf = fetch_portfolio_data()
    
    if hdf.empty:
        return None, cash, jdf, cdf

    # Standardize Holdings Columns
    # Dhan returns different keys sometimes: tradingSymbol, totalQty, avgCostPrice, lastPrice, lastTradedPrice, close
    hdf['Symbol'] = hdf.get('tradingSymbol', hdf.get('securityId', 'Unknown'))
    hdf['isin'] = hdf.get('isin', '')
    hdf['Qty'] = hdf.get('totalQty', hdf.get('netQty', 0))
    hdf['Avg'] = hdf.get('avgCostPrice', hdf.get('buyAvg', 0.0))
    
    # CMP/LTP robust fetch
    if 'lastTradedPrice' in hdf.columns:
        hdf['CMP'] = hdf['lastTradedPrice']
    elif 'ltp' in hdf.columns:
        hdf['CMP'] = hdf['ltp']
    elif 'lastPrice' in hdf.columns:
        hdf['CMP'] = hdf['lastPrice']
    elif 'close' in hdf.columns:
        hdf['CMP'] = hdf['close']
    else:
        hdf['CMP'] = 0.0 # Fallback
        
    hdf['Invested'] = hdf['Qty'] * hdf['Avg']
    hdf['CurVal'] = hdf['Qty'] * hdf['CMP']
    hdf['P&L'] = hdf['CurVal'] - hdf['Invested']
    hdf['P&L%'] = (hdf['P&L'] / hdf['Invested']) * 100
    
    # MERGE: Journal (Priority 1) -> CSV (Priority 2)
    final_df = hdf.copy()
    final_df['Sector'] = "Unknown"
    final_df['Timeframe'] = "Swing" # Default
    final_df['Quality'] = 3 # Average
    final_df['StopLoss'] = 0.0
    final_df['Tag'] = ""

    # Journal Merge
    if not jdf.empty:
        # Join on Symbol
        merged = final_df.merge(jdf, left_on='Symbol', right_on='symbol', how='left')
        final_df['Sector'] = merged['sector'].fillna("Unknown")
        final_df['Timeframe'] = merged['timeframe'].fillna("Swing")
        final_df['Quality'] = merged['trade_quality'].fillna(3)
        final_df['StopLoss'] = merged['stoploss'].fillna(0.0)
        final_df['Tag'] = merged['rationale'].fillna("") # Use rationale as tags
    
    # CSV Merge (Fallback for Sector/SL)
    # Loop to fill only if still Unknown/0
    if not cdf.empty:
        for idx, row in final_df.iterrows():
            sym = row['Symbol']
            # Find in CSV
            match = cdf[cdf['Ticker'] == sym]
            if not match.empty:
                # Fill Sector if Unknown
                if row['Sector'] == "Unknown":
                    final_df.at[idx, 'Sector'] = match.iloc[0].get('Sector', "Unknown")
                # Fill SL if 0
                if row['StopLoss'] == 0.0:
                    final_df.at[idx, 'StopLoss'] = match.iloc[0].get('SL', 0.0)

    # Clean Up Sector Names (Remove 'NSE:')
    final_df['Sector'] = final_df['Sector'].str.replace('NSE:', '').str.replace('^', '').str.strip()
    final_df['Sector'] = final_df['Sector'].replace("", "Unknown").fillna("Unknown")
    
    # Risk Metrics
    # Risk Amount = (Avg - SL) * Qty [If Long]
    # But more accurately: Risk = (CMP - SL) * Qty if SL is Trailing? 
    # Let's use Risk at Cost: (Avg - SL) * Qty
    final_df['RiskAmt'] = 0.0
    for i, r in final_df.iterrows():
        sl = r['StopLoss']
        if sl > 0:
            risk = (r['Avg'] - sl) * r['Qty']
            final_df.at[i, 'RiskAmt'] = max(0, risk) # Ensure non-negative
            
    return final_df, cash, jdf, cdf

@st.cache_data(ttl=600)
def get_symbol_sector(ticker):
    """Helper to get sector from local DB."""
    try:
        # Normalize ticker
        t = str(ticker).strip().upper()
        if not t.startswith("NSE:"):
            t = "NSE:" + t
            
        if not os.path.exists("sector_db.json"):
            return "Other"
        with open("sector_db.json", "r") as f:
            db = json.load(f)
            
        return db.get(t, "Other").replace("NSE:", "").replace("CNX", "")
    except:
        return "Other"

# --- 5. DASHBOARD UI ---
def main():
    # Use a cleaner way to handle data
    with st.spinner("🏥 Syncing with Dhan API..."):
        df_holdings, cash, journal_df, csv_df = processed_data()
        api_trades = fetch_trade_history()
        html_trades = parse_verified_trade_html()
        excel_trades = parse_global_transaction_report_excel()
        
        # Combine All Trade Sources with Priority
        if not api_trades.empty: api_trades['SourcePriority'] = 1
        else: api_trades = pd.DataFrame(columns=api_trades.columns.tolist() + ['SourcePriority'])
        
        if not html_trades.empty: html_trades['SourcePriority'] = 2
        else: html_trades = pd.DataFrame(columns=html_trades.columns.tolist() + ['SourcePriority'])
        
        if not excel_trades.empty: excel_trades['SourcePriority'] = 3
        else: excel_trades = pd.DataFrame(columns=excel_trades.columns.tolist() + ['SourcePriority'])

        sources = [api_trades, html_trades, excel_trades]
        valid_sources = [s for s in sources if not s.empty]
        
        if not valid_sources:
            source_df = pd.DataFrame()
        else:
            # Combine all
            source_df = pd.concat(valid_sources)
            
            # De-duplication Logic
            source_df['tradedPrice'] = source_df['tradedPrice'].round(2)
            source_df['match_date'] = pd.to_datetime(source_df['exchangeTime']).dt.date
            
            # Use Normalized Symbol for De-duplication
            source_df['NormSymbol'] = source_df['Symbol'].apply(normalize_symbol)
            
            # Sort: Priority first (API > HTML > Excel)
            source_df = source_df.sort_values(by=['SourcePriority', 'exchangeTime'])
            
            # Drop duplicates based on signature (Date, NormSymbol, Type, Qty, Price)
            # This keeps the highest priority source (API) for each unique trade
            source_df = source_df.drop_duplicates(
                subset=['match_date', 'NormSymbol', 'transactionType', 'tradedQuantity', 'tradedPrice'],
                keep='first'
            )
            
            source_df = source_df.drop(columns=['match_date', 'NormSymbol', 'SourcePriority'])
            source_df = source_df.sort_values('exchangeTime')
            
        xls_df = load_pnl_report()

    st.title("🏥 COMMANDER ANALYTICS PRO")
    
    # Sub-header with account status
    col_sys1, col_sys2 = st.columns([3, 1])
    with col_sys1:
        st.markdown("### 🏦 **LIVE TRADING PERFORMANCE AUDIT**")
    with col_sys2:
        if st.button("🔄 FORCE SYNC (API)", key="btn_force_sync", width="stretch"):
            st.cache_data.clear()
            st.rerun()
 
    # Initialize Tab State
    if 'analytics_tab' not in st.session_state:
        st.session_state.analytics_tab = "📊 HOLDINGS"
    
    # Button-styled Tabs (Cyber Amber Theme with Marker)
    t_col1, t_col2, t_col3 = st.columns(3)
    with t_col1:
        st.markdown('<div id="analytics-tabs-marker"></div>', unsafe_allow_html=True)
        if st.button("📊 HOLDINGS", width="stretch",
                     type="primary" if st.session_state.analytics_tab == "📊 HOLDINGS" else "secondary"):
            st.session_state.analytics_tab = "📊 HOLDINGS"
            st.rerun()
        with t_col2:
            if st.button("📈 PERFORMANCE", width="stretch",
                         type="primary" if st.session_state.analytics_tab == "📈 PERFORMANCE" else "secondary"):
                st.session_state.analytics_tab = "📈 PERFORMANCE"
                st.rerun()
        with t_col3:
            if st.button("📜 TRADE LOGS", width="stretch",
                         type="primary" if st.session_state.analytics_tab == "📜 TRADE LOGS" else "secondary"):
                st.session_state.analytics_tab = "📜 TRADE LOGS"
                st.rerun()

    st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
    active_tab = st.session_state.analytics_tab

    # --- TAB 1: HOLDINGS ---
    if active_tab == "📊 HOLDINGS":
        if df_holdings is None or df_holdings.empty:
            st.warning("No holdings found or API error.")
        else:
            # --- TOP METRICS ---
            # Ensure columns exist before summing (Defense)
            required_cols = ['Invested', 'CurVal', 'P&L']
            for col in required_cols:
                if col not in df_holdings.columns:
                    df_holdings[col] = 0.0
                    
            total_invested = df_holdings['Invested'].sum()
            total_cur_val = df_holdings['CurVal'].sum()
            total_pnl = df_holdings['P&L'].sum()
            total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
            
            total_equity = total_cur_val + cash
            cash_pct = (cash / total_equity * 100) if total_equity > 0 else 0
            
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("TOTAL EQUITY", format_inr(total_equity))
            m2.metric("INVESTED", format_inr(total_invested))
            m3.metric("CUR VAL", format_inr(total_cur_val))
            m4.metric("UNREALIZED P&L", format_inr(total_pnl), delta=f"{total_pnl_pct:.2f}%")
            m5.metric("CASH BALANCE", format_inr(cash), delta=f"{cash_pct:.1f}% Allocation")
            
            st.markdown("---")
            
            # --- CHARTS ROW 1 ---
            c1, c2 = st.columns([1, 1])
            
            with c1:
                st.subheader("🎨 SECTOR ALLOCATION")
                df_holdings['DisplaySector'] = df_holdings['Sector'].apply(lambda x: x if x and x != "Unknown" else "Other")
                
                fig_sec = px.sunburst(
                    df_holdings, 
                    path=['DisplaySector', 'Symbol'], 
                    values='CurVal',
                    color='DisplaySector', 
                    color_discrete_sequence=px.colors.qualitative.Prism 
                )
                fig_sec.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=400, paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#eee', family='Rajdhani'))
                st.plotly_chart(fig_sec, width="stretch", config={'displayModeBar': False})
                
            with c2:
                st.subheader("🔥 PERFORMANCE HEATMAP")
                fig_tree = px.treemap(
                    df_holdings,
                    path=[px.Constant("HOLDINGS"), 'Symbol'],
                    values='Invested',
                    color='P&L%',
                    color_continuous_scale='RdYlGn', 
                    range_color=[-10, 10], 
                    color_continuous_midpoint=0,
                    hover_data=['Qty', 'Avg', 'CMP', 'P&L']
                )
                fig_tree.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=400, paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#eee', family='Rajdhani'))
                st.plotly_chart(fig_tree, width="stretch", config={'displayModeBar': False})
    
            # --- DETAILED TABLE ---
            st.subheader("📋 HOLDINGS INSPECTOR")
            
            view_df = df_holdings[['Symbol', 'Qty', 'Avg', 'CMP', 'Invested', 'CurVal', 'P&L', 'P&L%', 'Sector', 'StopLoss', 'RiskAmt', 'Quality']].copy()
            # Fix ArrowTypeError by ensuring Quality is int
            view_df['Quality'] = pd.to_numeric(view_df['Quality'], errors='coerce').fillna(0).astype(int)
            view_df.reset_index(drop=True, inplace=True)
            view_df.index = view_df.index + 1
            view_df.index.name = 'Sr#'
            
            status = []
            for i, r in view_df.iterrows():
                if r['StopLoss'] <= 0: status.append("⚠️ NO SL")
                elif r['CMP'] < r['StopLoss']: status.append("❌ BREACHED")
                elif r['CMP'] < r['StopLoss'] * 1.02: status.append("⚠️ NEAR SL")
                else: status.append("✅ SAFE")
            view_df['Status'] = status
    
            # Table Header Alignment CSS
            st.markdown("""<style>[data-testid="stDataFrame"] th > div { font-weight: 800 !important; color: #00F260 !important; font-family: 'Rajdhani'; }</style>""", unsafe_allow_html=True)

            st.dataframe(
                view_df.style.map(color_pnl, subset=['P&L', 'P&L%'])
                       .format({
                           'Avg': '₹{:.2f}', 'CMP': '₹{:.2f}', 
                           'Invested': lambda x: format_inr(x), 'CurVal': lambda x: format_inr(x), 
                           'P&L': lambda x: format_inr(x), 'P&L%': '{:.2f}%',
                           'StopLoss': '₹{:.2f}', 'RiskAmt': lambda x: format_inr(x)
                       }),
                width="stretch"
            )

    # --- TAB 2: PERFORMANCE ANALYTICS ---
    elif active_tab == "📈 PERFORMANCE":
        st.subheader("📈 REALIZED P&L ANALYTICS (FY25-26)")
        
        # Consolidation: Combined API + HTML Sources
        # source_df is already prepared in main initialization
        
        if source_df.empty:
            st.info("No realized trade data found in Dhan API history.")
        else:
            # Process FIFO with Fallbacks
            completed_df = process_trade_history(source_df, journal_df=journal_df, holdings_df=df_holdings)
            
            if completed_df.empty:
                st.warning("Waiting for completed 'Buy+Sell' pairs to calculate realized performance.")
            else:
                # Better Sector Mapping: Use processed_data logic
                # Create a lookup from current holdings if possible, otherwise fuzzy match
                sector_map = {}
                if df_holdings is not None:
                    sector_map = dict(zip(df_holdings['Symbol'], df_holdings['Sector']))
                
                completed_df['Sector'] = completed_df['Symbol'].apply(lambda s: identify_sector(s, sector_map))
                
                # Metrics logic - Pure API Source
                api_realized = completed_df['Realized P&L'].sum()
                
                win_count = len(completed_df[completed_df['Realized P&L'] > 0])
                total_t = len(completed_df)
                win_rate = (win_count / total_t * 100) if total_t > 0 else 0
                gross_p = completed_df[completed_df['Realized P&L'] > 0]['Realized P&L'].sum()
                gross_l = abs(completed_df[completed_df['Realized P&L'] < 0]['Realized P&L'].sum())
                profit_factor = (gross_p / gross_l) if gross_l > 0 else (gross_p if gross_p > 0 else 0)
                
                # Risk Metrics Calculations
                # 1. Max Drawdown (₹)
                completed_df_chron = completed_df.sort_values('Exit Date').copy()
                completed_df_chron['CumulativeP&L'] = completed_df_chron['Realized P&L'].cumsum()
                running_max = completed_df_chron['CumulativeP&L'].cummax()
                drawdown = running_max - completed_df_chron['CumulativeP&L']
                max_drawdown = drawdown.max() if not drawdown.empty else 0.0

                # 2. Daily VaR (95%)
                daily_pnl = completed_df_chron.groupby('Exit Date')['Realized P&L'].sum()
                var_95 = np.percentile(daily_pnl, 5) if len(daily_pnl) > 0 else 0.0
                daily_var_val = abs(var_95) if var_95 < 0 else 0.0
                
                # 3 & 4. Sharpe & Sortino (Trade Basis)
                trade_roi = completed_df['ROI%'] / 100.0  # Decimal
                mean_roi = trade_roi.mean()
                std_roi = trade_roi.std()
                
                # Approximate Sharpe per trade (un-annualized)
                sharpe_ratio = (mean_roi / std_roi) if std_roi and std_roi > 0 else 0.0
                
                # Sortino per trade
                negative_roi = trade_roi[trade_roi < 0]
                std_neg_roi = negative_roi.std()
                # If there's only 1 losing trade, std is NaN, use 0 or something small
                if pd.isna(std_neg_roi) or std_neg_roi == 0:
                    sortino_ratio = sharpe_ratio  # Fallback
                else:
                    sortino_ratio = (mean_roi / std_neg_roi)
                
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("REALIZED P&L", format_inr(api_realized), 
                          help="Total P&L calculated via FIFO (Dhan API since Jan 2023). Incl. Journal fallbacks for older buys.")
                k2.metric("WIN RATE", f"{win_rate:.1f}%", f"{win_count} Wins")
                k3.metric("PROFIT FACTOR", f"{profit_factor:.2f}x", help="Ratio of Gross Profit to Gross Loss.")
                k4.metric("TOTAL TRADES", f"{total_t}", help="Count of completed Buy/Sell pairs.")

                st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
                
                q1, q2, q3, q4 = st.columns(4)
                q1.metric("SHARPE RATIO", f"{sharpe_ratio:.2f}", help="Return per unit of total risk (Trade basis).")
                q2.metric("SORTINO RATIO", f"{sortino_ratio:.2f}", help="Return per unit of downside risk (Trade basis).")
                q3.metric("MAX DRAWDOWN", format_inr(-max_drawdown) if max_drawdown > 0 else "₹0", help="Largest peak-to-trough drop in realized P&L.")
                q4.metric("DAILY VaR (95%)", format_inr(-daily_var_val) if daily_var_val > 0 else "₹0", help="Estimated max daily loss with 95% confidence based on historical exits.")
                
                # --- AI MENTOR SECTION ---
                st.markdown("---")
                m_col1, m_col2 = st.columns([1, 4])
                with m_col1:
                    st.markdown("### 🧠 AI MENTOR")
                    if st.button("📓 POST-TRADE AUTOPSY", use_container_width=True, type="primary"):
                        with st.spinner("Commander Mentor is analyzing your trade behavioral patterns..."):
                            import ai_mentor_engine
                            report = ai_mentor_engine.get_mentor_report(force_refresh=False)
                            st.session_state.mentor_report = report
                    
                    if st.button("🔄 FORCE NEW ANALYSIS", use_container_width=True, help="Bypasses cache for a tactical, detailed autopsy."):
                        with st.spinner("Executing detailed surgical audit..."):
                            import ai_mentor_engine
                            report = ai_mentor_engine.get_mentor_report(force_refresh=True)
                            st.session_state.mentor_report = report
                            st.rerun()
                
                if 'mentor_report' in st.session_state:
                    with st.container(border=True):
                        st.markdown(st.session_state.mentor_report)
                        if st.button("🗑️ Clear Report"):
                            del st.session_state.mentor_report
                            st.rerun()
                
                st.markdown("---")

                # GRAPHS ROW
                g1, g2 = st.columns([2, 1])
                
                with g1:
                    st.subheader("🚀 NET EQUITY CURVE (REALIZED)")
                    completed_df = completed_df.sort_values('Exit Date')
                    completed_df['CumulativeP&L'] = completed_df['Realized P&L'].cumsum()
                    
                    fig_curve = px.area(
                        completed_df, 
                        x='Exit Date', 
                        y='CumulativeP&L',
                        labels={'CumulativeP&L': 'Realized P&L (₹)'},
                        color_discrete_sequence=['#00F260'] if api_realized >= 0 else ['#FF5252']
                    )
                    fig_curve.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(255,255,255,0.05)',
                        font=dict(color='#eee', family='Rajdhani'), height=400,
                        margin=dict(t=10, l=10, r=10, b=10)
                    )
                    st.plotly_chart(fig_curve, width="stretch")

                with g2:
                    st.subheader("🎯 WIN/LOSS MIX")
                    pie_df = pd.DataFrame({
                        'Status': ['Winners', 'Losers'],
                        'Count': [win_count, total_t - win_count]
                    })
                    fig_pie = px.pie(
                        pie_df,
                        names='Status',
                        values='Count',
                        hole=0.5,
                        color='Status',
                        color_discrete_map={'Winners': '#00F260', 'Losers': '#FF5252'}
                    )
                    fig_pie.update_layout(height=350, paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#eee', family='Rajdhani'), showlegend=False)
                    st.plotly_chart(fig_pie, width="stretch")

                st.markdown("---")
                
                # SECTOR & MONTHLY
                s1, s2 = st.columns(2)
                
                with s1:
                    st.subheader("🏗️ P&L BY SECTOR")
                    sec_stats = completed_df.groupby('Sector')['Realized P&L'].sum().reset_index().sort_values('Realized P&L')
                    fig_sec_b = px.bar(sec_stats, y='Sector', x='Realized P&L', orientation='h', color='Realized P&L', color_continuous_scale='RdYlGn')
                    fig_sec_b.update_layout(height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#eee', family='Rajdhani'))
                    st.plotly_chart(fig_sec_b, width="stretch")
                    
                with s2:
                    st.subheader("🗓️ MONTHLY PERFORMANCE")
                    # Robust chronological sorting
                    completed_df['Exit Date DT'] = pd.to_datetime(completed_df['Exit Date'])
                    m_pnl = completed_df.groupby(pd.Grouper(key='Exit Date DT', freq='ME'))['Realized P&L'].sum().reset_index()
                    m_pnl = m_pnl.sort_values('Exit Date DT') # Ensure chronological
                    m_pnl['MonthLabel'] = m_pnl['Exit Date DT'].dt.strftime('%b %Y')
                    
                    fig_m = px.bar(
                        m_pnl, 
                        x='MonthLabel', 
                        y='Realized P&L', 
                        color='Realized P&L', 
                        color_continuous_scale='RdYlGn'
                    )
                    fig_m.update_layout(height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#eee', family='Rajdhani'))
                    st.plotly_chart(fig_m, width="stretch")

    # --- TAB 3: TRADE LOGS ---
    elif active_tab == "📜 TRADE LOGS":
        st.subheader("📜 DETAILED TRADE JOURNAL")
        # source_df is already prepared in main initialization
        if not source_df.empty:
            df_log = process_trade_history(source_df, journal_df=journal_df, holdings_df=df_holdings)
            
            # --- P&L AUDITOR (Warning for missing entry prices) ---
            unmatched = df_log[df_log['Matched'].str.contains('ERROR', na=False)]
            if not unmatched.empty:
                st.error(f"⚠️ FOUND {len(unmatched)} TRADES WITH MISSING ENTRY DATA")
                st.warning("These trades are skewing your Realized P&L. Please add their entry prices to your Journal.")
                with st.expander("🔍 VIEW UNMATCHED TRADES"):
                    st.dataframe(unmatched[['Symbol', 'Qty', 'Exit Date', 'Exit Price', 'Matched']], width="stretch")
                st.markdown("---")

            if not df_log.empty:
                df_log = df_log.sort_values('Exit Date', ascending=False)
                # Fix ArrowTypeError for mixed date/string types
                df_log['Entry Date'] = df_log['Entry Date'].astype(str)
                df_log.reset_index(drop=True, inplace=True)
                df_log.index = df_log.index + 1
                
                st.dataframe(
                    df_log.style.format({'Entry Price': '₹{:.2f}', 'Exit Price': '₹{:.2f}', 'Realized P&L': lambda x: format_inr(x), 'ROI%': '{:.2f}%'})
                          .map(color_pnl, subset=['Realized P&L', 'ROI%']),
                    width="stretch"
                )
        else:
            st.info("No trade data available from Dhan API.")

if __name__ == "__main__":
    main()
