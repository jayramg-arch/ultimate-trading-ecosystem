#!/usr/bin/env python3
"""Restore the two tranche-sold positions from the authoritative Dhan fills.

THE DEFECT. METALIETF and HDFCSML250 were each sold in TWO tranches, and the
journal correctly holds two rows for each. But both rows of each pair carry the
SAME (later) exit price and date -- the earlier tranche has been overwritten.

This is the reconcile quirk already on record: `reconcile_journal_exit_prices()`
writes the latest exit to ALL same-symbol CLOSED rows, so a symbol traded in
distinct lots collapses to one exit. The tranches were reconstructed by hand on
2 Jun 2026 and a later reconcile silently undid that work.

THE FILLS (pulled from Dhan trade history, securityId resolved via dhan_symbols):

  HDFCSML250  BUY  1100 @ 175.2500   2024-10-07
              BUY  1145 @ 175.0000   2024-10-22
              BUY  1875 @ 160.1600   2025-04-23     -> 4120 @ wtd avg 168.3131
              SELL 2060 @ 156.8000   2026-01-29
              SELL 2060 @ 144.1866   2026-03-30

  METALIETF   BUY 17200 @   8.7200   2025-04-22
              SELL 8600 @  10.8400   2025-12-24
              SELL 8600 @  12.8000   2026-04-16

WHAT THE OVERWRITE DID TO THE BOOK -- and note it cut BOTH ways, which is why
"the journal overstates losses" would have been the wrong summary:

  HDFCSML250  recorded 2 x -49,694 = -99,388     true -73,405   overstated  25,983
  METALIETF   recorded 2 x +35,088 = +70,176     true +53,320   OVERSTATED  16,856
                                                          net improvement    9,127

It inflated a WIN as well as a loss, and the inflated win was the journal's
"best trade".

SIDE EFFECT: HDFCSML250's earlier tranche exits 2026-01-29, not 2026-03-30, so it
is NOT part of the FY-end harvest batch and its TAX_HARVEST tag is removed.

Backed up before writing. --dry-run to preview.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trade_journal_v6.db")

# (symbol, qty, buy_price, entry_date, [(exit_price, exit_date, is_harvest), ...])
# Ordered EARLIEST tranche first. Straight from the fills above.
TRANCHES = [
    ("HDFCSML250", 2060.0, 168.3131, "2024-10-07",
     [(156.8000, "2026-01-29", False), (144.1866, "2026-03-30", True)]),
    ("METALIETF", 8600.0, 8.7200, "2025-04-22",
     [(10.8400, "2025-12-24", False), (12.8000, "2026-04-16", False)]),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    plan, net = [], 0.0
    for sym, qty, buy, entry, legs in TRANCHES:
        rows = cur.execute(
            "SELECT id, quantity, buy_price, exit_price, exit_date, exit_reason "
            "FROM journal WHERE symbol = ? AND UPPER(status) = 'CLOSED' ORDER BY id",
            (sym,)).fetchall()
        if len(rows) != len(legs):
            print(f"!! {sym}: journal has {len(rows)} closed rows, fills show "
                  f"{len(legs)} tranches — SKIPPED, resolve by hand")
            continue
        print(f"\n{sym}")
        for r, (px, dt_, harv) in zip(rows, legs):
            was = (float(r["exit_price"]) - float(r["buy_price"])) * float(r["quantity"])
            now = (px - buy) * qty
            net += now - was
            tag = "TAX_HARVEST" if harv else None
            chg = ("unchanged" if abs(was - now) < 0.5 else
                   f"{was:>12,.0f} -> {now:>12,.0f}")
            print(f"   id {r['id']:>3}  qty {qty:>8,.0f}  exit {r['exit_price']:>10.4f} "
                  f"-> {px:<10.4f} {str(r['exit_date'])[:10]} -> {dt_}   {chg}")
            if r["exit_reason"] == "TAX_HARVEST" and not harv:
                print(f"          untagging TAX_HARVEST — this tranche exited {dt_}, "
                      f"outside the FY-end batch")
            plan.append((qty, buy, px, dt_, tag, entry, r["id"]))

    print(f"\nnet effect on realized P&L: {net:>+12,.0f}")
    if args.dry_run:
        print("\n--dry-run: nothing written.")
        con.close()
        return 0
    if not plan:
        con.close()
        return 0

    bk = DB.replace(".db", f".backup_{datetime.now():%Y%m%d_%H%M%S}_pretranche.db")
    shutil.copy2(DB, bk)
    cur.executemany(
        "UPDATE journal SET quantity = ?, buy_price = ?, exit_price = ?, "
        "exit_date = ?, exit_reason = ?, entry_date = ? WHERE id = ?", plan)
    con.commit()
    print(f"\nrestored {len(plan)} rows. backup: {os.path.basename(bk)}")

    for sym, *_ in TRANCHES:
        for r in cur.execute(
                "SELECT id, quantity, buy_price, exit_price, exit_date, exit_reason "
                "FROM journal WHERE symbol = ? ORDER BY id", (sym,)).fetchall():
            pnl = (float(r["exit_price"]) - float(r["buy_price"])) * float(r["quantity"])
            print(f"   {sym:<12} id {r['id']:>3}  {r['exit_price']:>10.4f}  "
                  f"{str(r['exit_date'])[:10]}  {pnl:>+12,.0f}  {r['exit_reason'] or ''}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
