import pandas as pd
import os

file_path = "pnl-report.xls"

print(f"Checking file: {file_path}")
if not os.path.exists(file_path):
    print("File not found!")
    exit()

try:
    # Try reading as standard Excel
    df = pd.read_excel(file_path)
    print("Read successfully as Excel.")
    print("-" * 30)
    # Read without header to scan
    df = pd.read_excel(file_path, header=None) 
    
    header_row = -1
    for i, row in df.iterrows():
        # Check if row contains key columns
        row_vals = row.astype(str).values
        if 'Security Name' in row_vals and 'Realised P&L' in row_vals:
            print(f"FOUND HEADER at Row {i}")
            header_row = i
            break
            
    if header_row != -1:
        # Re-read with correct header
        df = pd.read_excel(file_path, header=header_row)
        print("Columns:", df.columns.tolist())
        
        if 'Realised P&L' in df.columns:
            print("Realised P&L dtype:", df['Realised P&L'].dtype)
            print("First 10 values in 'Realised P&L':")
            print(df['Realised P&L'].head(10))
            
            # Check sum 
            # Remove any empty rows first
            df = df[df['Security Name'].notna()]
            
            try:
                 total = pd.to_numeric(df['Realised P&L'], errors='coerce').sum()
                 print(f"Calculated Sum (Numeric): {total}")
            except:
                 print("Could not calculate sum.")
        else:
            print("'Realised P&L' column NOT FOUND in re-read dataframe.")
    else:
        print("Could not find header row with 'Security Name' and 'Realised P&L'.")
        
    print("-" * 30)
except Exception as e:
    print(f"Failed as Excel: {e}")
    try:
        # Try reading as HTML (common for broker 'xls' downloads)
        dfs = pd.read_html(file_path)
        print(f"Read successfully as HTML. Found {len(dfs)} tables.")
        if len(dfs) > 0:
            print("First Table Preview:")
            print(dfs[0].head())
    except Exception as e2:
        print(f"Failed as HTML too: {e2}")
