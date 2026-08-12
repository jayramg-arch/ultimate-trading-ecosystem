import streamlit as st
import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

# Local imports
import data_provider as dp
import sector_lookup as sl
from rrg_engine import (
    SECTOR_INDICES,
    QUADRANT_COLORS,
    calculate_jdk_rrg,
    compute_universe_rrg,
    render_rrg_plotly
)

st.set_page_config(
    page_title="Relative Rotation Graphs (RRG) — Web Commander",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main { background-color: #090d16; }
    .stMetric { background-color: #1e293b; padding: 12px; border-radius: 8px; border: 1px solid #334155; }
    .quadrant-badge-leading { background-color: rgba(38, 166, 154, 0.2); color: #26a69a; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .quadrant-badge-improving { background-color: rgba(41, 98, 255, 0.2); color: #2962ff; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .quadrant-badge-weakening { background-color: rgba(255, 179, 0, 0.2); color: #ffb300; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .quadrant-badge-lagging { background-color: rgba(239, 83, 80, 0.2); color: #ef5350; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


# Predefined Stock Watchlists
DEFENSE_STOCKS = [
    'DATAPATTNS.NS', 'HAL.NS', 'BEL.NS', 'BDL.NS', 'COCHINSHIP.NS', 
    'MAZDOCK.NS', 'GRSE.NS', 'SOLARINDS.NS', 'ZENTEC.NS', 'MTARTECH.NS', 
    'BEML.NS', 'PARAS.NS', 'IDEAFORGE.NS', 'ASTRAMICRO.NS', 'DCXIND.NS'
]

CHEMICAL_STOCKS = [
    'DEEPAKNTR.NS', 'AARTIIND.NS', 'NAVINFLUOR.NS', 'ATUL.NS', 'SRF.NS', 
    'CLEAN.NS', 'FINEORG.NS', 'GALAXYSURF.NS', 'CHAMBLFERT.NS', 
    'COROMANDEL.NS', 'FACT.NS', 'UPL.NS', 'PIIND.NS', 'SUMICHEM.NS'
]

NIFTY_50_STOCKS = [
    'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'INFY.NS', 
    'BHARTIARTL.NS', 'ITC.NS', 'SBIN.NS', 'LTIM.NS', 'LT.NS', 
    'HINDUNILVR.NS', 'AXISBANK.NS', 'KOTAKBANK.NS', 'M&M.NS', 'TATAMOTORS.NS', 
    'SUNPHARMA.NS', 'NTPC.NS', 'ONGC.NS', 'POWERGRID.NS', 'TATASTEEL.NS', 
    'COALINDIA.NS', 'BAJFINANCE.NS', 'MARUTI.NS', 'ADANIENT.NS', 'ASIANPAINT.NS'
]


# load_universe_data now lives in rrg_engine so the main app can import it too
# (it could not import this file - a module name cannot start with a digit).
from rrg_engine import load_universe_data


# ── PAGE HEADER ─────────────────────────────────────────────────────────────
st.title("🔄 Relative Rotation Graphs (RRG)")
st.caption("Canonical JdK 4-Quadrant Sector & Stock Rotation Engine · Powered by Dhan Data")

# ── SIDEBAR CONTROLS ────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ RRG Configuration")

    mode = st.radio(
        "Select Rotation Mode:",
        options=[
            "🌍 19 Nifty Sector Indices",
            "🛡️ Capital Goods & Defense Stocks",
            "🧪 Specialty Chemicals & Commodities",
            "🏆 Nifty 50 Heavyweights",
            "🔍 Intra-Sector Breakdown",
            "💼 Custom Watchlist"
        ]
    )

    timeframe = st.selectbox(
        "Timeframe / Horizon:",
        options=["Weekly (Positional / Stage 2)", "Daily (Swing Trading)"],
        index=0
    )
    interval = "1wk" if "Weekly" in timeframe else "1d"
    period = "2y" if "Weekly" in timeframe else "6mo"

    tail_length = st.slider("Historical Tail Length (Bars / Weeks):", min_value=1, max_value=15, value=6)
    jdk_length = st.slider("JdK Normalization Period:", min_value=6, max_value=26, value=12)

    # Secondary Filter for Sector Breakdown
    selected_sector_name = None
    custom_symbols_raw = None

    if mode == "🔍 Intra-Sector Breakdown":
        selected_sector_name = st.selectbox(
            "Choose Sector to Drill Down:",
            options=list(SECTOR_INDICES.keys())
        )
    elif mode == "💼 Custom Watchlist":
        custom_symbols_raw = st.text_area(
            "Enter Stock Tickers (comma separated):",
            value="DATAPATTNS, HAL, BEL, DEEPAKNTR, DIXON, TRENT, POLYCAB"
        )


# ── DATA RESOLUTION & FETCHING ──────────────────────────────────────────────
with st.spinner("🔄 Fetching market data & computing JdK RRG coordinates..."):
    symbols_to_fetch = []
    bench_symbol = "^CRSLDX" # Nifty 500
    display_title = ""

    if mode == "🌍 19 Nifty Sector Indices":
        symbols_to_fetch = list(SECTOR_INDICES.values()) + [bench_symbol, "^NSEI"]
        display_title = f"Nifty Sector Rotation vs Nifty 500 ({timeframe})"

    elif mode == "🛡️ Capital Goods & Defense Stocks":
        symbols_to_fetch = DEFENSE_STOCKS + [bench_symbol, "BSE:CG"]
        display_title = f"Defense & Capital Goods Rotation ({timeframe})"

    elif mode == "🧪 Specialty Chemicals & Commodities":
        symbols_to_fetch = CHEMICAL_STOCKS + [bench_symbol, "^CNXCMDT"]
        display_title = f"Specialty Chemicals & Commodities Rotation ({timeframe})"

    elif mode == "🏆 Nifty 50 Heavyweights":
        symbols_to_fetch = NIFTY_50_STOCKS + [bench_symbol, "^NSEI"]
        display_title = f"Nifty 50 Stock Rotation vs Nifty 500 ({timeframe})"

    elif mode == "🔍 Intra-Sector Breakdown" and selected_sector_name:
        sec_ticker = SECTOR_INDICES[selected_sector_name]
        bench_symbol = sec_ticker
        
        # Get all stocks in this sector from sectors.db
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sectors.db")
        sec_stocks = []
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                rows = cur.execute("SELECT symbol FROM stock_sector WHERE sector_index = ?", (sec_ticker,)).fetchall()
                sec_stocks = [r[0] + ".NS" for r in rows]

        if not sec_stocks:
            sec_stocks = DEFENSE_STOCKS
            
        symbols_to_fetch = sec_stocks + [sec_ticker, "^NSEI"]
        display_title = f"{selected_sector_name} Constituent Stocks vs {selected_sector_name} ({timeframe})"

    elif mode == "💼 Custom Watchlist" and custom_symbols_raw:
        raw_list = [s.strip().upper().replace('.NS', '') for s in custom_symbols_raw.split(',') if s.strip()]
        symbols_to_fetch = [s + ".NS" for s in raw_list] + [bench_symbol, "^NSEI"]
        display_title = f"Custom Watchlist Rotation vs Nifty 500 ({timeframe})"

    # Fetch data
    data_dict = load_universe_data(tuple(symbols_to_fetch), period=period, interval=interval)

    # Compute Canonical JdK RRG
    summary_df, tails_dict = compute_universe_rrg(
        data_dict=data_dict,
        benchmark_symbol=bench_symbol.replace('.NS', '').replace('^', ''),
        jdk_length=jdk_length,
        tail_length=tail_length
    )


# ── QUADRANT SUMMARY METRICS ────────────────────────────────────────────────
if not summary_df.empty:
    leading_cnt = len(summary_df[summary_df['Quadrant'] == 'Leading'])
    improving_cnt = len(summary_df[summary_df['Quadrant'] == 'Improving'])
    weakening_cnt = len(summary_df[summary_df['Quadrant'] == 'Weakening'])
    lagging_cnt = len(summary_df[summary_df['Quadrant'] == 'Lagging'])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🟢 Leading Quadrant", f"{leading_cnt}", help="Outperforming with strong momentum")
    c2.metric("🔵 Improving Quadrant", f"{improving_cnt}", help="Underperforming but momentum turning UP")
    c3.metric("🟠 Weakening Quadrant", f"{weakening_cnt}", help="Outperforming but momentum turning DOWN")
    c4.metric("🔴 Lagging Quadrant", f"{lagging_cnt}", help="Underperforming with weak momentum")

    st.markdown("---")

    # ── 2D RRG PLOTLY CANVAS ────────────────────────────────────────────────
    fig_rrg = render_rrg_plotly(
        summary_df=summary_df,
        tails_dict=tails_dict,
        title=display_title,
        tail_length=tail_length
    )
    st.plotly_chart(fig_rrg, use_container_width=True)

    # ── DETAILED DATA TABLE ─────────────────────────────────────────────────
    st.markdown("### 📊 RRG Rotation & Tradeable Gate Cockpit (Pine v67.4 Standard)")

    # Filter controls
    col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
    with col_f1:
        quad_filter = st.multiselect(
            "Filter by Quadrant:",
            options=["Leading", "Improving", "Weakening", "Lagging"],
            default=["Leading", "Improving", "Weakening", "Lagging"]
        )
    with col_f2:
        tradeable_only = st.checkbox("Filter Tradeable Setups ONLY (✓ BUY OK)", value=False)
    with col_f3:
        search_query = st.text_input("🔍 Search Symbol:", "").strip().upper()

    filtered_df = summary_df[summary_df['Quadrant'].isin(quad_filter)]
    if tradeable_only:
        filtered_df = filtered_df[filtered_df['Is_Tradeable'] == True]
    if search_query:
        filtered_df = filtered_df[filtered_df['Symbol'].str.contains(search_query)]

    # Render Clean Table matching Pine v67.4 Dashboard format
    st.dataframe(
        filtered_df[[
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

else:
    st.warning("⚠️ No data returned for the selected universe/timeframe. Please select another mode or check symbol tickers.")
