
import requests
from bs4 import BeautifulSoup
import json
import html

URLS = {
    "Stage 2 Hunter": "https://chartink.com/screener/stage-2-hunter",
    "Early Birds": "https://chartink.com/screener/early-bird-scanner",
    "Stage 2 Pullback": "https://chartink.com/screener/stage-2-pullback",
    "Strong Leaders": "https://chartink.com/screener/strong-leaders"
}

def extract_logic_json():
    print("🚀 Starting Vue Component Extraction for Chartink...\n")
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    })


    results = {}
    for name, url in URLS.items():
        print(f"👉 Fetching {name} ({url})...")
        try:
            r = session.get(url, timeout=30)
            if r.status_code != 200:
                print(f"❌ Failed to fetch {name} (Status {r.status_code})")
                continue

            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Find the <scanner> tag
            scanner_tag = soup.find('scanner')
            if scanner_tag and scanner_tag.has_attr(':scan-json'):
                raw_json = scanner_tag[':scan-json']
                
                try:
                    data = json.loads(raw_json)
                    logic = data.get('atlas_query')
                    
                    if logic:
                        print(f"✅ FOUND Logic for {name}!")
                        results[name] = logic
                    else:
                         print(f"❌ 'atlas_query' not found in JSON for {name}.\n")
                except json.JSONDecodeError as e:
                    print(f"❌ JSON Decode Error for {name}: {e}\nRaw: {raw_json[:100]}...")

            else:
                 print(f"❌ FAILED to find <scanner> tag with :scan-json for {name}.\n")

        except Exception as e:
            print(f"❌ Error extracting {name}: {e}\n")
    
    with open("chartink_logic_dump.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
    print("\n✅ Saved all logic to chartink_logic_dump.json")

if __name__ == "__main__":
    extract_logic_json()
