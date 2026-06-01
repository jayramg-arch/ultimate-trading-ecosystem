"""
test_uc_options2.py — Execute the API call directly from within Chrome via JS (execute_script).
No cookie transfer needed. The browser already has valid Akamai session.
"""
import sys, time, json
sys.path.insert(0, r"C:\Users\jayra\Documents\GeminiVSCode")

import undetected_chromedriver as uc

print("[1] Launching Chrome (version 146)...")
options = uc.ChromeOptions()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1400,900")
# Do NOT use headless — Akamai detects headless

try:
    driver = uc.Chrome(options=options, version_main=146)
    print("  OK")

    # Step 1: Land on NSE homepage (sets initial Akamai cookies)
    print("  Loading NSE homepage...")
    driver.get("https://www.nseindia.com")
    time.sleep(4)  # Let Akamai JS run

    # Step 2: Load option chain page (this page fires XHR for the data)
    print("  Loading option-chain page...")
    driver.get("https://www.nseindia.com/option-chain")
    time.sleep(6)  # Wait for full page load + XHR + Akamai JS
    print(f"  Title: {driver.title[:80]}")

    # Step 3: Fire the API call FROM WITHIN Chrome using fetch()
    print("  Firing fetch() inside Chrome...")
    script = """
    return new Promise((resolve, reject) => {
        fetch('/api/option-chain-indices?symbol=NIFTY', {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Accept': 'application/json, text/plain, */*',
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(r => r.text())
        .then(text => resolve(text))
        .catch(err => reject(err.toString()));
    });
    """
    result = driver.execute_async_script("""
        var callback = arguments[arguments.length - 1];
        fetch('/api/option-chain-indices?symbol=NIFTY', {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Accept': 'application/json, text/plain, */*',
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(r => r.text())
        .then(text => callback({ok: true, data: text}))
        .catch(err => callback({ok: false, error: err.toString()}));
    """)

    print(f"  Result type: {type(result)}")
    if result and result.get("ok"):
        raw = result["data"]
        print(f"  Response size: {len(raw)} bytes")
        if len(raw) > 100:
            data = json.loads(raw)
            rows = data.get("records", {}).get("data", [])
            spot = data.get("records", {}).get("underlyingValue", "?")
            expiries = data.get("records", {}).get("expiryDates", [])
            print(f"\n  *** SUCCESS! ***")
            print(f"  Spot     : {spot}")
            print(f"  Rows     : {len(rows)}")
            print(f"  Expiries : {expiries[:3]}")
            if rows:
                for r in rows[:3]:
                    sp = r.get("strikePrice", "?")
                    ce = r.get("CE", {}).get("openInterest", "n/a")
                    pe = r.get("PE", {}).get("openInterest", "n/a")
                    print(f"    Strike={sp}  CE_OI={ce}  PE_OI={pe}")
            # Save full sample
            with open(r"C:\Users\jayra\Documents\GeminiVSCode\nse_options_sample.json", "w") as f:
                json.dump(data, f, indent=2)
            print("  Saved to nse_options_sample.json")
        else:
            print(f"  Still small: {raw[:200]}")
    else:
        print(f"  Fetch error: {result}")

    # Also test BANKNIFTY
    print("\n[2] Testing BANKNIFTY...")
    result2 = driver.execute_async_script("""
        var callback = arguments[arguments.length - 1];
        fetch('/api/option-chain-indices?symbol=BANKNIFTY', {
            method: 'GET', credentials: 'include',
            headers: {'Accept': 'application/json, text/plain, */*', 'X-Requested-With': 'XMLHttpRequest'}
        })
        .then(r => r.text())
        .then(text => callback({ok: true, data: text}))
        .catch(err => callback({ok: false, error: err.toString()}));
    """)
    if result2 and result2.get("ok"):
        raw2 = result2["data"]
        if len(raw2) > 100:
            d2 = json.loads(raw2)
            print(f"  BANKNIFTY spot={d2.get('records',{}).get('underlyingValue','?')}, rows={len(d2.get('records',{}).get('data',[]))}")
        else:
            print(f"  BANKNIFTY blocked: {raw2[:100]}")

    driver.quit()
    print("\n  Chrome closed OK")

except Exception as e:
    import traceback
    print(f"\nERROR: {e}")
    traceback.print_exc()
    try:
        driver.quit()
    except:
        pass

print("\nDone.")
