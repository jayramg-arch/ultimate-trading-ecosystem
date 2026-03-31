import streamlit as st
import pandas as pd
import os, sys, sqlite3, base64
from dotenv import load_dotenv
from dhan_auth import ensure_valid_token
from dhanhq import dhanhq
from ai_risk_manager import get_market_health, get_noise_risk_stats, get_atr, get_portfolio_correlation_matrix, calculate_portfolio_vitals, get_adaptive_atr_multiplier
from ai_grading_engine import get_weinstein_score
import math
import plotly.express as px
import yfinance as yf
from pine_generator import generate_pine_code

def clean_symbol(symbol):
    """Clean Dhan symbols by stripping suffixes and mapping indices."""
    s = str(symbol).strip().upper().replace("NSE:", "").replace("BSE:", "")
    if s == "NIFTY": return "^NSEI"
    if s == "BANKNIFTY" or s == "NIFTYBANK": return "^NSEBANK"
    for suffix in ['-EQ', '-BE', '-SM', '-ST', '-BZ']:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    return s

st.set_page_config(
    page_title="Weinstein Commander Web",
    page_icon="🦁",
    layout="wide",
    initial_sidebar_state="expanded"
)

load_dotenv(override=True)

def check_auth_cached():
    try: return ensure_valid_token()
    except: return None

check_auth_cached()
load_dotenv(override=True)

CLIENT_ID    = os.getenv("DHAN_CLIENT_ID")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
DB_FILE      = "trade_journal_v6.db"

JOURNAL_RENAME_MAP = {
    'symbol':'Symbol','trade_type':'Type','stoploss':'StopLoss','target':'Target',
    'rationale':'Rationale','timeframe':'Timeframe','entry_date':'EntryDate',
    'quantity':'Quantity','buy_price':'BuyPrice','exit_date':'ExitDate',
    'exit_price':'ExitPrice','exit_reason':'ExitReason','status':'Status',
    'sector':'Sector','trade_quality':'Quality','compromises':'Compromises',
    'lessons':'Lessons','screenshot_path':'Screenshot','planned_rr':'PlannedRR',
    'ai_analysis':'AI Analysis'
}

def format_inr(number):
    """Format a number with Indian comma style: 1,23,456.78"""
    try:
        if number is None: return "0"
        val = float(number)
        sign = "-" if val < 0 else ""
        val = abs(val)
        s, *d = str("{:.2f}".format(val)).partition(".")
        r = ",".join([s[x-2:x] for x in range(-3, -len(s), -2)][::-1] + [s[-3:]])
        return sign + "".join([r] + d)
    except:
        return str(number)

def format_inr_int(number):
    """Format a number with Indian comma style, no decimals: 1,23,456"""
    try:
        if number is None: return "0"
        val = float(number)
        sign = "-" if val < 0 else ""
        val = abs(val)
        s = str(int(round(val)))
        r = ",".join([s[x-2:x] for x in range(-3, -len(s), -2)][::-1] + [s[-3:]])
        return sign + r
    except:
        return str(number)

def get_script_path(f): return os.path.join(os.getcwd(), f)
def get_img_as_base64(file):
    with open(file,"rb") as f: return base64.b64encode(f.read()).decode()

def launch_script(script_name, args=None, is_streamlit=False):
    try:
        if not os.path.exists(get_script_path(script_name)):
            st.error(f"❌ File not found: {script_name}"); return
        cmd_str = f'streamlit run "{script_name}"' if is_streamlit else f'"{sys.executable}" "{script_name}"'
        if args: cmd_str += f" {args}"
        os.system(f'start cmd /k "cd /d "{os.getcwd()}" && {cmd_str}"')
        st.toast(f"🚀 Launched: {script_name}")
    except Exception as e:
        st.error(f"Failed to launch: {e}")

def get_dhan_balance():
    try:
        if not CLIENT_ID or not ACCESS_TOKEN: return 0.0, "AUTH MISSING"
        dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
        resp = dhan.get_fund_limits()
        if isinstance(resp, dict) and resp.get('status') == 'success':
            data = resp.get('data', {})
            bal  = float(data.get('availabelBalance', data.get('availableBalance', 0.0)))
            return bal, "SYSTEM ONLINE"
        err = str(resp).lower()
        if any(k in err for k in ["expired","access token","unauthorized"]): return 0.0, "AUTH EXPIRED"
        return 0.0, "API OFFLINE"
    except Exception as e:
        return 0.0, f"OFFLINE ({type(e).__name__})"

def get_live_holdings_stats():
    try:
        if not CLIENT_ID or not ACCESS_TOKEN: return 0, 0.0, pd.DataFrame()
        dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
        resp = dhan.get_holdings()
        if isinstance(resp, dict) and resp.get('status') == 'success':
            data = resp.get('data', [])
            valid_data = [item for item in data if float(item.get('totalQty', 0)) > 0]
            total_deployed = sum(float(item.get('avgCostPrice', 0)) * float(item.get('totalQty', 0)) for item in valid_data)
            open_count = len(valid_data)
            
            if valid_data:
                df_live = pd.DataFrame(valid_data)
                df_live = df_live.rename(columns={
                    'tradingSymbol': 'Symbol',
                    'avgCostPrice': 'BuyPrice',
                    'totalQty': 'Quantity',
                    'lastTradedPrice': 'LTP'
                })
            else:
                df_live = pd.DataFrame()
                
            return open_count, total_deployed, df_live
        return 0, 0.0, pd.DataFrame()
    except:
        return 0, 0.0, pd.DataFrame()

def load_journal_db():
    conn = None
    try:
        if not os.path.exists(DB_FILE): return pd.DataFrame()
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql("SELECT * FROM journal WHERE status='OPEN'", conn)
        df = df.rename(columns=JOURNAL_RENAME_MAP)
        # Type enforcement
        if 'Quantity' in df.columns and 'BuyPrice' in df.columns:
            df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
            df['BuyPrice'] = pd.to_numeric(df['BuyPrice'], errors='coerce').fillna(0)
            df = df[df['Quantity'] > 0].copy()
        return df
    except: return pd.DataFrame()
    finally:
        if conn: conn.close()

def load_closed_trades_db():
    conn = None
    try:
        if not os.path.exists(DB_FILE): return pd.DataFrame()
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql("SELECT * FROM journal WHERE status='CLOSED'", conn)
        return df.rename(columns=JOURNAL_RENAME_MAP)
    except: return pd.DataFrame()
    finally:
        if conn: conn.close()

# ── DATA ───────────────────────────────────────────────────────────────
balance, sys_status   = get_dhan_balance()
live_pos, live_dep, df_live_holdings = get_live_holdings_stats()
is_healthy, mkt_ltp, mkt_sma = get_market_health("NSE:CNX500")

df_active_global      = load_journal_db()

# Map real-time LTP from broker to the journal DB for accurate risk calculation
if not df_active_global.empty and not df_live_holdings.empty:
    ltp_dict = dict(zip(df_live_holdings['Symbol'], df_live_holdings['LTP']))
    # Safe map, fallback to BuyPrice if not found
    df_active_global['LTP'] = df_active_global['Symbol'].map(ltp_dict).fillna(df_active_global['BuyPrice'])

if not df_active_global.empty:
    noise_count_g, noise_syms_g = get_noise_risk_stats(df_active_global)
else:
    noise_count_g, noise_syms_g = 0, []

h_color      = "#00f260" if is_healthy        else "#ff4b4b"
h_text       = "BULLISH" if is_healthy        else "BEARISH (<200DMA)"
w_color      = "#ff4b4b" if noise_count_g > 0 else "#00f260"
w_text       = f"⚠ {noise_count_g} AT RISK"  if noise_count_g > 0 else "✔ SECURE"
s_color      = "#00f260" if sys_status == "SYSTEM ONLINE" else "#ff4b4b"

# Use live broker data for absolute ground truth
total_deployed_g = live_dep
open_pos         = live_pos

# Safe deployment calculation with fallback to 5M as baseline to prevent div/0
total_cap    = balance + total_deployed_g if (balance + total_deployed_g) > 0 else 5000000 
deployed_pct = round((total_deployed_g / total_cap) * 100, 1) if total_cap > 0 else 0.0

for k, v in [('page','DASHBOARD'),('huntertab','SCANNERS'),
             ('watchlisttab','GENERATION'),('commandtab','ACTIVEOPS'),
             ('ailabtab','PREFLIGHT')]:
    if k not in st.session_state: st.session_state[k] = v

# ══════════════════════════════════════════════════════════════════════
#  CSS
# ══════════════════════════════════════════════════════════════════════
bg_str = ""
if os.path.exists("trading_bg_pro.png"):
    bg_img = get_img_as_base64("trading_bg_pro.png")
    bg_str = f', url("data:image/png;base64,{bg_img}")'

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=JetBrains+Mono:wght@400;600&family=Inter:wght@300;400;500&display=swap');

*, *::before, *::after {{ box-sizing: border-box; }}

.stApp {{
    background: linear-gradient(160deg,#050d18 0%,#0a1628 60%,#060e1a 100%){bg_str};
    background-attachment: fixed; background-size: cover;
    font-family: 'Inter', sans-serif; color: #c9d1d9;
}}
.block-container {{ padding: 0 !important; margin: 0 !important; max-width: 100% !important; }}
header, footer {{ visibility: hidden !important; }}
#MainMenu {{ visibility: hidden !important; }}

/* ══ HIDE SIDEBAR COLLAPSE / EXPAND BUTTON COMPLETELY ══ */
[data-testid="collapsedControl"]      {{ display: none !important; }}
[data-testid="stSidebarCollapseButton"] {{ display: none !important; }}
button[kind="header"]                 {{ display: none !important; }}
section[data-testid="stSidebar"] > div:first-child > div > button {{ display: none !important; }}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg,#0d1b2a 0%,#0a1628 100%) !important;
    border-right: 1px solid #1e3a5f !important;
    width: 230px !important; min-width: 230px !important;
    padding: 0 !important;
    /* Always visible, never collapsible */
    transform: none !important;
    visibility: visible !important;
    display: block !important;
}}
[data-testid="stSidebar"] > div {{ padding: 0 !important; }}
[data-testid="stSidebarContent"] {{
    padding: 0 !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    /* Scrollbar thin and dark */
    scrollbar-width: thin;
    scrollbar-color: #1e3a5f #0a1628;
}}
[data-testid="stSidebarContent"]::-webkit-scrollbar {{ width: 4px; }}
[data-testid="stSidebarContent"]::-webkit-scrollbar-track {{ background: #0a1628; }}
[data-testid="stSidebarContent"]::-webkit-scrollbar-thumb {{ background: #1e3a5f; border-radius: 2px; }}

/* ── TOP STATUS BAR ── */
.statusbar {{
    display: grid; grid-template-columns: repeat(5, 1fr);
    gap: 1px; background: #1e3a5f; border-bottom: 2px solid #1e3a5f;
}}
.sb-cell {{ background: #0a1628; padding: 6px 16px; display: flex; flex-direction: column; justify-content: center; }}
.sb-label {{ font-family: 'JetBrains Mono',monospace; font-size: 0.58rem; color: #5a8a9f; letter-spacing: 2px; text-transform: uppercase; }}
.sb-value {{ font-family: 'JetBrains Mono',monospace; font-size: 0.95rem; font-weight: 600; margin-top: 1px; letter-spacing: 0.5px; }}

/* ── PAGE TITLE ── */
.page-title {{
    font-family: 'Rajdhani',sans-serif; font-size: 1.5rem; font-weight: 700;
    letter-spacing: 3px; text-transform: uppercase; color: #e6edf3;
    border-left: 3px solid #238636; padding-left: 12px; margin: 14px 0 2px 0;
}}
.page-desc {{
    font-size: 0.68rem; color: #5a8a9f; letter-spacing: 2px; text-transform: uppercase;
    margin: 0 0 12px 15px; font-family: 'JetBrains Mono',monospace;
}}

/* ── SECTION HEADER ── */
.section-hdr {{
    font-family: 'JetBrains Mono',monospace; font-size: 0.62rem; color: #5a8a9f;
    letter-spacing: 3px; text-transform: uppercase; margin: 14px 0 8px 0;
    display: flex; align-items: center; gap: 10px;
}}
.section-hdr::after {{ content:''; flex:1; height:1px; background:#1e3a5f; }}

/* ── SUB SECTION LABEL ── */
.section-sub-lbl {{
    font-family: 'Rajdhani', sans-serif;
    font-size: 1.0rem; font-weight: 600;
    color: #e6edf3; letter-spacing: 1.5px; text-transform: uppercase;
    padding: 5px 12px;
    background: rgba(88,166,255,0.08);
    border-left: 3px solid #58a6ff;
    border-radius: 0 4px 4px 0;
    margin-bottom: 8px;
}}

/* ── ACTION BUTTONS (card-style, tall) ── */
button[kind="secondary"] {{
    background: #0d1b2a !important; border: 1px solid #1e3a5f !important;
    border-radius: 5px !important; color: #c9d1d9 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.82rem !important; font-weight: 400 !important;
    letter-spacing: 0.1px !important; text-transform: none !important;
    padding: 12px 16px !important; width: 100% !important;
    text-align: left !important; line-height: 1.6 !important;
    min-height: 76px !important; transition: all .15s ease !important;
}}
button[kind="secondary"]:hover {{
    background: #12243a !important; border-color: #238636 !important;
    color: #e6edf3 !important;
    box-shadow: inset 3px 0 0 #238636, 0 0 0 1px rgba(35,134,54,.2) !important;
}}
button[kind="secondary"] p {{
    white-space: pre-line !important; text-align: left !important;
    margin: 0 !important; color: #c9d1d9 !important;
    font-size: 0.82rem !important; line-height: 1.6 !important;
}}

button[kind="primary"] {{
    background: rgba(35,134,54,0.15) !important; border: 1px solid #238636 !important;
    border-radius: 5px !important; color: #3fb950 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.82rem !important; font-weight: 400 !important;
    letter-spacing: 0.1px !important; text-transform: none !important;
    padding: 12px 16px !important; width: 100% !important;
    text-align: left !important; line-height: 1.6 !important;
    min-height: 76px !important;
    box-shadow: 0 0 0 1px rgba(35,134,54,.15) !important;
    transition: all .15s ease !important;
}}
button[kind="primary"]:hover {{
    background: rgba(35,134,54,0.25) !important;
    box-shadow: 0 0 16px rgba(35,134,54,.3), inset 3px 0 0 #3fb950 !important;
    color: #e6edf3 !important;
}}
button[kind="primary"] p {{
    white-space: pre-line !important; text-align: left !important;
    margin: 0 !important; color: inherit !important;
    font-size: 0.82rem !important; line-height: 1.6 !important;
}}

/* ── SIDEBAR NAV BUTTONS ── */
[data-testid="stSidebar"] button {{
    background: transparent !important; border: none !important;
    border-radius: 0 !important; border-left: 3px solid transparent !important;
    padding: 7px 16px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.85rem !important; font-weight: 500 !important;
    color: #8b949e !important; letter-spacing: 0.3px !important;
    text-transform: none !important; text-align: left !important;
    width: 100% !important; min-height: 0 !important;
    line-height: 1.3 !important; box-shadow: none !important;
    transition: all .12s ease !important;
}}
[data-testid="stSidebar"] button:hover {{
    background: rgba(255,255,255,0.04) !important; color: #e6edf3 !important;
    border-left-color: #30363d !important; box-shadow: none !important;
}}
[data-testid="stSidebar"] button[kind="primary"] {{
    background: rgba(35,134,54,0.12) !important; color: #3fb950 !important;
    border-left-color: #238636 !important; font-weight: 600 !important;
    box-shadow: none !important;
}}
[data-testid="stSidebar"] button[kind="primary"]:hover {{
    background: rgba(35,134,54,0.20) !important; box-shadow: none !important;
}}
[data-testid="stSidebar"] button p {{
    white-space: nowrap !important; text-align: left !important;
    font-size: 0.85rem !important; color: inherit !important;
}}

/* ── SIDEBAR RADIO ── */
[data-testid="stRadio"] {{ margin: 1px 0 !important; }}
[data-testid="stRadio"] label {{
    background: transparent !important; border: none !important;
    border-radius: 0 !important; border-left: 3px solid transparent !important;
    padding: 6px 14px 6px 28px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.88rem !important; font-weight: 400 !important;
    color: #adbac7 !important; letter-spacing: 0.2px !important;
    text-transform: none !important; cursor: pointer !important;
    transition: all .12s !important; margin: 0 !important; display: block !important;
}}
[data-testid="stRadio"] label:hover {{
    background: rgba(255,255,255,0.04) !important; color: #e6edf3 !important;
    border-left-color: #30363d !important;
}}
[data-testid="stRadio"] label[data-checked="true"] {{
    background: rgba(35,134,54,0.10) !important; color: #3fb950 !important;
    border-left-color: #238636 !important; font-weight: 600 !important;
}}
[role="radiogroup"] input {{ display: none !important; }}
[role="radiogroup"] [data-testid="stMarkdownContainer"] p {{
    margin: 0 !important; font-size: 0.88rem !important; color: inherit !important;
}}

/* ── SIDEBAR SECTION LABEL ── */
.sb-section-lbl {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.60rem; color: #3d5a6e; letter-spacing: 3px; text-transform: uppercase;
    padding: 8px 16px 4px; border-top: 1px solid #1e3a5f; margin-top: 2px;
}}

/* ── METRICS ── */
[data-testid="metric-container"] {{
    background: #0d1b2a !important; border: 1px solid #1e3a5f !important;
    border-radius: 6px !important; padding: 10px 14px !important;
}}
[data-testid="metric-container"] label {{
    font-family: 'JetBrains Mono',monospace !important; font-size: 0.60rem !important;
    color: #5a8a9f !important; letter-spacing: 2px !important; text-transform: uppercase !important;
}}
[data-testid="metric-container"] [data-testid="stMetricValue"] {{
    font-family: 'JetBrains Mono',monospace !important; font-size: 1.2rem !important;
    font-weight: 600 !important; color: #e6edf3 !important;
}}

/* ── MISC ── */
[data-testid="stDataFrame"] {{ border: 1px solid #1e3a5f !important; border-radius: 6px !important; }}
iframe {{ border-radius: 6px !important; }}
hr {{ border-color: #1e3a5f !important; margin: 8px 0 !important; }}
[data-testid="stToast"] {{
    background: #0d1b2a !important; border: 1px solid #238636 !important;
    border-radius: 6px !important; color: #c9d1d9 !important;
    font-family: 'Inter', sans-serif !important;
}}
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {{
    background: #0a1628 !important; border: 1px solid #1e3a5f !important;
    border-radius: 4px !important; color: #e6edf3 !important;
    font-family: 'JetBrains Mono',monospace !important; font-size: 0.82rem !important;
}}
[data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus {{
    border-color: #238636 !important; box-shadow: 0 0 0 2px rgba(35,134,54,.2) !important;
}}
label {{ color: #8b949e !important; font-size: 0.75rem !important; }}
[data-testid="stSelectbox"] > div > div {{
    background: #0a1628 !important; border-color: #1e3a5f !important;
    color: #e6edf3 !important; border-radius: 4px !important;
}}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="padding:12px 16px 10px;border-bottom:1px solid #1e3a5f;background:#080f1a;">
      <div style="font-family:'Rajdhani',sans-serif;font-size:1.3rem;font-weight:700;color:#e6edf3;letter-spacing:1.5px;">🦁 WEINSTEIN</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;color:#3d5a6e;letter-spacing:3px;margin-top:2px;">COMMANDER WEB v11.0</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sb-section-lbl">Navigation</div>', unsafe_allow_html=True)
    for option in ['DASHBOARD','HUNTER','WATCHLIST','COMMAND','AI LAB','JOURNAL', 'X-RAY', 'TV SIDECAR']:
        btn_type = "primary" if st.session_state.page == option else "secondary"
        if st.button(option, key=f"nav_{option}", use_container_width=True, type=btn_type):
            if option == 'JOURNAL':
                launch_script("dhan_journal_v7.py", is_streamlit=True)
            elif option == 'X-RAY':
                launch_script("fundamental_xray.py", is_streamlit=True)
            elif option == 'TV SIDECAR':
                launch_script("tv_sidecar_app.py", is_streamlit=True)
            else:
                st.session_state.page = option
                st.rerun()

    page = st.session_state.page

    if page == 'HUNTER':
        st.markdown('<div class="sb-section-lbl">Targeting</div>', unsafe_allow_html=True)
        hopts = ['SCANNERS','ENRICHMENT','SELECTION']
        sel = st.radio("Hunter Nav", hopts,
                       index=hopts.index(st.session_state.huntertab),
                       label_visibility="collapsed")
        st.session_state.huntertab = sel

    elif page == 'WATCHLIST':
        st.markdown('<div class="sb-section-lbl">Actions</div>', unsafe_allow_html=True)
        wl_opts = ['GENERATE','SYNC CLOUD']
        wl_map  = {'GENERATE':'GENERATION','SYNC CLOUD':'SYNC'}
        wl_rev  = {v:k for k,v in wl_map.items()}
        sel = st.radio("WL Nav", wl_opts,
                       index=wl_opts.index(wl_rev.get(st.session_state.watchlisttab,'GENERATE')),
                       label_visibility="collapsed")
        st.session_state.watchlisttab = wl_map[sel]

    elif page == 'COMMAND':
        st.markdown('<div class="sb-section-lbl">Controls</div>', unsafe_allow_html=True)
        cmd_opts = ['ACTIVE OPS','LEDGER']
        cmd_map  = {'ACTIVE OPS':'ACTIVEOPS','LEDGER':'LEDGER'}
        cmd_rev  = {v:k for k,v in cmd_map.items()}
        sel = st.radio("Cmd Nav", cmd_opts,
                       index=cmd_opts.index(cmd_rev.get(st.session_state.commandtab,'ACTIVE OPS')),
                       label_visibility="collapsed")
        st.session_state.commandtab = cmd_map[sel]

    elif page == 'AI LAB':
        st.markdown('<div class="sb-section-lbl">Lab Bench</div>', unsafe_allow_html=True)
        ai_opts = ['PRE-FLIGHT','GENERATIVE','WORKFLOWS']
        ai_map  = {'PRE-FLIGHT':'PREFLIGHT','GENERATIVE':'GENERATIVE','WORKFLOWS':'WORKFLOWS'}
        ai_rev  = {v:k for k,v in ai_map.items()}
        sel = st.radio("AI Nav", ai_opts,
                       index=ai_opts.index(ai_rev.get(st.session_state.ailabtab,'PRE-FLIGHT')),
                       label_visibility="collapsed")
        st.session_state.ailabtab = ai_map[sel]

    st.markdown('<div class="sb-section-lbl">System Status</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="padding:8px 16px 14px;font-family:'JetBrains Mono',monospace;">
      <div style="font-size:0.58rem;color:#3d5a6e;letter-spacing:2px;text-transform:uppercase;margin-bottom:3px;">API Health</div>
      <div style="font-size:0.78rem;font-weight:600;color:{s_color};letter-spacing:0.5px;margin-bottom:8px;">{sys_status}</div>
      <div style="font-size:0.58rem;color:#3d5a6e;letter-spacing:2px;text-transform:uppercase;margin-bottom:3px;">Available Capital</div>
      <div style="font-size:0.88rem;font-weight:600;color:#e6edf3;">₹{format_inr_int(balance)}</div>
    </div>
    """, unsafe_allow_html=True)

    if sys_status == "AUTH EXPIRED":
        st.warning("⚠️ Token expired — re-run dhan_auth.py")


# ══════════════════════════════════════════════════════════════════════
#  TOP STATUS BAR
# ══════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="statusbar">
  <div class="sb-cell"><div class="sb-label">Nifty 500</div><div class="sb-value" style="color:{h_color};">{h_text}</div></div>
  <div class="sb-cell"><div class="sb-label">Risk Watchdog</div><div class="sb-value" style="color:{w_color};">{w_text}</div></div>
  <div class="sb-cell"><div class="sb-label">Deployment</div><div class="sb-value" style="color:#58a6ff;">{deployed_pct}%</div></div>
  <div class="sb-cell"><div class="sb-label">Open Positions</div><div class="sb-value" style="color:#e6edf3;">{open_pos}</div></div>
  <div class="sb-cell"><div class="sb-label">Total Deployed</div><div class="sb-value" style="color:#e3b341;">₹{format_inr(total_deployed_g)}</div></div>
</div>
""", unsafe_allow_html=True)

page = st.session_state.page

def section(label):
    st.markdown(f'<div class="section-hdr">{label}</div>', unsafe_allow_html=True)

def sub_label(label):
    st.markdown(f'<div class="section-sub-lbl">{label}</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ════════════════════════════════════════════════════════════════════
if page == 'DASHBOARD':
    st.markdown('<div class="page-title">📊 Mission Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Real-Time Market Intelligence // Sector Radar // Risk Audit</div>', unsafe_allow_html=True)

    df_active = df_active_global
    live_map  = {}
    if not df_active.empty:
        for sym in df_active['Symbol'].unique():
            try:
                ticker = yf.Ticker(f"{sym}.NS")
                live_map[sym] = {'LTP': ticker.history(period="1d")['Close'].iloc[-1]}
            except:
                live_map[sym] = {'LTP': 0.0}

    section("Quick Launch")
    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        if st.button("📝  Market Briefing\nDaily strategic analysis and sector rotation.\n→  Generate Report",
                     key="db_brief", use_container_width=True):
            launch_script("workflow_strategic_briefing.py")
    with c2:
        if st.button("📡  Sector Radar\nRRG Relative Strength Analysis vs Index.\n→  Launch Radar",
                     key="db_radar", use_container_width=True):
            launch_script("sector_radar.py")
    with c3:
        if st.button("🤖  Complete Workflow\nScanners → Fundamentals → Matching → Sync.\n→  Launch Auto-Pilot",
                     key="db_pipeline", use_container_width=True, type="primary"):
            launch_script("run_pipeline.py")
    with c4:
        if st.button("📄  Export PDF Report\nGenerate a portfolio report PDF.\n→  Export Now",
                     key="db_pdf", use_container_width=True):
            try:
                launch_script("generate_report_pdf.py")
            except Exception as e:
                st.error(f"PDF Export Error: {e}")
    
    # ── SECTOR MOMENTUM HEATMAP ──
    with st.expander("🔥 Sector Momentum Heatmap — Rotation Intelligence", expanded=False):
        sector_indices = {
            'Nifty Bank': '^NSEBANK', 'Nifty IT': '^CNXIT', 'Nifty Pharma': '^CNXPHARMA',
            'Nifty Auto': '^CNXAUTO', 'Nifty Metal': '^CNXMETAL', 'Nifty FMCG': '^CNXFMCG',
            'Nifty Realty': '^CNXREALTY', 'Nifty Energy': '^CNXENERGY', 'Nifty Infra': '^CNXINFRA',
            'Nifty PSE': '^CNXPSE', 'Nifty Media': '^CNXMEDIA'
        }
        with st.spinner("Fetching sector momentum data..."):
            momentum_data = []
            for name, sym in sector_indices.items():
                try:
                    sd = yf.download(sym, period="6mo", interval="1wk", progress=False)
                    if sd.empty or len(sd) < 10:
                        continue
                    if isinstance(sd.columns, pd.MultiIndex):
                        sd.columns = sd.columns.get_level_values(0)
                    close = sd['Close']
                    # RS vs Nifty 50 (simple 4-week momentum)
                    rs_4w = ((close.iloc[-1] / close.iloc[-5]) - 1) * 100 if len(close) >= 5 else 0
                    rs_8w = ((close.iloc[-1] / close.iloc[-9]) - 1) * 100 if len(close) >= 9 else 0
                    # Acceleration = recent momentum vs older momentum
                    accel = rs_4w - (rs_8w - rs_4w)
                    momentum_data.append({
                        'Sector': name,
                        '4W Momentum %': round(rs_4w, 1),
                        '8W Momentum %': round(rs_8w, 1),
                        'Acceleration': round(accel, 1),
                        'Signal': '🟢 Accelerating' if accel > 2 else '🔴 Decelerating' if accel < -2 else '🟡 Neutral'
                    })
                except:
                    pass
            if momentum_data:
                df_mom = pd.DataFrame(momentum_data).sort_values('Acceleration', ascending=False)
                st.dataframe(df_mom, use_container_width=True, hide_index=True)
            else:
                st.info("Could not fetch sector data.")
    
    st.markdown("---")

    # ── OPEN PORTFOLIO HEALTH VITALS ──
    if not df_live_holdings.empty:
        section("Open Portfolio Health Vitals")
        
        # Compute per-position P&L using live prices natively from broker
        pos_pnls = []        # Individual position P&L in ₹
        pos_pnl_pcts = []    # Individual position P&L %
        pos_names = []       # Symbol names
        total_unrealized = 0.0
        total_deployed = 0.0
        
        for _, row in df_live_holdings.iterrows():
            sym = row.get('Symbol', '')
            bp = float(row.get('BuyPrice', 0) or 0)
            qty = float(row.get('Quantity', 0) or 0)
            # Use live_map (fresh Yahoo Finance) or fallback to Dhan broker's LTP
            ltp = live_map.get(sym, {}).get('LTP', float(row.get('LTP', bp)))
            
            if bp > 0 and qty > 0:
                pnl_rs = (ltp - bp) * qty
                pnl_pct = ((ltp - bp) / bp) * 100
                deployed = bp * qty
                pos_pnls.append(pnl_rs)
                pos_pnl_pcts.append(pnl_pct)
                pos_names.append(sym)
                total_unrealized += pnl_rs
                total_deployed += deployed
        
        n_evaluated = len(pos_pnl_pcts)
        
        # Win/Loss split
        win_pcts = [p for p in pos_pnl_pcts if p > 0]
        loss_pcts = [p for p in pos_pnl_pcts if p <= 0]
        winning = len(win_pcts)
        losing = len(loss_pcts)
        win_rate = (winning / n_evaluated * 100) if n_evaluated > 0 else 0
        
        # Avg Gain % and Avg Loss %
        avg_gain_pct = sum(win_pcts) / winning if winning > 0 else 0
        avg_loss_pct = sum(loss_pcts) / losing if losing > 0 else 0  # Will be negative
        
        # Risk/Reward Ratio = |Avg Gain| / |Avg Loss|
        risk_reward = abs(avg_gain_pct / avg_loss_pct) if avg_loss_pct != 0 else 0
        
        # Portfolio-level return (unrealized / total capital)
        open_return_pct = (total_unrealized / total_cap * 100) if total_cap > 0 else 0
        
        # Display — Row 1: Portfolio Overview
        v1, v2, v3, v4 = st.columns(4, gap="small")
        v1.metric("Unrealized P&L", f"₹{format_inr_int(total_unrealized)}",
                   help="Total unrealized P&L across all open positions.")
        v2.metric("Open Return", f"{open_return_pct:.1f}%",
                   help="Unrealized P&L / Total Capital.")
        v3.metric("Current Value", f"₹{format_inr_int(total_deployed + total_unrealized)}",
                   help="Current market value of all open positions.")
        v4.metric("Open Positions", f"{winning + losing}",
                   help=f"Positions with valid data. Broker reports {open_pos} total holdings.")
        
        # Display — Row 2: Win/Loss Analysis
        ev1, ev2, ev3, ev4 = st.columns(4, gap="small")
        ev1.metric("Win Rate", f"{win_rate:.1f}%   ({winning}W / {losing}L)",
                    help=f"{winning} winning + {losing} losing = {n_evaluated} evaluated positions.")
        ev2.metric("Avg Gain %", f"{avg_gain_pct:.1f}%",
                    help=f"Average P&L% of {winning} winning positions.")
        ev3.metric("Avg Loss %", f"{avg_loss_pct:.1f}%",
                    help=f"Average P&L% of {losing} losing positions.")
        rr_color = "normal" if risk_reward >= 1.0 else "off"
        ev4.metric("Risk/Reward", f"{risk_reward:.2f}",
                    help="Avg Gain% / |Avg Loss%|. Above 1.0 = winners outpace losers. Target: >2.0.")
        st.markdown("---")
    
    if not df_active.empty:
        left_col, right_col = st.columns([3, 2], gap="medium")
        with left_col:
            section("Portfolio Heatmap — Capital Allocation")
            hmap = df_active.copy()
            hmap['Sector']     = hmap['Sector'].fillna("Unassigned").replace("","Unassigned")
            hmap['Deployment'] = hmap['Quantity'] * hmap['BuyPrice']
            hmap['PnLPct']     = [(live_map.get(s,{}).get('LTP',p)-p)/p*100 if p>0 else 0
                                   for s,p in zip(hmap['Symbol'],hmap['BuyPrice'])]
            fig = px.treemap(hmap, path=[px.Constant("Portfolio"),"Sector","Symbol"],
                             values="Deployment", color="PnLPct",
                             color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
                             hover_data=["Quantity","BuyPrice"])
            fig.update_layout(margin=dict(t=10,l=0,r=0,b=0), height=320,
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        with right_col:
            section("Alpha Benchmarking vs Nifty 500")
            df_closed = load_closed_trades_db()
            if df_closed is not None and not df_closed.empty:
                try:
                    dfc = df_closed.rename(columns=JOURNAL_RENAME_MAP) if 'exit_price' in df_closed.columns else df_closed.copy()
                    dfc['ExitDate'] = pd.to_datetime(dfc['ExitDate'])
                    dfc = dfc.sort_values('ExitDate')
                    dfc['PnL'] = (
                        pd.to_numeric(dfc['ExitPrice'],errors='coerce').fillna(0) -
                        pd.to_numeric(dfc['BuyPrice'], errors='coerce').fillna(0)
                    ) * pd.to_numeric(dfc['Quantity'],errors='coerce').fillna(0)
                    pc = dfc.groupby('ExitDate').agg({'PnL':'sum'}).reset_index()
                    pc['CumulativePnL'] = pc['PnL'].cumsum()
                    if total_cap > 0:
                         pc['Portfolio_%'] = (pc['CumulativePnL'] / total_cap) * 100
                    else:
                         pc['Portfolio_%'] = 0.0
                    pc = pc.rename(columns={'ExitDate': 'Date'})
                    nifty = yf.download("^NSEI", start=pc['Date'].min()-pd.Timedelta(days=7),
                                        end=pc['Date'].max()+pd.Timedelta(days=1), progress=False)
                    if not nifty.empty:
                        nifty = nifty['Close'].reset_index()
                        nifty.columns = ['Date','NiftyClose']
                        nifty['Date'] = pd.to_datetime(nifty['Date']).dt.tz_localize(None)
                        if isinstance(nifty['NiftyClose'], pd.DataFrame):
                             nifty['NiftyClose'] = nifty['NiftyClose'].iloc[:, 0]
                        nifty['Benchmark_%'] = ((nifty['NiftyClose'] - nifty['NiftyClose'].iloc[0]) / nifty['NiftyClose'].iloc[0]) * 100
                        merged = pd.merge_asof(pc, nifty[['Date','Benchmark_%']], on='Date')
                        fig2 = px.line(merged, x='Date', y=['Portfolio_%','Benchmark_%'], 
                                       labels={'value': 'Percentage Return (%)', 'variable': 'Metric'})
                        fig2.update_layout(height=300, margin=dict(t=10,l=0,r=0,b=0),
                                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                           legend=dict(font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
                                           yaxis_title="% Return")
                        st.plotly_chart(fig2, use_container_width=True)
                except Exception as e:
                    st.error(f"Chart error: {e}")
            else:
                st.info("No closed trades to benchmark yet.")

        # ── ACTIVE POSITIONS P&L TABLE ──
        section("Active Positions — Live P&L")
        pnl_rows = []
        
        from ai_risk_manager import get_atr, get_nifty_correlation
        
        for _, row in df_active.iterrows():
            sym = row['Symbol']
            bp = float(row.get('BuyPrice', 0) or 0)
            qty = float(row.get('Quantity', 0) or 0)
            ltp = live_map.get(sym, {}).get('LTP', bp)
            sl = float(row.get('StopLoss', 0) or 0)
            tgt = float(row.get('Target', 0) or 0)
            pnl_rs = (ltp - bp) * qty
            pnl_pct = ((ltp - bp) / bp * 100) if bp > 0 else 0
            dist_sl = ((ltp - sl) / ltp * 100) if sl > 0 and ltp > 0 else 0
            dist_tgt = ((tgt - ltp) / ltp * 100) if tgt > 0 and ltp > 0 else 0
            
            # Quantitative Diagnostics
            atr_val = get_atr(sym)
            if atr_val > 0 and sl > 0:
                sl_atr = round((ltp - sl) / atr_val, 1)
            else:
                sl_atr = "N/A"
            nifty_corr = get_nifty_correlation(sym)
            
            entry_dt = row.get('EntryDate', '')
            try:
                days_held = (pd.Timestamp.now() - pd.to_datetime(entry_dt)).days if entry_dt else 0
            except:
                days_held = 0
            pnl_rows.append({
                'Symbol': sym, 'Entry': round(bp, 2), 'LTP': round(ltp, 2),
                'P&L ₹': round(pnl_rs, 0), 'P&L %': round(pnl_pct, 1),
                'Dist SL %': round(dist_sl, 1), 'Dist Tgt %': round(dist_tgt, 1),
                'SL (ATR)': sl_atr, 'Nifty Corr': nifty_corr,
                'Days': days_held
            })
        if pnl_rows:
            df_pnl = pd.DataFrame(pnl_rows)
            st.dataframe(df_pnl, use_container_width=True, hide_index=True, height=300)

        # ── CORRELATION RISK MATRIX ──
        section("Portfolio Correlation Risk")
        with st.expander("🔍 View Correlation Matrix & Shadow Concentration", expanded=False):
            syms_for_corr = df_active['Symbol'].unique().tolist()
            if len(syms_for_corr) >= 2:
                try:
                    with st.spinner("Computing correlation matrix..."):
                        corr_df, shadows, div_score = get_portfolio_correlation_matrix(syms_for_corr)
                    dc1, dc2 = st.columns([1, 1])
                    with dc1:
                        st.metric("Diversification Score", f"{div_score}/10")
                    with dc2:
                        if shadows:
                            st.warning(f"⚠️ {len(shadows)} Shadow Concentration pair(s) detected!")
                            for sp in shadows:
                                st.caption(f"  {sp['Pair']} → r={sp['Correlation']} ({sp['Risk']})")
                        else:
                            st.success("✅ No shadow concentration detected.")
                    if not corr_df.empty:
                        import plotly.figure_factory as ff
                        fig_corr = ff.create_annotated_heatmap(
                            z=corr_df.values.round(2).tolist(),
                            x=corr_df.columns.tolist(), y=corr_df.index.tolist(),
                            colorscale='RdYlGn', showscale=True
                        )
                        fig_corr.update_layout(height=350, margin=dict(t=30,l=0,r=0,b=0),
                                               paper_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig_corr, use_container_width=True)
                    else:
                        st.info(f"Correlation matrix returned empty for symbols: {', '.join(syms_for_corr[:5])}")
                except Exception as e:
                    st.error(f"Correlation Error: {e}")
            else:
                st.info("Need at least 2 open positions for correlation analysis.")
    else:
        st.info("No open positions found. Launch a scanner to populate your portfolio.")


# ════════════════════════════════════════════════════════════════════
#  HUNTER
# ════════════════════════════════════════════════════════════════════
elif page == 'HUNTER':
    st.markdown('<div class="page-title">🎯 Hunter</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Stock Discovery Engine</div>', unsafe_allow_html=True)

    hunter_tab = st.session_state.huntertab

    if hunter_tab == 'SCANNERS':
        section("Chartink Scanners")
        left, right = st.columns(2, gap="medium")
        with left:
            sub_label("📌  Positional Strategies")
            if st.button("Stage 2 Hunter\nLong-horizon stage-based breakout entries.\n→  Run Scanner", use_container_width=True, key="h_s2"):
                launch_script("chartink_scanner_pro.py","1")
            if st.button("Early Birds Accumulation\nEarly-stage accumulation zone detection.\n→  Run Scanner", use_container_width=True, key="h_eb"):
                launch_script("chartink_scanner_pro.py","3")
        with right:
            sub_label("📈  Swing Strategies")
            if st.button("Stage 2 Pullback\nShort-term pullback within an uptrend.\n→  Run Scanner", use_container_width=True, key="h_pb"):
                launch_script("chartink_scanner_pro.py","2")
            if st.button("Strong Leaders\nMomentum leaders with relative strength.\n→  Run Scanner", use_container_width=True, key="h_sl"):
                launch_script("chartink_scanner_pro.py","4")

    elif hunter_tab == 'ENRICHMENT':
        section("Fundamental Data")
        left, right = st.columns(2, gap="medium")
        with left:
            if st.button("🌐  Fetch Screener.in Data\nPull raw fundamental HTML from Screener.in.\n→  Fetch Now", use_container_width=True, key="e_fetch"):
                launch_script("screener_fetcher.py")
        with right:
            if st.button("⚙️  Process HTML to CSV\nConvert raw HTML into structured CSV for analysis.\n→  Process Now", use_container_width=True, key="e_proc"):
                launch_script("screener_processor.py")

    elif hunter_tab == 'SELECTION':
        section("Golden Matcher Engine")
        if st.button("🏆  Run Golden Matcher\nCombines Technical Scans with Fundamental Filters to find 5-Star setups.\n→  Initiate Matching", type="primary", use_container_width=True, key="sel_run"):
            launch_script("brute_force_match_pro.py")
        section("Ultimate Golden Meta-Ranking")
        st.markdown("Aggregated ranking across **all** active strategies, sorted by AI Conviction.")
        
        pmap = {"Stage 2 Hunter":"FINAL_Hunter_Picks.csv",
                "Stage 2 Pullback":"FINAL_Pullback_Picks.csv",
                "Early Birds":"FINAL_EarlyBird_Picks.csv",
                "Strong Leaders":"FINAL_Leader_Picks.csv"}
        
        master_dfs = []
        for strat_name, fname in pmap.items():
            if os.path.exists(fname):
                try:
                    df_t = pd.read_csv(fname)
                    df_t.insert(0, 'Strategy', strat_name)
                    master_dfs.append(df_t)
                except: pass
                
        if master_dfs:
            master_df = pd.concat(master_dfs, ignore_index=True)
            # Create a sorting weight for Conviction
            conv_map = {'High': 3, 'Medium': 2, 'Low': 1, 'N/A': 0}
            if 'Conviction' in master_df.columns:
                master_df['Conv_Score'] = master_df['Conviction'].map(conv_map).fillna(0)
            else:
                master_df['Conv_Score'] = 0
            
            # Sort by Conviction Score (High to Low), then by Volume or %Chg if available
            sort_cols = ['Conv_Score']
            asc_opts = [False]
            if '%Chg' in master_df.columns:
                sort_cols.append('%Chg')
                asc_opts.append(False)
                
            master_df = master_df.sort_values(by=sort_cols, ascending=asc_opts)
            
            # Display Master Ranking
            show_cols = ['Strategy', 'Symbol']
            if 'Conviction' in master_df.columns: show_cols.append('Conviction')
            if 'AI Catalyst' in master_df.columns: show_cols.append('AI Catalyst')
            if 'AI_Catalyst' in master_df.columns: show_cols.append('AI_Catalyst')
            if '%Chg' in master_df.columns: show_cols.append('%Chg')
            if 'Volume' in master_df.columns: show_cols.append('Volume')
            
            st.dataframe(master_df[show_cols].head(25), use_container_width=True, hide_index=True)
        else:
            st.info("No Final Golden Pick CSVs found. Run the Golden Matcher first.")
            
        st.markdown("---")
        section("Category Drill-Down")
        preview_cat = st.selectbox("Select Strategy to drill down into specific fundamentals:", list(pmap.keys()))
        fname = pmap.get(preview_cat,"")
        if os.path.exists(fname):
            try:
                df_res = pd.read_csv(fname)
                ai_c = [c for c in ["Symbol","Conviction","AI Catalyst", "AI_Catalyst"] if c in df_res.columns]
                ot_c = [c for c in df_res.columns if c not in ai_c]
                st.dataframe(df_res[ai_c+ot_c], use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Error loading preview: {e}")
        else:
            st.info(f"No 5-Star matches found in the latest '{preview_cat}' scan.")


# ════════════════════════════════════════════════════════════════════
#  WATCHLIST
# ════════════════════════════════════════════════════════════════════
elif page == 'WATCHLIST':
    st.markdown('<div class="page-title">📋 Watchlist Sync</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Synchronize your selected setups across all platforms.</div>', unsafe_allow_html=True)

    wl_tab = st.session_state.watchlisttab

    if wl_tab == 'GENERATION':
        left_col, right_col = st.columns(2, gap="medium")
        with left_col:
            section("1. Local Generation")
            if st.button("📁  Generate CSVs — Local\nGenerate clean CSVs for local analysis.\n→  Generate Now", key="wl_gen"):
                launch_script("watchlist_manager.py")
        with right_col:
            section("2. TV Pine Screener Generator")
            st.info("Upload a TradingView Watchlist (.txt) to automatically generate your Ultimate Screener indicator.")
            uploaded_wl = st.file_uploader("Upload Watchlist (.txt)", type=["txt"])
            if uploaded_wl is not None:
                raw_text = uploaded_wl.read().decode("utf-8")
                # Parse symbols (lines, removing commas)
                raw_syms = [s.strip() for s in raw_text.replace(',', '\n').split('\n') if s.strip()]
                pine_code = generate_pine_code(raw_syms)
                st.download_button(
                    label="⬇️ Download Generated .pine",
                    data=pine_code,
                    file_name="Commander_Screener_Custom.pine",
                    mime="text/plain"
                )

    elif wl_tab == 'SYNC':
        section("2. External Cloud Sync")
        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            if st.button("💸  Sync to Strike.Money\nPush watchlist to Strike.Money platform.\n→  Sync Now", use_container_width=True, key="wl_strike"):
                launch_script("strike_automation.py","--mode watchlist")
        with c2:
            if st.button("📊  Sync to TradingView\nSync curated lists to TradingView.\n→  Sync Now", use_container_width=True, key="wl_tv"):
                launch_script("tradingview_automation_v2.py")
        with c3:
            if st.button("🔁  Master Sync — All\nPush to all connected platforms simultaneously.\n→  Sync All", type="primary", use_container_width=True, key="wl_master"):
                launch_script("master_portfolio_sync.py")

        section("3. Email Dispatches")
        c4, c5 = st.columns(2, gap="small")
        with c4:
            if st.button("📧  Send Test Email\nVerify SMTP Connection.\n→  Send Now", use_container_width=True, key="wl_em_test"):
                launch_script("gmail_dispatcher.py", "--mode test")
        with c5:
            if st.button("🏆  Email Golden Matches\nSend latest AI 5-Star picks to your inbox.\n→  Send Now", use_container_width=True, key="wl_em_match"):
                launch_script("gmail_dispatcher.py", "--mode matches")


# ════════════════════════════════════════════════════════════════════
#  COMMAND
# ════════════════════════════════════════════════════════════════════
elif page == 'COMMAND':
    st.markdown('<div class="page-title">⚡ Command Center</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Active trade management and execution protocols.</div>', unsafe_allow_html=True)

    cmd_tab = st.session_state.commandtab

    if cmd_tab == 'ACTIVEOPS':
        section("Active Operations")
        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            if st.button("🎯  Sniper Entry AI v2\nOrder execution with Institutional AI analysis.\n→  Launch", use_container_width=True, key="cmd_sniper"):
                launch_script("sniper_trigger.py")
        with c2:
            if st.button("🛡️  GTT Auto-Shield\nAuto-protect holdings using Journal levels.\n→  Launch", use_container_width=True, key="cmd_gtt"):
                launch_script("gtt_auto_shield.py")
        with c3:
            if st.button("📲  Telegram Sentinel\nActive market monitoring via Mobile.\n→  Launch", use_container_width=True, key="cmd_tg"):
                launch_script("telegram_sentinel.py")
        section("External Apps")
        if st.button("📓  Open Full Journal App\nLaunch the complete trade journal interface.\n→  Open", use_container_width=True, key="cmd_journal"):
            launch_script("dhan_journal_v7.py", is_streamlit=True)

    elif cmd_tab == 'LEDGER':
        section("Live Trade Ledger")
        df_j = load_journal_db()
        if not df_j.empty:
            show = [c for c in ["Symbol","Type","BuyPrice","Quantity","Status",
                                 "Sector","StopLoss","Target","PlannedRR","Timeframe"] if c in df_j.columns]
            st.dataframe(df_j[show], use_container_width=True, height=500, hide_index=True)
        else:
            st.info("No open trades found in the system.")


# ════════════════════════════════════════════════════════════════════
#  AI LAB
# ════════════════════════════════════════════════════════════════════
elif page == 'AI LAB':
    st.markdown('<div class="page-title">🧠 AI Laboratory</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Advanced Generative AI workflows and automation.</div>', unsafe_allow_html=True)

    ai_tab = st.session_state.ailabtab

    if ai_tab == 'PREFLIGHT':
        section("AI-Trade Proposer — Pre-flight Check")
        p1, p2, p3 = st.columns([2,1,1], gap="small")
        with p1: prop_sym   = st.text_input("Ticker Symbol", key="prop_sym", placeholder="e.g. RELIANCE").upper()
        with p2: prop_entry = st.number_input("Entry Price", min_value=0.0, step=0.1, key="prop_entry")
        with p3: prop_risk  = st.number_input("Risk ₹", value=5000, step=500, key="prop_risk")
        if st.button("🛫  Run Analysis\nScore and size a new trade before execution.\n→  Analyse Now", type="primary", use_container_width=True, key="btn_analysis"):
            if not prop_sym:
                st.error("Enter ticker.")
            else:
                with st.spinner(f"Analyzing {prop_sym}..."):
                    try:
                        # 1. Fetch LTP for accurate grading
                        ticker_sym = clean_symbol(prop_sym)
                        if not ticker_sym.startswith("^"): ticker_sym = f"{ticker_sym}.NS"
                        
                        ticker = yf.Ticker(ticker_sym)
                        hist = ticker.history(period="1mo") # Get more to avoid gaps
                        if hist.empty:
                            st.warning(f"Could not fetch data for {ticker_sym}. Using manual entry price.")
                            ltp_val = prop_entry
                        else:
                            ltp_val = hist['Close'].iloc[-1]
                        
                        # 2. Simple Sector Mapping (Fallback)
                        prop_sector = "Unknown"
                        from dhan_journal_v7 import get_sector
                        prop_sector = get_sector(prop_sym)
                        
                        # 3. Call Hybrid Quant+AI grading
                        rating_res   = get_weinstein_score(
                            symbol=prop_sym,
                            sector=prop_sector,
                            ltp=ltp_val,
                            buy_price=prop_entry
                        )
                        
                        atr_val      = get_atr(prop_sym)
                        atr_mult     = get_adaptive_atr_multiplier(prop_sym)
                        suggested_sl = prop_entry - (atr_mult * atr_val) if atr_val else 0
                        qty = int(prop_risk / (prop_entry - suggested_sl)) if (prop_entry - suggested_sl) > 0 else 0
                        
                        # Display Quant Scorecard
                        r1, r2, r3, r4 = st.columns(4)
                        r1.metric("Weinstein Grade", rating_res.get('rating','N/A'))
                        r2.metric("Quant Score", f"{rating_res.get('quant_score', 0)}/100")
                        r3.metric("Suggested SL", f"₹{format_inr(suggested_sl)}")
                        r4.metric("Rec. Quantity", f"{qty} shares")
                        
                        st.info(f"AI Rationale: {rating_res.get('reason','N/A')}")
                        
                        # Show Quant Breakdown
                        breakdown = rating_res.get('breakdown', {})
                        if breakdown:
                            with st.expander("📊 Quant Scorecard Breakdown", expanded=True):
                                for factor, detail in breakdown.items():
                                    st.caption(f"**{factor}:** {detail}")
                    except Exception as e:
                        st.error(f"Analysis error: {e}")

    elif ai_tab == 'GENERATIVE':
        section("Generative Analysis")
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            if st.button("🔬  AI Post-Trade Autopsy\nAI-driven post-trade performance review.\n→  Launch", use_container_width=True, key="ai_autopsy"):
                launch_script("portfolio_analytics.py", is_streamlit=True)
            if st.button("📋  Auto-Plan Journal\nAI-assisted journal planning and entry.\n→  Launch", use_container_width=True, key="ai_journal"):
                launch_script("dhan_journal_v7.py", is_streamlit=True)
        with c2:
            if st.button("✍️  Standalone Prompt Gen\nStandalone AI prompt generation tools.\n→  Launch", use_container_width=True, key="ai_prompt"):
                launch_script("generate_prompt_standalone.py")
        section("Cache Management")
        if st.button("🗑️  Clear AI Cache\nFetch fresh data on next run.\n→  Clear Now", use_container_width=True, key="ai_cache"):
            if os.path.exists("ai_cache.json"):
                os.remove("ai_cache.json")
                st.success("AI Cache Cleared!")
            else:
                st.info("Cache is already empty.")

    elif ai_tab == 'WORKFLOWS':
        section("Workflow Automation — Inline Pipeline")
        if st.button("🤖  Run Full Auto-Pilot\nExecute full pipeline: Scanners → Fundamentals → Golden Matching → Watchlist Sync.\n→  Initiate", type="primary", use_container_width=True, key="wf_run"):
            import time as _time
            phases = [
                ("Phase 1/9: Technical Scanners (Chartink)", "chartink_scanner_pro", "run_scan"),
                ("Phase 2/9: Fetching Fundamental Data", "screener_fetcher", "fetch_screener_data"),
                ("Phase 3/9: Processing HTML to CSV", "screener_processor", "process_screener_pages"),
                ("Phase 4/9: Golden Matcher", "brute_force_match_pro", "perform_match"),
                ("Phase 5/9: Generating Watchlists", "watchlist_manager", "generate_tradingview_files"),
            ]
            progress_bar = st.progress(0, text="Initializing Auto-Pilot...")
            results_log = []
            total = len(phases)
            for i, (label, module_name, func_name) in enumerate(phases):
                progress_bar.progress((i) / total, text=f"⏳ {label}")
                try:
                    mod = __import__(module_name)
                    fn = getattr(mod, func_name)
                    if module_name == "chartink_scanner_pro":
                        for scan_key in ['1', '2', '3', '4']:
                            fn(scan_key)
                            _time.sleep(0.5)
                    elif module_name == "screener_fetcher":
                        fn(interactive=False)
                    elif module_name == "brute_force_match_pro":
                        fn(return_raw=True)
                    elif module_name == "watchlist_manager":
                        fn(silent=True)
                    else:
                        fn()
                    results_log.append(f"✅ {label}")
                except Exception as e:
                    results_log.append(f"❌ {label}: {e}")
                progress_bar.progress((i + 1) / total, text=f"✅ {label}")
            
            progress_bar.progress(1.0, text="✅ Pipeline Complete!")
            st.success("🏁 Full Auto-Pilot Complete!")
            for log in results_log:
                st.caption(log)

        st.markdown("---")
        section("Sniper Entry — Web Interface")
        sub_label("🎯  Advanced Position Size Calculator & Order Entry")
        
        # Initialize session state for smart defaults
        if "prev_sniper_sym" not in st.session_state: 
            st.session_state.prev_sniper_sym = ""
            
        s1, s2 = st.columns([2, 2], gap="small")
        with s1: 
            sniper_sym_input = st.text_input("Stock Symbol", placeholder="e.g. CHOLAFIN").upper().strip()
            
        if sniper_sym_input != st.session_state.prev_sniper_sym and sniper_sym_input != "":
            st.session_state.prev_sniper_sym = sniper_sym_input
            try:
                import yfinance as yf
                from ai_risk_manager import get_atr
                ticker_yf = f"{sniper_sym_input}.NS"
                atr_val = get_atr(sniper_sym_input)
                # Fast LTP fetch
                info = yf.Ticker(ticker_yf).fast_info
                ltp = info.get("lastPrice", 0.0)
                if ltp > 0:
                    st.session_state.sniper_entry = round(ltp, 2)
                    st.session_state.sniper_sl = round(ltp - (2.0 * atr_val), 2)
                else:
                    st.session_state.sniper_entry = 0.0
                    st.session_state.sniper_sl = 0.0
            except Exception:
                pass

        c1, c2, c3 = st.columns([1, 1, 1], gap="small")
        with c1: 
            sniper_entry = st.number_input("Entry Price ₹", min_value=0.0, step=0.1, key="sniper_entry")
        with c2: 
            sniper_sl = st.number_input("Stop Loss ₹", min_value=0.0, step=0.1, key="sniper_sl")
        with c3: 
            risk_pct = st.slider("Max Risk %", min_value=0.25, max_value=2.0, value=1.0, step=0.25, key="sniper_risk_pct")
        
        if sniper_sym_input and sniper_entry > 0 and sniper_sl > 0 and sniper_entry > sniper_sl:
            risk_per_share = sniper_entry - sniper_sl
            risk_pct_of_entry = (risk_per_share / sniper_entry) * 100
            max_risk_rupees = balance * (risk_pct / 100.0)
            sniper_qty = math.floor(max_risk_rupees / risk_per_share) if risk_per_share > 0 else 0
            
            # 20% max per stock portfolio cap
            max_cap_allowed = balance * 0.20  
            capped_reason = ""
            if sniper_qty * sniper_entry > max_cap_allowed:
                sniper_qty = math.floor(max_cap_allowed / sniper_entry)
                capped_reason = f"Capped at 20% Portfolio Max: ₹{format_inr_int(max_cap_allowed)}"
                
            trade_value = sniper_qty * sniper_entry
            target_2r = sniper_entry + (risk_per_share * 2)
            target_3r = sniper_entry + (risk_per_share * 3)
            
            if capped_reason:
                st.info(f"💡 **Position Size Adjusted**: {capped_reason}")
            
            q1, q2, q3, q4 = st.columns(4)
            q1.metric("Quantity", f"{sniper_qty} shares")
            q2.metric("Trade Value", f"₹{format_inr_int(trade_value)}")
            q3.metric("Risk/Trade", f"₹{format_inr_int(max_risk_rupees)}")
            q4.metric("Risk %", f"{risk_pct_of_entry:.1f}%")
            t1, t2 = st.columns(2)
            t1.metric("Target 2R", f"₹{format_inr(target_2r)}")
            t2.metric("Target 3R", f"₹{format_inr(target_3r)}")
            
            if st.button("🚀  Execute CNC Order via Dhan", type="primary", use_container_width=True, key="sniper_exec"):
                try:
                    from dhan_symbols import get_nse_id_map
                    id_map = get_nse_id_map()
                    sec_id = id_map.get(sniper_sym_input)
                    if not sec_id:
                        st.error(f"❌ Symbol '{sniper_sym_input}' not found in NSE master.")
                    else:
                        from dhanhq import dhanhq as DhanHQ
                        dhan_exec = DhanHQ(CLIENT_ID, ACCESS_TOKEN)
                        from datetime import datetime as dt
                        now = dt.now()
                        mkt_open = now.replace(hour=9, minute=15, second=0)
                        mkt_close = now.replace(hour=15, minute=30, second=0)
                        is_amo = not (mkt_open <= now <= mkt_close and now.weekday() < 5)
                        order = dhan_exec.place_order(
                            security_id=sec_id, exchange_segment=dhan_exec.NSE,
                            transaction_type=dhan_exec.BUY, quantity=sniper_qty,
                            order_type=dhan_exec.LIMIT, product_type=dhan_exec.CNC,
                            price=sniper_entry, after_market_order=is_amo,
                            trading_symbol=sniper_sym_input
                        )
                        if order.get('status') == 'success':
                            st.success(f"✅ Order Placed! ID: {order['data']['orderId']}")
                            st.toast(f"🎯 {sniper_sym_input} order placed successfully!")
                        else:
                            st.error(f"❌ Order Failed: {order.get('remarks', 'Unknown error')}")
                except Exception as e:
                    st.error(f"❌ Execution Error: {e}")
        elif sniper_sym_input and sniper_entry > 0 and sniper_sl > 0:
            st.warning("⚠️ Entry Price must be higher than Stop Loss for a Long trade.")
