import os
import quopri
from email import message_from_file
from bs4 import BeautifulSoup
import re

def get_html_from_mhtml(path):
    if not os.path.exists(path): return ""
    with open(path, "r", encoding='utf-8', errors='ignore') as f:
        msg = message_from_file(f)
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload()
            if part.get("Content-Transfer-Encoding") == "quoted-printable":
                return quopri.decodestring(payload).decode('utf-8', errors='ignore')
            else:
                return payload
    return ""

def find_trades_in_content(content, source_name):
    print(f"\n--- Searching in: {source_name} ---")
    soup = BeautifulSoup(content, 'html.parser')
    
    # Try finding rows by searching for common patterns
    # Dhan Journal usually has "Cash Delivery" or "Buy" / "Sell" indicators
    trades = []
    
    # Method 1: All table rows
    for row in soup.find_all('tr'):
        text = row.get_text(separator=" ", strip=True)
        if any(m in text for m in ["2025", "2024"]):
            trades.append(text)
            
    # Method 2: If no table rows, try div-based rows (Dhan uses MDC tables sometimes which might be div-nested)
    if len(trades) < 5:
        for div in soup.find_all('div', class_=re.compile(r'row|item|cell|column', re.I)):
            text = div.get_text(separator=" ", strip=True)
            if any(m in text for m in ["2025", "2024"]) and ("Buy" in text or "Sell" in text):
                trades.append(text)

    # Print any trade that matches Oct or Dec 2025
    matches = 0
    for t in trades:
        # Looking for Oct 2025 or Dec 2025
        if ("Oct" in t or "October" in t or "Dec" in t or "December" in t) and "2025" in t:
            print(f"MATCH: {t}")
            matches += 1
            
    print(f"Total entries found in {source_name}: {len(trades)} (Oct/Dec Matches: {matches})")

def main():
    # 1. Check MHTML files
    for mhtml in ["Dhan Trade Journal-2024-25.mhtml", "Dhan Trade Journal-2025-26.mhtml"]:
        content = get_html_from_mhtml(mhtml)
        if content:
            find_trades_in_content(content, mhtml)
            
    # 2. Check the "saved_resource" files found earlier
    html_files = [
        "List of trades-2025-26_files/saved_resource.html",
        "Exchange Transactions_files/saved_resource.html",
        "Exchange Transactions_files/saved_resource(1).html",
        "Journal-2024-25_files/saved_resource.html"
    ]
    for h in html_files:
        if os.path.exists(h):
            with open(h, "r", encoding='utf-8', errors='ignore') as f:
                content = f.read()
            find_trades_in_content(content, h)

if __name__ == "__main__":
    main()
