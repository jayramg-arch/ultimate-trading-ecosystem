"""trade_class: the swing -> positional conversion gates and the weekly re-qualification."""
import os
import sqlite3

import numpy as np
import pandas as pd
import pytest

import trade_class as tc


def _frame(n=420, start=100.0, drift=0.002, noise=0.01, seed=1, tail=None):
    rng = np.random.default_rng(seed)
    r = drift + noise * rng.standard_normal(n)
    if tail is not None:
        r[-len(tail):] = tail
    c = start * np.exp(np.cumsum(r))
    idx = pd.bdate_range("2024-01-01", periods=n)
    h = c * 1.01
    l = c * 0.99
    return pd.DataFrame({"Open": c, "High": h, "Low": l, "Close": c, "Volume": 1e6}, index=idx)


@pytest.fixture(autouse=True)
def _fixed_budget(monkeypatch):
    monkeypatch.setattr(tc, "_budget", lambda sym, mult=1.0: 15000.0 * mult)


def test_uptrend_converts_with_locked_stop():
    f = tc.daily_facts("X", _frame())
    assert f and f["stage"] == 2 and not f["below200"] and f["atr_pct"] < 4
    entry = f["close"] * 0.7                         # well in profit
    ck = tc.conversion_check("X", 100, entry, facts=f, sector=("S", 2))
    assert ck["verdict"] == "CONVERT"
    assert ck["locked"] and ck["risk_now"] == 0
    assert ck["new_stop"] <= f["close"] - 4.0 * f["atr"] + 0.05


def test_stop_never_closer_than_floor():
    f = tc.daily_facts("X", _frame())
    s = tc.positional_stop(f)
    assert s <= f["close"] - 4.0 * f["atr"] + 0.05


def test_losing_but_qualifying_is_salvage_at_half_risk():
    f = tc.daily_facts("X", _frame())
    entry = f["close"] * 1.05                       # under water, stop below entry
    ck = tc.conversion_check("X", 10_000, entry, facts=f, sector=("S", 2))
    assert ck["verdict"].startswith("SALVAGE")
    assert ck["budget"] == 7500
    per = f["close"] - ck["new_stop"]
    assert ck["max_qty"] == int(7500 // per) and ck["trim"] == 10_000 - ck["max_qty"]


def test_below_200dma_is_not_eligible():
    tail = np.full(160, -0.004)                     # a long slide under the 200-DMA
    f = tc.daily_facts("X", _frame(tail=tail))
    assert f["below200"]
    ck = tc.conversion_check("X", 10, f["close"] * 0.5, facts=f, sector=("S", 2))
    assert ck["verdict"] == "NOT ELIGIBLE"
    assert any("200-DMA" in r for r in ck["reasons"])


def test_stage4_sector_is_soft():
    f = tc.daily_facts("X", _frame())
    ck = tc.conversion_check("X", 100, f["close"] * 0.7, facts=f, sector=("Bank", 4))
    assert ck["verdict"] == "CONVERT" and ck["soft_note_needed"]


def test_requalify_flags_stage_3_or_4():
    tail = np.full(160, -0.004)
    f = tc.daily_facts("X", _frame(tail=tail))
    rq = tc.requalify("X", facts=f)
    assert rq["status"] == "EXIT REVIEW" and rq["stage"] in (3, 4)
    ok = tc.requalify("X", facts=tc.daily_facts("X", _frame()))
    assert ok["status"] == "OK"


def test_record_conversion_writes_journal_and_event(tmp_path, monkeypatch):
    db = tmp_path / "j.db"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE journal (id INTEGER PRIMARY KEY, symbol TEXT, timeframe TEXT, "
                  "rationale TEXT, status TEXT)")
        c.execute("INSERT INTO journal (symbol, timeframe, rationale, status) VALUES ('ABC','Swing','r','OPEN')")
    monkeypatch.setattr(tc, "_journal", lambda: str(db))
    ev = tmp_path / "ev.csv"
    monkeypatch.setattr(tc, "EVENTS", str(ev))
    assert tc.record_conversion("abc", 123.45, "CONVERT", note="gates passed")
    with sqlite3.connect(db) as c:
        tf, rat = c.execute("SELECT timeframe, rationale FROM journal").fetchone()
    assert tf == "Positional" and "swing -> positional" in rat and "123.45" in rat
    assert "ABC" in ev.read_text(encoding="utf-8")
