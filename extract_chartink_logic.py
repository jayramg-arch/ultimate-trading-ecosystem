
import requests
import re
from bs4 import BeautifulSoup

URLS = {
    "Stage 2 Hunter": "https://chartink.com/screener/stage-2-hunter",
    "Early Birds": "https://chartink.com/screener/early-bird-scanner",
    "Stage 2 Pullback": "https://chartink.com/screener/stage-2-pullback",
    "Strong Leaders": "https://chartink.com/screener/strong-leaders"
}

def extract_logic_raw():
    print("🚀 Starting Raw HTML Extraction for Chartink...\n")
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    })

    for name, url in URLS.items():
        print(f"👉 Fetching {name} ({url})...")
        try:
            r = session.get(url, timeout=30)
            if r.status_code != 200:
                print(f"❌ Failed to fetch {name} (Status {r.status_code})")
                continue

            # Chartink logic is often in a hidden input field or JS variable
            # 1. Search for JS variable
            match = re.search(r"var\s+scan_clause\s*=\s*'(.*?)';", r.text)
            
            logic = None
            if match:
                logic = match.group(1).encode('utf-8').decode('unicode_escape')
            else:
                # 2. Search for TextArea
                soup = BeautifulSoup(r.text, 'html.parser')
                textarea = soup.find('textarea', {'id': 'scan_clause'})
                if textarea:
                    logic = textarea.text.strip()
            
            if logic:
                print(f"✅ FOUND Logic for {name}!")
                # Sanitize
                clean_logic = logic.replace("\n", " ").replace("\r", "")
                print(f"   FULL_LOGIC::{name}::{clean_logic}::END_LOGIC\n")
            else:
                print(f"❌ FAILED to find logic in HTML for {name}.\n")

        except Exception as e:
            print(f"❌ Error extracting {name}: {e}\n")

if __name__ == "__main__":
    extract_logic_raw()
