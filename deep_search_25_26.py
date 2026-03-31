import os
import quopri
from email import message_from_file

path = "Dhan Trade Journal-2025-26.mhtml"

def deep_search():
    if not os.path.exists(path):
        print(f"File {path} not found.")
        return
        
    print(f"Deep searching {path}...")
    with open(path, "r", encoding='utf-8', errors='ignore') as f:
        msg = message_from_file(f)
        
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload()
            if part.get("Content-Transfer-Encoding") == "quoted-printable":
                html_content = quopri.decodestring(payload).decode('utf-8', errors='ignore')
            else:
                html_content = payload
            
            # Look for ANY occurrence of October or Oct
            targets = ["Oct", "October", " Oct ", "2025-10", "10/2025"]
            for t in targets:
                if t in html_content:
                    print(f"FOUND TARGET: {t}")
                    idx = html_content.find(t)
                    print(f"Context: {html_content[max(0, idx-100):idx+300]}\n")
            
            # Let's also look for "SELL" or "SVG" identifying sell trades
            if "sell.svg" in html_content:
                print("FOUND 'sell.svg' in content!")
                # Find all positions of sell.svg and print context
                pos = 0
                while True:
                    pos = html_content.find("sell.svg", pos)
                    if pos == -1: break
                    print(f"Sell SVG Context: {html_content[max(0, pos-200):pos+300]}\n")
                    pos += 1
            else:
                print("No 'sell.svg' found.")

if __name__ == "__main__":
    deep_search()
