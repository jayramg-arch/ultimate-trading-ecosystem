from bs4 import BeautifulSoup
import pandas as pd
import os
import re

def parse_dhan_html_trades(file_path):
    if not os.path.exists(file_path):
        return pd.DataFrame()

    with open(file_path, "r", encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
        
    table = soup.find('table')
    if not table: return pd.DataFrame()
    
    parsed_trades = []
    rows = table.find_all('tr')
    
    for row in rows:
        cells = row.find_all('td')
        if len(cells) < 6: continue
        
        # 1. Date
        dt_str = cells[0].get_text(strip=True)
        
        # 2. Symbol and Transaction Type (Cell 1)
        sym_cell = cells[1]
        img = sym_cell.find('img')
        txn_type = "UNKNOWN"
        if img and img.get('src'):
            if 'buy.svg' in img.get('src'): txn_type = "BUY"
            elif 'sell.svg' in img.get('src'): txn_type = "SELL"
        
        # Symbol Name - usually inside a span or after a pipe
        # Or just clean the text
        sym_text = sym_cell.get_text(separator=" ", strip=True)
        # Often looks like "| Coal India NSE"
        # We can clean it
        sym_clean = sym_text.replace("|", "").replace("NSE", "").strip()
        
        # 3. Quantity (Cell 4)
        qty_str = cells[4].get_text(strip=True).replace(",", "")
        try:
            qty = float(qty_str)
        except:
            qty = 0
            
        # 4. Price (Cell 5)
        price_str = cells[5].get_text(strip=True).replace(",", "")
        try:
            # Price might have bold tags inside, get_text handles it
            price = float(price_str)
        except:
            price = 0.0
            
        parsed_trades.append({
            'Date': dt_str,
            'Symbol': sym_clean,
            'Type': txn_type,
            'Quantity': qty,
            'Price': price,
            'ExchangeTime': pd.to_datetime(dt_str) if dt_str else None
        })
        
    return pd.DataFrame(parsed_trades)

if __name__ == "__main__":
    df = parse_dhan_html_trades("List of trades-2025-26.html")
    print(df.head(20))
    print("\nSummary:")
    print(df['Type'].value_counts())
