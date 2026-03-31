import pandas as pd
import os
import glob
from bs4 import BeautifulSoup

def smart_scrape_screener():
    # 1. Find all HTML files
    html_files = glob.glob("*.html")
    
    if not html_files:
        print("❌ No HTML files found! Save your Screener pages as .html first.")
        return

    print(f"📂 Found {len(html_files)} files. Extracting hidden Symbols...")
    
    master_data = []

    for filename in html_files:
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
                
            # Find the results table
            table = soup.find('table', {'class': 'data-table'})
            if not table:
                # Try finding any table if the specific class isn't there
                table = soup.find('table')
            
            if not table:
                print(f"   ⚠️ No table found in {filename}")
                continue
                
            # Get all rows
            rows = table.find_all('tr')
            
            # Extract Headers
            headers = [th.text.strip() for th in rows[0].find_all('th')]
            # We will manually add 'Symbol' to the headers
            if 'Symbol' not in headers:
                headers.insert(1, 'Symbol') # Insert after Name

            # Extract Data Rows
            for tr in rows[1:]:
                cols = tr.find_all('td')
                if not cols: 
                    continue
                
                row_data = [td.text.strip() for td in cols]
                
                # --- THE TRICK: EXTRACT SYMBOL FROM LINK ---
                # The first column usually contains the Name and the Link
                name_col = cols[0] 
                anchor = name_col.find('a')
                
                extracted_symbol = "UNKNOWN"
                if anchor and 'href' in anchor.attrs:
                    # Link looks like: /company/RELIANCE/consolidated/
                    link = anchor['href']
                    parts = link.split('/')
                    
                    # Usually the symbol is the 3rd part (index 2)
                    if len(parts) > 2:
                        extracted_symbol = parts[2]
                
                # Insert the extracted symbol into the row data to match headers
                row_data.insert(1, extracted_symbol)
                
                master_data.append(row_data)

            print(f"   ✅ Processed {filename} ({len(rows)-1} stocks)")

        except Exception as e:
            print(f"   ❌ Error reading {filename}: {e}")

    # 3. Create DataFrame and Save
    if master_data:
        df = pd.DataFrame(master_data, columns=headers)
        
        # Clean up: Remove duplicates
        df.drop_duplicates(subset=['Symbol'], inplace=True)
        
        output_file = 'MASTER_scan_results.csv'
        df.to_csv(output_file, index=False)
        
        print("\n" + "="*40)
        print(f"🎯 SUCCESS! Extracted {len(df)} stocks with Symbols.")
        print(f"📝 Sample: {df['Name'].iloc[0]} -> {df['Symbol'].iloc[0]}")
        print(f"jw💾 Saved to: {output_file}")
        print("="*40)
    else:
        print("❌ Failed to extract data.")

if __name__ == "__main__":
    smart_scrape_screener()