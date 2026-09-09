"""Force-refresh OHLCV cache back to 5 years for Nifty 500 + benchmark,
then re-run the bull-regime backtest (Dec 2023 - Nov 2024)."""
import time, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import data_provider as dp
import bull_screener as _bs
import validation as v

UNIVERSE = "nifty500"
PERIOD_DAILY = "5y"
PERIOD_WEEKLY = "5y"

def refresh_cache():
    syms = v.default_universe(UNIVERSE)
    benches = ["^CRSLDX"]
    print(f"Refreshing {len(syms) + len(benches)} symbols with 5y of daily+weekly data...")
    t0 = time.time()
    refreshed = failed = 0
    for i, sym in enumerate(syms + benches, 1):
        yf_sym = _bs.to_yf(sym)
        try:
            dp.fetch_ohlcv(yf_sym, period=PERIOD_DAILY,  interval="1d",  use_cache=False)
            dp.fetch_ohlcv(yf_sym, period=PERIOD_WEEKLY, interval="1wk", use_cache=False)
            refreshed += 1
        except Exception as e:
            failed += 1
            print(f"  [{i:3d}] {sym}: FAIL {e}")
        if i % 50 == 0:
            elapsed = time.time() - t0
            print(f"  [{i:3d}/{len(syms)+len(benches)}] refreshed={refreshed} failed={failed} elapsed={elapsed:.0f}s")
    print(f"Done: {refreshed} refreshed, {failed} failed, {time.time()-t0:.0f}s total")

if __name__ == "__main__":
    print("="*70)
    print("PHASE 1: Cache refresh")
    print("="*70)
    refresh_cache()
    print()
    print("="*70)
    print("PHASE 2: Re-run regime test")
    print("="*70)
    import validate_bull_regime as vbr
    vbr.main()
