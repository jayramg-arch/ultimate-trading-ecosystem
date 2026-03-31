import pandas as pd
import glob
import os
from bs4 import BeautifulSoup

# --- SYMBOL CORRECTIONS ---
# Add any BSE codes here that need to be mapped to NSE Symbols
SYMBOL_MAP = {
    '506854': 'TANFAC',
    '543619': 'CONCORD',
}

def process_screener_pages():
    print("\n🚀 Starting " \
    " HTML Processor...")
    
    # 1. Find all HTML files
    html_files = glob.glob("*.html")
    if not html_files:
        print("❌ No .html files found! Please save your Screener pages as HTML first.")
        return False

    print(f"📂 Found {len(html_files)} pages to process.")
    master_data = []

    for filename in html_files:
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')

            # Find the stock table (looks for 'Name' in headers)
            target_table = None
            for t in soup.find_all('table'):
                headers = [th.text.strip() for th in t.find_all('th')]
                if 'Name' in headers:
                    target_table = t
                    final_headers = headers
                    break
            
            if not target_table: 
                continue

            # Extract Rows
            rows = target_table.find_all('tr')[1:] # Skip header
            for tr in rows:
                cols = tr.find_all('td')
                if not cols: continue
                
                row_data = [td.text.strip() for td in cols]
                
                # --- SYMBOL EXTRACTION ---
                extracted_symbol = "UNKNOWN"
                for col in cols:
                    anchor = col.find('a')
                    if anchor and 'href' in anchor.attrs and '/company/' in anchor['href']:
                        parts = anchor['href'].split('/')
                        try:
                            # Usually .../company/SYMBOL/...
                            extracted_symbol = parts[parts.index('company') + 1].upper()
                        except: pass
                
                # Fix Bad Symbols
                if extracted_symbol in SYMBOL_MAP:
                    extracted_symbol = SYMBOL_MAP[extracted_symbol]

                # Create Row Dict
                row_dict = {}
                for i, header in enumerate(final_headers):
                    if i < len(row_data):
                        row_dict[header] = row_data[i]
                row_dict['Symbol'] = extracted_symbol
                
                master_data.append(row_dict)

        except Exception as e:
            print(f"❌ Error reading {filename}: {e}")

    # Save to CSV
    if master_data:
        df = pd.DataFrame(master_data)
        
        # Ensure Symbol is the first column
        if 'Symbol' in df.columns:
            cols = ['Symbol'] + [c for c in df.columns if c != 'Symbol']
            df = df[cols]
            
        df.drop_duplicates(subset=['Symbol'], inplace=True)
        df.to_csv('MASTER_scan_results.csv', index=False)
        print(f"✅ Processed {len(df)} stocks -> MASTER_scan_results.csv")
        return True
    else:
        print("❌ No valid data found in HTML files.")
        return False

if __name__ == "__main__":
    process_screener_pages()
    input("\nPress Enter to exit...")