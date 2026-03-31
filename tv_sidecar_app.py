import streamlit as st
import os
import json
import time
from ai_sidecar_engine import generate_hedge_fund_brief

st.set_page_config(
    page_title="AI Sidecar | TradingView",
    page_icon="🤖",
    layout="wide"
)

# Configuration
DATA_DIR = "data"
TICKER_FILE = os.path.join(DATA_DIR, "active_ticker.json")

# Ensure CSS for clean look
st.markdown("""
<style>
    .report-box {
        background-color: #1E1E1E;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #00E676;
        margin-top: 10px;
        color: #E0E0E0;
    }
    .status-text {
        font-size: 0.9em;
        color: #888;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚡ AI TradingView Sidecar")
st.markdown("Instantly analyzes the active ticker from your TradingView tab.")

# Initialize session state for the ticker and report
if 'last_seen_ticker' not in st.session_state:
    st.session_state.last_seen_ticker = ""
if 'current_report' not in st.session_state:
    st.session_state.current_report = ""

def get_current_ticker():
    if os.path.exists(TICKER_FILE):
        try:
            with open(TICKER_FILE, 'r') as f:
                data = json.load(f)
                return data.get("active_symbol", "")
        except:
            return ""
    return ""

st.sidebar.markdown("### Sidecar Status")
st.sidebar.info("This UI automatically polls your local API. Whenever you change a symbol in Chrome, it will refresh here immediately.")

# --- Auto Refresh Logic ---
# Streamlit native auto-refresh using experimental fragment or loop
# We will use a standard loop with st.rerun() if they don't have streamline_autorefresh.
# For best compatibility without forcing pip installs, we use an empty container and sleep.

placeholder = st.empty()

# We need a small polling architecture that doesn't melt the CPU but is responsive
def poll_ticker():
    active_ticker = get_current_ticker()
    
    if active_ticker and active_ticker != st.session_state.last_seen_ticker:
        # Ticker has changed!
        st.session_state.last_seen_ticker = active_ticker
        
        with placeholder.container():
            st.info(f"🔄 Intercepted new ticker: **{active_ticker}**. Generating Hedge Fund Analysis...")
            
            # Call AI
            report = generate_hedge_fund_brief(active_ticker)
            st.session_state.current_report = report
            
            # Force a re-render to clear the spinner and show the report permanently
            st.rerun()
            
    else:
        # Render the current state
        with placeholder.container():
            if st.session_state.current_report:
                st.markdown(f"### Target: `{st.session_state.last_seen_ticker}`")
                st.markdown(f"<div class='report-box'>{st.session_state.current_report}</div>", unsafe_allow_html=True)
            else:
                st.warning("Awaiting ticker from TradingView Chrome Extension...")
                st.markdown("<p class='status-text'>Click any stock in TradingView to begin.</p>", unsafe_allow_html=True)

# Run polling once, then sleep, then rerun
poll_ticker()

# Adding a tiny delay to prevent stream loop crashing
time.sleep(2.0)
st.rerun()
