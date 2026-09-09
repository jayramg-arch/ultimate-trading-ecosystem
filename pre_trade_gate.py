"""Shared pre-trade portfolio risk gate for EVERY order-placing surface.

Created 26-Jul-2026 (audit remediation P0). The hardened gate written for the
TradingView webhook was the only one of four order surfaces that had any risk
check at all — `n8n_order_handler.py`, the `dhan_mcp_server.dhan_place_order`
MCP tool, and the Streamlit "Execute CNC Order" button all reached
`dhan.place_order` with zero portfolio checks. This module MOVES that gate
(logic unchanged) out of the FastAPI webhook so the other surfaces can reuse it
without importing FastAPI/uvicorn or triggering the webhook's import-time
scrip-master fetch.

Design rules, in order of importance:

1. **ENTRIES are gated; EXITS never are.** Every cap here exists to stop you
   over-committing capital. Applying them to a SELL could block you out of a
   position you need to exit — strictly more dangerous than letting one entry
   through. `gate_order()` therefore passes SELL straight through.
2. **FAIL-CLOSED on entries.** If the gate cannot be evaluated (holdings fetch
   fails, a sub-check throws), the BUY is BLOCKED, not allowed. A broker hiccup
   must not silently remove all three caps.
3. **Never raises.** Callers get `(ok: bool, reason: str)`.

Thresholds are env-overridable. `PRETRADE_*` is the canonical name; the original
`WEBHOOK_*` names still work so existing .env files keep their meaning.
"""

from __future__ import annotations

import os


def _env_num(name: str, default: str, cast=float):
    """PRETRADE_<name> wins, else the legacy WEBHOOK_<name>, else `default`."""
    raw = os.getenv(f"PRETRADE_{name}") or os.getenv(f"WEBHOOK_{name}") or default
    try:
        return cast(raw)
    except Exception:
        return cast(default)


MAX_OPEN_POSITIONS = _env_num("MAX_OPEN_POSITIONS", "15", int)
SECTOR_CAP_PCT     = _env_num("SECTOR_CAP_PCT", "25", float)
MAX_RISK_PCT       = _env_num("MAX_RISK_PCT", "1.5", float)   # of portfolio equity


def pre_trade_risk_check(dhan, ticker: str, qty: int, entry_price: float, sl_price: float):
    """Hard pre-trade portfolio risk gate. Returns (ok: bool, reason: str).

    Enforces three caps against the LIVE Dhan book: max open positions, single-
    sector exposure, and per-trade risk as a % of equity (reuses
    ai_risk_manager.analyze_sector_concentration + sector_lookup, same logic the
    Risk Shield surfaces). A breach → (False, reason) → the order is rejected.

    FAIL-CLOSED (23-Jul-2026, Fable audit): if the gate cannot be evaluated — the
    holdings fetch fails, or a sub-check throws — the order is BLOCKED, not allowed.
    A Dhan hiccup must not silently remove all three portfolio caps. It's a manual
    tool, so a false rejection costs nothing; a false allow could over-leverage.
    Never raises."""
    try:
        resp = dhan.get_holdings()
        holdings = resp.get('data', []) if isinstance(resp, dict) else []
    except Exception as e:
        return False, f"risk-gate UNAVAILABLE — holdings fetch failed ({e}); order BLOCKED"

    tk = str(ticker).upper()
    live = []
    for h in holdings or []:
        sym = str(h.get('tradingSymbol') or h.get('tradingsymbol') or '').upper()
        q = float(h.get('totalQty') or h.get('quantity') or 0)
        avg = float(h.get('avgCostPrice') or h.get('averagePrice') or 0)
        if q > 0:
            live.append({'Symbol': sym, 'Quantity': q, 'BuyPrice': avg})

    # 1) Max open positions (only blocks a BRAND-NEW name, not a top-up).
    open_syms = {p['Symbol'] for p in live}
    if tk not in open_syms and len(open_syms) >= MAX_OPEN_POSITIONS:
        return False, f"max open positions reached ({len(open_syms)}/{MAX_OPEN_POSITIONS})"

    # 2) Single-sector exposure cap — include the incoming order, test its sector.
    try:
        import pandas as _pd
        import ai_risk_manager as _rm
        import sector_lookup as _sl
        rows = list(live) + [{'Symbol': tk, 'Quantity': float(qty), 'BuyPrice': float(entry_price)}]
        breakdown = (_rm.analyze_sector_concentration(_pd.DataFrame(rows)) or {}).get('breakdown', {})
        rec = _sl.get_sector(tk)
        new_sector = (rec.get('display_name') or rec.get('sector_name')) if rec else None
        if new_sector and float(breakdown.get(new_sector, 0)) > SECTOR_CAP_PCT:
            return False, (f"sector cap breached: {new_sector} would be "
                           f"{breakdown[new_sector]:.1f}% (> {SECTOR_CAP_PCT:.0f}%)")
    except Exception as e:
        return False, f"sector-cap check failed ({e}) — order BLOCKED (fail-closed)"

    # 3) Per-trade risk as % of equity (needs a valid SL below entry).
    try:
        if sl_price and float(sl_price) > 0 and float(entry_price) > float(sl_price):
            risk_amt = float(qty) * (float(entry_price) - float(sl_price))
            funds = dhan.get_fund_limits()
            avail = float((funds.get('data') or {}).get('availabelBalance', 0)) if isinstance(funds, dict) else 0.0
            deployed = sum(p['Quantity'] * p['BuyPrice'] for p in live)
            equity = deployed + avail
            if equity > 0 and (risk_amt / equity * 100.0) > MAX_RISK_PCT:
                return False, (f"trade risk {risk_amt / equity * 100:.2f}% exceeds "
                               f"{MAX_RISK_PCT:.1f}% of equity (₹{equity:,.0f})")
    except Exception as e:
        return False, f"risk-% check failed ({e}) — order BLOCKED (fail-closed)"

    return True, "risk-gate passed"


def gate_order(dhan, ticker: str, side: str, qty: int,
               entry_price: float = 0.0, sl_price: float = 0.0):
    """Entry-point every order surface should call. Returns (ok, reason).

    SELL/exit orders pass through untouched — see rule 1 in the module docstring.
    BUY orders go through the full fail-closed `pre_trade_risk_check`.

    `sl_price` is optional: without a valid stop below entry the per-trade risk-%
    cap cannot be evaluated and is skipped, but the position-count and sector caps
    still apply. Pass a stop whenever you have one — it is the cap that most
    directly enforces the 1%-risk DNA rule.
    """
    if str(side).upper() not in ("BUY", "B"):
        return True, "SELL/exit — not gated (exits are never blocked)"
    try:
        return pre_trade_risk_check(dhan, ticker, int(qty),
                                    float(entry_price or 0.0), float(sl_price or 0.0))
    except Exception as e:
        return False, f"risk-gate raised unexpectedly ({e}) — order BLOCKED (fail-closed)"
