"""13-Oct-2026: positional GM targets follow the R-canon off the (floored) stop, and the
journal's R unit is frozen at entry so a widened or trailed Dhan stop never moves targets."""
import sqlite3

import commander_core as cc
import journal_core as jc


def test_positional_plan_gets_3r_5r_off_its_stop(monkeypatch):
    monkeypatch.setattr(cc, "plan_type_ctx", lambda ctx: "positional")
    t1, t2 = cc._canon_targets({}, 100.0, 88.0)           # R = 12 (a 4xATR(D) stop at ATR 3)
    assert (t1, t2) == (136.0, 160.0)


def test_swing_and_bad_stops_keep_the_plans_own_target(monkeypatch):
    monkeypatch.setattr(cc, "plan_type_ctx", lambda ctx: "swing")
    assert cc._canon_targets({}, 100.0, 95.0) == (None, None)
    monkeypatch.setattr(cc, "plan_type_ctx", lambda ctx: "positional")
    assert cc._canon_targets({}, 100.0, 101.0) == (None, None)       # stop above entry
    assert cc._canon_targets({}, None, 90.0) == (None, None)


def test_initial_sl_is_frozen_once_and_never_overwritten(tmp_path):
    db = str(tmp_path / "j.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE journal (id INTEGER PRIMARY KEY, symbol TEXT, status TEXT, "
                "stoploss REAL, buy_price REAL)")
    con.executemany("INSERT INTO journal (symbol,status,stoploss,buy_price) VALUES (?,?,?,?)",
                    [("A", "OPEN", 90.0, 100.0),      # below entry -> frozen
                     ("B", "OPEN", 105.0, 100.0),     # trailed above entry -> not frozen
                     ("C", "CLOSED", 90.0, 100.0),    # closed -> untouched
                     ("D", "OPEN", 0.0, 100.0)])      # no stop -> untouched
    con.commit(); con.close()
    assert jc.freeze_initial_sl(db) == 1
    con = sqlite3.connect(db)
    con.execute("UPDATE journal SET stoploss = 80.0 WHERE symbol='A'")      # widened for noise
    con.commit(); con.close()
    assert jc.freeze_initial_sl(db) == 0                                   # nothing re-frozen
    con = sqlite3.connect(db)
    got = dict(con.execute("SELECT symbol, initial_sl FROM journal").fetchall())
    assert got == {"A": 90.0, "B": None, "C": None, "D": None}
