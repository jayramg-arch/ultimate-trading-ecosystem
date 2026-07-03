import streamlit as st
import pandas as pd
from dhanhq import dhanhq
try:
    from dhanhq import DhanContext
except ImportError:
    DhanContext = None
import sqlite3
import os
from datetime import datetime, date, timedelta
import yfinance as yf
import io
import plotly.express as px
import sys
import subprocess
import time
from dhan_auth import ensure_valid_token
from ai_commander_engine import get_commander_response
from ai_risk_manager import validate_risk_hygiene, analyze_sector_concentration, generate_post_mortem_summary, get_atr
from ai_grading_engine import get_weinstein_score
from ai_market_intelligence import generate_breadth_brief
from ai_vision_manager import analyze_chart_screenshot

# Load environment variables first to ensure credentials are available
from dotenv import load_dotenv
load_dotenv(override=True)

# Ensure valid Dhan token before proceeding
@st.cache_resource(ttl=3600)
def check_auth_cached():
    try:
        print("[Auth] Checking Dhan API Token...")
        return ensure_valid_token()
    except Exception as e:
        print(f"[Auth] Warning: Auto-token refresh failed: {e}")
        return None

check_auth_cached()

# - 1. CONFIGURATION -
load_dotenv(override=True)

API_KEY = os.getenv("DHAN_ACCESS_TOKEN")
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DB_FILE = "trade_journal_v6.db"
DEFAULT_SECTOR = "NSE:CNX500" 
SCREENSHOT_DIR = "trade_screenshots"

# Force Install xlsxwriter
try:
    import xlsxwriter
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "xlsxwriter"])
    import xlsxwriter

if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

# Initialize Dhan
try:
    if CLIENT_ID and API_KEY:
        dhan = dhanhq(DhanContext(CLIENT_ID, API_KEY)) if DhanContext else dhanhq(CLIENT_ID, API_KEY)
    else:
        st.error("❌ Credentials Missing in .env file!")
        dhan = None
except Exception as e:
    st.error(f"❌ Connection Error: {e}")
    dhan = None

# - 2. HELPER FUNCTIONS -

def clean_symbol(symbol):
    """Clean Dhan symbols by stripping suffixes and mapping indices."""
    if symbol is None or pd.isna(symbol): return ""
    s = str(symbol).strip().upper().replace("NSE:", "").replace("BSE:", "")
    if s == "NIFTY": return "^NSEI"
    if s == "BANKNIFTY" or s == "NIFTYBANK": return "^NSEBANK"
    for suffix in ['-EQ', '-BE', '-SM', '-ST', '-BZ']:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    return s

def format_inr(number):
    try:
        if number is None or pd.isna(number): return "0.00"
        val = float(number)
        s, *d = str("{:.2f}".format(val)).partition(".")
        r = ",".join([s[x-2:x] for x in range(-3, -len(s), -2)][::-1] + [s[-3:]])
        return "".join([r] + d)
    except:
        return str(number)

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

def save_screenshot(uploaded_file, symbol):
    if uploaded_file is None: return None
    file_ext = uploaded_file.name.split('.')[-1]
    filename = f"{symbol}_{date.today()}.{file_ext}"
    file_path = os.path.join(SCREENSHOT_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

@st.cache_data(ttl=86400)
def get_sector(symbol):
    cleaned = clean_symbol(symbol)
    sym_upper = cleaned.upper()
    etf_map = {
    'BANKBEES': 'Financial Services',
        'BANKETF': 'Financial Services',
        'PSUBNKBEES': 'Public Sector Banks',
        'ITBEES': 'Technology',
        'PHARMABEES': 'Healthcare',
        'AUTOBEES': 'Automotive',
        'GOLDBEES': 'Commodities (Precious Metals)',
        'SILVERBEES': 'Commodities (Precious Metals)',
        'NIFTYBEES': 'Broad Market (Index)',
        'JUNIORBEES': 'Midcap (Index)',
        'SENSEXBEES': 'Broad Market (Index)',
        'LIQUIDBEES': 'Cash/Cash Equivalent',
        'INFRA': 'Infrastructure',
        'COMMODITIES': 'Commodities',
        'CONSUMBEES': 'Consumer Goods',
        'MAFANG': 'Global Tech (US)',
        'HNGSNGBEES': 'Global (Hong Kong)',
        'MON100': 'Global Tech (US)',
        'METALIETF': 'Metal',
        'GOLDIETF': 'Gold',
        'SILVERIETF': 'Silver',
        'CONSUMIETF': 'Consumables',
        'HDFCNIFTY': 'Nifty',
        'HDFCSML250': 'SmallCap 250',
        'HDFCNEXT50': 'Next 50',
        'HDFCMID150': 'MidCap 150',
        'HDFCLOWVOL': 'Nifty100 Low Vol 30'    
    }
    for key, sector in etf_map.items():
        if key in sym_upper: return sector
    if 'ETF' in sym_upper or 'BEES' in sym_upper: return 'ETF (Unknown)'
    try:
        ticker = yf.Ticker(f"{cleaned}.NS")
        return ticker.info.get('sector', 'Unknown')
    except:
        return 'Unknown'

def calculate_ageing(entry_str, exit_str=None):
    try:
        start = datetime.strptime(str(entry_str)[:10], '%Y-%m-%d')
        end = datetime.strptime(str(exit_str)[:10], '%Y-%m-%d') if exit_str else datetime.now()
        return (end - start).days
    except: return 0

def get_fy(date_val):
    """Returns the Financial Year string (e.g., FY 2024-25) for a given date."""
    try:
        dt = pd.to_datetime(date_val)
        if dt.month >= 4:
            return f"{dt.year}-{str(dt.year+1)[2:]}"
        else:
            return f"{dt.year-1}-{str(dt.year)[2:]}"
    except: return "N/A"

# - 3. DATABASE ENGINE -

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            trade_type TEXT,
            stoploss REAL,
            target REAL,
            rationale TEXT,
            timeframe TEXT,
            entry_date TEXT,
            quantity REAL, 
            buy_price REAL,
            exit_date TEXT,
            exit_price REAL,
            exit_reason TEXT,
            status TEXT DEFAULT 'OPEN',
            sector TEXT,
            trade_quality TEXT,
            compromises TEXT,
            lessons TEXT,
            screenshot_path TEXT,
            ai_analysis TEXT,
            planned_rr TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def load_db():
    if not os.path.exists(DB_FILE): init_db()
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT * FROM journal", conn)
    conn.close()
    
    rename_map = {
        'symbol': 'Symbol', 'trade_type': 'Type', 'stoploss': 'StopLoss',
        'target': 'Target', 'rationale': 'Rationale', 'timeframe': 'Timeframe',
        'entry_date': 'EntryDate', 'quantity': 'Quantity', 'buy_price': 'BuyPrice',
        'exit_date': 'ExitDate', 'exit_price': 'ExitPrice',
        'exit_reason': 'ExitReason', 'status': 'Status', 'sector': 'Sector',
        'trade_quality': 'Quality', 'compromises': 'Compromises', 
        'lessons': 'Lessons', 'screenshot_path': 'Screenshot',
        'planned_rr': 'PlannedRR', 'ai_analysis': 'AI Analysis'
    }
    return df.rename(columns=rename_map)

def upsert_trade(entry):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    db_map = {
        'id': 'id',
        'Symbol': 'symbol', 'Type': 'trade_type', 'StopLoss': 'stoploss',
        'Target': 'target', 'Rationale': 'rationale', 'Timeframe': 'timeframe',
        'EntryDate': 'entry_date', 'Quantity': 'quantity', 'BuyPrice': 'buy_price',
        'ExitDate': 'exit_date', 'ExitPrice': 'exit_price',
        'ExitReason': 'exit_reason', 'Status': 'status', 'Sector': 'sector',
        'Quality': 'trade_quality', 'Compromises': 'compromises', 
        'Lessons': 'lessons', 'Screenshot': 'screenshot_path',
        'PlannedRR': 'planned_rr', 'AI Analysis': 'ai_analysis'
    }
    
    clean_entry = {db_map[k]: v for k, v in entry.items() if k in db_map}
    
    # Logic: If ID exists, update. If Status is OPEN and Symbol exists, update. Else Insert.
    target_id = clean_entry.get('id')
    
    if not target_id and clean_entry.get('symbol'):
        # ALWAYS check for existing OPEN row by symbol before inserting
        c.execute("SELECT id FROM journal WHERE symbol = ? AND status = 'OPEN' LIMIT 1", (clean_entry.get('symbol'),))
        row = c.fetchone()
        if row: target_id = row[0]

    keys = [k for k in clean_entry.keys() if k != 'id']
    
    if target_id:
        # UPDATE
        update_str = ", ".join([f"{k} = ?" for k in keys])
        values = [clean_entry[k] for k in keys] + [target_id]
        c.execute(f"UPDATE journal SET {update_str} WHERE id = ?", values)
    else:
        # INSERT
        placeholders = ", ".join(["?"] * len(keys))
        c.execute(f"INSERT INTO journal ({', '.join(keys)}) VALUES ({placeholders})", [clean_entry[k] for k in keys])
        
    conn.commit()
    conn.close()

def parse_rr(rr_str):
    # Parse "1:2" -> 2.0
    try:
        if not rr_str: return 0.0
        parts = rr_str.split(':')
        if len(parts) == 2:
            return float(parts[1])
        return float(rr_str)
    except: return 0.0

def migrate_db():
    if not os.path.exists(DB_FILE): return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        # 1. Check if PK is id or symbol
        c.execute("PRAGMA table_info(journal)")
        info = c.fetchall()
        pk_col = next((col[1] for col in info if col[5] == 1), None)
        
        if pk_col == 'symbol':
            print("Migrating: Changing PRIMARY KEY from symbol to id...")
            # Need to recreate table for PK change in SQLite
            c.execute("ALTER TABLE journal RENAME TO journal_old")
            init_db()
            
            # Copy data, let ID be generated
            c.execute("""
                INSERT INTO journal (
                    symbol, trade_type, stoploss, target, rationale, timeframe, 
                    entry_date, quantity, buy_price, exit_date, exit_price, 
                    exit_reason, status, sector, trade_quality, compromises, 
                    lessons, screenshot_path, ai_analysis, planned_rr
                )
                SELECT 
                    symbol, trade_type, stoploss, target, rationale, timeframe, 
                    entry_date, quantity, buy_price, exit_date, exit_price, 
                    exit_reason, status, sector, trade_quality, compromises, 
                    lessons, screenshot_path, 
                    (SELECT ai_analysis FROM journal_old WHERE symbol=jo.symbol),
                    (SELECT planned_rr FROM journal_old WHERE symbol=jo.symbol)
                FROM journal_old jo
            """)
            c.execute("DROP TABLE journal_old")
            print("Migration: PK changed to id successfully.")
        
        # 2. Check for other columns (existing logic)
        c.execute("PRAGMA table_info(journal)")
        cols = [row[1] for row in c.fetchall()]
        if 'planned_rr' not in cols:
            c.execute("ALTER TABLE journal ADD COLUMN planned_rr TEXT")
        if 'ai_analysis' not in cols:
            c.execute("ALTER TABLE journal ADD COLUMN ai_analysis TEXT")
            
    except Exception as e: 
        print(f"Migration error: {e}")
        conn.rollback()
        
    conn.commit()
    conn.close()

migrate_db()

if not os.path.exists(DB_FILE):
    init_db()

# - 4. DATA FETCHING -

# - 4. DATA FETCHING -

@st.cache_data(ttl=60)
def fetch_live_data():
    if dhan is None: return [], {}, 0.0, {}
    
    active_symbols = []
    live_data = {}
    id_map = {} # Map securityId -> tradingSymbol
    funds = 0.0

    try:
        f = dhan.get_fund_limits()
        if f['status'] == 'success':
            data = f['data']
            funds = float(data.get('availabelBalance', data.get('availableBalance', 0.0)))
    except: funds = 0.0

    def process(data):
        for item in data:
            sym = item.get('tradingSymbol')
            sec_id = str(item.get('securityId', ''))
            if sec_id: id_map[sec_id] = sym
            
            qty = item.get('totalQty') or item.get('netQty')
            if qty == 0: continue
            ltp = item.get('lastTradedPrice') or item.get('ltp') or item.get('lastPrice') or item.get('close') or 0.0
            buy_avg = item.get('avgCostPrice') or item.get('buyAvg') or 0.0
            
            active_symbols.append(sym)
            live_data[sym] = {'Symbol': sym, 'Quantity': abs(qty), 'BuyPrice': buy_avg, 'LTP': ltp}

    try:
        h = dhan.get_holdings()
        if h['status'] == 'success': process(h['data'])
    except: pass
    
    try:
        p = dhan.get_positions()
        if p['status'] == 'success': process(p['data'])
    except: pass
    
    return active_symbols, live_data, funds, id_map

def sync_history_data(days=90, id_map=None):
    if dhan is None or not id_map: return {}
    
    to_date = str(date.today())
    from_date = str(date.today() - timedelta(days=days))
    
    trade_map = {} # Symbol -> Earliest Date
    
    try:
        # Fetch up to 300 pages (~7500 trades) for deep seek
        for page in range(0, 300):
            h = dhan.get_trade_history(from_date=from_date, to_date=to_date, page_number=page)
            if h['status'] == 'success':
                data = h['data']
                if not data: break 
                
                for t in data:
                    if t['transactionType'] == 'BUY':
                        sec_id = str(t.get('securityId', ''))
                        sym = id_map.get(sec_id)
                        
                        if sym:
                            ts = t.get('exchangeTime', '')
                            # Format: 2026-02-09T13...
                            if 'T' in ts:
                                dt = ts.split('T')[0]
                                
                                # Track earliest BUY date
                                if sym not in trade_map:
                                    trade_map[sym] = dt
                                else:
                                    if dt < trade_map[sym]:
                                        trade_map[sym] = dt
            else:
                break
    except Exception as e:
        print(f"History Sync Error: {e}")
        
    return trade_map

# - 5. DASHBOARD UI -

# Page config removed (handled by router)

st.markdown("""<style>
:root { -primary-color:#238636; -background-color:#0b1622; -secondary-background-color:#0d1b2a; -text-color:#c9d1d9; }

/* APP SHELL */
.stApp { background:#0b1622!important; font-family:'Inter',sans-serif!important; color:#c9d1d9!important; }
.block-container { padding:1rem 1.5rem!important; max-width:100%  !important; }
header, footer { visibility:hidden!important; }
#MainMenu { visibility:hidden!important; }
/* [data-testid='collapsedControl'] { display:none!important; } */
/* [data-testid='stSidebarCollapseButton'] { display:none!important; } */

/* ── SIDEBAR SHELL ── */
[data-testid='stSidebar'] { background:#0a1320!important; border-right:1px solid #1e3a5f!important; width:220px!important; min-width:220px!important; padding:0!important; }
[data-testid='stSidebar'] > div { padding:0!important; }
[data-testid='stSidebarContent'] { padding:0 0 12px 0!important; overflow-y:auto!important; overflow-x:hidden!important; }

/* ── SIDEBAR HEADINGS ── */
[data-testid='stSidebar'] h1 { font-size:0.88rem!important; font-weight:600!important; color:#e6edf3!important; padding:10px 14px 6px!important; margin:0!important; border-bottom:1px solid #1e3a5f!important; }
[data-testid='stSidebar'] h2, [data-testid='stSidebar'] h3 { font-size:0.60rem!important; font-weight:700!important; color:#58a6ff!important; letter-spacing:2px!important; text-transform:uppercase!important; padding:8px 14px 2px!important; margin:0!important; }

/* ── SIDEBAR UTILITY BUTTONS (Sync etc) ── */
[data-testid='stSidebar'] button { background:#0a1e35!important; background-color:#0a1e35!important; border:1px solid #1e4d6b!important; border-radius:4px!important; color:#58a6ff!important; font-size:0.72rem!important; width:100%!important; padding:5px 10px!important; text-align:left!important; }
[data-testid='stSidebar'] button p { color:#58a6ff!important; font-size:0.72rem!important; }
[data-testid='stSidebar'] button:hover { background:#102a45!important; background-color:#102a45!important; border-color:#7ec8ff!important; }
[data-testid='stSidebar'] .stButton { padding:0 8px!important; }

/* ── SIDEBAR METRICS ── */
[data-testid='stSidebar'] [data-testid='metric-container'] { background:#0d1b2a!important; border:1px solid #1e3a5f!important; border-radius:5px!important; padding:4px 10px 5px!important; margin:3px 8px!important; }
[data-testid='stSidebar'] [data-testid='metric-container'] label { font-size:0.58rem!important; color:#5a8a9f!important; letter-spacing:0.8px!important; text-transform:uppercase!important; }
[data-testid='stSidebar'] [data-testid='stMetricValue'] { font-size:0.82rem!important; font-weight:700!important; color:#e3b341!important; line-height:1.3!important; font-family:'JetBrains Mono',monospace!important; }
[data-testid='stSidebar'] [data-testid='stMetricValue'] * { font-size:0.82rem!important; color:#e3b341!important; }
[data-testid='stSidebar'] [data-testid='stMetricDelta'] { font-size:0.58rem!important; }
[data-testid='stSidebar'] hr { border-color:#1e3a5f!important; margin:5px 0!important; }
[data-testid='stSidebar'] [data-testid='stCaptionContainer'] p { font-size:0.58rem!important; color:#5a8a9f!important; }
[data-testid='stSidebar'] [data-testid='stExpander'] { background:#0d1b2a!important; border:1px solid #1e3a5f!important; border-radius:4px!important; margin:3px 8px!important; }
[data-testid='stSidebar'] [data-testid='stExpander'] summary { font-size:0.72rem!important; color:#adbac7!important; padding:5px 10px!important; }

/* ── MAIN AREA ALL BUTTONS (columns, containers, everywhere) ── */
section.main button,
[data-testid='stMainBlockContainer'] button,
[data-testid='stHorizontalBlock'] button,
[data-testid='stVerticalBlock'] button:not([data-testid='stSidebar'] button) {
    background:#0d1b2a!important; background-color:#0d1b2a!important;
    border:1px solid #2d4060!important; border-radius:5px!important;
    color:#c9d1d9!important; font-size:0.80rem!important; font-weight:400!important;
}
section.main button p,
[data-testid='stMainBlockContainer'] button p,
[data-testid='stHorizontalBlock'] button p {
    color:#c9d1d9!important; font-size:0.80rem!important;
}
section.main button *,
[data-testid='stMainBlockContainer'] button *,
[data-testid='stHorizontalBlock'] button * {
    color:#c9d1d9!important;
}
section.main button:hover,
[data-testid='stMainBlockContainer'] button:hover,
[data-testid='stHorizontalBlock'] button:hover {
    background:#12243a!important; background-color:#12243a!important;
    border-color:#58a6ff!important; color:#e6edf3!important;
}
section.main button:hover *,
[data-testid='stMainBlockContainer'] button:hover *,
[data-testid='stHorizontalBlock'] button:hover * {
    color:#e6edf3!important;
 /* Chat input row – dark border */
[data-testid='stChatInput'] textarea {
    background:#080f1a !important;
    border:1px solid #1e3a5f !important;
    color:#e6edf3 !important;
    font-size:0.80rem !important;
}
[data-testid='stChatInput']
   
}

/* ── MAIN HEADINGS ── */
.stApp h1 { font-size:1.15rem!important; font-weight:600!important; color:#e6edf3!important; border-left:3px solid #238636!important; padding-left:10px!important; margin:8px 0 4px!important; }
.stApp h2 { font-size:0.88rem!important; font-weight:600!important; color:#c9d1d9!important; border-bottom:1px solid #1e3a5f!important; padding-bottom:3px!important; margin:12px 0 6px!important; }
.stApp h3 { font-size:0.80rem!important; font-weight:500!important; color:#8b949e!important; margin:8px 0 4px!important; }

/* ── MAIN METRICS ── */
[data-testid='metric-container'] { background:#0d1b2a!important; border:1px solid #1e3a5f!important; border-radius:6px!important; padding:10px 14px!important; }
[data-testid='metric-container'] label { font-size:0.60rem!important; color:#5a8a9f!important; letter-spacing:1px!important; text-transform:uppercase!important; font-weight:400!important; }
[data-testid='stMetricValue'] { font-family:'JetBrains Mono',monospace!important; font-size:1.05rem!important; font-weight:600!important; color:#e3b341!important; }
[data-testid='stMetricValue'] * { font-size:1.05rem!important; color:#e3b341!important; }

/* ── EXPANDERS / CONTAINERS ── */
.stApp [data-testid='stExpander'] { background:#0d1b2a!important; border:1px solid #1e3a5f!important; border-radius:6px!important; }
.stApp [data-testid='stExpander'] summary { font-size:0.82rem!important; font-weight:500!important; color:#c9d1d9!important; padding:8px 14px!important; }
.stApp [data-testid='stVerticalBlockBorderWrapper'] { background:#0d1b2a!important; border:1px solid #1e3a5f!important; border-radius:6px!important; padding:10px 14px!important; }
[data-testid='stDataFrame'], [data-testid='stDataEditor'] { border:1px solid #1e3a5f!important; border-radius:6px!important; }

/* ── INPUTS ── */
[data-testid='stTextInput'] input, [data-testid='stNumberInput'] input { background:#080f1a!important; border:1px solid #1e3a5f!important; color:#e6edf3!important; font-family:'JetBrains Mono',monospace!important; font-size:0.78rem!important; }
[data-testid='stSelectbox'] > div > div { background:#080f1a!important; border-color:#1e3a5f!important; color:#e6edf3!important; font-size:0.78rem!important; }
[data-testid='stChatInput'] textarea { background:#080f1a!important; border:1px solid #1e3a5f!important; color:#e6edf3!important; font-size:0.80rem!important; }
[data-testid='stChatInput'] textarea:focus { border-color:#238636!important; }

/* ── ALERTS ── */
[data-testid='stAlert'] { border-radius:5px!important; font-size:0.78rem!important; }
[data-testid='stInfo']    { background:rgba(88,166,255,0.07)!important; border-left:3px solid #58a6ff!important; }
[data-testid='stSuccess'] { background:rgba(35,134,54,0.09)!important;  border-left:3px solid #3fb950!important; }
[data-testid='stWarning'] { background:rgba(227,179,65,0.09)!important;  border-left:3px solid #e3b341!important; }
[data-testid='stError']   { background:rgba(248,81,73,0.09)!important;   border-left:3px solid #ff4b4b!important; }

/* ── MISC ── */
hr { border-color:#1e3a5f!important; margin:8px 0!important; }
label { color:#8b949e!important; font-size:0.73rem!important; }
p { color:#c9d1d9; font-family:'Inter',sans-serif; font-size:0.83rem; }
div[data-testid='column-header-content'] { font-weight:bold!important; }

</style>
""", unsafe_allow_html=True)

# - GLOBAL SYNC (FIXED SECTOR SYNC) -
with st.spinner('Syncing Portfolio & Funds...'):
    active_symbols, live_map, live_funds, sec_id_map = fetch_live_data()
    db_df = load_db()

# 1. Load Portfolio CSV (Master Source for SL & Sector)
portfolio_data = {}
try:
    if os.path.exists("portfolio.csv"):
        p_df = pd.read_csv("portfolio.csv")
        p_df.columns = p_df.columns.str.strip()
        for _, r in p_df.iterrows():
            # Normalize Ticker: "NSE:RELIANCE-EQ" -> "RELIANCE"
            t_raw = str(r.get('Ticker', '')).strip().upper()
            t_clean = clean_symbol(t_raw)
            if t_clean:
                portfolio_data[t_clean] = {
                    'SL': float(r.get('SL', 0.0)),
                    'Sector': str(r.get('Sector', ''))
                }
except Exception as e:
    st.error(f"Portfolio Load Error: {e}")

# 2. Update Active Symbols in DB (Prices + SECTOR + SL SYNC)
for sym in active_symbols:
    live_qty = live_map[sym]['Quantity']
    live_buy = live_map[sym]['BuyPrice']
    
    # Check Master Portfolio for SL/Sector
    master_sl = 0.0
    master_sec = None
    
    # Robust Normalization for Lookup
    lookup_sym = clean_symbol(sym)
    
    if lookup_sym in portfolio_data:
        master_sl = portfolio_data[lookup_sym]['SL']
        master_sec = portfolio_data[lookup_sym]['Sector']

    existing_row = db_df[db_df['Symbol'] == sym]
    
    if existing_row.empty:
        # New Trade: Use Master/Auto Sector
        if not master_sec: master_sec = get_sector(sym)
        
        # Auto-Calc Target for New Trade if SL exists
        new_target = 0.0
        if master_sl > 0:
            risk = live_buy - master_sl
            if risk > 0: new_target = live_buy + (risk * 2) # Default 1:2
        
        upsert_trade({
            'Symbol': sym, 
            'Quantity': live_qty, 
            'BuyPrice': live_buy, 
            'Status': 'OPEN', 
            'Sector': master_sec,
            'StopLoss': master_sl,
            'Target': new_target,
            'PlannedRR': "1:2"
        })
    else:
        # Existing Trade: Sync Delta
        row = existing_row.iloc[0]
        updates = {}
        
        if row['Status'] == 'CLOSED': updates['Status'] = 'OPEN'
        if row['Quantity'] != live_qty: updates['Quantity'] = live_qty
        if row['BuyPrice'] != live_buy: updates['BuyPrice'] = live_buy
        
        # SL Sync: If DB SL is 0 or different from Master, update
        current_sl = float(row.get('StopLoss') or 0.0)
        current_target = float(row.get('Target') or 0.0)
        
        # Update if Master has a value and it differs
        if master_sl > 0 and abs(master_sl - current_sl) > 0.05:
            updates['StopLoss'] = master_sl
            
            # If we updated SL, and Target is 0, Auto-Calc Target
            if current_target == 0:
                risk = live_buy - master_sl
                if risk > 0: 
                    updates['Target'] = live_buy + (risk * 2) # Default 1:2
                    updates['PlannedRR'] = "1:2"
            
        # Sector Sync
        current_sec = row.get('Sector')
        if not current_sec or pd.isna(current_sec) or current_sec == 'Unknown':
             if master_sec: updates['Sector'] = master_sec
             else: updates['Sector'] = get_sector(sym)
        elif master_sec and master_sec != DEFAULT_SECTOR and master_sec != current_sec:
             if current_sec == 'NSE:CNX500':
                 updates['Sector'] = master_sec
            
        if updates:
            upsert_trade({'Symbol': sym, **updates})

# 2. Close stale trades & Reconcile automatically
db_df = load_db()
closed_stale = []
for index, row in db_df.iterrows():
    if row['Status'] == 'OPEN' and row['Symbol'] not in active_symbols and len(active_symbols) > 0:
        upsert_trade({**{k: row[k] for k in row.index}, 'Status': 'CLOSED'})
        closed_stale.append(row['Symbol'])

if closed_stale:
    with st.spinner(f"Automatically reconciling exits for {len(closed_stale)} trades..."):
        from ai_reconcile_engine import sync_journal_with_dhan
        sync_journal_with_dhan(target_symbols=closed_stale)

db_df = load_db() # Final Reload

# - SIDEBAR CALCULATIONS -
active_trades = db_df[db_df['Status'] == 'OPEN'].copy()
closed_trades = db_df[db_df['Status'] == 'CLOSED'].copy()

# A. Capital & Open P&L
capital_deployed = 0.0
total_unrealized_pnl = 0.0
active_wins = 0
active_loss = 0

if not active_trades.empty:
    active_trades['Quantity'] = pd.to_numeric(active_trades['Quantity'], errors='coerce').fillna(0)
    active_trades['BuyPrice'] = pd.to_numeric(active_trades['BuyPrice'], errors='coerce').fillna(0)
    # Q5 FIX (20 Jun 2026): exclude rows with no valid cost basis (BuyPrice<=0) or
    # qty<=0 — a missing buy price (->0) faked unrealized P&L and understated
    # deployed capital.
    active_trades = active_trades[(active_trades['Quantity'] > 0)
                                  & (active_trades['BuyPrice'] > 0)].copy()

    current_val_sum = 0.0
    for _, row in active_trades.iterrows():
        sym = row['Symbol']
        qty = row['Quantity']
        buy = row['BuyPrice']
        ltp = live_map[sym]['LTP'] if sym in live_map else buy
        
        val = ltp * qty
        pnl = (ltp - buy) * qty
        
        current_val_sum += val
        total_unrealized_pnl += pnl
        
        if pnl > 0: active_wins += 1
        else: active_loss += 1

    capital_deployed = (active_trades['Quantity'] * active_trades['BuyPrice']).sum() 

account_size = live_funds + capital_deployed 


# - RELOAD DB AFTER SYNC -
# Important: We just updated the DB with new Prices/SLs. 
# We must reload the DataFrame to show these changes in the UI.
db_df = load_db()

# 3. Categorize Trades
active_trades = db_df[db_df['Status'] == 'OPEN'].copy()
# Inject LTP for AI Risk Manager
active_trades['LTP'] = active_trades['Symbol'].map(lambda x: live_map.get(x, {}).get('LTP', 0))

closed_trades = db_df[db_df['Status'] == 'CLOSED'].copy()

# B. Closed Stats
closed_wins = 0
closed_loss = 0
realized_pnl = 0.0

if not closed_trades.empty:
    for c in ['ExitPrice', 'BuyPrice', 'Quantity']:
        closed_trades[c] = pd.to_numeric(closed_trades[c], errors='coerce').fillna(0)
    
    # Only consider fully reconciled trades (Exit Price > 0)
    valid_closed = closed_trades[closed_trades['ExitPrice'] > 0].copy()
    
    if not valid_closed.empty:
        valid_closed['Trade_PnL'] = (valid_closed['ExitPrice'] - valid_closed['BuyPrice']) * valid_closed['Quantity']
        realized_pnl = valid_closed['Trade_PnL'].sum()
        closed_wins = len(valid_closed[valid_closed['Trade_PnL'] > 0])
        closed_loss = len(valid_closed[valid_closed['Trade_PnL'] <= 0])
    
    # Keep closed_trades as the full list, but use valid_closed for stats
    # closed_trades = valid_closed  <- REMOVED to show all closed trades

# C. Overall Stats
total_wins = active_wins + closed_wins
total_loss = active_loss + closed_loss
total_trades = total_wins + total_loss
win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0.0
loss_rate = (total_loss / total_trades * 100) if total_trades > 0 else 0.0

# - SIDEBAR UI -
st.sidebar.title("📘 Trade Journal")

# Initialize Session State for Page
if 'journal_page' not in st.session_state:
    st.session_state.journal_page = "Ledger (Active)"

# Button-styled Navigation (TOP OF SIDEBAR)
st.sidebar.subheader("📡 NAVIGATION")
nav_options = ["Ledger (Active)", "Closed Trades", "Visual Analytics"]
active_idx = nav_options.index(st.session_state.journal_page)

st.sidebar.markdown(f"""<style>
div[data-testid='stSidebar'] div[data-testid='stVerticalBlock'] div[data-testid='stVerticalBlock'] > div:nth-of-type(1) button,
div[data-testid='stSidebar'] div[data-testid='stVerticalBlock'] div[data-testid='stVerticalBlock'] > div:nth-of-type(2) button,
div[data-testid='stSidebar'] div[data-testid='stVerticalBlock'] div[data-testid='stVerticalBlock'] > div:nth-of-type(3) button {{
    background:#0d1b2a!important;background-color:#0d1b2a!important;
    border:1px solid #2d4060!important;border-radius:5px!important;
    color:#8b949e!important;font-size:0.78rem!important;font-weight:400!important;
    padding:7px 12px!important;width:100%!important;margin:2px 0!important;
}}
div[data-testid='stSidebar'] div[data-testid='stVerticalBlock'] div[data-testid='stVerticalBlock'] > div:nth-of-type(1) button p,
div[data-testid='stSidebar'] div[data-testid='stVerticalBlock'] div[data-testid='stVerticalBlock'] > div:nth-of-type(2) button p,
div[data-testid='stSidebar'] div[data-testid='stVerticalBlock'] div[data-testid='stVerticalBlock'] > div:nth-of-type(3) button p {{
    color:#8b949e!important;font-size:0.78rem!important;
}}
div[data-testid='stSidebar'] div[data-testid='stVerticalBlock'] div[data-testid='stVerticalBlock'] > div:nth-of-type({active_idx + 1}) button {{
    background:#1a4d2e!important;background-color:#1a4d2e!important;
    border:1px solid #3fb950!important;color:#ffffff!important;font-weight:700!important;
}}
div[data-testid='stSidebar'] div[data-testid='stVerticalBlock'] div[data-testid='stVerticalBlock'] > div:nth-of-type({active_idx + 1}) button p,
div[data-testid='stSidebar'] div[data-testid='stVerticalBlock'] div[data-testid='stVerticalBlock'] > div:nth-of-type({active_idx + 1}) button * {{
    color:#ffffff!important;font-weight:700!important;
}}
</style>""", unsafe_allow_html=True)

for opt in nav_options:
    if st.sidebar.button(opt, key=f"journal_nav_{opt}", width="stretch"):
        st.session_state.journal_page = opt
        st.rerun()

page = st.session_state.journal_page
st.sidebar.divider()

# Section 1: Capital
st.sidebar.subheader("💰 Account")
st.sidebar.metric("Total Account", f"₹{format_inr(account_size)}")
st.sidebar.metric("Capital Deployed", f"₹{format_inr(capital_deployed)}")
st.sidebar.metric("Funds (Free)", f"₹{format_inr(live_funds)}")

st.sidebar.divider()

# Section 2: Active P&L
st.sidebar.subheader("🔥 Active Performance")
st.sidebar.metric("Open P&L", f"₹{format_inr(total_unrealized_pnl)}", delta=f"{total_unrealized_pnl:,.2f}")
c1, c2 = st.sidebar.columns(2)
c1.metric("Active Wins", active_wins)
c2.metric("Active Losses", active_loss)

st.sidebar.divider()

# Section 3: Historical P&L
st.sidebar.subheader("📜 Closed Performance")
st.sidebar.caption("History (Fully Exited Only)")

st.sidebar.metric("Realized P&L", f"₹{format_inr(realized_pnl)}", delta=f"{realized_pnl:,.2f}")
c3, c4 = st.sidebar.columns(2)
c3.metric("Wins", closed_wins)
c4.metric("Losses", closed_loss)
st.sidebar.divider()
if st.sidebar.button("🔄 Sync Entry Dates (3 Years)"):
    with st.spinner("Fetching Trade History (This may take a minute)..."):
        date_map = sync_history_data(days=1000, id_map=sec_id_map)
        
        updated_count = 0
        for sym in active_symbols:
            if sym in date_map:
                # Updation logic: Only if current date is today (default) or missing?
                # Actually, let's just update perfectly.
                # Use partial update to avoid overwriting other fields
                upsert_trade({'Symbol': sym, 'EntryDate': date_map[sym]})
                updated_count += 1
        
        st.toast(f"✅ Updated {updated_count} Entry Dates!")
        time.sleep(1)
        st.rerun()

if st.sidebar.button("⚓ Sync Trade Exits (Native API)"):
    with st.spinner("⚓ Fetching Trade Details from Dhan API..."):
        from ai_reconcile_engine import sync_journal_with_dhan
        count = sync_journal_with_dhan()
        if count > 0:
            st.success(f"✅ Reconciled {count} Exit Details!")
            time.sleep(1)
            st.rerun()
        else:
            st.info("No new exit details found in Dhan trade logs.")

if st.sidebar.button("⚠️ Force Resync SL/Targets"):
    with st.spinner("Forcing Master Portfolio Sync..."):
        # Load Portfolio
        p_data = {}
        try:
            if os.path.exists("portfolio.csv"):
                p_df = pd.read_csv("portfolio.csv")
                p_df.columns = p_df.columns.str.strip()
                for _, r in p_df.iterrows():
                    # Normalize: "NSE:RELIANCE-EQ" -> "RELIANCE"
                    t_clean = clean_symbol(r.get('Ticker', ''))
                    if t_clean:
                        p_data[t_clean] = {'SL': float(r.get('SL', 0.0)), 'Sector': str(r.get('Sector', ''))}
        except: pass
        
        upd_cnt = 0
        for sym in active_symbols:
            s_clean = clean_symbol(sym)
            if s_clean in p_data:
                m_sl = p_data[s_clean]['SL']
                m_sec = p_data[s_clean]['Sector']
                
                # Force Update Package
                pkg = {'Symbol': sym, 'StopLoss': m_sl, 'Sector': m_sec}
                
                # Auto-Calc Target if SL > 0
                live_buy = live_map[sym]['BuyPrice']
                if m_sl > 0:
                    risk = live_buy - m_sl
                    if risk > 0:
                        pkg['Target'] = live_buy + (risk * 2)
                        pkg['PlannedRR'] = "1:2"
                
                upsert_trade(pkg)
                upd_cnt += 1
                
        st.success(f"✅ Forced Update on {upd_cnt} trades!")
        time.sleep(1)
        st.rerun()

st.sidebar.metric("Win Rate", f"{win_rate:.1f}%")

# - SECTION 4: AI RISK GUARD -
st.sidebar.divider()
st.sidebar.subheader("🦁 AI RISK GUARD")
with st.sidebar.expander("🛡️ Tactical Alerts", expanded=True):
    # Fetch Sector & Hygiene Alerts
    risk_results = analyze_sector_concentration(active_trades)
    hygiene_alerts = validate_risk_hygiene(active_trades)
    
    # Combined Alerts
    all_risk_alerts = risk_results.get('alerts', []) + hygiene_alerts
    
    if not all_risk_alerts:
        st.success("✅ Risk hygiene looks optimal.")
    else:
        for alert in all_risk_alerts:
            if alert.get('Issue') == 'High Concentration':
                st.warning(f"⚠️ **{alert['Sector']}**: {alert['Exposure']} exposure. {alert['Detail']}")
            else:
                st.error(f"⚠️ **{alert['Symbol']}**: {alert['Issue']}. {alert['Detail']}")

st.sidebar.divider()


# - HEADER STYLING - (moved to top)

# - PAGE 1: ACTIVE LEDGER -
if page == "Ledger (Active)":
    st.title("📘 Active Trade Journal")

    # AI Market Brief Section
    with st.container(border=True):
        brief = generate_breadth_brief()
        st.markdown(f"📡 **Commander's Breadth Brief:** {brief}")

    # - ATR WATCHDOG SUMMARY -
    noise_risk_count = 0
    noise_risk_symbols = []
    
    # Pre-calculate noise risk for summary (will be duplicated in loop but good for UI)
    for sym in active_symbols:
        matching_db = db_df[db_df['Symbol'] == sym]
        if not matching_db.empty:
            je = matching_db.iloc[0]
            buy_price = je.get('BuyPrice', 0)
            ltp = live_map.get(sym, {}).get('LTP', buy_price)
            sl = float(je.get('StopLoss') or 0.0)
            if sl > 0:
                atr = get_atr(sym)
                if atr > 0:
                    dist = abs(ltp - sl)
                    if dist < (1.5 * atr):
                        noise_risk_count += 1
                        noise_risk_symbols.append(sym)

    if noise_risk_count > 0:
        st.error(f"⚠️ **NOISE WATCHDOG ALERT**: {noise_risk_count} trades ( {', '.join(noise_risk_symbols)} ) have Stop Losses inside the 'Noise Zone' (< 1.5x ATR). Consider widening stops to avoid premature exit.")
    else:
        st.success("🛡️ **NOISE WATCHDOG**: All Stop Losses are outside the immediate noise zone. Risk hygiene is optimal.")

    if not active_symbols:
        st.info("No active trades found.")
    else:
        ledger_rows = []
        for i, sym in enumerate(active_symbols):
            data = live_map[sym]
            matching_db = db_df[(db_df['Symbol'] == sym) & (db_df['Status'] == 'OPEN')]
            je = matching_db.iloc[0] if not matching_db.empty else pd.Series()
            
            sector = je.get('Sector')
            
            entry_date = je.get('EntryDate')
            if not entry_date or pd.isna(entry_date): entry_date = str(date.today())
            ageing = calculate_ageing(entry_date)
            
            buy_price = data['BuyPrice']
            ltp = data['LTP']
            qty = data['Quantity'] 
            sl = float(je.get('StopLoss') or 0.0)
            tgt = float(je.get('Target') or 0.0)
            
            pot_profit = (tgt - buy_price) * qty
            actual_pnl = (ltp - buy_price) * qty
            
            status_vis = "🟢 Winning" if actual_pnl > 0 else "🔴 Losing"
            
            # Calculate Default R:R if missing
            db_rr = je.get('PlannedRR')
            
            risk = buy_price - sl
            reward = tgt - buy_price
            
            # Use DB value logic: If DB has value, use it. Else calc. 
            # Actually, always show DB value if present.
            if db_rr and not pd.isna(db_rr):
                rr_vis = db_rr
            else:
                rr_vis = f"1:{round(reward/risk, 1)}" if risk > 0 else "1:2"

            # ATR Risk Calculation
            atr = get_atr(sym)
            dist_atr = 0.0
            risk_atr_vis = "N/A"
            if atr > 0 and sl > 0:
                dist_atr = abs(ltp - sl) / atr
                risk_atr_vis = f"{dist_atr:.1f}x ATR"
                if dist_atr < 1.5:
                    risk_atr_vis = "🔴 " + risk_atr_vis
                elif dist_atr < 2.0:
                    risk_atr_vis = "🟠 " + risk_atr_vis
                else:
                    risk_atr_vis = "🟢 " + risk_atr_vis

            ledger_rows.append({
                'Symbol': sym, 'Status': status_vis, 
                'Type': je.get('Type', 'Positional'), 'Sector': sector, 
                'Qty': qty, 'Buy Price': buy_price, 'Entry Date': entry_date, 
                'LTP': ltp, 'Ageing': f"{ageing} days", 'Risk (ATR)': risk_atr_vis,
                'Planned R:R': rr_vis, 'Pot. Profit': pot_profit, 'P&L': actual_pnl,
                'Stop Loss': sl, 'Target': tgt, 
                'Quality': je.get('Quality', ''), 
                'AI Analysis': je.get('AI Analysis', ''),
                'Rationale': je.get('Rationale', ''), 
                'Lessons': je.get('Lessons', ''),
                'Exit Date': je.get('ExitDate'), 'Exit Reason': je.get('ExitReason', ''),
                'Chart': je.get('Screenshot'),
                'Exit Price': float(je.get('ExitPrice') or 0.0)
            })
            
        df_view = pd.DataFrame(ledger_rows)
        
        # - SORTING & SR # ASSIGNMENT -
        if not df_view.empty:
            df_view['Entry Date'] = pd.to_datetime(df_view['Entry Date'])
            df_view = df_view.sort_values(by='Entry Date', ascending=True).reset_index(drop=True)
            df_view['Entry Date'] = df_view['Entry Date'].dt.date
            df_view.insert(0, 'Sr #', range(1, len(df_view) + 1))
        
        # Define Column Sequence
        column_order = [
            'Sr #', 'Symbol', 'Sector', 'Type', 'Status', 'Qty', 'Buy Price', 'Entry Date', 
            'LTP', 'Ageing', 'Risk (ATR)', 'Planned R:R', 'Pot. Profit', 'P&L', 'Stop Loss', 'Target', 
            'Quality', 'AI Analysis', 'Rationale', 'Lessons', 'Exit Price', 'Exit Date', 
            'Exit Reason', 'Chart'
        ]
        
        # Ensure all requested columns exist
        df_view = df_view[column_order]
        
        ai_col1, ai_col2, ai_col3 = st.columns([1.5, 1.5, 3])
        with ai_col1:
            if st.button("🤖 AI AUTO-ANALYSIS", width="stretch", help="Automatically generate latest tactical analysis for all open trades."):
                with st.spinner("AI is crafting tactical reports..."):
                    from ai_journaler_helper import generate_tactical_analysis
                    # We need active_trades from the outer scope
                    for idx, row in active_trades.iterrows():
                        # FORCE OVERWRITE: We now always generate fresh analysis to show IQ improvements
                        symbol = row['Symbol']
                        cleaned_sym = clean_symbol(symbol)
                        ltp_p = live_map.get(symbol, {}).get('LTP', row['BuyPrice'])
                        
                        new_analysis = generate_tactical_analysis(
                            symbol=symbol, 
                            sector=row['Sector'],
                            buy_price=row['BuyPrice'],
                            ltp=ltp_p,
                            sl=row['StopLoss'],
                            target=row['Target'],
                            force_refresh=True
                        )
                        # AI Grade Injection
                        grading = get_weinstein_score(
                            symbol=symbol,
                            sector=row['Sector'],
                            ltp=ltp_p,
                            buy_price=row['BuyPrice']
                        )
                        
                        pkg = {
                            'Symbol': symbol, 
                            'AI Analysis': new_analysis,
                            'Quality': grading['rating'] # Use Display Name 'Quality' for upsert_trade
                        }
                        
                        # Update description if possible? No, we'll just use Quality for now.
                        upsert_trade(pkg)
                    st.success("✅ Tactical Reports Regenerated!")
                    time.sleep(1)
                    st.rerun()
        
        with ai_col2:
            if st.button("⚓ RECONCILE EXITS", width="stretch", help="Sync missing Exit Prices for closed trades from Dhan Trade Logs."):
                with st.spinner("⚓ Reconciling with Dhan Logs..."):
                    from ai_reconcile_engine import reconcile_journal_exit_prices
                    count = reconcile_journal_exit_prices()
                    if count > 0:
                        st.success(f"✅ Reconciled {count} Trades!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.info("No missing exit prices found to reconcile.")
        
        st.divider()
        st.subheader("🦁 AI Commander Chat")
        with st.expander("💬 Chat with your Portfolio Analyst", expanded=True):
            user_query = st.chat_input("Ask about your performance, risk, or sector exposure...")
            if user_query:
                # Store query in session state to persist response across reruns
                st.session_state.last_query = user_query
                with st.spinner("AI Commander is analyzing..."):
                    response = get_commander_response(user_query, df_view)
                    st.session_state.commander_response = response

            if "commander_response" in st.session_state:
                st.markdown(f"**Commander:** {st.session_state.commander_response}")
                if st.button("Clear Chat"):
                    del st.session_state.commander_response
                    st.rerun()

        st.divider()
        # - INLINE EDITING ENABLED -
        st.info("💡 Tip: You can now edit Type, SL, Target, Rationale, and Exit details directly in the table below.")
        
        edited_df = st.data_editor(
            df_view,
            key="journal_editor",
            width="stretch",
            num_rows="fixed",
            hide_index=True,
            column_config={
                "Sr #": st.column_config.NumberColumn(width="small", disabled=True),
                "Symbol": st.column_config.TextColumn(width="small", disabled=True),
                "Sector": st.column_config.TextColumn("Sector", width="medium", disabled=True),
                "Type": st.column_config.SelectboxColumn("Type", options=["Positional", "Swing", "Investment"], required=True),
                "Status": st.column_config.TextColumn(width="small", disabled=True),
                "Qty": st.column_config.NumberColumn("Qty", disabled=True),
                "Buy Price": st.column_config.NumberColumn("Buy Price", format="₹%.2f", disabled=True),
                "Entry Date": st.column_config.DateColumn("Entry Date", disabled=True),
                "LTP": st.column_config.NumberColumn("LTP", format="₹%.2f", disabled=True),
                "Ageing": st.column_config.TextColumn("Ageing", disabled=True),
                "Risk (ATR)": st.column_config.TextColumn("Risk (ATR)", disabled=True, help="Distance to SL. Red if < 1.5x ATR (Noise Risk)"),
                "Planned R:R": st.column_config.TextColumn("Planned R:R", width="small", help="Default is 1:2"),
                "Pot. Profit": st.column_config.NumberColumn("Pot. Profit", format="₹%.2f", disabled=True),
                "P&L": st.column_config.NumberColumn("P&L", format="₹%.2f", disabled=True),
                "Stop Loss": st.column_config.NumberColumn("Stop Loss", format="₹%.2f", disabled=True),
                "Target": st.column_config.NumberColumn("Target", format="₹%.2f", disabled=True),
                "Quality": st.column_config.SelectboxColumn("Quality", options=["5-Star", "4-Star", "3-Star", "2-Star", "1-Star", "Avoid"]),
                "AI Analysis": st.column_config.TextColumn("AI Analysis", width="large", disabled=True),
                "Rationale": st.column_config.TextColumn("Rationale", width="large"),
                "Lessons": st.column_config.TextColumn("Lessons", width="large"),
                "Exit Price": st.column_config.NumberColumn("Exit Price", format="₹%.2f", disabled=True),
                "Exit Date": st.column_config.DateColumn("Exit Date", disabled=True),
                "Exit Reason": st.column_config.SelectboxColumn("Exit Reason", options=["", "Target Met", "SL Hit", "Trailing SL Hit", "Time Stop", "Fundamental Change", "Cost-to-Cost"]),
                "Chart": st.column_config.LinkColumn("Chart", display_text="View"),
            }
        )

        # - SAVE MECHANISM (DELTA BASED) -
        editor_state = st.session_state.get("journal_editor")
        
        if editor_state and "edited_rows" in editor_state and editor_state["edited_rows"]:
            changes_made = False
            
            for idx, changes in editor_state["edited_rows"].items():
                
                try:
                    # Index is now INTEGER (0,1,2..) because we didn't set Symbol as index
                    # So we use iloc to get the Symbol from the VIEW
                    sym = df_view.iloc[idx]['Symbol']
                except IndexError:
                    continue 

                # Prepare Update Dict
                # Only include changed fields
                update_dict = {'Symbol': sym}
                
                # Check for R:R Change -> Auto-Calc Target
                if 'Planned R:R' in changes:
                    new_rr_str = changes['Planned R:R']
                    update_dict['PlannedRR'] = new_rr_str
                    
                    # Calculate new Target
                    multiplier = parse_rr(new_rr_str)
                    
                    # Need Buy Price and Stop Loss. check changes first, else fallback to df_view
                    buy_p = df_view.iloc[idx]['Buy Price']
                    sl_p = float(changes.get('Stop Loss', df_view.iloc[idx]['Stop Loss']))
                    
                    risk = buy_p - sl_p
                    if risk > 0 and multiplier > 0:
                        new_target = buy_p + (risk * multiplier)
                        update_dict['Target'] = new_target
                        
                # Add other standard changes
                field_map = {
                    'Type': 'Type', 'Quality': 'Quality', 'Rationale': 'Rationale',
                    'Lessons': 'Lessons', 'Exit Reason': 'ExitReason', 'Planned R:R': 'PlannedRR',
                    'Stop Loss': 'StopLoss', 'Target': 'Target'
                }
                for k, v in changes.items():
                    if k in field_map:
                        update_dict[field_map[k]] = v
                    else:
                        # Fallback for keys that match DB exactly or aren't mapped
                        update_dict[k] = v

                try: 
                    # verify currently exists to merge defaults? 
                    # upsert_trade merges with excluded.k so we just pass what we want to update (plus Symbol)
                    upsert_trade(update_dict)
                    changes_made = True
                except Exception as e:
                    st.error(f"Error saving {sym}: {e}")

            if changes_made:
                st.toast("✅ Changes Saved!")
                time.sleep(0.5)
                st.rerun()
                
        
        st.divider()
        st.subheader("📸 Screenshot Management")
        c_sel, c_up, c_btn = st.columns([1, 2, 1])
        # FIX: Symbol is now the index, so use df_view.index
        sel_sym_upload = c_sel.selectbox("Select Stock for Image", df_view.index if not df_view.empty else [])
        uploaded_img = c_up.file_uploader("Upload Chart (Updates instantly)", type=['png', 'jpg'])
        
        if uploaded_img and sel_sym_upload:
             saved_path = save_screenshot(uploaded_img, sel_sym_upload)
             
             with st.spinner(f"AI Vision is analyzing {sel_sym_upload} chart..."):
                 vision_insight = analyze_chart_screenshot(saved_path, sel_sym_upload)
                 
             # Store path AND the vision insight
             upsert_trade({
                 'Symbol': sel_sym_upload, 
                 'Screenshot': saved_path,
                 'AI Analysis': f"👁️ VISION: {vision_insight}"
             })
             
             st.success(f"Snap saved and analyzed for {sel_sym_upload}!")
             time.sleep(1)
             st.rerun()


# - PAGE 2: CLOSED TRADES -
elif page == "Closed Trades":
    st.title("📜 Closed Trade History")
    
    if closed_trades.empty:
        st.info("No closed trades yet.")
    else:
        # FY Filter logic
        closed_trades['ExitDate_DT'] = pd.to_datetime(closed_trades['ExitDate'], errors='coerce')
        closed_trades['FY'] = closed_trades['ExitDate_DT'].apply(lambda x: get_fy(x) if pd.notnull(x) else "N/A")
        
        fy_list = sorted(closed_trades['FY'].unique().tolist(), reverse=True)
        sel_fy = st.sidebar.selectbox("📅 Filter by Financial Year", ["All Years"] + fy_list)
        
        if sel_fy != "All Years":
            display_df = closed_trades[closed_trades['FY'] == sel_fy].copy()
        else:
            display_df = closed_trades.copy()

        # Scorecard for the selected period
        st.subheader(f"📊 Performance Scorecard: {sel_fy}")
        
        # Calculate stats for the filtered set
        stats_df = display_df.copy()
        for c in ['ExitPrice', 'BuyPrice', 'Quantity']:
            stats_df[c] = pd.to_numeric(stats_df[c], errors='coerce').fillna(0)
        
        stats_df['Trade_PnL'] = (stats_df['ExitPrice'] - stats_df['BuyPrice']) * stats_df['Quantity']
        net_fy_pnl = stats_df['Trade_PnL'].sum()
        fy_wins = len(stats_df[stats_df['Trade_PnL'] > 0])
        fy_loss = len(stats_df[stats_df['Trade_PnL'] <= 0])
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Realized P&L", f"₹{format_inr(net_fy_pnl)}", delta=f"{net_fy_pnl:,.2f}")
        m2.metric("Wins", fy_wins)
        m3.metric("Losses", fy_loss)

        st.divider()
        
        # FY-WISE SUMMARY TABLE (Consolidated View)
        st.subheader("🗓️ Financial Year Performance Summary")
        summary_df = closed_trades.copy()
        for c in ['ExitPrice', 'BuyPrice', 'Quantity']:
            summary_df[c] = pd.to_numeric(summary_df[c], errors='coerce').fillna(0)
        summary_df['PnL'] = (summary_df['ExitPrice'] - summary_df['BuyPrice']) * summary_df['Quantity']
        
        fy_summary = summary_df.groupby('FY').agg(
            Total_PnL=('PnL', 'sum'),
            Trades=('PnL', 'count'),
            Wins=('PnL', lambda x: (x > 0).sum()),
            Losses=('PnL', lambda x: (x <= 0).sum())
        ).reset_index()
        
        fy_summary['Win_Rate'] = (fy_summary['Wins'] / fy_summary['Trades'] * 100).round(1).astype(str) + "%"
        fy_summary['Total_PnL_Str'] = fy_summary['Total_PnL'].apply(lambda x: f"₹{format_inr(x)}")
        
        st.dataframe(
            fy_summary[['FY', 'Total_PnL_Str', 'Win_Rate', 'Trades', 'Wins', 'Losses']],
            hide_index=True,
            width="stretch",
            column_config={
                "FY": st.column_config.TextColumn("Financial Year", width="medium"),
                "Total_PnL_Str": st.column_config.TextColumn("Net P&L", width="medium"),
                "Win_Rate": "Win %",
            }
        )

        st.divider()
        
        # AI Behavioral Analytics Section
        st.subheader("🦁 AI Behavioral Analytics")
        with st.container(border=True):
            pm_summary = generate_post_mortem_summary(display_df)
            st.markdown(f"**Commander's Post-Mortem ({sel_fy}):** {pm_summary}")
        
        st.divider()
        
        r_col1, r_col2 = st.columns([1, 4])
        with r_col1:
            if st.button("⚓ RECONCILE EXITS", key="recon_btn_closed", width="stretch", help="Sync missing Exit Prices for closed trades from Dhan Trade Logs."):
                with st.spinner("⚓ Reconciling with Dhan Logs..."):
                    from ai_reconcile_engine import reconcile_journal_exit_prices, discover_missing_trades
                    count = reconcile_journal_exit_prices()
                    discovered = discover_missing_trades()
                    
                    st.session_state.recon_count = count
                    st.session_state.discovered_trades = discovered
                    st.rerun()

        if st.session_state.get('recon_count', 0) > 0:
            st.success(f"✅ Successfully Reconciled {st.session_state.recon_count} Trades! (Check table below)")
            st.session_state.recon_count = 0

        if st.session_state.get('discovered_trades'):
            with st.expander("🔍 Log Discovery: Missing from Journal", expanded=True):
                st.warning(f"AI discovered {len(st.session_state.discovered_trades)} closed trades in logs that are NOT in your journal.")
                disc_df = pd.DataFrame(st.session_state.discovered_trades)
                st.dataframe(disc_df[['Symbol', 'Name', 'ExitPrice', 'Pnl']], hide_index=True)
                
                if st.button("➕ BACKFILL DISCOVERED TRADES", width="stretch"):
                    from ai_reconcile_engine import backfill_trades
                    b_count = backfill_trades(st.session_state.discovered_trades)
                    if b_count > 0:
                        st.success(f"Added {b_count} historical trades to Journal as CLOSED.")
                        st.session_state.discovered_trades = []
                        time.sleep(1)
                        st.rerun()
        
        st.divider()

        def get_result(row):
            if float(row.get('ExitPrice', 0)) <= 0: return "⏳ Awaiting Reconcile"
            pnl = (float(row['ExitPrice']) - float(row['BuyPrice'])) * float(row['Quantity'])
            return "🟢 WIN" if pnl > 0 else "🔴 LOSS"

        def get_pnl_str(row):
            if float(row.get('ExitPrice', 0)) <= 0: return "Pending"
            pnl = (float(row['ExitPrice']) - float(row['BuyPrice'])) * float(row['Quantity'])
            return f"₹{format_inr(pnl)}"

        display_df['Result'] = display_df.apply(get_result, axis=1)
        display_df['Realized_PnL_Str'] = display_df.apply(get_pnl_str, axis=1)
        
        # Proper Column Mapping for display
        display_df = display_df.rename(columns={
            'Symbol': 'Ticker', 'ExitDate': 'Exit Date', 'Type': 'Type', 
            'Sector': 'Sector', 'ExitReason': 'Reason'
        })
        
        st.dataframe(display_df[['Ticker', 'FY', 'Result', 'Realized_PnL_Str', 'Type', 'Sector', 'Reason', 'Exit Date']], width="stretch", hide_index=True)

# - PAGE 3: ANALYTICS (FIXED NULL SECTORS) -
elif page == "Visual Analytics":
    st.title("📊 Performance Laboratory")
    
    # - 1. PERFORMANCE SCORECARD -
    if not closed_trades.empty:
        analytics_df = closed_trades.copy()
        for c in ['ExitPrice', 'BuyPrice', 'Quantity']:
            analytics_df[c] = pd.to_numeric(analytics_df[c], errors='coerce').fillna(0)
        
        analytics_df['Realized_PnL'] = (analytics_df['ExitPrice'] - analytics_df['BuyPrice']) * analytics_df['Quantity']
        valid_trades = analytics_df[analytics_df['ExitPrice'] > 0].copy()
        
        if not valid_trades.empty:
            net_pnl = valid_trades['Realized_PnL'].sum()
            total_closed = len(valid_trades)
            wins = len(valid_trades[valid_trades['Realized_PnL'] > 0])
            losses = len(valid_trades[valid_trades['Realized_PnL'] <= 0])
            win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
            
            # Profit Factor
            gross_prof = valid_trades[valid_trades['Realized_PnL'] > 0]['Realized_PnL'].sum()
            gross_loss = abs(valid_trades[valid_trades['Realized_PnL'] <= 0]['Realized_PnL'].sum())
            profit_factor = (gross_prof / gross_loss) if gross_loss > 0 else (gross_prof if gross_prof > 0 else 0)
            
            # Avg Win/Loss
            avg_win = valid_trades[valid_trades['Realized_PnL'] > 0]['Realized_PnL'].mean() if wins > 0 else 0
            avg_loss = valid_trades[valid_trades['Realized_PnL'] <= 0]['Realized_PnL'].mean() if losses > 0 else 0
            
            st.subheader("🎯 Key Metrics")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Net Realized P&L", f"₹{format_inr(net_pnl)}", delta=f"₹{format_inr(net_pnl)}")
            m2.metric("Win Rate", f"{win_rate:.1f}%")
            m3.metric("Profit Factor", f"{profit_factor:.2f}")
            m4.metric("Avg Win/Loss", f"₹{format_inr(avg_win)} / ₹{format_inr(avg_loss)}")
            
            st.divider()

    # - 2. SECTOR ALLOCATION (Active) -
    st.subheader("Sector Allocation (Active)")
    if not active_trades.empty:
        active_trades['Sector'] = active_trades['Sector'].fillna("Unassigned").replace('', 'Unassigned')
        fig_sec = px.pie(active_trades, names='Sector', title='Current Exposure', hole=0.4, 
                         color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_sec.update_layout(showlegend=True, margin=dict(t=50, b=50, l=0, r=0))
        st.plotly_chart(fig_sec, width="stretch")
    else: st.info("No active exposure.")
    
    st.divider()
    
    # - 3. PERFORMANCE TRENDS -
    if closed_trades.empty: st.info("No closed trades to analyze yet.")
    else:
        valid_trades['ExitDate'] = pd.to_datetime(valid_trades['ExitDate'])
        equity_df = valid_trades.sort_values(by='ExitDate').dropna(subset=['ExitDate'])
        
        c1, c2 = st.columns(2)
        
        with c1:
            if not equity_df.empty:
                equity_df['Cumulative_PnL'] = equity_df['Realized_PnL'].cumsum()
                fig_eq = px.line(equity_df, x='ExitDate', y='Cumulative_PnL', markers=True, title="Account Growth Curve")
                fig_eq.update_traces(line_color='#00f260', line_width=3)
                fig_eq.add_hline(y=0, line_dash="dash", line_color="gray")
                st.plotly_chart(fig_eq, width="stretch")

        with c2:
            daily_pnl = equity_df.groupby('ExitDate')['Realized_PnL'].sum().reset_index()
            if not daily_pnl.empty:
                daily_pnl['Color'] = daily_pnl['Realized_PnL'].apply(lambda x: 'Profit' if x > 0 else 'Loss')
                fig_cal = px.bar(daily_pnl, x='ExitDate', y='Realized_PnL', color='Color',
                                 color_discrete_map={'Profit': '#00f260', 'Loss': '#ff4b4b'}, title="Daily Net P&L")
                st.plotly_chart(fig_cal, width="stretch")

        st.divider()
        
        # - 4. BEHAVIORAL DEEP DIVE -
        st.subheader("🧠 Behavioral Insights")
        b1, b2 = st.columns(2)
        
        with b1:
            # Holding Period Analysis (P&L vs Ageing)
            valid_trades['Ageing'] = valid_trades.apply(lambda r: calculate_ageing(r['EntryDate'], r['ExitDate']), axis=1)
            fig_age = px.scatter(valid_trades, x='Ageing', y='Realized_PnL', color='Quality', size='Quantity',
                                 hover_name='Symbol', title="P&L vs Holding Period (Ageing)",
                                 labels={'Ageing': 'Holding Period (Days)', 'Realized_PnL': 'Realized P&L (₹)'},
                                 color_discrete_sequence=px.colors.qualitative.Vivid)
            st.plotly_chart(fig_age, width="stretch")
            
        with b2:
            # Trade Quality Distribution
            if 'Quality' in valid_trades.columns:
                quality_stats = valid_trades.groupby('Quality')['Realized_PnL'].agg(['sum', 'count']).reset_index()
                quality_stats.columns = ['Quality', 'Total P&L', 'Number of Trades']
                fig_qual = px.bar(quality_stats, x='Quality', y='Total P&L', color='Quality',
                                  text='Number of Trades', title="P&L Distribution by Trade Quality",
                                  category_orders={"Quality": ["5-Star", "4-Star", "3-Star", "2-Star", "1-Star", "Avoid", ""]})
                st.plotly_chart(fig_qual, width="stretch")
