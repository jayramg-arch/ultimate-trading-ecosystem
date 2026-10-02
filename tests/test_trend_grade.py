"""Trend alignment grade (2-Oct-2026) - display only; these pin the five outcomes and
the rule that an unknown trend never fails a test. Mirrors S4Core.trendGrade."""
import commander_core as cc


def g(*a, **k):
    return cc.trend_grade(*a, **k)[0]


def test_f_on_stage_3_or_4():
    assert g("3") == "F" and g("4", 1, 1) == "F"


def test_not_stage2_or_weekly_down():
    assert g("1", 1, 1) == "–"
    assert g("2", -1, 1) == "–"


def test_b_daily_down():
    assert g("2", 1, -1, 0.5, True, True, True) == "B"


def test_c_extended():
    assert g("2", 1, 1, cc.TREND_EXT_WARN_ATR, True, True, True) == "C"


def test_a_plus_and_pending():
    assert g("2", 1, 0, 0.5, True, True, True) == "A+"
    grade, why = cc.trend_grade("2", 1, 1, 0.5, False, True, True)
    assert grade == "A+ pending" and "daily location" in why


def test_unknown_trends_never_fail():
    assert g("2", None, None, None, True, True, True) == "A+"
