import pandas as pd
import os
import glob

def scrape_and_merge_pages(output_filename='MASTER_scan_results.csv'):
    """
    Finds ALL .html files in the current folder, scrapes the stock table 
    from each, and merges them into one master CSV.
    """
    # 1. Find all HTML files in the current directory
    html_files = glob.glob("*.html")
    
    if not html_files:
        print("❌ No HTML files found in this folder!")
        print("   -> Please save your Screener pages as .html files here first.")
        return

    print(f"📂 Found {len(html_files)} HTML files: {html_files}")
    
    all_data_frames = []

    # 2. Loop through each file
    for filename in html_files:
        try:
            print(f"   Processing {filename}...")
            tables = pd.read_html(filename, flavor='lxml')
            
            # Find the correct table (looking for 'Name' or 'CMP')
            target_table = None
            for table in tables:
                if 'Name' in table.columns or 'CMP' in table.columns:
                    target_table = table
                    break
            
            if target_table is not None:
                # Clean up "Unnamed" columns
                target_table = target_table.loc[:, ~target_table.columns.str.contains('^Unnamed')]
                all_data_frames.append(target_table)
            else:
                print(f"   ⚠️ Warning: No stock table found in {filename} (skipping).")

        except Exception as e:
            print(f"   ❌ Error reading {filename}: {e}")

    # 3. Merge and Save
    if all_data_frames:
        # Concatenate all tables into one
        master_df = pd.concat(all_data_frames, ignore_index=True)
        
        # Remove duplicates just in case (e.g., if you saved the same page twice)
        initial_count = len(master_df)
        master_df.drop_duplicates(inplace=True)
        final_count = len(master_df)

        if initial_count > final_count:
            print(f"   🧹 Removed {initial_count - final_count} duplicate rows.")

        # Save to CSV
        master_df.to_csv(output_filename, index=False)
        
        print("\n" + "="*40)
        print(f"✅ SUCCESS! Merged {len(html_files)} pages.")
        print(f"📊 Total Stocks Found: {len(master_df)}")
        print(f"jw💾 Saved as: {output_filename}")
        print("="*40)
    else:
        print("❌ No valid data extracted from any files.")

if __name__ == "__main__":
    scrape_and_merge_pages()