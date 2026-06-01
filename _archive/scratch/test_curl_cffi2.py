"""
test_curl_cffi2.py — Enhanced curl_cffi test with chrome131 and full browser headers
"""
import sys, time
sys.path.insert(0, r"C:\Users\jayra\Documents\GeminiVSCode")
from curl_cffi import requests as cf_requests

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-CH-UA": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "DNT": "1",
    "Cache-Control": "max-age=0",
}

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Referer": "https://www.nseindia.com/option-chain",
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Sec-CH-UA": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "Connection": "keep-alive",
}

print("[chrome131] Starting session...")
try:
    sess = cf_requests.Session(impersonate="chrome131")

    # Warm-up 1: Homepage
    print("  GET nseindia.com ...", end=" ", flush=True)
    r1 = sess.get("https://www.nseindia.com", headers=BROWSER_HEADERS, timeout=20)
    print(f"HTTP {r1.status_code} | {len(r1.content)} bytes | cookies: {list(sess.cookies.keys())}")
    time.sleep(2.5)

    # Warm-up 2: Option chain landing page
    print("  GET /option-chain ...", end=" ", flush=True)
    r2 = sess.get("https://www.nseindia.com/option-chain", headers=BROWSER_HEADERS, timeout=20)
    print(f"HTTP {r2.status_code} | {len(r2.content)} bytes | cookies: {list(sess.cookies.keys())}")
    time.sleep(2.0)

    # Warm-up 3: Another NSE page to build cookie state
    print("  GET /market-data/live-equity-market ...", end=" ", flush=True)
    r2b = sess.get("https://www.nseindia.com/market-data/live-equity-market", headers=BROWSER_HEADERS, timeout=20)
    print(f"HTTP {r2b.status_code} | {len(r2b.content)} bytes")
    time.sleep(1.5)

    # API call - NIFTY options
    print("  GET option-chain API (NIFTY) ...", end=" ", flush=True)
    r3 = sess.get(
        "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY",
        headers=API_HEADERS,
        timeout=20
    )
    print(f"HTTP {r3.status_code} | {len(r3.content)} bytes")

    if r3.status_code == 200 and len(r3.content) > 200:
        data = r3.json()
        rows = data.get("records", {}).get("data", [])
        spot = data.get("records", {}).get("underlyingValue", "?")
        expiries = data.get("records", {}).get("expiryDates", [])
        print(f"\n  *** SUCCESS! ***")
        print(f"  Spot     : {spot}")
        print(f"  Rows     : {len(rows)}")
        print(f"  Expiries : {expiries[:3]}")
        if rows:
            s = rows[0]
            print(f"  Sample   : Strike={s.get('strikePrice')}, CE_OI={s.get('CE',{}).get('openInterest','n/a')}")
    else:
        print(f"  Still blocked. Body: {r3.text[:300]}")
        print(f"  Cookies present: {dict(sess.cookies)}")

except Exception as e:
    print(f"\n  FAIL: {e}")

# Try BANKNIFTY too if NIFTY worked
print("\n[chrome131] Testing BANKNIFTY...")
try:
    sess2 = cf_requests.Session(impersonate="chrome131")
    sess2.get("https://www.nseindia.com", headers=BROWSER_HEADERS, timeout=20)
    time.sleep(2.0)
    sess2.get("https://www.nseindia.com/option-chain", headers=BROWSER_HEADERS, timeout=20)
    time.sleep(1.5)
    r = sess2.get(
        "https://www.nseindia.com/api/option-chain-indices?symbol=BANKNIFTY",
        headers=API_HEADERS, timeout=20
    )
    print(f"  BANKNIFTY: HTTP {r.status_code} | {len(r.content)} bytes")
    if len(r.content) > 200:
        d = r.json()
        print(f"  Spot={d.get('records',{}).get('underlyingValue','?')}, Rows={len(d.get('records',{}).get('data',[]))}")
    else:
        print(f"  Body: {r.text[:200]}")
except Exception as e:
    print(f"  FAIL: {e}")

print("\nDone.")
