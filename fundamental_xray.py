import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import requests
from bs4 import BeautifulSoup
import os
import json
import time

st.set_page_config(
    page_title="Fundamental X-Ray",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ══════════════════════════════════════════════════════════════════════
#  CSS STYLING (Terminal Aesthetics)
# ══════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;700&family=Rajdhani:wght@500;600;700&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif;
    color: #c9d1d9;
    background-color: #010409 !important;
}
.stAppHeader {
    background-color: transparent !important;
    display: none !important;
}

/* Global Spacing Compress */
.block-container {
    padding-top: 1rem;
    padding-bottom: 0rem;
    max-width: 95%;
}

/* Headers */
.page-title {
    font-family: 'Rajdhani', sans-serif;
    font-size: 1.8rem; font-weight: 700; color: #e6edf3;
    letter-spacing: 1px; margin-bottom: 0px;
    border-bottom: 2px solid #1e3a5f; padding-bottom: 5px;
}
.page-desc {
    font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;
    color: #8b949e; margin-bottom: 5px; margin-top: 5px;
}
.section-hdr {
    font-family: 'Rajdhani', sans-serif;
    font-size: 0.95rem; font-weight: 600; color: #58a6ff;
    letter-spacing: 2px; text-transform: uppercase; margin: 10px 0 5px 0;
    border-bottom: 1px solid #1e3a5f; padding-bottom: 3px;
}

/* Metric Cards */
.metric-box {
    background: #0d1b2a; border: 1px solid #1e3a5f;
    border-radius: 4px; padding: 6px 10px; margin-bottom: 6px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
}
.metric-lbl {
    font-family: 'JetBrains Mono', monospace; font-size: 0.60rem;
    color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px;
    margin-bottom: 2px;
}
.metric-val {
    font-family: 'Inter', sans-serif; font-size: 1.05rem;
    font-weight: 600; color: #e6edf3; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap;
}
.metric-val-sub {
    font-size: 0.85rem; font-weight: 500;
}

/* Colors */
.c-good { color: #3fb950 !important; }
.c-warn { color: #d29922 !important; }
.c-bad  { color: #f85149 !important; }

/* Input Styling */
.stTextInput > div > div > input {
    background-color: #0a1628 !important;
    border: 1px solid #1e3a5f !important;
    color: #e6edf3 !important;
    caret-color: #e6edf3 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.95rem !important;
    font-weight: bold !important;
    text-transform: uppercase !important;
    padding: 6px 12px !important;
    min-height: 38px !important;
}
</style>
""", unsafe_allow_html=True)

t_col1, t_col2 = st.columns([2, 1])
with t_col1:
    st.markdown('<div class="page-title">🔎 FUNDAMENTAL X-RAY</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">High-Fidelity Automated Earnings & Valuation Audit via Screener.in</div>', unsafe_allow_html=True)
with t_col2:
    st.markdown('<div style="display:flex; justify-content:flex-end; gap: 10px; align-items:center; margin-top:20px;">', unsafe_allow_html=True)
    sync_tv = st.toggle("🔗 Sync TV", value=False, help="Automatically update when you click a stock in TradingView.")
    
    TICKER_FILE = os.path.join("data", "active_ticker.json")
    
    if sync_tv and os.path.exists(TICKER_FILE):
        try:
            with open(TICKER_FILE, 'r') as f:
                tv_data = json.load(f)
                active_sym = tv_data.get("active_symbol", "")
                if active_sym:
                    ticker_input = active_sym
                else:
                    ticker_input = ""
        except:
            ticker_input = ""
        # Render a disabled input to show it's locked
        st.text_input("TICKER", value=ticker_input, disabled=True, label_visibility="collapsed")
    else:
        ticker_input = st.text_input("TICKER", placeholder="e.g. RELIANCE", label_visibility="collapsed").strip()
    
    st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
#  HELPERS & DATA EXTRACTION
# ══════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=900)
def fetch_macro():
    macro = {}
    try: 
        t_nifty = yf.Ticker('^NSEI').history(period='5d')
        macro['Nifty'] = t_nifty['Close'].iloc[-1]
        macro['Nifty_pct'] = ((t_nifty['Close'].iloc[-1] - t_nifty['Close'].iloc[-2]) / t_nifty['Close'].iloc[-2]) * 100
    except: macro['Nifty'] = np.nan; macro['Nifty_pct'] = np.nan
    
    try: 
        t_usd = yf.Ticker('INR=X').history(period='5d')
        macro['USDINR'] = t_usd['Close'].iloc[-1]
        macro['USDINR_pct'] = ((t_usd['Close'].iloc[-1] - t_usd['Close'].iloc[-2]) / t_usd['Close'].iloc[-2]) * 100
    except: macro['USDINR'] = np.nan; macro['USDINR_pct'] = np.nan
    
    try:
        t_10y = yf.Ticker('GILT5YBEES.NS').history(period='5d')
        macro['IN10Y'] = t_10y['Close'].iloc[-1]
        macro['IN10Y_pct'] = ((t_10y['Close'].iloc[-1] - t_10y['Close'].iloc[-2]) / t_10y['Close'].iloc[-2]) * 100
    except Exception as e:
        macro['IN10Y'] = np.nan; macro['IN10Y_pct'] = np.nan
    
    try:
        t_cnx = yf.Ticker('^CRSLDX').history(period='5d')
        macro['CNX_val'] = t_cnx['Close'].iloc[-1]
        macro['CNX_pct'] = ((t_cnx['Close'].iloc[-1] - t_cnx['Close'].iloc[-2]) / t_cnx['Close'].iloc[-2]) * 100
    except: macro['CNX_val'] = np.nan; macro['CNX_pct'] = np.nan

    try:
        # Brent Crude
        t_oil = yf.Ticker('BZ=F').history(period='5d')
        macro['Oil'] = t_oil['Close'].iloc[-1]
        macro['Oil_pct'] = ((t_oil['Close'].iloc[-1] - t_oil['Close'].iloc[-2]) / t_oil['Close'].iloc[-2]) * 100
    except: macro['Oil'] = np.nan; macro['Oil_pct'] = np.nan
    
    try:
        # India VIX
        t_vix = yf.Ticker('^INDIAVIX').history(period='5d')
        macro['Vix'] = t_vix['Close'].iloc[-1]
        macro['Vix_pct'] = ((t_vix['Close'].iloc[-1] - t_vix['Close'].iloc[-2]) / t_vix['Close'].iloc[-2]) * 100
    except: macro['Vix'] = np.nan; macro['Vix_pct'] = np.nan

    return macro

from ai_risk_manager import get_market_health
@st.cache_data(ttl=3600)
def fetch_market_health():
    try:
        import data_provider as dp
        df_cnx = dp.fetch_ohlcv('^CRSLDX', period='6mo', interval='1d', use_cache=True, auto_adjust=True)
        if df_cnx is None or df_cnx.empty:
            return "Unknown"
        is_bullish, ma50, ma200 = get_market_health(df_cnx)
        return "BULLISH" if is_bullish else "BEARISH"
    except:
        return "Unknown"

macro_data = fetch_macro()
mkt_health = fetch_market_health()

def fmt_macro(val, pct=None, prefix="", suffix=""):
    if pd.isna(val) or val is None: return "N/A"
    base = f"{prefix}{val:.2f}{suffix}"
    if pct is not None and not pd.isna(pct):
        arrow = "▲" if pct > 0 else "▼"
        color = "#3fb950" if pct > 0 else "#f85149"
        # Standardize strictly: Green if positive, Red if negative
        base += f' <span style="color:{color}; font-size:0.75rem;">{arrow} {abs(pct):.2f}%</span>'
    return base

hdr_container = st.container()

with hdr_container:
    st.markdown(f"""
    <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 10px;">
        <div style="flex:1; background: rgba(88,166,255,0.05); border: 1px solid #1e3a5f; border-radius: 4px; padding: 6px 10px;">
            <div style="font-family: 'Rajdhani', sans-serif; font-size: 0.75rem; color: #58a6ff; border-bottom: 1px solid #1e3a5f; margin-bottom: 4px; letter-spacing: 1px;">MACRO (GLOBAL)</div>
            <div style="display: flex; gap: 15px; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #8b949e; flex-wrap: wrap;">
                <div><span style="color:#58a6ff;">OIL:</span> {fmt_macro(macro_data.get('Oil'), macro_data.get('Oil_pct'), prefix="$")}</div>
                <div><span style="color:#58a6ff;">USDINR:</span> {fmt_macro(macro_data.get('USDINR'), macro_data.get('USDINR_pct'), prefix="₹")}</div>
                <div><span style="color:#58a6ff;">IN10Y:</span> {fmt_macro(macro_data.get('IN10Y'), macro_data.get('IN10Y_pct'), prefix="₹")}</div>
            </div>
        </div>
        <div style="flex:1; background: rgba(88,166,255,0.05); border: 1px solid #1e3a5f; border-radius: 4px; padding: 6px 10px;">
            <div style="font-family: 'Rajdhani', sans-serif; font-size: 0.75rem; color: #58a6ff; border-bottom: 1px solid #1e3a5f; margin-bottom: 4px; letter-spacing: 1px;">MARKET (DOMESTIC)</div>
            <div style="display: flex; gap: 15px; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #8b949e; flex-wrap: wrap;">
                <div><span style="color:#58a6ff;">NIFTY:</span> {fmt_macro(macro_data.get('Nifty'), macro_data.get('Nifty_pct'))}</div>
                <div><span style="color:#58a6ff;">CNX500:</span> {fmt_macro(macro_data.get('CNX_val'), macro_data.get('CNX_pct'))} <span style="color:{'#3fb950' if mkt_health == 'BULLISH' else '#f85149'}; margin-left:3px; font-size:0.65rem; border:1px solid currentColor; padding:0 3px; border-radius:3px;">{mkt_health}</span></div>
                <div><span style="color:#58a6ff;">VIX:</span> {fmt_macro(macro_data.get('Vix'), macro_data.get('Vix_pct'))}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def fmt_money_inr(val):
    if pd.isna(val) or val is None: return "N/A"
    abs_val = abs(val)
    # Screener natively reports values in Crores (Cr)
    s, *d = str(int(abs_val)).partition(".")
    
    # Apply Indian comma grouping (e.g., 10,24,548 instead of 1,024,548)
    r = ",".join([s[x-2:x] for x in range(-3, -len(s), -2)][::-1] + [s[-3:]]) if len(s) > 3 else s
    
    # Include up to 2 decimal places if present
    decimals = f".{int((abs_val - int(abs_val)) * 100):02d}" if abs_val % 1 != 0 else ""
    
    return f"₹{'-' if val < 0 else ''}{r}{decimals} Cr"

def fmt_pct(val):
    if pd.isna(val) or val is None: return "N/A"
    return f"{val * 100:.1f}%"

def fmt_float(val, dec=2):
    if pd.isna(val) or val is None: return "N/A"
    return f"{val:.{dec}f}"

def clean_num(s):
    if not s: return np.nan
    s = str(s).replace(',', '').replace('%', '').replace('₹', '').replace('Cr.', '').strip()
    try: return float(s)
    except: return np.nan

@st.cache_data(ttl=3600)
def get_nifty_1m():
    try:
        t = yf.Ticker('^NSEI').history(period='1mo')
        return ((t['Close'].iloc[-1] - t['Close'].iloc[0]) / t['Close'].iloc[0]) * 100
    except: return np.nan

@st.cache_data(ttl=900)
def get_stock_1m(symbol):
    try:
        t = yf.Ticker(f"{symbol}.NS").history(period='1mo')
        return ((t['Close'].iloc[-1] - t['Close'].iloc[0]) / t['Close'].iloc[0]) * 100
    except: return np.nan

@st.cache_data(ttl=3600)
def get_sector_median(symbol):
    try:
        url = f'https://www.screener.in/company/{symbol}/consolidated/'
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if res.status_code == 404:
            url = f'https://www.screener.in/company/{symbol}/'
            res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        
        import re
        match = re.search(r'data-company-id="(\d+)"', res.text)
        if not match: return {}
        cid = match.group(1)
        
        peer_url = f'https://www.screener.in/api/company/{cid}/peers/'
        peer_res = requests.get(peer_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(peer_res.text, 'html.parser')
        
        headers = [th.text.strip() for th in soup.select('th')]
        
        for tr in soup.select('tr'):
            if 'Median' in tr.text:
                cells = [td.text.strip() for td in tr.select('td')]
                return dict(zip(headers[1:], cells[1:]))
        return {}
    except: return {}

@st.cache_data(ttl=3600)
def fetch_fundamentals(symbol):
    base_sym = symbol.upper()
    if base_sym.endswith(".NS") or base_sym.endswith(".BO"):
        base_sym = base_sym[:-3]

    # Quick ETF pre-check
    is_etf = False
    if ('ETF' in base_sym) or ('BEES' in base_sym) or ('INDEX' in base_sym):
        is_etf = True

    if is_etf:
        try:
            info = yf.Ticker(f"{base_sym}.NS").info
            return {
                'Symbol': base_sym,
                'Name': info.get('shortName', base_sym),
                'CurrentPrice': info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose', np.nan),
                'IsETF': True
            }
        except Exception as e:
            return {"error": f"Failed to fetch ETF data: {str(e)}"}

    try:
        url = f"https://www.screener.in/company/{base_sym}/consolidated/"
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-Dest': 'document'
        }
        res = session.get(url, headers=headers)
        if res.status_code == 404:
            url = f"https://www.screener.in/company/{base_sym}/"
            res = session.get(url, headers=headers)
        
        if res.status_code != 200:
            return {"error": f"Screener.in returned status {res.status_code} for {base_sym}"}

        soup = BeautifulSoup(res.text, 'html.parser')

        # Fallback for Banks where /consolidated/ returns 200 OK but the tables are empty shells
        pl_sec = soup.find('section', id='profit-loss')
        if pl_sec:
            pl_table = pl_sec.find('table')
            if pl_table:
                first_tr = pl_table.find('tbody').find('tr') if pl_table.find('tbody') else None
                if first_tr:
                    tds = first_tr.find_all('td')
                    if len(tds) <= 1:
                        # Table is empty, fallback to standalone URL
                        url = f"https://www.screener.in/company/{base_sym}/"
                        res = session.get(url, headers=headers)
                        if res.status_code == 200:
                            soup = BeautifulSoup(res.text, 'html.parser')
                        
        data = {
            'Symbol': f"{base_sym}.NS",
            'Name': soup.find('h1', class_='h2').text.strip() if soup.find('h1', class_='h2') else base_sym,
            'Sector': 'Equities', 
            'Industry': 'N/A',
            'IsETF': False
        }
        
        # Sector and Industry extraction
        for a in soup.find_all('a'):
            title = a.get('title', '')
            if title == 'Sector':
                data['Sector'] = a.text.strip()
            elif title == 'Industry':
                data['Industry'] = a.text.strip()

        top_ratios = {}
        for el in soup.select('div.company-ratios ul#top-ratios li'):
            name_el = el.find('span', class_='name')
            val_el = el.find('span', class_='number')
            if name_el and val_el:
                top_ratios[name_el.text.strip()] = clean_num(val_el.text)
        
        data['MarketCap'] = top_ratios.get('Market Cap', np.nan)
        data['CurrentPrice'] = top_ratios.get('Current Price', np.nan)
        data['TrailingPE'] = top_ratios.get('Stock P/E', np.nan)
        data['DividendYield'] = top_ratios.get('Dividend Yield', np.nan)
        data['ROE'] = top_ratios.get('ROE', np.nan)
        
        book_val = top_ratios.get('Book Value')
        if data['CurrentPrice'] and book_val and book_val != 0:
            data['PriceToBook'] = data['CurrentPrice'] / book_val
        else: data['PriceToBook'] = np.nan

        def get_table(section_id):
            sec = soup.find('section', id=section_id)
            if not sec: return {}
            
            table = sec.find('table')
            if not table: return {}
            
            tbody = table.find('tbody')
            if not tbody: return {}
            
            rows = {}
            trs = tbody.find_all('tr')
            
            for tr in trs:
                tds = tr.find_all('td')
                if not tds: continue
                
                row_name_btn = tds[0].find('button', class_='button-plain')
                if row_name_btn:
                    row_name = row_name_btn.text.replace('\xa0', '').replace('+', '').strip()
                else:
                    row_name = tds[0].text.replace('\xa0', '').replace('\n', '').replace('+', '').strip()
                
                import re
                row_name = re.sub(r'\s+', ' ', row_name).strip()
                
                vals = []
                for td in tds[1:]:
                    val_text = td.text.replace(',', '').replace('%', '').strip()
                    vals.append(clean_num(val_text))
                
                if vals: rows[row_name] = vals
            return rows

        q_rows = get_table('quarters')
        data['RevenueGrowth'] = np.nan
        data['EpsGrowth'] = np.nan
        sales_arr = q_rows.get('Sales', [])
        if sales_arr is None or len(sales_arr) == 0: sales_arr = q_rows.get('Revenue', [])
        if sales_arr and len(sales_arr) >= 5:
            curr = sales_arr[-1]; prev = sales_arr[-5]
            if curr and prev and prev != 0 and not np.isnan(curr) and not np.isnan(prev):
                data['RevenueGrowth'] = (curr - prev) / prev
                
        eps_arr = q_rows.get('EPS in Rs')
        data['EpsFQ'] = np.nan
        if eps_arr and len(eps_arr) > 0:
            data['EpsFQ'] = eps_arr[-1]
            
        if eps_arr and len(eps_arr) >= 5:
            curr_eps = eps_arr[-1]; prev_eps = eps_arr[-5]
            if curr_eps and prev_eps and prev_eps != 0 and not np.isnan(curr_eps) and not np.isnan(prev_eps):
                data['EpsGrowth'] = (curr_eps - prev_eps) / abs(prev_eps)
                
        np_arr = q_rows.get('Net Profit')
        data['NiGrowth'] = np.nan
        data['IsAccelerating'] = False
        
        if np_arr and len(np_arr) >= 5:
            curr_np = np_arr[-1]; prev_np = np_arr[-5]
            if curr_np and prev_np and prev_np != 0 and not np.isnan(curr_np) and not np.isnan(prev_np):
                data['NiGrowth'] = (curr_np - prev_np) / abs(prev_np)
                
        if np_arr and len(np_arr) >= 3:
            fq = np_arr[-1]; pq = np_arr[-2]; ppq = np_arr[-3]
            if pq and ppq and pq != 0 and ppq != 0 and not np.isnan(fq) and not np.isnan(pq) and not np.isnan(ppq):
                g1 = (fq - pq) / abs(pq)
                g2 = (pq - ppq) / abs(ppq)
                data['IsAccelerating'] = (g1 > g2) and (g1 > 0)

        pl_rows = get_table('profit-loss')
        
        data['RevenueTTM'] = np.nan
        data['NetIncomeTTM'] = np.nan
        data['OpMargin'] = np.nan
        data['EpsTTM'] = np.nan
        data['ProfitMargin'] = np.nan
        sales_pl = pl_rows.get('Sales', [])
        if sales_pl is None or len(sales_pl) == 0: sales_pl = pl_rows.get('Revenue', [])
        if sales_pl and len(sales_pl) > 0: data['RevenueTTM'] = sales_pl[-1]
            
        opm_pl = pl_rows.get('OPM %', [])
        if opm_pl is None or len(opm_pl) == 0:
            opm_pl = pl_rows.get('Financing Margin %', [])
        if opm_pl and len(opm_pl) > 0: data['OpMargin'] = opm_pl[-1] / 100 if not np.isnan(opm_pl[-1]) else np.nan
            
        eps_pl = pl_rows.get('EPS in Rs')
        if eps_pl and len(eps_pl) > 0: data['EpsTTM'] = eps_pl[-1]
            
        np_pl = pl_rows.get('Net Profit')
        if np_pl and len(np_pl) > 0: data['NetIncomeTTM'] = np_pl[-1]
        
        if np_pl and sales_pl and len(np_pl) > 0 and len(sales_pl) > 0 and sales_pl[-1]:
            data['ProfitMargin'] = np_pl[-1] / sales_pl[-1]

        # ── EBITDA MARGIN — from SCREENER, not yfinance (29-Jul-2026, Jay: "move all
        # fundamentals to screener.in unless there is a compelling reason").
        # Screener's P&L publishes OPM % = Operating Profit / Sales, which IS the
        # EBITDA margin for these statements. yfinance's `ebitdaMargins` is frequently
        # absent for NSE names, and a missing value was being scored as a FAILED check.
        # Reuses `opm_pl` above, which already carries the bank fallback
        # (OPM % -> Financing Margin %), so banks are handled the same way here.
        data['EbitdaMargin'] = np.nan
        try:
            if opm_pl and len(opm_pl) > 0 and opm_pl[-1] is not None and not np.isnan(opm_pl[-1]):
                data['EbitdaMargin'] = float(opm_pl[-1]) / 100.0
        except Exception:
            pass

        # ── The genuinely-unavailable fields stay on yfinance, and WHY is recorded so
        # nobody "fixes" this later without checking:
        #   CurrentRatio  — NOT on screener.in's public company page (documented in
        #                   fundamental_hub.fetch_screener_rff_row's docstring).
        #   GrossMargin   — screener's P&L gives Sales / Expenses / Operating Profit
        #                   but does not split COGS, so gross margin is not derivable.
        #                   (OPM is operating margin, a different thing — do not
        #                   substitute it here; it is already used for EbitdaMargin.)
        #   ROA / EpsFwd / EvToEbitda — broker/derived fields not on the public page.
        # These are the "compelling reason" exceptions. Everything else is screener.
        try:
            yf_info = yf.Ticker(f"{base_sym}.NS").info
            data['EpsFwd'] = yf_info.get('forwardEps', np.nan)
            data['EvToEbitda'] = yf_info.get('enterpriseToEbitda', np.nan)
            data['GrossMargin'] = yf_info.get('grossMargins', np.nan)
            data['ROA'] = yf_info.get('returnOnAssets', np.nan)
            data['CurrentRatio'] = yf_info.get('currentRatio', np.nan)
            if np.isnan(data['EbitdaMargin']):          # screener OPM missing → fall back
                data['EbitdaMargin'] = yf_info.get('ebitdaMargins', np.nan)
            fcf = yf_info.get('freeCashflow', np.nan)
            data['FreeCashFlow'] = (fcf / 10000000) if pd.notna(fcf) else np.nan
        except:
            data['EpsFwd'] = np.nan
            data['EvToEbitda'] = np.nan
            data['GrossMargin'] = np.nan
            data['ROA'] = np.nan
            data['CurrentRatio'] = np.nan
            data['FreeCashFlow'] = np.nan

        # ── FREE CASH FLOW — prefer SCREENER's cash-flow statement over yfinance.
        # FCF = Cash from Operating Activity - capex. Screener does not isolate capex,
        # so "Cash from Investing Activity" is used as its proxy (it is dominated by
        # capex for operating companies). Only overrides when screener actually
        # returned an operating-cash figure.
        try:
            _cf = get_table('cash-flow')
            _ocf = _cf.get('Cash from Operating Activity') or _cf.get('Cash from Operating Activity +')
            _inv = _cf.get('Cash from Investing Activity') or _cf.get('Cash from Investing Activity +')
            if _ocf and _ocf[-1] is not None and not np.isnan(_ocf[-1]):
                _capex = abs(_inv[-1]) if (_inv and _inv[-1] is not None and not np.isnan(_inv[-1])) else 0.0
                data['FreeCashFlow'] = float(_ocf[-1]) - _capex      # already ₹ Cr on screener
        except Exception:
            pass
        
        bs_rows = get_table('balance-sheet')
        data['DebtToEquity'] = np.nan
        borrowings = bs_rows.get('Borrowings')
        eq_cap = bs_rows.get('Equity Capital')
        reserves = bs_rows.get('Reserves')
        if borrowings and eq_cap and reserves:
            b = borrowings[-1]; eq = eq_cap[-1]; res = reserves[-1]
            if b is not None and eq is not None and res is not None and not np.isnan(b) and not np.isnan(eq) and not np.isnan(res):
                if (eq + res) != 0: data['DebtToEquity'] = (b / (eq + res)) * 100

        data['PegRatio'] = np.nan
        pe = data['TrailingPE']; eg = data['EpsGrowth']
        if pe and eg and not np.isnan(pe) and not np.isnan(eg) and eg > 0:
            data['PegRatio'] = pe / (eg * 100)

        # EV to EBITDA already handled natively via yfinance backfill
        
        inv_rows = get_table('shareholding')
        data['InsiderOwn'] = np.nan
        data['InstOwn'] = np.nan
        if inv_rows:
            promoters = inv_rows.get('Promoters', [np.nan])[-1]
            fii = inv_rows.get('FIIs', [np.nan])[-1]
            dii = inv_rows.get('DIIs', [np.nan])[-1]
            if promoters and not np.isnan(promoters): data['InsiderOwn'] = promoters / 100
            inst = 0
            if fii and not np.isnan(fii): inst += fii
            if dii and not np.isnan(dii): inst += dii
            data['InstOwn'] = inst / 100
            
        if not np.isnan(data['DividendYield']): data['DividendYield'] = data['DividendYield'] / 100
        if not np.isnan(data['ROE']): data['ROE'] = data['ROE'] / 100

        return data
    except Exception as e:
        return {"error": str(e)}

# ══════════════════════════════════════════════════════════════════════
#  UI LAYOUT
# ══════════════════════════════════════════════════════════════════════


def calculate_scores(data, mkt_health, macro_data):
    rg = data.get('RevenueGrowth')
    nig = data.get('NiGrowth')
    accel = data.get('IsAccelerating', False)
    roe = data.get('ROE')
    gm = data.get('GrossMargin')
    de = data.get('DebtToEquity')
    de_ratio = de / 100 if de is not None and not pd.isna(de) else None
    cr = data.get('CurrentRatio')
    fcf = data.get('FreeCashFlow')
    is_bank = "Bank" in data.get('Name', '') or "Bank" in data.get('Sector', '') or "Fin" in data.get('Sector', '')

    ms_rg = 1 if rg and rg >= 0.20 else 0
    ms_ni = 1 if nig and nig >= 0.25 else 0
    ms_accel = 1 if accel else 0
    ms_roe = 1 if roe and roe >= 0.15 else 0
    ms_gm = 1 if gm and gm >= 0.15 else 0
    ms_de = 1 if de_ratio is not None and de_ratio <= 1.5 else (1 if is_bank else 0)
    ms_cr = 1 if cr and cr >= 1.0 else (1 if is_bank else 0)
    ms_fcf = 1 if fcf and fcf > 0 else (1 if is_bank else 0)
    minervini_score = ms_rg + ms_ni + ms_accel + ms_roe + ms_gm + ms_de + ms_cr + ms_fcf
    
    ov_macro = 0
    if mkt_health == 'BULLISH': ov_macro += 1
    if macro_data.get('IN10Y_pct', 0) < 0: ov_macro += 1
    if macro_data.get('USDINR_pct', 0) < 0: ov_macro += 1
    
    ov_mom = 0
    ni = data.get('NetIncomeTTM')
    eg = data.get('EpsGrowth')
    if rg and rg >= 0.20: ov_mom += 1
    if nig and nig >= 0.25: ov_mom += 1
    if eg and eg >= 0.25: ov_mom += 1
    if accel: ov_mom += 1
    if ni and ni > 0: ov_mom += 1
    
    ov_mar = 0
    ebm = data.get('EbitdaMargin')
    opm = data.get('OpMargin')
    if gm and gm >= 0.30: ov_mar += 1
    if ebm and ebm >= 0.20: ov_mar += 1
    if opm and opm >= 0.15: ov_mar += 1
    if roe and roe >= 0.20: ov_mar += 1
    
    ov_hlth = 0
    pe = data.get('TrailingPE')
    pb = data.get('PriceToBook')
    if de_ratio is not None and de_ratio <= 1.0: ov_hlth += 1
    elif is_bank: ov_hlth += 1
    if cr and cr >= 1.5: ov_hlth += 1
    elif is_bank: ov_hlth += 1
    if fcf and fcf > 0: ov_hlth += 1
    elif is_bank: ov_hlth += 1
    if pe and 0 < pe <= 40: ov_hlth += 1
    if pb and 0 < pb <= 5.0: ov_hlth += 1
    
    # ── MISSING DATA MUST NOT SCORE AS A FAILURE (29-Jul-2026) ────────────────
    # Every check above is `if value and value >= threshold`, so a MISSING value
    # scores 0 — identical to a value that genuinely failed. That is the NaN->0
    # pattern this desk bans, and it was the real reason names sat at C/D: an NSE
    # stock missing 3-4 yfinance fields was being PENALISED for the gaps, not just
    # scored on what is known.
    #
    # Fix: count how many of the data-dependent checks were EVALUABLE, then scale
    # the earned score up to the full 17-point scale before grading. A name with 8
    # of 13 available checks now grades like 10.5/17 (B) instead of 8/17 (C).
    # The macro block (3 pts) is market-wide and always available, so it is added
    # back untouched rather than scaled.
    def _avail(v):
        return v is not None and not (isinstance(v, float) and np.isnan(v))

    _data_checks = [
        # (value, how many points in the raw scale depend on it)
        (rg, 1), (nig, 1), (data.get('EpsGrowth'), 1), (data.get('NetIncomeTTM'), 1),   # ov_mom (accel is derived, always evaluable)
        (gm, 1), (data.get('EbitdaMargin'), 1), (data.get('OpMargin'), 1), (roe, 1),    # ov_mar
        (de_ratio, 1), (cr, 1), (fcf, 1), (pe, 1), (pb, 1),                             # ov_hlth
    ]
    _avail_pts = sum(w for v, w in _data_checks if _avail(v)) + 1   # +1 = ov_mom's accel
    _max_data_pts = sum(w for _, w in _data_checks) + 1             # 14
    _earned_data = ov_mom + ov_mar + ov_hlth
    _coverage = (_avail_pts / _max_data_pts) if _max_data_pts else 1.0
    # Scale only when something is genuinely missing, and never inflate past the max.
    _scaled_data = (_earned_data / _avail_pts * _max_data_pts) if _avail_pts > 0 else 0.0
    _scaled_data = min(_scaled_data, float(_max_data_pts))
    overall_rating = int(round(ov_macro + _scaled_data))
    if overall_rating >= 15: grade, g_col = "A+", "#3fb950"
    elif overall_rating >= 13: grade, g_col = "A", "#3fb950"
    elif overall_rating >= 10: grade, g_col = "B", "#58a6ff"
    elif overall_rating >= 7: grade, g_col = "C", "#d29922"
    elif overall_rating >= 4: grade, g_col = "D", "#f85149"
    else: grade, g_col = "F", "#f85149"
    
    return {
        "minervini_score": minervini_score,
        "overall_rating": overall_rating,
        # Honesty fields (29-Jul-2026): a low grade from MISSING DATA and a low grade
        # from BAD FUNDAMENTALS are decision-different, and the UI could not tell them
        # apart. `data_coverage` is the share of data-dependent checks that were
        # evaluable; `overall_rating_raw` is the old un-scaled number for comparison.
        "data_coverage": round(_coverage, 3),
        "overall_rating_raw": int(ov_macro + _earned_data),
        "grade": grade,
        "g_col": g_col,
        "ov_macro": ov_macro,
        "ov_mom": ov_mom,
        "ov_mar": ov_mar,
        "ov_hlth": ov_hlth,
        "ms": {
            "rg": ms_rg, "ni": ms_ni, "accel": ms_accel, "roe": ms_roe, 
            "gm": ms_gm, "de": ms_de, "cr": ms_cr, "fcf": ms_fcf
        },
        "is_bank": is_bank,
        "de_ratio": de_ratio,
        "rg": rg, "nig": nig, "accel": accel, "roe": roe, "gm": gm, "cr": cr, "fcf": fcf, "pe": pe, "pb": pb, "ebm": ebm, "opm": opm, "ni": ni, "eg": eg
    }

tab_single, tab_batch = st.tabs(["X-Ray (Single Ticker)", "Screener (Batch / CSV)"])

with tab_single:
    if ticker_input:
        with st.spinner(f"Auditing fundamentals for {ticker_input}..."):
            data = fetch_fundamentals(ticker_input)
        
        if "error" in data:
            st.error(f"Failed to fetch data for {ticker_input}. Ensure it's a valid NSE listed symbol. Error: {data['error']}")
        elif data.get('IsETF', False):
            st.markdown(f"<div style='margin-bottom: 10px; font-size: 0.9rem; color: #8b949e;'>**{data['Name']}** (Exchange Traded Fund / Index) | **LTP:** ₹{data['CurrentPrice']}</div>", unsafe_allow_html=True)
            st.warning("Fundamental scorecards (Revenue, Margins, P/E) are mathematically invalid for Index Funds and ETFs. yFinance currently does not supply accurate Expense Ratios or AUM for NSE ETFs.")
        
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown('<div class="section-hdr">▶ ETF PRICING</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">Current Price</div><div class="metric-val">₹{fmt_float(data["CurrentPrice"])}</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown('<div class="section-hdr">▶ AUM / ASSETS</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">Total Assets</div><div class="metric-val" style="color:#8b949e; font-size:0.95rem;">N/A (yFinance)</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown('<div class="section-hdr">▶ METRICS</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">Expense Ratio & Yield</div><div class="metric-val" style="color:#8b949e; font-size:0.95rem;">N/A (yFinance)</div></div>', unsafe_allow_html=True)
            
            st.markdown(f"""
            <div style="background: #0d1b2a; border: 2px solid #1e3a5f; border-radius: 8px; padding: 12px; text-align: center; margin-top: 5px;">
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #8b949e; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 5px;">FUNDAMENTAL X-RAY</div>
                <div class="c-warn" style="font-family: 'Rajdhani', sans-serif; font-size: 1.8rem; font-weight: 700; line-height: 1;">ETF MODE</div>
                <div style="font-family: 'Inter', sans-serif; font-size: 0.8rem; color: #8b949e; margin-top: 5px;">Use Technical Analysis via TradingView for momentum scoring.</div>
            </div>
            """, unsafe_allow_html=True)

        else:
            # Emergency Screener Price Fallback if yfinance failed
            if pd.isna(data.get('CurrentPrice')):
                try:
                     url = f"https://www.screener.in/company/{ticker_input.upper().replace('.NS', '')}/"
                     res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
                     soup = BeautifulSoup(res.text, 'html.parser')
                     price_el = soup.find('span', text='Current Price').find_next('span', class_='number')
                     if price_el: data['CurrentPrice'] = float(price_el.text.replace(',', ''))
                except: pass
            
            st.markdown(f"<div style='margin-bottom: 10px; font-size: 0.9rem; color: #8b949e;'>**{data['Name']}** | **LTP:** ₹{data['CurrentPrice']}</div>", unsafe_allow_html=True)
        
            nifty_1m = get_nifty_1m()
            raw_sym = ticker_input.upper().replace('.NS', '').replace('.BO', '')
            stock_1m = get_stock_1m(raw_sym)
            rs_1m = stock_1m - nifty_1m if pd.notna(stock_1m) and pd.notna(nifty_1m) else np.nan
        
            sector_med = get_sector_median(raw_sym)
            s_pe = sector_med.get('P/E', 'N/A')
            s_roce = sector_med.get('ROCE\n                  %', 'N/A')
            s_div = sector_med.get('Div Yld\n                  %', 'N/A')
        
            def fmt_perf(pct):
                if pd.isna(pct) or pct is None: return "N/A"
                arrow = "▲" if pct > 0 else "▼"
                color = "#3fb950" if pct > 0 else "#f85149"
                return f'<span style="color:{color};">{arrow} {abs(pct):.2f}%</span>'

            def color_pe(val_str):
                if val_str == 'N/A': return '#c9d1d9'
                try:
                    v = float(val_str)
                    return "#3fb950" if v < 20 else ("#d29922" if v <= 30 else "#f85149")
                except: return '#c9d1d9'
            
            def color_roce(val_str):
                if val_str == 'N/A': return '#c9d1d9'
                try:
                    v = float(val_str)
                    return "#3fb950" if v >= 15 else ("#d29922" if v >= 10 else "#f85149")
                except: return '#c9d1d9'

            def color_div(val_str):
                if val_str == 'N/A': return '#c9d1d9'
                try:
                    v = float(val_str)
                    return "#3fb950" if v >= 2 else ("#d29922" if v > 0 else "#c9d1d9")
                except: return '#c9d1d9'
            
            c_pe = color_pe(s_pe)
            c_div = color_div(s_div)
            c_roce = color_roce(s_roce)

            st.markdown(f"""
            <div style="background: rgba(88,166,255,0.05); border: 1px solid #1e3a5f; border-radius: 4px; padding: 6px 10px; margin-bottom: 10px;">
                <div style="font-family: 'Rajdhani', sans-serif; font-size: 0.75rem; color: #58a6ff; border-bottom: 1px solid #1e3a5f; margin-bottom: 4px; letter-spacing: 1px;">SECTOR MEDIANS [{data.get('Sector', 'N/A')} / {data.get('Industry', 'N/A')}]</div>
                <div style="display: flex; gap: 15px; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #8b949e; flex-wrap: wrap;">
                    <div><span style="color:#58a6ff;">P/E:</span> <span style="color:{c_pe};">{s_pe}</span></div>
                    <div><span style="color:#58a6ff;">DIV YIELD:</span> <span style="color:{c_div};">{s_div}{'%' if s_div != 'N/A' else ''}</span></div>
                    <div><span style="color:#58a6ff;">ROCE:</span> <span style="color:{c_roce};">{s_roce}{'%' if s_roce != 'N/A' else ''}</span></div>
                    <div><span style="color:#58a6ff;">1M RETURN:</span> {fmt_perf(stock_1m)}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
            # --- SCORE CALCULATIONS ---
            sc = calculate_scores(data, mkt_health, macro_data)
            rg, nig, accel, roe, gm = sc['rg'], sc['nig'], sc['accel'], sc['roe'], sc['gm']
            de_ratio, cr, fcf, pe, pb = sc['de_ratio'], sc['cr'], sc['fcf'], sc['pe'], sc['pb']
            ebm, opm, ni, eg = sc['ebm'], sc['opm'], sc['ni'], sc['eg']
            is_bank = sc['is_bank']
            
            minervini_score = sc['minervini_score']
            overall_rating = sc['overall_rating']
            grade, g_col = sc['grade'], sc['g_col']
            ov_macro, ov_mom, ov_mar, ov_hlth = sc['ov_macro'], sc['ov_mom'], sc['ov_mar'], sc['ov_hlth']
            ms_rg, ms_gm, ms_ni, ms_de = sc['ms']['rg'], sc['ms']['gm'], sc['ms']['ni'], sc['ms']['de']
            ms_accel, ms_cr, ms_roe, ms_fcf = sc['ms']['accel'], sc['ms']['cr'], sc['ms']['roe'], sc['ms']['fcf']

            m_col1, m_col2, m_col3, m_col4 = st.columns([1, 1, 1, 1.3])
        
            # --- MOMENTUM ---
            with m_col1:
                st.markdown('<div class="section-hdr">▶ MOMENTUM & GROWTH</div>', unsafe_allow_html=True)
            
                mc = data.get('MarketCap')
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">Market Capitalization</div><div class="metric-val">{fmt_money_inr(mc)}</div></div>', unsafe_allow_html=True)
            
                rev = data.get('RevenueTTM')
                c_rg = "c-good" if rg and rg >= 0.20 else ("c-warn" if rg and rg > 0 else "c-bad")
                rg_str = fmt_pct(rg)
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">Total Rev (TTM) & YoY Growth</div><div class="metric-val"><div>{fmt_money_inr(rev)}</div> <div class="metric-val-sub {c_rg}">{rg_str}</div></div></div>', unsafe_allow_html=True)
            
                c_ni = "c-good" if ni and ni > 0 else "c-bad"
                ni_str = fmt_money_inr(ni)
                c_nig = "c-good" if nig and nig >= 0.25 else ("c-warn" if nig and nig > 0 else "c-bad")
                nig_str = fmt_pct(nig)
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">Net Income (TTM) & YoY Growth</div><div class="metric-val"><div class="{c_ni}">{ni_str}</div> <div class="metric-val-sub {c_nig}">{nig_str}</div></div></div>', unsafe_allow_html=True)
            
                eps_fq = data.get('EpsFQ')
                eps_fq_str = f"₹{fmt_float(eps_fq)}" if eps_fq is not None and not pd.isna(eps_fq) else "N/A"
                c_eg = "c-good" if eg and eg >= 0.25 else ("c-warn" if eg and eg > 0 else "c-bad")
                eg_str = fmt_pct(eg)
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">EPS (FQ) & YoY Growth</div><div class="metric-val"><div>{eps_fq_str}</div> <div class="metric-val-sub {c_eg}">{eg_str}</div></div></div>', unsafe_allow_html=True)
            
                c_accel = "c-good" if accel else "c-bad"
                accel_str = "Yes" if accel else "No"
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">Earnings Acceleration</div><div class="metric-val {c_accel}">{accel_str}</div></div>', unsafe_allow_html=True)
            
            # --- MARGINS ---
            with m_col2:
                st.markdown('<div class="section-hdr">▶ MARGINS (TTM/LATEST)</div>', unsafe_allow_html=True)
            
                c_gm = "c-good" if gm and gm >= 0.30 else ("c-warn" if gm and gm >= 0.15 else "c-bad")
                gm_str = fmt_pct(gm)
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">Gross Margin</div><div class="metric-val {c_gm}">{gm_str}</div></div>', unsafe_allow_html=True)
            
                c_ebm = "c-good" if ebm and ebm >= 0.20 else ("c-warn" if ebm and ebm > 0 else "c-bad")
                ebm_str = fmt_pct(ebm)
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">EBITDA Margin</div><div class="metric-val {c_ebm}">{ebm_str}</div></div>', unsafe_allow_html=True)
            
                c_opm = "c-good" if opm and opm >= 0.15 else ("c-warn" if opm and opm > 0 else "c-bad")
                opm_str = fmt_pct(opm)
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">Operating Margin</div><div class="metric-val {c_opm}">{opm_str}</div></div>', unsafe_allow_html=True)
            
                if pd.isna(roe) and is_bank:
                    st.markdown(f'<div class="metric-box"><div class="metric-lbl">Return on Equity (ROE)</div><div class="metric-val" style="color:#8b949e;">N/A (Bank)</div></div>', unsafe_allow_html=True)
                else:
                    c_roe = "c-good" if roe and roe >= 0.20 else ("c-warn" if roe and roe >= 0.15 else "c-bad")
                    roe_str = fmt_pct(roe)
                    st.markdown(f'<div class="metric-box"><div class="metric-lbl">Return on Equity (ROE)</div><div class="metric-val {c_roe}">{roe_str}</div></div>', unsafe_allow_html=True)
                
                roa = data.get('ROA')
                c_roa = "c-good" if roa and roa >= 0.05 else ("c-warn" if roa and roa > 0 else "c-bad")
                roa_str = fmt_pct(roa)
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">Return on Assets (ROA)</div><div class="metric-val {c_roa}">{roa_str}</div></div>', unsafe_allow_html=True)

            # --- HEALTH & VALUE ---
            with m_col3:
                st.markdown('<div class="section-hdr">▶ HEALTH & VALUE</div>', unsafe_allow_html=True)
            
                if pd.isna(de_ratio) and is_bank:
                    st.markdown(f'<div class="metric-box"><div class="metric-lbl">Debt to Equity</div><div class="metric-val" style="color:#8b949e;">N/A (Bank)</div></div>', unsafe_allow_html=True)
                else:
                    c_de = "c-good" if de_ratio and de_ratio <= 1.0 else ("c-warn" if de_ratio and de_ratio <= 1.5 else "c-bad")
                    de_str = f"{de_ratio:.2f}x" if de_ratio is not None else "N/A"
                    st.markdown(f'<div class="metric-box"><div class="metric-lbl">Debt to Equity</div><div class="metric-val {c_de}">{de_str}</div></div>', unsafe_allow_html=True)
                
                if pd.isna(cr) and is_bank:
                    st.markdown(f'<div class="metric-box"><div class="metric-lbl">Current Ratio</div><div class="metric-val" style="color:#8b949e;">N/A (Bank)</div></div>', unsafe_allow_html=True)
                else:
                    c_cr = "c-good" if cr and cr >= 1.5 else ("c-warn" if cr and cr >= 1.0 else "c-bad")
                    cr_str = f"{cr:.2f}x" if cr is not None and not pd.isna(cr) else "N/A"
                    st.markdown(f'<div class="metric-box"><div class="metric-lbl">Current Ratio</div><div class="metric-val {c_cr}">{cr_str}</div></div>', unsafe_allow_html=True)
                
                if pd.isna(fcf) and is_bank:
                    st.markdown(f'<div class="metric-box"><div class="metric-lbl">Free Cash Flow (TTM)</div><div class="metric-val" style="color:#8b949e;">N/A (Bank)</div></div>', unsafe_allow_html=True)
                else:
                    c_fcf = "c-good" if fcf and fcf > 0 else "c-bad"
                    fcf_str = fmt_money_inr(fcf)
                    st.markdown(f'<div class="metric-box"><div class="metric-lbl">Free Cash Flow (TTM)</div><div class="metric-val {c_fcf}">{fcf_str}</div></div>', unsafe_allow_html=True)
                
                c_pe = "c-good" if pe and 0 < pe <= 40 else ("c-warn" if pe and pe > 40 else "c-bad")
                if pe and pe < 0: c_pe = "c-bad"
                pe_str = fmt_float(pe) if pe and pe > 0 else "Loss" if pe else "N/A"
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">P/E Ratio (TTM)</div><div class="metric-val {c_pe}">{pe_str}</div></div>', unsafe_allow_html=True)
            
                c_pb = "c-good" if pb and 0 < pb <= 5.0 else ("c-warn" if pb and pb > 5.0 else "c-bad")
                pb_str = fmt_float(pb)
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">P/B Ratio</div><div class="metric-val {c_pb}">{pb_str}</div></div>', unsafe_allow_html=True)
            
            # --- SCORE & RATINGS ---
            with m_col4:
                st.markdown('<div class="section-hdr">▶ SCORING & RATING</div>', unsafe_allow_html=True)
            
                st.markdown(f"""
                <div style="background: #0d1b2a; border: 1px solid #1e3a5f; border-radius: 4px; padding: 10px; margin-bottom: 8px;">
                    <div style="font-family: 'Rajdhani', sans-serif; font-size: 0.95rem; color: #58a6ff; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 5px; border-bottom: 1px solid #1e3a5f; padding-bottom: 3px;">MINERVINI FUNDAMENTAL SCORE (0-8)</div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #8b949e;">Score</div>
                        <div style="font-family: 'Rajdhani', sans-serif; font-size: 1.8rem; font-weight: 700; color: {'#3fb950' if minervini_score >= 6 else ('#d29922' if minervini_score >= 4 else '#f85149')}; line-height: 1;">{minervini_score}/8</div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-family: 'Inter', sans-serif; font-size: 0.75rem; color: #c9d1d9;">
                        <div>{'✅' if ms_rg else '❌'} Rev Growth > 20%</div>
                        <div>{'✅' if ms_gm else '❌'} Gross Margin > 15%</div>
                        <div>{'✅' if ms_ni else '❌'} NI Growth > 25%</div>
                        <div>{'✅' if ms_de else '❌'} D/E < 1.5</div>
                        <div>{'✅' if ms_accel else '❌'} Accelerating EPS</div>
                        <div>{'✅' if ms_cr else '❌'} Curr Ratio > 1.0</div>
                        <div>{'✅' if ms_roe else '❌'} ROE > 15%</div>
                        <div>{'✅' if ms_fcf else '❌'} FCF Positive</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
                st.markdown(f"""
                <div style="background: #0d1b2a; border: 1px solid #1e3a5f; border-radius: 4px; padding: 10px; text-align: center; display: flex; flex-direction: column; justify-content: center;">
                    <div style="font-family: 'Rajdhani', sans-serif; font-size: 0.95rem; color: #58a6ff; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 5px;">OVERALL FUNDAMENTAL RATING</div>
                    <div style="font-family: 'Rajdhani', sans-serif; font-size: 2.5rem; font-weight: 700; color: {g_col}; line-height: 1.1;">{grade}</div>
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; color: #c9d1d9; margin-top: 2px;">{overall_rating} / 17 Points</div>
                    <div style="display: flex; justify-content: center; gap: 8px; font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #8b949e; margin-top: 8px; flex-wrap: wrap;">
                        <div>Macro: {ov_macro}/3</div>
                        <div>Momentum: {ov_mom}/5</div>
                        <div>Margins: {ov_mar}/4</div>
                        <div>Health/Value: {ov_hlth}/5</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)


with tab_batch:
    st.markdown("### 📂 BATCH SCREENER")
    st.markdown("<div style='color:#8b949e; font-size:0.85rem; margin-bottom:15px;'>Upload a CSV or TXT file containing a list of tickers (e.g., 'NSE:RELIANCE, HDFC'). Data will be batch processed. Note: Safe scraping rate limit applies (~0.5s per ticker).</div>", unsafe_allow_html=True)
    
    import re
    uploaded_file = st.file_uploader("Upload Ticker List (.csv, .txt)", type=["csv", "txt"])
    
    if uploaded_file is not None:
        try:
            file_name = uploaded_file.name.lower()
            tickers_raw = []
            
            if file_name.endswith('.csv'):
                try:
                    df_input = pd.read_csv(uploaded_file)
                    sym_col = next((c for c in df_input.columns if str(c).lower() in ['ticker', 'symbol', 'name']), None)
                    if sym_col:
                        tickers_raw = df_input[sym_col].dropna().astype(str).tolist()
                    else:
                        uploaded_file.seek(0)
                        content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
                        tickers_raw = re.split(r'[,\n\t]+', content)
                except:
                    uploaded_file.seek(0)
                    content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
                    tickers_raw = re.split(r'[,\n\t]+', content)
            else:
                content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
                tickers_raw = re.split(r'[,\n\t]+', content)
            
            tickers = []
            for tkr in tickers_raw:
                tkr = str(tkr).strip().upper()
                if not tkr: continue
                # Remove prefixes like NSE: and BSE:
                tkr = tkr.replace('NSE:', '').replace('BSE:', '').strip()
                # Ignore standard header names
                if tkr in ['TICKER', 'SYMBOL', 'NAME'] or len(tkr) < 2: continue
                # Only accept clean alphanumeric tickers with common symbols
                if re.match(r'^[A-Z0-9\-\&\.]+$', tkr):
                    if tkr not in tickers:
                        tickers.append(tkr)
            
            if not tickers:
                st.error("No valid tickers found in the file.")
            else:
                st.info(f"Loaded {len(tickers)} valid tickers {tickers[:5]}... Processing...")
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                results = []
                for i, tkr in enumerate(tickers):
                    status_text.text(f"Processing ({i+1}/{len(tickers)}): {tkr} / Fetching...")
                    
                    data = fetch_fundamentals(tkr)
                    if "error" in data or data.get('IsETF', False):
                        # skip or mark NA
                        time.sleep(0.3)
                    else:
                        sc = calculate_scores(data, mkt_health, macro_data)
                        results.append({
                            "Ticker": tkr.upper(),
                            "Name": data.get("Name", "N/A"),
                            "Rating": sc['grade'],
                            "Minervini Score (/8)": sc['minervini_score'],
                            "Overall (/17)": sc['overall_rating'],
                            "MarketCap (Cr)": data.get("MarketCap", 0),
                            "RevGrowth YoY": data.get("RevenueGrowth", 0),
                            "NIGrowth YoY": data.get("NiGrowth", 0),
                            "ROE": data.get("ROE", 0),
                            "Gross Margin": data.get("GrossMargin", 0),
                            "P/E": data.get("TrailingPE", 0)
                        })
                        time.sleep(0.5) # rate limit
                    
                    progress_bar.progress((i + 1) / len(tickers))
                
                status_text.text("Processing Complete.")
                
                if results:
                    df_res = pd.DataFrame(results)
                    # Format percentages
                    df_res["RevGrowth YoY"] = df_res["RevGrowth YoY"].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A")
                    df_res["NIGrowth YoY"] = df_res["NIGrowth YoY"].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A")
                    df_res["ROE"] = df_res["ROE"].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A")
                    df_res["Gross Margin"] = df_res["Gross Margin"].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A")
                    
                    # Sort primarily by Rating
                    grade_map = {"A+": 6, "A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
                    df_res['_rank'] = df_res['Rating'].map(grade_map)
                    df_res = df_res.sort_values(by=['_rank', 'Minervini Score (/8)', 'Overall (/17)'], ascending=[False, False, False]).drop(columns=['_rank'])
                    
                    st.dataframe(df_res, width="stretch")
                else:
                    st.warning("No valid data fetched for the provided tickers.")
        except Exception as e:
            st.error(f"Error processing CSV: {e}")

# Polling Logic if Sync is enabled
if st.session_state.get('sync_tv', False) or sync_tv:
    if 'last_xray_ticker' not in st.session_state:
        st.session_state.last_xray_ticker = ticker_input
        
    time.sleep(2.0)
    
    # Check if file changed
    current_file_ticker = ""
    if os.path.exists(TICKER_FILE):
        try:
            with open(TICKER_FILE, 'r') as f:
                tv_data = json.load(f)
                current_file_ticker = tv_data.get("active_symbol", "")
        except: pass
        
    if current_file_ticker and current_file_ticker != st.session_state.last_xray_ticker:
        st.session_state.last_xray_ticker = current_file_ticker
        st.rerun()
    else:
        st.rerun()
