import os
import quopri
from email import message_from_file
from bs4 import BeautifulSoup
import re

path = "Dhan Trade Journal-2025-26.mhtml"

def extract_all_info():
    if not os.path.exists(path):
        print(f"File {path} not found.")
        return
        
    with open(path, "r", encoding='utf-8', errors='ignore') as f:
        msg = message_from_file(f)
        
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload()
            if part.get("Content-Transfer-Encoding") == "quoted-printable":
                html_content = quopri.decodestring(payload).decode('utf-8', errors='ignore')
            else:
                html_content = payload
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all text and look for dates
            text_content = soup.get_text(separator=" ", strip=True)
            # Match formats like "26 Oct 2025" or "Oct 26, 2025"
            dates = re.findall(r'\d{1,2}\s+[A-Za-z]{3}\s+2025', text_content)
            print(f"Found {len(dates)} dates in 2025.")
            print(f"Unique dates: {sorted(list(set(dates)))}")
            
            # Print all rows that contain "SELL"
            rows = soup.find_all('tr')
            print(f"Total rows: {len(rows)}")
            for row in rows:
                row_text = row.get_text(separator=" ", strip=True)
                if any(m in row_text for m in ["Oct", "October", "Dec", "December"]):
                    print(f"TRADES ROW: {row_text}")

if __name__ == "__main__":
    extract_all_info()
