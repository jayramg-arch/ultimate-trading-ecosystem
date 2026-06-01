import yfinance as yf
import pandas as pd

symbols = ["HDFCSML250.NS", "METALIETF.NS", "HDFCSML250", "METALIETF"]

for sym in symbols:
    print(f"\n--- Testing {sym} ---")
    try:
        data = yf.download(sym, period="1mo", interval="1d", progress=False)
        if data.empty:
            print(f"  FAILED: Data is empty for {sym}")
        else:
            print(f"  SUCCESS: Data found for {sym}")
            print(f"  Columns: {data.columns.tolist()}")
            # Handle multi-index columns if they exist
            if isinstance(data.columns, pd.MultiIndex):
                print("  MultiIndex detected.")
                # Look for 'Close' in the first level
                if 'Close' in data.columns.levels[0]:
                    close_val = data['Close'].iloc[-1].values[0]
                    print(f"  Last Close: {close_val}")
            elif 'Close' in data.columns:
                print(f"  Last Close: {data['Close'].iloc[-1]}")
            else:
                print("  'Close' column not found.")
    except Exception as e:
        print(f"  ERROR for {sym}: {e}")
