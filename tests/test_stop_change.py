"""stop_change (29-Oct-2026): a Disaster SL changed from Web Commander is sent only when every
blocking condition holds - and never by these tests: Dhan, the journal, the guard state and
Telegram are all fakes or temp files."""
import os
import sqlite3
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import stop_change as sc  # noqa: E402


class FakeDhan:
    LIMIT = "LIMIT"

    def __init__(self, ok=True):
        self.calls, self.ok = [], ok

    def modify_forever(self, **kw):
        self.calls.append(kw)
        return {"status": "success"} if self.ok else {"status": "failure", "remarks": "rejected"}


def _legs(trig, q1=100, q2=100):
    return {"X": [{"order_id": "A", "sl_trigger": trig, "sl_qty": q1, "flag": "OCO", "leg_name": "STOP_LOSS_LEG"},
                  {"order_id": "B", "sl_trigger": trig, "sl_qty": q2, "flag": "OCO", "leg_name": "STOP_LOSS_LEG"}]}


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    import gtt_auto_shield as gas
    import house_policy as hp
    import sl_board
    import ai_risk_manager
    import digest_common
    import journal_path
    monkeypatch.setattr(gas, "stop_prices", lambda s, t: (round(t * 2) / 2, round(t * 2) / 2 - 1.0))
    monkeypatch.setattr(hp, "sizing_capital", lambda: (2000000.0, "test"))
    monkeypatch.setattr(hp, "risk_pct_for", lambda s, add=False: 0.5)          # budget 10,000
    monkeypatch.setattr(sl_board, "build", lambda symbols=None: (pd.DataFrame(), {}))
    monkeypatch.setattr(ai_risk_manager, "get_atr", lambda s: 10.0)
    monkeypatch.setattr(digest_common, "send", lambda t: True)
    db = tmp_path / "j.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE journal (symbol TEXT, status TEXT, stoploss REAL, manual_sl_override REAL)")
    con.execute("INSERT INTO journal VALUES ('X','OPEN',300,300)")
    con.commit()
    con.close()
    monkeypatch.setattr(journal_path, "JOURNAL_DB", str(db))
    return db


BOOK = [{"symbol": "X", "qty": 200, "avg": 350.0, "broker_ltp": 340.0, "setup": ""}]


def _names(p, failed_only=False):
    return [c["name"] for c in p["checks"] if (not c["ok"] if failed_only else True) and c["block"]]


def test_lowering_with_too_many_shares_is_refused_and_names_the_sale():
    p = sc.plan("X", 280, dhan=FakeDhan(), book=BOOK, legs_by=_legs(300))
    assert not p["ok"] and p["direction"] == "lower"
    assert "Shares fit the rule at the new stop" in _names(p, failed_only=True)
    assert p["allowed"] == 150 and p["sell_first"] == 50       # 10,500 / 70 = 150


def test_apply_sends_nothing_when_a_condition_fails():
    d = FakeDhan()
    r = sc.apply("X", 280, dhan=d, book=BOOK, legs_by=_legs(300))
    assert not r["ok"] and d.calls == []


def test_after_the_sale_every_leg_is_modified_and_the_trail_floor_follows(_offline):
    d = FakeDhan()
    book = [{**BOOK[0], "qty": 150}]
    legs = _legs(300, 75, 75)
    r = sc.apply("X", 280, dhan=d, book=book, legs_by=legs,
                 reread=lambda: _legs(280, 75, 75))
    assert r["ok"] and len(d.calls) == 2
    assert {c["trigger_price"] for c in d.calls} == {280.0} and all(c["price"] < 280 for c in d.calls)
    con = sqlite3.connect(_offline)
    assert con.execute("SELECT stoploss, manual_sl_override FROM journal").fetchone() == (280.0, 280.0)
    import stop_guard as sg
    assert sg.load_state()["X"]["floor"] == 280.0              # the guard will not flag it


def test_legs_bigger_than_the_holding_block_the_change():
    book = [{**BOOK[0], "qty": 150}]
    p = sc.plan("X", 280, dhan=FakeDhan(), book=book, legs_by=_legs(300, 100, 100))   # 200 covered
    assert "Stop legs ≤ holding" in _names(p, failed_only=True)


def test_never_into_the_price():
    p = sc.plan("X", 338, dhan=FakeDhan(), book=BOOK, legs_by=_legs(330))          # 0.5 x ATR = 5
    assert "Below the price" in _names(p, failed_only=True)


def test_raising_needs_no_cut_and_a_stop_above_cost_is_free():
    up = sc.plan("X", 310, dhan=FakeDhan(), book=BOOK, legs_by=_legs(300))
    assert up["ok"] and up["direction"] == "raise"
    rich = [{"symbol": "X", "qty": 200, "avg": 200.0, "broker_ltp": 340.0, "setup": ""}]
    down = sc.plan("X", 280, dhan=FakeDhan(), book=rich, legs_by=_legs(300))
    assert down["ok"]                                            # 280 is still above the 200 cost


def test_v2_holdings_and_unknown_names_are_refused():
    v2 = [{**BOOK[0], "setup": "POS-V2"}]
    assert not sc.plan("X", 280, dhan=FakeDhan(), book=v2, legs_by=_legs(300))["ok"]
    assert not sc.plan("Y", 280, dhan=FakeDhan(), book=BOOK, legs_by=_legs(300))["ok"]
