"""The intraday session-fill must ask Dhan one day PAST the target session: Dhan's to_date
is exclusive, so to_date=target never returned the target day (7-Oct-2026)."""
import datetime as dt

import pandas as pd

import dhan_ohlcv as d


def test_session_fill_requests_one_day_past_target(monkeypatch):
    target = dt.date(2026, 10, 6)
    monkeypatch.setattr(d, "_last_completed_session_date", lambda: target)
    seen = {}

    def fake_intraday(symbol, from_date=None, to_date=None, interval=15):
        seen["to"] = to_date
        idx = pd.to_datetime(["2026-10-06 09:15", "2026-10-06 15:15"])
        return pd.DataFrame({"Open": [10, 11], "High": [12, 12], "Low": [9, 10], "Close": [11, 11.5],
                             "Volume": [100, 200]}, index=idx)

    monkeypatch.setattr(d, "fetch_intraday", fake_intraday)
    daily = pd.DataFrame({"Open": [9], "High": [10], "Low": [8], "Close": [9.5], "Volume": [50]},
                         index=pd.to_datetime(["2026-10-05"]))
    out = d._append_completed_session_from_intraday("X", {}, daily)
    assert seen["to"] == "2026-10-07"
    assert out.index[-1].date() == target and float(out["Close"].iloc[-1]) == 11.5
