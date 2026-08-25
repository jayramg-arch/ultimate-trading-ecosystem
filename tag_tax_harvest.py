#!/usr/bin/env python3
"""Tag the FY-end tax-loss-harvest exits so they stop reading as trading losses.

WHY (Jay, 25-Aug-2026): "take into account the tax loss harvesting I did towards
the end of March'26. So, those ETF trades should not be taken as losses."

A tax-loss harvest is an ACCOUNTING decision, not a trading outcome. The loss had
already happened on paper; crystallising it before 31 March converts an unrealised
mark into a realised one to offset gains elsewhere. Counting that as "the strategy
lost money" is a category error twice over -- it was not the strategy's decision to
exit, and the exit price was not chosen on merit.

WHAT IT MATCHES, and why the rule is narrow:
    exit_date == 2026-03-30  AND  exit_reason IS NULL

Eighteen positions closed on that single day, one day before the financial year
ends, with no exit reason recorded on any of them. That is the signature of a batch
action rather than eighteen independent decisions -- no strategy produces eighteen
simultaneous exits across ETFs, banks, IT and midcaps. The date is hardcoded on
purpose: a general "any big single-day batch" rule would eventually swallow a real
risk-off exit, which is exactly the kind of loss that MUST stay in the record.

Rows that already carry an exit_reason are left alone -- an explicit reason is
evidence of a real decision and outranks this inference.

Reversible: --revert restores exit_reason to NULL on rows tagged by this script.
A timestamped .db backup is written before any change.

    python tag_tax_harvest.py --dry-run     # show what would change
    python tag_tax_harvest.py               # apply
    python tag_tax_harvest.py --revert      # undo
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trade_journal_v6.db")
HARVEST_DATE = "2026-03-30"
TAG = "TAX_HARVEST"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--date", default=HARVEST_DATE)
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if not os.path.exists(DB):
        print(f"journal not found: {DB}")
        return 1

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    if args.revert:
        rows = cur.execute(
            "SELECT id, symbol FROM journal WHERE exit_reason = ?", (TAG,)).fetchall()
        print(f"tagged rows to revert: {len(rows)}")
        for r in rows:
            print(f"   {r['id']:>4}  {r['symbol']}")
        if not rows or args.dry_run:
            con.close()
            return 0
        bk = DB.replace(".db", f".backup_{datetime.now():%Y%m%d_%H%M%S}_pretagrevert.db")
        shutil.copy2(DB, bk)
        cur.execute("UPDATE journal SET exit_reason = NULL WHERE exit_reason = ?", (TAG,))
        con.commit()
        print(f"\nreverted {cur.rowcount}. backup: {os.path.basename(bk)}")
        con.close()
        return 0

    rows = cur.execute(
        "SELECT id, symbol, quantity, buy_price, exit_price, exit_reason "
        "FROM journal WHERE date(exit_date) = ? AND "
        "(exit_reason IS NULL OR TRIM(exit_reason) = '')", (args.date,)).fetchall()

    skipped = cur.execute(
        "SELECT symbol, exit_reason FROM journal WHERE date(exit_date) = ? AND "
        "exit_reason IS NOT NULL AND TRIM(exit_reason) <> ''", (args.date,)).fetchall()

    print(f"exit_date {args.date} — untagged rows: {len(rows)}")
    total = 0.0
    for r in rows:
        try:
            pnl = (float(r["exit_price"]) - float(r["buy_price"])) * float(r["quantity"])
        except (TypeError, ValueError):
            pnl = float("nan")
        total += 0.0 if pnl != pnl else pnl
        print(f"   {r['id']:>4}  {r['symbol']:<14} {pnl:>14,.0f}")
    print(f"   {'':>4}  {'TOTAL':<14} {total:>14,.0f}")
    if skipped:
        print(f"\nleft alone (already carry a reason): "
              f"{', '.join(f'{s[0]}={s[1]}' for s in skipped)}")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        con.close()
        return 0
    if not rows:
        con.close()
        return 0

    bk = DB.replace(".db", f".backup_{datetime.now():%Y%m%d_%H%M%S}_pretagharvest.db")
    shutil.copy2(DB, bk)
    cur.executemany("UPDATE journal SET exit_reason = ? WHERE id = ?",
                    [(TAG, r["id"]) for r in rows])
    con.commit()
    print(f"\ntagged {len(rows)} rows as {TAG}. backup: {os.path.basename(bk)}")
    print("These are now reported as their own category by performance_attribution — "
          "out of\nboth the system and the discretionary performance figures, because "
          "the exit was an\naccounting decision rather than a trading one.")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
