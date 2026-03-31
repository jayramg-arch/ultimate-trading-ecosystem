import json
import re
import yfinance as yf
import pandas as pd
from datetime import datetime

INPUT_FILE = "portfolio_data.json"
OUTPUT_FILE = "deep_analysis.json"

def clean_value(val_str):
    if not val_str: return 0.0
    # specific fix for comma decimals if any
    val_str = val_str.replace(',', '')
    try:
        return float(val_str)
    except:
        return 0.0

def analyze_portfolio():
    print("🧠 Starting Professional Analysis Engine...")
    
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        
    analysis_results = []
    
    # Batch keys for yfinance to be faster? 
    # yfinance handles one by one okay for 20 items.
    
    for symbol, lines in raw_data.items():
        if not lines:
            print(f"⚠️ Skipping {symbol} (No Dashboard Data)")
            continue
            
        data_line = lines[0]
        print(f"🔍 Analyzing {symbol}...")
        
        # 1. Parsing Dashboard Data
        # -------------------------
        rrg_status = "Unknown"
        entry_price = 0.0
        stop_loss = 0.0
        target_1 = 0.0
        
        # Extract RRG
        rrg_match = re.search(r"RRG=([\w\-\(\)+]+)", data_line)
        if rrg_match: rrg_status = rrg_match.group(1)
        
        # Extract Levels
        # Handles "Entry#1=123.45"
        e_match = re.search(r"Entry#1=([\d\.,]+)", data_line)
        sl_match = re.search(r"SL#1=([\d\.,]+)", data_line)
        t1_match = re.search(r"Tgt#1=([\d\.,]+)", data_line)
        
        if e_match: entry_price = clean_value(e_match.group(1))
        if sl_match: stop_loss = clean_value(sl_match.group(1))
        if t1_match: target_1 = clean_value(t1_match.group(1))
        
        # 2. Fetch Market Context (YFinance)
        # ----------------------------------
        # Append .NS for NSE stocks
        yf_ticker = f"{symbol}.NS"
        stock = yf.Ticker(yf_ticker)
        
        # Get last 1 year for broad context (200 SMA)
        hist = stock.history(period="1y")
        
        if hist.empty:
            print(f"   ❌ No market data for {yf_ticker}")
            current_price = entry_price # Fallback to avoid div/0
            sma50 = 0
            sma200 = 0
            vol_avg = 0
        else:
            current_price = hist['Close'].iloc[-1]
            hist['SMA50'] = hist['Close'].rolling(window=50).mean()
            hist['SMA200'] = hist['Close'].rolling(window=200).mean()
            
            sma50 = hist['SMA50'].iloc[-1]
            sma200 = hist['SMA200'].iloc[-1]
            vol_avg = hist['Volume'].iloc[-20:].mean() # 20 day avg vol

        # 3. synthesize the "Verdict"
        # ---------------------------
        verdict = "HOLD"
        reason = "Neutral price action."
        color = "grey"
        
        # A. Stop Loss Check (Critical)
        if stop_loss > 0 and current_price < stop_loss:
            verdict = "SELL / EXIT"
            reason = f"⛔ Price ({current_price:.2f}) violated Stop Loss ({stop_loss:.2f}). Breakdown confirmed."
            color = "red"
            
        # B. Target Check
        elif target_1 > 0 and current_price >= target_1:
            verdict = "PARTIAL PROFIT"
            reason = f"🎯 Target 1 ({target_1:.2f}) achieved. Secure gains."
            color = "orange"
            
        # C. Trend Analysis (Weinstein Stage 2 Logic)
        else:
            # Is it in Stage 2? (Price > SMA50 > SMA200 recommended, but mainly Price > SMA30 weekly)
            # We use Daily SMA50/200 as proxy.
            
            trend_strength = "Neutral"
            if current_price > sma200:
                trend_strength = "Bullish"
                if current_price > sma50:
                    trend_strength = "Strong Bullish"
            elif current_price < sma200:
                trend_strength = "Bearish"
                
            # Combine with RRG
            # Leading (LE) + Bullish Trend = STRONG BUY/ADD
            if "LE" in rrg_status and "Weakening" not in rrg_status and trend_strength == "Strong Bullish":
                verdict = "ADD / BUY"
                reason = f"🚀 Strong Momentum. RRG Leading & Price > SMA50/200."
                color = "green"
                
            # Weakening (W) + Price dropping = CAUTION
            elif "Weakening" in rrg_status or "W-" in rrg_status:
                verdict = "CAUTION / TRIM"
                reason = f"⚠️ Momentum loss (RRG Weakening). Tighten stops."
                color = "yellow"
                
            # Improving (I) + Price > Entry = EARLY ENTRY
            elif "I-" in rrg_status or "Improving" in rrg_status:
                if current_price > entry_price:
                    verdict = "ACCUMULATE"
                    reason = "📈 Improving Sector rotation. Early stage breakout."
                    color = "blue"

        # Calculate P&L if we have entry
        pnl_pct = 0.0
        if entry_price > 0:
            pnl_pct = ((current_price - entry_price) / entry_price) * 100

        # Construct Record
        record = {
            "Symbol": symbol,
            "CMP": round(current_price, 2),
            "P&L": round(pnl_pct, 2),
            "RRG": rrg_status,
            "Entry": entry_price,
            "SL": stop_loss,
            "SMA200": round(sma200, 2),
            "Verdict": verdict,
            "Reason": reason,
            "Raw": data_line,
            "Color": color
        }
        analysis_results.append(record)

    # Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(analysis_results, f, indent=4)
        
    print(f"✅ Deep Analysis Complete. Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    analyze_portfolio()
