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


def _series(days, v1_step, v2_step):
    rows = []
    n1 = n2 = 1.0
    b = 100.0
    for i in range(days):
        d = (dt.date(2026, 10, 19) + dt.timedelta(days=i)).isoformat()
        rows += [{"date": d, "system": "v1", "mv": 0, "cash": 0, "equity": 2e6 * n1, "flow": 0, "nav": n1, "n": 1,
                  "unclassified": 0, "bench": b},
                 {"date": d, "system": "v2", "mv": 0, "cash": 0, "equity": 1e6 * n2, "flow": 0, "nav": n2, "n": 1,
                  "unclassified": 0, "bench": b}]
        n1 *= 1 + v1_step
        n2 *= 1 + v2_step
        b *= 1.0001
    import pandas as pd
    return pd.DataFrame(rows)


def test_metrics_and_capital_rule(se):
    mod, vl, tmp = se
    m = mod.metrics(_series(30, 0.0, 0.001))
    assert m["v2"]["cagr"] is None and m["v2"]["twr"] > 0          # under 90 days: no annualised number
    led = {"open": {}, "closed": [{"entry_date": "2026-10-21"}] * 30}
    r = mod.capital_rule(m, led, dt.date(2027, 6, 1))
    assert r["verdict"].startswith("NOT YET")                         # the edge cannot be judged yet
    m = mod.metrics(_series(400, 0.0, 0.001))
    r = mod.capital_rule(m, led, dt.date(2027, 6, 1))
    assert all(c[1] for c in r["checks"]) and r["verdict"].startswith("MOVE")
    r = mod.capital_rule(mod.metrics(_series(400, 0.001, 0.0005)), led, dt.date(2027, 6, 1))
    assert r["verdict"].startswith("NO MOVE")
    r = mod.capital_rule(m, {"open": {}, "closed": []}, dt.date(2027, 6, 1))
    assert not r["verdict"].startswith("MOVE")
