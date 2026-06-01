import requests
import os
import time
import glob
import re

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

# ⚠️ HOW TO GET YOUR COOKIE:
# 1. Go to screener.in and login.
# 2. Press F12 -> Go to 'Network' tab -> Refresh page.
# 3. Click the first request (usually 'screener.in').
# 4. Scroll down to 'Request Headers'.
# 5. Copy the long string next to 'cookie:'.
# 6. Paste it inside the quotes below.
COOKIE_STRING = "csrftoken=TTQwjRrn5mKrjemC7LKLDL7m3wJrwTQU; expires=Sun, 24 Jan 2027 13:34:38 GMT; Max-Age=31449600; Path=/; SameSite=Lax; Secure"

# ==========================================
# 2. PAGINATION ENGINE
# ==========================================
def fetch_screener_data(interactive=True):
    print("="*60)
    print("📥 SCREENER.IN MULTI-PAGE FETCHER (PRO)")
    print("="*60)

    if "PASTE" in COOKIE_STRING:
        print("❌ ERROR: Please paste your Cookie in the script.")
        return

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Cookie": COOKIE_STRING
    }

    # 1. CLEANUP OLD FILES (Crucial for data hygiene)
    print("🧹 Cleaning up old HTML files...")
    old_files = glob.glob("*.html")
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
        
        page = 1
        max_pages = 10  # Safety limit to prevent infinite loops
        last_page_content = ""
        
        while page <= max_pages:
            # Construct Paged URL
            # Handles if URL already has '?' or not
            separator = "&" if "?" in base_url else "?"
            paged_url = f"{base_url}{separator}page={page}"
            
            try:
                print(f"   -> Downloading Page {page}...", end=" ")
                r = requests.get(paged_url, headers=headers)
                
                if r.status_code != 200:
                    print(f"❌ Failed (Status {r.status_code})")
                    break

                # CHECK FOR EMPTY RESULTS (Enhanced)
                text_content = r.text.lower()
                
                # 1. Explicit clean message
                if "no results found" in text_content:
                    print("✅ (End of results - Explicit)")
                    break
                
                # 2. Page Number Check (Redirect Detection)
                # Screener redirects to the last valid page if you go too far.
                # We check for text like "Showing page 2 of 2"
                # If we requested Page 3 but got Page 2, we stop.
                match = re.search(r"showing page (\d+) of", text_content)
                if match:
                    detected_page = int(match.group(1))
                    if detected_page < page:
                        print(f"✅ (End of results - Redirected to max page {detected_page})")
                        break
    
                # 3. Row Count Check
                # If table exists but has no data rows (only header)
                # Count <tr> tags. A typical header has 1 row.
                row_count = text_content.count("<tr")
                if row_count < 2:  # Assuming at least 1 header row + 1 data row = 2
                        print(f"✅ (End of results - Low Rows: {row_count})")
                        break
    
                # Save File
                filename = f"{name}_p{page}.html"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(r.text)
                
                print("✅ Saved.")
                
                page += 1
                time.sleep(1) # Be polite to server

            except Exception as e:
                print(f"❌ Error: {e}")
                break
        
    print("\n" + "="*60)
    print("✨ ALL DATA FETCHED.")
    print("   Run 'Process Screener HTMLs' now.")
    print("   (It will automatically merge all these pages).")
    
    if interactive:
        input("Press Enter to exit...")

if __name__ == "__main__":
    fetch_screener_data()