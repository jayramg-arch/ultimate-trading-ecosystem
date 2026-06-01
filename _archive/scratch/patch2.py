import re

file_path = 'master_portfolio_sync.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix PINE PATH
content = re.sub(r'PINE_PATH = ".*?"', 'PINE_PATH = "Weinstein and Swing Pro Dashboard v64.0.pine"', content)

# Step 1: tv_data dict update
content = content.replace("tv_data[t] = {'SL': sl, 'Sector': sec}", "tv_data[t] = {'SL': sl, 'Sector': sec, 'Date': row.get('Date', '')}")

# Step 2: manual_data dict update
content = content.replace("'Sector': row.get('Sector', DEFAULT_SECTOR)", "'Sector': row.get('Sector', DEFAULT_SECTOR), 'Date': str(row.get('Date', ''))")

# Step 4: Add final_date
content = content.replace("final_sec = DEFAULT_SECTOR", "final_sec = DEFAULT_SECTOR\n        final_date = 0")

content = content.replace("final_sec = tv_data[norm_sym]['Sector']", "final_sec = tv_data[norm_sym]['Sector']\n            if 'Date' in tv_data[norm_sym] and tv_data[norm_sym]['Date'] and str(tv_data[norm_sym]['Date']).lower() != 'nan':\n                final_date = tv_data[norm_sym]['Date']")

content = content.replace("final_sec = existing_manual_data[norm_sym]['Sector']", "final_sec = existing_manual_data[norm_sym]['Sector']\n            if 'Date' in existing_manual_data[norm_sym] and existing_manual_data[norm_sym]['Date'] and str(existing_manual_data[norm_sym]['Date']).lower() != 'nan':\n                final_date = existing_manual_data[norm_sym]['Date']")

content = content.replace("'Sector': final_sec", "'Sector': final_sec, 'Date': final_date")

content = content.replace("columns=['Slot', 'Ticker', 'Entry', 'Qty', 'SL', 'Sector']", "columns=['Slot', 'Ticker', 'Entry', 'Qty', 'SL', 'Date', 'Sector']")

inject_parse = r'''    try:
        with open(PINE_PATH, "r", encoding="utf-8") as f:
            pine_content = f.read()
    except Exception as e:
        print(f"Error reading {PINE_PATH}: {e}")
        return

    import re
    existing_dates = {}
    for match in re.finditer(r'p\d+_tick\s*=\s*input\.string\("([^"]+)"[\s\S]*?p\d+_date\s*=\s*input\.time\(([^,]+)', pine_content):
        t = normalize_ticker(match.group(1).strip())
        d = match.group(2).strip()
        if t: existing_dates[t] = d

    # Generate Pine Code'''

content = content.replace('# Generate Pine Code', inject_parse)

inject_loop = r'''        if pd.notna(row['Sector']): sec = str(row['Sector']).strip()

        tick_norm = normalize_ticker(tick)
        date_val = "0"
        if tick_norm in existing_dates:
            date_val = existing_dates[tick_norm]
            
        if 'Date' in row and pd.notna(row['Date']) and str(row['Date']).strip() and str(row['Date']).lower() != 'nan':
            try:
                dt_obj = datetime.strptime(str(row['Date']).strip(), "%Y-%m-%d")
                date_val = str(int(dt_obj.timestamp() * 1000))
            except: pass'''

content = re.sub(r'if pd\.notna\(row\[\'Sector\'\]\): sec = str\(row\[\'Sector\'\]\)\.strip\(\)', inject_loop, content)

content = re.sub(r'lines\.append\(f\'p\{i\}_date = input\.time\(0, title="Date"', r'lines.append(f\'p{i}_date = input.time({date_val}, title="Date"', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch successful!")
