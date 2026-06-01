import sqlite3
import pandas as pd
import yfinance as yf
import numpy as np

DB_FILE = "trade_journal_v6.db"

def calculate_atr(df, period=14):
    """Calculates Average True Range"""
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    atr = true_range.rolling(period).mean()
    return atr.iloc[-1] if not atr.empty and not pd.isna(atr.iloc[-1]) else 0

def analyze_trades():
    print("Loading Nifty50 benchmark data (60d)...")
    try:
        nifty = yf.Ticker("^NSEI").history(period="60d")
        nifty['return'] = nifty['Close'].pct_change()
        nifty.index = nifty.index.tz_localize(None)
    except Exception as e:
        print(f"Failed to load Nifty50: {e}")
        nifty = pd.DataFrame()

    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT symbol, buy_price, stoploss, target, sector, status FROM journal", conn)
    conn.close()
    
    if df.empty:
        print("No trades found in journal.")
        return

    results = []
    print(f"Analyzing {len(df)} total trades...\n")

    for _, row in df.iterrows():
        symbol = row['symbol']
        buy_price = row['buy_price']
        sl = row['stoploss']
        status = row['status'].upper() if row['status'] else 'UNKNOWN'
        
        try:
            # Clean symbol for yfinance
            clean_sym = symbol.replace("NSE:", "").strip()
            ticker = yf.Ticker(f"{clean_sym}.NS")
            hist = ticker.history(period="60d")
            
            if hist.empty:
                continue
                
            hist.index = hist.index.tz_localize(None)
            ltp = hist['Close'].iloc[-1]
            atr_14 = calculate_atr(hist)
            
            # Correlation
            hist['return'] = hist['Close'].pct_change()
            correlation = "N/A"
            if not nifty.empty and len(hist) > 10:
                combined = pd.DataFrame({'stock': hist['return'], 'nifty': nifty['return']}).dropna()
                if len(combined) > 10:
                    corr = combined['stock'].corr(combined['nifty'])
                    correlation = round(corr, 2)
            
            pnl = (ltp - buy_price)
            pnl_pct = (pnl / buy_price) * 100 if buy_price > 0 else 0
            
            # Filter logically:
            # If OPEN and PnL >= 0, it's not a losing trade, so skip.
            # If CLOSED / STOPPED_OUT, include it to diagnose the historical setup.
            is_losing_open = (status == 'OPEN' and pnl < 0)
            is_closed = (status in ['CLOSED', 'STOPPED_OUT', 'STOP_LOSS'])
            
            if is_losing_open or is_closed:
                # ATR Multiples (Absolute math)
                stop_distance = buy_price - sl if sl > 0 else 0
                atr_multiple = round(stop_distance / atr_14, 2) if atr_14 > 0 else 0
                
                results.append({
                    'Symbol': symbol,
                    'Status': status,
                    'Buy Price': buy_price,
                    # For closed trades, LTP is just where it's at today, so label it 'Current Price'
                    'Current Price': round(ltp, 2),
                    'Current Unrealized PnL%': round(pnl_pct, 2) if status == 'OPEN' else 'N/A (Closed)',
                    'Stop Loss': sl,
                    'ATR (14d)': round(atr_14, 2),
                    'SL Distance (ATR)': atr_multiple,
                    'Nifty Correlation': correlation
                })
        except Exception:
            pass

    if not results:
        print("No losing/closed trades returned for analysis.")
    else:
        print("="*70)
        print("                   TRADE DIAGNOSTIC REPORT")
        print("="*70)
        
        for res in results:
            print(f"[{res['Symbol']}] - Status: {res['Status']}")
            if res['Status'] == 'OPEN':
                print(f"   📉 PnL: {res['Current Unrealized PnL%']}% (Buy: {res['Buy Price']} | LTP: {res['Current Price']})")
            else:
                print(f"   🔒 Trade Closed (Buy: {res['Buy Price']} | Original SL: {res['Stop Loss']})")
            
            sl_atr = res['SL Distance (ATR)']
            if sl_atr == 0:
                quant_msg = "⚠️ No valid initial Stop Loss found."
            elif sl_atr < 1.5:
                quant_msg = f"⚠️ SL placed at {sl_atr}x ATR. VERY TIGHT. High risk of getting stopped by purely market noise."
            elif sl_atr < 2.5:
                quant_msg = f"✅ SL placed at {sl_atr}x ATR. Mathematically sound buffer against noise."
            else:
                quant_msg = f"⚠️ SL placed at {sl_atr}x ATR. VERY WIDE. Suboptimal risk-reward ratio."
            print(f"   ⚖️  Quant Insight  -> {quant_msg}")
            
            corr = res['Nifty Correlation']
            if corr == "N/A":
                mkt_msg = "Insufficient data for correlation."
            elif isinstance(corr, float):
                if corr > 0.70:
                    mkt_msg = f"High positive correlation ({corr}). Asset weakness is highly systemic/market-driven."
                elif corr < 0.30:
                    mkt_msg = f"Low correlation ({corr}). Asset setup failing independently of broad market."
                else:
                    mkt_msg = f"Moderate positive correlation ({corr}). Mix of market drag and specific weakness."
            else:
                mkt_msg = str(corr)
            print(f"   📊 Market Insight -> {mkt_msg}")
            print("-" * 70)

if __name__ == "__main__":
    analyze_trades()
