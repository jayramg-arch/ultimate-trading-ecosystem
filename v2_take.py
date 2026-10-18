#!/usr/bin/env python3
"""Record a REAL v2 fill (18-Oct-2026, Doc 42 §8 D2).

    python v2_take.py SYMBOL --price 1234.50 --qty 12              a v2 BUY you placed at Dhan
    python v2_take.py SYMBOL --price 1234.50 --qty 12 --stop 1180   override the disaster stop
    python v2_take.py SYMBOL --sell --price 1290 [--qty 12]          v2 SOLD its slice (rank exit)

v2's own shares live in the v2 ledger (v2_ledger.py, data/v2/real_book.json). The house keeps
ONE journal row and ONE resting stop per holding, so:
  - a NEW name: the ledger slice AND a journal OPEN row (setup POS-V2, Positional, the disaster
    stop as Initial SL and StopLoss, no targets - v2 exits on the weekly rank);
  - a PYRAMID onto a holding the current system already has: the ledger slice only; the journal
    row is left alone (journal_sync lifts its quantity to Dhan's total at 16:30), and you keep
    ONE stop for all shares at the higher of the holding's stop and the add's disaster stop.
Sells of a whole v2-only holding need nothing more: journal_sync closes the row from the Dhan
trade. Nothing here places an order.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SETUP = "POS-V2"


def atr14_daily(sym: str) -> float | None:
    """Wilder ATR14 on daily bars - the ATR the v2 engine sets the disaster stop with."""
    try:
        import data_provider as dp
        import pandas as pd
        d = dp.fetch_ohlcv(sym, period="1y", interval="1d", use_cache=True)
        if d is None or len(d) < 30:
            return None
        prev = d["Close"].shift()
        tr = pd.concat([d["High"] - d["Low"], (d["High"] - prev).abs(), (d["Low"] - prev).abs()], axis=1).max(axis=1)
        return float(tr.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1])
    except Exception:
        return None


def open_row(sym: str):
    """(id, setup, stoploss, quantity) of the symbol's OPEN journal row, or None."""
    import journal_path as jp
    con = sqlite3.connect(jp.JOURNAL_DB)
    try:
        r = con.execute("SELECT id, setup, stoploss, quantity FROM journal WHERE UPPER(symbol)=? AND "
                        "UPPER(status)='OPEN' ORDER BY id LIMIT 1", (sym,)).fetchone()
    finally:
        con.close()
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("symbol")
    ap.add_argument("--price", type=float, required=True, help="your actual fill")
    ap.add_argument("--qty", type=float, help="shares (required for a buy; a sell defaults to the whole slice)")
    ap.add_argument("--stop", type=float, help="disaster stop for a buy (default: fill - 4 x ATR14 daily)")
    ap.add_argument("--sell", action="store_true", help="v2 sold its slice")
    ap.add_argument("--date", help="fill date YYYY-MM-DD (default today)")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    import v2_house as vh
    import v2_ledger as vl
    sym = a.symbol.upper().replace("NSE:", "").replace(".NS", "")
    date = a.date or dt.date.today().isoformat()

    if a.sell:
        rec = vl.sell(sym, a.price, a.qty, date, why="v2 rank exit" + ((" · " + a.note) if a.note else ""))
        if not rec:
            print("v2 holds no slice of %s - nothing recorded" % sym, file=sys.stderr)
            return 2
        print("v2 slice SOLD: %s %g sh @ %.2f (entry %.2f) · P&L %+.0f%s" % (
            sym, rec["sh"], a.price, rec["entry"], (a.price - rec["entry"]) * rec["sh"],
            " · shared holding: the current system's shares and the journal row stay" if rec["shared"] else ""))
        return 0

    if not a.qty or a.qty <= 0:
        print("--qty is required for a buy", file=sys.stderr)
        return 2
    stop = a.stop
    if stop is None:
        atr = atr14_daily(sym)
        if atr is None:
            print("no ATR for %s - pass --stop" % sym, file=sys.stderr)
            return 2
        stop = round(a.price - vh.H["stop_atr"] * atr, 2)
    if stop >= a.price:
        print("stop %.2f is not below the fill %.2f" % (stop, a.price), file=sys.stderr)
        return 2
    row = open_row(sym)
    import house_policy as hp
    shared = bool(row) and not hp.is_v2(row[1])
    vl.buy(sym, a.price, a.qty, stop, date, shared=shared)
    if shared:
        cur = float(row[2] or 0)
        one = max(cur, stop)
        print("v2 PYRAMID onto a current-system holding: %s +%g sh @ %.2f (ledger) · journal row %s left alone"
              % (sym, a.qty, a.price, row[0]))
        print("Keep ONE stop for all %g shares at %.2f (the higher of the holding's stop %.2f and the add's "
              "disaster stop %.2f) - resize the existing Dhan stop order to the full quantity."
              % (float(row[3] or 0) + a.qty, one, cur, stop))
        return 0
    if row:                                    # already a v2 row: more v2 shares, same stop rule
        print("v2 adds %g sh to its own %s (ledger); journal_sync lifts the row's quantity tonight" % (a.qty, sym))
        print("Keep ONE stop for all shares at %.2f or higher." % stop)
        return 0
    import dhan_journal_v7 as dj
    sector = ""
    try:
        import sector_lookup
        sector = (sector_lookup.get_sector(sym) or {}).get("sector", "") or ""
    except Exception:
        pass
    res = dj.upsert_trade({"Symbol": sym, "Type": "LONG", "StopLoss": stop, "Target1": None, "Target2": None,
                           "Timeframe": "Positional", "EntryDate": date, "Quantity": a.qty, "BuyPrice": a.price,
                           "Status": "OPEN", "Sector": sector, "Initial SL": stop,
                           "Rationale": "v2 system (V2H) weekly buy%s" % ((" · " + a.note) if a.note else "")})
    new = open_row(sym)
    if new:
        import journal_path as jp
        con = sqlite3.connect(jp.JOURNAL_DB)
        con.execute("UPDATE journal SET setup=? WHERE id=?", (SETUP, new[0]))
        con.commit()
        con.close()
    print("v2 BUY: %s %g @ %.2f · disaster stop %.2f (%.1f%%) · ledger + journal OPEN (setup %s, Positional%s)" % (
        sym, a.qty, a.price, stop, (a.price - stop) / a.price * 100, SETUP,
        (", id %s" % res) if isinstance(res, int) else ""))
    print("Place the stop at Dhan now: one stop order for all %g shares, trigger %.2f, limit below it." % (a.qty, stop))
    return 0


if __name__ == "__main__":
    sys.exit(main())
