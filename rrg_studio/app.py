"""
app.py — Standalone Strike.Money Style Relative Rotation Graphs (RRG) Cockpit

Ultra-wide layout:
  • Clickable Stock/Sector Card Rows (Zero Checkboxes - Click to Auto-Select & Toggle)
  • Slim Left Panel (~13.5% width) with Quadrant / Alphabetical sorting
  • Maximized 4-Quadrant RRG Canvas (>86% screen width)
  • Reliable Select All & Clear All batch actions
  • Clean Benchmark resolution (Zero NSEI contamination)
  • High-contrast, standout buttons and controls
"""

import streamlit as st
import pandas as pd
import numpy as np
import os
import sys
import json
from datetime import datetime

# Path resolution: Ensure rrg_studio is prioritized first in sys.path
STUDIO_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(STUDIO_DIR)
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)
if STUDIO_DIR in sys.path:
    sys.path.remove(STUDIO_DIR)
sys.path.insert(0, STUDIO_DIR)

# Force flush cached rrg_engine module if modified
sys.modules.pop('rrg_engine', None)

from rrg_engine import (
    SECTOR_INDICES,
    QUADRANT_COLORS,
    ALL_BENCHMARK_INDICES,
    calculate_jdk_rrg,
    compute_universe_rrg,
    render_rrg_plotly,
    render_benchmark_sparkline,
    get_all_universe_options,
    get_all_sectors_from_db,
    load_custom_watchlists,
    save_custom_watchlists,
    load_universe_data,
    get_screener_fundamentals,
    get_dhan_technicals
)

st.set_page_config(
    page_title="RRG Studio — Sector Rotation Cockpit",
    page_icon="rrg_icon.png" if os.path.exists("rrg_icon.png") else "🔄",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── ULTRA-COMPACT, EDGE-TO-EDGE HIGH-CONTRAST CSS ──────────────────────────
st.markdown("""
<style>
    /* Remove all outer unused margins and header padding */
    .block-container {
        padding-top: 0.25rem !important;
        padding-bottom: 0.25rem !important;
        padding-left: 0.4rem !important;
        padding-right: 0.4rem !important;
        max-width: 100% !important;
    }
    header[data-testid="stHeader"] {
        display: none !important;
    }
    footer {
        display: none !important;
    }
    
    /* Global Base */
    .stApp { 
        background-color: #F8FAFC; 
        color: #0F172A;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }

    /* Tighten Streamlit Column Gutters */
    div[data-testid="column"] {
        padding: 0 3px !important;
    }
    div[data-testid="stVerticalBlock"] > div {
        gap: 0.2rem !important;
    }

    /* ─── PREMIUM GRADIENT & GLOWING BLUE THEME FOR ALL FIELDS & BUTTONS ─── */
    
    /* Standout Form Labels */
    label[data-testid="stWidgetLabel"] p {
        font-size: 0.72rem !important;
        font-weight: 800 !important;
        color: #0F172A !important;
        margin-bottom: 2px !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* All Selectboxes: High-Contrast Light Blue Gradient with Glowing Border */
    div[data-baseweb="select"] > div {
        min-height: 36px !important;
        height: auto !important;
        border: 1.5px solid #38BDF8 !important;
        border-radius: 7px !important;
        background: linear-gradient(135deg, #F0F9FF 0%, #E0F2FE 50%, #BAE6FD 100%) !important;
        font-size: 0.82rem !important;
        font-weight: 800 !important;
        color: #0F172A !important;
        padding-top: 2px !important;
        padding-bottom: 2px !important;
        box-shadow: 0 0 10px rgba(56, 189, 248, 0.45) !important;
        transition: all 0.25s ease-in-out !important;
    }
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] div,
    div[data-baseweb="select"] p {
        font-size: 0.80rem !important;
        font-weight: 800 !important;
        color: #0F172A !important;
        line-height: normal !important;
    }
    div[data-baseweb="select"] > div:hover {
        background: linear-gradient(135deg, #E0F2FE 0%, #BAE6FD 50%, #7DD3FC 100%) !important;
        border-color: #0284C7 !important;
        box-shadow: 0 0 15px rgba(2, 132, 199, 0.7), 0 0 5px rgba(56, 189, 248, 0.9) !important;
    }
    /* Selected / Focused Selectbox: Dark Blue Gradient with HIGH-CONTRAST PURE WHITE TEXT & Cyan Glow */
    div[data-baseweb="select"]:focus-within > div {
        background: linear-gradient(135deg, #0284C7 0%, #0369A1 50%, #075985 100%) !important;
        border: 2px solid #38BDF8 !important;
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.95), 0 0 8px rgba(14, 165, 233, 1) !important;
    }
    div[data-baseweb="select"]:focus-within span,
    div[data-baseweb="select"]:focus-within div,
    div[data-baseweb="select"]:focus-within p,
    div[data-baseweb="select"]:focus-within * {
        color: #FFFFFF !important;
        font-weight: 800 !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.6) !important;
    }
    div[data-baseweb="select"]:focus-within svg {
        fill: #FFFFFF !important;
    }
    
    /* Popover Menu Options (When Dropdown is Clicked) */
    ul[data-baseweb="menu"] {
        background: #FFFFFF !important;
        border: 1.5px solid #38BDF8 !important;
        box-shadow: 0 10px 25px rgba(2, 132, 199, 0.3) !important;
        border-radius: 8px !important;
    }
    ul[data-baseweb="menu"] li {
        color: #0F172A !important;
        font-weight: 700 !important;
    }
    ul[data-baseweb="menu"] li:hover,
    ul[data-baseweb="menu"] li[aria-selected="true"] {
        background: linear-gradient(135deg, #0284C7 0%, #0369A1 100%) !important;
        color: #FFFFFF !important;
    }

    /* All Text Inputs & Number Inputs */
    div[data-baseweb="input"] > div {
        min-height: 34px !important;
        height: auto !important;
        border: 1.5px solid #38BDF8 !important;
        border-radius: 7px !important;
        background: linear-gradient(135deg, #F0F9FF 0%, #E0F2FE 50%, #BAE6FD 100%) !important;
        font-size: 0.80rem !important;
        font-weight: 800 !important;
        color: #0F172A !important;
        box-shadow: 0 0 10px rgba(56, 189, 248, 0.45) !important;
        transition: all 0.25s ease-in-out !important;
    }
    div[data-baseweb="input"] input {
        color: #0F172A !important;
        font-weight: 800 !important;
    }
    div[data-baseweb="input"] > div:hover {
        background: linear-gradient(135deg, #E0F2FE 0%, #BAE6FD 50%, #7DD3FC 100%) !important;
        border-color: #0284C7 !important;
        box-shadow: 0 0 15px rgba(2, 132, 199, 0.7), 0 0 5px rgba(56, 189, 248, 0.9) !important;
    }
    /* Selected / Focused Input: Pure White Text on Dark Blue */
    div[data-baseweb="input"]:focus-within > div {
        background: linear-gradient(135deg, #0284C7 0%, #0369A1 50%, #075985 100%) !important;
        border: 2px solid #38BDF8 !important;
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.95), 0 0 8px rgba(14, 165, 233, 1) !important;
    }
    div[data-baseweb="input"]:focus-within input,
    div[data-baseweb="input"]:focus-within * {
        color: #FFFFFF !important;
        font-weight: 800 !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.6) !important;
    }

    /* All TextAreas: Light Blue Gradient Default with White Text when focused */
    div[data-baseweb="textarea"] > div,
    div[data-baseweb="textarea"] textarea {
        border: 1.5px solid #38BDF8 !important;
        border-radius: 7px !important;
        background: linear-gradient(135deg, #F0F9FF 0%, #E0F2FE 50%, #BAE6FD 100%) !important;
        color: #0F172A !important;
        font-weight: 800 !important;
        box-shadow: 0 0 10px rgba(56, 189, 248, 0.45) !important;
        transition: all 0.25s ease-in-out !important;
    }
    div[data-baseweb="textarea"]:focus-within > div,
    div[data-baseweb="textarea"] textarea:focus {
        background: linear-gradient(135deg, #0284C7 0%, #0369A1 50%, #075985 100%) !important;
        color: #FFFFFF !important;
        border: 2px solid #38BDF8 !important;
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.95), 0 0 8px rgba(14, 165, 233, 1) !important;
    }

    /* Standard Streamlit Buttons */
    div.stButton button {
        background: linear-gradient(135deg, #F0F9FF 0%, #E0F2FE 50%, #BAE6FD 100%) !important;
        color: #0F172A !important;
        border: 1.5px solid #38BDF8 !important;
        font-size: 0.76rem !important;
        font-weight: 800 !important;
        border-radius: 6px !important;
        box-shadow: 0 0 10px rgba(56, 189, 248, 0.45) !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    div.stButton button:hover {
        background: linear-gradient(135deg, #BAE6FD 0%, #7DD3FC 100%) !important;
        color: #075985 !important;
        border-color: #0284C7 !important;
        box-shadow: 0 0 16px rgba(2, 132, 199, 0.75), 0 0 6px rgba(56, 189, 248, 0.9) !important;
        transform: translateY(-1px);
    }
    div.stButton button:active,
    div.stButton button[kind="primary"] {
        background: linear-gradient(135deg, #0284C7 0%, #0369A1 50%, #075985 100%) !important;
        color: #FFFFFF !important;
        border: 2px solid #38BDF8 !important;
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.95), 0 0 8px rgba(14, 165, 233, 1) !important;
    }
    div.stButton button[kind="primary"] * {
        color: #FFFFFF !important;
        font-weight: 800 !important;
    }

    /* Top Bar Quick Action Buttons */
    .btn-sel-all button {
        background: linear-gradient(135deg, #E0F2FE 0%, #BAE6FD 100%) !important;
        color: #0369A1 !important;
        border: 1.5px solid #38BDF8 !important;
        font-size: 0.76rem !important;
        font-weight: 800 !important;
        height: 28px !important;
        border-radius: 6px !important;
        box-shadow: 0 0 10px rgba(56, 189, 248, 0.45) !important;
    }
    .btn-sel-all button:hover,
    .btn-sel-all button:active {
        background: linear-gradient(135deg, #0284C7 0%, #0369A1 50%, #075985 100%) !important;
        color: #FFFFFF !important;
        border-color: #38BDF8 !important;
        box-shadow: 0 0 18px rgba(56, 189, 248, 0.95) !important;
    }
    
    .btn-clr-all button {
        background: linear-gradient(135deg, #F0F9FF 0%, #E0F2FE 100%) !important;
        color: #334155 !important;
        border: 1.5px solid #94A3B8 !important;
        font-size: 0.76rem !important;
        font-weight: 800 !important;
        height: 28px !important;
        border-radius: 6px !important;
        box-shadow: 0 0 8px rgba(148, 163, 184, 0.4) !important;
    }
    .btn-clr-all button:hover,
    .btn-clr-all button:active {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important;
        color: #FFFFFF !important;
        border-color: #38BDF8 !important;
        box-shadow: 0 0 16px rgba(56, 189, 248, 0.8) !important;
    }

    /* ─── ULTRA-DENSE LEFT COLUMN MICRO-TYPOGRAPHY & ZERO-GAP RULES ─── */
    div[data-testid="column"]:first-child div[data-testid="stVerticalBlock"] {
        gap: 0px !important;
        row-gap: 0px !important;
    }
    div[data-testid="column"]:first-child [data-testid="stVerticalBlockBorderWrapper"] > div {
        gap: 0px !important;
        row-gap: 0px !important;
    }
    div[data-testid="column"]:first-child .element-container,
    div[data-testid="column"]:first-child [data-testid="element-container"] {
        margin: 0px !important;
        padding: 0px !important;
        margin-bottom: 0px !important;
    }
    div[data-testid="column"]:first-child div.stButton {
        margin: 0px !important;
        padding: 0px !important;
        margin-bottom: 0px !important;
    }
    div[data-testid="column"]:first-child [data-testid="stVerticalBlockBorderWrapper"] button {
        height: 22px !important;
        min-height: 22px !important;
        max-height: 22px !important;
        padding: 0px 3px !important;
        margin: 0px 0px 1px 0px !important;
        font-size: 0.58rem !important; /* ~9px micro-font */
        font-weight: 800 !important;
        line-height: 20px !important;
        letter-spacing: 0.1px !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        border-radius: 4px !important;
        border: 1px solid #7DD3FC !important;
        border-left: 3.5px solid #0284C7 !important;
        background: linear-gradient(135deg, #F0F9FF 0%, #E0F2FE 100%) !important;
        color: #0F172A !important;
        display: flex !important;
        justify-content: flex-start !important;
        align-items: center !important;
        text-align: left !important;
        box-shadow: 0 0 6px rgba(125, 211, 252, 0.45) !important;
        -webkit-font-smoothing: antialiased !important;
        transition: all 0.15s ease-in-out !important;
    }
    div[data-testid="column"]:first-child [data-testid="stVerticalBlockBorderWrapper"] button p,
    div[data-testid="column"]:first-child [data-testid="stVerticalBlockBorderWrapper"] button span {
        font-size: 0.58rem !important;
        font-weight: 800 !important;
        color: #0F172A !important;
        line-height: 20px !important;
        white-space: nowrap !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    /* Left Panel Button Hover */
    div[data-testid="column"]:first-child [data-testid="stVerticalBlockBorderWrapper"] button:hover {
        background: linear-gradient(135deg, #BAE6FD 0%, #7DD3FC 100%) !important;
        border-color: #0284C7 !important;
        box-shadow: 0 0 12px rgba(2, 132, 199, 0.75) !important;
    }

    /* Left Panel Selected Stock (Active / Primary): Dark Blue Gradient with HIGH-CONTRAST PURE WHITE TEXT */
    div[data-testid="column"]:first-child [data-testid="stVerticalBlockBorderWrapper"] button[kind="primary"] {
        background: linear-gradient(135deg, #0284C7 0%, #0369A1 50%, #075985 100%) !important;
        border: 1.5px solid #38BDF8 !important;
        border-left: 4.5px solid #38BDF8 !important;
        color: #FFFFFF !important;
        font-weight: 900 !important;
        box-shadow: 0 0 16px rgba(56, 189, 248, 0.95), 0 0 6px rgba(14, 165, 233, 1) !important;
    }
    div[data-testid="column"]:first-child [data-testid="stVerticalBlockBorderWrapper"] button[kind="primary"] p,
    div[data-testid="column"]:first-child [data-testid="stVerticalBlockBorderWrapper"] button[kind="primary"] span,
    div[data-testid="column"]:first-child [data-testid="stVerticalBlockBorderWrapper"] button[kind="primary"] * {
        color: #FFFFFF !important;
        font-weight: 900 !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.6) !important;
    }

    /* Custom Slim Scrollbar for Left Panel */
    div[data-testid="column"]:first-child [data-testid="stVerticalBlockBorderWrapper"] ::-webkit-scrollbar {
        width: 3px !important;
    }
    div[data-testid="column"]:first-child [data-testid="stVerticalBlockBorderWrapper"] ::-webkit-scrollbar-thumb {
        background: #94A3B8 !important;
        border-radius: 3px !important;
    }

    /* Quadrant Pill Badges */
    .badge-leading { 
        background: #DCFCE7; 
        color: #15803D; 
        border: 1px solid #86EFAC; 
        padding: 1px 4px; 
        border-radius: 3px; 
        font-size: 0.62rem; 
        font-weight: 800; 
    }
    .badge-improving { 
        background: #E0E7FF; 
        color: #4338CA; 
        border: 1px solid #A5B4FC; 
        padding: 1px 4px; 
        border-radius: 3px; 
        font-size: 0.62rem; 
        font-weight: 800; 
    }
    .badge-weakening { 
        background: #FEF3C7; 
        color: #B45309; 
        border: 1px solid #FDE047; 
        padding: 1px 4px; 
        border-radius: 3px; 
        font-size: 0.62rem; 
        font-weight: 800; 
    }
    .badge-lagging { 
        background: #FEE2E2; 
        color: #B91C1C; 
        border: 1px solid #FCA5A5; 
        padding: 1px 4px; 
        border-radius: 3px; 
        font-size: 0.62rem; 
        font-weight: 800; 
    }

    /* Expander Compactness */
    div[data-testid="stExpander"] details {
        border: 1px solid #94A3B8 !important;
        border-radius: 4px !important;
        background: #FFFFFF !important;
    }
    div[data-testid="stExpander"] summary {
        font-size: 0.72rem !important;
        font-weight: 800 !important;
        padding: 3px 6px !important;
    }
</style>
""", unsafe_allow_html=True)


# ─── TOP CONTROL BAR (ULTRA-COMPACT STRIKE.MONEY STYLE) ─────────────────────
universe_options = get_all_universe_options()

c_top1, c_top2, c_top3, c_top4, c_top5, c_top6, c_top7 = st.columns([2.0, 2.3, 1.8, 1.5, 1.3, 1.5, 1.3])

with c_top1:
    view_mode = st.radio(
        "View Mode",
        options=["🔘 RRG Chart", "📋 Data Table"],
        horizontal=True,
        key="studio_view_mode"
    )

with c_top2:
    bench_choice = st.selectbox(
        "Benchmark",
        options=list(ALL_BENCHMARK_INDICES.keys()),
        index=0,
        key="studio_bench"
    )

with c_top3:
    timeframe = st.selectbox(
        "Timeframe",
        options=["Weekly (Stage 2)", "Daily (Swing)"],
        index=0,
        key="studio_tf"
    )

with c_top4:
    date_range = st.selectbox(
        "Date Range",
        options=["2 Years", "1 Year", "5 Years"],
        index=0,
        key="studio_range"
    )

with c_top5:
    tail_length = st.number_input(
        "Tail Bars", 
        min_value=1, 
        max_value=30, 
        value=15, 
        step=1,
        key="studio_tail"
    )

with c_top6:
    label_mode = st.selectbox(
        "Labels", 
        ["Show All", "Leaders Only", "Hover Only"], 
        index=0, 
        key="studio_lbl"
    )

with c_top7:
    theme_choice = st.selectbox(
        "Theme", 
        ["☀️ Light", "🌙 Dark"], 
        index=0, 
        key="studio_theme"
    )

# ─── RESOLVE PARAMETERS ──────────────────────────────────────────────────────
interval = "1wk" if "Weekly" in timeframe else "1d"
if "5 Years" in date_range:
    period = "5y"
elif "1 Year" in date_range:
    period = "1y"
else:
    period = "2y"

benchmark_symbol = ALL_BENCHMARK_INDICES.get(bench_choice, "^CRSLDX")
theme_str = "dark" if "Dark" in theme_choice else "light"
lbl_mode_full = "Show All Tickers" if "Show All" in label_mode else ("Top Leaders Only" if "Leaders" in label_mode else "Hover Only")

# ─── JdK ENGINE & NORMALIZATION SETTINGS ──────────────────────────────────────
with st.expander("⚙️ JdK Algorithm & Normalization Settings"):
    c_cfg1, c_cfg2, c_cfg3 = st.columns([2.2, 1.1, 1.1])
    with c_cfg1:
        calc_mode_choice = st.selectbox(
            "Calculation Formula Preset",
            options=[
                "Strike.money Parity — CALIBRATED (fit n=17 · held-out n=14)",
                "Strike.money Model (39-Wk Institutional EMA)",
                "Weinstein Commander Model (12-Wk Swing SMA)",
                "Classical JdK Standard (StockCharts / Optuma Z-Score)"
            ],
            index=0,
            help=(
                "CALIBRATED is the closest match to Strike's printed COORDINATES. The two "
                "axes get separate lookbacks (one shared N cannot serve both), then an "
                "origin-preserving rescale — it pivots about (100,100), so it can never "
                "move a name across a quadrant line.\n\n"
                "FITTED on 17 names, 19-May-2026: ratio error 8.65 → 0.46, momentum "
                "2.22 → 0.25.\n"
                "VALIDATED OUT-OF-SAMPLE on 14 fresh pairs, 18-Aug-2026 — different date, "
                "different names, EIGHT of them below 100 (the half the fit never saw): "
                "ratio MAE 0.74, momentum 0.52, correlation 0.999, quadrant 14/14. The best-"
                "fit slope on that held-out set is 1.006, i.e. the shipped constants need no "
                "correction.\n\n"
                "COST: this chain needs 44 weekly bars (25 + 10 + 7 + 2), so a stock listed "
                "within about 10 months cannot be plotted on it — the constituent list will "
                "say so by name. Weinstein 12/5 needs only 19 bars if you want full coverage "
                "of a young universe.\n"
                "Lookback/Smoothing are ignored by CALIBRATED — it carries its own per-axis "
                "values.\n\n"
                "Strike.money uses a 39-week (200-day) EMA baseline. Weinstein Commander uses "
                "a 12-week (3-month) swing rotation SMA. Classical JdK uses standard deviation "
                "(Z-score) normalization — tested against Strike and REFUTED (a Z-score spans "
                "±2; Strike's ratio spans 100.6–125.7)."
            ),
            key="studio_calc_mode"
        )

    # Dynamic defaults based on preset
    _is_cal = "CALIBRATED" in calc_mode_choice
    # CALIBRATED carries its own per-axis lookbacks (STRIKE_CAL) and IGNORES these
    # two boxes — one shared N is precisely what does not work. Show its real
    # values and disable the inputs, rather than leaving live-looking controls
    # that silently do nothing (they were also still showing the pre-refit 32/5).
    from rrg_engine import STRIKE_CAL as _SC
    def_n = _SC["ratio_length"] if _is_cal else (39 if "Strike" in calc_mode_choice else (12 if "Weinstein" in calc_mode_choice else 14))
    def_s = _SC["ratio_smooth"] if _is_cal else (2 if "Strike" in calc_mode_choice else (5 if "Weinstein" in calc_mode_choice else 1))
    
    with c_cfg2:
        jdk_len_val = st.number_input("Lookback (N)", min_value=5, max_value=52, value=def_n, step=1,
                                      disabled=_is_cal, key="studio_jdk_n",
                                      help="Ignored by the CALIBRATED preset — it uses its own per-axis lookbacks." if _is_cal else None)
    with c_cfg3:
        smooth_len_val = st.number_input("Smoothing (S)", min_value=1, max_value=12, value=def_s, step=1,
                                         disabled=_is_cal, key="studio_smooth_s",
                                         help="Ignored by the CALIBRATED preset — it uses its own per-axis smoothing." if _is_cal else None)

# CALIBRATED must be tested BEFORE the plain "Strike" check — its label also
# contains "Strike.money", so an `in` test in the old order would swallow it.
if "CALIBRATED" in calc_mode_choice:
    calc_mode_str = "strike_cal"
elif "Strike" in calc_mode_choice:
    calc_mode_str = "strike"
elif "Classical" in calc_mode_choice:
    calc_mode_str = "classic"
else:
    calc_mode_str = "weinstein"


# ─── SPLIT LAYOUT: SLIM LEFT (~14.5%) & MAXIMIZED RIGHT (>85.5%) ───────────
col_left, col_right = st.columns([1.75, 10.25])

with col_left:
    # ── Watchlist Selector Dropdown ──
    selected_watchlist_key = st.selectbox(
        "Watchlist / Sector",
        options=list(universe_options.keys()),
        index=0,
        key="studio_wl"
    )

    # ── Custom Watchlist Manager (Create, Edit & Delete) ──
    with st.expander("➕ Manage Custom Watchlists"):
        tab_new_wl, tab_edit_wl = st.tabs(["Create New", "Edit / Delete"])
        
        with tab_new_wl:
            new_wl_name = st.text_input("Watchlist Name:", placeholder="e.g. Breakout Stocks", key="studio_new_wl_n")
            new_wl_symbols = st.text_area("Stock Tickers (comma or newline):", placeholder="e.g. TATAMOTORS, HAL, BEL, ZENTEC, HDFCBANK", key="studio_new_wl_s", height=85)
            if st.button("💾 Create Watchlist", use_container_width=True, key="studio_save_wl"):
                if new_wl_name.strip() and new_wl_symbols.strip():
                    raw_syms = [s.strip().upper().replace('.NS', '').replace('NSE:', '').replace('BSE:', '') for s in new_wl_symbols.replace('\n', ',').split(',') if s.strip()]
                    cw = load_custom_watchlists()
                    cw[new_wl_name.strip()] = list(dict.fromkeys(raw_syms))
                    save_custom_watchlists(cw)
                    st.success(f"Created {new_wl_name} with {len(raw_syms)} stocks!")
                    st.rerun()
                else:
                    st.warning("Please provide a name and at least one ticker.")
                    
        with tab_edit_wl:
            existing_custom = load_custom_watchlists()
            if existing_custom:
                edit_choice = st.selectbox("Select Watchlist:", list(existing_custom.keys()), key="studio_edit_sel")
                curr_stocks_str = ", ".join(existing_custom.get(edit_choice, []))
                edited_stocks = st.text_area("Edit Tickers:", value=curr_stocks_str, key="studio_edit_area", height=85)
                c_w1, c_w2 = st.columns(2)
                with c_w1:
                    if st.button("🔄 Update", use_container_width=True, key="studio_update_wl"):
                        raw_syms = [s.strip().upper().replace('.NS', '').replace('NSE:', '').replace('BSE:', '') for s in edited_stocks.replace('\n', ',').split(',') if s.strip()]
                        existing_custom[edit_choice] = list(dict.fromkeys(raw_syms))
                        save_custom_watchlists(existing_custom)
                        st.success(f"Updated {edit_choice}!")
                        st.rerun()
                with c_w2:
                    if st.button("🗑️ Delete", use_container_width=True, key="studio_del_wl"):
                        existing_custom.pop(edit_choice, None)
                        save_custom_watchlists(existing_custom)
                        st.success(f"Deleted {edit_choice}!")
                        st.rerun()
            else:
                st.info("No custom watchlists created yet.")

    # Resolve active symbols to fetch ONLY active constituents and benchmark (NO NSEI contamination)
    active_entry = universe_options[selected_watchlist_key]
    symbols_to_fetch = list(set(active_entry["symbols"] + [benchmark_symbol]))

    # ── Sort Selector & Search Box ──
    c_s1, c_s2 = st.columns([1.1, 1.0])
    with c_s1:
        sort_by = st.selectbox(
            "Sort",
            options=["🎯 Quadrant", "🔤 A-Z", "📈 4W %", "📏 Distance"],
            index=0,
            key="studio_sort_by"
        )
    with c_s2:
        search_query = st.text_input("Filter", "", key="studio_search", placeholder="Filter...").strip().upper()


# ─── FETCH & COMPUTE DATA ────────────────────────────────────────────────────
with st.spinner("Calculating JdK coordinates..."):
    data_dict = load_universe_data(tuple(symbols_to_fetch), period=period, interval=interval)
    
    clean_bench = benchmark_symbol.replace('.NS', '').replace('^', '')
    benchmark_df = data_dict.get(benchmark_symbol) if benchmark_symbol in data_dict else data_dict.get(clean_bench)
    
    if benchmark_df is None or len(benchmark_df) < 15:
        # Fallback to Nifty 50 if benchmark fails
        benchmark_df = data_dict.get("^NSEI") if "^NSEI" in data_dict else data_dict.get("NSEI")
        if benchmark_df is not None and len(benchmark_df) >= 15:
            benchmark_symbol = "^NSEI"
        else:
            st.error(f"Failed to fetch sufficient benchmark data for {benchmark_symbol}. Please check internet or switch benchmark.")
            st.stop()

    summary_df, tails_dict = compute_universe_rrg(
        data_dict=data_dict,
        benchmark_symbol=benchmark_symbol,
        active_symbols=active_entry["symbols"],
        jdk_length=jdk_len_val,
        smooth_length=smooth_len_val,
        tail_length=tail_length,
        mode=calc_mode_str
    )

if summary_df.empty:
    st.warning("⚠️ No data available for selected universe.")
    st.stop()

# COLLAPSED NAMES (17-Aug). The universe label counts what was REQUESTED; this
# says what was actually plotted and why the two differ. Without it the broad
# market view drew 11 series under an "18 Broad Market Indices" heading, three
# of them the same line under different names — which reads as three independent
# confirmations of a rotation that is really one.
# AS-OF + STALENESS (17-Aug-2026). The coordinates are computed at the last bar
# the benchmark and the constituents SHARE — which was silently a week behind
# when the cached index series lagged the stocks. Always state the date; shout
# only when something is actually behind.
_as_of = summary_df.attrs.get("as_of") or ""
_lag = summary_df.attrs.get("bench_lag") or ""
_stale = summary_df.attrs.get("stale") or {}
if _lag:
    st.error(f"⚠️ {_lag}")
elif _stale:
    st.warning(f"⚠️ {len(_stale)} symbol(s) behind the rest of the universe: "
               + ", ".join(f"{k} ({v})" for k, v in list(_stale.items())[:6])
               + (" …" if len(_stale) > 6 else ""))
if _as_of:
    st.caption(f"Coordinates as of **{_as_of}** (last bar shared by the benchmark and its constituents)")

_collapsed = summary_df.attrs.get("collapsed") or []
_shortened = summary_df.attrs.get("shortened") or []
if _collapsed or _shortened:
    _req = len(active_entry["symbols"])
    _bits = []
    if _collapsed:
        _bits.append(f"{len(_collapsed)} not plotted")
    if _shortened:
        _bits.append(f"{len(_shortened)} on a short tail")
    with st.expander(f"ℹ️ Plotting {len(summary_df)} of {_req} — " + " · ".join(_bits)
                     + "  (click for why)"):
        if _collapsed:
            st.caption("**Not plotted**")
            for _c in _collapsed:
                st.caption(f"• {_c}")
            st.caption(
                "Dropped when the name has too little history for the selected model, "
                "when its symbol no longer trades, when it IS the benchmark, or when its "
                "data came from a DIFFERENT index than the one named. Plotting that last "
                "case would label a dot as an index it is not."
            )
        if _shortened:
            # These ARE plotted — the head is correct, only the trail is stubby.
            # Worth saying, because a 3-bar tail next to a 15-bar one looks like a
            # rendering fault rather than a young index.
            st.caption("**Plotted with a shorter tail** (head is exact; only the trail is short)")
            for _s in _shortened:
                st.caption(f"• {_s}")


# ─── LEFT PANEL: CONSTITUENT CARDS & INSTANT CONTROLS ────────────────────────
with col_left:
    display_df = summary_df.copy()

    # Apply instant search filter
    if search_query:
        display_df = display_df[display_df['Symbol'].str.contains(search_query)]

    # Ensure deduplication and valid rank
    display_df = display_df.drop_duplicates(subset=['Symbol'])
    if 'Quadrant_Rank' not in display_df.columns:
        q_map = {'Leading': 1, 'Improving': 2, 'Weakening': 3, 'Lagging': 4}
        display_df['Quadrant_Rank'] = display_df['Quadrant'].map(q_map).fillna(5)

    # Apply Sort Order
    if sort_by == "🎯 Quadrant":
        display_df = display_df.sort_values(by=['Quadrant_Rank', 'Distance'], ascending=[True, False])
    elif sort_by == "🔤 A-Z":
        display_df = display_df.sort_values(by='Symbol', ascending=True)
    elif sort_by == "📈 4W %":
        display_df = display_df.sort_values(by='4W %', ascending=False)
    elif sort_by == "📏 Distance":
        display_df = display_df.sort_values(by='Distance', ascending=False)

    # Detect if universe changed -> Reset all stocks to selected by default
    if st.session_state.get("active_universe_tracker") != selected_watchlist_key:
        st.session_state["active_universe_tracker"] = selected_watchlist_key
        st.session_state["studio_selected_syms"] = set(display_df['Symbol'].tolist())

    if "studio_selected_syms" not in st.session_state:
        st.session_state["studio_selected_syms"] = set(display_df['Symbol'].tolist())

    # Select All / Clear All action buttons
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        st.markdown('<div class="btn-sel-all">', unsafe_allow_html=True)
        if st.button("✓ All", use_container_width=True, key="btn_sel_all"):
            st.session_state["studio_selected_syms"] = set(display_df['Symbol'].tolist())
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with c_btn2:
        st.markdown('<div class="btn-clr-all">', unsafe_allow_html=True)
        if st.button("✗ Clear", use_container_width=True, key="btn_clr_all"):
            st.session_state["studio_selected_syms"] = set()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # "N of M", not a bare N (18-Aug, Jay: the Watchlist/Sector label said 29 while
    # this said 19, and there was nothing on screen to explain the difference).
    # M = what the index declares, N = what carries enough data to plot. The gap is
    # real and named in the expander above (recent listings, dead tickers, the
    # benchmark itself); showing only N made a correct chart look broken.
    _req_n = len(active_entry["symbols"])
    _hdr = f"CONSTITUENTS ({len(display_df)}"
    if not search_query and len(display_df) < _req_n:
        _hdr += f" of {_req_n}"
    _hdr += "):"
    st.markdown(f"<div style='color: #0F172A; font-weight: 800; font-size: 0.72rem; margin: 3px 0 1px 0;'>{_hdr}</div>", unsafe_allow_html=True)

    # ── Calculate dynamic horizontal fill bars based on Distance ──
    max_dist = max(display_df['Distance'].max(), 0.1) if not display_df.empty else 1.0
    dynamic_css = []
    
    for idx, row in display_df.reset_index(drop=True).iterrows():
        sym = row['Symbol']
        clean_key = f"{sym.replace('^', '').replace('.', '_').replace('-', '_').replace('&', '_')}_{idx}"
        quad = row['Quadrant'].lower()
        dist = row['Distance']
        pct = min(100.0, max(4.0, (dist / max_dist) * 100.0))
        
        if quad == "leading":
            fill_col = "rgba(34, 197, 94, 0.28)"
            fill_active = "rgba(34, 197, 94, 0.65)"
            border_col = "#16A34A"
            bg_active_tail = "#DCFCE7"
        elif quad == "improving":
            fill_col = "rgba(168, 85, 247, 0.28)"
            fill_active = "rgba(168, 85, 247, 0.65)"
            border_col = "#9333EA"
            bg_active_tail = "#F3E8FF"
        elif quad == "weakening":
            fill_col = "rgba(245, 158, 11, 0.28)"
            fill_active = "rgba(245, 158, 11, 0.65)"
            border_col = "#D97706"
            bg_active_tail = "#FEF3C7"
        else: # lagging
            fill_col = "rgba(239, 68, 68, 0.28)"
            fill_active = "rgba(239, 68, 68, 0.65)"
            border_col = "#DC2626"
            bg_active_tail = "#FEE2E2"
            
        is_active = (sym in st.session_state["studio_selected_syms"])
        
        if is_active:
            dynamic_css.append(f"""
            div.st-key-btn_tile_{clean_key} button {{
                background: linear-gradient(to right, {fill_active} {pct:.1f}%, {bg_active_tail} {pct:.1f}%) !important;
                border-left: 4.5px solid {border_col} !important;
                border-color: {border_col} !important;
                color: #0F172A !important;
                font-weight: 800 !important;
            }}
            """)
        else:
            dynamic_css.append(f"""
            div.st-key-btn_tile_{clean_key} button {{
                background: linear-gradient(to right, {fill_col} {pct:.1f}%, #FFFFFF {pct:.1f}%) !important;
                border-left: 3px solid {border_col} !important;
                color: #1E293B !important;
            }}
            """)

    st.markdown("<style>" + "".join(dynamic_css) + "</style>", unsafe_allow_html=True)

    # Clickable Stock Card List with Distance-Filled Progress Bars
    with st.container(height=720):
        for idx, row in display_df.reset_index(drop=True).iterrows():
            sym = row['Symbol']
            clean_key = f"{sym.replace('^', '').replace('.', '_').replace('-', '_').replace('&', '_')}_{idx}"
            quad = row['Quadrant']
            price_str = f"₹{row['Last_Price']:,.1f}" if row['Last_Price'] > 0 else "-"
            chg_str = f"{row['4W %']:+.1f}%"
            dist_val = f"d:{row['Distance']:.1f}"
            quad_short = quad[:4].upper()
            
            is_active = (sym in st.session_state["studio_selected_syms"])
            icon = "✓ " if is_active else "  "

            # Formatted single-line micro-label
            card_label = f"{icon}{sym} [{quad_short}] {dist_val} {price_str} ({chg_str})"

            if st.button(
                card_label, 
                key=f"btn_tile_{clean_key}", 
                use_container_width=True
            ):
                # Single-focus selection: click selects this stock, deselects previous
                st.session_state["studio_selected_syms"] = {sym}
                st.rerun()


# ─── RIGHT MAIN AREA: MAXIMIZED 4-QUADRANT RRG CANVAS (>86% WIDTH) ────────
with col_right:
    # Top Sparkline Ribbon
    sparkline_fig = render_benchmark_sparkline(benchmark_symbol, data_dict, timeframe)
    sparkline_fig.update_layout(height=55, margin=dict(l=5, r=5, t=2, b=2))
    st.plotly_chart(sparkline_fig, use_container_width=True, config={'displayModeBar': False})

    if "RRG Chart" in view_mode:
        selected_symbols_list = list(st.session_state.get("studio_selected_syms", set()))
        filtered_plot_df = summary_df.copy()
        if selected_symbols_list:
            filtered_plot_df = filtered_plot_df[filtered_plot_df['Symbol'].isin(selected_symbols_list)]
        else:
            filtered_plot_df = filtered_plot_df.head(0)

        fig_rrg = render_rrg_plotly(
            summary_df=filtered_plot_df,
            tails_dict=tails_dict,
            title=f"{selected_watchlist_key} vs {bench_choice} ({timeframe})",
            tail_length=tail_length,
            selected_symbols=selected_symbols_list,
            label_mode=lbl_mode_full,
            chart_height=680,
            theme=theme_str
        )

        fig_rrg.update_layout(
            margin=dict(l=30, r=30, t=35, b=30)
        )

        st.plotly_chart(
            fig_rrg, 
            use_container_width=True, 
            config={
                'scrollZoom': True,
                'displayModeBar': True,
                'modeBarButtonsToRemove': ['lasso2d'],
                'displaylogo': False
            }
        )

        # ── DHAN TECHNICALS & SCREENER.IN FUNDAMENTALS DOCK ──
        if len(selected_symbols_list) == 1:
            active_sym = selected_symbols_list[0]
            tech = get_dhan_technicals(active_sym, data_dict, benchmark_symbol)
            fund = get_screener_fundamentals(active_sym)
            
            c_dock1, c_dock2 = st.columns(2)
            with c_dock1:
                st.markdown(f"""
                <div style="background: #FFFFFF; border: 1.5px solid #2563EB; border-radius: 6px; padding: 8px 12px; margin-top: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #E2E8F0; padding-bottom: 4px; margin-bottom: 6px;">
                        <span style="font-weight: 800; font-size: 0.78rem; color: #1E40AF;">⚡ DHAN DATA API — TECHNICAL PULSE</span>
                        <span style="font-size: 0.68rem; font-weight: 800; background: #DBEAFE; color: #1D4ED8; padding: 1px 6px; border-radius: 3px;">{tech['Weinstein_Stage']}</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; font-size: 0.72rem;">
                        <div><span style="color: #64748B;">LTP:</span> <b>₹{tech['LTP']:,.1f}</b> <span style="color: {'#16A34A' if tech['Day_Chg_Pct'] >= 0 else '#DC2626'}; font-weight: 700;">({tech['Day_Chg_Pct']:+.1f}%)</span></div>
                        <div><span style="color: #64748B;">4W Return:</span> <b style="color: {'#16A34A' if tech['4W_Chg_Pct'] >= 0 else '#DC2626'};">{tech['4W_Chg_Pct']:+.1f}%</b></div>
                        <div><span style="color: #64748B;">Vol Surge:</span> <b style="color: {'#16A34A' if tech['Vol_Surge'] >= 1.2 else '#475569'};">{tech['Vol_Surge']:.2f}x</b> <span style="font-size: 0.62rem; color: #94A3B8;">(20D)</span></div>
                        <div><span style="color: #64748B;">Mansfield RS:</span> <b style="color: {'#16A34A' if tech['Mansfield_RS'] >= 0 else '#DC2626'};">{tech['Mansfield_RS']:+.2f}%</b></div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; font-size: 0.70rem; margin-top: 4px; border-top: 1px dashed #F1F5F9; padding-top: 4px;">
                        <div><span style="color: #64748B;">52W High:</span> <b>₹{tech['52W_High']:,.1f}</b> <span style="font-size: 0.62rem; color: #DC2626;">({tech['Dist_52W_High_Pct']:+.1f}%)</span></div>
                        <div><span style="color: #64748B;">50 SMA / 200 SMA:</span> <b>₹{tech['SMA_50']:,.0f}</b> / <b>₹{tech['SMA_200']:,.0f}</b></div>
                        <div><span style="color: #64748B;">SMA Stack:</span> <span style="font-weight: 700; color: #0F172A;">{tech['SMA_Alignment']}</span></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with c_dock2:
                mkt_cap_str = f"₹{fund['Market_Cap_Cr']:,.0f} Cr" if fund['Market_Cap_Cr'] else "N/A"
                pe_str = f"{fund['PE']:.1f}" if fund['PE'] else "N/A"
                roce_str = f"{fund['ROCE_Pct']:.1f}%" if fund['ROCE_Pct'] else "N/A"
                roe_str = f"{fund['ROE_Pct']:.1f}%" if fund['ROE_Pct'] else "N/A"
                de_str = f"{fund['Debt_to_Equity']:.2f}" if fund['Debt_to_Equity'] is not None else "N/A"
                prom_str = f"{fund['Promoter_Pct']:.1f}%" if fund['Promoter_Pct'] else "N/A"
                bv_str = f"₹{fund['Book_Value']:,.1f}" if fund['Book_Value'] else "N/A"
                
                st.markdown(f"""
                <div style="background: #FFFFFF; border: 1.5px solid #059669; border-radius: 6px; padding: 8px 12px; margin-top: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #E2E8F0; padding-bottom: 4px; margin-bottom: 6px;">
                        <span style="font-weight: 800; font-size: 0.78rem; color: #065F46;">📊 SCREENER.IN — FUNDAMENTAL SCORECARD</span>
                        <span style="font-size: 0.68rem; font-weight: 800; background: #D1FAE5; color: #047857; padding: 1px 6px; border-radius: 3px;">{fund['Name']}</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; font-size: 0.72rem;">
                        <div><span style="color: #64748B;">Mkt Cap:</span> <b>{mkt_cap_str}</b></div>
                        <div><span style="color: #64748B;">Stock P/E:</span> <b>{pe_str}</b></div>
                        <div><span style="color: #64748B;">ROCE:</span> <b style="color: {'#059669' if fund['ROCE_Pct'] and fund['ROCE_Pct'] >= 15 else '#0F172A'};">{roce_str}</b></div>
                        <div><span style="color: #64748B;">ROE:</span> <b style="color: {'#059669' if fund['ROE_Pct'] and fund['ROE_Pct'] >= 15 else '#0F172A'};">{roe_str}</b></div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; font-size: 0.70rem; margin-top: 4px; border-top: 1px dashed #F1F5F9; padding-top: 4px;">
                        <div><span style="color: #64748B;">Debt / Equity:</span> <b style="color: {'#059669' if fund['Debt_to_Equity'] is not None and fund['Debt_to_Equity'] < 0.5 else ('#DC2626' if fund['Debt_to_Equity'] and fund['Debt_to_Equity'] > 1.5 else '#0F172A')};">{de_str}</b></div>
                        <div><span style="color: #64748B;">Promoter Stake:</span> <b>{prom_str}</b></div>
                        <div><span style="color: #64748B;">Book Value:</span> <b>{bv_str}</b></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    else:
        st.markdown("#### 📊 Sector Universe: Full Technical (Dhan) & Fundamental (Screener.in) Matrix")
        
        # Build enriched table
        table_rows = []
        for _, r in summary_df.iterrows():
            sym = r['Symbol']
            tech = get_dhan_technicals(sym, data_dict, benchmark_symbol)
            fund = get_screener_fundamentals(sym)
            table_rows.append({
                'Symbol': sym,
                'Quadrant': r['Quadrant_Badge'],
                'Arrow': r.get('Arrow', '•'),
                'Trajectory': r.get('Trajectory', '-'),
                'Tradeable Gate': r.get('Tradeable Gate', '-'),
                'Score Bonus': r.get('RRG Score', 0),
                '4W %': r.get('4W %', 0.0),
                'RS-Ratio': r['RS-Ratio'],
                'RS-Momentum': r['RS-Momentum'],
                'Distance': r['Distance'],
                'LTP (₹)': tech['LTP'],
                'Day %': tech['Day_Chg_Pct'],
                'Vol Surge': tech['Vol_Surge'],
                'Stage': tech['Weinstein_Stage'],
                'Mansfield RS %': tech['Mansfield_RS'],
                'Mkt Cap (₹ Cr)': fund['Market_Cap_Cr'],
                'Stock P/E': fund['PE'],
                'ROCE %': fund['ROCE_Pct'],
                'ROE %': fund['ROE_Pct'],
                'Debt / Equity': fund['Debt_to_Equity'],
                'Promoter %': fund['Promoter_Pct']
            })
            
        full_matrix_df = pd.DataFrame(table_rows)
        st.dataframe(
            full_matrix_df,
            use_container_width=True,
            hide_index=True
        )
        
        # CSV Export
        csv_data = full_matrix_df.to_csv(index=False)
        st.download_button(
            label="📥 Export Full Technical & Fundamental Dataset (CSV)",
            data=csv_data,
            file_name=f"RRG_{selected_watchlist_key.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
