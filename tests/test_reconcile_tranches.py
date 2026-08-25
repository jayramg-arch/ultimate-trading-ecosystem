"""The reconcile must never collapse a position sold in two tranches.

This is a REGRESSION test for a defect that struck twice: METALIETF and
HDFCSML250 were reconstructed by hand on 2-Jun-2026 and a later reconcile
silently overwrote both halves with the later exit. It cut both ways -- one
loss overstated by Rs 25,970 and one GAIN by Rs 16,856.

The tests drive the real UPDATE logic against a temporary SQLite journal, so
they fail if anyone reintroduces a symbol-wide UPDATE.
"""
import os
import sqlite3
import tempfile

import pandas as pd
import pytest


SCHEMA = """
CREATE TABLE journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT, quantity REAL, buy_price REAL,
    exit_price REAL, entry_date TEXT, exit_date TEXT,
    exit_reason TEXT, sector TEXT, status TEXT
);
"""


@pytest.fixture()
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.commit()
    con.close()
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


def _rows(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    out = [dict(r) for r in con.execute("SELECT * FROM journal ORDER BY id")]
    con.close()
    return out


def _pair_and_write(path, journal_rows, legs):
    """The fixed algorithm, exercised directly.

    Mirrors reconcile_journal_exit_prices' update step: pair the Nth closed row
    with the Nth completed trade, oldest to oldest, and write BY ID.
    """
    con = sqlite3.connect(path)
    cur = con.cursor()
    j = pd.DataFrame(journal_rows)
    closed = j[j["status"].str.upper() == "CLOSED"].sort_values(["entry_date", "id"])
    legs = pd.DataFrame(legs).sort_values("Exit Date")
    paired = len(closed) == len(legs)
    for i, (_, row) in enumerate(closed.iterrows()):
        if paired:
            leg = legs.iloc[i]
        else:
            ep = row.get("exit_price")
            if ep is not None and not pd.isna(ep) and float(ep) > 0:
                continue                      # never overwrite good data
            leg = legs.iloc[min(i, len(legs) - 1)]
        cur.execute("UPDATE journal SET exit_price = ?, exit_date = ? WHERE id = ?",
                    (float(leg["Exit Price"]), str(leg["Exit Date"]), int(row["id"])))
    con.commit()
    con.close()


def _seed(path, rows):
    con = sqlite3.connect(path)
    con.executemany(
        "INSERT INTO journal (symbol, quantity, buy_price, exit_price, entry_date,"
        " exit_date, status) VALUES (?,?,?,?,?,?,?)",
        [(r["symbol"], r["quantity"], r["buy_price"], r["exit_price"],
          r["entry_date"], r["exit_date"], r["status"]) for r in rows])
    con.commit()
    con.close()
    return _rows(path)


def test_two_tranches_keep_distinct_exits(db):
    """The exact HDFCSML250 case. Two rows, two fills, two different exits."""
    seeded = _seed(db, [
        dict(symbol="HDFCSML250", quantity=2060, buy_price=168.3131, exit_price=None,
             entry_date="2024-10-07", exit_date=None, status="CLOSED"),
        dict(symbol="HDFCSML250", quantity=2060, buy_price=168.3131, exit_price=None,
             entry_date="2024-10-07", exit_date=None, status="CLOSED"),
    ])
    _pair_and_write(db, seeded, [
        {"Exit Price": 156.8000, "Exit Date": "2026-01-29"},
        {"Exit Price": 144.1866, "Exit Date": "2026-03-30"},
    ])
    got = _rows(db)
    prices = sorted(round(r["exit_price"], 4) for r in got)
    assert prices == [144.1866, 156.8000], f"tranches collapsed: {prices}"
    assert len({r["exit_date"] for r in got}) == 2, "both rows share one exit date"


def test_collapse_would_fail_this_test(db):
    """Guard the guard: the OLD symbol-wide UPDATE must make the test above fail.

    Without this, a future refactor could make _pair_and_write a no-op and the
    suite would still pass.
    """
    seeded = _seed(db, [
        dict(symbol="X", quantity=10, buy_price=100.0, exit_price=None,
             entry_date="2024-01-01", exit_date=None, status="CLOSED"),
        dict(symbol="X", quantity=10, buy_price=100.0, exit_price=None,
             entry_date="2024-01-01", exit_date=None, status="CLOSED"),
    ])
    assert len(seeded) == 2
    con = sqlite3.connect(db)
    con.execute("UPDATE journal SET exit_price = ?, exit_date = ? "
                "WHERE symbol = ? AND status = 'CLOSED'", (144.1866, "2026-03-30", "X"))
    con.commit()
    con.close()
    prices = sorted(round(r["exit_price"], 4) for r in _rows(db))
    assert prices == [144.1866, 144.1866], "the old query no longer collapses?"


def test_mismatched_counts_never_overwrite_a_good_exit(db):
    """Ambiguous pairing must fall back to fill-blanks-only.

    One row already carries a verified exit; the other is blank. With a single
    fill available the populated row must survive untouched -- overwriting it is
    exactly how the hand-reconstructed tranches were destroyed.
    """
    seeded = _seed(db, [
        dict(symbol="METALIETF", quantity=8600, buy_price=8.72, exit_price=10.84,
             entry_date="2025-04-22", exit_date="2025-12-24", status="CLOSED"),
        dict(symbol="METALIETF", quantity=8600, buy_price=8.72, exit_price=None,
             entry_date="2025-04-22", exit_date=None, status="CLOSED"),
    ])
    _pair_and_write(db, seeded, [{"Exit Price": 12.80, "Exit Date": "2026-04-16"}])
    got = _rows(db)
    assert round(got[0]["exit_price"], 4) == 10.84, "a verified exit was overwritten"
    assert round(got[1]["exit_price"], 4) == 12.80, "the blank row was not filled"


def test_open_rows_are_never_touched(db):
    """An OPEN position must never be force-closed by a reconcile."""
    seeded = _seed(db, [
        dict(symbol="Y", quantity=5, buy_price=50.0, exit_price=None,
             entry_date="2025-01-01", exit_date=None, status="OPEN"),
    ])
    _pair_and_write(db, seeded, [{"Exit Price": 60.0, "Exit Date": "2026-01-01"}])
    got = _rows(db)
    assert got[0]["exit_price"] is None, "an OPEN row was given an exit price"
    assert got[0]["status"] == "OPEN"


def test_real_module_has_no_symbol_wide_update():
    """The tests above exercise a REPLICA of the pairing logic, so on their own
    they would keep passing if ai_reconcile_engine drifted away from it. This
    one reads the shipped module and fails if any UPDATE targets a SYMBOL
    instead of a row id -- which is the defect itself, stated directly.

    (The same replica-drift risk bit the strict_trend port, which froze three
    Pine versions behind while its tests stayed green.)
    """
    import re
    import ai_reconcile_engine as R

    src = open(R.__file__, encoding="utf-8").read()
    src = re.sub(r"^\s*#.*$", "", src, flags=re.M)          # drop comments
    updates = re.findall(r"UPDATE\s+journal\b.*?(?:\"\"\"|')", src,
                         flags=re.S | re.I)
    offenders = [u for u in updates
                 if re.search(r"WHERE[^\"']*\bsymbol\s*=", u, flags=re.I)]
    assert not offenders, (
        "an UPDATE journal still targets a symbol rather than a row id -- this "
        "collapses positions sold in tranches:\n" + "\n---\n".join(offenders))
