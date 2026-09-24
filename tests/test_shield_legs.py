"""The shield must place the house exit structure — two OCO legs + a stop-only runner —
sized by the same partial_qty_for the backtest uses (Jay, 24-Sep-2026)."""
from gtt_auto_shield import plan_legs


def _q(legs):
    return [(l["kind"], l["qty"], l["target"]) for l in legs]


def test_positional_is_25_25_plus_half_runner():
    legs = plan_legs(100, "POS-BO", "Positional", t1=130.0, t2=150.0)
    assert _q(legs) == [("OCO", 25, 130.0), ("OCO", 25, 150.0), ("SL", 50, None)]


def test_swing_breakout_is_33_33_plus_runner():
    legs = plan_legs(90, "SWG-PB", "Swing", t1=110.0, t2=120.0)
    assert _q(legs) == [("OCO", 29, 110.0), ("OCO", 29, 120.0), ("SL", 32, None)]


def test_quantities_always_sum_to_the_holding():
    for q in (4, 5, 7, 13, 101, 999):
        for setup in ("POS-BO", "SWG-PB", "SWG-REV", None):
            legs = plan_legs(q, setup, None, t1=10.0, t2=12.0)
            assert sum(l["qty"] for l in legs) == q


def test_missing_t2_leaves_a_bigger_runner_not_a_naked_leg():
    legs = plan_legs(100, "POS-BO", "Positional", t1=130.0, t2=None)
    assert _q(legs) == [("OCO", 25, 130.0), ("SL", 75, None)]


def test_legacy_target_is_used_when_t1_missing():
    legs = plan_legs(100, "POS-BO", "Positional", t1=None, t2=None, target=140.0)
    assert legs[0]["target"] == 140.0


def test_tiny_position_is_one_oco():
    assert _q(plan_legs(3, "POS-BO", "Positional", t1=130.0, t2=150.0)) == [("OCO", 3, 130.0)]


def test_no_target_means_no_plan():
    assert plan_legs(100, "POS-BO", "Positional") == []
