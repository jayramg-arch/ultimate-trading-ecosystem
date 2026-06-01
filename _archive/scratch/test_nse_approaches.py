"""Test multiple approaches to get NSE options data"""
import sys, time, requests
sys.path.insert(0, r"C:\Users\jayra\Documents\GeminiVSCode")

# ── Approach 1: nsepython ──────────────────────────────────────────────────
print("=" * 55)
print("Approach 1: nsepython library")
try:
    from nsepython import nse_optionchain_scrapper, nsefetch
    data = nse_optionchain_scrapper("NIFTY")
    rows = data.get("records", {}).get("data", [])
    spot = data.get("records", {}).get("underlyingValue", "?")
    print(f"  SUCCESS — spot={spot}, rows={len(rows)}")
except Exception as e:
    print(f"  FAIL: {e}")

# ── Approach 2: Playwright with HTTP/2 disabled ────────────────────────────
print("\nApproach 2: Playwright + --disable-http2")
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-http2", "--no-sandbox",
                  "--disable-blink-features=AutomationControlled"]
        )
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"),
            locale="en-US",
        )
        page = ctx.new_page()
        # Remove webdriver flag
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page.goto("https://www.nseindia.com", timeout=25000,
                  wait_until="domcontentloaded")
        time.sleep(2)
        page.goto("https://www.nseindia.com/option-chain",
                  timeout=25000, wait_until="domcontentloaded")
        time.sleep(2)
        cookies = ctx.cookies()
        browser.close()

    sess = requests.Session()
    sess.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nseindia.com/option-chain",
        "X-Requested-With": "XMLHttpRequest",
    })
    for ck in cookies:
        sess.cookies.set(ck["name"], ck["value"])

    print(f"  Cookies obtained: {[c['name'] for c in cookies]}")
    url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
    r = sess.get(url, timeout=15)
    print(f"  API response: HTTP {r.status_code}, size={len(r.content)} bytes")
    if r.status_code == 200 and len(r.content) > 100:
        data2 = r.json()
        rows2 = data2.get("records", {}).get("data", [])
        spot2 = data2.get("records", {}).get("underlyingValue", "?")
        print(f"  SUCCESS — spot={spot2}, rows={len(rows2)}")
    else:
        print(f"  Body: {r.text[:200]}")
except Exception as e:
    print(f"  FAIL: {e}")

# ── Approach 3: Direct nsefetch (uses requests internally) ─────────────────
print("\nApproach 3: nsefetch direct")
try:
    from nsepython import nsefetch
    url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
    data3 = nsefetch(url)
    rows3 = data3.get("records", {}).get("data", [])
    spot3 = data3.get("records", {}).get("underlyingValue", "?")
    print(f"  SUCCESS — spot={spot3}, rows={len(rows3)}")
except Exception as e:
    print(f"  FAIL: {e}")
