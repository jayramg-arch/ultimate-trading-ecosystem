
import requests

url = "https://chartink.com/screener/stage-2-hunter"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Referer": "https://chartink.com/"
}

try:
    print(f"👉 Fetching {url}...")
    r = requests.get(url, headers=headers, timeout=10)
    print(f"Status Code: {r.status_code}")
    print(f"Headers: {r.headers}")
    print("\n--- CONTENT START ---")
    print(r.text[:1000])  # Print first 1000 chars
    print("--- CONTENT END ---\n")
    
    if "csrf-token" in r.text:
        print("✅ CSRF Token found.")
    else:
        print("❌ CSRF Token NOT found.")

except Exception as e:
    print(f"❌ Error: {e}")
