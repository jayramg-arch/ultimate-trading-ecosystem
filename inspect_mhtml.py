import os
import quopri
from email import message_from_file
from bs4 import BeautifulSoup

files = ["Dhan Trade Journal-2024-25.mhtml", "Dhan Trade Journal-2025-26.mhtml"]

def inspect_mhtml():
    for path in files:
        if not os.path.exists(path): continue
            
        print(f"\n--- Inspecting {path} ---")
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
                rows = soup.find_all('tr')
                print(f"Total rows found in {path}: {len(rows)}")
                
                # Check for 2025 or specific months in text
                count = 0
                for row in rows:
                    text = row.get_text(separator=" ", strip=True)
                    if "2025" in text:
                        if count < 10: # Sample first few
                            print(f"Row Match: {text[:200]}")
                        count += 1
                    
                    # Specific target months
                    if "Oct" in text or "Dec" in text:
                        print(f"MONTH MATCH: {text}")
                
                print(f"Total '2025' rows in {path}: {count}")

if __name__ == "__main__":
    inspect_mhtml()
