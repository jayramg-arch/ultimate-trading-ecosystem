"""journal_core — the trade journal's DATA layer, with no UI attached.

WHY THIS EXISTS (23-Sep-2026). dhan_journal_v7.py is a Streamlit app whose UI runs at
MODULE LEVEL, starting with st.set_page_config. Anything that imported it for a data
helper therefore rendered the entire journal - sidebar, metrics, watchdog banners - into
whatever page was calling, and ran a live Dhan portfolio sync as a side effect. The
Golden Matcher's "Log OPEN trade" button did exactly that (web app :15898), which was
only invisible because the stray output landed at the bottom of a long page.

Everything here is lifted VERBATIM from dhan_journal_v7.py lines 1-510 - the half that
was already UI-free - so the DB schema, the migration and upsert_trade are byte-identical
and there is one journal data layer, not two. dhan_journal_v7 now imports from here, so
the standalone app, journal_enrichment, journal_sync and the web app all share it.
"""

import streamlit as st
import pandas as pd
from dhanhq import dhanhq
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
        print("⏳ Checking Dhan API Token...")
        return ensure_valid_token()
    except Exception as e:
        print(f"⚠️ Warning: Auto-token refresh failed: {e}")
        return None

check_auth_cached()

# - 1. CONFIGURATION -
load_dotenv(override=True)

API_KEY = os.getenv("DHAN_ACCESS_TOKEN")
_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
import journal_path as _jp  # AUD-INT-14: one owner of the journal location
DB_FILE = _jp.JOURNAL_DB   # env override: render tests use a copy
DEFAULT_SECTOR = "NSE:CNX500"
SCREENSHOT_DIR = os.path.join(_DIR, "trade_screenshots")

# Force Install xlsxwriter
try:
    import xlsxwriter
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "xlsxwriter"])
    import xlsxwriter

if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

# Initialize Dhan
#
# 23-Sep-2026: these two branches used to call st.error() at MODULE level. That is the
# very bug this split exists to end — on a missing .env or a broker hiccup, every module
# that imported the journal for upsert_trade would paint a red banner into whatever page
# it was called from, with no way to tell where it came from. A data layer records the
# failure; the UI decides whether and where to show it (journal_page.render does, first
# thing), and headless callers - journal_sync, journal_enrichment, s4_take - get a plain
# stderr line instead of a Streamlit call they have no runtime for.
INIT_ERROR = None
try:
    if CLIENT_ID and API_KEY:
        dhan = dhanhq(client_id=CLIENT_ID, access_token=API_KEY)
    else:
        INIT_ERROR = "❌ Credentials Missing in .env file!"
        dhan = None
except Exception as e:
    INIT_ERROR = f"❌ Connection Error: {e}"
    dhan = None
if INIT_ERROR:
    print("[journal_core] " + INIT_ERROR, file=sys.stderr)

# - 2. HELPER FUNCTIONS -

def format_inr(number):
    try:
        if number is None or pd.isna(number): return "0.00"
        val = float(number)
        s, *d = str("{:.2f}".format(val)).partition(".")
        r = ",".join([s[x-2:x] for x in range(-3, -len(s), -2)][::-1] + [s[-3:]])
        return "".join([r] + d)
    except (ValueError, TypeError, AttributeError):
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
    # Phase-2A: prefer the unified sector DB (curated, 536 symbols) before
    # falling through to a yfinance.info call. The DB has Pine v67 mappings
    # plus aliases — handles M_M, BAJAJ-AUTO, NSE:TCS-EQ etc. cleanly.
    try:
        import sector_lookup as _sl
        rec = _sl.get_sector(cleaned)
        if rec:
            return rec.get("display_name") or rec.get("sector_name") or "Unknown"
    except Exception:
        pass
    # Last-resort yfinance lookup (the .info endpoint is the only one that
    # surfaces the Yahoo sector label — data_provider doesn't cache .info).
    try:
        ticker = yf.Ticker(f"{cleaned}.NS")
        return ticker.info.get('sector', 'Unknown')
    except Exception:
        return 'Unknown'

def calculate_ageing(entry_str, exit_str=None):
    try:
        start = datetime.strptime(str(entry_str)[:10], '%Y-%m-%d')
        end = datetime.strptime(str(exit_str)[:10], '%Y-%m-%d') if exit_str else datetime.now()
        return (end - start).days
    except (ValueError, TypeError): return 0

def get_fy(date_val):
    """Returns the Financial Year string (e.g., FY 2024-25) for a given date."""
    try:
        dt = pd.to_datetime(date_val)
        if dt.month >= 4:
            return f"{dt.year}-{str(dt.year+1)[2:]}"
        else:
            return f"{dt.year-1}-{str(dt.year)[2:]}"
    except (ValueError, TypeError): return "N/A"

# - 2.5 SYMBOL CLEANER -

def clean_symbol(symbol):
    """Clean Dhan symbols by stripping suffixes and mapping indices."""
    s = str(symbol).strip().upper().replace("NSE:", "").replace("BSE:", "")
    if s == "NIFTY": return "^NSEI"
    if s == "BANKNIFTY" or s == "NIFTYBANK": return "^NSEBANK"
    for suffix in ['-EQ', '-BE', '-SM', '-ST', '-BZ']:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    return s

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
            target1 REAL,
            target2 REAL,
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
            setup TEXT,
            entry_stage INTEGER,
            entry_alpha INTEGER,
            entry_rs REAL,
            entry_conviction REAL,
            snapshot_meta TEXT,
            manual_sl_override REAL,
            custom_ce_mult REAL,
            pyramid_status TEXT,
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
        'target1': 'Target1', 'target2': 'Target2', 'rationale': 'Rationale', 'timeframe': 'Timeframe',
        'entry_date': 'EntryDate', 'quantity': 'Quantity', 'buy_price': 'BuyPrice',
        'exit_date': 'ExitDate', 'exit_price': 'ExitPrice',
        'exit_reason': 'ExitReason', 'status': 'Status', 'sector': 'Sector',
        'trade_quality': 'Quality', 'compromises': 'Compromises', 
        'lessons': 'Lessons', 'screenshot_path': 'Screenshot',
        'planned_rr': 'PlannedRR', 'ai_analysis': 'AI Analysis',
        'setup': 'Setup', 'entry_stage': 'EntryStage',
        'entry_alpha': 'EntryAlpha', 'entry_rs': 'EntryRS',
        'entry_conviction': 'EntryConviction', 'snapshot_meta': 'SnapshotMeta',
        'manual_sl_override': 'Manual SL Override',
        'custom_ce_mult': 'Custom CE Mult',
        'pyramid_status': 'Pyramid Status'
    }
    return df.rename(columns=rename_map)

def upsert_trade(entry):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    db_map = {
        'id': 'id',
        'Symbol': 'symbol', 'Type': 'trade_type', 'StopLoss': 'stoploss',
        'Target1': 'target1', 'Target2': 'target2', 'Rationale': 'rationale', 'Timeframe': 'timeframe',
        'EntryDate': 'entry_date', 'Quantity': 'quantity', 'BuyPrice': 'buy_price',
        'ExitDate': 'exit_date', 'ExitPrice': 'exit_price',
        'ExitReason': 'exit_reason', 'Status': 'status', 'Sector': 'sector',
        'Quality': 'trade_quality', 'Compromises': 'compromises', 
        'Lessons': 'lessons', 'Screenshot': 'screenshot_path',
        'PlannedRR': 'planned_rr', 'AI Analysis': 'ai_analysis',
        'AI_Analysis': 'ai_analysis',
        'Manual SL Override': 'manual_sl_override',
        'Custom CE Mult': 'custom_ce_mult',
        'Pyramid Status': 'pyramid_status'
    }
    
    clean_entry = {db_map[k]: v for k, v in entry.items() if k in db_map}
    
    # Logic: If ID exists, update. If Symbol exists with OPEN status, update. Else Insert.
    target_id = clean_entry.get('id')
    
    if not target_id and clean_entry.get('symbol'):
        # ALWAYS check for existing OPEN row by symbol before inserting
        c.execute("SELECT id FROM journal WHERE symbol = ? AND status = 'OPEN' LIMIT 1", (clean_entry.get('symbol'),))
        row = c.fetchone()
        if row: target_id = row[0]

    keys = [k for k in clean_entry.keys() if k != 'id']
    
    new_id = None
    if target_id:
        # UPDATE
        update_str = ", ".join([f"{k} = ?" for k in keys])
        values = [clean_entry[k] for k in keys] + [target_id]
        c.execute(f"UPDATE journal SET {update_str} WHERE id = ?", values)
    else:
        # INSERT
        placeholders = ", ".join(["?"] * len(keys))
        c.execute(f"INSERT INTO journal ({', '.join(keys)}) VALUES ({placeholders})", [clean_entry[k] for k in keys])
        new_id = c.lastrowid

    conn.commit()
    conn.close()

    # True entry-time signal snapshot — only for brand-new OPEN trades. Runs
    # AFTER the DB is committed/closed so the slow network fetch never holds a
    # lock, and is fully guarded so a fetch failure can never block the save.
    if new_id is not None:
        status = str(clean_entry.get('status', 'OPEN') or 'OPEN').upper()
        symbol = clean_entry.get('symbol')
        if status == 'OPEN' and symbol:
            try:
                import journal_enrichment as je
                je.ensure_schema(DB_FILE)
                snap = je.snapshot_symbol(symbol, source="recompute")
                if snap:
                    je.write_snapshot(new_id, snap, DB_FILE)
            except Exception as _e:
                print(f"[journal] entry snapshot skipped for {symbol}: {_e}")

    return new_id

def parse_rr(rr_str):
    # Parse "1:2" -> 2.0
    try:
        if not rr_str: return 0.0
        parts = rr_str.split(':')
        if len(parts) == 2:
            return float(parts[1])
        return float(rr_str)
    except (ValueError, TypeError): return 0.0

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
        # Lean entry-signal snapshot columns (see journal_enrichment.py).
        for _col, _type in (('setup','TEXT'), ('entry_stage','INTEGER'),
                            ('entry_alpha','INTEGER'), ('entry_rs','REAL'),
                            ('entry_conviction','REAL'), ('snapshot_meta','TEXT'),
                            ('manual_sl_override','REAL'), ('custom_ce_mult','REAL'),
                            ('pyramid_status','TEXT')):
            if _col not in cols:
                c.execute(f"ALTER TABLE journal ADD COLUMN {_col} {_type}")
            
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
    except Exception: funds = 0.0

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
    except Exception: pass

    try:
        p = dhan.get_positions()
        if p['status'] == 'success': process(p['data'])
    except Exception: pass
    
    return active_symbols, live_data, funds, id_map

@st.cache_data(ttl=60)
def fetch_active_orders():
    if dhan is None: return {}
    live_orders = {}
    
    def process_orders(data):
        for item in data:
            if item.get('transactionType') != 'SELL' or item.get('orderStatus') != 'PENDING':
                continue
            
            sym = item.get('tradingSymbol')
            if not sym: continue
            
            clean_sym = clean_symbol(sym)
            if clean_sym not in live_orders:
                live_orders[clean_sym] = []
            
            leg = item.get('legName')
            otype = item.get('orderType', '')
            price = float(item.get('price') or 0.0)
            trigger = float(item.get('triggerPrice') or 0.0)
            
            live_orders[clean_sym].append({
                'leg': leg, 'otype': otype, 'price': price, 'trigger': trigger
            })

    try:
        ord_res = dhan.get_order_list()
        if ord_res.get('status') == 'success' and ord_res.get('data'):
            process_orders(ord_res['data'])
    except Exception: pass
    
    try:
        gtt_res = dhan.get_forever()
        if gtt_res.get('status') == 'success' and gtt_res.get('data'):
            process_orders(gtt_res['data'])
    except Exception: pass
    
    return live_orders

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

