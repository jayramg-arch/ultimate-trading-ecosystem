"""Probe JdK values for GESHIP via the SAME data path bull_screener.py uses
(data_provider.fetch_ohlcv -> parquet cache). If the cache is stale, this
will show different last-bar dates than a fresh yfinance pull."""
import numpy as np
import pandas as pd

import data_provider as _dp
from bull_screener import _flatten_cols, compute_weekly_indicators

SYM   = "GESHIP.NS"
BENCH = "^CRSLDX"

print("=== via data_provider (screener path) ===")
df_w = _flatten_cols(_dp.fetch_ohlcv(SYM,   period="3y", interval="1wk"))
df_b = _flatten_cols(_dp.fetch_ohlcv(BENCH, period="3y", interval="1wk"))
print(f"  stock bars={len(df_w)}, last={df_w.index[-1].date() if not df_w.empty else 'n/a'}, last_close={float(df_w['Close'].iloc[-1]):.2f}")
print(f"  bench bars={len(df_b)}, last={df_b.index[-1].date() if not df_b.empty else 'n/a'}, last_close={float(df_b['Close'].iloc[-1]):.2f}")

weekly = compute_weekly_indicators(df_w, df_b)
print(f"  --> mansfield (=RS_Ratio-100): {weekly['mansfield']:.2f}  -->  RS_Ratio={weekly['mansfield']+100:.2f}")
print(f"  --> mansfield_4w (=RS_Mom-100): {weekly['mansfield_4w']:.2f}  -->  RS_Mom={weekly['mansfield_4w']+100:.2f}")
print(f"  --> Quadrant: {weekly['rrg_quadrant']}")

print()
print("=== same code path with fresh data_provider ===")
import data_provider as dp
ys = dp.fetch_ohlcv(SYM,   period="3y", interval="1wk", use_cache=False, auto_adjust=True)
yb = dp.fetch_ohlcv(BENCH, period="3y", interval="1wk", use_cache=False, auto_adjust=True)
ys = _flatten_cols(ys); yb = _flatten_cols(yb)
print(f"  stock bars={len(ys)}, last={ys.index[-1].date()}, last_close={float(ys['Close'].iloc[-1]):.2f}")
print(f"  bench bars={len(yb)}, last={yb.index[-1].date()}, last_close={float(yb['Close'].iloc[-1]):.2f}")
weekly2 = compute_weekly_indicators(ys, yb)
print(f"  --> RS_Ratio={weekly2['mansfield']+100:.2f}, RS_Mom={weekly2['mansfield_4w']+100:.2f}, Quadrant={weekly2['rrg_quadrant']}")
