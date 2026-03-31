import yfinance as yf
import pandas as pd
import numpy as np
import os

# ==========================================
# 1. SETUP: AUTO-READ CHARTINK FILE
# ==========================================
filename = "chartink.csv"
benchmark_symbol = "^NSEI"

stocks = []

print(f"\n--- STEP 1: Reading {filename} ---")
try:
    # Read the file downloaded from Chartink
    df_input = pd.read_csv(filename)
    
    # Chartink CSVs have a column named 'Symbol'. We grab that list.
    # We strip spaces to be safe.
    if 'Symbol' in df_input.columns:
        raw_symbols = df_input['Symbol'].astype(str).str.strip().tolist()
    else:
        # Fallback if column is named differently (e.g. 'NSE Code')
        raw_symbols = df_input.iloc[:, 0].astype(str).str.strip().tolist()

    # ADD '.NS' SUFFIX for yfinance (Chartink gives "NALCO", yfinance needs "NALCO.NS")
    # We check if '.NS' is already there to avoid duplicates
    stocks = [f"{sym}.NS" if not sym.endswith('.NS') else sym for sym in raw_symbols]
    
    print(f"[SUCCESS] Loaded {len(stocks)} stocks from {filename}.")
    print(f"List: {stocks[:3]} ...")

except FileNotFoundError:
    print(f"\n[ERROR] Could not find '{filename}'!")
    print(f"-> Please download the Chartink results to: {os.getcwd()}")
    print("-> Rename the file to 'chartink.csv'")
    exit() # Stop the script here
except Exception as e:
    print(f"[ERROR] Something went wrong reading the file: {e}")
    exit()

# ==========================================
# 2. ANALYSIS ENGINE
# ==========================================
def calculate_stage_analysis(tickers, benchmark):
    print(f"\n--- STEP 2: Fetching Data & Calculating ---")
    
    # Download Weekly Data (1 Year)
    # ignore_tz=True prevents cache errors
    all_tickers = tickers + [benchmark]
    data = yf.download(all_tickers, period="1y", interval="1wk", group_by='ticker', progress=False, ignore_tz=True)
    
    results = []
    
    # Process Benchmark
    try:
        bench_close = data[benchmark]['Close']
    except KeyError:
        print("[CRITICAL ERROR] Could not fetch Nifty 50 Data. Restart VS Code.")
        return pd.DataFrame()

    for ticker in tickers:
        try:
            df = data[ticker].copy()
            if df.empty: continue
            
            # --- CALCULATIONS ---
            # 1. Price vs 30-Week SMA
            df['SMA_30'] = df['Close'].rolling(window=30).mean()
            df['SMA_Slope'] = df['SMA_30'].diff(3)
            
            # 2. Mansfield Relative Strength
            df['RS_Ratio'] = df['Close'] / bench_close
            df['RS_Base'] = df['RS_Ratio'].rolling(window=30).mean()
            df['Mansfield_RS'] = ((df['RS_Ratio'] / df['RS_Base']) - 1) * 10
            
            # 3. Volume Analysis (RVOL)
            df['Vol_SMA'] = df['Volume'].rolling(window=10).mean()
            curr_vol = df['Volume'].iloc[-1]
            avg_vol = df['Vol_SMA'].iloc[-1]
            rvol = curr_vol / avg_vol if avg_vol > 0 else 0.0
            
            # --- SCORING (The Quality Control) ---
            current = df.iloc[-1]
            score = 0
            if current['Close'] > current['SMA_30']: score += 1
            if df['SMA_Slope'].iloc[-1] > 0: score += 1
            if current['Mansfield_RS'] > 0: score += 1

            # CLEAN SYMBOL NAME (Remove .NS for Strike export)
            clean_symbol = ticker.replace('.NS', '')

            results.append({
                'Symbol': clean_symbol,
                'Close': round(current['Close'], 2),
                'Mansfield_RS': round(current['Mansfield_RS'], 2),
                'RVOL': round(float(rvol), 2),
                'Score': score
            })
            
        except Exception:
            continue

    final_df = pd.DataFrame(results)
    if not final_df.empty:
        # Sort by Score (3 first), then by Strength (Highest RS first)
        final_df = final_df.sort_values(by=['Score', 'Mansfield_RS'], ascending=False)
    
    return final_df

# Run Analysis
analysis_df = calculate_stage_analysis(stocks, benchmark_symbol)

# Show User the Results
print("\n--- ANALYSIS RESULTS (Top 5) ---")
print(analysis_df.head(5))

# ==========================================
# 3. EXPORT TO STRIKE.MONEY
# ==========================================
print(f"\n--- STEP 3: Saving Top 12 for Strike.Money ---")

# Filter only the best stocks (Score = 3)
top_picks = analysis_df[analysis_df['Score'] == 3]

if not top_picks.empty:
    # 1. Take only the Top 12 (Sorted by Strength)
    top_12_only = top_picks.head(12)
    
    # 2. Select ONLY the 'Symbol' column
    strike_import = top_12_only[['Symbol']]
    
    # 3. Save to CSV
    output_filename = "strike_watchlist.csv"
    strike_import.to_csv(output_filename, index=False)
    
    print(f"[SUCCESS] Created file: {output_filename}")
    print(f"-> Contains {len(strike_import)} stocks (The Elite List).")
    print(f"-> Location: {os.getcwd()}\\{output_filename}")
    print("-> ACTION: Upload this file to Strike.Money Watchlist.")
else:
    print("[INFO] No stocks met the 'Score 3' criteria. No file created.")