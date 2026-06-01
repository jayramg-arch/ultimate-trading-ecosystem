"""
test_uc_options3.py — Poll until Akamai _abck cookie is validated, then fire API call.
Akamai's JS runs asynchronously; we need to wait for it to update _abck before calling the API.
"""
import sys, time, json
sys.path.insert(0, r"C:\Users\jayra\Documents\GeminiVSCode")
import undetected_chromedriver as uc

def wait_for_akamai_validation(driver, timeout=25):
    """Poll _abck cookie until Akamai JS has validated (removes trailing -1 pattern)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        abck = cookies.get("_abck", "")
        # Valid _abck: contains many ~-separated segments, last one is NOT -1
        if abck and not (abck.endswith("~-1") or "~-1~-1~-1~-1~-1~-1" in abck):
            return True, abck
        time.sleep(1.5)
    return False, cookies.get("_abck", "")

def fetch_via_script(driver, symbol):
    """Fire fetch() inside Chrome context and return the response text."""
    result = driver.execute_async_script(f"""
        var callback = arguments[arguments.length - 1];
        fetch('/api/option-chain-indices?symbol={symbol}', {{
            method: 'GET', credentials: 'include',
            headers: {{
                'Accept': 'application/json, text/plain, */*',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://www.nseindia.com/option-chain'
            }}
        }})
        .then(r => r.text())
        .then(t => callback({{ok: true, data: t, len: t.length}}))
        .catch(e => callback({{ok: false, error: e.toString()}}));
    """)
    return result

print("[1] Launching Chrome...")
options = uc.ChromeOptions()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1400,900")
# Add realistic user preferences
options.add_argument("--lang=en-IN")

try:
    driver = uc.Chrome(options=options, version_main=146)
    driver.set_page_load_timeout(30)
    print("  OK")

    # NSE homepage — warm up cookies
    print("  Loading NSE homepage...")
    driver.get("https://www.nseindia.com")
    time.sleep(3)

    # Option chain page
    print("  Loading /option-chain (waiting for Akamai JS)...")
    driver.get("https://www.nseindia.com/option-chain")

    # Poll for Akamai validation (up to 25s)
    validated, abck_val = wait_for_akamai_validation(driver, timeout=25)
    abck_tail = abck_val[-50:] if abck_val else "none"
    print(f"  Akamai validated: {validated}")
    print(f"  _abck tail: ...{abck_tail}")

    # List all cookies
    cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
    print(f"  All cookies: {list(cookies.keys())}")
    print(f"  nsit present: {'nsit' in cookies}")

    # Fire API from within Chrome
    print("\n  Fetching NIFTY option chain via Chrome fetch()...")
    res = fetch_via_script(driver, "NIFTY")
    if res and res.get("ok"):
        size = res.get("len", 0)
        print(f"  Response: {size} bytes")
        if size > 200:
            data = json.loads(res["data"])
            rows = data.get("records", {}).get("data", [])
            spot = data.get("records", {}).get("underlyingValue", "?")
            expiries = data.get("records", {}).get("expiryDates", [])
            print(f"\n  *** SUCCESS! ***")
            print(f"  Spot: {spot}  |  Rows: {len(rows)}  |  Expiries: {expiries[:3]}")
            # Save
            with open(r"C:\Users\jayra\Documents\GeminiVSCode\nse_options_sample.json", "w") as f:
                json.dump(data, f, indent=2)
            print("  Saved to nse_options_sample.json")
        else:
            print(f"  Still blocked: {res.get('data','')[:100]}")
    else:
        print(f"  Fetch error: {res}")

    # Check if the page itself loaded option chain data in DOM
    print("\n  Checking DOM for option chain table...")
    try:
        rows_on_page = driver.execute_script("""
            var tbl = document.querySelector('table.optionsTable') ||
                      document.querySelector('#optionChainData') ||
                      document.querySelector('.oc-table');
            if (tbl) return tbl.rows.length;
            return -1;
        """)
        print(f"  Table rows in DOM: {rows_on_page}")
    except Exception as e:
        print(f"  DOM check: {e}")

    driver.quit()
    print("\n  Chrome closed")

except Exception as e:
    import traceback
    print(f"\nERROR: {e}")
    traceback.print_exc()
    try: driver.quit()
    except: pass

print("\nDone.")
