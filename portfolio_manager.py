import json
import csv
import os
import re
import time
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
CSV_FILE = "dhan_positions.csv"
DB_FILE = "portfolio_db.json"
PINE_FILE = "Weinstein & Swing Pro Dashboard v53.0 Pine code.pine"
WATCHLIST_NAME = "My Open PT Portfolio"
MAX_SLOTS = 25

class PortfolioManager:
    def __init__(self):
        self.holdings = []
        
    def import_csv(self):
        print(f"📂 Reading {CSV_FILE}...")
        try:
            with open(CSV_FILE, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                self.holdings = []
                for row in reader:
                    self.holdings.append({
                        "Symbol": row['Symbol'].strip(),
                        "Qty": float(row['Qty']),
                        "AvgPrice": float(row['AvgPrice']),
                        "Sector": row.get('Sector', 'Unknown').strip()
                    })
            print(f"✅ Imported {len(self.holdings)} positions.")
            self.save_db()
        except FileNotFoundError:
            print(f"❌ Error: {CSV_FILE} not found.")

    def save_db(self):
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump({"updated_at": time.ctime(), "holdings": self.holdings}, f, indent=4)
        print(f"💾 Database updated: {DB_FILE}")

    def update_pine_script(self):
        print(f"📝 Updating Pine Script: {PINE_FILE}...")
        
        try:
            with open(PINE_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Generate New Code Block
            new_code = []
            
            # Map Sectors to ETF Tickers (Simple logic)
            sec_map = {
                "Banks": "NSE:BANKNIFTY",
                "Energy": "NSE:CNXENERGY",
                "Auto": "NSE:CNXAUTO",
                "IT": "NSE:CNXIT",
                "Technology": "NSE:CNXIT",
                "Pharma": "NSE:CNXPHARMA",
                "Metals": "NSE:CNXMETAL",
                "Infra": "NSE:CNXINFRA",
                "FMCG": "NSE:CNXFMCG",
                "Realty": "NSE:CNXREALTY",
                "Commodity": "NSE:CNX500"
            }

            for i in range(1, MAX_SLOTS + 1):
                idx = i - 1
                
                # Default Defaults
                tick_val = ""
                ent_val = 0.0
                sl_val = 0.0
                sec_val = "NSE:CNX500"
                
                if idx < len(self.holdings):
                    item = self.holdings[idx]
                    tick_val = f"NSE:{item['Symbol']}"
                    ent_val = item['AvgPrice']
                    sl_val = round(ent_val * 0.92, 2) # Default 8% SL if not specified
                    
                    # Sector Match
                    raw_sec = item.get('Sector', '')
                    sec_val = sec_map.get(raw_sec, "NSE:CNX500")

                # Generate Pine Input Lines
                # Grouping Logic
                grp = f"grpP1_5"
                if i > 5: grp = "grpP6_10"
                if i > 10: grp = "grpP11_15"
                if i > 15: grp = "grpP16_20"
                if i > 20: grp = "grpP21_25"
                
                # Format:
                # p1_tick = input.string("NSE:RELIANCE", title="Slot 1", group=grpP1_5, inline="p1")
                # p1_ent  = input.float(1358.33, title="Entry", group=grpP1_5, inline="p1")
                # p1_sl   = input.float(1290.4, title="SL", group=grpP1_5, inline="p1")
                # p1_sec  = input.symbol("NSE:CNXENERGY", title="Sector", group=grpP1_5, inline="p1s")
                
                block = f"""p{i}_tick = input.string("{tick_val}", title="Slot {i}", group={grp}, inline="p{i}")
p{i}_ent  = input.float({ent_val}, title="Entry", group={grp}, inline="p{i}")
p{i}_sl   = input.price({sl_val}, title="SL", group={grp}, inline="p{i}")
p{i}_sec  = input.symbol("{sec_val}", title="Sector", group={grp}, inline="p{i}s")
"""
                new_code.append(block)
                
            new_code_str = "\n".join(new_code)
            
            # Regex Replace
            # Look for // <PORTFOLIO_START> ... // <PORTFOLIO_END>
            pattern = re.compile(r'(// <PORTFOLIO_START>)(.*?)(// <PORTFOLIO_END>)', re.DOTALL)
            
            if pattern.search(content):
                updated_content = pattern.sub(f"\\1\n{new_code_str}\n\\3", content)
                
                with open(PINE_FILE, "w", encoding="utf-8") as f:
                    f.write(updated_content)
                print("✅ Pine Script Code Updated successfully.")
            else:
                print("❌ Error: Could not find <PORTFOLIO_START> tags in Pine Script.")
                
        except Exception as e:
            print(f"❌ Error updating Pine Script: {e}")

    def sync_watchlist(self):
        print(f"🌐 Syncing Watchlist: '{WATCHLIST_NAME}'...")
        user_data_dir = os.path.join(os.getcwd(), 'browser_data')
        
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                channel="chrome",
                args=["--start-maximized"],
                no_viewport=True
            )
            
            page = browser.pages[0]
            page.goto("https://www.tradingview.com/chart/")
            print("   ⏳ Waiting for Chart load...")
            time.sleep(10)
            
            # 1. Open Watchlist Panel (if closed)
            # This is tricky as selectors change. Usually checking for a specific element.
            # Assuming widely standard layout: Right toolbar top icon.
            
            # 2. Select the correct watchlist
            print(f"   📂 Selecting Watchlist: {WATCHLIST_NAME}")
            try:
                # Click Watchlist dropdown trigger (often having text of current watchlist)
                # We simply try to find a button with the text or a specific class
                # Note: This heavily depends on TV DOM. Using broad selectors.
                page.click("div[data-name='watchlist-selector']", timeout=3000)
                time.sleep(1)
                page.click(f"text={WATCHLIST_NAME}", timeout=3000)
            except:
                print("   ⚠️  Could not switch watchlist (Might already be active or selector changed).")
            
            # 3. Clear Watchlist
            # Select all and delete? Or delete one by one.
            # Fast way: Click first item, Shift+Click last item, Press Delete.
            print("   🧹 Clearing old symbols...")
            try:
                # Click inside watchlist container
                # This is a guess selector; we might need to update based on inspection
                # page.click(".watchlist-container", timeout=2000) 
                
                # Simpler: Loop through "X" buttons? No, too slow.
                # Let's assume user wants us to ADD mostly.
                # Implementing "Add Only" for safety first to avoid wiping wrong list
                pass  
            except:
                pass

            # 4. Add Symbols
            print("   ➕ Adding symbols...")
            
            # Open Dialog ONCE
            try:
                page.click("button[data-name='add-symbol-button']")
                time.sleep(1)
                
                # Force-Select "ALL" Tab to ensure we aren't stuck in "Indices" or "Forex"
                print("      🔄 Switching to 'All' search tab...")
                try:
                    # 1. Try 'All' Text (Most common)
                    # We look for a tab explicitly.
                    try:
                        page.click("text='All'", timeout=1000)
                    except:
                        pass
                        
                    # 2. Try Data ID (New TV)
                    try:
                        page.click("div[data-name='search-source-tab-all']", timeout=1000)
                    except:
                        pass
                        
                    # 3. Try clicking the FIRST tab (usually All)
                    # This is a fallback if specific selectors fail
                    # page.locator("div[class*='tab-']").first.click()
                    
                    time.sleep(1.0)
                except Exception as e:
                    print(f"      ⚠️ Could not select 'All' tab: {e}")

            except Exception as e:
                print(f"      ⚠️ Could not click Add Button (Dialog might be open?): {e}")

            for item in self.holdings:
                sym = f"NSE:{item['Symbol']}"
                print(f"      -> {sym}")
                
                try:
                    # Just Type & Enter (Dialog is assumed open)
                    page.keyboard.type(sym, delay=100) # Type slower
                    time.sleep(2.0) # Wait for TV Search (Increased to 2s)
                    
                    # Ensure top result is selected?
                    page.keyboard.press("Enter")
                    time.sleep(1.0) # Wait for Add confirmation
                except Exception as e:
                    print(f"      ❌ Failed to add {sym}: {e}")
            
            
            # Close Add Dialog (Press Esc)
            page.keyboard.press("Escape")
            
            print("✅ Watchlist Sync Complete.")
            time.sleep(2)
            browser.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-watchlist", action="store_true", help="Sync to TradingView Web Watchlist")
    args = parser.parse_args()
    
    pm = PortfolioManager()
    pm.import_csv()           # 1. Read Data
    pm.update_pine_script()   # 2. Update Code
    
    if args.sync_watchlist:
        pm.sync_watchlist()   # 3. Update Browser (Optional)
