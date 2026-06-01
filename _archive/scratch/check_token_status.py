"""Quick token status — no browser, no API call, just JWT decode."""
import os, time, base64, json, datetime
from dotenv import load_dotenv

load_dotenv(r'C:\Users\jayra\Documents\GeminiVSCode\.env', override=True)

tok = os.getenv("DHAN_ACCESS_TOKEN", "")
cid = os.getenv("DHAN_CLIENT_ID", "")
pin = os.getenv("DHAN_PIN", "")
totp = os.getenv("DHAN_TOTP_KEY", "")

print("=" * 60)
print("  Dhan Credentials Status")
print("=" * 60)
print(f"  CLIENT_ID  : {cid}")
print(f"  PIN        : {'set (' + pin + ')' if pin else 'NOT SET'}")
print(f"  TOTP_KEY   : {'set (' + totp[:8] + '...)' if totp else 'NOT SET'}")

if tok:
    print(f"  TOKEN      : {tok[:35]}…")
    try:
        parts = tok.split('.')
        payload = json.loads(base64.b64decode(parts[1] + '==').decode())
        exp = payload.get('exp', 0)
        iat = payload.get('iat', 0)
        dhan_cid = payload.get('dhanClientId', '?')

        exp_dt = datetime.datetime.fromtimestamp(exp)
        iat_dt = datetime.datetime.fromtimestamp(iat)
        remaining = exp - time.time()

        print(f"\n  JWT Payload:")
        print(f"    Issued at    : {iat_dt.strftime('%d %b %Y %H:%M')}")
        print(f"    Expires at   : {exp_dt.strftime('%d %b %Y %H:%M')}")
        print(f"    dhanClientId : {dhan_cid}  (env CLIENT_ID: {cid})")
        if remaining > 0:
            print(f"    Status       : ✅ VALID ({remaining/3600:.1f}h remaining)")
        else:
            print(f"    Status       : ❌ EXPIRED ({abs(remaining)/3600:.1f}h ago)")
            print(f"    Action       : Browser will auto-launch to refresh")
    except Exception as e:
        print(f"  Token decode error: {e}")
else:
    print("  TOKEN      : NOT SET")

print("=" * 60)
