from bs4 import BeautifulSoup
import os

def check_file(file_path):
    print(f"\n--- {file_path} ---")
    with open(file_path, "r", encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    table = soup.find('table')
    if not table:
        print("No table found")
        return
        
    rows = table.find_all('tr')
    for r_idx, row in enumerate(rows[:5]):
        print(f"Row {r_idx}")
        cells = row.find_all(['td', 'th'])
        cell_data = []
        for c in cells:
            txt = c.get_text(strip=True)
            cls = c.get('class', [])
            # Also check if row has a specific color or indicator
            cell_data.append(f"{txt} (cls:{cls})")
        print(" | ".join(cell_data))
        
        # Check if row has a style or class that might indicate Buy/Sell
        row_cls = row.get('class', [])
        if row_cls: print(f"  Row classes: {row_cls}")

check_file("List of trades-2025-26.html")
check_file("Exchange Transactions.html")
