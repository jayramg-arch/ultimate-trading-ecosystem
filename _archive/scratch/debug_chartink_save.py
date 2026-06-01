
import requests

url = "https://chartink.com/screener/stage-2-hunter"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

try:
    print(f"👉 Fetching {url}...")
    r = requests.get(url, headers=headers)
    
    with open("debug_chartink_full.html", "w", encoding="utf-8") as f:
        f.write(r.text)
        
    print("✅ Saved to debug_chartink_full.html")

except Exception as e:
    print(f"❌ Error: {e}")
