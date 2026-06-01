import sys
sys.path.insert(0, r"C:\Users\jayra\Documents\GeminiVSCode")
from nse_options_fetcher import fetch_option_chain_raw, parse_chain_summary

print("Testing NSE options fetch via Playwright...")
print("(First run opens headless Chromium ~3-5s)")
raw = fetch_option_chain_raw("NIFTY")
if raw:
    summary = parse_chain_summary(raw)
    rows = raw.get("records", {}).get("data", [])
    print(f"SUCCESS — {len(rows)} strikes fetched")
    print(f"  Spot        : {summary.get('spot_price')}")
    print(f"  PCR (OI)    : {summary.get('pcr_oi')}")
    print(f"  PCR (Vol)   : {summary.get('pcr_vol')}")
    print(f"  Max Pain    : {summary.get('max_pain_strike')}")
    print(f"  ATM IV      : {summary.get('atm_iv')}%")
    print(f"  Call Wall   : {summary.get('strongest_call_strike')}")
    print(f"  Put Wall    : {summary.get('strongest_put_strike')}")
    print(f"  Expiries    : {summary.get('expiry_dates', [])[:4]}")
    print(f"  Fetched at  : {summary.get('fetched_at')}")
else:
    print("FAILED — raw data is None")
