from bs4 import BeautifulSoup

def find_keywords(file_path):
    print(f"\n--- Searching {file_path} ---")
    with open(file_path, "r", encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    # Find any tag containing "Buy" or "Sell"
    for word in ["Buy", "Sell", "BUY", "SELL"]:
        found = soup.find_all(string=lambda t: word in t)
        if found:
            print(f"Found '{word}': {len(found)} times")
            for item in found[:3]:
                parent = item.parent
                print(f"  Parent Tag: {parent.name}, Classes: {parent.get('class')}, Text: {item.strip()}")

find_keywords("List of trades-2025-26.html")
find_keywords("Exchange Transactions.html")
