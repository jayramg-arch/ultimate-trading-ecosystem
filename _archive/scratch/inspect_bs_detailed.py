from bs4 import BeautifulSoup

def inspect_bs(file_path):
    print(f"\n--- {file_path} ---")
    with open(file_path, "r", encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    table = soup.find('table')
    if not table: return
    
    rows = table.find_all('tr')
    for i, row in enumerate(rows[:10]):
        cells = row.find_all(['td', 'th'])
        if i == 0:
            print("Header:", [c.get_text(strip=True) for c in cells])
            continue
            
        if len(cells) > 2:
            bs_cell = cells[2] # B / S column
            bs_text = bs_cell.get_text(strip=True)
            bs_cls = bs_cell.get('class', [])
            # Also check children
            children = bs_cell.find_all(['span', 'div', 'i'])
            child_info = []
            for c in children:
                child_info.append(f"<{c.name} cls:{c.get('class')} txt:{c.get_text(strip=True)}>")
            
            print(f"Row {i}: Name={cells[1].get_text(strip=True)} | B/S='{bs_text}' | Cls={bs_cls} | Children={child_info}")

inspect_bs("Exchange Transactions.html")
