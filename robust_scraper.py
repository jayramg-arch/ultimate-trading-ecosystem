import pandas as pd
import glob
import os
from bs4 import BeautifulSoup

def robust_scrape():
    print("🚀 Starting Robust Scraper...")
    
    # 1. Find all HTML files
    html_files = glob.glob("*.html")
    if not html_files:
        print("❌ No HTML files found! Please save Screener pages as .html files in this folder.")
        return

    master_data = []
    
    for filename in html_files:
        print(f"\n📂 Processing file: {filename}")
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')

            # 2. Find the CORRECT table
            # We look for a table that actually has "Name" in the headers
            target_table = None
            all_tables = soup.find_all('table')
            
            for t in all_tables:
                # Get all header text from this table
                headers = [th.text.strip() for th in t.find_all('th')]
                
                # Check if this looks like the stock list (Must have Name and CMP)
                if 'Name' in headers and any(x in headers for x in ['CMP', 'Price', 'P/E']):
                    target_table = t
                    final_headers = headers
                    print(f"   ✅ Found Stock Table with columns: {headers[:5]}...")
                    break
            
            if target_table is None:
                print("   ⚠️ Could not find a stock table in this file. Skipping.")
                continue

            # 3. Extract Rows
            rows = target_table.find_all('tr')
            # Skip the first row (headers)
            stock_rows = rows[1:]
            
            print(f"   📊 Found {len(stock_rows)} rows of data.")

            for tr in stock_rows:
                cols = tr.find_all('td')
                if not cols: 
                    continue
                
                # Extract text for all columns
                row_data = [td.text.strip() for td in cols]
                
                # --- SYMBOL EXTRACTION LOGIC ---
                # The Name is usually in the 2nd column (index 1) if there is a checkbox in index 0
                # Or index 0 if no checkbox. We check for the 'a' tag.
                
                extracted_symbol = "UNKNOWN"
                
                # Loop through cols to find the one with the link
                for col in cols:
                    anchor = col.find('a')
                    if anchor and 'href' in anchor.attrs:
                        href = anchor['href']
                        # check if it is a company link
                        if '/company/' in href:
                            # Link format: /company/RELIANCE/ or /company/RELIANCE/consolidated/
                            parts = href.split('/')
                            try:
                                # Find the part after 'company'
                                company_idx = parts.index('company')
                                extracted_symbol = parts[company_idx + 1]
                                break # Stop once found
                            except (ValueError, IndexError):
                                pass
                
                # Inject Symbol at the start or alongside Name
                # We will add a completely new column 'Symbol' to the data
                row_dict = {}
                
                # Map headers to data (handling potential length mismatch safely)
                for i, header in enumerate(final_headers):
                    if i < len(row_data):
                        row_dict[header] = row_data[i]
                
                row_dict['Symbol'] = extracted_symbol.upper()
                
                # Only add if we actually found a symbol or a valid name
                if row_dict.get('Name') or row_dict['Symbol'] != "UNKNOWN":
                    master_data.append(row_dict)

        except Exception as e:
            print(f"   ❌ Critical error reading {filename}: {e}")

    # 4. Save to CSV
    if master_data:
        df = pd.DataFrame(master_data)
        
        # Reorder columns to put Symbol first
        cols = ['Symbol'] + [c for c in df.columns if c != 'Symbol']
        df = df[cols]
        
        # Drop duplicates
        df.drop_duplicates(subset=['Symbol'], inplace=True)
        
        output_filename = 'MASTER_scan_results.csv'
        df.to_csv(output_filename, index=False)
        print("\n" + "="*50)
        print(f"🎉 SUCCESS! Extracted {len(df)} unique stocks.")
        print(f"💾 Saved to: {os.path.abspath(output_filename)}")
        print("="*50)
        print("First 5 extracted symbols:")
        print(df['Symbol'].head().tolist())
    else:
        print("\n❌ Failed to extract any data. Check if the HTML files are correct.")

if __name__ == "__main__":
    robust_scrape()