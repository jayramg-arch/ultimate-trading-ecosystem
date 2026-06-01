import os
from dotenv import load_dotenv
from dhanhq import dhanhq
import json

load_dotenv()
dhan = dhanhq(os.getenv("DHAN_CLIENT_ID"), os.getenv("DHAN_ACCESS_TOKEN"))

print("--- FUND LIMITS ---")
f_resp = dhan.get_fund_limits()
print(json.dumps(f_resp, indent=2))

print("\n--- HOLDINGS ---")
h_resp = dhan.get_holdings()
if h_resp.get('status') == 'success':
    # Show first item to see keys
    if h_resp.get('data'):
        print(json.dumps(h_resp['data'][0], indent=2))
    else:
        print("No holdings data found.")
else:
    print(f"Error: {h_resp}")
