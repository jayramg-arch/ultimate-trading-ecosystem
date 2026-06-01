"""
Test: Use Playwright network interception to capture NSE API response
from INSIDE the browser — never transfers cookies out.
The browser loads option-chain page, we intercept the API call it makes.
"""
import sys, json, time
sys.path.insert(0, r"C:\Users\jayra\Documents\GeminiVSCode")

_captured = {}

def fetch_via_interception(symbol="NIFTY", timeout_ms=30000):
    from playwright.sync_api import sync_playwright
    result = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"),
            locale="en-US",
            viewport={"width": 1366, "height": 768},
        )

        # Intercept the API response from inside the browser
        def handle_response(response):
            url = response.url
            if "option-chain-indices" in url and symbol in url:
                try:
                    body = response.json()
                    rows = body.get("records", {}).get("data", [])
                    if rows:
                        result["data"] = body
                        print(f"  Intercepted: {url}")
                        print(f"  Rows: {len(rows)}, Spot: {body.get('records',{}).get('underlyingValue','?')}")
                except Exception as e:
                    print(f"  Intercept parse error: {e}")

        page = ctx.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page.on("response", handle_response)

        print(f"[1] Loading NSE homepage...")
        try:
            page.goto("https://www.nseindia.com", timeout=timeout_ms,
                      wait_until="domcontentloaded")
            time.sleep(2)
            print(f"[2] Loading option-chain page (browser will call API automatically)...")
            page.goto(f"https://www.nseindia.com/option-chain?type=Indices&symbol={symbol}",
                      timeout=timeout_ms, wait_until="networkidle")
            time.sleep(3)  # wait for any late XHR calls
        except Exception as e:
            print(f"  Page load error: {e}")

        browser.close()

    return result.get("data")

print("=" * 55)
print("NSE Option Chain — Network Interception Test")
print("=" * 55)
data = fetch_via_interception("NIFTY")
if data:
    rows = data.get("records", {}).get("data", [])
    spot = data.get("records", {}).get("underlyingValue", "?")
    expiries = data.get("records", {}).get("expiryDates", [])
    print(f"\nSUCCESS!")
    print(f"  Spot     : {spot}")
    print(f"  Rows     : {len(rows)}")
    print(f"  Expiries : {expiries[:4]}")
    # Save for inspection
    with open(r"C:\Users\jayra\Documents\GeminiVSCode\nse_sample.json", "w") as f:
        json.dump({"spot": spot, "row_count": len(rows), "expiries": expiries}, f)
    print("  Sample saved to nse_sample.json")
else:
    print("\nFAILED — could not intercept API response")
    print("NSE may be blocking headless browsers or network is restricted.")
