import streamlit as st
import pandas as pd
from dhanhq import dhanhq
import sqlite3
import os
from datetime import datetime, date, timedelta
import yfinance as yf
import io
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURATION ---
API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzY5MzQ5MjkwLCJpYXQiOjE3NjkyNjI4OTAsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMDAwNTM5ODk4In0.6bOjCYqfUaPMBbMv4O1fmE_FhOone4Bbb4q21oUhSR8mGyYi1gItoCEavgFx0WcYUe7f7THeF05xnPUfVyG5UA"
CLIENT_ID = "1000539898"
DB_FILE = "trade_journal_v6.db" 
SCREENSHOT_DIR = "trade_screenshots"

# Force Install xlsxwriter
import sys
import subprocess
try:
    import xlsxwriter
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "xlsxwriter"])
    import xlsxwriter

if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

# Initialize Dhan
try:
    dhan = dhanhq(client_id=CLIENT_ID, access_token=API_KEY)
except:
    dhan = None

# --- 2. HELPER FUNCTIONS ---

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
    sym_upper = symbol.upper()
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
        ticker = yf.Ticker(f"{symbol}.NS")
        return ticker.info.get('sector', 'Unknown')
    except:
        return 'Unknown'

def calculate_ageing(entry_str, exit_str=None):
    try:
        if not entry_str: return 0
        entry = datetime.strptime(str(entry_str), "%Y-%m-%d").date()
        if exit_str and str(exit_str) != 'None' and pd.notna(exit_str):
             exit_d = datetime.strptime(str(exit_str), "%Y-%m-%d").date()
             return (exit_d - entry).days
        else:
             return (date.today() - entry).days
    except:
        return 0

# --- 3. DATABASE ENGINE ---

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS journal (
            symbol TEXT PRIMARY KEY,
            trade_type TEXT,
            stoploss REAL,
            target REAL,
            rationale TEXT,
            timeframe TEXT,
            entry_date TEXT,
            
            -- EXECUTION DATA
            quantity REAL, 
            buy_price REAL, -- NEW FIELD: Essential for Equity Curve
            
            -- EXIT DATA
            exit_date TEXT,
            exit_price REAL,
            exit_reason TEXT,
            status TEXT DEFAULT 'OPEN',
            
            -- METADATA
            sector TEXT,
            trade_quality TEXT,
            compromises TEXT,
            lessons TEXT,
            screenshot_path TEXT,
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
        'lessons': 'Lessons', 'screenshot_path': 'Screenshot'
    }
    return df.rename(columns=rename_map)

def upsert_trade(entry):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    db_map = {
        'Symbol': 'symbol', 'Type': 'trade_type', 'StopLoss': 'stoploss',
        'Target': 'target', 'Rationale': 'rationale', 'Timeframe': 'timeframe',
        'EntryDate': 'entry_date', 'Quantity': 'quantity', 'BuyPrice': 'buy_price',
        'ExitDate': 'exit_date', 'ExitPrice': 'exit_price',
        'ExitReason': 'exit_reason', 'Status': 'status', 'Sector': 'sector',
        'Quality': 'trade_quality', 'Compromises': 'compromises', 
        'Lessons': 'lessons', 'Screenshot': 'screenshot_path'
    }
    
    clean_entry = {db_map[k]: v for k, v in entry.items() if k in db_map}
    keys = list(clean_entry.keys())
    placeholders = ":" + ", :".join(keys)
    update_logic = ", ".join([f"{k}=excluded.{k}" for k in keys])
    
    sql = f'''
        INSERT INTO journal ({", ".join(keys)})
        VALUES ({placeholders})
        ON CONFLICT(symbol) DO UPDATE SET
            {update_logic}
    '''
    c.execute(sql, clean_entry)
    conn.commit()
    conn.close()

if not os.path.exists(DB_FILE):
    init_db()

# --- 4. DATA FETCHING ---

def fetch_live_data():
    if dhan is None: return [], {}
    
    active_symbols = []
    live_data = {}

    def process(data):
        for item in data:
            sym = item.get('tradingSymbol')
            qty = item.get('totalQty') or item.get('netQty')
            if qty == 0: continue
            
            ltp = item.get('lastTradedPrice') or item.get('ltp') or item.get('lastPrice') or item.get('close') or 0.0
            buy_avg = item.get('avgCostPrice') or item.get('buyAvg') or 0.0
            
            active_symbols.append(sym)
            live_data[sym] = {
                'Symbol': sym, 'Quantity': abs(qty), 'BuyPrice': buy_avg, 'LTP': ltp
            }

    try:
        h = dhan.get_holdings()
        if h['status'] == 'success': process(h['data'])
    except: pass
    
    try:
        p = dhan.get_positions()
        if p['status'] == 'success': process(p['data'])
    except: pass
    
    return active_symbols, live_data

# --- 5. DASHBOARD UI ---

st.set_page_config(page_title="Pro Trade Ledger", layout="wide", page_icon="📈")

# --- SIDEBAR & SYNC ---

st.sidebar.header("📊 Performance Stats")
all_trades = load_db()
closed_trades = all_trades[all_trades['Status'] == 'CLOSED'].copy()

if not closed_trades.empty:
    win_count = len(closed_trades[closed_trades['ExitReason'] == 'Target Met'])
    win_rate = (win_count / len(closed_trades)) * 100
    st.sidebar.metric("Avg Win Rate", f"{win_rate:.1f}%")
else:
    st.sidebar.metric("Avg Win Rate", "0.0%")

st.sidebar.divider()
st.sidebar.header("⚙️ Capital Config")
cap_total = st.sidebar.number_input("Total Capital (₹)", value=4000000)

page = st.sidebar.radio("Navigation", ["Ledger (Active)", "Closed Trades", "Visual Analytics"])

# Global Sync Logic (Updated for BuyPrice)
with st.spinner('Syncing...'):
    active_symbols, live_map = fetch_live_data()
    db_df = load_db()

for index, row in db_df.iterrows():
    sym = row['Symbol']
    if row['Status'] == 'OPEN' and sym in active_symbols:
        live_qty = live_map[sym]['Quantity']
        live_buy = live_map[sym]['BuyPrice']
        # Sync Qty and Buy Price to DB so it's saved for posterity
        if row['Quantity'] != live_qty or row['BuyPrice'] != live_buy:
            upsert_trade({**{k: row[k] for k in row.index}, 'Quantity': live_qty, 'BuyPrice': live_buy})
            
    elif row['Status'] == 'OPEN' and sym not in active_symbols and len(active_symbols) > 0:
        upsert_trade({**{k: row[k] for k in row.index}, 'Status': 'CLOSED'})

db_df = load_db() # Reload with new synced data

# --- PAGE 1: ACTIVE LEDGER ---
if page == "Ledger (Active)":
    st.title("📘 Active Trade Ledger")

    if not active_symbols:
        st.info("No active trades found.")
    else:
        ledger_rows = []
        for i, sym in enumerate(active_symbols):
            data = live_map[sym]
            matching_db = db_df[db_df['Symbol'] == sym]
            je = matching_db.iloc[0] if not matching_db.empty else pd.Series()

            sector = je.get('Sector')
            if not sector or pd.isna(sector): sector = get_sector(sym)

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
            
            risk = buy_price - sl
            reward = tgt - buy_price
            rr = f"1:{round(reward/risk, 1)}" if risk > 0 else "N/A"

            ledger_rows.append({
                'Sr #': i + 1, 'Symbol': sym, 'Type': je.get('Type', 'Positional'),
                'Sector': sector, 'Quantity': qty, 'BuyPrice': buy_price,
                'LTP': ltp, 'Ageing': f"{ageing} days", 'Planned R:R': rr,
                'Potential Profit': pot_profit, 'Actual P&L': actual_pnl,
                'StopLoss': sl, 'Target': tgt, 'Quality': je.get('Quality', ''),
                'Rationale': je.get('Rationale', ''), 'Lessons': je.get('Lessons', ''),
                'EntryDate': entry_date, 'Exit Price': float(je.get('ExitPrice') or 0.0),
                'Exit Date': je.get('ExitDate'), 'Exit Reason': je.get('ExitReason', ''),
                'Screenshot': je.get('Screenshot')
            })
            
        df_view = pd.DataFrame(ledger_rows)
        
        # Stats & Table
        total_act_pnl = df_view['Actual P&L'].sum()
        c1, c2 = st.columns(2)
        c1.metric("Total Active P&L", f"₹{format_inr(total_act_pnl)}", delta=f"{total_act_pnl:,.2f}")

        st.dataframe(df_view, hide_index=True, use_container_width=False,
            column_config={
                "Sr #": st.column_config.NumberColumn(width="small"),
                "Symbol": st.column_config.TextColumn(width="small"),
                "Sector": st.column_config.TextColumn(width="medium"),
                "BuyPrice": st.column_config.NumberColumn(format="₹%.2f"),
                "LTP": st.column_config.NumberColumn(format="₹%.2f"),
                "Actual P&L": st.column_config.NumberColumn(format="₹%.2f"),
                "Potential Profit": st.column_config.NumberColumn(format="₹%.2f"),
                "Screenshot": st.column_config.LinkColumn(display_text="View"),
            })
        
        # Downloads... (Keeping code brief)
        st.divider()
        st.subheader("📝 Edit & Upload")
        sel_sym = st.selectbox("Select Stock", df_view['Symbol'])
        if sel_sym:
            curr = df_view[df_view['Symbol'] == sel_sym].iloc[0]
            
            if curr['Screenshot'] and os.path.exists(curr['Screenshot']):
                with st.expander("🖼️ View Attached Chart", expanded=True):
                    st.image(curr['Screenshot'], caption=f"Chart: {sel_sym}")

            with st.form("edit_form_final"):
                c1, c2, c3, c4 = st.columns(4)
                valid_types = ["Positional", "Swing", "Investment"]
                curr_type = curr['Type'] if curr['Type'] in valid_types else "Positional"
                new_type = c1.selectbox("Type", valid_types, index=valid_types.index(curr_type))
                new_sl = c2.number_input("Stop Loss", value=float(curr['StopLoss']))
                new_tgt = c3.number_input("Target", value=float(curr['Target']))
                new_entry = c4.date_input("Entry Date", value=datetime.strptime(str(curr['EntryDate']), "%Y-%m-%d").date())
                
                new_sector = st.text_input("Sector", value=str(curr['Sector']))
                uploaded_img = st.file_uploader("📸 Upload Chart", type=['png', 'jpg'])

                c5, c6, c7 = st.columns(3)
                new_exit_price = c5.number_input("Exit Price", value=float(curr.get('Exit Price') or 0.0))
                ex_val = curr.get('Exit Date')
                ex_date_val = datetime.strptime(str(ex_val), "%Y-%m-%d").date() if (ex_val and str(ex_val) != 'None') else None
                new_exit_date = c6.date_input("Exit Date", value=ex_date_val)
                curr_reason = curr.get('Exit Reason') or ""
                valid_reasons = ["", "Target Met", "SL Hit", "Trailing SL Hit", "Time Stop", "Fundamental Change", "Cost-to-Cost"]
                new_exit_reason = c7.selectbox("Reason for Exit", valid_reasons, index=valid_reasons.index(curr_reason) if curr_reason in valid_reasons else 0)
                
                new_rationale = st.text_area("Rationale", value=str(curr.get('Rationale') or ""))
                new_lessons = st.text_area("Lessons Learnt", value=str(curr.get('Lessons') or ""))
                
                if st.form_submit_button("Update Ledger"):
                    saved_path = curr['Screenshot']
                    if uploaded_img: saved_path = save_screenshot(uploaded_img, sel_sym)
                    
                    upsert_trade({
                        'Symbol': sel_sym, 'Type': new_type, 'StopLoss': new_sl, 'Target': new_tgt,
                        'EntryDate': str(new_entry), 'Quantity': float(curr['Quantity']),
                        'BuyPrice': float(curr['BuyPrice']), # PERSIST BUY PRICE
                        'ExitPrice': new_exit_price, 'ExitDate': str(new_exit_date) if new_exit_date else None,
                        'ExitReason': new_exit_reason, 'Sector': new_sector,
                        'Rationale': new_rationale, 'Lessons': new_lessons, 'Screenshot': saved_path
                    })
                    st.success("Updated!"); st.rerun()

# --- PAGE 2: CLOSED TRADES ---
elif page == "Closed Trades":
    st.title("📜 Closed Trade History")
    if closed_trades.empty:
        st.info("No closed trades yet.")
    else:
        st.dataframe(closed_trades, use_container_width=True)

# --- PAGE 3: VISUAL ANALYTICS ---
elif page == "Visual Analytics":
    st.title("📊 Trading Business Analytics")
    
    if closed_trades.empty:
        st.info("No closed trades yet. Close some positions to see your performance curve.")
    else:
        # DATA PREP FOR CHARTS
        analytics_df = closed_trades.copy()
        
        # Ensure Numeric
        cols = ['ExitPrice', 'BuyPrice', 'Quantity']
        for c in cols: analytics_df[c] = pd.to_numeric(analytics_df[c], errors='coerce').fillna(0)
        
        # Calculate Realized P&L
        analytics_df['Realized_PnL'] = (analytics_df['ExitPrice'] - analytics_df['BuyPrice']) * analytics_df['Quantity']
        
        # --- 1. EQUITY CURVE ---
        st.subheader("📈 Equity Curve (Growth)")
        
        # Sort by Exit Date
        analytics_df['ExitDate'] = pd.to_datetime(analytics_df['ExitDate'])
        equity_df = analytics_df.sort_values(by='ExitDate').dropna(subset=['ExitDate'])
        
        if not equity_df.empty:
            # Cumulative Sum
            equity_df['Cumulative_PnL'] = equity_df['Realized_PnL'].cumsum()
            
            fig_eq = px.line(equity_df, x='ExitDate', y='Cumulative_PnL', markers=True, 
                             title="Account Growth (Realized P&L)")
            fig_eq.update_traces(line_color='#2ca02c', line_width=3)
            fig_eq.add_hline(y=0, line_dash="dash", line_color="gray")
            st.plotly_chart(fig_eq, width="stretch")
        else:
            st.warning("Ensure your closed trades have valid Exit Dates.")

        st.divider()

        # --- 2. CALENDAR HEATMAP ---
        st.subheader("📅 Trading Heatmap")
        
        # Group P&L by Date
        daily_pnl = equity_df.groupby('ExitDate')['Realized_PnL'].sum().reset_index()
        
        if not daily_pnl.empty:
            # Create a full date range grid? No, simple bar heatmap is clearer for traders
            # Green bars for profit days, Red for loss days
            daily_pnl['Color'] = daily_pnl['Realized_PnL'].apply(lambda x: 'Profit' if x > 0 else 'Loss')
            
            fig_cal = px.bar(daily_pnl, x='ExitDate', y='Realized_PnL', color='Color',
                             color_discrete_map={'Profit': '#2ca02c', 'Loss': '#d62728'},
                             title="Daily Net P&L")
            st.plotly_chart(fig_cal, width="stretch")
        
        st.divider()

        # --- 3. SECTOR PIE ---
        st.subheader("Exposure Analysis")
        c1, c2 = st.columns(2)
        with c1:
            # Active Exposure
            active_df = all_trades[all_trades['Status'] == 'OPEN'].copy()
            if not active_df.empty:
                fig_sec = px.pie(active_df, names='Sector', title='Current Sector Allocation', hole=0.4)
                st.plotly_chart(fig_sec, width="stretch")
            else: st.write("No active exposure.")