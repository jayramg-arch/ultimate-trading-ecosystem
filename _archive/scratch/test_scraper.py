import requests
from bs4 import BeautifulSoup
import re
import numpy as np

def clean_num(s):
    if not s: return np.nan
    s = s.replace(',', '').replace('%', '').replace('₹', '').replace('Cr.', '').strip()
    try:
        return float(s)
    except:
        return np.nan

def fetch_screener(symbol):
    url = f"https://www.screener.in/company/{symbol}/consolidated/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    res = requests.get(url, headers=headers)
    if res.status_code == 404:
        url = f"https://www.screener.in/company/{symbol}/"
        res = requests.get(url, headers=headers)
    
    if res.status_code != 200:
        return {"error": "Failed to fetch from Screener.in"}

    soup = BeautifulSoup(res.text, 'html.parser')

    data = {
        'Symbol': symbol,
        'Name': soup.find('h1', class_='h2').text.strip() if soup.find('h1', class_='h2') else symbol,
        'Sector': 'Equities', # Screener shows sector further down in peer comparison or at top
        'Industry': 'N/A'
    }
    
    # Extract sector/industry if available
    for p in soup.find_all('p'):
        if 'Sector:' in p.text:
            try:
                data['Sector'] = p.find_all('a')[0].text.strip()
                data['Industry'] = p.find_all('a')[1].text.strip()
            except: pass

    # 1. Top Ratios
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
    else:
        data['PriceToBook'] = np.nan

    # Helper for tables
    def get_table(section_id):
        sec = soup.find('section', id=section_id)
        if not sec: return {}
        table = sec.find('table')
        if not table: return {}
        rows = {}
        for tr in table.find('tbody').find_all('tr'):
            cols = [td.text.replace('\xa0+', '').replace('\n', '').strip() for td in tr.find_all('td')]
            if cols:
                # clean row name
                row_name = cols[0].replace('+', '').strip()
                rows[row_name] = [clean_num(c) for c in cols[1:]]
        return rows

    # 2. Quarters Table
    q_rows = get_table('quarters')
    data['RevenueGrowth'] = np.nan
    data['EpsGrowth'] = np.nan
    
    # Revenue (Sales or Interest for banks)
    sales_arr = q_rows.get('Sales') or q_rows.get('Revenue')
    if sales_arr and len(sales_arr) >= 5:
        curr = sales_arr[-1]
        prev = sales_arr[-5]
        if curr and prev and prev != 0 and not np.isnan(curr) and not np.isnan(prev):
            data['RevenueGrowth'] = (curr - prev) / prev
            
    eps_arr = q_rows.get('EPS in Rs')
    if eps_arr and len(eps_arr) >= 5:
        curr_eps = eps_arr[-1]
        prev_eps = eps_arr[-5]
        if curr_eps and prev_eps and prev_eps != 0 and not np.isnan(curr_eps) and not np.isnan(prev_eps):
            # If prev_eps < 0 but current is > 0, growth is mathematically odd, but we'll use standard
            data['EpsGrowth'] = (curr_eps - prev_eps) / abs(prev_eps)

    # 3. P&L Table (TTM)
    pl_rows = get_table('profit-loss')
    data['RevenueTTM'] = np.nan
    data['OpMargin'] = np.nan
    data['EpsTTM'] = np.nan
    data['ProfitMargin'] = np.nan
    
    sales_pl = pl_rows.get('Sales') or pl_rows.get('Revenue')
    if sales_pl and len(sales_pl) > 0:
        data['RevenueTTM'] = sales_pl[-1]
        
    opm_pl = pl_rows.get('OPM %') or pl_rows.get('Financing Margin %')
    if opm_pl and len(opm_pl) > 0:
        data['OpMargin'] = opm_pl[-1] / 100 if not np.isnan(opm_pl[-1]) else np.nan
        
    eps_pl = pl_rows.get('EPS in Rs')
    if eps_pl and len(eps_pl) > 0:
        data['EpsTTM'] = eps_pl[-1]
        
    np_pl = pl_rows.get('Net Profit')
    if np_pl and sales_pl and len(np_pl) > 0 and len(sales_pl) > 0:
        if sales_pl[-1] and sales_pl[-1] != 0:
            data['ProfitMargin'] = np_pl[-1] / sales_pl[-1]

    # No Forward EPS on Screener
    data['EpsFwd'] = np.nan

    # 4. Balance Sheet
    bs_rows = get_table('balance-sheet')
    data['DebtToEquity'] = np.nan
    borrowings = bs_rows.get('Borrowings')
    eq_cap = bs_rows.get('Equity Capital')
    reserves = bs_rows.get('Reserves')
    
    if borrowings and eq_cap and reserves:
        b = borrowings[-1]
        eq = eq_cap[-1]
        res = reserves[-1]
        if b is not None and eq is not None and res is not None:
            if not np.isnan(b) and not np.isnan(eq) and not np.isnan(res):
                tot_eq = eq + res
                if tot_eq != 0:
                    data['DebtToEquity'] = b / tot_eq

    # PEG Ratio
    data['PegRatio'] = np.nan
    pe = data['TrailingPE']
    eg = data['EpsGrowth']
    if pe and eg and not np.isnan(pe) and not np.isnan(eg) and eg > 0:
        data['PegRatio'] = pe / (eg * 100) # eg is decimal, PEG expects eg in % 

    # EV to EBITDA
    data['EvToEbitda'] = np.nan
    # EV = Market Cap + Debt - Cash
    # EBITDA = Op Profit
    
    # 5. Shareholding Pattern
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
        
    # Standardize Debt ratio for compatibility with UI
    # Currently UI checks `de / 100` if yF returned %.
    # We parsed a raw ratio, so let's multiply by 100 so the UI logic works without huge changes, 
    # OR change the UI. The UI currently does `de_ratio = de / 100`. So we multiply by 100 here.
    if data['DebtToEquity'] is not None and not np.isnan(data['DebtToEquity']):
        data['DebtToEquity'] = data['DebtToEquity'] * 100
        
    # Same for Dividend Yield, yf gives raw decimal (0.01 for 1%). Screener gives 1.0. 
    # UI uses `fmt_pct()` which expects decimal. Wait, the existing `fetch_fundamentals` ...
    # Wait, yf DividendYield is 0.015 for 1.5%. Screener is 1.50. So we need to divide screener DivY by 100
    if not np.isnan(data['DividendYield']):
        data['DividendYield'] = data['DividendYield'] / 100
        
    # ROE Screener is 15.5 for 15.5%. UI expects 0.155.
    if not np.isnan(data['ROE']):
        data['ROE'] = data['ROE'] / 100

    return data

if __name__ == '__main__':
    for sym in ['FEDERALBNK', 'RELIANCE', 'TCS']:
        res = fetch_screener(sym)
        print(f"\n--- {sym} ---")
        for k, v in res.items():
            print(f"{k}: {v}")
