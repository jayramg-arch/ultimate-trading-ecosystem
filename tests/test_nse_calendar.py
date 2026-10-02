"""nse_calendar (2-Oct-2026): NSE holidays, from the built-in 2026 list so the test
needs no network."""
import datetime as dt

import nse_calendar as c


def test_gandhi_jayanti_is_not_a_trading_day():
    assert not c.is_trading_day(dt.date(2026, 10, 2))
    assert c.is_trading_day(dt.date(2026, 10, 1))


def test_last_completed_session_skips_holiday_and_weekend():
    assert c.last_completed_session(dt.datetime(2026, 10, 2, 20, 0)) == dt.date(2026, 10, 1)
    assert c.last_completed_session(dt.datetime(2026, 10, 5, 10, 0)) == dt.date(2026, 10, 1)
    assert c.last_completed_session(dt.datetime(2026, 10, 5, 16, 0)) == dt.date(2026, 10, 5)


def test_session_open_false_on_holiday():
    assert not c.is_session_open(dt.datetime(2026, 10, 20, 11, 0))      # Dussehra
    assert c.is_session_open(dt.datetime(2026, 10, 19, 11, 0))


def test_prev_trading_day_crosses_holiday():
    assert c.prev_trading_day(dt.date(2026, 10, 21)) == dt.date(2026, 10, 19)
