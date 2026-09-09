# broker_options.py
# Broker API options chain — primary: Dhan
# Returns (calls_df, puts_df, spot, expiries_list) — same format as NSE parser

import os, time
import pandas as pd
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

# Dhan security IDs for index options
DHAN_SEC_IDS = {
    "NIFTY":      13,
    "BANKNIFTY":  25,
    "FINNIFTY":   27,
    "MIDCPNIFTY": 442,
}
DHAN_SEG = "IDX_I"   # exchange segment for indices


def _empty():
    return pd.DataFrame(), pd.DataFrame(), 0.0, []


def _build_dfs(rows: list, spot: float, expiries: list):
    """Convert raw rows into (calls_df, puts_df, spot, expiries)."""
    calls, puts = [], []
    for r in rows:
        s, e = r["strike"], r["expiry"]
        calls.append({"strike": s, "expiry": e,
                      "OI":     r.get("call_oi", 0),
                      "chgOI":  r.get("call_chg_oi", 0),
                      "Volume": r.get("call_vol", 0),
                      "IV%":    round(float(r.get("call_iv", 0)), 1),
                      "LTP":    round(float(r.get("call_ltp", 0)), 2),
                      "chg%":   0.0})
        puts.append({"strike": s, "expiry": e,
                     "OI":     r.get("put_oi", 0),
                     "chgOI":  r.get("put_chg_oi", 0),
                     "Volume": r.get("put_vol", 0),
                     "IV%":    round(float(r.get("put_iv", 0)), 1),
                     "LTP":    round(float(r.get("put_ltp", 0)), 2),
                     "chg%":   0.0})
    return pd.DataFrame(calls), pd.DataFrame(puts), spot, expiries


def get_dhan_expiries(nse_symbol: str) -> list:
    """Fetch available expiry dates from Dhan for a given index."""
    from dhan_auth import get_dhan_client
    dhan   = get_dhan_client()
    sec_id = DHAN_SEC_IDS.get(nse_symbol.upper(), 13)
    resp   = dhan.expiry_list(sec_id, DHAN_SEG)
    if resp.get("status") == "failure":
        raise RuntimeError(f"Dhan expiry_list error: {resp.get('data',{})}")
    data = resp.get("data", {})
    # dhanhq returns {"data": {"data": [...]}} or {"data": [...]}
    if isinstance(data, dict):
        data = data.get("data", [])
    return sorted(data) if isinstance(data, list) else []


def get_option_chain_dhan(nse_symbol: str, expiry: str = None) -> tuple:
    """
    Fetch full options chain from Dhan.
    Requires: Dhan Data API subscription + valid token (auto-refreshed via dhan_auth).

    nse_symbol: "NIFTY" | "BANKNIFTY" | "FINNIFTY" | "MIDCPNIFTY"
    expiry:     "YYYY-MM-DD" — if None, uses nearest expiry
    Returns:    (calls_df, puts_df, spot, expiries_list)
    """
    from dhan_auth import get_dhan_client
    dhan   = get_dhan_client()
    sec_id = DHAN_SEC_IDS.get(nse_symbol.upper(), 13)

    # Get expiries
    expiries = get_dhan_expiries(nse_symbol)
    if not expiries:
        raise RuntimeError(f"No expiry dates returned by Dhan for {nse_symbol}")
    target = expiry or expiries[0]

    from dhan_helpers import fetch_chain_df
    try:
        chain_df, spot = fetch_chain_df(dhan, sec_id, target, DHAN_SEG)
    except Exception as e:
        raise RuntimeError(f"Dhan fetch_chain_df error: {e}")

    calls = []
    puts = []
    for _, r in chain_df.iterrows():
        s = r["strike"]
        calls.append({"strike": s, "expiry": target,
                      "OI":     int(r.get("ce_oi", 0) or 0),
                      "chgOI":  int(r.get("ce_oi_change", 0) or 0),
                      "Volume": int(r.get("ce_volume", 0) or 0),
                      "IV%":    round(float(r.get("ce_iv", 0) or 0), 1),
                      "LTP":    round(float(r.get("ce_ltp", 0) or 0), 2),
                      "chg%":   0.0})
        puts.append({"strike": s, "expiry": target,
                     "OI":     int(r.get("pe_oi", 0) or 0),
                     "chgOI":  int(r.get("pe_oi_change", 0) or 0),
                     "Volume": int(r.get("pe_volume", 0) or 0),
                     "IV%":    round(float(r.get("pe_iv", 0) or 0), 1),
                     "LTP":    round(float(r.get("pe_ltp", 0) or 0), 2),
                     "chg%":   0.0})

    return pd.DataFrame(calls), pd.DataFrame(puts), spot, expiries


def get_option_chain(nse_symbol: str, expiry: str = None) -> tuple:
    """
    Unified entry point — tries Dhan first.
    Returns (calls_df, puts_df, spot, expiries_list, source_label, error_msg).
    """
    try:
        calls, puts, spot, expiries = get_option_chain_dhan(nse_symbol, expiry)
        return calls, puts, spot, expiries, "Dhan", None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), 0.0, [], "none", str(e)


def dhan_subscription_check() -> dict:
    """
    Quick check: can we reach Dhan option chain?
    Returns {"ok": bool, "error": str|None, "token_valid": bool, "client_id": str}
    """
    try:
        from dhan_auth import get_dhan_client, token_status
        ts = token_status()
        if not ts.get("valid"):
            return {"ok": False, "error": "Token expired — auto-refresh needed",
                    "token_valid": False, "client_id": ts.get("client_id", "?")}

        dhan = get_dhan_client()
        resp = dhan.expiry_list(13, DHAN_SEG)   # NIFTY probe
        if resp.get("status") == "failure":
            err_data = resp.get("data", {})
            if isinstance(err_data, dict):
                err_data = err_data.get("data", err_data)
            code = list(err_data.keys())[0] if err_data else "?"
            msg  = list(err_data.values())[0] if err_data else str(err_data)
            return {"ok": False, "error": f"[{code}] {msg}",
                    "token_valid": True, "client_id": ts.get("client_id", "?")}

        return {"ok": True, "error": None,
                "token_valid": True, "client_id": ts.get("client_id", "?")}
    except Exception as e:
        return {"ok": False, "error": str(e), "token_valid": False, "client_id": "?"}
