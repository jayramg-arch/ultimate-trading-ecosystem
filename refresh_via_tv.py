"""Populate data_provider cache with DEEP history via TradingView (primary)
and nselib (fallback). Replaces refresh_via_nse.py.

After this, subsequent data_provider.fetch_ohlcv(symbol, period=..., interval=...)
returns the deeper history written here.
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import data_provider as dp
import bull_screener as _bs
import validation as v
import tv_ohlcv as tv
import nse_ohlcv as nse

UNIVERSE = "nifty500"
N_BARS_D = 1500  # ~6y daily
N_BARS_W = 500   # ~10y weekly


def _populate(symbol: str) -> tuple[bool, str, int]:
    """Fetch via TV (primary), fall back to NSE. Write to data_provider cache.

    Returns (success, source, n_daily_bars)."""
    df_d = tv.fetch_daily(symbol, n_bars=N_BARS_D)
    df_w = tv.fetch_weekly(symbol, n_bars=N_BARS_W)
    source = "TV"
    if df_d.empty or df_w.empty:
        # Fallback to nselib
        df_d2 = nse.fetch_daily(symbol, years=5) if df_d.empty else df_d
        df_w2 = nse.fetch_weekly(symbol, years=5) if df_w.empty else df_w
        if df_d2.empty:
            return False, "FAIL", 0
        df_d, df_w = df_d2, df_w2
        source = "NSE"
    yf_sym = _bs.to_yf(symbol)
    for period in ("2y", "3y", "5y"):
        key = dp._cache_key(yf_sym, period, "1d", True)
        dp._write_cache(key, df_d, period, "1d", True)
    for period in ("3y", "5y"):
        key = dp._cache_key(yf_sym, period, "1wk", True)
        dp._write_cache(key, df_w, period, "1wk", True)
    return True, source, len(df_d)


def main():
    syms = v.default_universe(UNIVERSE)
    targets = syms + ["^CRSLDX"]
    print(f"Populating data_provider cache  primary: TV  fallback: NSE")
    print(f"  Universe: {UNIVERSE} ({len(syms)} stocks) + 1 benchmark")
    print(f"  Depth: {N_BARS_D} daily bars (~6y), {N_BARS_W} weekly bars (~10y)")
    t0 = time.time()
    counts = {"TV": 0, "NSE": 0, "FAIL": 0}
    bars_total = 0
    for i, sym in enumerate(targets, 1):
        try:
            ok, source, n = _populate(sym)
        except Exception as e:
            ok, source, n = False, "FAIL", 0
            print(f"  [{i:3d}] {sym}: EXC {e}")
        counts[source] += 1
        bars_total += n
        if i % 50 == 0:
            elapsed = time.time() - t0
            print(f"  [{i:3d}/{len(targets)}] TV={counts['TV']} NSE={counts['NSE']} FAIL={counts['FAIL']} "
                  f"avg_bars={bars_total/max(1,counts['TV']+counts['NSE']):.0f} elapsed={elapsed:.0f}s",
                  flush=True)
    print(f"\nDone: TV={counts['TV']} NSE-fallback={counts['NSE']} FAIL={counts['FAIL']}, "
          f"{bars_total} total daily bars, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
