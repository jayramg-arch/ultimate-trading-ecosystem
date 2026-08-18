import streamlit as st
import pandas as pd
import numpy as np
import os
import sys
import json
from datetime import datetime

# Local imports
import data_provider as dp
import sector_lookup as sl
from rrg_engine import (
    SECTOR_INDICES,
    QUADRANT_COLORS,
    calculate_jdk_rrg,
    compute_universe_rrg,
    render_rrg_plotly,
    render_benchmark_sparkline,
    get_all_universe_options,
    get_all_sectors_from_db,
    load_custom_watchlists,
    save_custom_watchlists,
    load_universe_data
)

st.set_page_config(
    page_title="Relative Rotation Graph (RRG) — Strike.Money Style",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for Strike.Money authentic high-contrast aesthetics
st.markdown("""
<style>
    /* Global Background */
    .stApp { 
        background-color: #F8FAFC; 
        color: #0F172A;
    }
    
    /* Top Toolbar Ribbon */
    .strike-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px 16px;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    /* Symbol Row Item */
    .symbol-row-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 10px;
        margin-bottom: 4px;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 6px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }
    .symbol-row-item:hover {
        background: #F1F5F9;
        border-color: #CBD5E1;
    }
    
    /* Quadrant Pill Badges (High Contrast) */
    .badge-leading { 
        background: #DCFCE7; 
        color: #15803D; 
        border: 1px solid #86EFAC; 
        padding: 2px 7px; 
        border-radius: 4px; 
        font-size: 0.72rem; 
        font-weight: 700; 
    }
    .badge-improving { 
        background: #E0E7FF; 
        color: #4338CA; 
        border: 1px solid #A5B4FC; 
        padding: 2px 7px; 
        border-radius: 4px; 
        font-size: 0.72rem; 
        font-weight: 700; 
    }
    .badge-weakening { 
        background: #FEF3C7; 
        color: #B45309; 
        border: 1px solid #FDE047; 
        padding: 2px 7px; 
        border-radius: 4px; 
        font-size: 0.72rem; 
        font-weight: 700; 
    }
    .badge-lagging { 
        background: #FEE2E2; 
        color: #B91C1C; 
        border: 1px solid #FCA5A5; 
        padding: 2px 7px; 
        border-radius: 4px; 
        font-size: 0.72rem; 
        font-weight: 700; 
    }
</style>
""", unsafe_allow_html=True)


# ─── TOP CONTROL BAR (STRIKE.MONEY STYLE) ────────────────────────────────────
universe_options = get_all_universe_options()

c_top1, c_top2, c_top3, c_top4, c_top5 = st.columns([3, 2, 2, 2, 2])

with c_top1:
    view_mode = st.radio(
        "View Mode:",
        options=["🔘 RRG (Rotation Graph)", "📋 Data Cockpit Table"],
        horizontal=True,
        label_visibility="collapsed"
    )

with c_top2:
    bench_choice = st.selectbox(
        "Benchmark:",
        options=[
            "Nifty 500 (^CRSLDX)",
            "Nifty 50 (^NSEI)",
            "Bank Nifty (^NSEBANK)",
            "Auto Index (^CNXAUTO)",
            "IT Index (^CNXIT)",
            "Pharma Index (^CNXPHARMA)",
            "Metal Index (^CNXMETAL)",
            "FMCG Index (^CNXFMCG)",
            "Realty Index (^CNXREALTY)",
            "Infra Index (^CNXINFRA)",
            "Commodities (^CNXCMDT)"
        ],
        index=0
    )

with c_top3:
    timeframe = st.selectbox(
        "Timeframe:",
        options=["Weekly (Positional / Stage 2)", "Daily (Swing Trading)"],
        index=0
    )

with c_top4:
    date_range = st.selectbox(
        "Date Range:",
        options=["2 Years (Standard)", "1 Year", "5 Years"],
        index=0
    )

with c_top5:
    tail_length = st.number_input("Tail Length (Weeks / Bars):", min_value=1, max_value=15, value=10, step=1)

# Resolution of Timeframe and Period
interval = "1wk" if "Weekly" in timeframe else "1d"
if "5 Years" in date_range:
    period = "5y"
elif "1 Year" in date_range:
    period = "1y"
else:
    period = "2y"

# Benchmark ticker resolution
BENCHMARK_MAP = {
    "Nifty 500 (^CRSLDX)": "^CRSLDX",
    "Nifty 50 (^NSEI)": "^NSEI",
    "Bank Nifty (^NSEBANK)": "^NSEBANK",
    "Auto Index (^CNXAUTO)": "^CNXAUTO",
    "IT Index (^CNXIT)": "^CNXIT",
    "Pharma Index (^CNXPHARMA)": "^CNXPHARMA",
    "Metal Index (^CNXMETAL)": "^CNXMETAL",
    "FMCG Index (^CNXFMCG)": "^CNXFMCG",
    "Realty Index (^CNXREALTY)": "^CNXREALTY",
    "Infra Index (^CNXINFRA)": "^CNXINFRA",
    "Commodities (^CNXCMDT)": "^CNXCMDT"
}
benchmark_symbol = BENCHMARK_MAP.get(bench_choice, "^CRSLDX")


# ─── SUB-TOOLBAR (VIEW CONTROLS & TIMELINE) ──────────────────────────────────
c_sub1, c_sub2, c_sub3, c_sub4, c_sub5 = st.columns([3, 2, 2, 2, 2])
with c_sub1:
    st.markdown(f"<span style='color: #334155; font-weight: 600;'>📅 Historical Horizon: {datetime.now().strftime('%d %b %Y')} · Benchmark: <code>{benchmark_symbol}</code></span>", unsafe_allow_html=True)
with c_sub2:
    chart_height = st.slider("Canvas Height (px):", min_value=500, max_value=1000, value=680, step=20)
with c_sub3:
    label_mode = st.selectbox("Ticker Labels:", ["Show All Tickers", "Top Leaders Only", "Hover Only"], index=0)
with c_sub4:
    theme_choice = st.selectbox("Theme:", ["☀️ Light Canvas (Strike)", "🌙 Dark Canvas"], index=0)
with c_sub5:
    tradeable_filter = st.checkbox("BUY OK Only (✓)", value=False)

theme_str = "dark" if "Dark" in theme_choice else "light"


# ─── SPLIT LAYOUT: LEFT PANEL (SYMBOLS) & RIGHT (RRG CANVAS) ────────────────
col_left, col_right = st.columns([4, 9])

with col_left:
    # ── Watchlist Selector Dropdown ──
    selected_watchlist_key = st.selectbox(
        "Watchlist / Universe:",
        options=list(universe_options.keys()),
        index=0
    )

    # ── Add/Create Watchlist Expander ──
    with st.expander("➕ Create / Manage Custom Watchlists"):
        new_wl_name = st.text_input("New Watchlist Name:", placeholder="e.g. My Breakouts")
        new_wl_symbols = st.text_area("Stock Tickers (comma separated):", placeholder="e.g. TATAMOTORS, HAL, BEL, DIXON, TRENT")
        if st.button("💾 Save Watchlist", use_container_width=True):
            if new_wl_name and new_wl_symbols:
                raw_syms = [s.strip().upper().replace('.NS', '') for s in new_wl_symbols.split(',') if s.strip()]
                cw = load_custom_watchlists()
                cw[new_wl_name] = raw_syms
                save_custom_watchlists(cw)
                st.success(f"Watchlist '{new_wl_name}' saved!")
                st.rerun()

    # Resolve active symbols to fetch
    active_entry = universe_options[selected_watchlist_key]
    symbols_to_fetch = active_entry["symbols"] + [benchmark_symbol, "^NSEI"]

    # ── Search Box ──
    search_query = st.text_input("🔍 Search symbol in list:", "").strip().upper()


# ─── FETCH & COMPUTE DATA ────────────────────────────────────────────────────
with st.spinner("🔄 Fetching market data & calculating JdK coordinates..."):
    data_dict = load_universe_data(tuple(symbols_to_fetch), period=period, interval=interval)
    summary_df, tails_dict = compute_universe_rrg(
        data_dict=data_dict,
        benchmark_symbol=benchmark_symbol.replace('.NS', '').replace('^', ''),
        jdk_length=12,
        tail_length=tail_length,
        # 18-Aug-2026: Strike.Money parity - same reason as the RRG tab in
        # weinstein_commander_web_v4.0.py. Both callers must pass this or the two
        # surfaces disagree with each other as well as with RRG Studio.
        mode="strike_cal"
    )

if summary_df.empty:
    st.warning("⚠️ No RRG data returned. Please select a different universe or check symbol tickers.")
    st.stop()


# ─── LEFT PANEL: STRIKE.MONEY SYMBOL TABLE WITH CHECKBOXES ───────────────────
with col_left:
    # Apply search filter
    display_df = summary_df.copy()
    if search_query:
        display_df = display_df[display_df['Symbol'].str.contains(search_query)]
    if tradeable_filter:
        display_df = display_df[display_df['Is_Tradeable'] == True]

    # Select All / Deselect All controls
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("✓ Select All", use_container_width=True):
            st.session_state["selected_symbols_rrg"] = display_df['Symbol'].tolist()
    with c_btn2:
        if st.button("✗ Clear All", use_container_width=True):
            st.session_state["selected_symbols_rrg"] = []

    # Initialize session state for selected symbols if not set
    if "selected_symbols_rrg" not in st.session_state:
        st.session_state["selected_symbols_rrg"] = display_df['Symbol'].head(15).tolist()

    st.markdown(f"<div style='color: #0F172A; font-weight: 700; margin: 8px 0 4px 0;'>Constituent Symbols ({len(display_df)}):</div>", unsafe_allow_html=True)

    # Interactive Checkbox list matching Strike.Money
    selected_symbols_list = []
    
    # Scrollable container for symbols
    with st.container(height=540):
        for _, row in display_df.iterrows():
            sym = row['Symbol']
            quad = row['Quadrant']
            price_str = f"₹{row['Last_Price']:,.2f}" if row['Last_Price'] > 0 else "-"
            chg_str = f"{row['4W %']:+.1f}%"
            badge_class = f"badge-{quad.lower()}"
            chg_color = "#15803D" if row['4W %'] >= 0 else "#DC2626"
            
            # Row Layout
            c_chk, c_info = st.columns([1, 6])
            with c_chk:
                is_checked = st.checkbox(
                    f"chk_{sym}",
                    value=(sym in st.session_state["selected_symbols_rrg"]),
                    key=f"chk_sym_{sym}",
                    label_visibility="collapsed"
                )
                if is_checked:
                    selected_symbols_list.append(sym)
                    
            with c_info:
                st.markdown(f"""
                <div class="symbol-row-item">
                    <div>
                        <span style="font-weight: 700; font-size: 0.92rem; color: #0F172A;">{sym}</span> &nbsp;
                        <span class="{badge_class}">{quad.upper()}</span>
                    </div>
                    <div style="text-align: right;">
                        <span style="font-weight: 600; font-size: 0.88rem; color: #334155;">{price_str}</span> &nbsp;
                        <span style="color: {chg_color}; font-weight: 700; font-size: 0.85rem;">{chg_str}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)


# ─── RIGHT MAIN AREA: 4-QUADRANT RRG CANVAS OR DATA TABLE ────────────────────
with col_right:
    # Top Sparkline Ribbon
    sparkline_fig = render_benchmark_sparkline(benchmark_symbol, data_dict, timeframe)
    st.plotly_chart(sparkline_fig, use_container_width=True, config={'displayModeBar': False})

    if "Rotation Graph" in view_mode:
        # Filter plotted symbols by user's checkbox selection
        filtered_plot_df = summary_df.copy()
        if selected_symbols_list:
            filtered_plot_df = filtered_plot_df[filtered_plot_df['Symbol'].isin(selected_symbols_list)]

        # Render 4-Quadrant Plotly Graph with Pan & Zoom
        fig_rrg = render_rrg_plotly(
            summary_df=filtered_plot_df,
            tails_dict=tails_dict,
            title=f"{selected_watchlist_key} Rotation vs {bench_choice} ({timeframe})",
            tail_length=tail_length,
            selected_symbols=selected_symbols_list,
            label_mode=label_mode,
            chart_height=chart_height,
            theme=theme_str
        )

        # Plotly chart with interactive pan and zoom enabled
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

    else:
        # Data Cockpit Table (Pine v67.4 Standard)
        st.markdown("### 📊 RRG Rotation & Tradeable Gate Cockpit")
        st.dataframe(
            summary_df[[
                'Symbol', 'Quadrant_Badge', 'Arrow', 'Trajectory', 'Tradeable Gate', 
                'RRG Score', 'RS-Ratio', 'RS-Momentum', '4W %', 'Distance', 'Last_Price'
            ]].rename(columns={
                'Quadrant_Badge': 'Current Quadrant',
                'Distance': 'Dist from Center',
                'RRG Score': 'Score Bonus'
            }),
            use_container_width=True,
            hide_index=True
        )
