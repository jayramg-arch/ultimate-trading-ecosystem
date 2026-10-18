"""v2 ledger (Doc 42 §8 D2): v2's own shares, incl. slices of shared holdings."""
import pandas as pd

import v2_ledger as vl


def _iso(tmp_path, monkeypatch):
    monkeypatch.setattr(vl, "LEDGER", str(tmp_path / "real_book.json"))


def test_buy_average_and_partial_sell(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    vl.buy("LAURUSLABS", 1000.0, 10, 960.0, "2026-10-21", shared=True)
    q = vl.buy("LAURUSLABS", 1100.0, 10, 1050.0, "2026-11-04")
    assert abs(q["entry"] - 1050.0) < 1e-9 and q["sh"] == 20 and q["stop"] == 1050.0
    assert q["entry_date"] == "2026-10-21" and q["shared"] is True
    rec = vl.sell("LAURUSLABS", 1200.0, 5, "2026-12-01")
    assert rec["sh"] == 5 and vl.load()["open"]["LAURUSLABS"]["sh"] == 15
    assert abs(vl.realised() - 5 * 150.0) < 1e-9
    vl.sell("LAURUSLABS", 1200.0)
    assert "LAURUSLABS" not in vl.load()["open"]
    assert vl.sell("NOPE", 1.0) is None


def test_reconcile_closes_a_slice_whose_holding_was_sold(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    vl.buy("ABC", 100.0, 10, 90.0, "2026-10-21")
    vl.buy("XYZ", 50.0, 20, 45.0, "2026-10-21", shared=True)
    J = pd.DataFrame([
        {"symbol": "ABC", "status": "CLOSED", "quantity": 10, "exit_price": 91.0, "exit_date": "2026-11-02"},
        {"symbol": "XYZ", "status": "OPEN", "quantity": 12, "exit_price": None, "exit_date": None},
    ])
    notes = vl.reconcile(J)
    d = vl.load()
    assert "ABC" not in d["open"] and d["closed"][-1]["exit"] == 91.0
    assert "XYZ" in d["open"]                                  # still open, but flagged
    assert any("XYZ" in n and "--sell" in n for n in notes)
