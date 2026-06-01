import re

file_path = 'master_portfolio_sync.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

inject_parse = '''    try:
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

inject_loop = '''        if pd.notna(row.get('Sector', '')): sec = str(row.get('Sector', '')).strip()

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
