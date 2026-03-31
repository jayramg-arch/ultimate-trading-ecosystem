import streamlit as st
import os

# 1. Page Configuration (Must be the ONLY call across the entire app)
st.set_page_config(
    page_title="Weinstein Commander Web v3",
    page_icon="🦁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Define the Pages
dashboard_page = st.Page("pages/1_home.py", title="Dashboard", icon="📊", default=True)
xray_page = st.Page("pages/2_xray.py", title="Fundamental X-Ray", icon="🔬")
journal_page = st.Page("pages/3_journal.py", title="Trade Journal", icon="📘")
autopsy_page = st.Page("pages/4_autopsy.py", title="AI Autopsy", icon="🏥")

# 3. Create the Navigation Menu
pg = st.navigation({
    "Commander Core": [dashboard_page, journal_page],
    "Analytics": [xray_page, autopsy_page]
})

# 3.5. Fix Native Navigation UI (Make Links Brighter)
st.markdown("""
<style>
    /* Target the native Streamlit Multipage Navigation elements */
    [data-testid="stSidebarNav"] span {
        color: #e6edf3 !important;
        font-size: 1rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.5px !important;
    }
    
    /* Hover effect for native links */
    [data-testid="stSidebarNav"] a:hover span {
        color: #00F260 !important;
    }
    
    /* Section headers in native navigation */
    [data-testid="stSidebarNav"] div[data-testid="stSidebarNavSeparator"] + div span {
         color: #3d5a6e !important;
         font-family: 'JetBrains Mono', monospace !important;
         font-size: 0.70rem !important;
         letter-spacing: 3px !important;
         text-transform: uppercase !important;
    }
</style>
""", unsafe_allow_html=True)

# 4. Global Sidebar Header
st.sidebar.markdown("""
<div style="padding:12px 16px 10px;border-bottom:1px solid #1e3a5f;background:#080f1a;">
    <div style="font-family:'Rajdhani',sans-serif;font-size:1.3rem;font-weight:700;color:#e6edf3;letter-spacing:1.5px;">🦁 WEINSTEIN</div>
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;color:#3d5a6e;letter-spacing:3px;margin-top:2px;">COMMANDER MOBILE v1.0</div>
</div>
""", unsafe_allow_html=True)

# 5. Execute the selected page
pg.run()
