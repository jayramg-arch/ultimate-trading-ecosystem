import streamlit as st
import pandas as pd
import os, sys, sqlite3, base64
from dotenv import load_dotenv
from dhan_auth import ensure_valid_token
from dhanhq import dhanhq
from ai_risk_manager import get_market_health, get_noise_risk_stats, get_atr
from ai_grading_engine import get_weinstein_score
import plotly.express as px
import yfinance as yf

st.set_page_config(
    page_title="Weinstein Commander Web",
    page_icon="🦁",
    layout="wide",
    initial_sidebar_state="expanded"
)

load_dotenv(override=True)

@st.cache_resource(ttl=3600)
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

# ── HELPERS ────────────────────────────────────────────────────────────
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

def load_journal_db():
    conn = None
    try:
        if not os.path.exists(DB_FILE): return pd.DataFrame()
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql("SELECT * FROM journal WHERE status='OPEN'", conn)
        return df.rename(columns=JOURNAL_RENAME_MAP)
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
is_healthy, mkt_ltp, mkt_sma = get_market_health("NSE:CNX500")
df_active_global      = load_journal_db()
if not df_active_global.empty:
    noise_count_g, noise_syms_g = get_noise_risk_stats(df_active_global)
    total_deployed_g = (df_active_global['Quantity'] * df_active_global['BuyPrice']).sum()
else:
    noise_count_g, noise_syms_g, total_deployed_g = 0, [], 0

h_color      = "#00f260" if is_healthy        else "#ff4b4b"
h_text       = "HEALTHY" if is_healthy        else "WEAK"
w_color      = "#ff4b4b" if noise_count_g > 0 else "#00f260"
w_text       = f"⚠ {noise_count_g} AT RISK" if noise_count_g > 0 else "✔ SECURE"
s_color      = "#00f260" if sys_status == "SYSTEM ONLINE" else "#ff4b4b"
deployed_pct = round((1 - balance / 500000) * 100, 1) if balance < 500000 else 0.0
open_pos     = len(df_active_global) if not df_active_global.empty else 0

# ── SESSION STATE ──────────────────────────────────────────────────────
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

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg,#0d1b2a 0%,#0a1628 100%) !important;
    border-right: 1px solid #1e3a5f !important;
    width: 230px !important; min-width: 230px !important; padding: 0 !important;
}}
[data-testid="stSidebar"] > div {{ padding: 0 !important; }}
[data-testid="stSidebarContent"] {{ padding: 0 !important; }}

/* ── TOP STATUS BAR ── */
.statusbar {{
    display: grid; grid-template-columns: 1fr 1fr 1fr 1fr 1fr;
    gap: 1px; background: #1e3a5f; border-bottom: 2px solid #1e3a5f; margin-bottom: 0;
}}
.sb-cell {{ background: #0a1628; padding: 7px 16px; display: flex; flex-direction: column; justify-content: center; }}
.sb-label {{ font-family: 'JetBrains Mono',monospace; font-size: 0.58rem; color: #3d6a99; letter-spacing: 2px; text-transform: uppercase; }}
.sb-value {{ font-family: 'JetBrains Mono',monospace; font-size: 1.0rem; font-weight: 600; margin-top: 1px; letter-spacing: 0.5px; }}

/* ── MAIN CONTENT ── */
.main-content {{ padding: 20px 28px 40px 28px; }}

/* ── PAGE TITLE ── */
.page-title {{
    font-family: 'Rajdhani',sans-serif; font-size: 1.5rem; font-weight: 700;
    letter-spacing: 3px; text-transform: uppercase; color: #e6edf3;
    border-left: 3px solid #238636; padding-left: 12px; margin: 16px 0 2px 0;
}}
.page-desc {{
    font-size: 0.68rem; color: #3d6a99; letter-spacing: 2px; text-transform: uppercase;
    margin: 0 0 16px 15px; font-family: 'JetBrains Mono',monospace;
}}

/* ── SECTION HEADER ── */
.section-hdr {{
    font-family: 'JetBrains Mono',monospace; font-size: 0.60rem; color: #3d6a99;
    letter-spacing: 3px; text-transform: uppercase; margin: 14px 0 8px 0;
    display: flex; align-items: center; gap: 8px;
}}
.section-hdr::after {{ content:''; flex:1; height:1px; background:#1e3a5f; }}

/* ── SECTION SUB LABEL ── */
.section-sub-lbl {{
    font-family: 'JetBrains Mono',monospace; font-size: 0.60rem; color: #3d6a99;
    letter-spacing: 2px; text-transform: uppercase;
    margin: 0 0 8px 0; padding: 6px 0 6px 10px; border-left: 2px solid #1e3a5f;
}}

/* ── ACTION BUTTONS (card-style, tall) ── */
button[kind="secondary"] {{
    background: #0d1b2a !important; border: 1px solid #1e3a5f !important;
    border-radius: 5px !important; color: #c9d1d9 !important;
    font-family: 'JetBrains Mono',monospace !important;
    font-size: 0.72rem !important; font-weight: 400 !important;
    letter-spacing: 0.3px !important; text-transform: none !important;
    padding: 14px 16px !important; width: 100% !important;
    text-align: left !important; line-height: 1.6 !important;
    transition: all .15s ease !important; min-height: 72px !important;
}}
button[kind="secondary"]:hover {{
    background: #12243a !important; border-color: #238636 !important;
    color: #e6edf3 !important; box-shadow: 0 0 0 1px rgba(35,134,54,.2), inset 3px 0 0 #238636 !important;
}}
/* First line of button text = title style */
button[kind="secondary"] p {{ white-space: pre-line !important; text-align: left !important; margin: 0 !important; }}

button[kind="primary"] {{
    background: linear-gradient(135deg,#1a5c2a,#238636) !important;
    border: 1px solid #2ea043 !important; border-radius: 5px !important;
    color: #fff !important; font-family: 'JetBrains Mono',monospace !important;
    font-size: 0.72rem !important; font-weight: 400 !important;
    letter-spacing: 0.3px !important; text-transform: none !important;
    padding: 14px 16px !important; width: 100% !important;
    text-align: left !important; line-height: 1.6 !important;
    box-shadow: 0 0 14px rgba(35,134,54,.25) !important;
    transition: all .15s ease !important; min-height: 72px !important;
}}
button[kind="primary"]:hover {{
    background: linear-gradient(135deg,#238636,#2ea043) !important;
    box-shadow: 0 0 20px rgba(35,134,54,.45) !important;
}}
button[kind="primary"] p {{ white-space: pre-line !important; text-align: left !important; margin: 0 !important; }}

/* ── SIDEBAR NAV BUTTONS ── */
[data-testid="stSidebar"] button[kind="secondary"] {{
    background: transparent !important; border: none !important; border-radius: 0 !important;
    color: #8b949e !important; font-family: 'Rajdhani',sans-serif !important;
    font-size: 0.80rem !important; font-weight: 600 !important;
    letter-spacing: 2px !important; text-transform: uppercase !important;
    padding: 10px 20px !important; text-align: left !important;
    border-left: 3px solid transparent !important;
    min-height: 0 !important; line-height: 1.2 !important;
    transition: all .15s !important; margin: 0 !important; box-shadow: none !important;
}}
[data-testid="stSidebar"] button[kind="secondary"]:hover {{
    background: rgba(35,134,54,.08) !important; color: #e6edf3 !important;
    border-left-color: #238636 !important; box-shadow: none !important;
}}
[data-testid="stSidebar"] button[kind="primary"] {{
    background: rgba(35,134,54,.12) !important; border: none !important;
    border-radius: 0 !important; border-left: 3px solid #238636 !important;
    color: #3fb950 !important; font-family: 'Rajdhani',sans-serif !important;
    font-size: 0.80rem !important; font-weight: 700 !important;
    letter-spacing: 2px !important; text-transform: uppercase !important;
    padding: 10px 20px !important; text-align: left !important;
    min-height: 0 !important; line-height: 1.2 !important;
    box-shadow: none !important; transition: all .15s !important;
}}
[data-testid="stSidebar"] button[kind="primary"]:hover {{
    background: rgba(35,134,54,.18) !important; box-shadow: none !important;
}}
[data-testid="stSidebar"] button p {{ white-space: nowrap !important; text-align: left !important; }}

/* ── SIDEBAR RADIO ── */
[data-testid="stRadio"] label {{
    background: transparent !important; border: none !important; border-radius: 0 !important;
    border-left: 3px solid transparent !important; padding: 8px 14px 8px 30px !important;
    font-family: 'JetBrains Mono',monospace !important; font-size: 0.68rem !important;
    color: #4a6f8a !important; letter-spacing: 1px !important; text-transform: uppercase !important;
    cursor: pointer !important; transition: all .15s !important; margin: 0 !important; display: block !important;
}}
[data-testid="stRadio"] label:hover {{
    background: rgba(35,134,54,.06) !important; color: #c9d1d9 !important; border-left-color: rgba(35,134,54,.4) !important;
}}
[data-testid="stRadio"] label[data-checked="true"] {{
    background: rgba(35,134,54,.10) !important; color: #3fb950 !important;
    border-left-color: #238636 !important; font-weight: 600 !important;
}}
[role="radiogroup"] input {{ display: none !important; }}
[role="radiogroup"] [data-testid="stMarkdownContainer"] p {{ margin: 0 !important; }}

/* ── SIDEBAR SECTION LABEL ── */
.sb-section-lbl {{
    font-family: 'JetBrains Mono',monospace; font-size: 0.55rem; color: #2d4a63;
    letter-spacing: 3px; text-transform: uppercase; padding: 16px 20px 6px 20px;
    border-top: 1px solid #1e3a5f; margin-top: 4px;
}}

/* ── METRICS ── */
[data-testid="metric-container"] {{
    background: #0d1b2a !important; border: 1px solid #1e3a5f !important;
    border-radius: 6px !important; padding: 12px 16px !important;
}}
[data-testid="metric-container"] label {{
    font-family: 'JetBrains Mono',monospace !important; font-size: 0.60rem !important;
    color: #3d6a99 !important; letter-spacing: 2px !important; text-transform: uppercase !important;
}}
[data-testid="metric-container"] [data-testid="stMetricValue"] {{
    font-family: 'JetBrains Mono',monospace !important; font-size: 1.2rem !important;
    font-weight: 600 !important; color: #e6edf3 !important;
}}

/* ── MISC ── */
[data-testid="stDataFrame"] {{ border: 1px solid #1e3a5f !important; border-radius: 6px !important; }}
iframe {{ border-radius: 6px !important; }}
hr {{ border-color: #1e3a5f !important; margin: 10px 0 !important; }}
[data-testid="stAlert"] {{ border-radius: 4px !important; font-family: 'JetBrains Mono',monospace !important; font-size: 0.72rem !important; }}
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {{
    background: #0a1628 !important; border: 1px solid #1e3a5f !important;
    border-radius: 4px !important; color: #e6edf3 !important;
    font-family: 'JetBrains Mono',monospace !important; font-size: 0.78rem !important;
}}
[data-testid="stToast"] {{
    background: #0d1b2a !important; border: 1px solid #238636 !important;
    border-radius: 6px !important; font-family: 'JetBrains Mono',monospace !important;
}}
label {{ color: #4a6f8a !important; font-size: 0.70rem !important; }}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="padding:20px 20px 14px 20px;border-bottom:1px solid #1e3a5f;">
      <div style="font-family:'Rajdhani',sans-serif;font-size:1.35rem;font-weight:700;color:#e6edf3;letter-spacing:2px;">🦁 WEINSTEIN</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.58rem;color:#2d4a63;letter-spacing:3px;margin-top:2px;">COMMANDER WEB v11.0</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sb-section-lbl">Navigation</div>', unsafe_allow_html=True)
    for option in ['DASHBOARD','HUNTER','WATCHLIST','COMMAND','AI LAB','JOURNAL']:
        btn_type = "primary" if st.session_state.page == option else "secondary"
        if st.button(option, key=f"nav_{option}", use_container_width=True, type=btn_type):
            if option == 'JOURNAL':
                launch_script("dhan_journal_v6.py", is_streamlit=True)
            else:
                st.session_state.page = option
                st.rerun()

    page = st.session_state.page

    if page == 'HUNTER':
        st.markdown('<div class="sb-section-lbl">Targeting</div>', unsafe_allow_html=True)
        hopts = ['SCANNERS','ENRICHMENT','SELECTION']
        sel = st.radio("Hunter Nav", hopts, index=hopts.index(st.session_state.huntertab), label_visibility="collapsed")
        st.session_state.huntertab = sel

    elif page == 'WATCHLIST':
        st.markdown('<div class="sb-section-lbl">Actions</div>', unsafe_allow_html=True)
        wl_opts = ['GENERATE','SYNC CLOUD']
        wl_map  = {'GENERATE':'GENERATION','SYNC CLOUD':'SYNC'}
        wl_rev  = {v:k for k,v in wl_map.items()}
        sel = st.radio("WL Nav", wl_opts, index=wl_opts.index(wl_rev.get(st.session_state.watchlisttab,'GENERATE')), label_visibility="collapsed")
        st.session_state.watchlisttab = wl_map[sel]

    elif page == 'COMMAND':
        st.markdown('<div class="sb-section-lbl">Controls</div>', unsafe_allow_html=True)
        cmd_opts = ['ACTIVE OPS','LEDGER']
        cmd_map  = {'ACTIVE OPS':'ACTIVEOPS','LEDGER':'LEDGER'}
        cmd_rev  = {v:k for k,v in cmd_map.items()}
        sel = st.radio("Cmd Nav", cmd_opts, index=cmd_opts.index(cmd_rev.get(st.session_state.commandtab,'ACTIVE OPS')), label_visibility="collapsed")
        st.session_state.commandtab = cmd_map[sel]

    elif page == 'AI LAB':
        st.markdown('<div class="sb-section-lbl">Lab Bench</div>', unsafe_allow_html=True)
        ai_opts = ['PRE-FLIGHT','GENERATIVE','WORKFLOWS']
        ai_map  = {'PRE-FLIGHT':'PREFLIGHT','GENERATIVE':'GENERATIVE','WORKFLOWS':'WORKFLOWS'}
        ai_rev  = {v:k for k,v in ai_map.items()}
        sel = st.radio("AI Nav", ai_opts, index=ai_opts.index(ai_rev.get(st.session_state.ailabtab,'PRE-FLIGHT')), label_visibility="collapsed")
        st.session_state.ailabtab = ai_map[sel]

    # Sidebar status footer
    st.markdown('<div class="sb-section-lbl">System Status</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="padding:10px 20px 20px 20px;font-family:'JetBrains Mono',monospace;">
      <div style="font-size:0.60rem;color:#2d4a63;letter-spacing:1px;margin-bottom:4px;">API HEALTH</div>
      <div style="font-size:0.75rem;font-weight:600;color:{s_color};letter-spacing:1px;">{sys_status}</div>
      <div style="font-size:0.60rem;color:#2d4a63;letter-spacing:1px;margin:8px 0 4px 0;">AVAILABLE CAPITAL</div>
      <div style="font-size:0.90rem;font-weight:600;color:#e6edf3;">₹{balance:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

    if sys_status == "AUTH EXPIRED":
        st.warning("⚠️ Token expired. Re-run dhan_auth.py")


# ══════════════════════════════════════════════════════════════════════
#  TOP STATUS BAR
# ══════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="statusbar">
  <div class="sb-cell"><div class="sb-label">Nifty 500</div><div class="sb-value" style="color:{h_color}">{h_text}</div></div>
  <div class="sb-cell"><div class="sb-label">Risk Watchdog</div><div class="sb-value" style="color:{w_color}">{w_text}</div></div>
  <div class="sb-cell"><div class="sb-label">Deployment</div><div class="sb-value" style="color:#58a6ff">{deployed_pct}%</div></div>
  <div class="sb-cell"><div class="sb-label">Open Positions</div><div class="sb-value" style="color:#e6edf3">{open_pos}</div></div>
  <div class="sb-cell"><div class="sb-label">Total Deployed</div><div class="sb-value" style="color:#f0883e">₹{total_deployed_g:,.0f}</div></div>
</div>
""", unsafe_allow_html=True)

page = st.session_state.page

# ── UI helpers ─────────────────────────────────────────────────────
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
        if st.button(
            "📝  MARKET BRIEFING\nDaily strategic analysis and sector rotation.\n→ GENERATE REPORT",
            key="db_brief", use_container_width=True
        ):
            launch_script("workflow_strategic_briefing.py")
    with c2:
        if st.button(
            "📡  SECTOR RADAR\nRRG Relative Strength Analysis vs Index.\n→ LAUNCH RADAR",
            key="db_radar", use_container_width=True
        ):
            launch_script("sector_radar.py")
    with c3:
        if st.button(
            "💼  PORTFOLIO HEALTH\nRisk assessment and exposure audit.\n→ LAUNCH ANALYTICS",
            key="db_analytics", use_container_width=True
        ):
            launch_script("portfolio_analytics.py", is_streamlit=True)

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
            fig.update_layout(margin=dict(t=10,l=0,r=0,b=0), height=340,
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        with right_col:
            section("Alpha Benchmarking vs Nifty 500")
            df_closed = load_closed_trades_db()
            if not df_closed.empty:
                try:
                    df_closed['ExitDate'] = pd.to_datetime(df_closed['ExitDate'])
                    df_closed = df_closed.sort_values('ExitDate')
                    df_closed['PnL'] = (
                        pd.to_numeric(df_closed['ExitPrice'],errors='coerce').fillna(0) -
                        pd.to_numeric(df_closed['BuyPrice'], errors='coerce').fillna(0)
                    ) * pd.to_numeric(df_closed['Quantity'],errors='coerce').fillna(0)
                    pc = df_closed.groupby('ExitDate')['PnL'].sum().cumsum().reset_index()
                    pc.columns = ['Date','PortfolioProfit']
                    nifty = yf.download("^NSEI", start=pc['Date'].min()-pd.Timedelta(days=7),
                                        end=pc['Date'].max()+pd.Timedelta(days=1), progress=False)
                    if not nifty.empty:
                        nifty = nifty['Close'].reset_index()
                        nifty.columns = ['Date','NiftyClose']
                        nifty['Date'] = pd.to_datetime(nifty['Date']).dt.tz_localize(None)
                        nifty['Benchmark'] = (nifty['NiftyClose']-nifty['NiftyClose'].iloc[0])/nifty['NiftyClose'].iloc[0]*100
                        merged = pd.merge_asof(pc, nifty[['Date','Benchmark']], on='Date')
                        fig2 = px.line(merged, x='Date', y=['PortfolioProfit','Benchmark'])
                        fig2.update_layout(height=310, margin=dict(t=10,l=0,r=0,b=0),
                                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                           legend=dict(font=dict(size=10), bgcolor="rgba(0,0,0,0)"))
                        st.plotly_chart(fig2, use_container_width=True)
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
            sub_label("📌 POSITIONAL STRATEGIES")
            if st.button("Stage 2 Hunter\nLong-horizon stage-based breakout entries.\n→ RUN SCANNER", use_container_width=True, key="h_s2"):
                launch_script("chartink_scanner_pro.py","1")
            if st.button("Early Birds Accumulation\nEarly-stage accumulation zone detection.\n→ RUN SCANNER", use_container_width=True, key="h_eb"):
                launch_script("chartink_scanner_pro.py","3")
        with right:
            sub_label("📈 SWING STRATEGIES")
            if st.button("Stage 2 Pullback\nShort-term pullback within an uptrend.\n→ RUN SCANNER", use_container_width=True, key="h_pb"):
                launch_script("chartink_scanner_pro.py","2")
            if st.button("Strong Leaders\nMomentum leaders with relative strength.\n→ RUN SCANNER", use_container_width=True, key="h_sl"):
                launch_script("chartink_scanner_pro.py","4")

    elif hunter_tab == 'ENRICHMENT':
        section("Fundamental Data")
        left, right = st.columns(2, gap="medium")
        with left:
            if st.button("🌐  FETCH SCREENER.IN DATA\nPull raw fundamental HTML from Screener.in.\n→ FETCH NOW", use_container_width=True, key="e_fetch"):
                launch_script("screener_fetcher.py")
        with right:
            if st.button("⚙️  PROCESS HTML TO CSV\nConvert raw HTML into structured CSV for analysis.\n→ PROCESS NOW", use_container_width=True, key="e_proc"):
                launch_script("screener_processor.py")

    elif hunter_tab == 'SELECTION':
        section("Golden Matcher Engine")
        if st.button("🏆  RUN GOLDEN MATCHER\nCombines Technical Scans with Fundamental Filters to find 5-Star setups.\n→ INITIATE MATCHING", type="primary", use_container_width=True, key="sel_run"):
            launch_script("brute_force_match_pro.py")
        section("AI Top Picks Preview")
        preview_cat = st.selectbox("Select Strategy to Preview",
                                   ["Stage 2 Hunter","Stage 2 Pullback","Early Birds","Strong Leaders"])
        pmap = {"Stage 2 Hunter":"stage2_results.csv","Stage 2 Pullback":"pullback_results.csv",
                "Early Birds":"earlybirds_results.csv","Strong Leaders":"leaders_results.csv"}
        fname = pmap.get(preview_cat,"")
        if os.path.exists(fname):
            try:
                df_res = pd.read_csv(fname)
                ai_c = [c for c in ["Symbol","Conviction","AI Catalyst"] if c in df_res.columns]
                ot_c = [c for c in df_res.columns if c not in ai_c]
                st.dataframe(df_res[ai_c+ot_c].head(15), use_container_width=True, hide_index=True)
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
        if st.button("📁  GENERATE CSVs — LOCAL\nGenerate clean CSVs for local analysis.\n→ GENERATE NOW", use_container_width=True, key="wl_gen"):
            import watchlist_manager
            watchlist_manager.generate_tradingview_files()
            st.success("Watchlists generated in WL folder")

    elif wl_tab == 'SYNC':
        section("2. External Cloud Sync")
        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            if st.button("💸  SYNC TO STRIKE.MONEY\nPush watchlist to Strike.Money platform.\n→ SYNC NOW", use_container_width=True, key="wl_strike"):
                launch_script("strike_automation.py","--mode watchlist")
        with c2:
            if st.button("📊  SYNC TO TRADINGVIEW\nSync curated lists to TradingView.\n→ SYNC NOW", use_container_width=True, key="wl_tv"):
                launch_script("tradingview_automation_v2.py")
        with c3:
            if st.button("🔁  MASTER SYNC — ALL\nPush to all connected platforms simultaneously.\n→ SYNC ALL", type="primary", use_container_width=True, key="wl_master"):
                launch_script("master_portfolio_sync.py")


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
            if st.button("🎯  SNIPER ENTRY AI v2\nOrder execution with Institutional AI analysis.\n→ LAUNCH", use_container_width=True, key="cmd_sniper"):
                launch_script("sniper_trigger.py")
        with c2:
            if st.button("🛡️  GTT AUTO-SHIELD\nAuto-protect holdings using Journal levels.\n→ LAUNCH", use_container_width=True, key="cmd_gtt"):
                launch_script("gtt_auto_shield.py")
        with c3:
            if st.button("📲  TELEGRAM SENTINEL\nActive market monitoring via Mobile.\n→ LAUNCH", use_container_width=True, key="cmd_tg"):
                launch_script("telegram_sentinel.py")
        section("External Apps")
        if st.button("📓  OPEN FULL JOURNAL APP\nLaunch the complete trade journal interface.\n→ OPEN", use_container_width=True, key="cmd_journal"):
            launch_script("dhan_journal_v6.py", is_streamlit=True)

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
        if st.button("🛫  RUN ANALYSIS\nScore and size a new trade before execution.\n→ ANALYSE NOW", type="primary", use_container_width=True, key="btn_analysis"):
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
            if st.button("🔬  AI POST-TRADE AUTOPSY\nAI-driven post-trade performance review.\n→ LAUNCH", use_container_width=True, key="ai_autopsy"):
                launch_script("portfolio_analytics.py", is_streamlit=True)
            if st.button("📋  AUTO-PLAN JOURNAL\nAI-assisted journal planning and entry.\n→ LAUNCH", use_container_width=True, key="ai_journal"):
                launch_script("dhan_journal_v6.py", is_streamlit=True)
        with c2:
            if st.button("✍️  STANDALONE PROMPT GEN\nStandalone AI prompt generation tools.\n→ LAUNCH", use_container_width=True, key="ai_prompt"):
                launch_script("generate_prompt_standalone.py")
        section("Cache")
        if st.button("🗑️  CLEAR AI CACHE\nFetch fresh data on next run.\n→ CLEAR NOW", use_container_width=True, key="ai_cache"):
            if os.path.exists("ai_cache.json"):
                os.remove("ai_cache.json"); st.success("AI Cache Cleared!")
            else:
                st.info("Cache is already empty.")

    elif ai_tab == 'WORKFLOWS':
        section("Workflow Automation")
        if st.button("🤖  RUN FULL AUTO-PILOT\nExecute full pipeline: Scanners → Fundamentals → Golden Matching → Watchlist Sync.\n→ INITIATE", type="primary", use_container_width=True, key="wf_run"):
            launch_script("run_pipeline.py")
