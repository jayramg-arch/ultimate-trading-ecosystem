import os
import time
import shutil
import sys
import yfinance as yf
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- SAFETY CHECK: IMPORT WEBDRIVER MANAGER ---
try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("\n[CRITICAL ERROR] webdriver_manager is still not found!")
    sys.exit()

# ==============================================================================
# 1. CONFIGURATION (ENTER YOUR DETAILS HERE)
# ==============================================================================
CHARTINK_EMAIL = "your_email@gmail.com"  # <--- REPLACE THIS
CHARTINK_PASSWORD = "your_password"      # <--- REPLACE THIS

URL_HUNTER = "https://chartink.com/screener/your-stage-2-hunter-url"      # <--- WEEKEND SCAN
URL_PULLBACK = "https://chartink.com/screener/stage-2-pullback"           # <--- DAILY SCAN

BENCHMARK_SYMBOL = "^NSEI"

# ==============================================================================
# 2. THE ROBOT (AUTO-FETCHER)
# ==============================================================================
def fetch_chartink_data(scan_url, scan_name):
    print(f"\n[ROBOT] Waking up to run: {scan_name}...")
    
    # --- ARMORED SETUP (Fixes Hex Code Crashes) ---
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")                  # <--- FIX 1
    options.add_argument("--no-sandbox")                   # <--- FIX 2
    options.add_argument("--disable-software-rasterizer")  # <--- FIX 3
    options.add_argument("--disable-dev-shm-usage")        # <--- FIX 4
    options.add_experimental_option("detach", True) 
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        # A. Login
        print("[ROBOT] Logging in...")
        driver.get("https://chartink.com/login")
        
        wait = WebDriverWait(driver, 25)
        
        # Wait for email box
        email_box = wait.until(EC.element_to_be_clickable((By.NAME, "email")))
        time.sleep(1)
        email_box.clear()
        email_box.send_keys(CHARTINK_EMAIL)
        
        pass_box = driver.find_element(By.NAME, "password")
        pass_box.clear()
        pass_box.send_keys(CHARTINK_PASSWORD)
        
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(3) 
        
        # B. Run Scan
        print(f"[ROBOT] Navigating to {scan_name}...")
        driver.get(scan_url)
        
        # Wait for results
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "table-striped")))
        
        # C. Download CSV
        print("[ROBOT] Downloading data...")
        try:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'CSV')]")))
            btn.click()
        except:
            print("Standard button not found, trying icon...")
            driver.find_element(By.XPATH, "//i[contains(@class,'fa-file-excel-o')]").click()

        time.sleep(5) 

        # D. Move & Rename File
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        files = [os.path.join(downloads, f) for f in os.listdir(downloads)]
        files.sort(key=os.path.getmtime)
        
        if not files:
            print("[ERROR] No files found in Downloads folder.")
            return

        newest_file = files[-1]
        
        target = os.path.join(os.getcwd(), "chartink.csv")
        if os.path.exists(target): os.remove(target)
        shutil.move(newest_file, target)
        print(f"[SUCCESS] Data saved to {target}")
        
        driver.quit() # Close browser only if successful
        
    except Exception as e:
        print(f"[ERROR] Robot failed. Browser kept open.")
        print(f"Error Message: {e}")

# ==============================================================================
# 3. THE ANALYST (WEINSTEIN MATH)
# ==============================================================================
def run_analysis():
    print("\n[ANALYST] processing data...")
    filename = "chartink.csv"
    
    if not os.path.exists(filename):
        print("[ERROR] No data file found. Did the robot fail?")
        return

    # Load Data
    try:
        df_input = pd.read_csv(filename)
        col_name = 'Symbol' if 'Symbol' in df_input.columns else df_input.columns[0]
        raw_symbols = df_input[col_name].astype(str).str.strip().tolist()
        stocks = [f"{sym}.NS" if not sym.endswith('.NS') else sym for sym in raw_symbols]
        print(f"[ANALYST] Found {len(stocks)} candidates.")
    except Exception as e:
        print(f"[ERROR] Reading CSV: {e}")
        return

    # Fetch Market Data
    all_tickers = stocks + [BENCHMARK_SYMBOL]
    data = yf.download(all_tickers, period="1y", interval="1wk", group_by='ticker', progress=False, ignore_tz=True)
    
    results = []
    
    try:
        bench_close = data[BENCHMARK_SYMBOL]['Close']
    except:
        print("[ERROR] Could not fetch Nifty data.")
        return

    for ticker in stocks:
        try:
            df = data[ticker].copy()
            if df.empty: continue
            
            # --- MATH ---
            df['SMA_30'] = df['Close'].rolling(window=30).mean()
            df['SMA_Slope'] = df['SMA_30'].diff(3)
            
            df['RS_Ratio'] = df['Close'] / bench_close
            df['RS_Base'] = df['RS_Ratio'].rolling(window=30).mean()
            df['Mansfield_RS'] = ((df['RS_Ratio'] / df['RS_Base']) - 1) * 10
            
            # Volume
            df['Vol_SMA'] = df['Volume'].rolling(window=10).mean()
            curr_vol = df['Volume'].iloc[-1]
            avg_vol = df['Vol_SMA'].iloc[-1]
            rvol = curr_vol / avg_vol if avg_vol > 0 else 0.0
            
            # Score
            current = df.iloc[-1]
            score = 0
            if current['Close'] > current['SMA_30']: score += 1
            if df['SMA_Slope'].iloc[-1] > 0: score += 1
            if current['Mansfield_RS'] > 0: score += 1

            results.append({
                'Symbol': ticker.replace('.NS', ''),
                'Close': round(current['Close'], 2),
                'Mansfield_RS': round(current['Mansfield_RS'], 2),
                'RVOL': round(float(rvol), 2),
                'Score': score
            })
        except:
            continue

    # Export Logic
    final_df = pd.DataFrame(results)
    if not final_df.empty:
        # Filter for Score 3
        top_picks = final_df[final_df['Score'] == 3].sort_values(by='Mansfield_RS', ascending=False)
        
        # Save Top 12
        output_file = "strike_watchlist.csv"
        top_picks.head(12)[['Symbol']].to_csv(output_file, index=False)
        
        print("\n" + "="*40)
        print(" ANALYSIS COMPLETE ")
        print("="*40)
        print(top_picks.head(5))
        print(f"\n[SUCCESS] 'strike_watchlist.csv' created.")
    else:
        print("[INFO] No stocks passed criteria.")

# ==============================================================================
# 4. COMMAND CENTER
# ==============================================================================
if __name__ == "__main__":
    print("\n" + "="*40)
    print(" WEINSTEIN TRADING SYSTEM ")
    print("="*40)
    print("1. WEEKEND HUNTER")
    print("2. DAILY PULLBACK")
    print("3. MANUAL MODE (I have downloaded chartink.csv myself)")
    print("="*40)
    
    choice = input("Enter choice (1-3): ")
    
    if choice == "1":
        fetch_chartink_data(URL_HUNTER, "Stage 2 Hunter")
        run_analysis()
    elif choice == "2":
        fetch_chartink_data(URL_PULLBACK, "Stage 2 Pullback")
        run_analysis()
    elif choice == "3":
        run_analysis()
    else:
        print("Invalid choice.")