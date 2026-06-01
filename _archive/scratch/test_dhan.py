import sys
sys.path.insert(0, r'C:\Users\jayra\Documents\GeminiVSCode')

from dhan_auth import token_status, get_valid_token, refresh_token
import os
from dotenv import load_dotenv
load_dotenv(r'C:\Users\jayra\Documents\GeminiVSCode\.env', override=True)

print("=== Current Token Status ===")
ts = token_status()
for k,v in ts.items(): print(f"  {k}: {v}")

print("\n=== Attempting auto-refresh via TOTP ===")
pin      = os.getenv("DHAN_PIN","").split("#")[0].strip()
totp_key = os.getenv("DHAN_TOTP_KEY","").split("#")[0].strip()
cid      = os.getenv("DHAN_CLIENT_ID","")
print(f"  client_id: {cid}, pin: {'*'*len(pin)}, totp_key[:8]: {totp_key[:8]}...")

try:
    new_token = refresh_token(cid, pin, totp_key)
    print(f"  New token[:40]: {new_token[:40]}")
    ts2 = token_status()
    print(f"  New expiry: {ts2.get('expires_at')}")
except Exception as e:
    print(f"  REFRESH FAILED: {e}")

print("\n=== Testing broker_options with refreshed token ===")
from broker_options import dhan_subscription_check
chk = dhan_subscription_check()
for k,v in chk.items(): print(f"  {k}: {v}")
