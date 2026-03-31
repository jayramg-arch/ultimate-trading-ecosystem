import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import time

# ==========================================
# 1. SETUP & UTILS
# ==========================================
SECTOR_DB_FILE = "sector_db.json"
CHARTINK_FILE = "chartink.csv"
OUTPUT_FILE = "pullback_candidates.csv"

def load_tickers():
    """
    Loads tickers from sector_db.json (Preferred) or chartink.csv.
    Returns a list of yfinance-ready symbols (e.g., 'RELIANCE.NS').
    """
    stocks = []
    
    # Method 1: Sector DB (Best Source for Nifty 500)
    if os.path.exists(SECTOR_DB_FILE):
        print(f"Reading {SECTOR_DB_FILE}...")
        try:
            with open(SECTOR_DB_FILE, 'r') as f:
                data = json.load(f)
                # Keys are 'NSE:TCS'. Need 'TCS.NS'
                for k in data.keys():
                    clean = k.replace("NSE:", "") + ".NS"
                    stocks.append(clean)
            print(f"Loaded {len(stocks)} stocks from Sector DB.")
        except Exception as e:
            print(f"Error reading Sector DB: {e}")

    # Method 2: Chartink CSV (Fallback or Supplement)
    if not stocks and os.path.exists(CHARTINK_FILE):
        print(f"Reading {CHARTINK_FILE}...")
        try:
            df = pd.read_csv(CHARTINK_FILE)
            if 'Symbol' in df.columns:
                raw = df['Symbol'].tolist()
                stocks = [f"{s}.NS" for s in raw]
            elif 'NSE Code' in df.columns:
                raw = df['NSE Code'].tolist()
                stocks = [f"{s}.NS" for s in raw]
            print(f"Loaded {len(stocks)} stocks from Chartink CSV.")
        except Exception as e:
            print(f"Error reading Chartink CSV: {e}")

    if not stocks:
        # Emergency Fallback: Top 10 for testing
        print("No source files found. Using default Top 10.")
        stocks = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "TRENT.NS", "HAL.NS", "BEL.NS", "TATAMOTORS.NS", "SBIN.NS"]

    return list(set(stocks)) # Remove duplicates

# ==========================================
# 2. ANALYSIS LOGIC
# ==========================================
def calculate_metrics(df):
    """
    Calculates SMAs, EMAs, RSI, and Volume metrics on a Daily DataFrame.
    Returns the modified DF.
    """
    # Price SMAs
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_150'] = df['Close'].rolling(window=150).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    
    # EMA 20 (The Magnet)
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Volume MA (50)
    df['Vol_SMA_50'] = df['Volume'].rolling(window=50).mean()
    
    return df

def get_weekly_rsi(df_daily):
    """
    Resamples Daily data to Weekly to calculate Weekly RSI.
    """
    # Resample to Weekly (W-FRI)
    logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
    df_weekly = df_daily.resample('W-FRI').apply(logic)
    
    # Calc RSI
    delta = df_weekly['Close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean() # Wilder's Smoothing usually preferred for RSI, or simple rolling
    # Using Simple Rolling for consistency with common libraries
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df_weekly['RSI_W'] = 100 - (100 / (1 + rs))
    
    return df_weekly['RSI_W']

def scan_market(tickers):
    print(f"Scanning {len(tickers)} stocks... (This may take a minute)")
    
    # Download Data Batch
    # Period: 2y to ensure enough data for 200 SMA + Weekly RSI
    data = yf.download(tickers, period="2y", interval="1d", group_by='ticker', progress=True, ignore_tz=True)
    
    candidates = []
    
    for ticker in tickers:
        try:
            # Handle Single Ticker vs Multi Ticker structure
            if len(tickers) == 1:
                df = data
            else:
                df = data[ticker].copy()
            
            if df.empty: continue
            
            # Remove NaN rows
            df.dropna(inplace=True)
            if len(df) < 200: continue
            
            # 1. Calc Indicators
            df = calculate_metrics(df)
            
            # 2. Get Weekly RSI (Last value)
            w_rsi_series = get_weekly_rsi(df)
            if w_rsi_series.empty: continue
            cur_w_rsi = w_rsi_series.iloc[-1]
            
            # Getting current (latest) Daily values
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # --- CRITERIA CHECKS ---
            
            # A. Trend Template (Stage 2)
            # Price > 150 > 200, 50 > 150
            trend_ok = (curr['Close'] > curr['SMA_150']) and \
                       (curr['Close'] > curr['SMA_200']) and \
                       (curr['SMA_150'] > curr['SMA_200']) and \
                       (curr['SMA_50'] > curr['SMA_150'])
            
            # B. Momentum
            # Daily RSI > 40, Weekly RSI > 60
            mom_ok = (curr['RSI'] > 40) and (cur_w_rsi > 60)
            
            # C. Pullback (EMA 20 Zone)
            # Price is within X% of EMA 20
            # User Criteria: "Price touches/nears the Daily EMA 20 zone"
            # We check if Low <= EMA 20 * 1.015 (Top of zone) AND High >= EMA 20 * 0.985 (Bottom of zone)
            # Basically, did the price bar intersect the zone? 
            # Or is the Close near it?
            ema = curr['EMA_20']
            dist_pct = (curr['Close'] - ema) / ema
            
            # Let's say "Near" is within +3% to -2% range? Or specifically retracing?
            # User: "Price retraces to the Daily EMA 20"
            # We want catch it when it involves the EMA.
            # Strict: Low <= EMA * 1.015 and Close > EMA * 0.95
            pullback_ok = (curr['Low'] <= ema * 1.02) and (curr['Close'] >= ema * 0.98)
            
            # D. Volume Dry Up (VDU)
            # "Volume on down-days (red candles) must be lower than 50-period Volume MA"
            # Check Today: If Red, Vol < MA?
            # Or Check Prev Day: If Red, Vol < MA?
            # We pass if *current* condition is not a "High Vol Distribution".
            is_red = curr['Close'] < curr['Open']
            vol_ok = True
            if is_red:
                vol_ok = curr['Volume'] < (curr['Vol_SMA_50'] * 0.8) # 20% lower ideally
            
            # Final Filter
            if trend_ok and mom_ok and pullback_ok and vol_ok:
                candidates.append({
                    'Symbol': ticker.replace(".NS", ""),
                    'Close': round(curr['Close'], 2),
                    'EMA_20': round(curr['EMA_20'], 2),
                    'Dist_EMA%': round(dist_pct * 100, 2),
                    'RSI_D': round(curr['RSI'], 1),
                    'RSI_W': round(cur_w_rsi, 1),
                    'Vol_Rel': round(curr['Volume'] / curr['Vol_SMA_50'], 2)
                })
                
        except Exception as e:
            continue
            
    return pd.DataFrame(candidates)

# ==========================================
# 3. EXECUTION
# ==========================================
if __name__ == "__main__":
    print("="*50)
    print("NSE INSTITUTIONAL PULLBACK SCANNER")
    print("="*50)
    
    # 1. Load Universe
    tickers = load_tickers()
    
    # 2. Scan
    results = scan_market(tickers)
    
    # 3. Save
    if not results.empty:
        # Sort by proximity to EMA 20? Or Strength?
        # Let's sort by Weekly RSI (Strength)
        results = results.sort_values(by='RSI_W', ascending=False)
        
        results.to_csv(OUTPUT_FILE, index=False)
        print(f"\n[SUCCESS] Found {len(results)} candidates.")
        print(results.head(10))
        print(f"Saved to: {os.getcwd()}\\{OUTPUT_FILE}")
        print("ACTION: Copy the 'Symbol' column to TradingView Watchlist.")
    else:
        print("\n[INFO] No stocks matched the strict Stage 2 + Pullback criteria today.")
