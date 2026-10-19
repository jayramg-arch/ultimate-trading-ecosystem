#!/usr/bin/env python3
"""Which system a journal row belongs to: v1 / v2 / legacy (Jay, 19-Oct-2026).

The comparison of v1 vs v2 needs to know who CHOSE each trade. The entry snapshot tag
(`snapshot_meta` recompute vs backfill) records how a row was written, not who chose it - 13 of
the 18 open v1 holdings read `backfill` because the 16:30 sync recorded them. So each row
carries an explicit `origin`:

  v2      setup POS-V2 (written by v2_take.py)
  v1      chosen by the current system (GM + S4) - written by s4_take.py from now on
  legacy  not chosen by either system: entered before the system era, cash parks (LIQUID*),
          and the 30-Mar-2026 tax-harvest batch
  NULL    a holding the 16:30 sync picked up with no origin - shown as UNCLASSIFIED for Jay

Defaults for rows that existed on 19-Oct-2026 (Jay): entered on/after V1_FROM = v1, earlier =
legacy; COALINDIA (open, entered Feb-2026) is legacy. The comparison page lets Jay change any
row; `set_origin()` is the one writer.

    python trade_origin.py            show the split (no changes)
    python trade_origin.py --apply    write the defaults to rows with no origin (backup first)
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
V1_FROM = "2026-04-01"
ORIGINS = ("v1", "v2", "legacy")


def default_origin(r: dict) -> str:
    """The default for a row with no origin (rules above)."""
    sym = str(r.get("symbol") or "").upper()
    setup = str(r.get("setup") or "").upper()
    if setup.startswith("POS-V2"):
        return "v2"
    if sym.startswith("LIQUID") or "LIQUIDETF" in sym or str(r.get("exit_reason") or "").upper() == "TAX_HARVEST":
        return "legacy"
    ed = str(r.get("entry_date") or "")[:10]
    if not ed or ed in ("None", "nan"):
        xd = str(r.get("exit_date") or "")[:10]
        return "v1" if xd >= "2026-05-01" else "legacy"
    return "v1" if ed >= V1_FROM else "legacy"


def _rows(con):
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute(
        "SELECT id, symbol, status, entry_date, exit_date, exit_reason, setup, origin FROM journal")]


def apply_defaults(db: str | None = None, overrides: dict | None = None, dry: bool = False) -> dict:
    """Write default origins to rows that have none (never overwrites a set origin).
    overrides = {symbol: origin} applied to OPEN rows (Jay's calls, e.g. COALINDIA legacy)."""
    import journal_path as jp
    db = db or jp.JOURNAL_DB
    # The column directly (journal_core runs a Dhan token check at import; its migrate_db also
    # adds `origin` for the app, so both paths agree).
    if not dry:
        _c = sqlite3.connect(db)
        try:
            if "origin" not in [r[1] for r in _c.execute("PRAGMA table_info(journal)")]:
                _c.execute("ALTER TABLE journal ADD COLUMN origin TEXT")
                _c.commit()
        finally:
            _c.close()
    if not dry and db == jp.JOURNAL_DB:
        bk = os.path.join(HERE, "trade_journal_v6_backup_%s_origin.db" % dt.datetime.now().strftime("%Y%m%d_%H%M"))
        shutil.copy2(db, bk)
    con = sqlite3.connect(db)
    out = {"v1": 0, "v2": 0, "legacy": 0, "kept": 0}
    try:
        for r in _rows(con):
            if r.get("origin"):
                out["kept"] += 1
                continue
            o = default_origin(r)
            if overrides and str(r.get("status", "")).upper() == "OPEN" and str(r["symbol"]).upper() in overrides:
                o = overrides[str(r["symbol"]).upper()]
            out[o] += 1
            if not dry:
                con.execute("UPDATE journal SET origin=? WHERE id=?", (o, r["id"]))
        if not dry:
            con.commit()
    finally:
        con.close()
    return out


def set_origin(row_id: int, origin: str, db: str | None = None) -> None:
    """The one writer of a row's origin (the comparison page calls this)."""
    if origin not in ORIGINS:
        raise ValueError("origin must be one of %s" % (ORIGINS,))
    import journal_path as jp
    con = sqlite3.connect(db or jp.JOURNAL_DB)
    try:
        con.execute("UPDATE journal SET origin=? WHERE id=?", (origin, int(row_id)))
        con.commit()
    finally:
        con.close()


def origin_of(row: dict) -> str:
    """The row's origin, falling back to the default rule ('unclassified' only when the row is
    OPEN, has none, and was added after the defaults were applied)."""
    o = row.get("origin")
    if o in ORIGINS:
        return o
    return "unclassified" if str(row.get("status", "")).upper() == "OPEN" else default_origin(row)


def main() -> int:
    ov = {"COALINDIA": "legacy"}
    res = apply_defaults(overrides=ov, dry="--apply" not in sys.argv)
    print(("APPLIED " if "--apply" in sys.argv else "DRY RUN ") + str(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
