from bs4 import BeautifulSoup

def inspect_bs(file_path):
    print(f"\n--- {file_path} ---")
    with open(file_path, "r", encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    table = soup.find('table')
    if not table: return
    
    rows = table.find_all('tr')
    for i, row in enumerate(rows[1:5]):
        cells = row.find_all(['td', 'th'])
        if len(cells) > 2:
            print(f"Row {i+1} Cell 2 HTML: {str(cells[2])}")

inspect_bs("Exchange Transactions.html")
