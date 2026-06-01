import sys, time
sys.path.insert(0, r'C:\Users\jayra\Documents\GeminiVSCode')

from curl_cffi import requests as cffi_req

print("=== Testing curl_cffi against NSE option chain ===")

session = cffi_req.Session(impersonate="chrome131")

# Step 1 — get cookies
print("1. Warming up NSE session...")
r0 = session.get("https://www.nseindia.com", timeout=15)
print(f"   Homepage: {r0.status_code}, cookies: {list(r0.cookies.keys())[:5]}")
time.sleep(1.5)

# Step 2 — hit the option chain endpoint
url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
headers = {
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/option-chain",
    "X-Requested-With": "XMLHttpRequest",
}
print("2. Fetching NIFTY option chain...")
r1 = session.get(url, headers=headers, timeout=20)
print(f"   Status: {r1.status_code}")
print(f"   Content-length: {len(r1.text)}")
print(f"   First 300 chars: {r1.text[:300]}")

if r1.status_code == 200:
    try:
        data = r1.json()
        records = data.get("records", {})
        expiries = records.get("expiryDates", [])
        spot = records.get("underlyingValue", 0)
        row_count = len(records.get("data", []))
        print(f"\n   SUCCESS! spot={spot}, expiries={expiries[:3]}, rows={row_count}")
    except Exception as e:
        print(f"   JSON parse error: {e}")
else:
    print(f"   BODY: {r1.text[:500]}")
