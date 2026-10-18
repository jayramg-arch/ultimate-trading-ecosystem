"""v2 house rules (PREREG_v2_house_rules): schedule, tiers, tax netting."""
import datetime as dt

import pandas as pd

import v2_house as vh


def _d(s):
    return pd.Timestamp(s)


def test_wednesday_rule_normal_week():
    # Tue 20-Oct-2026 close decides, Wed 21 fills
    assert vh.is_wed_decision(_d("2026-10-20"), _d("2026-10-21"))
    assert not vh.is_wed_decision(_d("2026-10-19"), _d("2026-10-20"))   # Mon -> Tue
    assert not vh.is_wed_decision(_d("2026-10-21"), _d("2026-10-22"))   # Wed -> Thu
    assert not vh.is_wed_decision(_d("2026-10-23"), _d("2026-10-26"))   # Fri -> Mon


def test_wednesday_rule_holidays():
    assert vh.is_wed_decision(_d("2026-10-19"), _d("2026-10-21"))       # Tue holiday: Mon decides
    assert vh.is_wed_decision(_d("2026-10-16"), _d("2026-10-21"))       # Mon+Tue holiday: Fri decides
    assert vh.is_wed_decision(_d("2026-10-20"), _d("2026-10-22"))       # Wed holiday: Tue decides, Thu fills


def test_decision_days_one_per_week():
    idx = pd.bdate_range("2026-01-05", "2026-03-27")
    dd = vh.decision_days(idx, True)
    assert len(dd) == 12 and all(d.weekday() == 1 for d in dd)


def test_tiers_from_house_policy():
    assert vh.tier(1)["new_ok"] is False
    t = vh.tier(4)
    assert t["new_ok"] and t["risk_mult"] == 0.5 and abs(t["cap"] - 0.70) < 1e-9
    t = vh.tier(7)
    assert t["new_ok"] and t["risk_mult"] == 1.0 and t["cap"] is None
    assert vh.tier(None)["new_ok"] is False                          # unknown -> strictest


def test_fy_tax_netting():
    r = [(_d("2025-05-01"), 100.0, False), (_d("2025-06-01"), -40.0, False), (_d("2025-07-01"), 50.0, True)]
    t = vh.fy_tax(r)
    assert abs(t.iloc[0] - (0.20 * 60 + 0.125 * 50)) < 1e-9
    # an ST loss larger than ST gains sets off the LT gain in the same year
    t = vh.fy_tax([(_d("2025-05-01"), -80.0, False), (_d("2025-07-01"), 50.0, True)])
    assert abs(t.iloc[0]) < 1e-9
    # the remaining ST loss is carried into the next FY
    t = vh.fy_tax([(_d("2025-05-01"), -80.0, False), (_d("2025-07-01"), 50.0, True), (_d("2026-05-01"), 100.0, False)])
    assert abs(t.iloc[1] - 0.20 * 70) < 1e-9
    # an LT loss never offsets ST gains
    t = vh.fy_tax([(_d("2025-05-01"), 100.0, False), (_d("2025-06-01"), -30.0, True)])
    assert abs(t.iloc[0] - 20.0) < 1e-9
