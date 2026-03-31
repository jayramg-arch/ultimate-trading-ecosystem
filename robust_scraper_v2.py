import pandas as pd
import glob
import os
from bs4 import BeautifulSoup
import re

# --- 🛠️ USER CONFIGURATION: CORRECTION MAP 🛠️ ---
# Add any weird number codes here to convert them to proper NSE Symbols.
# Format: 'BAD_CODE': 'CORRECT_SYMBOL'
SYMBOL_CORRECTIONS = {
    '506854': 'TANFAC',      # Tanfac Industries
    '543619': 'CONCORD',     # Concord Control Systems
    '500000': 'EXAMPLE'      # (You can add more rows like this in future)
}
# ------------------------------------------------

def robust_scrape_v2():
    print("🚀 Starting Robust Scraper V2 (with Correction Map)...")
    
    html_files = glob.glob("*.html")
    if not html_files:
        print("❌ No HTML files found! Save Screener pages as .html files first.")
        return

    master_data = []
    
    for filename in html_files:
        print(f"\n📂 Processing: {filename}")
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')

            # 1. FIND THE STOCK TABLE
            target_table = None
            all_tables = soup.find_all('table')
            
            for t in all_tables:
                headers = [th.text.strip() for th in t.find_all('th')]
                if 'Name' in headers and any(x in headers for x in ['CMP', 'Price', 'P/E']):
                    target_table = t
                    final_headers = headers
                    break
            
            if target_table is None:
                print("   ⚠️ No stock table found. Skipping.")
                continue

            # 2. EXTRACT ROWS
            rows = target_table.find_all('tr')[1:] # Skip header
            
            for tr in rows:
                cols = tr.find_all('td')
                if not cols: continue
                
                row_data = [td.text.strip() for td in cols]
                
                # --- SYMBOL EXTRACTION ---
                extracted_symbol = "UNKNOWN"
                
                for col in cols:
                    anchor = col.find('a')
                    if anchor and 'href' in anchor.attrs:
                        href = anchor['href']
                        if '/company/' in href:
                            parts = href.split('/')
                            try:
                                company_idx = parts.index('company')
                                candidate = parts[company_idx + 1]
                                extracted_symbol = candidate.upper()
                                break
                            except: pass
                
                # --- 🔧 APPLY CORRECTIONS 🔧 ---
                # 1. Check the Manual Map first
                if extracted_symbol in SYMBOL_CORRECTIONS:
                    print(f"   🔧 Fixing: {extracted_symbol} -> {SYMBOL_CORRECTIONS[extracted_symbol]}")
                    extracted_symbol = SYMBOL_CORRECTIONS[extracted_symbol]
                
                # 2. Warn if it's still a number (BSE Code)
                elif re.match(r'^\d+$', extracted_symbol):
                    print(f"   ⚠️ WARNING: Symbol is a number (BSE Code?): {extracted_symbol} ({row_data[1] if len(row_data)>1 else 'Unknown Name'})")

                # --- BUILD ROW ---
                row_dict = {}
                for i, header in enumerate(final_headers):
                    if i < len(row_data):
                        row_dict[header] = row_data[i]
                
                row_dict['Symbol'] = extracted_symbol
                
                if row_dict.get('Name') or row_dict['Symbol'] != "UNKNOWN":
                    master_data.append(row_dict)

        except Exception as e:
            print(f"   ❌ Error: {e}")

    # 3. SAVE TO CSV
    if master_data:
        df = pd.DataFrame(master_data)
        
        # Ensure Symbol is the first column
        cols = ['Symbol'] + [c for c in df.columns if c != 'Symbol']
        df = df[cols]
        
        df.drop_duplicates(subset=['Symbol'], inplace=True)
        
        output_filename = 'MASTER_scan_results.csv'
        df.to_csv(output_filename, index=False)
        print("\n" + "="*50)
        print(f"✅ DONE! Processed {len(df)} stocks.")
        print(f"💾 Saved to: {output_filename}")
        print("="*50)
    else:
        print("❌ No data found.")

if __name__ == "__main__":
    robust_scrape_v2()