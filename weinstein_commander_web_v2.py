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
import base64

# Set page config FIRST
st.set_page_config(
    page_title="Weinstein Commander Web",
    page_icon="🦁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 1. CONFIGURATION ---
from dotenv import load_dotenv, set_key
load_dotenv(override=True)

@st.cache_resource(ttl=3600)
def check_auth_cached():
    try:
        print("⏳ Checking Dhan API Token...")
        return ensure_valid_token()
    except Exception as e:
        print(f"⚠️ Warning: Auto-token refresh failed: {e}")
        return None

check_auth_cached()
load_dotenv(override=True)

CLIENT_ID    = os.getenv("DHAN_CLIENT_ID")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
DB_FILE      = "trade_journal_v6.db"

JOURNAL_RENAME_MAP = {
    'symbol': 'Symbol', 'trade_type': 'Type', 'stoploss': 'StopLoss',
    'target': 'Target', 'rationale': 'Rationale', 'timeframe': 'Timeframe',
    'entry_date': 'EntryDate', 'quantity': 'Quantity', 'buy_price': 'BuyPrice',
    'exit_date': 'ExitDate', 'exit_price': 'ExitPrice', 'exit_reason': 'ExitReason',
    'status': 'Status', 'sector': 'Sector', 'trade_quality': 'Quality',
    'compromises': 'Compromises', 'lessons': 'Lessons',
    'screenshot_path': 'Screenshot', 'planned_rr': 'PlannedRR',
    'ai_analysis': 'AI Analysis'
}

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
            cmd_str = f'streamlit run "{script_name}"'
        else:
            cmd_str = f'"{sys.executable}" "{script_name}"'
        if args:
            cmd_str += f" {args}"
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
            balance = float(data.get('availabelBalance', data.get('availableBalance', 0.0)))
            return balance, "SYSTEM ONLINE"
        else:
            err_msg = str(resp).lower()
            if "expired" in err_msg or "access token" in err_msg or "unauthorized" in err_msg:
                return 0.0, "AUTH EXPIRED"
            return 0.0, "API OFFLINE"
    except Exception as e:
        return 0.0, f"OFFLINE ({type(e).__name__})"

def load_journal_db():
    conn = None
    try:
        if not os.path.exists(DB_FILE):
            return pd.DataFrame()
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
        if not os.path.exists(DB_FILE):
            return pd.DataFrame()
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql("SELECT * FROM journal WHERE status='CLOSED'", conn)
        return df.rename(columns=JOURNAL_RENAME_MAP)
    except:
        return pd.DataFrame()
    finally:
        if conn: conn.close()

def get_img_as_base64(file):
    with open(file, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

# --- 3. CUSTOM STYLING ---
bg_str = ""
if os.path.exists("trading_bg_pro.png"):
    bg_img = get_img_as_base64("trading_bg_pro.png")
    bg_str = f', url("data:image/png;base64,{bg_img}")'

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=Inter:wght@300;400;600&display=swap');

/* ── GLOBAL ── */
.stApp {{
    background-image: linear-gradient(rgba(5,10,20,0.92), rgba(5,10,20,0.97)){bg_str};
    background-attachment: fixed; background-size: cover;
    font-family: 'Inter', sans-serif; color: #e0f2f1;
}}
.block-container {{
    max-width: 98% !important;
    padding: 0.5rem 1.2rem 4rem !important;
}}
header {{ visibility: hidden; }}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {{
    background: rgba(8,14,24,0.80);
    backdrop-filter: blur(20px);
    border-right: 1px solid rgba(0,242,96,0.08);
}}

/* ── TOPBAR ── */
.wc-topbar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 18px;
    margin-bottom: 8px;
    background: rgba(5,10,20,0.88);
    border-bottom: 1px solid rgba(0,242,96,0.18);
    border-radius: 8px;
}}
.wc-title {{
    font-family: 'Rajdhani', sans-serif;
    font-size: 1.7rem; font-weight: 700; letter-spacing: 1px;
    background: linear-gradient(to right, #00C9FF, #92FE9D);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}}
.wc-subtitle {{
    font-size: 0.68rem; color: #555; letter-spacing: 3px; margin-top: 1px;
    font-family: 'Rajdhani', sans-serif; text-transform: uppercase;
}}
.wc-status-pill {{
    display: inline-block; padding: 3px 12px; border-radius: 20px;
    font-family: 'Rajdhani', sans-serif; font-size: 0.78rem; font-weight: 700;
    letter-spacing: 1px;
}}
.wc-online  {{ background: rgba(0,242,96,0.10); color: #00f260; border: 1px solid rgba(0,242,96,0.40); }}
.wc-offline {{ background: rgba(255,75,75,0.10); color: #ff4b4b; border: 1px solid rgba(255,75,75,0.40); }}
.wc-capital {{
    font-size: 1.05rem; font-weight: 700; color: #fff;
    font-family: 'Rajdhani', sans-serif; margin-top: 3px;
}}

/* ── KPI STRIP ── */
.kpi-card {{
    background: rgba(12,20,34,0.65);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px; padding: 9px 14px; height: 60px;
    display: flex; flex-direction: column; justify-content: center;
    transition: border-color 0.25s, transform 0.25s;
}}
.kpi-card:hover {{
    border-color: rgba(0,242,96,0.30); transform: translateY(-2px);
}}
.kpi-label {{
    font-size: 0.60rem; color: #555;
    letter-spacing: 2px; text-transform: uppercase;
}}
.kpi-value {{
    font-size: 1.05rem; font-weight: 700;
    font-family: 'Rajdhani', sans-serif; margin-top: 2px;
}}

/* ── TOP NAV BUTTONS (DASHBOARD / HUNTER / ...) ── */
[data-testid="column"] button {{
    background: linear-gradient(135deg, #0f2027 0%, #203a43 100%) !important;
    color: #00f260 !important;
    border: 1px solid rgba(0,242,96,0.35) !important;
    border-radius: 5px !important;
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 600 !important; font-size: 0.80rem !important;
    letter-spacing: 1px !important; text-transform: uppercase !important;
    padding: 6px 10px !important; width: 100% !important;
    transition: all 0.2s ease !important;
}}
[data-testid="column"] button:hover {{
    background: linear-gradient(135deg, #00f260 0%, #0575E6 100%) !important;
    color: #000 !important; border-color: #00f260 !important;
    box-shadow: 0 0 10px rgba(0,242,96,0.35) !important;
    transform: translateX(2px) !important;
}}
/* Active page button */
[data-testid="column"] button[kind="primary"] {{
    background: linear-gradient(90deg, #ff512f, #dd2476) !important;
    color: #fff !important; border: none !important;
    box-shadow: 0 0 14px rgba(221,36,118,0.35) !important;
    font-weight: 700 !important;
}}

/* ── SECTION CARDS ── */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: rgba(12,20,34,0.55) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    transition: border-color 0.25s, transform 0.25s !important;
}}
[data-testid="stVerticalBlockBorderWrapper"]:hover {{
    border-color: rgba(0,242,96,0.22) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 28px rgba(0,242,96,0.06) !important;
}}

/* ── HEADINGS ── */
h1, h2, h3 {{
    font-family: 'Rajdhani', sans-serif !important;
    text-transform: uppercase !important; letter-spacing: 2px !important;
    background: linear-gradient(90deg, #00f260, #0575E6);
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    text-shadow: 0 0 24px rgba(0,242,96,0.20) !important;
}}

/* ── SIDEBAR RADIO ── */
[data-testid="stRadio"] label {{
    background: rgba(12,20,34,0.55) !important;
    border: 1px solid rgba(0,242,96,0.15) !important;
    border-radius: 5px !important; padding: 6px 10px !important;
    margin-bottom: 3px !important; font-size: 0.78rem !important;
    color: #aaa !important; cursor: pointer !important;
    transition: all 0.2s ease !important;
}}
[data-testid="stRadio"] label:hover {{
    background: rgba(0,242,96,0.08) !important;
    border-color: #00f260 !important; color: #fff !important;
}}
[data-testid="stRadio"] label[data-checked="true"] {{
    background: linear-gradient(90deg, rgba(0,201,255,0.15), rgba(146,254,157,0.15)) !important;
    color: #00f260 !important; font-weight: bold !important;
    border-color: rgba(0,242,96,0.50) !important;
    box-shadow: 0 0 8px rgba(0,242,96,0.15) !important;
}}
[role="radiogroup"] input {{ display: none !important; }}
[role="radiogroup"] [data-testid="stMarkdownContainer"] p {{ margin: 0 !important; }}

/* ── PRIMARY BUTTON ── */
button[kind="primary"] {{
    background: linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%) !important;
    color: #000 !important; border: none !important;
    border-radius: 5px !important;
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 700 !important; font-size: 0.80rem !important;
    letter-spacing: 1px !important; text-transform: uppercase !important;
    box-shadow: 0 0 12px rgba(0,201,255,0.25) !important;
}}

/* ── METRICS ── */
[data-testid="metric-container"] {{
    background: rgba(12,20,34,0.55) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important; padding: 10px 14px !important;
}}
[data-testid="metric-container"] label {{
    font-size: 0.65rem !important; color: #666 !important;
    letter-spacing: 2px !important; text-transform: uppercase !important;
}}
[data-testid="metric-container"] [data-testid="stMetricValue"] {{
    font-family: 'Rajdhani', sans-serif !important;
    font-size: 1.25rem !important; font-weight: 700 !important;
}}

/* ── DATAFRAME ── */
[data-testid="stDataFrame"] {{
    border: 1px solid rgba(0,242,96,0.12) !important;
    border-radius: 8px !important;
}}

/* ── DIVIDER ── */
hr {{ border-color: rgba(255,255,255,0.06) !important; margin: 6px 0 !important; }}

/* ── TOAST ── */
[data-testid="stToast"] {{
    background: rgba(8,14,24,0.95) !important;
    border: 1px solid rgba(0,242,96,0.30) !important;
    border-radius: 8px !important;
}}

/* ── WIDE SCREEN ── */
.block-container {{ padding-top: 0.5rem !important; }}
</style>
""", unsafe_allow_html=True)

# --- 4. DATA LOAD ---
balance, sys_status = get_dhan_balance()
is_healthy, mkt_ltp, mkt_sma = get_market_health("NSE:CNX500")
df_active_global = load_journal_db()

if not df_active_global.empty:
    noise_count_g, noise_syms_g = get_noise_risk_stats(df_active_global)
    total_deployed_g = (df_active_global['Quantity'] * df_active_global['BuyPrice']).sum()
else:
    noise_count_g, noise_syms_g = 0, []
    total_deployed_g = 0

status_color = "#00f260" if sys_status == "SYSTEM ONLINE" else "#ff4b4b"
h_color      = "#00f260" if is_healthy else "#ff4b4b"
h_text       = "HEALTHY" if is_healthy else "WEAK"
risk_count   = noise_count_g
status_cls   = "wc-online" if sys_status == "SYSTEM ONLINE" else "wc-offline"

# --- TOPBAR ---
st.markdown(f"""
<div class="wc-topbar">
  <div>
    <div class="wc-title">🦁 WEINSTEIN COMMANDER</div>
    <div class="wc-subtitle">REAL-TIME MARKET INTELLIGENCE // SECTOR RADAR // RISK AUDIT</div>
  </div>
  <div style="text-align:right">
    <span class="wc-status-pill {status_cls}">{sys_status}</span>
    <div class="wc-capital">CAPITAL &nbsp;₹{balance:,.0f}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# --- KPI STRIP (3 original + 2 bonus) ---
k1, k2, k3, k4, k5 = st.columns(5)
w_color = "#ff4b4b" if risk_count > 0 else "#00f260"
w_text  = f"{risk_count} AT RISK" if risk_count > 0 else "SECURE"
deployed_pct = (1 - balance / 500000) * 100 if balance < 500000 else 0

with k1:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">NIFTY 500</div><div class="kpi-value" style="color:{h_color}">{h_text}</div></div>', unsafe_allow_html=True)
with k2:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">RISK WATCHDOG</div><div class="kpi-value" style="color:{w_color}">{w_text}</div></div>', unsafe_allow_html=True)
with k3:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">DEPLOYMENT</div><div class="kpi-value" style="color:#00C9FF">{deployed_pct:.1f}%</div></div>', unsafe_allow_html=True)
with k4:
    open_pos = len(df_active_global) if not df_active_global.empty else 0
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">OPEN POSITIONS</div><div class="kpi-value" style="color:#92FE9D">{open_pos}</div></div>', unsafe_allow_html=True)
with k5:
    st.markdown(f'<div class="kpi-card"><div class="kpi-label">TOTAL DEPLOYED</div><div class="kpi-value" style="color:#f7b731">₹{total_deployed_g:,.0f}</div></div>', unsafe_allow_html=True)

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# --- SESSION STATE INIT ---
if 'page'         not in st.session_state: st.session_state.page         = 'DASHBOARD'
if 'huntertab'    not in st.session_state: st.session_state.huntertab    = 'SCANNERS'
if 'watchlisttab' not in st.session_state: st.session_state.watchlisttab = 'GENERATION'
if 'commandtab'   not in st.session_state: st.session_state.commandtab   = 'ACTIVEOPS'
if 'ailabtab'     not in st.session_state: st.session_state.ailabtab     = 'PREFLIGHT'

# --- TOP NAV BAR (exact original pages) ---
nav_cols = st.columns(6)
nav_options = ['DASHBOARD', 'HUNTER', 'WATCHLIST', 'COMMAND', 'AI LAB', 'JOURNAL']
for i, option in enumerate(nav_options):
    with nav_cols[i]:
        btn_type = "primary" if st.session_state.page == option else "secondary"
        if st.button(option, key=f"nav_{option}", use_container_width=True, type=btn_type):
            if option == 'JOURNAL':
                launch_script("dhan_journal_v6.py", is_streamlit=True)
            else:
                st.session_state.page = option
                st.rerun()

st.divider()

page = st.session_state.page

if sys_status == "AUTH EXPIRED":
    st.warning("⚠️ DHAN TOKEN EXPIRED — update the .env file or re-run dhan_auth.py.", icon="🔐")

st.markdown(f'<div style="text-align:right;font-size:0.65rem;color:#333;">COMMANDER JAY v11.0 &nbsp;·&nbsp; {sys_status}</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════
#  PAGE: DASHBOARD
# ════════════════════════════════════════════
if page == 'DASHBOARD':
    st.markdown("# MISSION DASHBOARD")
    st.markdown('<p style="font-size:1.1rem;color:#aaa;margin-bottom:20px;">REAL-TIME MARKET INTELLIGENCE // SECTOR RADAR // RISK AUDIT</p>', unsafe_allow_html=True)

    df_active = df_active_global

    live_map = {}
    if not df_active.empty:
        for sym in df_active['Symbol'].unique():
            try:
                ticker = yf.Ticker(f"{sym}.NS")
                live_map[sym] = {'LTP': ticker.history(period="1d")['Close'].iloc[-1]}
            except:
                live_map[sym] = {'LTP': 0.0}

    # KPI Quick-Launch Row
    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.markdown("### 📝 MARKET BRIEFING")
            st.caption("Daily strategic analysis and sector rotation.")
            st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
            if st.button("GENERATE REPORT", use_container_width=True):
                launch_script("workflow_strategic_briefing.py")
            st.markdown('<div style="text-align:right;color:#555;font-size:0.8rem;margin-top:10px;">STATUS: READY</div>', unsafe_allow_html=True)
    with col2:
        with st.container(border=True):
            st.markdown("### 📡 SECTOR RADAR")
            st.caption("RRG Relative Strength Analysis vs Index.")
            st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
            if st.button("LAUNCH RADAR", use_container_width=True):
                launch_script("sector_radar.py")
            st.markdown('<div style="text-align:right;color:#555;font-size:0.8rem;margin-top:10px;">TARGET: NIFTY 50/500</div>', unsafe_allow_html=True)
    with col3:
        with st.container(border=True):
            st.markdown("### 💼 PORTFOLIO HEALTH")
            st.caption("Risk assessment and exposure audit.")
            st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
            if st.button("LAUNCH ANALYTICS", use_container_width=True):
                launch_script("portfolio_analytics.py", is_streamlit=True)
            st.markdown('<div style="text-align:right;color:#555;font-size:0.8rem;margin-top:10px;">LIVE CENTER: ACTIVE</div>', unsafe_allow_html=True)

    st.divider()

    if not df_active.empty:
        st.markdown("### PORTFOLIO HEATMAP — CAPITAL ALLOCATION")
        heatmap_df = df_active.copy()
        heatmap_df['Sector']     = heatmap_df['Sector'].fillna("Unassigned").replace("", "Unassigned")
        heatmap_df['Deployment'] = heatmap_df['Quantity'] * heatmap_df['BuyPrice']
        heatmap_df['PnLPct']     = [
            (live_map.get(s, {}).get('LTP', p) - p) / p * 100 if p > 0 else 0
            for s, p in zip(heatmap_df['Symbol'], heatmap_df['BuyPrice'])
        ]
        fig = px.treemap(
            heatmap_df,
            path=[px.Constant("Portfolio"), "Sector", "Symbol"],
            values="Deployment", color="PnLPct",
            color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
            hover_data=["Quantity", "BuyPrice"],
            title="Capital Deployment by Sector & Symbol (Size=Capital, Color=P&L)"
        )
        fig.update_layout(
            margin=dict(t=30, l=10, r=10, b=10), height=480,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.markdown("### ALPHA BENCHMARKING VS NIFTY 500")
    df_closed = load_closed_trades_db()
    if not df_closed.empty:
        try:
            df_closed['ExitDate'] = pd.to_datetime(df_closed['ExitDate'])
            df_closed = df_closed.sort_values('ExitDate')
            df_closed['PnL'] = (
                pd.to_numeric(df_closed['ExitPrice'], errors='coerce').fillna(0) -
                pd.to_numeric(df_closed['BuyPrice'],  errors='coerce').fillna(0)
            ) * pd.to_numeric(df_closed['Quantity'], errors='coerce').fillna(0)
            portfolio_curve = df_closed.groupby('ExitDate')['PnL'].sum().cumsum().reset_index()
            portfolio_curve.columns = ['Date', 'PortfolioProfit']
            start_date = portfolio_curve['Date'].min()
            end_date   = portfolio_curve['Date'].max()
            nifty500 = yf.download("^NSEI", start=start_date - pd.Timedelta(days=7),
                                   end=end_date + pd.Timedelta(days=1), progress=False)
            if nifty500.empty:
                nifty500 = yf.download("^NSEI", start=start_date - pd.Timedelta(days=7),
                                       end=end_date + pd.Timedelta(days=1), progress=False)
            if not nifty500.empty:
                nifty500 = nifty500['Close'].reset_index()
                nifty500.columns = ['Date', 'NiftyClose']
                nifty500['Date'] = pd.to_datetime(nifty500['Date']).dt.tz_localize(None)
                first_nifty = nifty500['NiftyClose'].iloc[0]
                nifty500['Benchmark'] = (nifty500['NiftyClose'] - first_nifty) / first_nifty * 100
                merged = pd.merge_asof(portfolio_curve, nifty500[['Date', 'Benchmark']], on='Date')
                fig_alpha = px.line(merged, x='Date', y=['PortfolioProfit', 'Benchmark'],
                                    labels={'value': '₹ / %', 'variable': ''})
                fig_alpha.update_layout(
                    height=320, margin=dict(t=10, l=0, r=0, b=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    legend=dict(font=dict(size=11), bgcolor="rgba(0,0,0,0)")
                )
                st.plotly_chart(fig_alpha, use_container_width=True)
        except Exception as e:
            st.error(f"Alpha chart error: {e}")
    else:
        st.info("No closed trades yet to benchmark.")

# ════════════════════════════════════════════
#  PAGE: HUNTER
# ════════════════════════════════════════════
elif page == 'HUNTER':
    st.markdown("# 🎯 HUNTER")
    st.markdown("---")

    hunter_nav_map = {'SCANNERS': 'SCANNERS', 'ENRICHMENT': 'ENRICHMENT', 'SELECTION': 'SELECTION'}
    opts = list(hunter_nav_map.keys())
    curr_idx = 0
    for i, k in enumerate(hunter_nav_map.values()):
        if k == st.session_state.huntertab:
            curr_idx = i
            break

    menu_col, content_col = st.columns([1, 6])
    with menu_col:
        st.markdown("##### TARGETING")
        st.markdown('<div style="margin-bottom:5px"></div>', unsafe_allow_html=True)
        selected_opt = st.radio("Hunter Nav", opts, index=curr_idx, label_visibility="collapsed")
        st.session_state.huntertab = hunter_nav_map[selected_opt]

    with content_col:
        hunter_tab = st.session_state.huntertab

        if hunter_tab == 'SCANNERS':
            with st.container(border=True):
                st.subheader("Chartink Scanners")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Positional Strategies**")
                    if st.button("Stage 2 Hunter",         use_container_width=True): launch_script("chartink_scanner_pro.py", "1")
                    if st.button("Early Birds Accumulation", use_container_width=True): launch_script("chartink_scanner_pro.py", "3")
                with c2:
                    st.markdown("**Swing Strategies**")
                    if st.button("Stage 2 Pullback",       use_container_width=True): launch_script("chartink_scanner_pro.py", "2")
                    if st.button("Strong Leaders",         use_container_width=True): launch_script("chartink_scanner_pro.py", "4")

        elif hunter_tab == 'ENRICHMENT':
            with st.container(border=True):
                st.subheader("Fundamental Data")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Fetch Screener.in Data", use_container_width=True): launch_script("screener_fetcher.py")
                with c2:
                    if st.button("Process HTML to CSV",    use_container_width=True): launch_script("screener_processor.py")

        elif hunter_tab == 'SELECTION':
            with st.container(border=True):
                st.subheader("Golden Matcher Engine")
                st.info("Combines Technical Scans with Fundamental Filters to find 5-Star setups.")
                if st.button("RUN GOLDEN MATCHER", type="primary", use_container_width=True):
                    launch_script("brute_force_match_pro.py")
                st.divider()
                st.subheader("AI Top Picks Preview")
                preview_cat = st.selectbox("Select Strategy to Preview",
                                           ["Stage 2 Hunter", "Stage 2 Pullback", "Early Birds", "Strong Leaders"])
                preview_map = {
                    "Stage 2 Hunter":  "stage2_results.csv",
                    "Stage 2 Pullback": "pullback_results.csv",
                    "Early Birds":     "earlybirds_results.csv",
                    "Strong Leaders":  "leaders_results.csv"
                }
                fname = preview_map.get(preview_cat, "")
                if os.path.exists(fname):
                    try:
                        df_res = pd.read_csv(fname)
                        cols = df_res.columns.tolist()
                        ai_cols = [c for c in ["Symbol", "Conviction", "AI Catalyst"] if c in cols]
                        other_cols = [c for c in cols if c not in ai_cols]
                        display_cols = ai_cols + other_cols
                        st.dataframe(df_res[display_cols].head(15), use_container_width=True, hide_index=True)
                    except Exception as e:
                        st.error(f"Error loading preview: {e}")
                else:
                    st.info(f"No 5-Star matches found in the latest '{preview_cat}' scan.")

# ════════════════════════════════════════════
#  PAGE: WATCHLIST
# ════════════════════════════════════════════
elif page == 'WATCHLIST':
    st.markdown("# 📋 WATCHLIST SYNC")
    st.markdown("Synchronize your selected setups across all platforms.")
    st.markdown("---")

    wl_nav_map = {'GENERATE': 'GENERATION', 'SYNC CLOUD': 'SYNC'}
    wl_opts = list(wl_nav_map.keys())
    wl_idx = 0 if st.session_state.watchlisttab == 'GENERATION' else 1

    menu_col, content_col = st.columns([1, 6])
    with menu_col:
        st.markdown("##### ACTIONS")
        st.markdown('<div style="margin-bottom:5px"></div>', unsafe_allow_html=True)
        sel_wl = st.radio("WL Nav", wl_opts, index=wl_idx, label_visibility="collapsed")
        st.session_state.watchlisttab = wl_nav_map[sel_wl]

    with content_col:
        active_tab = st.session_state.watchlisttab

        if active_tab == 'GENERATION':
            with st.container(border=True):
                st.subheader("1. Local Generation")
                st.write("Generate clean CSVs for local analysis.")
                if st.button("Generate CSVs — Local", use_container_width=True):
                    import watchlist_manager
                    watchlist_manager.generate_tradingview_files()
                    st.success("Watchlists generated in WL folder")

        elif active_tab == 'SYNC':
            with st.container(border=True):
                st.subheader("2. External Cloud Sync")
                st.write("Push lists to cloud platforms.")
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("Sync to Strike.Money",  use_container_width=True): launch_script("strike_automation.py", "--mode watchlist")
                with c2:
                    if st.button("Sync to TradingView",   use_container_width=True): launch_script("tradingview_automation_v2.py")
                with c3:
                    if st.button("MASTER SYNC — All", type="primary", use_container_width=True): launch_script("master_portfolio_sync.py")

# ════════════════════════════════════════════
#  PAGE: COMMAND
# ════════════════════════════════════════════
elif page == 'COMMAND':
    st.markdown("# ⚡ COMMAND CENTER")
    st.markdown("Active trade management and execution protocols.")
    st.markdown("---")

    cmd_opts = ['ACTIVE OPS', 'LEDGER']
    cmd_idx = 0 if st.session_state.commandtab == 'ACTIVEOPS' else 1

    menu_col, content_col = st.columns([1, 6])
    with menu_col:
        st.markdown("##### CONTROLS")
        st.markdown('<div style="margin-bottom:5px"></div>', unsafe_allow_html=True)
        sel_cmd = st.radio("Cmd Nav", cmd_opts, index=cmd_idx, label_visibility="collapsed")
        st.session_state.commandtab = 'ACTIVEOPS' if sel_cmd == 'ACTIVE OPS' else 'LEDGER'

    with content_col:
        active_tab = st.session_state.commandtab

        if active_tab == 'ACTIVEOPS':
            with st.container(border=True):
                st.subheader("Active Operations")
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("Sniper Entry AI v2",  use_container_width=True, help="Order execution with Institutional AI analysis."): launch_script("sniper_trigger.py")
                with c2:
                    if st.button("GTT Auto-Shield",     use_container_width=True, help="Auto-protect holdings using Journal levels."):      launch_script("gtt_auto_shield.py")
                with c3:
                    if st.button("Telegram Sentinel",   use_container_width=True, help="Active market monitoring via Mobile."):            launch_script("telegram_sentinel.py")
            st.divider()
            with st.container(border=True):
                st.write("**External Apps**")
                if st.button("Open Full Journal App", use_container_width=True):
                    launch_script("dhan_journal_v6.py", is_streamlit=True)

        elif active_tab == 'LEDGER':
            with st.container(border=True):
                st.subheader("Live Trade Ledger")
                df_journal = load_journal_db()
                if not df_journal.empty:
                    cols_show = [c for c in ["Symbol", "Type", "BuyPrice", "Quantity",
                                             "Status", "Sector", "StopLoss", "Target",
                                             "PlannedRR", "Timeframe"] if c in df_journal.columns]
                    st.dataframe(df_journal[cols_show], use_container_width=True, height=480, hide_index=True)
                else:
                    st.info("No open trades found in the system.")

# ════════════════════════════════════════════
#  PAGE: AI LAB
# ════════════════════════════════════════════
elif page == 'AI LAB':
    st.markdown("# 🧠 AI LABORATORY")
    st.markdown("Advanced Generative AI workflows and automation.")
    st.markdown("---")

    ai_nav_map = {'PRE-FLIGHT': 'PREFLIGHT', 'GENERATIVE': 'GENERATIVE', 'WORKFLOWS': 'WORKFLOWS'}
    ai_opts = list(ai_nav_map.keys())
    ai_idx = 0
    for i, val in enumerate(ai_nav_map.values()):
        if val == st.session_state.ailabtab:
            ai_idx = i
            break

    menu_col, content_col = st.columns([1, 6])
    with menu_col:
        st.markdown("##### LAB BENCH")
        st.markdown('<div style="margin-bottom:5px"></div>', unsafe_allow_html=True)
        sel_ai = st.radio("AI Nav", ai_opts, index=ai_idx, label_visibility="collapsed", key="ai_nav_radio")
        st.session_state.ailabtab = ai_nav_map[sel_ai]

    with content_col:
        active_tab = st.session_state.ailabtab

        if active_tab == 'PREFLIGHT':
            with st.container(border=True):
                st.subheader("AI-Trade Proposer — Pre-flight Check")
                st.write("Score and size a new trade before execution.")
                p1, p2, p3 = st.columns([2, 1, 1])
                with p1:
                    prop_sym   = st.text_input("Ticker Symbol", key="prop_sym", placeholder="e.g. RELIANCE").upper()
                with p2:
                    prop_entry = st.number_input("Entry Price", min_value=0.0, step=0.1, key="prop_entry")
                with p3:
                    prop_risk  = st.number_input("Risk ₹", value=5000, step=500, key="prop_risk")
                if st.button("RUN ANALYSIS", type="primary", use_container_width=True, key="btn_run_analysis"):
                    if not prop_sym:
                        st.error("Enter ticker.")
                    else:
                        with st.spinner(f"Analyzing {prop_sym}..."):
                            try:
                                rating_res   = get_weinstein_score(prop_sym)
                                atr_val      = get_atr(prop_sym)
                                suggested_sl = prop_entry - (2.0 * atr_val) if atr_val else 0
                                qty = int(prop_risk / (prop_entry - suggested_sl)) if (prop_entry - suggested_sl) > 0 else 0
                                r1, r2, r3 = st.columns(3)
                                r1.metric("Weinstein Grade", rating_res.get('rating', 'N/A'))
                                r2.metric("Suggested SL",    f"{suggested_sl:.2f}")
                                r3.metric("Rec. Quantity",   f"{qty} shares")
                                st.info(f"AI Rationale: {rating_res.get('reason', 'N/A')}")
                            except Exception as e:
                                st.error(f"Analysis error: {e}")

        elif active_tab == 'GENERATIVE':
            with st.container(border=True):
                st.subheader("Generative Analysis")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("AI Post-Trade Autopsy", use_container_width=True, key="btn_ai_autopsy"): launch_script("portfolio_analytics.py", is_streamlit=True)
                    if st.button("Auto-Plan Journal",     use_container_width=True, key="btn_ai_journal"):  launch_script("dhan_journal_v6.py", is_streamlit=True)
                with c2:
                    if st.button("Standalone Prompt Gen", use_container_width=True, key="btn_ai_prompt"):  launch_script("generate_prompt_standalone.py")
                st.divider()
                if st.button("Clear AI Cache", help="Fetch fresh data on next run.", key="btn_clear_ai_cache"):
                    if os.path.exists("ai_cache.json"):
                        os.remove("ai_cache.json")
                        st.success("AI Cache Cleared!")
                    else:
                        st.info("Cache is already empty.")

        elif active_tab == 'WORKFLOWS':
            st.markdown("#### Workflow Automation")
            with st.container(border=True):
                st.write("Execute complex multi-stage pipelines autonomously.")
                if st.button("Run Full Auto-Pilot", use_container_width=True, key="btn_run_pipeline"):
                    launch_script("run_pipeline.py")
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown("**AUTO-PILOT PROTOCOL**")
                    st.write("Execute full pipeline: Scanners → Fundamentals → Golden Matching → Watchlist Sync")
                with c2:
                    st.markdown('<div style="height:15px"></div>', unsafe_allow_html=True)
                    if st.button("INITIATE", type="primary", use_container_width=True):
                        launch_script("run_pipeline.py")
