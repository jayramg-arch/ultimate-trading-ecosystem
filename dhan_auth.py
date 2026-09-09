# dhan_auth.py
# Auto-refresh Dhan access token using TOTP + PIN
# Requires: pip install pyotp requests python-dotenv
# Reads: DHAN_CLIENT_ID, DHAN_PIN, DHAN_TOTP_KEY from .env
# Writes fresh token back to .env and returns it

import os, json, time, re
import requests
from dotenv import load_dotenv, set_key
from net_utils import is_internet_available

_ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")

def _get_env():
    load_dotenv(_ENV_PATH, override=True)
    return {
        "client_id":  os.getenv("DHAN_CLIENT_ID", ""),
        "pin":        os.getenv("DHAN_PIN", "").split("#")[0].strip(),
        "totp_key":   os.getenv("DHAN_TOTP_KEY", "").split("#")[0].strip(),
        "token":      os.getenv("DHAN_ACCESS_TOKEN", "").strip("'\""),
    }

def is_token_valid(token: str) -> bool:
    """Check if JWT is not expired (with 10-min buffer)."""
    if not token or "." not in token:
        return False
    try:
        import base64, json as _j
        b64_string = token.split(".")[1]
        padding = '=' * (-len(b64_string) % 4)
        payload = _j.loads(base64.urlsafe_b64decode(b64_string + padding))
        return payload.get("exp", 0) > time.time() + 600
    except Exception:
        return False

def get_valid_token(force_refresh: bool = False) -> str:
    """
    Return a valid Dhan access token.
    Uses cached token if still valid; otherwise auto-refreshes via TOTP.
    """
    cfg = _get_env()
    token = cfg["token"]

    if not force_refresh and is_token_valid(token):
        return token

    # Guard: if the internet is offline, attempting to refresh will timeout/hang.
    # Fallback to the existing token (even if invalid/expired) to avoid deadlocks.
    if not is_internet_available():
        import logging
        logging.getLogger(__name__).warning("[dhan_auth] Internet offline -- returning cached token as-is.")
        return token

    return refresh_token(cfg["client_id"], cfg["pin"], cfg["totp_key"])


_AUTH_URL = "https://auth.dhan.co/app/generateAccessToken"


def _call_generate_token(client_id: str, pin: str, otp: str) -> dict:
    """POST to the official Dhan token endpoint. Params go in the query string (per docs v2)."""
    try:
        r = requests.post(
            _AUTH_URL,
            params={"dhanClientId": client_id, "pin": pin, "totp": otp},
            timeout=30,
        )
        return r.json()
    except ValueError:
        return {"message": f"Non-JSON response (HTTP {r.status_code}): {r.text[:200]}"}
    except requests.RequestException as e:
        return {"message": f"Request failed: {e}"}


def refresh_token(client_id: str, pin: str, totp_key: str) -> str:
    """
    Log into Dhan programmatically using PIN + TOTP and return fresh access_token.
    Calls https://auth.dhan.co/app/generateAccessToken directly — the installed
    dhanhq (2.0.2) has no DhanLogin class, so we don't depend on the SDK here.
    Saves the new token to .env automatically.
    """
    try:
        import pyotp
    except ImportError:
        raise ImportError("Run: pip install pyotp")

    if not client_id or not pin or not totp_key:
        raise RuntimeError(
            "Missing DHAN_CLIENT_ID / DHAN_PIN / DHAN_TOTP_KEY in .env — "
            "cannot auto-refresh the Dhan token."
        )

    totp = pyotp.TOTP(totp_key)
    res  = _call_generate_token(client_id, pin, totp.now())

    if not res or 'accessToken' not in res:
        msg = res.get('message', '') or res.get('errorMessage', '') if isinstance(res, dict) else str(res)

        # Handle concurrent process refresh or explicit 2-minute API block
        if "once every 2 minutes" in msg or "rate limit" in msg.lower():
            print("[dhan_auth] Hit 2-minute rate limit. Checking if another process updated .env...")
            time.sleep(3)
            cfg = _get_env()
            if is_token_valid(cfg["token"]):
                print("[dhan_auth] Recovered! Loaded freshly generated token from .env")
                return cfg["token"]

            print("[dhan_auth] Rate limited and no fresh token found. Waiting 120s to retry...")
            time.sleep(120)
            res = _call_generate_token(client_id, pin, totp.now())
            if not res or 'accessToken' not in res:
                raise RuntimeError(f"Dhan TOTP step failed after 120s wait: {res}")
        elif "totp" in msg.lower() or "otp" in msg.lower():
            # Possible TOTP window rollover mid-request — wait for the next
            # 30s window and retry once with a fresh code.
            wait = 31 - (int(time.time()) % 30)
            print(f"[dhan_auth] TOTP rejected ({msg}). Retrying in {wait}s with a fresh code...")
            time.sleep(wait)
            res = _call_generate_token(client_id, pin, totp.now())
            if not res or 'accessToken' not in res:
                raise RuntimeError(
                    f"Dhan TOTP step failed after retry: {res}\n"
                    "Verify DHAN_TOTP_KEY is the base32 secret shown when enabling TOTP "
                    "(not a 6-digit code) and DHAN_PIN is the login PIN."
                )
        else:
            raise RuntimeError(
                f"Dhan TOTP step failed: {res}\n"
                "Please regenerate your token at https://web.dhan.co -> API -> Access Token "
                "and update DHAN_ACCESS_TOKEN in .env"
            )

    new_token = res['accessToken']

    # Save to .env
    set_key(_ENV_PATH, "DHAN_ACCESS_TOKEN", new_token)
    os.environ["DHAN_ACCESS_TOKEN"] = new_token
    print(f"[dhan_auth] Token refreshed successfully (client: {client_id})")
    return new_token


# Backward-compat alias — older files import ensure_valid_token
ensure_valid_token = get_valid_token


def get_dhan_client(force_refresh: bool = False):
    """
    Return an authenticated dhanhq client with a valid token.
    Handles auto-refresh transparently.
    """
    from dhanhq import dhanhq as Dhan
    try:
        from dhanhq import DhanContext
    except ImportError:
        DhanContext = None

    cfg   = _get_env()
    token = get_valid_token(force_refresh=force_refresh)
    
    if DhanContext:
        return Dhan(DhanContext(cfg["client_id"], token))
    else:
        return Dhan(cfg["client_id"], token)


def token_status() -> dict:
    """Return token validity info for display in UI."""
    import base64, json as _j, datetime
    cfg   = _get_env()
    token = cfg["token"]
    if not token or "." not in token:
        return {"valid": False, "error": "No token found in .env (DHAN_ACCESS_TOKEN is empty)"}
    try:
        payload = _j.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
        exp     = payload.get("exp", 0)
        iat     = payload.get("iat", 0)
        valid   = exp > time.time() + 600
        exp_dt  = datetime.datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M IST")
        return {
            "valid":      valid,
            "client_id":  payload.get("dhanClientId", cfg["client_id"]),
            "expires_at": exp_dt,
            "token_type": payload.get("tokenConsumerType", ""),
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


if __name__ == "__main__":
    # Run directly to test / force-refresh token
    import sys
    force = "--force" in sys.argv
    try:
        token = get_valid_token(force_refresh=force)
        st    = token_status()
        print(f"Token valid : {st['valid']}")
        print(f"Client ID   : {st.get('client_id')}")
        print(f"Expires at  : {st.get('expires_at')}")
    except Exception as e:
        print(f"ERROR: {e}")
