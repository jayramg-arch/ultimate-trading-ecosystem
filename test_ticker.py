import yfinance as yf

# Common variants for Indian 10 year bond yield
tickers = [
    '^IN10YT',       # Usually correct but spotty
    'IN10YT=RR',     # Reuters variant
    'IN10YT=X',      # Yahoo finance currency variant
    'IN10Y=X',
    'IN10Y.BO',
    'IN10Y.NS',
    'IN10Y',
    'IND10Y=RR',
    'IN10YT.BO',
]

for t in tickers:
    try:
        df = yf.Ticker(t).history(period='5d', timeout=5)
        if not df.empty:
            print(f'SUCCESS: {t}')
        else:
            print(f'EMPTY: {t}')
    except Exception as e:
        print(f'ERROR: {t} failed to fetch - {e}')
