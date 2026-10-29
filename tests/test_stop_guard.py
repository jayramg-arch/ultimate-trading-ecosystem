"""stop_guard + gap-aware sizing (29-Oct-2026): no Disaster SL comes down until the quantity
has, and an entry is sized on the larger of the stop distance and the stock's worst gap."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gap_risk as gr  # noqa: E402
import stop_guard as sg  # noqa: E402


def _leg(oid, trig, qty):
    return {"order_id": oid, "sl_trigger": trig, "sl_qty": qty, "flag": "OCO", "leg_name": "STOP_LOSS_LEG"}


BASE = {"orders": {"A": 300.0, "B": 300.0}, "floor": 300.0, "covered": 200, "qty": 200}


def test_first_sight_sets_the_baseline():
    r = sg.evaluate("X", [_leg("A", 300, 100)], 200, 350, 340, 10, 15000, None)
    assert r["kind"] == "NEW" and r["new_base"]["floor"] == 300


def test_a_raised_stop_moves_the_baseline_up():
    r = sg.evaluate("X", [_leg("A", 310, 100), _leg("B", 310, 100)], 200, 350, 340, 10, 15000, BASE)
    assert r["kind"] == "RAISED" and r["new_base"]["floor"] == 310


def test_lowering_with_the_same_shares_is_a_violation_naming_the_sell():
    # 200 sh, cost 350, new stop 280: 70 x 200 = 14,000 > rule 10,000 x 1.05 -> allowed 150
    r = sg.evaluate("X", [_leg("A", 280, 100), _leg("B", 300, 100)], 200, 350, 340, 10, 10000, BASE)
    assert r["kind"] == "VIOLATION" and r["allowed"] == 150 and r["sell_first"] == 50
    assert r["new_base"] is None and [a for _, a in r["lowered"]] == [300.0]
    assert not r["through"]


def test_lowering_after_the_cut_is_accepted():
    r = sg.evaluate("X", [_leg("A", 280, 75), _leg("B", 280, 75)], 150, 350, 340, 10, 10000, BASE)
    assert r["kind"] == "ACCEPTED" and r["new_base"]["floor"] == 280


def test_a_stop_still_above_cost_is_free_to_lower():
    r = sg.evaluate("X", [_leg("A", 360, 100), _leg("B", 360, 100)], 200, 350, 420, 10,
                    10000, {"orders": {"A": 380, "B": 380}, "floor": 380, "covered": 200})
    assert r["kind"] == "ACCEPTED"


def test_cancel_and_replace_lower_is_caught_but_new_cover_is_not():
    lower = sg.evaluate("X", [_leg("C", 280, 100), _leg("B", 300, 100)], 200, 350, 340, 10, 10000, BASE)
    assert lower["kind"] == "VIOLATION"
    cover = sg.evaluate("X", [_leg("A", 300, 100), _leg("B", 300, 100), _leg("R", 290, 50)], 250, 350, 340, 10,
                        10000, BASE)
    assert cover["kind"] != "VIOLATION"


def test_never_reverts_into_the_price():
    # approved 300, LTP 302, ATR 10 -> within 0.5 ATR: putting it back would sell at once
    r = sg.evaluate("X", [_leg("A", 280, 100), _leg("B", 280, 100)], 200, 350, 302, 10, 10000, BASE)
    assert r["kind"] == "VIOLATION" and r["through"]


def test_entry_qty_sizes_on_the_wider_of_stop_and_gap():
    # entry 100, stop 90 (10/sh); worst gap -15% -> 15/sh; budget 15,000
    q = gr.entry_qty(100, 90, -15.0, 15000)
    assert (q["qty_stop"], q["qty_gap"], q["qty"], q["binding"]) == (1500, 1000, 1000, "gap")
    q2 = gr.entry_qty(100, 80, -15.0, 15000)          # stop wider than the gap: the stop binds
    assert q2["qty"] == q2["qty_stop"] == 750 and q2["binding"] == "stop"
    q3 = gr.entry_qty(100, 90, -15.0, 15000, cap_rupees=50000)
    assert q3["qty"] == 500 and q3["binding"] == "cap"


def test_same_risk_and_rule_quantities():
    assert gr.lower_stop_qty(257, 387.36, 251.5, 15000 * 1.05) == (115, 142)   # M&MFIN 23-Oct
    assert gr.lower_stop_qty(10, 100, 120, 1000) == (10, 0)                    # above cost
    assert gr.same_risk_qty(100, 200, 180, 180, 160) == 50                     # risk 2,000 kept


def test_unmatched_widenings_use_the_guard_rule():
    import stop_history as sh
    ev = pd.DataFrame([
        {"date": "2026-10-01", "symbol": "X", "kind": "WIDENED", "from": 300.0, "to": 280.0, "pct": -6.7,
         "rupees": 4000.0, "below_entry": True, "qty_from": 200.0, "qty_to": 200.0, "avg": 350.0},
        {"date": "2026-10-02", "symbol": "Y", "kind": "WIDENED", "from": 300.0, "to": 280.0, "pct": -6.7,
         "rupees": 3000.0, "below_entry": True, "qty_from": 200.0, "qty_to": 150.0, "avg": 350.0},
    ])
    u = sh.unmatched_widenings(ev, budget_for=lambda s: 10000.0)
    assert list(u["symbol"]) == ["X"] and int(u.iloc[0]["sell_first"]) == 50


def test_house_size_qty_takes_the_gap_when_it_is_wider(monkeypatch):
    import house_policy as hp
    monkeypatch.setattr(hp, "risk_pct_for", lambda s, add=False: 0.5)
    monkeypatch.setattr(hp, "max_alloc", lambda: 10_000_000.0)
    q0, _ = hp.size_qty("X", 100, 90, capital=3_000_000)                 # 15,000 / 10
    q1, n1 = hp.size_qty("X", 100, 90, capital=3_000_000, gap_pct=-15.0)  # 15,000 / 15
    q2, _ = hp.size_qty("X", 100, 80, capital=3_000_000, gap_pct=-15.0)   # stop wider: 15,000 / 20
    assert (q0, q1, q2) == (1500, 1000, 750) and "worst gap" in n1
