#!/usr/bin/env python3
"""Record a REAL v2 fill in the journal (18-Oct-2026, Doc 41 workflow).

    python v2_take.py SYMBOL --price 1234.50 --qty 12            a v2 buy you placed at Dhan
    python v2_take.py SYMBOL --price 1234.50 --qty 12 --stop 1180  override the disaster stop

Writes the journal OPEN row the rest of the house reads: setup POS-V2 (so the house Chandelier
trail treats it as positional - 4.5 x ATR22, the rule the v2 backtest used), Timeframe Positional,
the disaster stop as Initial SL and StopLoss (fill - 4 x ATR14 daily unless --stop), no targets
(v2 exits on the weekly rank, not on targets). The v2 order sheet reads these rows to decide
next week's sells for YOUR book. Sells need nothing: journal_sync closes the row from the Dhan
trade at 16:30. Nothing here places an order.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SETUP = "POS-V2"


def atr14_daily(sym: str) -> float | None:
    """Wilder ATR14 on daily bars - the same ATR the v2 engine sizes the disaster stop with."""
    try:
        import data_provider as dp
        d = dp.fetch_ohlcv(sym, period="1y", interval="1d", use_cache=True)
        if d is None or len(d) < 30:
            return None
        import pandas as pd
        prev = d["Close"].shift()
        tr = pd.concat([d["High"] - d["Low"], (d["High"] - prev).abs(), (d["Low"] - prev).abs()], axis=1).max(axis=1)
        return float(tr.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1])
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("symbol")
    ap.add_argument("--price", type=float, required=True, help="your actual fill")
    ap.add_argument("--qty", type=int, required=True)
    ap.add_argument("--stop", type=float, help="disaster stop (default: fill - 4 x ATR14 daily)")
    ap.add_argument("--date", help="fill date YYYY-MM-DD (default today)")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    import v2_house as vh
    sym = a.symbol.upper().replace("NSE:", "").replace(".NS", "")
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
    import dhan_journal_v7 as dj
    sector = ""
    try:
        import sector_lookup
        sector = (sector_lookup.get_sector(sym) or {}).get("sector", "") or ""
    except Exception:
        pass
    entry = {"Symbol": sym, "Type": "LONG", "StopLoss": stop, "Target1": None, "Target2": None,
             "Timeframe": "Positional", "EntryDate": a.date or dt.date.today().isoformat(),
             "Quantity": a.qty, "BuyPrice": a.price, "Status": "OPEN", "Sector": sector,
             "Initial SL": stop, "Rationale": "v2 system (V2H) weekly buy%s" % ((" · " + a.note) if a.note else "")}
    res = dj.upsert_trade(entry)
    import sqlite3
    c = sqlite3.connect(dj.DB_FILE)
    c.execute("UPDATE journal SET setup=? WHERE symbol=? AND status='OPEN'", (SETUP, sym))
    c.commit()
    c.close()
    print("journal OPEN: %s %d @ %.2f · disaster stop %.2f (%.1f%%) · setup %s · Positional%s" % (
        sym, a.qty, a.price, stop, (a.price - stop) / a.price * 100, SETUP,
        (" · id %s" % res) if isinstance(res, int) else ""))
    print("Place the stop at Dhan now: one stop order for all %d shares, trigger %.2f, limit below it." % (a.qty, stop))
    return 0


if __name__ == "__main__":
    sys.exit(main())
