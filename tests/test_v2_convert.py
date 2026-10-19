"""v2 CONVERT (PREREG_pyramid_slices_vs_convert): a v1 holding becomes v2's, resized at once.
Runs v2_take.py against COPIES of the journal and the v2 ledger - never the live files."""
import json
import os
import shutil
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(args, env):
    return subprocess.run([sys.executable, os.path.join(HERE, "v2_take.py")] + args, env=env,
                          capture_output=True, text=True, cwd=HERE, timeout=300)


def test_convert_closes_v1_and_opens_v2(tmp_path):
    db = tmp_path / "journal.db"
    shutil.copy2(os.path.join(HERE, "trade_journal_v6.db"), db)
    con = sqlite3.connect(db)
    con.execute("INSERT INTO journal (symbol, trade_type, status, quantity, buy_price, stoploss, entry_date, setup, "
                "timeframe) VALUES ('ZZCONV', 'LONG', 'OPEN', 80, 1000, 900, '2026-08-01', 'POS-BO', 'Positional')")
    con.commit()
    con.close()
    env = dict(os.environ, COMMANDER_JOURNAL_DB=str(db), V2_LEDGER=str(tmp_path / "book.json"))
    r = _run(["ZZCONV", "--price", "1100", "--qty", "5"], env)          # a plain buy is refused
    assert r.returncode == 2 and "--convert" in r.stderr
    r = _run(["ZZCONV", "--convert", "--price", "1100", "--keep", "30", "--date", "2026-10-21"], env)
    assert r.returncode == 0, r.stderr + r.stdout
    con = sqlite3.connect(db)
    rows = con.execute("SELECT status, quantity, buy_price, exit_price, exit_reason, setup, stoploss FROM journal "
                       "WHERE symbol='ZZCONV' ORDER BY id").fetchall()
    con.close()
    assert rows[0][0] == "CLOSED" and rows[0][3] == 1100 and rows[0][4] == "Converted to v2"
    assert rows[1][0] == "OPEN" and rows[1][1] == 30 and rows[1][2] == 1100 and rows[1][5] == "POS-V2"
    assert rows[1][6] is None                                            # v2 carries no stop
    book = json.load(open(tmp_path / "book.json"))
    assert book["open"]["ZZCONV"]["sh"] == 30 and book["open"]["ZZCONV"]["stop"] is None
    r = _run(["ZZCONV", "--convert", "--price", "1100", "--keep", "30"], env)   # already v2
    assert r.returncode == 2
