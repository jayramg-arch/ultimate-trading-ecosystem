"""system_equity.py - daily equity per system (v1 / v2 / legacy), on a scratch journal + ledger."""
import datetime as dt
import importlib
import sqlite3

import pytest


def _journal(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE journal (id INTEGER PRIMARY KEY, symbol TEXT, status TEXT, quantity REAL, "
                "buy_price REAL, exit_price REAL, exit_date TEXT, setup TEXT, origin TEXT)")
    con.execute("INSERT INTO journal VALUES (1,'AAA','OPEN',10,100,NULL,NULL,'POS-BO','v1')")
    con.execute("INSERT INTO journal VALUES (2,'BBB','OPEN',5,200,NULL,NULL,'','legacy')")
    con.commit()
    con.close()


@pytest.fixture
def se(tmp_path, monkeypatch):
    monkeypatch.setenv("SYSTEM_EQUITY_DIR", str(tmp_path))
    monkeypatch.setenv("V2_LEDGER", str(tmp_path / "book.json"))
    monkeypatch.setenv("V2_CAPITAL", "1000000")
    import house_policy
    import v2_ledger
    import system_equity
    importlib.reload(v2_ledger)
    mod = importlib.reload(system_equity)
    monkeypatch.setattr(house_policy, "sizing_capital", lambda: (3000000.0, "test"))
    px = {"AAA": 110.0, "BBB": 190.0, "CCC": 55.0, "DDD": 105.0, "^CRSLDX": 20000.0}
    monkeypatch.setattr(mod, "_close", lambda s, d: px.get(s))
    return mod, v2_ledger, tmp_path


def test_first_day_and_flows(se):
    mod, vl, tmp = se
    db = str(tmp / "j.db")
    _journal(db)
    d1 = dt.date(2026, 10, 19)
    r = {x["system"]: x for x in mod.snapshot(d1, db)}
    assert r["v1"]["equity"] == pytest.approx(2000000.0)          # capital less v2's, book at market
    assert r["v1"]["mv"] == pytest.approx(1100.0)
    assert r["legacy"]["equity"] == pytest.approx(950.0) and r["legacy"]["cash"] == 0
    assert r["v2"]["equity"] == pytest.approx(1000000.0)
    assert all(x["nav"] == 1.0 for x in r.values())
    assert mod.snapshot(d1, db) == []                             # a date is written once

    con = sqlite3.connect(db)                                      # AAA sold @120, CCC bought, v2 buys DDD
    con.execute("UPDATE journal SET status='CLOSED', exit_price=120, exit_date='2026-10-22' WHERE id=1")
    con.execute("INSERT INTO journal VALUES (3,'CCC','OPEN',2,50,NULL,NULL,'POS-BO','v1')")
    con.commit()
    con.close()
    vl.buy("DDD", 100.0, 10, None, "2026-10-22")
    d2 = dt.date(2026, 10, 22)
    r = {x["system"]: x for x in mod.snapshot(d2, db)}
    i = mod.IDLE_CASH_RATE * 3 / 365.0
    v1_cash = (2000000.0 - 1100.0) * (1 + i) + 1200.0 - 100.0
    assert r["v1"]["cash"] == pytest.approx(v1_cash, abs=0.01)
    assert r["v1"]["equity"] == pytest.approx(v1_cash + 110.0, abs=0.01)
    assert r["v1"]["nav"] == pytest.approx((v1_cash + 110.0) / 2000000.0, abs=1e-6)
    assert r["v2"]["cash"] == pytest.approx(1000000.0 * (1 + i) - 1000.0, abs=0.01)
    assert r["v2"]["mv"] == pytest.approx(1050.0) and r["v2"]["n"] == 1
    assert r["legacy"]["nav"] == pytest.approx(1.0)


def test_transfer_is_not_return(se):
    mod, vl, tmp = se
    db = str(tmp / "j.db")
    _journal(db)
    mod.snapshot(dt.date(2026, 10, 19), db)
    open(tmp / "system_transfers.csv", "w").write("date,system,amount,note\n2026-10-20,v2,500000,top-up\n")
    r = {x["system"]: x for x in mod.snapshot(dt.date(2026, 10, 20), db)}
    assert r["v2"]["flow"] == 500000
    i = mod.IDLE_CASH_RATE / 365.0
    assert r["v2"]["nav"] == pytest.approx(1 + i, abs=1e-6)       # the top-up is not a gain


def test_reclassified_row_moves_value_not_return(se):
    mod, vl, tmp = se
    db = str(tmp / "j.db")
    _journal(db)
    mod.snapshot(dt.date(2026, 10, 19), db)
    con = sqlite3.connect(db)
    con.execute("UPDATE journal SET origin='v1' WHERE id=2")       # Jay re-marks BBB as v1
    con.commit()
    con.close()
    r = {x["system"]: x for x in mod.snapshot(dt.date(2026, 10, 20), db)}
    assert r["legacy"]["flow"] == pytest.approx(-950.0) and r["v1"]["flow"] == pytest.approx(950.0)
    assert r["legacy"]["equity"] == pytest.approx(0.0)
