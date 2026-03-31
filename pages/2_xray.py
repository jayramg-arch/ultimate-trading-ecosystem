import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import requests
from bs4 import BeautifulSoup

# Page config removed (handled by router)
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
    border-radius: 6px; padding: 8px 12px; margin-bottom: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
}
.metric-lbl {
    font-family: 'JetBrains Mono', monospace; font-size: 0.65rem;
    color: #8b949e; text-transform: uppercase; letter-spacing: 1px;
    margin-bottom: 2px;
}
.metric-val {
    font-family: 'Inter', sans-serif; font-size: 1.15rem;
    font-weight: 600; color: #e6edf3; display: flex; align-items: center; gap: 5px;
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

t_col1, t_col2 = st.columns([3, 1])
with t_col1:
    st.markdown('<div class="page-title">🔎 FUNDAMENTAL X-RAY</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">High-Fidelity Automated Earnings & Valuation Audit via Screener.in</div>', unsafe_allow_html=True)
with t_col2:
    ticker_input = st.text_input("TICKER", placeholder="e.g. FEDERALBNK, RELIANCE", label_visibility="collapsed").strip()


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
        df_cnx = yf.download('^CRSLDX', period='6mo', progress=False)
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
    <div style="font-family: 'Rajdhani', sans-serif; font-size: 0.9rem; color: #58a6ff; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 2px; border-bottom: 1px solid #1e3a5f; padding-bottom: 2px;">▶ MACRO-LEVEL (GLOBAL)</div>
    <div style="display: flex; gap: 20px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #8b949e; margin-bottom: 10px; padding: 6px 12px; background: rgba(88,166,255,0.05); border: 1px solid #1e3a5f; border-radius: 6px; flex-wrap: wrap;">
        <div><span style="color:#58a6ff; font-weight: bold;">BRENT CRUDE:</span> {fmt_macro(macro_data.get('Oil'), macro_data.get('Oil_pct'), prefix="$")}</div>
        <div><span style="color:#58a6ff; font-weight: bold;">USD/INR:</span> {fmt_macro(macro_data.get('USDINR'), macro_data.get('USDINR_pct'), prefix="₹")}</div>
        <div><span style="color:#58a6ff; font-weight: bold;">10Y G-SEC (IND):</span> {fmt_macro(macro_data.get('IN10Y'), macro_data.get('IN10Y_pct'), prefix="₹")}</div>
    </div>
    
    <div style="font-family: 'Rajdhani', sans-serif; font-size: 0.9rem; color: #58a6ff; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 2px; border-bottom: 1px solid #1e3a5f; padding-bottom: 2px;">▶ MARKET-LEVEL (DOMESTIC)</div>
    <div style="display: flex; gap: 20px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #8b949e; margin-bottom: 10px; padding: 6px 12px; background: rgba(88,166,255,0.05); border: 1px solid #1e3a5f; border-radius: 6px; flex-wrap: wrap;">
        <div><span style="color:#58a6ff; font-weight: bold;">NIFTY 50:</span> {fmt_macro(macro_data.get('Nifty'), macro_data.get('Nifty_pct'))}</div>
        <div><span style="color:#58a6ff; font-weight: bold;">CNX500:</span> {fmt_macro(macro_data.get('CNX_val'), macro_data.get('CNX_pct'))} <span style="margin-left:5px; color:{'#3fb950' if mkt_health == 'BULLISH' else '#f85149'}; border:1px solid currentColor; padding: 1px 4px; border-radius:3px; font-size:0.70rem;">{mkt_health}</span></div>
        <div><span style="color:#58a6ff; font-weight: bold;">INDIA VIX:</span> {fmt_macro(macro_data.get('Vix'), macro_data.get('Vix_pct'))}</div>
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
        if eps_arr and len(eps_arr) >= 5:
            curr_eps = eps_arr[-1]; prev_eps = eps_arr[-5]
            if curr_eps and prev_eps and prev_eps != 0 and not np.isnan(curr_eps) and not np.isnan(prev_eps):
                data['EpsGrowth'] = (curr_eps - prev_eps) / abs(prev_eps)

        pl_rows = get_table('profit-loss')
        
        data['RevenueTTM'] = np.nan
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
        if np_pl and sales_pl and len(np_pl) > 0 and len(sales_pl) > 0 and sales_pl[-1]:
            data['ProfitMargin'] = np_pl[-1] / sales_pl[-1]

        # Backfill Broker Estimates via yFinance (Screener omits Forward EPS & EV/EBITDA)
        try:
            yf_info = yf.Ticker(f"{base_sym}.NS").info
            data['EpsFwd'] = yf_info.get('forwardEps', np.nan)
            data['EvToEbitda'] = yf_info.get('enterpriseToEbitda', np.nan)
        except:
            data['EpsFwd'] = np.nan
            data['EvToEbitda'] = np.nan
        
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
        <div style="font-family: 'Rajdhani', sans-serif; font-size: 0.9rem; color: #58a6ff; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 2px; border-bottom: 1px solid #1e3a5f; padding-bottom: 2px;">▶ SECTOR-LEVEL (MEDIANS) [{data.get('Sector', 'N/A')} / {data.get('Industry', 'N/A')}]</div>
        <div style="display: flex; gap: 20px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #8b949e; margin-bottom: 15px; padding: 6px 12px; background: rgba(88,166,255,0.05); border: 1px solid #1e3a5f; border-radius: 6px; flex-wrap: wrap;">
            <div><span style="color:#58a6ff; font-weight: bold;">SECTOR P/E:</span> <span style="color:{c_pe}; font-weight: bold;">{s_pe}</span></div>
            <div><span style="color:#58a6ff; font-weight: bold;">SECTOR DIV YIELD:</span> <span style="color:{c_div}; font-weight: bold;">{s_div}{'%' if s_div != 'N/A' else ''}</span></div>
            <div><span style="color:#58a6ff; font-weight: bold;">SECTOR ROCE:</span> <span style="color:{c_roce}; font-weight: bold;">{s_roce}{'%' if s_roce != 'N/A' else ''}</span></div>
            <div><span style="color:#58a6ff; font-weight: bold;">STOCK 1M RETURN:</span> {fmt_perf(stock_1m)}</div>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        score = 0
        max_score = 0
        
        # --- QUADRANT A: GROWTH ---
        with c1:
            st.markdown('<div class="section-hdr">▶ MOMENTUM & GROWTH</div>', unsafe_allow_html=True)
            
            # Revenue TTM
            rev = data.get('RevenueTTM')
            st.markdown(f'<div class="metric-box"><div class="metric-lbl">Total Revenue (TTM)</div><div class="metric-val">{fmt_money_inr(rev)}</div></div>', unsafe_allow_html=True)

            # Rev Growth
            rg = data['RevenueGrowth']
            c_rg = "c-good" if rg and rg > 0.15 else ("c-warn" if rg and rg > 0 else "c-bad")
            if rg and rg > 0.15: score += 1
            if rg is not None and not pd.isna(rg): max_score += 1
            rg_str = fmt_pct(rg)
            st.markdown(f'<div class="metric-box"><div class="metric-lbl">YoY Quarterly Rev Growth</div><div class="metric-val {c_rg}">{rg_str}</div></div>', unsafe_allow_html=True)
            
            # EPS Growth
            eg = data['EpsGrowth']
            c_eg = "c-good" if eg and eg > 0.15 else ("c-warn" if eg and eg > 0 else "c-bad")
            if eg and eg > 0.15: score += 1
            if eg is not None and not pd.isna(eg): max_score += 1
            eg_str = fmt_pct(eg)
            st.markdown(f'<div class="metric-box"><div class="metric-lbl">YoY Quarterly EPS Growth</div><div class="metric-val {c_eg}">{eg_str}</div></div>', unsafe_allow_html=True)

            # TTM vs Fwd EPS Target
            eps = data['EpsTTM']
            fwd = data['EpsFwd']
            
            has_eps = eps is not None and pd.notna(eps)
            has_fwd = fwd is not None and pd.notna(fwd)
            
            c_eps = "c-good" if has_eps and has_fwd and fwd > eps else ("c-bad" if has_eps and has_fwd and fwd < eps else "c-warn")
            if has_eps and has_fwd and fwd > eps: score += 1
            if has_eps and has_fwd: max_score += 1
            
            eps_trend = "🟢 Projecting Growth" if has_eps and has_fwd and fwd > eps else ("🔴 Contraction" if has_eps and has_fwd and fwd < eps else "N/A (No Fwd Data)")
            st.markdown(f'<div class="metric-box"><div class="metric-lbl">EPS Trajectory (TTM → FWD)</div><div class="metric-val {c_eps}">₹{fmt_float(eps)} → ₹{fmt_float(fwd)}<br><span style="margin-top:5px; color:#8b949e;">{eps_trend}</span></div></div>', unsafe_allow_html=True)
            
        # --- QUADRANT B: PROFITABILITY ---
        with c2:
            st.markdown('<div class="section-hdr">▶ PROFITABILITY & EFFICIENCY</div>', unsafe_allow_html=True)
            
            # ROE
            roe = data['ROE']
            is_bank = "Bank" in data['Name'] or "Bank" in data['Sector'] or "Fin" in data['Sector']
            
            if pd.isna(roe) and is_bank:
                st.markdown(f'<div class="metric-box" title="Standard ROE equations strictly divide Net Income by Shareholder Equity. Banks use massive leverage (deposits) to generate income, skewing standard equity multipliers, so yFinance omits it."><div class="metric-lbl">Return on Equity (ROE)</div><div class="metric-val" style="color:#8b949e;">N/A (Financial Inst.)</div></div>', unsafe_allow_html=True)
            else:
                c_roe = "c-good" if roe and roe >= 0.15 else ("c-warn" if roe and roe >= 0.05 else "c-bad")
                if roe and roe >= 0.15: score += 1
                if roe is not None and not pd.isna(roe): max_score += 1
                roe_str = fmt_pct(roe)
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">Return on Equity (ROE)</div><div class="metric-val {c_roe}">{roe_str}</div></div>', unsafe_allow_html=True)
            
            # Operating Margin
            opm = data['OpMargin']
            c_opm = "c-good" if opm and opm >= 0.15 else ("c-warn" if opm and opm > 0 else "c-bad")
            if opm and opm >= 0.15: score += 1
            if opm is not None and not pd.isna(opm): max_score += 1
            opm_str = fmt_pct(opm)
            st.markdown(f'<div class="metric-box"><div class="metric-lbl">Operating Margin (OPM)</div><div class="metric-val {c_opm}">{opm_str}</div></div>', unsafe_allow_html=True)
            
            # Debt to Equity
            de = data['DebtToEquity']
            de_ratio = de / 100 if de is not None and not pd.isna(de) else None
            
            if pd.isna(de_ratio) and is_bank:
                st.markdown(f'<div class="metric-box" title="Banks inherently have massive Debt/Equity ratios because customer deposits are technically liabilities (debt). Standard D/E is meaningless for banks."><div class="metric-lbl">Debt to Equity</div><div class="metric-val" style="color:#8b949e;">N/A (Financial Inst.)</div></div>', unsafe_allow_html=True)
            else:
                c_de = "c-good" if de_ratio and de_ratio <= 1.0 else ("c-warn" if de_ratio and de_ratio <= 2.0 else "c-bad")
                if de_ratio and de_ratio <= 1.0: score += 1
                if de_ratio is not None and not pd.isna(de_ratio): max_score += 1
                de_str = f"{de_ratio:.2f}x" if de_ratio is not None else "N/A"
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">Debt to Equity</div><div class="metric-val {c_de}">{de_str}</div></div>', unsafe_allow_html=True)

        # --- QUADRANT C: VALUATION ---
        with c3:
            st.markdown('<div class="section-hdr">▶ VALUATION & HOLDINGS</div>', unsafe_allow_html=True)
            
            mc = data['MarketCap']
            st.markdown(f'<div class="metric-box"><div class="metric-lbl">Market Capitalization</div><div class="metric-val">{fmt_money_inr(mc)}</div></div>', unsafe_allow_html=True)
            
            pe = data['TrailingPE']
            c_pe = "c-good" if pe and 0 < pe <= 30 else ("c-warn" if pe and pe > 30 else "")
            if pe and pe < 0: c_pe = "c-bad"
            if pe and 0 < pe <= 30: score += 1
            if pe is not None and not pd.isna(pe) and pe > 0: max_score += 1
            pe_str = fmt_float(pe) if pe and pe > 0 else "Loss" if pe else "N/A"
            
            peg = data['PegRatio']
            peg_str = fmt_float(peg)
            c_peg = "c-good" if peg and 0 < peg <= 1.0 else ("c-warn" if peg and peg <= 2.0 else "c-bad")
            if peg and 0 < peg <= 1.5: score += 1
            if peg is not None and not pd.isna(peg): max_score += 1
            
            if pd.isna(peg) and is_bank:
                 st.markdown(f'<div class="metric-box" title="PEG relies on strict EPS growth forecasts which are highly regulated and opaque for Indian banking institutions."><div class="metric-lbl">P/E Ratio (TTM)</div><div class="metric-val {c_pe}">P/E: {pe_str} <span style="color:#8b949e; margin-left:10px;">| PEG: N/A (Bank)</span></div></div>', unsafe_allow_html=True)
            else:
                 st.markdown(f'<div class="metric-box"><div class="metric-lbl">P/E Ratio (TTM) & PEG</div><div class="metric-val {c_pe}">P/E: {pe_str} <span class="{c_peg}" style="margin-left:10px;">| PEG: {peg_str}</span></div></div>', unsafe_allow_html=True)
            
            pb = data['PriceToBook']
            ev = data['EvToEbitda']
            pb_str = fmt_float(pb)
            ev_str = fmt_float(ev)
            c_pb = "c-good" if pb and 0 < pb <= 3.0 else ("c-warn" if pb and pb <= 5.0 else "c-bad")
            if pb and 0 < pb <= 3.0: score += 1
            if pb is not None and not pd.isna(pb): max_score += 1
            
            c_ev = "c-good" if ev and 0 < ev <= 10.0 else ("c-warn" if ev and ev <= 15.0 else "c-bad")
            if ev and 0 < ev <= 10.0: score += 1
            if ev is not None and not pd.isna(ev): max_score += 1
            
            if pd.isna(ev) and is_bank:
                st.markdown(f'<div class="metric-box" title="EV/EBITDA is invalid for banks. Enterprise Value includes Debt. For banks, debt (deposits) is their raw material. EBITDA completely ignores Interest Expense, which is the primary operating cost for a bank."><div class="metric-lbl">P/B Ratio</div><div class="metric-val {c_pb}">P/B: {pb_str} <span style="color:#8b949e; margin-left:10px;">| EV/EBITDA: INVALID</span></div></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="metric-box"><div class="metric-lbl">P/B & EV/EBITDA</div><div class="metric-val {c_pb}">P/B: {pb_str} <span class="{c_ev}" style="margin-left:10px;">| EV/EBITDA: {ev_str}</span></div></div>', unsafe_allow_html=True)
            
            inst = data['InstOwn']
            ins = data['InsiderOwn']
            # yfinance info block does not natively return quarter-over-quarter change % for institutional ownership
            # We display the absolute holding % and color code based on minimum Minervini thresholds (>10%)
            c_inst = "c-good" if inst and inst >= 0.10 else "c-warn"
            c_ins = "c-good" if ins and ins >= 0.05 else "c-warn"
            if inst and inst >= 0.10: score += 1
            if inst is not None and not pd.isna(inst): max_score += 1
            inst_str = fmt_pct(inst)
            ins_str  = fmt_pct(ins)
            msg = "yFinance API currently does not expose QoQ % change for Institutional holdings directly."
            st.markdown(f'<div class="metric-box" title="{msg}"><div class="metric-lbl">Sponsorship (Absolute %)</div><div class="metric-val"><span class="{c_inst}">🏦 Inst: {inst_str}</span> <span class="{c_ins}" style="margin-left:10px;">| 👔 Insider: {ins_str}</span></div></div>', unsafe_allow_html=True)

        # --- SCORECARD ---
        final = 0
        if max_score > 0:
            final = (score / max_score) * 10
        c_fin = "c-good" if final >= 7 else ("c-warn" if final >= 4 else "c-bad")
        
        st.markdown(f"""
        <div style="background: #0d1b2a; border: 2px solid #1e3a5f; border-radius: 8px; padding: 10px; text-align: center; margin-top: 5px;">
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #8b949e; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 2px;">Aggregate Fundamental Score</div>
            <div class="{c_fin}" style="font-family: 'Rajdhani', sans-serif; font-size: 2.2rem; font-weight: 700; line-height: 1;">{final:.1f} <span style="font-size:1.0rem; color:#8b949e;">/ 10</span></div>
            <div style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: #8b949e; margin-top: 2px;">Score derived from {max_score} available Weinstein/Minervini target metrics.</div>
        </div>
        """, unsafe_allow_html=True)
