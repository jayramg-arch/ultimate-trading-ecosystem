import yfinance as yf
import pandas as pd

symbols = ["HDFCSML250.NS", "METALIETF.NS", "HDFCSML250", "METALIETF"]

for sym in symbols:
    print(f"Testing {sym}...")
    try:
        data = yf.download(sym, period="1mo", interval="1d", progress=False)
        if data.empty:
            print(f"  FAILED: Data is empty for {sym}")
        else:
            print(f"  SUCCESS: Data found for {sym}. Last Close: {data['Close'].iloc[0]['Close'] if isinstance(data['Close'], pd.DataFrame) else data['Close'].iloc[-1]}")
    except Exception as e:
        print(f"  ERROR for {sym}: {e}")
