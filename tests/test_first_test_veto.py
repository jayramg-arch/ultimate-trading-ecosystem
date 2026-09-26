"""FIRST TEST (26-Sep-2026, Jay): Stage 3/4 and/or weekly trend DOWN = straight veto.
The board's S4-GO column must mirror S4: DOWN blocks, SIDEWAYS/UP pass, unknown never blocks."""
import gm_trigger_board as g

CTX = {"relvol": 1.5, "bar_ok": True, "support": {"at_support": True}}


def _go(stage="2", wt=None):
    return g.s4go_status(5, CTX, True, "bull", stage=stage, rrg_tradeable=True, fund_ok=True, w_trend=wt)


def test_weekly_down_is_vetoed():
    assert _go(wt=-1).startswith("⛔ W trend down")


def test_sideways_and_up_pass():
    assert _go(wt=0).startswith("5/5")
    assert _go(wt=1).startswith("5/5")


def test_unknown_weekly_trend_never_vetoes():
    assert _go(wt=None).startswith("5/5")


def test_stage_3_still_reports_as_stage():
    assert _go(stage="3", wt=-1).startswith("⛔ Stage 3")
