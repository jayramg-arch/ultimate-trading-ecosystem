"""open_risk: risk from LTP vs below-cost risk, and the trim plan order."""
import pandas as pd

import open_risk as ork


def _journal(rows):
    return pd.DataFrame(rows, columns=["symbol", "quantity", "buy_price", "timeframe"])


def test_position_risk_counts_each_leg_and_locked():
    j = _journal([("AAA", 100, 100.0, "Swing"), ("BBB", 10, 50.0, "Positional")])
    gtts = {"AAA": [{"sl_trigger": 90.0, "sl_qty": 60}, {"sl_trigger": 92.0, "sl_qty": 40}],
            "BBB": [{"sl_trigger": 55.0, "sl_qty": 10}]}
    df = ork.position_risk(gtts, [], {"AAA": 95.0, "BBB": 60.0}, j).set_index("symbol")
    assert df.at["AAA", "risk_ltp"] == 60 * 5 + 40 * 3
    assert df.at["AAA", "risk_cap"] == 60 * 10 + 40 * 8
    assert df.at["BBB", "locked"] and df.at["BBB", "risk_cap"] == 0 and df.at["BBB", "risk_ltp"] == 50


def test_uncovered_shares_flagged():
    j = _journal([("AAA", 100, 100.0, "Swing")])
    df = ork.position_risk({"AAA": [{"sl_trigger": 90.0, "sl_qty": 30}]}, [], {"AAA": 95.0}, j)
    assert df.iloc[0]["uncovered"] == 70


def test_trim_plan_cuts_failed_swing_before_locked_winner():
    j = _journal([("LOSE", 100, 100.0, "Swing"), ("WIN", 100, 50.0, "Positional")])
    gtts = {"LOSE": [{"sl_trigger": 80.0, "sl_qty": 100}], "WIN": [{"sl_trigger": 60.0, "sl_qty": 100}]}
    df = ork.position_risk(gtts, [], {"LOSE": 90.0, "WIN": 70.0}, j)   # risk 1000 each
    p = ork.trim_plan(df, 1500.0, {"LOSE": "NOT ELIGIBLE", "WIN": "HOLD (qualifies)"}).set_index("symbol")
    assert p.at["LOSE", "trim"] == 50 and p.at["WIN", "trim"] == 0
    assert abs(p["risk_after"].sum() - 1500.0) < 1e-6


def test_winner_on_watch_is_not_trimmed_first():
    row = {"ltp": 110.0, "entry": 100.0, "locked": False}
    assert ork.trim_class(row, "WATCH") == 4
    assert ork.trim_class({"ltp": 90.0, "entry": 100.0, "locked": False}, "WATCH") == 1


def test_within_budget_trims_nothing():
    j = _journal([("AAA", 10, 100.0, "Swing")])
    df = ork.position_risk({"AAA": [{"sl_trigger": 90.0, "sl_qty": 10}]}, [], {"AAA": 95.0}, j)
    assert ork.trim_plan(df, 1000.0, {})["trim"].sum() == 0
