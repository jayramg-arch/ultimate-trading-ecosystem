#!/usr/bin/env python
"""
patch_v4.py — Converts weinstein_commander_web_v3.0.py → v4.0
Run once:  python patch_v4.py
Preserves ALL existing page logic. Adds new pages as additional elif blocks.
"""

import sys
from pathlib import Path

BASE = Path(__file__).parent
SRC  = BASE / "weinstein_commander_web_v3.0.py"
DST  = BASE / "weinstein_commander_web_v4.0.py"

src = SRC.read_text(encoding="utf-8")
print(f"Read {len(src):,} chars from {SRC.name}")

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 1: Header comment line 1-2 — update version
# ─────────────────────────────────────────────────────────────────────────────
src = src.replace(
    "# weinstein_commander_web_v3.0.py — Weinstein Commander Web",
    "# weinstein_commander_web_v4.0.py — Weinstein Commander Web",
    1
)
src = src.replace(
    "# Fixes: BUG-01..15 | FORM-01..03 | E-01..E-09",
    "# v4.0 — Phase 1: Pre-Market Hub | Post-Market | Breadth Engine | Macro+ | Gemini AI",
    1
)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 2: Add new imports after "from pine_generator import generate_pine_code"
# ─────────────────────────────────────────────────────────────────────────────
NEW_IMPORTS = '''
# ── v4.0 Phase-1 imports ─────────────────────────────────────────────────────
try:
    from market_data_hub import (
        build_premarket_snapshot, build_postmarket_snapshot,
        fetch_global_overview, fetch_fii_dii_data, fetch_india_vix_history,
        fetch_nse_options_summary, fetch_economic_calendar, fetch_fno_ban_list,
        fetch_nse_breadth,
    )
    _HUB_OK = True
except ImportError as _e:
    _HUB_OK = False
    logger = logging.getLogger(__name__)
    logging.getLogger(__name__).warning(f"market_data_hub not available: {_e}")

try:
    from gemini_reporter import (
        generate_premarket_brief, generate_postmarket_summary,
        generate_weekly_market_report,
    )
    _GEMINI_OK = True
except ImportError:
    _GEMINI_OK = False

try:
    from breadth_engine import (
        calculate_breadth_metrics, build_breadth_regime,
        get_sector_breadth, calculate_mcclellan, format_breadth_for_report,
    )
    _BREADTH_OK = True
except ImportError:
    _BREADTH_OK = False

try:
    from scheduler_daemon import (
        start_scheduler, get_scheduler_status, load_latest_report,
        trigger_manual_report,
    )
    _SCHED_OK = True
except ImportError:
    _SCHED_OK = False

# Start background scheduler (once per process)
if _SCHED_OK and "___scheduler_started" not in st.session_state:
    try:
        _sched = start_scheduler()
        st.session_state["___scheduler_started"] = True
    except Exception as _se:
        st.session_state["___scheduler_started"] = False
        logging.getLogger(__name__).warning(f"Scheduler start failed: {_se}")
'''

src = src.replace(
    "from pine_generator import generate_pine_code",
    "from pine_generator import generate_pine_code" + NEW_IMPORTS,
    1
)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 3: Add new session state keys
# ─────────────────────────────────────────────────────────────────────────────
src = src.replace(
    "    ('macrotab','OVERVIEW'), ('autopsytab','OVERVIEW')",
    "    ('macrotab','OVERVIEW'), ('autopsytab','OVERVIEW'),\n"
    "    ('premarkettab','BRIEF'), ('postmarkettab','SUMMARY'), ('breadthtab','OVERVIEW'),",
    1
)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 4: Widen sidebar from 230px to 270px (dual widescreen)
# ─────────────────────────────────────────────────────────────────────────────
src = src.replace(
    "width: 230px !important; min-width: 230px !important;",
    "width: 270px !important; min-width: 270px !important;",
    1
)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 5: Update version label in sidebar header
# ─────────────────────────────────────────────────────────────────────────────
src = src.replace(
    "COMMANDER WEB v3.0</div>",
    "COMMANDER WEB v4.0</div>",
    1
)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 6: Replace flat NAV_PAGES with grouped navigation
# ─────────────────────────────────────────────────────────────────────────────
OLD_NAV = """    st.markdown('<div class="sb-section-lbl">Navigation</div>', unsafe_allow_html=True)
    NAV_PAGES = ['DASHBOARD','HUNTER','WATCHLIST','COMMAND','AI LAB',
                 'MACRO','OPTIONS','AUTOPSY','BACKTEST','JOURNAL','X-RAY','TV SIDECAR']
    for option in NAV_PAGES:
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
                st.rerun()"""

NEW_NAV = """    # ── v4.0 Grouped Navigation ─────────────────────────────────────────────
    EXTERNAL_PAGES = {'JOURNAL': 'dhan_journal_v7.py',
                      'X-RAY':   'fundamental_xray.py',
                      'TV SIDECAR': 'tv_sidecar_app.py'}

    NAV_GROUPS = [
        ("📅  DAILY INTEL", [
            ("🌅 PRE-MARKET",  "PRE-MARKET"),
            ("📊 DASHBOARD",   "DASHBOARD"),
            ("🌙 POST-MARKET", "POST-MARKET"),
        ]),
        ("🌍  MARKET INTEL", [
            ("🌐 MACRO",       "MACRO"),
            ("📈 BREADTH",     "BREADTH"),
            ("📐 OPTIONS",     "OPTIONS"),
        ]),
        ("🔍  RESEARCH", [
            ("🎯 HUNTER",      "HUNTER"),
            ("📋 WATCHLIST",   "WATCHLIST"),
            ("🧬 X-RAY",       "X-RAY"),
        ]),
        ("⚡  ACTIVE TRADING", [
            ("⚡ COMMAND",     "COMMAND"),
            ("🧪 AI LAB",      "AI LAB"),
            ("📺 TV SIDECAR",  "TV SIDECAR"),
        ]),
        ("🔬  ANALYSIS", [
            ("🔬 AUTOPSY",     "AUTOPSY"),
            ("📈 BACKTEST",    "BACKTEST"),
        ]),
        ("📁  RECORDS", [
            ("📓 JOURNAL",     "JOURNAL"),
        ]),
    ]

    for group_label, group_pages in NAV_GROUPS:
        st.markdown(f'<div class="sb-section-lbl">{group_label}</div>', unsafe_allow_html=True)
        for display_name, page_key in group_pages:
            btn_type = "primary" if st.session_state.page == page_key else "secondary"
            if st.button(display_name, key=f"nav_{page_key}",
                         use_container_width=True, type=btn_type):
                if page_key in EXTERNAL_PAGES:
                    launch_script(EXTERNAL_PAGES[page_key], is_streamlit=True)
                else:
                    st.session_state.page = page_key
                    st.rerun()"""

src = src.replace(OLD_NAV, NEW_NAV, 1)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 7: Add new sub-nav entries for new pages
# ─────────────────────────────────────────────────────────────────────────────
OLD_MACRO_NAV = """    elif page == 'MACRO':
        st.markdown('<div class="sb-section-lbl">Macro</div>', unsafe_allow_html=True)
        mac_opts = ['OVERVIEW','SECTOR RRG']
        sel = st.radio("Macro Nav", mac_opts, index=mac_opts.index(st.session_state.macrotab) if st.session_state.macrotab in mac_opts else 0, label_visibility="collapsed")
        st.session_state.macrotab = sel"""

NEW_MACRO_NAV = """    elif page == 'MACRO':
        st.markdown('<div class="sb-section-lbl">Macro</div>', unsafe_allow_html=True)
        mac_opts = ['OVERVIEW','GLOBAL INDICES','FII/DII FLOWS','SECTOR RRG']
        sel = st.radio("Macro Nav", mac_opts, index=mac_opts.index(st.session_state.macrotab) if st.session_state.macrotab in mac_opts else 0, label_visibility="collapsed")
        st.session_state.macrotab = sel

    elif page == 'PRE-MARKET':
        st.markdown('<div class="sb-section-lbl">Pre-Market</div>', unsafe_allow_html=True)
        pm_opts = ['BRIEF','GLOBAL','CALENDAR','OPTIONS']
        sel = st.radio("PM Nav", pm_opts, index=pm_opts.index(st.session_state.premarkettab) if st.session_state.premarkettab in pm_opts else 0, label_visibility="collapsed")
        st.session_state.premarkettab = sel

    elif page == 'POST-MARKET':
        st.markdown('<div class="sb-section-lbl">Post-Market</div>', unsafe_allow_html=True)
        po_opts = ['SUMMARY','BREADTH','FII/DII','MOVERS']
        sel = st.radio("PO Nav", po_opts, index=po_opts.index(st.session_state.postmarkettab) if st.session_state.postmarkettab in po_opts else 0, label_visibility="collapsed")
        st.session_state.postmarkettab = sel

    elif page == 'BREADTH':
        st.markdown('<div class="sb-section-lbl">Breadth</div>', unsafe_allow_html=True)
        br_opts = ['OVERVIEW','SECTORS','MCCLELLAN','STAGE MAP']
        sel = st.radio("BR Nav", br_opts, index=br_opts.index(st.session_state.breadthtab) if st.session_state.breadthtab in br_opts else 0, label_visibility="collapsed")
        st.session_state.breadthtab = sel"""

src = src.replace(OLD_MACRO_NAV, NEW_MACRO_NAV, 1)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 8: Expand status bar from 5 to 8 cells
# ─────────────────────────────────────────────────────────────────────────────
OLD_STATUSBAR_CSS = "grid-template-columns: repeat(5, 1fr);"
NEW_STATUSBAR_CSS = "grid-template-columns: repeat(8, 1fr);"
src = src.replace(OLD_STATUSBAR_CSS, NEW_STATUSBAR_CSS, 1)

OLD_STATUSBAR_HTML = '''st.markdown(f"""
<div class="statusbar">
  <div class="sb-cell"><div class="sb-label">Nifty 500</div><div class="sb-value" style="color:{h_color};">{h_text}</div></div>
  <div class="sb-cell"><div class="sb-label">Risk Watchdog</div><div class="sb-value" style="color:{w_color};">{w_text}</div></div>
  <div class="sb-cell"><div class="sb-label">Deployment</div><div class="sb-value" style="color:#58a6ff;">{deployed_pct}%</div></div>
  <div class="sb-cell"><div class="sb-label">Open Positions</div><div class="sb-value" style="color:#e6edf3;">{open_pos}</div></div>
  <div class="sb-cell"><div class="sb-label">Total Deployed</div><div class="sb-value" style="color:#e3b341;">₹{format_inr(total_deployed_g)}</div></div>
</div>
""", unsafe_allow_html=True)'''

NEW_STATUSBAR_HTML = '''# v4.0 extended status bar — fetch VIX + FII for top bar
try:
    _vix_bar = yf.download("^INDIAVIX", period="2d", interval="1d", progress=False, auto_adjust=True)
    if isinstance(_vix_bar.columns, pd.MultiIndex): _vix_bar.columns = _vix_bar.columns.get_level_values(0)
    _vix_val = float(_vix_bar["Close"].iloc[-1]) if not _vix_bar.empty else 0
    _vix_col = "#ff4b4b" if _vix_val > 20 else "#e3b341" if _vix_val > 15 else "#00f260"
    _vix_txt = f"{_vix_val:.1f}"
except Exception:
    _vix_val, _vix_col, _vix_txt = 0, "#5a8a9f", "N/A"

_fii_txt, _fii_col = "–", "#5a8a9f"
if _HUB_OK:
    try:
        _fii_df = fetch_fii_dii_data()
        if not _fii_df.empty and "fii_net" in _fii_df.columns:
            _fii_net = float(_fii_df["fii_net"].iloc[-1])
            _fii_txt = f"{'▲' if _fii_net>=0 else '▼'} ₹{abs(_fii_net)/1e7:.0f}Cr"
            _fii_col = "#00f260" if _fii_net >= 0 else "#ff4b4b"
    except Exception:
        pass

# Regime text from breadth if available
_regime_txt, _regime_col = "–", "#5a8a9f"
if _BREADTH_OK:
    try:
        _br = calculate_breadth_metrics()
        _regime_txt = build_breadth_regime(_br)
        _regime_col = "#00f260" if "BULL" in _regime_txt else "#ff4b4b" if "BEAR" in _regime_txt else "#e3b341"
    except Exception:
        pass

st.markdown(f"""
<div class="statusbar">
  <div class="sb-cell"><div class="sb-label">Nifty 500</div><div class="sb-value" style="color:{h_color};">{h_text}</div></div>
  <div class="sb-cell"><div class="sb-label">Market Regime</div><div class="sb-value" style="color:{_regime_col};font-size:0.75rem;">{_regime_txt}</div></div>
  <div class="sb-cell"><div class="sb-label">India VIX</div><div class="sb-value" style="color:{_vix_col};">{_vix_txt}</div></div>
  <div class="sb-cell"><div class="sb-label">FII Flow (prev)</div><div class="sb-value" style="color:{_fii_col};font-size:0.78rem;">{_fii_txt}</div></div>
  <div class="sb-cell"><div class="sb-label">Risk Watchdog</div><div class="sb-value" style="color:{w_color};">{w_text}</div></div>
  <div class="sb-cell"><div class="sb-label">Deployment</div><div class="sb-value" style="color:#58a6ff;">{deployed_pct}%</div></div>
  <div class="sb-cell"><div class="sb-label">Open Positions</div><div class="sb-value" style="color:#e6edf3;">{open_pos}</div></div>
  <div class="sb-cell"><div class="sb-label">Total Deployed</div><div class="sb-value" style="color:#e3b341;">₹{format_inr(total_deployed_g)}</div></div>
</div>
""", unsafe_allow_html=True)'''

src = src.replace(OLD_STATUSBAR_HTML, NEW_STATUSBAR_HTML, 1)

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 9: Append all new page handlers (read from sidecar file)
# ─────────────────────────────────────────────────────────────────────────────
NEW_PAGES = (BASE / "patch_v4_pages.py").read_text(encoding="utf-8")

src = src + NEW_PAGES

# ─────────────────────────────────────────────────────────────────────────────
# Write output
# ─────────────────────────────────────────────────────────────────────────────
DST.write_text(src, encoding="utf-8")
print(f"✅ Written {len(src):,} chars to {DST.name}")
print(f"   Source lines: {src.count(chr(10)):,}")
print("\nPatches applied:")
print("  1. Header comment updated to v4.0")
print("  2. New imports: market_data_hub, gemini_reporter, breadth_engine, scheduler_daemon")
print("  3. New session state keys: premarkettab, postmarkettab, breadthtab")
print("  4. Sidebar widened: 270px")
print("  5. Version label: COMMANDER WEB v4.0")
print("  6. NAV_PAGES → grouped NAV_GROUPS (6 sections, 15 items)")
print("  7. New sub-nav for PRE-MARKET, POST-MARKET, BREADTH, extended MACRO")
print("  8. Status bar: 5 cells → 8 cells (+ India VIX, FII Flow, Market Regime)")
print("  9. New page handlers appended: PRE-MARKET, POST-MARKET, BREADTH, MACRO new tabs")
print("\nRun with: streamlit run weinstein_commander_web_v4.0.py")
