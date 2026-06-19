import yfinance as yf
import pandas as pd

# Route OHLCV through the Dhan-first data_provider; yfinance stays as fallback.
try:
    import data_provider as _dp
    _USE_DP = True
except Exception:
    _dp = None
    _USE_DP = False


def _fetch(symbol_yf, symbol_clean, period):
    """data_provider first (Dhan), yfinance fallback. Returns titlecase OHLCV."""
    if _USE_DP and _dp is not None:
        try:
            df = _dp.fetch_ohlcv(symbol_clean, period=period, interval="1d")
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass
    data = yf.download(symbol_yf, period=period, interval="1d", progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data


def get_technical_context(symbol):
    try:
        data = _fetch(f"{symbol}.NS", symbol, "3mo")
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
        data = _fetch("^CRSLDX", "^CRSLDX", "1y")
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
