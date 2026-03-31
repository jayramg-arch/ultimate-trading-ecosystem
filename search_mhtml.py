import os
import quopri
from email import message_from_file

files = ["Dhan Trade Journal-2024-25.mhtml", "Dhan Trade Journal-2025-26.mhtml"]

def search_mhtml(target_str):
    print(f"\n--- Searching for '{target_str}' ---")
    for path in files:
        if not os.path.exists(path):
            print(f"File {path} not found.")
            continue
            
        print(f"Checking {path}...")
        with open(path, "r", encoding='utf-8', errors='ignore') as f:
            msg = message_from_file(f)
            
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload()
                if part.get("Content-Transfer-Encoding") == "quoted-printable":
                    html_content = quopri.decodestring(payload).decode('utf-8', errors='ignore')
                else:
                    html_content = payload
                
                # Search in HTML
                if target_str in html_content:
                    idx = html_content.find(target_str)
                    print(f"MATCH FOUND in {path} at index {idx}")
                    # Print 500 chars surrounding match
                    snippet = html_content[max(0, idx-200):idx+500]
                    print(f"Snippet:\n{snippet}\n")
                else:
                    print(f"No match for '{target_str}' in {path}")

if __name__ == "__main__":
    search_mhtml("Oct")
    search_mhtml("October")
    search_mhtml("Dec")
    search_mhtml("December")
    search_mhtml("2025-10")
    search_mhtml("2025-12")
