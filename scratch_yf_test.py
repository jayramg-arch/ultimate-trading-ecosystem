import yfinance as yf
import pandas as pd

symbols = ["RELIANCE", "INFY"]
_yf_tickers = " ".join([s + ".NS" for s in symbols])

_dl = yf.download(_yf_tickers, period="1y", progress=False)

hist_data = {}
for _s in symbols:
    _ysym = _s + ".NS"
    if len(symbols) == 1:
        _c = _dl["Close"] if "Close" in _dl.columns else pd.Series()
    else:
        if "Close" in _dl.columns and _ysym in _dl["Close"]:
            _c = _dl["Close"][_ysym]
        else:
            _c = pd.Series()
    
    _c = _c.dropna()
    print(_s, len(_c))
    if len(_c) >= 200:
        _sma50 = _c.rolling(50).mean().iloc[-1]
        _sma200 = _c.rolling(200).mean().iloc[-1]
        _sma200_10d_ago = _c.rolling(200).mean().shift(10).iloc[-1]
        _sma200slp = ((_sma200 - _sma200_10d_ago) / _sma200_10d_ago) * 100 if _sma200_10d_ago else 0
        _hi52 = _c.rolling(252).max().iloc[-1]
        _lo52 = _c.rolling(252).min().iloc[-1]
        _ltp = _c.iloc[-1]
        
        _ws_above200 = _ltp > _sma200
        _ws_above50 = _ltp > _sma50
        _ws_pos52 = ((_ltp - _lo52) / max(_hi52 - _lo52, 1)) * 100 if _hi52 > _lo52 else 50
        _ws_score = (
            (25 if _ws_above200 and _sma200slp > 0 else 0) +
            (20 if _ws_above200 else 0) +
            (15 if _sma200slp > 0 else 0) +
            (12 if _ws_pos52 >= 75 else 6 if _ws_pos52 >= 50 else 0) +
            (8  if _ws_above50  else 0)
        )
        
        hist_data[_s] = {
            "ws_score": int(_ws_score),
            "sma200_slope": round(_sma200slp, 2),
            "sma200": round(_sma200, 2),
            "sma50": round(_sma50, 2),
        }

print(hist_data)
