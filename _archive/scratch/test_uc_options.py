"""
test_uc_options.py — Uses undetected-chromedriver (patched Chrome, bypasses Akamai JS)
Installs uc if needed, then harvests NSE options data via real Chrome + requests.
"""
import sys, subprocess, time, json

sys.path.insert(0, r"C:\Users\jayra\Documents\GeminiVSCode")

# ---------- install if needed ----------
for pkg, import_name in [("undetected-chromedriver", "undetected_chromedriver"), ("selenium", "selenium")]:
    try:
        __import__(import_name)
        print(f"{import_name}: already installed")
    except ImportError:
        print(f"Installing {pkg}...")
        subprocess.run([sys.executable, "-m", "pip", "install", pkg, "--quiet"], check=True)

import undetected_chromedriver as uc
import requests

print("\n[1] Launching undetected Chrome...")
options = uc.ChromeOptions()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1280,900")
# NOTE: NOT headless — uc works best in visible mode for Akamai bypass

try:
    driver = uc.Chrome(options=options, version_main=146)
    print("  Chrome launched OK")

    # Step 1: NSE homepage
    print("  Navigating to nseindia.com...")
    driver.get("https://www.nseindia.com")
    time.sleep(3)
    print(f"  Title: {driver.title[:60]}")

    # Step 2: Option chain page (this triggers Akamai JS validation)
    print("  Navigating to option-chain...")
    driver.get("https://www.nseindia.com/option-chain")
    time.sleep(4)
    print(f"  Title: {driver.title[:60]}")

    # Step 3: Harvest all cookies from the real Chrome session
    browser_cookies = driver.get_cookies()
    cookie_dict = {c["name"]: c["value"] for c in browser_cookies}
    print(f"  Cookies: {list(cookie_dict.keys())}")

    abck = cookie_dict.get("_abck", "")
    # Check if Akamai approved: valid _abck does NOT end in -1~-1~-1~-1~-1~-1
    if abck.endswith("-1~-1~-1~-1~-1~-1") or abck.endswith("~-1"):
        print("  WARNING: _abck still not validated by Akamai JS")
    else:
        print("  _abck looks valid (JS ran successfully)")

    driver.quit()
    print("  Chrome closed")

    # Step 4: Use harvested cookies in a requests.Session
    print("\n[2] Using harvested cookies in requests.Session...")
    sess = requests.Session()
    for name, value in cookie_dict.items():
        sess.cookies.set(name, value, domain=".nseindia.com")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.7",
        "Referer": "https://www.nseindia.com/option-chain",
        "X-Requested-With": "XMLHttpRequest",
    }

    url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
    r = sess.get(url, headers=headers, timeout=15)
    print(f"  API response: HTTP {r.status_code}, {len(r.content)} bytes")

    if r.status_code == 200 and len(r.content) > 200:
        data = r.json()
        rows = data.get("records", {}).get("data", [])
        spot = data.get("records", {}).get("underlyingValue", "?")
        expiries = data.get("records", {}).get("expiryDates", [])
        print(f"\n  *** SUCCESS! ***")
        print(f"  Spot     : {spot}")
        print(f"  Rows     : {len(rows)}")
        print(f"  Expiries : {expiries[:3]}")
        if rows:
            s = rows[0]
            print(f"  Sample   : Strike={s.get('strikePrice')}, CE_OI={s.get('CE',{}).get('openInterest','n/a')}, PE_OI={s.get('PE',{}).get('openInterest','n/a')}")
        # Save sample for inspection
        with open(r"C:\Users\jayra\Documents\GeminiVSCode\nse_options_sample.json", "w") as f:
            json.dump(data.get("records", {}), f, indent=2)
        print("  Saved sample to nse_options_sample.json")
    else:
        print(f"  Still blocked: {r.text[:300]}")

except Exception as e:
    import traceback
    print(f"\nERROR: {e}")
    traceback.print_exc()
    try:
        driver.quit()
    except:
        pass

print("\nDone.")
