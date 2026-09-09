import streamlit as st
import pandas as pd
import os, sys, sqlite3, base64
from dotenv import load_dotenv
from dhan_auth import ensure_valid_token
from dhanhq import dhanhq
try:
    from dhanhq import DhanContext
except ImportError:
    DhanContext = None
from ai_risk_manager import get_market_health, get_noise_risk_stats, get_atr
from ai_grading_engine import get_weinstein_score
import plotly.express as px
import yfinance as yf

def clean_symbol(symbol):
    """Clean Dhan symbols by stripping suffixes and mapping indices."""
    s = str(symbol).strip().upper().replace("NSE:", "").replace("BSE:", "")
    if s == "NIFTY": return "^NSEI"
    if s == "BANKNIFTY" or s == "NIFTYBANK": return "^NSEBANK"
    for suffix in ['-EQ', '-BE', '-SM', '-ST', '-BZ']:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    return s

# Page config removed (handled by router)
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
        dhan = dhanhq(DhanContext(CLIENT_ID, ACCESS_TOKEN)) if DhanContext else dhanhq(CLIENT_ID, ACCESS_TOKEN)
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
        if not CLIENT_ID or not ACCESS_TOKEN: return 0, 0.0
        dhan = dhanhq(DhanContext(CLIENT_ID, ACCESS_TOKEN)) if DhanContext else dhanhq(CLIENT_ID, ACCESS_TOKEN)
        resp = dhan.get_holdings()
        if isinstance(resp, dict) and resp.get('status') == 'success':
            data = resp.get('data', [])
            total_deployed = sum(float(item.get('avgCostPrice', 0)) * float(item.get('totalQty', 0)) for item in data if float(item.get('totalQty', 0)) > 0)
            open_count = len([item for item in data if float(item.get('totalQty', 0)) > 0])
            return open_count, total_deployed
        return 0, 0.0
    except:
        return 0, 0.0

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
            # Q5 FIX: also drop rows with no valid buy price — a 0 cost basis is a
            # data error and would fake unrealized P&L / understate deployed capital.
            df = df[(df['Quantity'] > 0) & (df['BuyPrice'] > 0)].copy() # Filter ghosts/errors
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
live_pos, live_dep    = get_live_holdings_stats()
is_healthy, mkt_ltp, mkt_sma = get_market_health("NSE:CNX500")

df_active_global      = load_journal_db()
if not df_active_global.empty:
    noise_count_g, noise_syms_g = get_noise_risk_stats(df_active_global)
else:
    noise_count_g, noise_syms_g = 0, []

h_color      = "#15803D" if is_healthy        else "#DC2626"
h_text       = "HEALTHY" if is_healthy        else "WEAK"
w_color      = "#DC2626" if noise_count_g > 0 else "#15803D"
w_text       = f"⚠ {noise_count_g} AT RISK"  if noise_count_g > 0 else "✔ SECURE"
s_color      = "#15803D" if sys_status == "SYSTEM ONLINE" else "#DC2626"

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
    background: #EBF1F6 !important;
    font-family: 'Inter', sans-serif; color: #090D16;
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
    background: #E2E8F0 !important;
    border-right: 2px solid #94A3B8 !important;
    width: 230px !important; min-width: 230px !important;
    padding: 0 !important;
    transform: none !important;
    visibility: visible !important;
    display: block !important;
}}
[data-testid="stSidebar"] > div {{ padding: 0 !important; }}
[data-testid="stSidebarContent"] {{
    padding: 0 !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    scrollbar-width: thin;
    scrollbar-color: #94A3B8 #E2E8F0;
}}
[data-testid="stSidebarContent"]::-webkit-scrollbar {{ width: 5px; }}
[data-testid="stSidebarContent"]::-webkit-scrollbar-track {{ background: #E2E8F0; }}
[data-testid="stSidebarContent"]::-webkit-scrollbar-thumb {{ background: #94A3B8; border-radius: 3px; }}

/* ── TOP STATUS BAR ── */
.statusbar {{
    display: grid; grid-template-columns: repeat(5, 1fr);
    gap: 1px; background: #94A3B8; border-bottom: 2px solid #64748B;
}}
.sb-cell {{ background: #FFFFFF; padding: 6px 16px; display: flex; flex-direction: column; justify-content: center; }}
.sb-label {{ font-family: 'JetBrains Mono',monospace; font-size: 0.60rem; color: #334155; letter-spacing: 2px; text-transform: uppercase; font-weight: 700; }}
.sb-value {{ font-family: 'JetBrains Mono',monospace; font-size: 0.95rem; font-weight: 700; margin-top: 1px; letter-spacing: 0.5px; color: #090D16; }}

/* ── PAGE TITLE ── */
.page-title {{
    font-family: 'Rajdhani',sans-serif; font-size: 1.6rem; font-weight: 800;
    letter-spacing: 3px; text-transform: uppercase; color: #090D16;
    border-left: 4px solid #1D4ED8; padding-left: 12px; margin: 14px 0 4px 0;
}}
.page-desc {{
    font-size: 0.70rem; color: #1E293B; letter-spacing: 2px; text-transform: uppercase;
    margin: 0 0 12px 15px; font-family: 'JetBrains Mono',monospace; font-weight: 700;
}}

/* ── SECTION HEADER ── */
.section-hdr {{
    font-family: 'JetBrains Mono',monospace; font-size: 0.65rem; color: #1E3A8A;
    letter-spacing: 3px; text-transform: uppercase; margin: 14px 0 8px 0;
    display: flex; align-items: center; gap: 10px; font-weight: 700;
}}
.section-hdr::after {{ content:''; flex:1; height:2px; background:#94A3B8; }}

/* ── SUB SECTION LABEL ── */
.section-sub-lbl {{
    font-family: 'Rajdhani', sans-serif;
    font-size: 1.05rem; font-weight: 700;
    color: #1E3A8A; letter-spacing: 1.5px; text-transform: uppercase;
    padding: 6px 14px;
    background: #DBEAFE;
    border-left: 4px solid #1D4ED8;
    border-radius: 0 4px 4px 0;
    margin-bottom: 8px;
}}

/* ── ACTION BUTTONS (card-style, tall) ── */
button[kind="secondary"] {{
    background: #FFFFFF !important; border: 1.5px solid #64748B !important;
    border-radius: 6px !important; color: #0F172A !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.84rem !important; font-weight: 600 !important;
    letter-spacing: 0.1px !important; text-transform: none !important;
    padding: 12px 16px !important; width: 100% !important;
    text-align: left !important; line-height: 1.6 !important;
    min-height: 76px !important; transition: all .15s ease !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
}}
button[kind="secondary"]:hover {{
    background: #F1F5F9 !important; border-color: #1D4ED8 !important;
    color: #1E3A8A !important;
    box-shadow: inset 4px 0 0 #1D4ED8, 0 2px 6px rgba(29,78,216,.2) !important;
}}
button[kind="secondary"] p {{
    white-space: pre-line !important; text-align: left !important;
    margin: 0 !important; color: #0F172A !important;
    font-size: 0.84rem !important; font-weight: 600 !important; line-height: 1.6 !important;
}}

button[kind="primary"] {{
    background: #1D4ED8 !important; border: 1.5px solid #1E40AF !important;
    border-radius: 6px !important; color: #FFFFFF !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.84rem !important; font-weight: 700 !important;
    letter-spacing: 0.1px !important; text-transform: none !important;
    padding: 12px 16px !important; width: 100% !important;
    text-align: left !important; line-height: 1.6 !important;
    min-height: 76px !important;
    box-shadow: 0 2px 5px rgba(29,78,216,.3) !important;
    transition: all .15s ease !important;
}}
button[kind="primary"]:hover {{
    background: #1E40AF !important;
    box-shadow: 0 3px 10px rgba(29,78,216,.45), inset 4px 0 0 #93C5FD !important;
    color: #FFFFFF !important;
}}
button[kind="primary"] p {{
    white-space: pre-line !important; text-align: left !important;
    margin: 0 !important; color: #FFFFFF !important;
    font-size: 0.84rem !important; font-weight: 700 !important; line-height: 1.6 !important;
}}

/* ── SIDEBAR NAV BUTTONS ── */
[data-testid="stSidebar"] button {{
    background: transparent !important; border: none !important;
    border-radius: 0 !important; border-left: 3px solid transparent !important;
    padding: 8px 16px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.86rem !important; font-weight: 600 !important;
    color: #1E293B !important; letter-spacing: 0.3px !important;
    text-transform: none !important; text-align: left !important;
    width: 100% !important; min-height: 0 !important;
    line-height: 1.3 !important; box-shadow: none !important;
    transition: all .12s ease !important;
}}
[data-testid="stSidebar"] button:hover {{
    background: #CBD5E1 !important; color: #000000 !important;
    border-left-color: #64748B !important; box-shadow: none !important;
}}
[data-testid="stSidebar"] button[kind="primary"] {{
    background: #BFDBFE !important; color: #1E3A8A !important;
    border-left-color: #1D4ED8 !important; font-weight: 700 !important;
    box-shadow: none !important;
}}
[data-testid="stSidebar"] button[kind="primary"]:hover {{
    background: #93C5FD !important; box-shadow: none !important;
}}
[data-testid="stSidebar"] button p {{
    white-space: nowrap !important; text-align: left !important;
    font-size: 0.86rem !important; color: inherit !important; font-weight: inherit !important;
}}

/* ── SIDEBAR RADIO ── */
[data-testid="stRadio"] {{ margin: 1px 0 !important; }}
[data-testid="stRadio"] label {{
    background: transparent !important; border: none !important;
    border-radius: 0 !important; border-left: 3px solid transparent !important;
    padding: 6px 14px 6px 28px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.88rem !important; font-weight: 600 !important;
    color: #1E293B !important; letter-spacing: 0.2px !important;
    text-transform: none !important; cursor: pointer !important;
    transition: all .12s !important; margin: 0 !important; display: block !important;
}}
[data-testid="stRadio"] label:hover {{
    background: #CBD5E1 !important; color: #000000 !important;
    border-left-color: #64748B !important;
}}
[data-testid="stRadio"] label[data-checked="true"] {{
    background: #BFDBFE !important; color: #1E3A8A !important;
    border-left-color: #1D4ED8 !important; font-weight: 700 !important;
}}
[role="radiogroup"] input {{ display: none !important; }}
[role="radiogroup"] [data-testid="stMarkdownContainer"] p {{
    margin: 0 !important; font-size: 0.88rem !important; color: inherit !important; font-weight: inherit !important;
}}

/* ── SIDEBAR SECTION LABEL ── */
.sb-section-lbl {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem; color: #334155; letter-spacing: 2.5px; text-transform: uppercase; font-weight: 800;
    padding: 8px 16px 4px; border-top: 1.5px solid #94A3B8; margin-top: 4px;
}}

/* ── METRICS & FORM INPUTS ── */
[data-testid="metric-container"] {{
    background: #FFFFFF !important; border: 1.5px solid #CBD5E1 !important;
    border-radius: 6px !important; padding: 10px 14px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
}}
[data-testid="metric-container"] label {{
    font-family: 'JetBrains Mono',monospace !important; font-size: 0.62rem !important;
    color: #334155 !important; letter-spacing: 2px !important; text-transform: uppercase !important; font-weight: 700 !important;
}}
[data-testid="metric-container"] [data-testid="stMetricValue"] {{
    font-family: 'JetBrains Mono',monospace !important; font-size: 1.25rem !important;
    font-weight: 700 !important; color: #090D16 !important;
}}

/* ── MISC ── */
[data-testid="stDataFrame"] {{ border: 1.5px solid #CBD5E1 !important; border-radius: 6px !important; }}
iframe {{ border-radius: 6px !important; }}
hr {{ border-color: #94A3B8 !important; margin: 10px 0 !important; }}
[data-testid="stToast"] {{
    background: #FFFFFF !important; border: 2px solid #1D4ED8 !important;
    border-radius: 6px !important; color: #0F172A !important;
    font-family: 'Inter', sans-serif !important; font-weight: 600 !important;
}}
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {{
    background: #FFFFFF !important; border: 1.5px solid #64748B !important;
    border-radius: 4px !important; color: #090D16 !important;
    font-family: 'JetBrains Mono',monospace !important; font-size: 0.84rem !important; font-weight: 600 !important;
}}
[data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus {{
    border-color: #1D4ED8 !important; box-shadow: 0 0 0 2px rgba(29,78,216,.25) !important;
}}
label {{ color: #1E293B !important; font-size: 0.78rem !important; font-weight: 700 !important; }}
[data-testid="stSelectbox"] > div > div {{
    background: #FFFFFF !important; border-color: #64748B !important;
    color: #090D16 !important; border-radius: 4px !important; font-weight: 600 !important;
}}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<div class="sb-section-lbl">App Modules (Hub)</div>', unsafe_allow_html=True)
    for option in ['DASHBOARD','HUNTER','WATCHLIST','COMMAND','AI LAB']:
        btn_type = "primary" if st.session_state.page == option else "secondary"
        if st.button(option, key=f"nav_{option}", width="stretch", type=btn_type):
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
      <div style="font-size:0.58rem;color:#1E3A5F;letter-spacing:2px;text-transform:uppercase;margin-bottom:3px;">API Health</div>
      <div style="font-size:0.78rem;font-weight:600;color:{s_color};letter-spacing:0.5px;margin-bottom:8px;">{sys_status}</div>
      <div style="font-size:0.58rem;color:#1E3A5F;letter-spacing:2px;text-transform:uppercase;margin-bottom:3px;">Available Capital</div>
      <div style="font-size:0.88rem;font-weight:600;color:#e6edf3;">₹{balance:,.0f}</div>
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
  <div class="sb-cell"><div class="sb-label">Deployment</div><div class="sb-value" style="color:#1D4ED8;">{deployed_pct}%</div></div>
  <div class="sb-cell"><div class="sb-label">Open Positions</div><div class="sb-value" style="color:#e6edf3;">{open_pos}</div></div>
  <div class="sb-cell"><div class="sb-label">Total Deployed</div><div class="sb-value" style="color:#B45309;">₹{total_deployed_g:,.2f}</div></div>
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
    c1, c2, c3 = st.columns(3, gap="small")
    with c1:
        if st.button("📝  Market Briefing\nDaily strategic analysis and sector rotation.\n→  Generate Report",
                     key="db_brief", width="stretch"):
            launch_script("workflow_strategic_briefing.py")
    with c2:
        if st.button("📡  Sector Radar\nRRG Relative Strength Analysis vs Index.\n→  Launch Radar",
                     key="db_radar", width="stretch"):
            launch_script("sector_radar.py")
    with c3:
        if st.button("🤖  Complete Workflow\nScanners → Fundamentals → Matching → Sync.\n→  Launch Auto-Pilot",
                     key="db_pipeline", width="stretch", type="primary"):
            launch_script("run_pipeline.py")
    
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
            st.plotly_chart(fig, width="stretch")
        with right_col:
            section("Alpha Benchmarking vs Nifty 500")
            df_closed = load_closed_trades_db()
            if not df_closed.empty:
                try:
                    df_closed['ExitDate'] = pd.to_datetime(df_closed['ExitDate'])
                    df_closed = df_closed.sort_values('ExitDate')
                    
                    # 1. Calculate PnL and Deployed Capital per trade
                    # Q5 FIX (20 Jun 2026): EXCLUDE rows with a missing/invalid
                    # buy price, exit price, or quantity — do NOT fillna(0). A
                    # missing BuyPrice previously defaulted to 0, turning the full
                    # exit value into fake profit AND zeroing deployed capital
                    # (inflating the % return / alpha). Now such rows are dropped.
                    _bp  = pd.to_numeric(df_closed['BuyPrice'],  errors='coerce')
                    _ep  = pd.to_numeric(df_closed['ExitPrice'], errors='coerce')
                    _qty = pd.to_numeric(df_closed['Quantity'],  errors='coerce')
                    _valid = _bp.gt(0) & _ep.gt(0) & _qty.gt(0)
                    if not _valid.all():
                        df_closed = df_closed[_valid].copy()
                        _bp, _ep, _qty = _bp[_valid], _ep[_valid], _qty[_valid]
                    df_closed['PnL'] = (_ep - _bp) * _qty
                    df_closed['CapitalDeployed'] = _bp * _qty
                    
                    # 2. Group by date to get cumulative PnL
                    pc = df_closed.groupby('ExitDate').agg({'PnL':'sum'}).reset_index()
                    pc['CumulativePnL'] = pc['PnL'].cumsum()
                    
                    # 3. Calculate Portfolio % Return
                    # We use the 'total_cap' (Balance + Deployed) to represent true alpha generation on account size
                    if total_cap > 0:
                         pc['Portfolio_%'] = (pc['CumulativePnL'] / total_cap) * 100
                    else:
                         pc['Portfolio_%'] = 0.0
                    
                    pc = pc.rename(columns={'ExitDate': 'Date'})

                    # 4. Fetch Nifty Data
                    import data_provider as dp
                    nifty_full = dp.fetch_ohlcv("^NSEI", period="5y", interval="1d", use_cache=True, auto_adjust=True)
                    start_date = pd.to_datetime(pc['Date'].min() - pd.Timedelta(days=7)).tz_localize(None)
                    end_date = pd.to_datetime(pc['Date'].max() + pd.Timedelta(days=1)).tz_localize(None)
                    
                    if nifty_full is not None and not nifty_full.empty:
                        nifty_full.index = pd.to_datetime(nifty_full.index).tz_localize(None)
                        nifty = nifty_full.loc[start_date:end_date].copy()
                    else:
                        nifty = pd.DataFrame()

                    if not nifty.empty:
                        nifty = nifty['Close'].reset_index()
                        nifty.columns = ['Date','NiftyClose']
                        nifty['Date'] = pd.to_datetime(nifty['Date']).dt.tz_localize(None)
                        
                        if isinstance(nifty['NiftyClose'], pd.DataFrame):
                             # MultiIndex result from download
                             nifty['NiftyClose'] = nifty['NiftyClose'].iloc[:, 0]
                        
                        # 5. Base index performance relative to Day 1
                        nifty['Benchmark_%'] = ((nifty['NiftyClose'] - nifty['NiftyClose'].iloc[0]) / nifty['NiftyClose'].iloc[0]) * 100
                        
                        # Merge and Plot
                        merged = pd.merge_asof(pc, nifty[['Date','Benchmark_%']], on='Date')
                        fig2 = px.line(merged, x='Date', y=['Portfolio_%','Benchmark_%'], 
                                       labels={'value': 'Percentage Return (%)', 'variable': 'Metric'})
                        fig2.update_layout(height=300, margin=dict(t=10,l=0,r=0,b=0),
                                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                           legend=dict(font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
                                           yaxis_title="% Return")
                        st.plotly_chart(fig2, width="stretch")
                except Exception as e:
                    st.error(f"Chart error: {e}")
            else:
                st.info("No closed trades to benchmark yet.")
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
            if st.button("Stage 2 Hunter\nLong-horizon stage-based breakout entries.\n→  Run Scanner", width="stretch", key="h_s2"):
                launch_script("chartink_scanner_pro.py","1")
            if st.button("Early Birds Accumulation\nEarly-stage accumulation zone detection.\n→  Run Scanner", width="stretch", key="h_eb"):
                launch_script("chartink_scanner_pro.py","3")
        with right:
            sub_label("📈  Swing Strategies")
            if st.button("Stage 2 Pullback\nShort-term pullback within an uptrend.\n→  Run Scanner", width="stretch", key="h_pb"):
                launch_script("chartink_scanner_pro.py","2")
            if st.button("Strong Leaders\nMomentum leaders with relative strength.\n→  Run Scanner", width="stretch", key="h_sl"):
                launch_script("chartink_scanner_pro.py","4")

    elif hunter_tab == 'ENRICHMENT':
        section("Fundamental Data")
        left, right = st.columns(2, gap="medium")
        with left:
            if st.button("🌐  Fetch Screener.in Data\nPull raw fundamental HTML from Screener.in.\n→  Fetch Now", width="stretch", key="e_fetch"):
                launch_script("screener_fetcher.py")
        with right:
            if st.button("⚙️  Process HTML to CSV\nConvert raw HTML into structured CSV for analysis.\n→  Process Now", width="stretch", key="e_proc"):
                launch_script("screener_processor.py")

    elif hunter_tab == 'SELECTION':
        section("Golden Matcher Engine")
        if st.button("🏆  Run Golden Matcher\nCombines Technical Scans with Fundamental Filters to find 5-Star setups.\n→  Initiate Matching", type="primary", width="stretch", key="sel_run"):
            launch_script("brute_force_match_pro.py")
        section("AI Top Picks Preview")
        preview_cat = st.selectbox("Select Strategy to Preview",
                                   ["Stage 2 Hunter","Stage 2 Pullback","Early Birds","Strong Leaders"])
        pmap = {"Stage 2 Hunter":"FINAL_Hunter_Picks.csv","Stage 2 Pullback":"FINAL_Pullback_Picks.csv",
                "Early Birds":"FINAL_EarlyBird_Picks.csv","Strong Leaders":"FINAL_Leader_Picks.csv"}
        fname = pmap.get(preview_cat,"")
        if os.path.exists(fname):
            try:
                df_res = pd.read_csv(fname)
                ai_c = [c for c in ["Symbol","Conviction","AI Catalyst"] if c in df_res.columns]
                ot_c = [c for c in df_res.columns if c not in ai_c]
                st.dataframe(df_res[ai_c+ot_c].head(15), width="stretch", hide_index=True)
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
        section("1. Local Generation")
        if st.button("📁  Generate CSVs — Local\nGenerate clean CSVs for local analysis.\n→  Generate Now", width="stretch", key="wl_gen"):
            launch_script("watchlist_manager.py")

    elif wl_tab == 'SYNC':
        section("2. External Cloud Sync")
        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            if st.button("💸  Sync to Strike.Money\nPush watchlist to Strike.Money platform.\n→  Sync Now", width="stretch", key="wl_strike"):
                launch_script("strike_automation.py","--mode watchlist")
        with c2:
            if st.button("📊  Sync to TradingView\nSync curated lists to TradingView.\n→  Sync Now", width="stretch", key="wl_tv"):
                launch_script("tradingview_automation_v2.py")
        with c3:
            if st.button("🔁  Master Sync — All\nPush to all connected platforms simultaneously.\n→  Sync All", type="primary", width="stretch", key="wl_master"):
                launch_script("master_portfolio_sync.py")

        section("3. Email Dispatches")
        c4, c5 = st.columns(2, gap="small")
        with c4:
            if st.button("📧  Send Test Email\nVerify SMTP Connection.\n→  Send Now", width="stretch", key="wl_em_test"):
                launch_script("gmail_dispatcher.py", "--mode test")
        with c5:
            if st.button("🏆  Email Golden Matches\nSend latest AI 5-Star picks to your inbox.\n→  Send Now", width="stretch", key="wl_em_match"):
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
            if st.button("🎯  Sniper Entry AI v2\nOrder execution with Institutional AI analysis.\n→  Launch", width="stretch", key="cmd_sniper"):
                launch_script("sniper_trigger.py")
        with c2:
            if st.button("🛡️  GTT Auto-Shield\nAuto-protect holdings using Journal levels.\n→  Launch", width="stretch", key="cmd_gtt"):
                launch_script("gtt_auto_shield.py")
        with c3:
            if st.button("📲  Telegram Sentinel\nActive market monitoring via Mobile.\n→  Launch", width="stretch", key="cmd_tg"):
                launch_script("telegram_sentinel.py")
        section("External Apps")
        if st.button("📓  Open Full Journal App\nLaunch the complete trade journal interface.\n→  Open", width="stretch", key="cmd_journal"):
            launch_script("dhan_journal_v7.py", is_streamlit=True)

    elif cmd_tab == 'LEDGER':
        section("Live Trade Ledger")
        df_j = load_journal_db()
        if not df_j.empty:
            show = [c for c in ["Symbol","Type","BuyPrice","Quantity","Status",
                                 "Sector","StopLoss","Target","PlannedRR","Timeframe"] if c in df_j.columns]
            st.dataframe(df_j[show], width="stretch", height=500, hide_index=True)
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
        if st.button("🛫  Run Analysis\nScore and size a new trade before execution.\n→  Analyse Now", type="primary", width="stretch", key="btn_analysis"):
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
                        
                        # 3. Call grading with correct signature
                        rating_res   = get_weinstein_score(
                            symbol=prop_sym,
                            sector=prop_sector,
                            ltp=ltp_val,
                            buy_price=prop_entry
                        )
                        
                        atr_val      = get_atr(prop_sym)
                        suggested_sl = prop_entry - (2.0 * atr_val) if atr_val else 0
                        qty = int(prop_risk / (prop_entry - suggested_sl)) if (prop_entry - suggested_sl) > 0 else 0
                        
                        r1, r2, r3 = st.columns(3)
                        r1.metric("Weinstein Grade", rating_res.get('rating','N/A'))
                        r2.metric("Suggested SL", f"{suggested_sl:.2f}")
                        r3.metric("Rec. Quantity", f"{qty} shares")
                        st.info(f"AI Rationale: {rating_res.get('reason','N/A')}")
                    except Exception as e:
                        st.error(f"Analysis error: {e}")

    elif ai_tab == 'GENERATIVE':
        section("Generative Analysis")
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            if st.button("🔬  AI Post-Trade Autopsy\nAI-driven post-trade performance review.\n→  Launch", width="stretch", key="ai_autopsy"):
                launch_script("portfolio_analytics.py", is_streamlit=True)
            if st.button("📋  Auto-Plan Journal\nAI-assisted journal planning and entry.\n→  Launch", width="stretch", key="ai_journal"):
                launch_script("dhan_journal_v7.py", is_streamlit=True)
        with c2:
            if st.button("✍️  Standalone Prompt Gen\nStandalone AI prompt generation tools.\n→  Launch", width="stretch", key="ai_prompt"):
                launch_script("generate_prompt_standalone.py")
        section("Cache Management")
        if st.button("🗑️  Clear AI Cache\nFetch fresh data on next run.\n→  Clear Now", width="stretch", key="ai_cache"):
            if os.path.exists("ai_cache.json"):
                os.remove("ai_cache.json")
                st.success("AI Cache Cleared!")
            else:
                st.info("Cache is already empty.")

    elif ai_tab == 'WORKFLOWS':
        section("Workflow Automation")
        if st.button("🤖  Run Full Auto-Pilot\nExecute full pipeline: Scanners → Fundamentals → Golden Matching → Watchlist Sync.\n→  Initiate", type="primary", width="stretch", key="wf_run"):
            launch_script("run_pipeline.py")
