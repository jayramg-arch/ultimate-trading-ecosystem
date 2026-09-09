"""Force-refresh data_provider cache with DEEP history via nselib.

Fetches 5 years of daily OHLCV per symbol directly from NSE India (nselib),
then writes it into the data_provider cache using the same keys yfinance
would. After this, subsequent data_provider.fetch_ohlcv(...) calls will
return the deeper history.
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import data_provider as dp
import bull_screener as _bs
import validation as v
import nse_ohlcv as nse

UNIVERSE = "nifty500"
YEARS    = 5
DELAY_S  = 0.15   # gentle on NSE


def _populate(symbol: str) -> tuple[bool, int]:
    """Fetch via nselib and write to data_provider cache for both period+interval combos used."""
    df_d = nse.fetch_daily(symbol, years=YEARS)
    if df_d.empty:
        return False, 0
    df_w = nse.fetch_weekly(symbol, years=YEARS)
    # Write daily under the period='2y' key (what bull_screener uses)
    yf_sym = _bs.to_yf(symbol)
    for period, df in [("2y", df_d), ("3y", df_d), ("5y", df_d)]:
        key = dp._cache_key(yf_sym, period, "1d", True)
        dp._write_cache(key, df, period, "1d", True)
    # Weekly under '3y' / '5y' keys
    for period, df in [("3y", df_w), ("5y", df_w)]:
        key = dp._cache_key(yf_sym, period, "1wk", True)
        dp._write_cache(key, df, period, "1wk", True)
    return True, len(df_d)


def main():
    syms = v.default_universe(UNIVERSE)
    benches = ["^CRSLDX"]
    targets = syms + benches
    print(f"Populating data_provider cache via nselib")
    print(f"  Universe: {UNIVERSE} ({len(syms)} stocks) + {len(benches)} bench(es)")
    print(f"  Depth: {YEARS} years daily + resampled weekly")
    t0 = time.time()
    ok = fail = 0
    bars_total = 0
    for i, sym in enumerate(targets, 1):
        success, n_bars = False, 0
        try:
            success, n_bars = _populate(sym)
        except Exception as e:
            print(f"  [{i:3d}] {sym}: FAIL {e}")
        if success:
            ok += 1
            bars_total += n_bars
        else:
            fail += 1
        if i % 25 == 0:
            elapsed = time.time() - t0
            avg_bars = bars_total / max(1, ok)
            print(f"  [{i:3d}/{len(targets)}] ok={ok} fail={fail} avg_bars={avg_bars:.0f} elapsed={elapsed:.0f}s",
                  flush=True)
        time.sleep(DELAY_S)
    print(f"\nDone: {ok} populated, {fail} failed, {bars_total} total bars, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
