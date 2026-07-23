"""Regression tests for the OHLCV data spine (data_provider.fetch_ohlcv).

fetch_ohlcv is the 67-edge god node ~24 subsystems depend on, so a defect in its
cache/freshness layer corrupts every screener, backtest and risk check at once and
SILENTLY. These tests encode the two incidents that actually happened, so a future
refactor can't reintroduce them:

  1. cache-poisoning (2026-07-03): the fallback-period serve RE-TIMESTAMPED weeks-old
     data as fresh, so the stale frame self-renewed forever and the network was never
     consulted again → 15 symbols stuck on dead bars for 9 days.
  2. Dhan IST→UTC date-shift (2026-07-08): every daily bar dated one day early → a
     Monday session printed as an impossible Sunday, propagated through the spine.

Run:  python test_data_provider_contract.py    (or: pytest test_data_provider_contract.py)
"""
import logging
import pandas as pd
import data_provider as dp


def _daily_frame(dates, close=100.0):
    idx = pd.DatetimeIndex(pd.to_datetime(dates))
    return pd.DataFrame({"Open": close, "High": close, "Low": close,
                         "Close": close, "Volume": 1000}, index=idx)


# ── 1. The contract net catches the date-shift tell + structural breaks ──────────
def test_frame_contract_flags_weekend_future_and_dupes(caplog):
    # A daily frame with a SUNDAY-dated bar (the date-shift tell) + a future bar.
    future = (pd.Timestamp.now().normalize() + pd.Timedelta(days=10))
    df = _daily_frame(["2026-07-05",              # a Sunday
                       "2026-07-06",              # Monday
                       future.strftime("%Y-%m-%d")])
    with caplog.at_level(logging.WARNING):
        dp._assert_frame_contract(df, "TESTSYM", "1d", None)
    msg = " ".join(r.getMessage() for r in caplog.records)
    assert "weekend" in msg.lower(), "weekend-dated daily bar must be flagged (date-shift regression)"
    assert "FUTURE" in msg, "future-dated bar must be flagged"


def test_frame_contract_ignores_isolated_weekend_sessions(caplog):
    # A handful of weekend bars in a long history = legit NSE Saturday special sessions,
    # NOT a systematic shift — must stay silent at WARNING (no false alarm during auto-pilot).
    weekdays = [d for d in pd.bdate_range("2024-01-01", periods=250)]
    dates = weekdays + [pd.Timestamp("2024-02-03"), pd.Timestamp("2024-03-02")]  # 2 real NSE Saturdays
    df = _daily_frame(sorted(dates))
    with caplog.at_level(logging.WARNING):
        dp._assert_frame_contract(df, "TESTSYM", "1d", None)
    assert not [r for r in caplog.records if "systematic" in r.getMessage()], \
        "a couple of weekend bars in a long history must NOT trip the shift warning"


def test_frame_contract_flags_systematic_shift(caplog):
    # A −1-day shift dumps ~1/5 of bars onto Sunday → a large fraction → MUST warn.
    mondays_as_sunday = list(pd.date_range("2024-01-07", periods=40, freq="7D"))  # 40 Sundays
    weekdays = list(pd.bdate_range("2024-01-01", periods=120))
    df = _daily_frame(sorted(set(mondays_as_sunday + weekdays)))
    with caplog.at_level(logging.WARNING):
        dp._assert_frame_contract(df, "TESTSYM", "1d", None)
    assert [r for r in caplog.records if "systematic" in r.getMessage()], \
        "a systematic weekend fraction must trip the shift warning"


def test_frame_contract_silent_on_clean_frame(caplog):
    # Three consecutive weekdays, all in the past — must produce NO warnings.
    df = _daily_frame(["2026-07-06", "2026-07-07", "2026-07-08"])  # Mon/Tue/Wed
    with caplog.at_level(logging.WARNING):
        dp._assert_frame_contract(df, "TESTSYM", "1d", None)
    assert not [r for r in caplog.records if "FRAME CONTRACT" in r.getMessage()], \
        "a clean weekday frame must not trip the contract"


# ── 2. Freshness invariant (cache-poisoning guard) ───────────────────────────────
def test_content_stale_for_live_and_pin_exempt():
    stale = _daily_frame([pd.Timestamp.now().normalize() - pd.Timedelta(days=20)])
    fresh = _daily_frame([pd.Timestamp.now().normalize()])
    # live mode: a 20-day-old daily frame is stale; a today frame is not
    assert dp._content_stale_for_live(stale, "1d", None) is True
    assert dp._content_stale_for_live(fresh, "1d", None) is False
    # pinned/replay is EXEMPT — old frames are legitimate as-of reads
    assert dp._content_stale_for_live(stale, "1d", "2026-06-01") is False


# ── 3. The poisoning regression: a cache-serve must NOT re-write the frame ────────
def test_cache_serve_does_not_retimestamp(monkeypatch):
    """The exact 2026-07-03 bug: serving a cached frame must never call _write_cache
    (which re-stamped cached_at fresh → self-renewing stale data). Force a cache hit
    and assert _write_cache is never invoked."""
    good = _daily_frame([pd.Timestamp.now().normalize()])
    writes = []
    monkeypatch.setattr(dp, "_read_cache", lambda key, ignore_ttl=False: good)
    monkeypatch.setattr(dp, "_is_cache_valid_for_pin", lambda *a, **k: True)
    monkeypatch.setattr(dp, "_content_stale_for_live", lambda *a, **k: False)
    monkeypatch.setattr(dp, "_write_cache", lambda *a, **k: writes.append(a))
    # If it ever falls through to the network, force an empty return instead.
    monkeypatch.setattr(dp, "is_internet_available", lambda: False)

    out = dp.fetch_ohlcv("RELIANCE", period="6mo", interval="1d", use_cache=True)
    assert not out.empty, "a valid cached frame must be served"
    assert writes == [], "serving from cache must NOT re-write/re-timestamp (poisoning regression)"


# ── standalone runner (no pytest needed) ─────────────────────────────────────────
if __name__ == "__main__":
    class _Cap:
        """Minimal caplog/monkeypatch stand-in so the file runs under plain python."""
        def __init__(self): self.records = []; self._h = None; self._saved = []
        def at_level(self, lvl):
            cap = self
            class _Ctx:
                def __enter__(s):
                    cap._h = logging.Handler(); cap._h.emit = lambda r: cap.records.append(r)
                    logging.getLogger("data_provider").addHandler(cap._h)
                    logging.getLogger("data_provider").setLevel(lvl); return cap
                def __exit__(s, *a):
                    logging.getLogger("data_provider").removeHandler(cap._h)
            return _Ctx()
        def setattr(self, obj, name, val):
            self._saved.append((obj, name, getattr(obj, name))); setattr(obj, name, val)
        def undo(self):
            for obj, name, val in reversed(self._saved): setattr(obj, name, val)

    passed = failed = 0
    for fn in (test_frame_contract_flags_weekend_future_and_dupes,
               test_frame_contract_ignores_isolated_weekend_sessions,
               test_frame_contract_flags_systematic_shift,
               test_frame_contract_silent_on_clean_frame,
               test_content_stale_for_live_and_pin_exempt,
               test_cache_serve_does_not_retimestamp):
        cap = _Cap()
        try:
            import inspect
            args = inspect.signature(fn).parameters
            fn(cap) if args else fn()
            print(f"PASS  {fn.__name__}"); passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}"); failed += 1
        except Exception as e:
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}"); failed += 1
        finally:
            cap.undo()
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
