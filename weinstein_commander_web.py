import streamlit as st
import pandas as pd
import os
import sys
import subprocess
import time
from dhan_auth import ensure_valid_token
from dhanhq import dhanhq
import sqlite3
from datetime import date
from ai_risk_manager import get_market_health, get_noise_risk_stats, get_atr
from ai_grading_engine import get_weinstein_score
import plotly.express as px
import yfinance as yf

# Set page config FIRST
st.set_page_config(page_title="Weinstein Commander Web", page_icon="🦁", layout="wide", initial_sidebar_state="expanded")

# --- 1. CONFIGURATION ---
# Load environment variables
from dotenv import load_dotenv, set_key
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

load_dotenv(override=True) # Reload to get new token if refreshed
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
DB_FILE = "trade_journal_v6.db"

JOURNAL_RENAME_MAP = {
    'symbol': 'Symbol', 'trade_type': 'Type', 'stoploss': 'StopLoss',
    'target': 'Target', 'rationale': 'Rationale', 'timeframe': 'Timeframe',
    'entry_date': 'EntryDate', 'quantity': 'Quantity', 'buy_price': 'BuyPrice',
    'exit_date': 'ExitDate', 'exit_price': 'ExitPrice',
    'exit_reason': 'ExitReason', 'status': 'Status', 'sector': 'Sector',
    'trade_quality': 'Quality', 'compromises': 'Compromises', 
    'lessons': 'Lessons', 'screenshot_path': 'Screenshot',
    'planned_rr': 'PlannedRR', 'ai_analysis': 'AI Analysis'
}

import base64

# --- 2. HELPER FUNCTIONS ---
def get_script_path(filename):
    return os.path.join(os.getcwd(), filename)

def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def launch_script(script_name, args=None, is_streamlit=False):
    """Launches a python script or streamlit app in a new terminal window."""
    try:
        full_path = get_script_path(script_name)
        if not os.path.exists(full_path):
            st.error(f"❌ File not found: {script_name}")
            return

        if is_streamlit:
            # Construct command for Streamlit
            cmd_str = f'streamlit run "{script_name}"'
        else:
            # Construct command for standard Python script
            cmd_str = f'"{sys.executable}" "{script_name}"'
            
        if args:
            cmd_str += f" {args}"
            
        # /k keeps window open, /c closes it
        # Keep open for visual feedback on long running scripts
        mode = "/k" 
        base_folder = os.getcwd()
        
        cmd = f'start cmd {mode} "cd /d "{base_folder}" && {cmd_str}"'
        os.system(cmd)
        st.toast(f"🚀 Launched: {script_name}")
    except Exception as e:
        st.error(f"Failed to launch: {e}")

def get_dhan_balance():
    """Fetches available balance and checks API health."""
    try:
        if not CLIENT_ID or not ACCESS_TOKEN:
            return 0.0, "AUTH MISSING"
        
        dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
        resp = dhan.get_fund_limits()
        
        if isinstance(resp, dict) and resp.get('status') == 'success':
            data = resp.get('data', {})
            # Handle Dhan's common typo 'availabelBalance'
            balance = float(data.get('availabelBalance', data.get('availableBalance', 0.0)))
            return balance, "SYSTEM ONLINE"
        else:
            # Detect expired tokens or API errors
            err_msg = str(resp).lower()
            if "expired" in err_msg or "access token" in err_msg or "unauthorized" in err_msg:
                return 0.0, "AUTH EXPIRED"
            return 0.0, "API OFFLINE"
    except Exception as e:
        return 0.0, f"OFFLINE ({type(e).__name__})"

def load_journal_db():
    conn = None
    try:
        if not os.path.exists(DB_FILE): return pd.DataFrame()
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql("SELECT * FROM journal WHERE status='OPEN'", conn)
        return df.rename(columns=JOURNAL_RENAME_MAP)
    except:
        return pd.DataFrame()
    finally:
        if conn: conn.close()

def load_closed_trades_db():
    conn = None
    try:
        if not os.path.exists(DB_FILE): return pd.DataFrame()
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql("SELECT * FROM journal WHERE status='CLOSED'", conn)
        return df.rename(columns=JOURNAL_RENAME_MAP)
    except:
        return pd.DataFrame()
    finally:
        if conn: conn.close()

# --- 3. CUSTOM STYLING ---

# --- 3. CUSTOM STYLING (ULTRA MODERN 34" OPTIMIZED) ---
def get_img_as_base64(file):
    with open(file, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

# Load Background
# Load Background
bg_str = ""
if os.path.exists("trading_bg_pro.png"):
    bg_img = get_img_as_base64("trading_bg_pro.png")
    bg_str = f', url("data:image/png;base64,{bg_img}")'

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=Inter:wght@300;400;600&display=swap');

    /* --- GLOBAL BACKGROUND --- */
    .stApp {{
        background-image: linear-gradient(rgba(5, 10, 20, 0.85), rgba(5, 10, 20, 0.95)){bg_str};
        background-attachment: fixed;
        background-size: cover;
        font-family: 'Inter', sans-serif;
        color: #e0f2f1;
    }}

    /* --- SIDEBAR (GLASSY & SLIM) --- */
    [data-testid="stSidebar"] {{
        background: rgba(12, 18, 28, 0.65);
        backdrop-filter: blur(25px);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
        min-width: 280px; /* Wider for 34" if needed, but keeping standard for scale */
    }}
    
    /* --- HEADERS (CYBERPUNK STYLE) --- */
    h1, h2, h3 {{
        font-family: 'Rajdhani', sans-serif;
        text-transform: uppercase;
        letter-spacing: 2px;
        background: linear-gradient(90deg, #00f260, #0575E6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 0 30px rgba(0, 242, 96, 0.3);
    }}
    
    /* --- METRICS & CARDS (GLASSMORPHISM) --- */
    div[data-testid="metric-container"], div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {{
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        backdrop-filter: blur(12px);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }}
    
    div[data-testid="metric-container"]:hover, div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"]:hover {{
        transform: translateY(-5px);
        box-shadow: 0 12px 40px 0 rgba(0, 242, 96, 0.1);
        border: 1px solid rgba(0, 242, 96, 0.3);
    }}
    /* --- BUTTONS (NEON GLOW - ULTRA COMPACT FORCE) --- */
    /* Target buttons inside columns specifically */
    div[data-testid="column"] button {{
        background: linear-gradient(135deg, #0f2027 0%, #203a43 100%) !important;
        color: #00f260 !important;
        border: 1px solid rgba(0, 242, 96, 0.4) !important;
        border-radius: 4px !important; /* Sharp technical look */
        font-family: 'Rajdhani', sans-serif !important;
        font-weight: 600 !important;
        font-size: 13px !important; /* Smaller text */
        letter-spacing: 0.5px !important;
        text-transform: uppercase !important;
        padding: 4px 8px !important; /* Minimal padding */
        margin: 2px 0 !important;   /* Minimal margin */
        line-height: 1.2 !important;
        box-shadow: none !important; /* Clean look */
        min-height: 0px !important;
        height: auto !important;
        width: 100% !important;
    }}

    div[data-testid="column"] button:hover {{
        background: linear-gradient(135deg, #00f260 0%, #0575E6 100%) !important;
        color: #000 !important;
        border: 1px solid #00f260 !important;
        box-shadow: 0 0 10px rgba(0, 242, 96, 0.4) !important;
        transform: translateX(3px) !important; /* Slide effect */
    }}

    /* Active State (Primary) */
    div[data-testid="column"] button[kind="primary"] {{
        background: linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%) !important;
        color: #000 !important;
        border: none !important;
        box-shadow: 0 0 8px rgba(0, 201, 255, 0.3) !important;
        font-weight: 700 !important;
    }}

    /* --- WIDE SCREEN OPTIMIZATION & TOP BAR REMOVAL --- */
    .block-container {{
        max-width: 95% !important; 
        padding-top: 0rem !important; /* REDUCED PADDING 0 */
        margin-top: -3rem !important; /* Pull content up */
        padding-bottom: 5rem;
    }}
    
    header {{ 
        visibility: hidden; /* Hide Streamlit's default hamburger menu/header bar */
    }}

    /* --- RADIO BUTTONS (Vertical Sub-Menu) --- */
    div[data-testid="stRadio"] label {{
        background: rgba(15, 32, 39, 0.6) !important;
        border: 1px solid rgba(0, 242, 96, 0.2) !important;
        border-radius: 4px !important;
        padding: 6px 10px !important;
        margin-bottom: 3px !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
        color: #ddd !important;
        font-size: 0.8rem !important;
    }}
    
    div[data-testid="stRadio"] label:hover {{
        background: rgba(0, 242, 96, 0.1) !important;
        border-color: #00f260 !important;
    }}
    
    div[data-testid="stRadio"] label[data-checked="true"] {{
        background: linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%) !important;
        color: #000 !important;
        font-weight: bold !important;
        border: none !important;
        box-shadow: 0 0 10px rgba(0, 242, 96, 0.3) !important;
    }}
    
    /* Hide Radio Circles */
    div[role="radiogroup"] div[data-testid="stMarkdownContainer"] p {{
        margin: 0 !important;
    }}
    div[role="radiogroup"] input {{
        display: none !important;
    }}

    /* --- MAIN NAVIGATION BUTTONS (Fix for White Blocks) --- */
    /* Target ALL buttons inside columns, specifically secondary ones */
    button[kind="secondary"] {{
        background: rgba(20, 30, 40, 0.8) !important;
        color: #00f260 !important; 
        border: 1px solid rgba(0, 242, 96, 0.3) !important;
        border-radius: 4px !important;
        height: auto !important;
        padding: 0.4rem 0.8rem !important;
        font-family: 'Rajdhani', sans-serif !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        transition: all 0.2s ease !important;
    }}
    
    button[kind="secondary"]:hover {{
        border-color: #00f260 !important;
        background: rgba(0, 242, 96, 0.1) !important;
        box-shadow: 0 0 10px rgba(0, 242, 96, 0.2) !important;
        color: #fff !important;
    }}

    /* Active Nav Button (Primary) */
    button[kind="primary"] {{
        background: linear-gradient(90deg, #ff512f, #dd2476) !important; 
        color: #fff !important;
        border: none !important;
        box-shadow: 0 0 15px rgba(221, 36, 118, 0.4) !important;
        font-weight: 700 !important;
    }}
    
</style>
""", unsafe_allow_html=True)


# --- 4. SIDEBAR (NAVIGATION & STATUS) ---

# --- 4. TOP-DOWN LAYOUT (TERMINAL X STYLE) ---

# B. GLOBAL STATUS DECK (Metrics Row)
# Fetches data early to display at top
balance, sys_status = get_dhan_balance()
is_healthy, mkt_ltp, mkt_sma = get_market_health("NSE:CNX500")

# Noise Watchdog Logic
df_active_global = load_journal_db()
if not df_active_global.empty:
    noise_count_g, noise_syms_g = get_noise_risk_stats(df_active_global)
    total_deployed_g = (df_active_global['Quantity'] * df_active_global['BuyPrice']).sum()
else:
    noise_count_g, noise_syms_g = 0, []
    total_deployed_g = 0

# Pre-calculate variables
status_color = "#00f260" if sys_status == "SYSTEM ONLINE" else "#ff4b4b"
h_color = "#00f260" if is_healthy else "#ff4b4b"
h_text = "HEALTHY" if is_healthy else "WEAK"
risk_count = noise_count_g

# --- HEADER & STATUS DECK (COMPACT) ---
# Title & Version - REMOVED NEGATIVE MARGIN TO FIX VISIBILITY
st.markdown(f"""
<div style='display: flex; justify-content: space-between; align-items: center; padding: 10px 20px; background: rgba(5, 10, 20, 0.8); border-bottom: 1px solid rgba(0, 242, 96, 0.2); margin-bottom: 20px; border-radius: 8px;'>
    <div style='text-align: left;'>
        <h2 style='margin:0; font-size: 2.2rem; background: linear-gradient(to right, #00C9FF, #92FE9D); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-shadow: 0 0 20px rgba(0,201,255,0.3);'>COMMANDER JAY</h2>
        <span style='font-family: "Rajdhani"; color: #aaa; font-size: 0.9rem; letter-spacing: 3px;'>PRO TERMINAL v11.0</span>
    </div>
    <div style='text-align: right;'>
        <span style='color: {status_color}; font-weight: bold; font-family: "Rajdhani"; font-size: 1.1rem; letter-spacing: 1px;'>● {sys_status}</span>
        <div style='color: #888; font-size: 0.85rem; margin-top: 4px;'>CAPITAL: <span style='color:#fff'>₹{balance:,.0f}</span></div>
    </div>
</div>
""", unsafe_allow_html=True)

# KPI Row (Slim Layout)
mkt_col, risk_col, cap_col = st.columns(3)

with mkt_col:
    # Nifty 500
    st.markdown(f"""
    <div style='background: rgba(10, 20, 30, 0.4); border-left: 3px solid {h_color}; padding: 8px 12px; border-radius: 4px;'>
        <div style='font-size: 0.7rem; color: #888; letter-spacing: 1px;'>NIFTY 500</div>
        <div style='font-size: 1.1rem; font-weight: bold; color: {h_color};'>{h_text}</div>
    </div>
    """, unsafe_allow_html=True)

with risk_col:
    # Noise Watchdog
    w_color = "#ff4b4b" if risk_count > 0 else "#00f260"
    w_text = f"🚨 {risk_count} AT RISK" if risk_count > 0 else "🛡️ SECURE"
    st.markdown(f"""
    <div style='background: rgba(10, 20, 30, 0.4); border-left: 3px solid {w_color}; padding: 8px 12px; border-radius: 4px;'>
        <div style='font-size: 0.7rem; color: #888; letter-spacing: 1px;'>RISK WATCHDOG</div>
        <div style='font-size: 1.1rem; font-weight: bold; color: {w_color};'>{w_text}</div>
    </div>
    """, unsafe_allow_html=True)

with cap_col:
    # Capital
    c_color = "#00C9FF"
    deployed_pct = 100 - (balance / 500000 * 100) if balance < 500000 else 0
    st.markdown(f"""
    <div style='background: rgba(10, 20, 30, 0.4); border-left: 3px solid {c_color}; padding: 8px 12px; border-radius: 4px;'>
        <div style='font-size: 0.7rem; color: #888; letter-spacing: 1px;'>DEPLOYMENT</div>
        <div style='font-size: 1.1rem; font-weight: bold; color: {c_color};'>{deployed_pct:.1f}%</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# C. HORIZONTAL NAVIGATION DECK (Restored)
# Initialize Session State
if 'page' not in st.session_state:
    st.session_state.page = "DASHBOARD"

# 6 Columns for 6 Menu Items
nav_cols = st.columns(6)
nav_options = ["DASHBOARD", "HUNTER", "WATCHLIST", "COMMAND", "AI LAB", "📓 JOURNAL"]

for i, option in enumerate(nav_options):
    with nav_cols[i]:
        # Highlight active button
        btn_type = "primary" if st.session_state.page == option else "secondary"
        if st.button(option, key=f"nav_{option}", width="stretch", type=btn_type):
            if option == "📓 JOURNAL":
                launch_script("dhan_journal_v6.py", is_streamlit=True)
            else:
                st.session_state.page = option
                st.rerun()

page = st.session_state.page
st.markdown("---")

# Session Warning
if sys_status == "AUTH EXPIRED":
    st.warning("🚨 **DHAN TOKEN EXPIRED**\nPlease update the `.env` file or re-run `dhan_auth.py`.")
    
st.markdown(f"<div style='text-align: right; font-size: 0.7rem; color: #666;'>COMMANDER JAY v11.0 // {sys_status}</div>", unsafe_allow_html=True)


# --- 5. PAGE CONTENT ---

if page == "DASHBOARD":
    st.markdown("<h1 style='font-size: 3rem; margin-bottom: 10px;'>📊 MISSION DASHBOARD</h1>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 1.2rem; color: #aaa; margin-bottom: 30px;'>REAL-TIME MARKET INTELLIGENCE // SECTOR RADAR // RISK AUDIT</p>", unsafe_allow_html=True)
    
    # Reuse the globally fetched data
    df_active = df_active_global
    
    # Populate Live Map for Heatmap (if not already done efficiently, but for now simple checks)
    live_map = {}
    if not df_active.empty:
        for sym in df_active['Symbol'].unique():
            try:
                ticker = yf.Ticker(f"{sym}.NS")
                live_map[sym] = {'LTP': ticker.history(period="1d")['Close'].iloc[-1]}
            except:
                live_map[sym] = {'LTP': 0.0}
    
    # KPI Row (Wide Layout)
    col1, col2, col3 = st.columns(3)
    
    with col1:
        with st.container(border=True):
            st.markdown("### 📝 MARKET BRIEFING")
            st.caption("Daily strategic analysis and sector rotation.")
            st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
            if st.button("GENERATE REPORT", width="stretch"):
                launch_script("workflow_strategic_briefing.py")
            st.markdown("<div style='text-align: right; color: #555; font-size: 0.8rem; margin-top: 10px;'>STATUS: READY</div>", unsafe_allow_html=True)

    with col2:
        with st.container(border=True):
            st.markdown("### 📡 SECTOR RADAR")
            st.caption("RRG Relative Strength Analysis vs Index.")
            st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
            if st.button("LAUNCH RADAR", width="stretch"):
                launch_script("sector_radar.py")
            st.markdown("<div style='text-align: right; color: #555; font-size: 0.8rem; margin-top: 10px;'>TARGET: NIFTY 50/500</div>", unsafe_allow_html=True)

    with col3:
        with st.container(border=True):
            st.markdown("### 🏥 PORTFOLIO HEALTH")
            st.caption("Risk assessment and exposure audit.")
            st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
            if st.button("LAUNCH ANALYTICS", width="stretch"):
                launch_script("portfolio_analytics.py", is_streamlit=True)
            st.markdown("<div style='text-align: right; color: #555; font-size: 0.8rem; margin-top: 10px;'>LIVE CENTER: ACTIVE</div>", unsafe_allow_html=True)

    st.markdown("---")
    
    # --- PORTFOLIO HEATMAP (CAPITAL ALLOCATION) ---
    if not df_active.empty:
        st.markdown("### 🗺️ PORTFOLIO HEATMAP (CAPITAL ALLOCATION)")
        # Prepare data for Treemap
        heatmap_df = df_active.copy()
        heatmap_df['Sector'] = heatmap_df['Sector'].fillna("Unassigned").replace('', 'Unassigned')
        heatmap_df['Deployment'] = heatmap_df['Quantity'] * heatmap_df['BuyPrice']
        
        # Calculate PnL % using populated live_map
        heatmap_df['PnL_Pct'] = [(live_map.get(s, {}).get('LTP', p) - p) / p * 100 if p > 0 else 0 
                                 for s, p in zip(heatmap_df['Symbol'], heatmap_df['BuyPrice'])]
        
        fig = px.treemap(
            heatmap_df, 
            path=[px.Constant("Portfolio"), 'Sector', 'Symbol'], 
            values='Deployment',
            color='PnL_Pct',
            color_continuous_scale='RdYlGn',
            color_continuous_midpoint=0,
            hover_data=['Quantity', 'BuyPrice'],
            title="Capital Deployment by Sector & Symbol (Size=Capital, Color=P&L%)"
        )
        fig.update_layout(margin=dict(t=30, l=10, r=10, b=10), height=500)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")

    # --- ALPHA BENCHMARKING (vs NIFTY 500) ---
    st.markdown("### 📈 ALPHA BENCHMARKING (VS NIFTY 500)")
    df_closed = load_closed_trades_db()
    
    if not df_closed.empty:
        try:
            # 1. Prepare Portfolio Curve
            df_closed['ExitDate'] = pd.to_datetime(df_closed['ExitDate'])
            df_closed = df_closed.sort_values('ExitDate')
            
            # Use Realized PnL Calculation
            df_closed['PnL'] = (pd.to_numeric(df_closed['ExitPrice'], errors='coerce').fillna(0) - 
                                pd.to_numeric(df_closed['BuyPrice'], errors='coerce').fillna(0)) * \
                               pd.to_numeric(df_closed['Quantity'], errors='coerce').fillna(0)
            
            portfolio_curve = df_closed.groupby('ExitDate')['PnL'].sum().cumsum().reset_index()
            portfolio_curve.columns = ['Date', 'Portfolio_Profit']
            
            start_date = portfolio_curve['Date'].min()
            end_date = portfolio_curve['Date'].max()
            
            # 2. Prepare Benchmark Curve (Nifty 500 with Fallback)
            # Fallback to Nifty 50 (^NSEI) since CNX500 is unreliable on Yahoo Finance
            nifty500 = yf.download("^NSEI", start=start_date - pd.Timedelta(days=7), end=end_date + pd.Timedelta(days=1), progress=False)
            if nifty500.empty:
                # Fallback to Nifty 50 if 500 is down/delisted
                nifty500 = yf.download("^NSEI", start=start_date - pd.Timedelta(days=7), end=end_date + pd.Timedelta(days=1), progress=False)
            
            if not nifty500.empty:
                nifty500 = nifty500['Close'].reset_index()
                nifty500.columns = ['Date', 'Nifty_Close']
                nifty500['Date'] = pd.to_datetime(nifty500['Date']).dt.tz_localize(None)
                
                # Normalize starting points for comparison (as % change)
                first_nifty = nifty500['Nifty_Close'].iloc[0]
                nifty500['Benchmark %'] = (nifty500['Nifty_Close'] - first_nifty) / first_nifty * 100
                
                # For Portfolio, we need to map profit to % change of an assumed starting capital (e.g. 10L)
                starting_capital = 1000000 # Assume 10L if not defined
                portfolio_curve['Portfolio %'] = portfolio_curve['Portfolio_Profit'] / starting_capital * 100
                
                # Merge for plotting
                comparison_df = pd.merge_asof(nifty500, portfolio_curve, on='Date')
                
                fig_alpha = px.line(comparison_df, x='Date', y=['Benchmark %', 'Portfolio %'], 
                                   title="Relative Performance: Portfolio vs Nifty 500 (Base=0%)")
                fig_alpha.update_layout(yaxis_title="Percent Change (%)", hovermode="x unified")
                st.plotly_chart(fig_alpha, use_container_width=True)
            else:
                st.warning("Could not fetch Nifty 500 data for benchmarking.")
        except Exception as e:
            st.error(f"Error generating Alpha Benchmarking: {e}")
    else:
        st.info("No closed trades found to generate performance benchmark.")

    st.markdown("---")

    # Wide Quick Action Bar
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown("### ⚡ AUTO-PILOT PROTOCOL")
            st.write("Execute full pipeline: Scanners -> Fundamentals -> Golden Matching -> Watchlist Sync")
        with c2:
            st.markdown("<div style='height: 15px'></div>", unsafe_allow_html=True)
            if st.button("🚀 INITIATE", type="primary", width="stretch"):
                launch_script("run_pipeline.py")


elif page == "HUNTER":
    # Main Header
    st.markdown("<h1 style='font-size: 2.5rem;'>🦅 MARKET HUNTER</h1>", unsafe_allow_html=True)
    st.markdown("Identify high-probability setups using multi-factor analysis.")
    st.markdown("---")
    
    # Initialize Tab State
    if 'hunter_tab' not in st.session_state:
        st.session_state.hunter_tab = "SCANNERS"
        
    # LAYOUT: Left Vertical Menu (Adjusted for visibility) | Right Content
    menu_col, content_col = st.columns([1, 6])
    
    with menu_col:
        st.markdown("#### 📡 TARGETING")
        st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)
        
        # Vertical Radio Menu
        hunter_nav_map = {
            "🔍 SCANNERS": "SCANNERS", 
            "⬇️ ENRICHMENT": "ENRICHMENT", 
            "✨ SELECTION": "SELECTION"
        }
        
        # Determine index
        opts = list(hunter_nav_map.keys())
        curr_idx = 0
        current_val = st.session_state.hunter_tab
        for i, k in enumerate(hunter_nav_map.values()):
            if k == current_val:
                curr_idx = i
                break
        
        selected_opt = st.radio("Hunter Nav", opts, index=curr_idx, label_visibility="collapsed")
        
        # Update State
        st.session_state.hunter_tab = hunter_nav_map[selected_opt]

    # Content Area
    with content_col:
        active_tab = st.session_state.hunter_tab
        
        if active_tab == "SCANNERS":
            with st.container(border=True):
                st.subheader("Chartink Scanners")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("##### Positional Strategies")
                    if st.button("🚀 Stage 2 Hunter", width="stretch"):
                        launch_script("chartink_scanner_pro.py", "1")
                    if st.button("🐣 Early Birds (Accumulation)", width="stretch"):
                        launch_script("chartink_scanner_pro.py", "3")
                with c2:
                    st.markdown("##### Swing Strategies")
                    if st.button("📉 Stage 2 Pullback", width="stretch"):
                        launch_script("chartink_scanner_pro.py", "2")
                    if st.button("⚡ Strong Leaders", width="stretch"):
                        launch_script("chartink_scanner_pro.py", "4")
            
        elif active_tab == "ENRICHMENT":
            with st.container(border=True):
                st.subheader("Fundamental Data")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("⬇️ Fetch Screener.in Data", width="stretch"):
                        launch_script("screener_fetcher.py")
                with c2:
                    if st.button("⚙️ Process HTML to CSV", width="stretch"):
                        launch_script("screener_processor.py")
            
        elif active_tab == "SELECTION":
            with st.container(border=True):
                st.subheader("Golden Matcher Engine")
                st.info("Combines Technical Scans with Fundamental Filters to find '5-Star' setups.")
                if st.button("✨ RUN GOLDEN MATCHER", type="primary", width="stretch"):
                    launch_script("brute_force_match_pro.py")
                
                st.divider()
                st.subheader("🏆 AI Top Picks Preview")
                
                # Category Selection for Preview
                preview_cat = st.selectbox("Select Strategy to Preview:", 
                                         ["Stage 2 Hunter", "Stage 2 Pullback", "Early Birds", "Strong Leaders"])
                
                # Map selection to file
                cat_map = {
                    "Stage 2 Hunter": "FINAL_Hunter_Picks.csv",
                    "Stage 2 Pullback": "FINAL_Pullback_Picks.csv",
                    "Early Birds": "FINAL_EarlyBird_Picks.csv",
                    "Strong Leaders": "FINAL_Leader_Picks.csv"
                }
                
                target_preview = cat_map.get(preview_cat)
                
                if target_preview and os.path.exists(target_preview):
                    try:
                        df_res = pd.read_csv(target_preview)
                        if not df_res.empty:
                            # Reorder to show AI columns first
                            cols = df_res.columns.tolist()
                            ai_cols = ['Symbol', 'Conviction', 'AI_Catalyst']
                            other_cols = [c for c in cols if c not in ai_cols]
                            display_cols = [c for c in ai_cols if c in cols] + other_cols
                            
                            st.dataframe(df_res[display_cols].head(15), use_container_width=True)
                        else:
                            st.info(f"No '5-Star' matches found in the latest {preview_cat} scan.")
                    except Exception as e:
                        st.error(f"Error loading preview: {e}")
                else:
                    st.info(f"Run the Golden Matcher to see {preview_cat} ranked picks.")


elif page == "WATCHLIST":
    # Header
    st.markdown("<h1 style='font-size: 2.5rem;'>📋 WATCHLIST SYNC</h1>", unsafe_allow_html=True)
    st.markdown("Synchronize your selected setups across all platforms.")
    st.markdown("---")

    # Initialize Context State
    if 'watchlist_tab' not in st.session_state:
        st.session_state.watchlist_tab = "GENERATION"

    # LAYOUT: Menu (15%) | Content (85%)
    menu_col, content_col = st.columns([1, 6])

    with menu_col:
        st.markdown("#### ⚙️ ACTIONS")
        st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)
        
        wl_opts = ["📂 GENERATE", "☁️ SYNC CLOUD"]
        wl_idx = 0 if st.session_state.watchlist_tab == "GENERATION" else 1
        
        sel_wl = st.radio("WL Nav", wl_opts, index=wl_idx, label_visibility="collapsed")
        
        if sel_wl == "📂 GENERATE":
            st.session_state.watchlist_tab = "GENERATION"
        else:
            st.session_state.watchlist_tab = "SYNC"

    with content_col:
        active_tab = st.session_state.watchlist_tab
        
        if active_tab == "GENERATION":
            with st.container(border=True):
                st.subheader("1. Local Generation")
                st.write("Generate clean CSVs for local analysis.")
                if st.button("📂 Generate CSVs (Local)", use_container_width=True):
                    import watchlist_manager
                    watchlist_manager.generate_tradingview_files()
                    st.success("Watchlists generated in /WL folder")
                    
        elif active_tab == "SYNC":
            with st.container(border=True):
                st.subheader("2. External Cloud Sync")
                st.write("Push lists to cloud platforms.")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("☁️ Sync to Strike.Money", use_container_width=True):
                        launch_script("strike_automation.py", "--mode=watchlist")
                with c2:
                    if st.button("☁️ Sync to TradingView", use_container_width=True):
                        launch_script("tradingview_automation_v2.py")
                with c3:
                    if st.button("⚡ MASTER SYNC (All)", type="primary", use_container_width=True):
                        launch_script("master_portfolio_sync.py")


elif page == "COMMAND":
    # Header
    st.markdown("<h1 style='font-size: 2.5rem;'>⚔️ COMMAND CENTER</h1>", unsafe_allow_html=True)
    st.markdown("Active trade management and execution protocols.")
    st.markdown("---")

    # Initialize Context
    if 'command_tab' not in st.session_state:
        st.session_state.command_tab = "ACTIVE_OPS"

    # LAYOUT: Menu (15%) | Content (85%)
    menu_col, content_col = st.columns([1, 6])

    with menu_col:
        st.markdown("#### 🎮 CONTROLS")
        st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)
        
        cmd_opts = ["⚡ ACTIVE OPS", "📓 LEDGER"]
        cmd_idx = 0 if st.session_state.command_tab == "ACTIVE_OPS" else 1
        
        sel_cmd = st.radio("Cmd Nav", cmd_opts, index=cmd_idx, label_visibility="collapsed")
        
        if sel_cmd == "⚡ ACTIVE OPS":
            st.session_state.command_tab = "ACTIVE_OPS"
        else:
            st.session_state.command_tab = "LEDGER"

    with content_col:
        active_tab = st.session_state.command_tab
        
        if active_tab == "ACTIVE_OPS":
            with st.container(border=True):
                st.subheader("Active Operations")
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("🎯 Sniper Entry (AI v2)", use_container_width=True, help="Order execution with Institutional AI analysis."):
                        launch_script("sniper_trigger.py")
                with c2:
                    if st.button("🛡️ GTT Auto-Shield", use_container_width=True, help="Auto-protect holdings using Journal levels."):
                        launch_script("gtt_auto_shield.py")
                with c3:
                    if st.button("📱 Telegram Sentinel", use_container_width=True, help="Active market monitoring via Mobile."):
                        launch_script("telegram_sentinel.py")
                        
                st.divider()
                st.write("External Apps")
                if st.button("📂 Open Full Journal App", use_container_width=True):
                    launch_script("dhan_journal_v6.py", is_streamlit=True)

        elif active_tab == "LEDGER":
            with st.container(border=True):
                st.subheader("📓 Live Trade Ledger")
                # Embedded Journal View
                df_journal = load_journal_db()
                if not df_journal.empty:
                    st.dataframe(
                        df_journal[['Symbol', 'Type', 'BuyPrice', 'Quantity', 'Status', 'Sector']], 
                        use_container_width=True,
                        height=500,
                        hide_index=True
                    )
                else:
                    st.info("No open trades found in the system.")



elif page == "AI LAB":
    # Header
    st.markdown("<h1 style='font-size: 2.5rem;'>🧠 AI LABORATORY</h1>", unsafe_allow_html=True)
    st.markdown("Advanced Generative AI workflows and automation.")
    st.markdown("---")

    # Initialize Context
    if 'ailab_tab' not in st.session_state:
        st.session_state.ailab_tab = "PRE_FLIGHT"

    # LAYOUT: Menu (15%) | Content (85%)
    menu_col, content_col = st.columns([1, 6])

    with menu_col:
        st.markdown("#### 🧪 LAB BENCH")
        st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)
        
        ai_nav_map = {
            "🛫 PRE-FLIGHT": "PRE_FLIGHT",
            "⚡ GENERATIVE": "GENERATIVE",
            "⚙️ WORKFLOWS": "WORKFLOWS"
        }
        
        ai_opts = list(ai_nav_map.keys())
        ai_idx = 0
        for i, val in enumerate(ai_nav_map.values()):
            if val == st.session_state.ailab_tab:
                ai_idx = i
                break
                
        # Unique Key for AI Nav to prevent collision
        sel_ai = st.radio("AI Nav", ai_opts, index=ai_idx, label_visibility="collapsed", key="ai_nav_radio")
        st.session_state.ailab_tab = ai_nav_map[sel_ai]

    with content_col:
        active_tab = st.session_state.ailab_tab
        
        if active_tab == "PRE_FLIGHT":
            # --- AI-TRADE PROPOSER ---
            with st.container(border=True):
                st.subheader("🎯 AI-Trade Proposer (Pre-flight Check)")
                st.write("Score and size a new trade before execution.")
                
                p1, p2, p3 = st.columns([2, 1, 1])
                with p1:
                    prop_sym = st.text_input("Ticker Symbol", key="prop_sym").upper()
                with p2:
                    prop_entry = st.number_input("Entry Price", min_value=0.0, step=0.1, key="prop_entry")
                with p3:
                    prop_risk = st.number_input("Risk (₹)", value=5000, step=500, key="prop_risk")
                    
                if st.button("✨ RUN ANALYSIS", type="primary", use_container_width=True, key="btn_run_analysis"):
                    if not prop_sym:
                        st.error("Enter ticker.")
                    else:
                        with st.spinner(f"Analyzing {prop_sym}..."):
                            # 1. Fetch Technicals
                            atr = get_atr(prop_sym)
                            try:
                                ticker = yf.Ticker(f"{prop_sym}.NS")
                                ltp = ticker.history(period="1d")['Close'].iloc[-1]
                            except:
                                ltp = prop_entry if prop_entry > 0 else 0
                            
                            # 2. Score via Gemini
                            rating_res = get_weinstein_score(prop_sym, "Unknown", ltp, prop_entry if prop_entry > 0 else ltp)
                            
                            # 3. Calculate Sizing & Stops
                            suggested_sl = ltp - (2.0 * atr) if atr > 0 else ltp * 0.95
                            risk_per_share = ltp - suggested_sl
                            qty = int(prop_risk / risk_per_share) if risk_per_share > 0 else 0
                            
                            # Display Results
                            st.divider()
                            r1, r2, r3 = st.columns(3)
                            r1.metric("Weinstein Grade", rating_res['rating'])
                            r2.metric("Suggested SL", f"₹{suggested_sl:.2f}")
                            r3.metric("Rec. Quantity", f"{qty} shares")
                            st.info(f"**AI Rationale:** {rating_res['reason']}")

        elif active_tab == "GENERATIVE":
            with st.container(border=True):
                st.subheader("Generative Analysis")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🤖 AI Post-Trade Autopsy", use_container_width=True, key="btn_ai_autopsy"):
                        launch_script("portfolio_analytics.py", is_streamlit=True)
                    if st.button("🤖 Auto-Plan Journal", use_container_width=True, key="btn_ai_journal"):
                        launch_script("dhan_journal_v6.py", is_streamlit=True)
                
                with c2:
                    if st.button("🤖 Standalone Prompt Gen", use_container_width=True, key="btn_ai_prompt"):
                        launch_script("generate_prompt_standalone.py")
                
                st.divider()
                if st.button("🗑️ Clear AI Cache", help="Fetch fresh data on next run.", key="btn_clear_ai_cache"):
                    if os.path.exists("ai_cache.json"):
                        os.remove("ai_cache.json")
                        st.success("AI Cache Cleared!")
                    else:
                        st.info("Cache is already empty.")

        elif active_tab == "WORKFLOWS":
            st.markdown("### ⚡ Workflow Automation")
            with st.container(border=True):
                st.write("Execute complex multi-stage pipelines autonomously.")
                if st.button("⚡ Run Full Auto-Pilot", use_container_width=True, key="btn_run_pipeline"):
                    launch_script("run_pipeline.py")
