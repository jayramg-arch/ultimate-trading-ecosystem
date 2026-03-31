import yfinance as yf
import pandas as pd

def get_technical_context(symbol):
    try:
        data = yf.download(f"{symbol}.NS", period="3mo", interval="1d", progress=False)
        if data.empty: return None
        
        # ATR 14
        high_low = data['High'] - data['Low']
        high_close = abs(data['High'] - data['Close'].shift())
        low_close = abs(data['Low'] - data['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        tr = ranges.max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        ltp = data['Close'].iloc[-1]
        
        return {
            'LTP': float(ltp),
            'ATR': float(atr)
        }
    except:
        return None

def check_market_health():
    try:
        data = yf.download("^CNX500", period="1y", interval="1d", progress=False)
        if data.empty: return "Unknown"
        
        sma200 = data['Close'].rolling(200).mean().iloc[-1]
        ltp = data['Close'].iloc[-1]
        
        status = "HEALTHY" if ltp > sma200 else "WEAK"
        return f"Nifty 500: {status} (LTP: {ltp:.0f} vs SMA200: {sma200:.0f})"
    except:
        return "Market Health Check Failed"

if __name__ == "__main__":
    print(check_market_health())
    for sym in ['AIAENG', 'COALINDIA']:
        ctx = get_technical_context(sym)
        if ctx:
            print(f"--- {sym} ---")
            print(f"LTP: {ctx['LTP']:.2f}")
            print(f"ATR (14d): {ctx['ATR']:.2f}")
            print(f"2x ATR Buffer: {2*ctx['ATR']:.2f}")
