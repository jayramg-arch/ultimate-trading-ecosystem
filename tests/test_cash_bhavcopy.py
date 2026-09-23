"""Delivery history — the parsing quirks and the one guard that matters.

NSE's sec_bhavdata_full has two traps that are silent rather than loud:
  every column name is prefixed with a SPACE, so df['DELIV_PER'] raises KeyError; and
  DELIV_QTY / DELIV_PER are literally "-" on rows the exchange did not compute.
Either one, wrapped in a bare except, turns the whole feed into an empty frame that
looks like "no data today".

The third test is the one that caught a real bug: a 20-day baseline assembled from
non-consecutive rows. Mid-backfill, ANANDRATHI's mean was drawn from rows spanning
Aug-2025 to Sep-2026 and still printed as a clean 38.8%.
"""
import datetime as dt

import pandas as pd

import cash_bhavcopy as cb

RAW = pd.DataFrame({
    "SYMBOL": ["RELIANCE", "TATASTEEL", "SOMESME", "ODDONE"],
    " SERIES": ["EQ", "EQ", "SM", "BE"],
    " CLOSE_PRICE": [1400.0, 150.0, 10.0, 22.0],
    " TTL_TRD_QNTY": [1_000_000, 2_000_000, 500, 900],
    " DELIV_QTY": [600_000, 900_000, 100, "-"],
    " DELIV_PER": [60.0, 45.0, 20.0, "-"],
})


def test_leading_spaces_in_every_column_name_are_stripped():
    out = cb.derive(RAW, dt.date(2026, 9, 22))
    assert not out.empty, "the space-prefixed headers defeated the parse"
    assert set(out.columns) == set(cb.COLS)
    assert float(out[out["symbol"] == "RELIANCE"]["deliv_pct"].iloc[0]) == 60.0


def test_only_deliverable_series_are_kept():
    out = cb.derive(RAW, dt.date(2026, 9, 22))
    assert set(out["symbol"]) == {"RELIANCE", "TATASTEEL", "ODDONE"}, "SM should be dropped"


def test_a_dash_becomes_missing_not_zero():
    """The pre-registration says missing is EXCLUDED, never zero — and a 0.0 here would
    read as 'nothing was delivered', which is a different and wrong claim."""
    out = cb.derive(RAW, dt.date(2026, 9, 22))
    odd = out[out["symbol"] == "ODDONE"].iloc[0]
    assert pd.isna(odd["deliv_pct"]) and pd.isna(odd["deliv_qty"])


def test_a_garbled_file_yields_an_empty_frame_not_an_exception():
    assert cb.derive(pd.DataFrame({"nonsense": [1]}), dt.date(2026, 9, 22)).empty
    assert cb.derive(None, dt.date(2026, 9, 22)).empty


def _hist(dates, pcts):
    return pd.DataFrame({"date": dates, "symbol": ["X"] * len(dates),
                         "series": ["EQ"] * len(dates),
                         "close": [100.0] * len(dates), "ttl_qty": [1] * len(dates),
                         "deliv_qty": [1] * len(dates), "deliv_pct": pcts})


def test_baseline_needs_a_contiguous_window(monkeypatch):
    """The bug this was written for: 21 rows that are not 21 consecutive sessions."""
    gappy = ["2025-08-%02d" % d for d in range(1, 21)] + ["2026-09-23"]
    monkeypatch.setattr(cb, "load", lambda: _hist(gappy, [40.0] * 20 + [60.0]))
    assert cb.delivery_signal("X") == {}, "a baseline straddling a 13-month hole was accepted"


def test_a_contiguous_window_is_accepted_and_the_ratio_is_right(monkeypatch):
    days = pd.bdate_range("2026-08-26", periods=21).strftime("%Y-%m-%d").tolist()
    monkeypatch.setattr(cb, "load", lambda: _hist(days, [40.0] * 20 + [60.0]))
    sig = cb.delivery_signal("X")
    assert sig, "a clean 21-session window was rejected"
    assert sig["deliv_pct"] == 60.0 and sig["mean20"] == 40.0
    assert abs(sig["ratio"] - 1.5) < 1e-9


def test_too_little_history_is_missing_rather_than_a_guess(monkeypatch):
    days = pd.bdate_range("2026-09-01", periods=5).strftime("%Y-%m-%d").tolist()
    monkeypatch.setattr(cb, "load", lambda: _hist(days, [40.0] * 5))
    assert cb.delivery_signal("X") == {}
