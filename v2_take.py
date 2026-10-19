#!/usr/bin/env python3
"""Record a REAL v2 fill (18-Oct-2026; Clenow rules from 19-Oct-2026, Doc 42).

    python v2_take.py SYMBOL --price 1234.50 --qty 12                  a v2 BUY (or a resize top-up)
    python v2_take.py SYMBOL --sell --price 1290 [--qty 12]              a v2 SELL (rank exit / resize trim)
    python v2_take.py SYMBOL --convert --price 1250 --keep 26 [--bought 0]
                                                                         a v1 holding becomes v2's

v2 holdings carry NO stop (Jay, 19-Oct): they leave on Clenow's exits - out of the rank cut,
a close below the 100-day average, a 15 % one-day move, leaving the Nifty 500, or NSE
surveillance. `--stop` is still accepted and recorded if you place one anyway.

CONVERT (PREREG_pyramid_slices_vs_convert, adopted 19-Oct): when v2's weekly buy list names a
stock the current system (v1) holds, the whole holding moves to v2 and is resized to v2's target
at once - you sell the excess at the Wednesday open (or buy the shortfall) and CANCEL the v1 stop
order. This closes v1's journal row at --price (its trade ends here; for tax, your real cost basis
is unchanged - no sale happened on the kept shares) and opens a v2 row for the kept shares at the
same price, paid from v2's capital, so the 1/3 capital split stays exact.

Sells of a whole v2 holding need nothing more if you prefer: journal_sync closes the row from the
Dhan trade at 16:30. Nothing here places an order.
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


def open_row(sym: str):
    """(id, setup, stoploss, quantity, buy_price) of the symbol's OPEN journal row, or None."""
    import journal_path as jp
    con = sqlite3.connect(jp.JOURNAL_DB)
    try:
        r = con.execute("SELECT id, setup, stoploss, quantity, buy_price FROM journal WHERE UPPER(symbol)=? AND "
                        "UPPER(status)='OPEN' ORDER BY id LIMIT 1", (sym,)).fetchone()
    finally:
        con.close()
    return r


def _sector(sym: str) -> str:
    try:
        import sector_lookup
        return (sector_lookup.get_sector(sym) or {}).get("sector", "") or ""
    except Exception:
        return ""


def _open_v2_row(sym: str, price: float, qty: float, date: str, stop, note: str) -> None:
    """Insert the v2 OPEN row directly (journal_core would run a Dhan token check at import)."""
    import journal_path as jp
    con = sqlite3.connect(jp.JOURNAL_DB)
    try:
        con.execute("INSERT INTO journal (symbol, trade_type, stoploss, target1, target2, timeframe, entry_date, "
                    "quantity, buy_price, status, sector, initial_sl, rationale, setup, origin) "
                    "VALUES (?, 'LONG', ?, NULL, NULL, 'Positional', ?, ?, ?, 'OPEN', ?, ?, ?, ?, 'v2')",
                    (sym, stop, date, qty, price, _sector(sym), stop, note, SETUP))
        con.commit()
    finally:
        con.close()


def convert(sym: str, price: float, keep: float, bought: float, date: str, note: str) -> int:
    import house_policy as hp
    import journal_path as jp
    import v2_ledger as vl
    row = open_row(sym)
    if not row:
        print("%s has no OPEN journal row - nothing to convert" % sym, file=sys.stderr)
        return 2
    if hp.is_v2(row[1]):
        print("%s is already a v2 holding - use a plain buy / --sell to resize" % sym, file=sys.stderr)
        return 2
    held = float(row[3] or 0)
    keep_total = keep + bought
    if keep_total <= 0 or keep > held + 1e-9:
        print("--keep %g must be between 1 and the %g shares v1 holds" % (keep, held), file=sys.stderr)
        return 2
    con = sqlite3.connect(jp.JOURNAL_DB)
    why = ("converted to v2 on %s @ %.2f: v2 kept %g, %g sold at the open%s" %
           (date, price, keep, held - keep, (" · " + note) if note else ""))
    con.execute("UPDATE journal SET status='CLOSED', exit_price=?, exit_date=?, exit_reason=?, "
                "rationale=COALESCE(rationale,'') || ? WHERE id=?",
                (price, date, "Converted to v2", " | " + why, row[0]))
    con.commit()
    con.close()
    _open_v2_row(sym, price, keep_total, date, None,
                 "v2 system (V2H) - converted from the current system on %s (v1 avg cost %.2f)%s"
                 % (date, float(row[4] or 0), (" · " + note) if note else ""))
    vl.buy(sym, price, keep_total, None, date, shared=False)
    print("CONVERTED %s: v1 row %s closed @ %.2f (%g sh) · v2 now holds %g sh @ %.2f (journal setup %s, ledger)"
          % (sym, row[0], price, held, keep_total, price, SETUP))
    print("Make sure the v1 stop order(s) for %s are CANCELLED at Dhan - v2 holdings carry no stop." % sym)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("symbol")
    ap.add_argument("--price", type=float, required=True, help="your actual fill (for --convert: the open / excess-sale fill)")
    ap.add_argument("--qty", type=float, help="shares (required for a buy; a sell defaults to the whole slice)")
    ap.add_argument("--stop", type=float, help="optional - v2 carries no stop; recorded only if you placed one")
    ap.add_argument("--sell", action="store_true", help="v2 sold shares (rank exit or resize trim)")
    ap.add_argument("--convert", action="store_true", help="a v1 holding becomes v2's (needs --keep)")
    ap.add_argument("--keep", type=float, help="--convert: v1 shares v2 keeps (its target size)")
    ap.add_argument("--bought", type=float, default=0.0, help="--convert: extra shares bought when v1 held fewer than the target")
    ap.add_argument("--date", help="fill date YYYY-MM-DD (default today)")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    import house_policy as hp
    import v2_ledger as vl
    sym = a.symbol.upper().replace("NSE:", "").replace(".NS", "")
    date = a.date or dt.date.today().isoformat()

    if a.convert:
        if a.keep is None:
            print("--convert needs --keep (the order sheet prints it)", file=sys.stderr)
            return 2
        return convert(sym, a.price, a.keep, a.bought, date, a.note)

    if a.sell:
        rec = vl.sell(sym, a.price, a.qty, date, why="v2 exit / resize" + ((" · " + a.note) if a.note else ""))
        if not rec:
            print("v2 holds no slice of %s - nothing recorded" % sym, file=sys.stderr)
            return 2
        print("v2 SOLD: %s %g sh @ %.2f (entry %.2f) · P&L %+.0f" % (
            sym, rec["sh"], a.price, rec["entry"], (a.price - rec["entry"]) * rec["sh"]))
        return 0

    if not a.qty or a.qty <= 0:
        print("--qty is required for a buy", file=sys.stderr)
        return 2
    if a.stop is not None and a.stop >= a.price:
        print("stop %.2f is not below the fill %.2f" % (a.stop, a.price), file=sys.stderr)
        return 2
    row = open_row(sym)
    if row and not hp.is_v2(row[1]):
        print("%s is a current-system (v1) holding - v2 takes it over with --convert, not a plain buy "
              "(the order sheet's CONVERT line gives --keep)." % sym, file=sys.stderr)
        return 2
    vl.buy(sym, a.price, a.qty, a.stop, date, shared=False)
    if row:                                     # already v2's: a resize top-up
        print("v2 adds %g sh to its %s (ledger); journal_sync lifts the row's quantity at 16:30" % (a.qty, sym))
        return 0
    _open_v2_row(sym, a.price, a.qty, date, a.stop, "v2 system (V2H) weekly buy%s" % ((" · " + a.note) if a.note else ""))
    print("v2 BUY: %s %g @ %.2f · ledger + journal OPEN (setup %s, Positional) · %s" % (
        sym, a.qty, a.price, SETUP, ("stop %.2f recorded" % a.stop) if a.stop else
        "no stop - exits on the weekly rank, the 100-day average, a 15 % move, the index or surveillance"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
