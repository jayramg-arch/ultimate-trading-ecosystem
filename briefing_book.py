"""The book for the Strategic Daily Briefing (15-Oct-2026).

WHY. The briefing built its universe from portfolio_data.json, which only ever ADDED names
(merged from live holdings, never pruned), plus portfolio.csv - three rows last written
months ago. So sold names (RELIANCE) stayed in the report and in the Gemini prompt with
their old quantities, "Invested Value" was the market value of a book that no longer
existed, and the sector came from yfinance ('.' for some names).

NOW. One source: live Dhan holdings (the broker is the truth; cash-park LIQUID* excluded),
joined to the journal's OPEN row for the plan fields - plan type, setup, entry date, the
Dhan stop, the thesis and the initial stop. If Dhan cannot be read, the journal's OPEN rows
stand in and the result says so. Sector from sector_lookup (the board's own map).
"""
from __future__ import annotations

import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))


def _f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _journal_open() -> dict:
    try:
        import journal_path as jp
        con = sqlite3.connect(jp.JOURNAL_DB)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute("SELECT * FROM journal WHERE UPPER(status)='OPEN'").fetchall()
        finally:
            con.close()
        return {str(r["symbol"]).strip().upper(): dict(r) for r in rows}
    except Exception:
        return {}


def _dhan_holdings() -> dict | None:
    """{SYMBOL: {qty, avg, ltp}} from Dhan, or None when it cannot be read."""
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(HERE, ".env"))
        from dhan_auth import ensure_valid_token
        from dhanhq import dhanhq
        resp = dhanhq(os.getenv("DHAN_CLIENT_ID"), ensure_valid_token()).get_holdings()
        if not (isinstance(resp, dict) and resp.get("status") == "success"):
            return None
        out = {}
        for it in resp.get("data") or []:
            sym = str(it.get("tradingSymbol") or "").strip().upper()
            qty = _f(it.get("totalQty")) or 0
            if sym and qty > 0:
                out[sym] = {"qty": qty, "avg": _f(it.get("avgCostPrice")) or 0.0,
                            "ltp": _f(it.get("lastTradedPrice"))}
        return out
    except Exception:
        return None


def sector_of(sym: str) -> str:
    try:
        import sector_lookup as sl
        rec = sl.get_sector(sym)
        if rec:
            return str(rec.get("display_name") or rec.get("sector_name") or "Unassigned")
    except Exception:
        pass
    return "Unassigned"


def load_book() -> tuple[list[dict], str]:
    """(positions, source) - source is 'dhan' or 'journal (Dhan unavailable)'."""
    jr = _journal_open()
    live = _dhan_holdings()
    src = "dhan"
    if live is None:
        src = "journal (Dhan unavailable)"
        live = {s: {"qty": _f(r.get("quantity")) or 0, "avg": _f(r.get("buy_price")) or 0.0, "ltp": None}
                for s, r in jr.items()}
    out = []
    for sym in sorted(live):
        if sym.startswith("LIQUID"):
            continue                       # cash park - not a position (risk-off carry)
        h, j = live[sym], jr.get(sym, {})
        out.append({
            "symbol": sym, "qty": h["qty"], "avg": h["avg"], "broker_ltp": h["ltp"],
            "sector": sector_of(sym),
            "plan": str(j.get("timeframe") or "").strip() or "Positional (default)",
            "setup": str(j.get("setup") or "").strip(),
            "entry_date": j.get("entry_date"),
            "dhan_sl": _f(j.get("stoploss")), "thesis_sl": _f(j.get("thesis_sl")),
            "initial_sl": _f(j.get("initial_sl")),
            "in_journal": bool(j),
        })
    return out, src
