"""Test curl_cffi — impersonates Chrome TLS fingerprint, bypasses Akamai"""
import sys, subprocess
sys.path.insert(0, r"C:\Users\jayra\Documents\GeminiVSCode")

# Install if needed
try:
    import curl_cffi
    print("curl_cffi already installed")
except ImportError:
    print("Installing curl_cffi...")
    subprocess.run([sys.executable, "-m", "pip", "install", "curl-cffi", "--quiet"])
    import curl_cffi

import time
from curl_cffi import requests as cf_requests

print("\n[1] Testing curl_cffi with Chrome130 impersonation...")
try:
    sess = cf_requests.Session(impersonate="chrome130")

    # Step 1: Homepage
    r1 = sess.get("https://www.nseindia.com", timeout=15)
    print(f"  Homepage: HTTP {r1.status_code}, cookies: {list(sess.cookies.keys())}")
    time.sleep(1.5)

    # Step 2: Option chain page
    r2 = sess.get("https://www.nseindia.com/option-chain", timeout=15)
    print(f"  OC page: HTTP {r2.status_code}, cookies: {list(sess.cookies.keys())}")
    time.sleep(1.0)

    # Step 3: API call
    url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nseindia.com/option-chain",
        "X-Requested-With": "XMLHttpRequest",
    }
    r3 = sess.get(url, headers=headers, timeout=15)
    print(f"  API: HTTP {r3.status_code}, size={len(r3.content)} bytes")

    if r3.status_code == 200 and len(r3.content) > 100:
        data = r3.json()
        rows = data.get("records", {}).get("data", [])
        spot = data.get("records", {}).get("underlyingValue", "?")
        expiries = data.get("records", {}).get("expiryDates", [])
        print(f"\n  *** SUCCESS! ***")
        print(f"  Spot     : {spot}")
        print(f"  Rows     : {len(rows)}")
        print(f"  Expiries : {expiries[:3]}")
    else:
        print(f"  Body (first 200): {r3.text[:200]}")
except Exception as e:
    print(f"  FAIL: {e}")

print("\n[2] Trying chrome124 impersonation...")
try:
    sess2 = cf_requests.Session(impersonate="chrome124")
    sess2.get("https://www.nseindia.com", timeout=15)
    time.sleep(1.5)
    sess2.get("https://www.nseindia.com/option-chain", timeout=15)
    time.sleep(1.0)
    r = sess2.get(
        "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY",
        headers={"Accept": "application/json", "Referer": "https://www.nseindia.com/option-chain"},
        timeout=15
    )
    print(f"  API: HTTP {r.status_code}, size={len(r.content)} bytes")
    if r.status_code == 200 and len(r.content) > 100:
        d = r.json()
        rows = d.get("records", {}).get("data", [])
        print(f"  SUCCESS — spot={d.get('records',{}).get('underlyingValue','?')}, rows={len(rows)}")
    else:
        print(f"  Body: {r.text[:200]}")
except Exception as e:
    print(f"  FAIL: {e}")
