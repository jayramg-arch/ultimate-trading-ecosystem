import requests
import os
import time
import glob
import re
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(override=True)

# ==========================================
# 1. CONFIGURATION
# ==========================================
# PASTE YOUR 4 SCREENER.IN URLS HERE
SCREENER_URLS = {
    # ── Stage 2 Screens (Normal Market) ──────────────────────────────────────
    "Stage2_Hunter":   "https://www.screener.in/screens/3454433/stage2-hunter-final/",
    "Stage2_Pullback": "https://www.screener.in/screens/3440648/pullback-fundamentals-jay/",
    "Early_Birds":     "https://www.screener.in/screens/3440667/early-birds-fundamentals-jay/",
    "Strong_Leaders":  "https://www.screener.in/screens/3440684/leader-fundamentals-jay/",

    # ── Recovery Phase Screens (Post-Shock Apr-2026) ──────────────────────────
    # Prefix 'Recovery_' is used by screener_processor.py to route these
    # to separate CSVs instead of merging into MASTER_scan_results.csv
    "Recovery_RS_Survivors":   "https://www.screener.in/screens/3591202/rs-survivors/",
    "Recovery_Climax_Bounce":  "https://www.screener.in/screens/3591217/climax-bottom-bounce/",
    "Recovery_Early_Birds":    "https://www.screener.in/screens/3591222/recovery-early-birds/",
}

# ⚠️ HOW TO SET YOUR COOKIE:
# 1. Go to screener.in and login.
# 2. Press F12 -> Go to 'Network' tab -> Refresh page.
# 3. Click the first request (usually 'screener.in').
# 4. Scroll down to 'Request Headers'.
# 5. Copy the long string next to 'cookie:'.
# 6. Add this line to your .env file:  SCREENER_COOKIE=<your cookie string here>
#
# Example (in .env):
# SCREENER_COOKIE=csrftoken=ABC123...; sessionid=XYZ...
COOKIE_STRING = os.getenv("SCREENER_COOKIE", "").strip("'\"")

# ==========================================
# 2. PAGINATION ENGINE
# ==========================================
def fetch_screener_data(interactive=True):
    print("="*60)
    print("📥 SCREENER.IN MULTI-PAGE FETCHER (PRO)")
    print("="*60)

    # Automatically refresh the Screener cookie if credentials are in env
    try:
        from screener_cookie_refresh import ensure_valid_cookie
        # We run headlessly so it doesn't pop up a browser window during background tasks
        ensure_valid_cookie(headless=True)
    except Exception as e:
        print(f"⚠️  Cookie refresh check failed: {e}. Attempting fetch with current cookie...")

    # Reload cookie string after potential refresh
    cookie_str = os.getenv("SCREENER_COOKIE", "").strip("'\"")
    if not cookie_str or len(cookie_str) < 20:
        print("❌ ERROR: SCREENER_COOKIE not set or expired in .env file.")
        print("   Add SCREENER_EMAIL and SCREENER_PASSWORD to .env for auto-refresh,")
        print("   or manually paste your SCREENER_COOKIE value.")
        return

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Cookie": cookie_str
    }

    # 1. CLEANUP OLD FILES (Crucial for data hygiene)
    print("🧹 Cleaning up old HTML and premium CSV files...")
    old_files = glob.glob("*.html") + glob.glob("*_premium.csv")
    for f in old_files:
        try:
            os.remove(f)
        except: pass
    print("   Done.")

    # 2. FETCH LOOP
    for name, base_url in SCREENER_URLS.items():
        if "PASTE" in base_url:
            print(f"⚠️ Skipping {name} (URL missing).")
            continue

        print(f"\n🔍 Fetching Strategy: {name}")
        
        # Check if we can download the premium CSV directly
        premium_success = False
        form_url = None
        form_csrf = None
        
        try:
            r_page = requests.get(base_url, headers=headers, timeout=15)
            if r_page.status_code == 200:
                soup = BeautifulSoup(r_page.text, 'html.parser')
                form = None
                for f in soup.find_all('form'):
                    if f.get('action') and 'export' in f.get('action'):
                        form = f
                        break
                if form:
                    form_url = f"https://www.screener.in{form.get('action')}"
                    csrf_input = form.find('input', {'name': 'csrfmiddlewaretoken'})
                    if csrf_input:
                        form_csrf = csrf_input.get('value')
        except Exception as e:
            print(f"❌ (Failed to load screen page form details: {e})")

        if form_url:
            try:
                print(f"   -> Attempting direct CSV export...", end=" ")
                # Extract csrftoken value from cookie to use in headers
                csrftoken = None
                for part in cookie_str.split(';'):
                    if '=' in part:
                        k, v = part.strip().split('=', 1)
                        if k == 'csrftoken':
                            csrftoken = v
                            break
                
                # Use form_csrf if found, else fallback to csrftoken
                active_csrf = form_csrf if form_csrf else csrftoken
                
                post_data = {
                    "csrfmiddlewaretoken": active_csrf
                }
                post_headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Cookie": cookie_str,
                    "Referer": base_url,
                    "X-CSRFToken": active_csrf,
                    "Origin": "https://www.screener.in"
                }
                
                r = requests.post(form_url, headers=post_headers, data=post_data, timeout=15)
                is_html = "text/html" in r.headers.get("Content-Type", "").lower()
                if r.status_code == 200 and not is_html:
                    csv_filename = f"{name}_premium.csv"
                    # Screener returns raw CSV text. Save it.
                    with open(csv_filename, "w", encoding="utf-8") as f:
                        f.write(r.text)
                    print(f"✅ Premium CSV Saved ({len(r.text.splitlines()) - 1} stocks)")
                    premium_success = True
                else:
                    print("❌ (Cookie expired or non-premium, falling back to HTML scraping)")
            except Exception as e:
                print(f"❌ (Export failed: {e}, falling back to HTML scraping)")

        if not premium_success:
            print("❌ Premium CSV export failed. HTML pagination fallback has been strictly disabled. Please check your SCREENER_COOKIE.")

    print("\n" + "="*60)
    print("✨ ALL DATA FETCHED.")
    print("   Run 'Process Screener HTMLs' now.")
    print("   (It will automatically merge all these pages).")
    
    if interactive:
        input("Press Enter to exit...")

if __name__ == "__main__":
    import sys
    interactive_mode = "--batch" not in sys.argv
    fetch_screener_data(interactive=interactive_mode)