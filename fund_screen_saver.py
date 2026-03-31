import pandas as pd
import os

def scrape_local_screener_file(filename='screener_results.html', output_filename='stage2_targets.csv'):
    """
    Parses a locally saved Screener.in HTML page and saves the main table to CSV.
    """
    print(f"📂 Reading file: {filename}...")
    
    if not os.path.exists(filename):
        print(f"❌ Error: The file '{filename}' was not found in this folder.")
        print("   -> Please go to Screener.in, press Ctrl+S, and save the page as 'screener_results.html'.")
        return

    try:
        # Pandas read_html automatically finds tables in the HTML file
        # flavor='lxml' is faster, but 'bs4' is more forgiving if lxml fails
        tables = pd.read_html(filename, flavor='lxml')
        
        # Screener usually puts the main data in the first large table found
        # We look for the table that contains "Name" or "CMP" to be sure
        target_table = None
        for table in tables:
            # Check if likely headers exist in the table columns
            if 'Name' in table.columns or 'CMP' in table.columns:
                target_table = table
                break
        
        if target_table is not None:
            # CLEANUP: Remove "junk" columns often caught by scrapers (like checkboxes or empty cols)
            # Drop columns that are unnamed (usually the checkbox column)
            target_table = target_table.loc[:, ~target_table.columns.str.contains('^Unnamed')]
            
            # Save to CSV
            target_table.to_csv(output_filename, index=False)
            print(f"✅ Success! Extracted {len(target_table)} stocks.")
            print(f"📊 Saved to: {os.path.abspath(output_filename)}")
            
            # Optional: Preview the top 5 rows
            print("\nPreview:")
            print(target_table.head())
            
        else:
            print("⚠️ No valid stock table found in the HTML file.")

    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    # You can change the filename below if you saved it with a different name
    scrape_local_screener_file('screener_results.html', 'stage2_targets.csv')