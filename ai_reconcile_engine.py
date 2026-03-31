import pandas as pd
import os
import sqlite3
import datetime
import json
from dhanhq import dhanhq
from dotenv import load_dotenv
from dhan_auth import ensure_valid_token
from bs4 import BeautifulSoup
import quopri
from email import message_from_file

# Load Config
load_dotenv(override=True)
API_KEY = os.getenv("DHAN_ACCESS_TOKEN")
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DB_FILE = "trade_journal_v6.db"

def normalize_symbol(symbol):
    """Strips standard noise (Ltd, Limited, NSE, BSE, etc.) for robust matching."""
    if not symbol or pd.isna(symbol): return "UNKNOWN"
    s = str(symbol).strip().upper()
    # Remove exchanges
    s = s.replace("| NSE", "").replace("| BSE", "").replace("NSE:", "").replace("BSE:", "").replace(" NSE", "").replace(" BSE", "")
    s = s.replace("-EQ", "").replace("-BE", "")
    
    # Specific ETF/Stock Map
    sym_map = {
        'HDFC NIFTY NEXT 50 ETF': 'HDFCNEXT50',
        'HDFC NIFTY SMALLCAP 250 ETF': 'HDFCSML250',
        'HDFC NIFTY MIDCAP 150 ETF': 'HDFCMID150',
        'HDFC NIFTY 100 LOW VOLATILITY 30 ETF': 'HDFCLOWVOL',
        'HDFC NIFTY 50 ETF': 'HDFCNIFTY',
        'ICICI PRU NIFTY CONSUMPTION ETF': 'CONSUMIETF',
        'ICICI PRU NIFTY INFRASTRUCTURE ETF': 'INFRAIETF',
        'ICICI PRU NIFTY METAL ETF': 'METALIETF',
        'ICICI PRU NIFTY FMCG ETF': 'FMCGBEES',
        'ICICI PRU NIFTY 200 QUALITY 30 ETF': 'QUALITYIETF',
        'ICICI PRU NIFTY FIN SVC EX-BANK ETF': 'FINIETF',
        'KOTAK NIFTY ALPHA 50 ETF': 'ALPHAETF',
        'ADITYA BIRLA NIFTY 200 MOMENTUM 30 ETF': 'MOM30IETF',
        'MIRAE AST NIFTY SMALLCAP 250 MQ 100 ETF': 'MIDCAPETF',
        'MIRAE ASSET NIFTY SMALLCAP 250 Q100 ETF': 'MIDCAPETF',
        'HDFC NIFTY SMALL CAP 250 ETF': 'HDFCSML250',
        'ICICI PRU NIFTY FIN. SERVICES EX-BANK ET': 'FINIETF',
        'ICICI PRU NIFTY FIN SVC EX-BANK ETF': 'FINIETF',
        'ICICI PRU SILVER ETF': 'SILVERIETF',
        'ICICI PRU GOLD ETF': 'GOLDIETF',
        'NIPPON NIFTY BANK ETF (BANKBEES)': 'BANKBEES',
        'NIPPON NIFTY IT ETF (ITBEES)': 'ITBEES',
        'DATA PATTERNS': 'DATAPATTNS',
        'DATA PATTERNS (INDIA)': 'DATAPATTNS',
        'FEDERAL BANK': 'FEDERALBNK',
        'COAL INDIA': 'COALINDIA',
        'CITY UNION BANK': 'CUB',
        'HINDUSTAN COPPER': 'HINDCOPPER',
        'RELIANCE INDUSTRIES': 'RELIANCE',
        'LARSEN & TOUBRO': 'LT',
        'LARSEN AND TOUBRO': 'LT',
        'MAHINDRA & MAHINDRA': 'M&M',
        'TATA CONSULTANCY SERVICES': 'TCS',
        'TATA MOTORS': 'TATAMOTORS',
        'STATE BANK OF INDIA': 'SBIN',
        'BHARTI AIRTEL': 'BHARTIARTL',
        'ADANI ENTERPRISES': 'ADANIENT',
        'ADANI PORTS AND SECIAL ECONOMIC ZONE': 'ADANIPORTS',
        'HDFC BANK': 'HDFCBANK',
        'ICICI BANK': 'ICICIBANK',
        'AXIS BANK': 'AXISBANK',
        'KOTAK MAHINDRA BANK': 'KOTAKBANK',
        'HCL TECHNOLOGIES': 'HCLTECH',
        'AIA ENGINEERING': 'AIAENG',
        'HINDUSTAN UNILEVER': 'HINDUNILVR'
    }
    if s in sym_map: return sym_map[s]
    
    # Remove legal suffixes
    for suffix in [" LIMITED", " LTD", " IND", " IN", " CORP", " CORPORATION", " INDUSTRIES", " INDS", " ENTERPRISES", " ENTP", " SOLUTIONS", " SOLNS", " SERVICES", " SVCS", " INDIA", " (INDIA)"]:
        if s.endswith(suffix):
            s = s[:-len(suffix)].strip()
            
    # Clean characters
    s = s.replace(".", "").replace(",", "").replace(" ", "").strip()
    return s

def get_symbol_sector(ticker):
    """Helper to get sector from local DB."""
    try:
        t = str(ticker).strip().upper()
        if not t.startswith("NSE:"): t = "NSE:" + t
        if not os.path.exists("sector_db.json"): return "Other"
        with open("sector_db.json", "r") as f:
            db = json.load(f)
        return db.get(t, "Other").replace("NSE:", "").replace("CNX", "")
    except: return "Other"

def fetch_trade_history():
    tok = ensure_valid_token()
    cid = os.getenv("DHAN_CLIENT_ID")
    if not tok or not cid: return pd.DataFrame()
    try:
        dhan = dhanhq(client_id=cid, access_token=tok)
        from_date = '2023-01-01'
        to_date = datetime.datetime.now().strftime('%Y-%m-%d')
        all_trades = []
        page = 0
        while True:
            resp = dhan.get_trade_history(from_date=from_date, to_date=to_date, page_number=page)
            if resp['status'] == 'success' and resp['data']:
                all_trades.extend(resp['data'])
                page += 1
            else: break
        if not all_trades: return pd.DataFrame()
        df = pd.DataFrame(all_trades)
        df['Symbol'] = df['tradingSymbol'].fillna(df['customSymbol']).fillna(df['symbol'])
        df['exchangeTime'] = pd.to_datetime(df['exchangeTime'])
        return df.sort_values('exchangeTime')
    except: return pd.DataFrame()

def parse_html_trades():
    # Support both .html and .mhtml
    files = [f for f in os.listdir(".") if (f.lower().endswith(".html") or f.lower().endswith(".mhtml")) and ("trades" in f.lower() or "journal" in f.lower())]
    all_parsed = []
    for path in files:
        try:
            html_content = ""
            if path.lower().endswith(".mhtml"):
                with open(path, "r", encoding='utf-8', errors='ignore') as f:
                    msg = message_from_file(f)
                for part in msg.walk():
                    if part.get_content_type() == "text/html":
                        payload = part.get_payload()
                        if part.get("Content-Transfer-Encoding") == "quoted-printable":
                            html_content = quopri.decodestring(payload).decode('utf-8', errors='ignore')
                        else:
                            html_content = payload
                        break
            else:
                with open(path, "r", encoding='utf-8', errors='ignore') as f:
                    html_content = f.read()

            if not html_content: continue
            
            soup = BeautifulSoup(html_content, 'html.parser')
            table = soup.find('table')
            if not table: continue
            
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) < 6: continue
                # Date is usually in the first cell
                dt_str = cells[0].get_text(strip=True)
                sym_cell = cells[1]
                img = sym_cell.find('img')
                txn_type = "UNKNOWN"
                if img and img.get('src'):
                    src = img.get('src').lower()
                    if 'buy.svg' in src: txn_type = "BUY"
                    elif 'sell.svg' in src: txn_type = "SELL"
                
                # Cleanup symbol text
                sym = " ".join(sym_cell.get_text(separator=" ", strip=True).replace("|", "").replace("NSE", "").replace("BSE", "").split())
                
                try: qty = float(cells[4].get_text(strip=True).replace(",", ""))
                except: qty = 0
                try: price = float(cells[5].get_text(strip=True).replace(",", ""))
                except: price = 0.0
                
                dt = pd.to_datetime(dt_str, errors='coerce')
                if pd.notna(dt):
                    all_parsed.append({'exchangeTime': dt, 'Symbol': sym, 'transactionType': txn_type, 'tradedQuantity': qty, 'tradedPrice': price})
        except Exception as e:
            print(f"Error parsing trade file {path}: {e}")
            continue
    return pd.DataFrame(all_parsed)

def parse_global_transaction_report_excel():
    xl_files = [f for f in os.listdir(".") if f.lower().endswith(".xlsx") and "globaltransction" in f.lower() and not f.startswith("~$")]
    all_trades = []
    for path in xl_files:
        try:
            # Header is usually at Row 4
            df = pd.read_excel(path, header=4)
            df.columns = [str(c).strip() for c in df.columns]
            col_date = 'Date' if 'Date' in df.columns else df.columns[0]
            col_scrip = 'Scrip Name' if 'Scrip Name' in df.columns else df.columns[1]
            col_buy_qty = 'Buy Qty.' if 'Buy Qty.' in df.columns else 'Unnamed: 4'
            col_buy_val = 'Buy Value' if 'Buy Value' in df.columns else 'Unnamed: 5'
            col_sell_qty = 'Sell Qty.' if 'Sell Qty.' in df.columns else 'Unnamed: 6'
            col_sell_val = 'Sell Value' if 'Sell Value' in df.columns else 'Unnamed: 7'

            for _, row in df.dropna(subset=[col_date, col_scrip]).iterrows():
                if str(row[col_date]).lower() == 'date': continue
                dt = pd.to_datetime(row[col_date], errors='coerce')
                if pd.isna(dt): continue
                scrip = str(row[col_scrip]).replace("NSE", "").replace("BSE", "").strip()
                scrip = " ".join(scrip.split())
                
                b_qty = float(row.get(col_buy_qty, 0))
                if b_qty > 0:
                    all_trades.append({'exchangeTime': dt, 'Symbol': scrip, 'transactionType': 'BUY', 'tradedQuantity': b_qty, 'tradedPrice': float(row.get(col_buy_val, 0))/b_qty})
                
                s_qty = float(row.get(col_sell_qty, 0))
                if s_qty > 0:
                    all_trades.append({'exchangeTime': dt, 'Symbol': scrip, 'transactionType': 'SELL', 'tradedQuantity': s_qty, 'tradedPrice': float(row.get(col_sell_val, 0))/s_qty})
        except: continue
    return pd.DataFrame(all_trades)

def process_trade_history(trade_df, journal_df=None):
    """FIFO Matching with Fallbacks."""
    if trade_df.empty: return pd.DataFrame()
    df = trade_df.sort_values('exchangeTime')
    inventory = {}
    completed = []
    
    for _, row in df.iterrows():
        isin = row.get('isin', '')
        sym = row.get('Symbol', 'Unknown')
        key = isin if isin and str(isin) != 'nan' else sym
        qty, price, date = row['tradedQuantity'], row['tradedPrice'], row['exchangeTime']
        txn_type = str(row.get('transactionType', '')).upper()
        
        if key not in inventory: inventory[key] = []
        if txn_type == 'BUY':
            inventory[key].append({'qty': qty, 'price': price, 'date': date})
        elif txn_type == 'SELL':
            rem = qty
            while rem > 0 and inventory[key]:
                buy = inventory[key][0]
                m = min(rem, buy['qty'])
                completed.append({
                    'Symbol': sym, 'Qty': m, 'Entry Date': buy['date'].date(),
                    'Entry Price': buy['price'], 'Exit Date': date.date(), 'Exit Price': price,
                    'Realized P&L': (price - buy['price']) * m
                })
                rem -= m
                buy['qty'] -= m
                if buy['qty'] <= 0: inventory[key].pop(0)
            
            # Carry Forward / Journal Fallback
            if rem > 0 and journal_df is not None:
                j_match = journal_df[journal_df['symbol'].apply(normalize_symbol) == normalize_symbol(sym)]
                if not j_match.empty:
                    ej_price = j_match.iloc[0].get('entry_price', 0)
                    if ej_price > 0:
                        completed.append({
                            'Symbol': sym, 'Qty': rem, 'Entry Date': 'PRE-FETCH',
                            'Entry Price': ej_price, 'Exit Date': date.date(), 'Exit Price': price,
                            'Realized P&L': (price - ej_price) * rem
                        })
                        rem = 0
            
            if rem > 0:
                completed.append({
                    'Symbol': sym, 'Qty': rem, 'Entry Date': 'UNKNOWN',
                    'Entry Price': 0, 'Exit Date': date.date(), 'Exit Price': price,
                    'Realized P&L': 0
                })
    return pd.DataFrame(completed)

def sync_journal_with_dhan(target_symbols=None):
    """
    Primary API-driven reconciliation for the Journal.
    If target_symbols is provided, it attempts to specifically sync those.
    """
    if not os.path.exists(DB_FILE): return 0
    
    # 1. Fetch Latest Trade History from Dhan API
    api_trades = fetch_trade_history()
    if api_trades.empty:
        return 0
        
    # 2. Match & Process FIFO
    conn = sqlite3.connect(DB_FILE)
    j_df = pd.read_sql("SELECT * FROM journal", conn)
    
    api_trades['NormSym'] = api_trades['Symbol'].apply(normalize_symbol)
    completed_trades = process_trade_history(api_trades, journal_df=j_df)
    
    if completed_trades.empty:
        conn.close()
        return 0
        
    # 3. Update Journal
    reconciled_count = 0
    cursor = conn.cursor()
    
    # Filter for target symbols if provided
    symbols_to_check = target_symbols if target_symbols else j_df['symbol'].tolist()
    
    for sym in symbols_to_check:
        norm = normalize_symbol(sym)
        match = completed_trades[completed_trades['Symbol'].apply(normalize_symbol) == norm]
        
        if not match.empty:
            m = match.iloc[-1] # Primary target is the latest exit
            exit_price = float(m['Exit Price'])
            exit_date = str(m['Exit Date'])
            
            # Update Database — ONLY update rows already marked CLOSED (by stale-trade detector)
            # NEVER force-close an OPEN position here
            cursor.execute("""
                UPDATE journal 
                SET exit_price = ?, exit_date = ?
                WHERE symbol = ? AND status = 'CLOSED' AND (exit_price IS NULL OR exit_price = 0 OR exit_price = '')
            """, (exit_price, exit_date, sym))
            if cursor.rowcount > 0:
                reconciled_count += 1
                
    conn.commit()
    conn.close()
    return reconciled_count

def reconcile_journal_exit_prices():
    """Matches trades in journal with real trade logs for Exit Details & Sector."""
    if not os.path.exists(DB_FILE): return 0
    conn = sqlite3.connect(DB_FILE)
    j_df = pd.read_sql("SELECT * FROM journal", conn)
    
    # 1. Build Master Trade Log (with priority)
    api = fetch_trade_history()
    html = parse_html_trades()
    excel = parse_global_transaction_report_excel()
    
    source = pd.concat([api, html, excel])
    if source.empty: 
        conn.close()
        return 0
        
    source['NormSym'] = source['Symbol'].apply(normalize_symbol)
    source['match_date'] = pd.to_datetime(source['exchangeTime']).dt.date
    # Deduplicate priority: API > HTML > Excel
    source = source.drop_duplicates(subset=['match_date', 'NormSym', 'transactionType', 'tradedQuantity'], keep='first')
    
    # 2. Process FIFO
    master_completed = process_trade_history(source, journal_df=j_df)
    
    # 3. Handle Updates
    reconciled_count = 0
    cursor = conn.cursor()
    
    for idx, row in j_df.iterrows():
        sym = row['symbol']
        norm = normalize_symbol(sym)
        match = master_completed[master_completed['Symbol'].apply(normalize_symbol) == norm]
        
        if not match.empty:
            # SKIP rows that are currently OPEN — never force-close active holdings
            if str(row.get('status', '')).upper() == 'OPEN':
                continue
                
            m = match.iloc[-1] # Latest trade
            exit_price = float(m['Exit Price'])
            exit_date = str(m['Exit Date'])
            
            # Inject Sector if missing or unassigned
            current_sector = row.get('sector', '')
            if not current_sector or current_sector in ['Unknown', 'Other', 'Unassigned', '']:
                new_sector = get_symbol_sector(sym)
            else:
                new_sector = current_sector
            
            cursor.execute("""
                UPDATE journal 
                SET exit_price = ?, exit_date = ?, sector = ?
                WHERE symbol = ? AND status = 'CLOSED'
            """, (exit_price, exit_date, new_sector, sym))
            reconciled_count += 1
            
    conn.commit()
    conn.close()
    return reconciled_count

def discover_missing_trades():
    """Identifies trades in logs that are not present in the journal at all."""
    if not os.path.exists(DB_FILE): return []
    conn = sqlite3.connect(DB_FILE)
    j_df = pd.read_sql("SELECT symbol FROM journal", conn)
    journal_syms = set(j_df['symbol'].apply(normalize_symbol).unique())
    conn.close()
    
    api = fetch_trade_history()
    html = parse_html_trades()
    excel = parse_global_transaction_report_excel()
    source = pd.concat([api, html, excel])
    if source.empty: return []
    
    source['NormSym'] = source['Symbol'].apply(normalize_symbol)
    source['match_date'] = pd.to_datetime(source['exchangeTime']).dt.date
    source = source.drop_duplicates(subset=['match_date', 'NormSym', 'transactionType', 'tradedQuantity'], keep='first')
    
    master_completed = process_trade_history(source)
    if master_completed.empty: return []
    
    missing = []
    for _, row in master_completed.iterrows():
        norm = normalize_symbol(row['Symbol'])
        if norm not in journal_syms:
            missing.append({
                'Symbol': norm,
                'Name': row['Symbol'],
                'ExitPrice': float(row['Exit Price']),
                'Pnl': float(row['Realized P&L']),
                'ExitDate': str(row['Exit Date']),
                'EntryPrice': float(row['Entry Price']),
                'Qty': float(row['Qty'])
            })
    return missing

def backfill_trades(missing_list):
    if not missing_list or not os.path.exists(DB_FILE): return 0
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    created = 0
    for item in missing_list:
        try:
            sym = item['Symbol']
            cursor.execute("SELECT symbol FROM journal WHERE symbol = ?", (sym,))
            if cursor.fetchone(): continue
            
            sector = get_symbol_sector(sym)
            cursor.execute("""
                INSERT INTO journal (
                    symbol, status, exit_price, exit_date, 
                    rationale, trade_type, quantity, buy_price, sector
                ) VALUES (?, 'CLOSED', ?, ?, 'Backfilled from logs.', 'Investment', ?, ?, ?)
            """, (sym, item['ExitPrice'], item['ExitDate'], item['Qty'], item['EntryPrice'], sector))
            created += 1
        except: continue
    conn.commit()
    conn.close()
    return created

if __name__ == "__main__":
    count = reconcile_journal_exit_prices()
    print(f"Reconciled {count} trades.")
