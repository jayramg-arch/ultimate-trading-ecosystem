"""Friday in-session forming week (25-Sep-2026).

Both weekly engines treated the week ending TODAY as confirmed while Friday's session was
still trading. The guard is live-only: a pinned (replay) date is a closed bar.
"""
import pandas as pd

import pa_patterns as pap


def test_a_past_friday_is_never_still_trading():
    assert pap._friday_still_trading("2026-09-18") is False


def test_replay_is_never_live(monkeypatch):
    import data_provider as dp
    monkeypatch.setattr(dp, "get_pinned_date", lambda: "2026-09-25")
    assert pap._friday_still_trading(pd.Timestamp.today()) is False


def test_confirmed_weeks_drop_a_week_that_has_not_reached_friday():
    idx = pd.bdate_range("2026-08-03", "2026-09-23")          # ends Wednesday
    df = pd.DataFrame({"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0, "Volume": 1.0}, index=idx)
    wk = pap._confirmed_weekly_ohlcv(df)
    assert wk.index[-1] == pd.Timestamp("2026-09-18")
