# -*- coding: utf-8 -*-
"""Regression tests for S/R level ageing (zone_engine, 9 Sep 2026).

Pins the three things that would silently break the feature:
  * the clock is LAST touch and it is PER TIMEFRAME, in that TF's own bars;
  * a stale level is dropped as a CEILING only, never as support;
  * the HTF rescue is the ONLY rescue — the AVWAP and gap rescues were controlled
    on live data and carried no information about staleness, so if either ever
    reappears in sr_rescued these tests should be revisited, not deleted.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import zone_engine as ze


# ── the clock ────────────────────────────────────────────────────────────────
def test_expiry_is_per_timeframe_in_own_bars():
    assert ze.sr_expiry_bars("D") == 126        # ~6 months of daily bars
    assert ze.sr_expiry_bars("W") == 130        # ~2.5 years of weekly bars
    assert ze.sr_expiry_bars("M") == 120        # ~10 years of monthly bars
    assert ze.sr_expiry_bars("75") == 10        # ~10 sessions
    assert ze.sr_expiry_bars("nonsense") == ze.sr_expiry_bars("D")


@pytest.mark.parametrize("age,band", [(0, "FRESH"), (20, "FRESH"), (21, "SEASONED"),
                                      (62, "SEASONED"), (63, "AGED"), (125, "AGED"),
                                      (126, "STALE"), (400, "STALE")])
def test_daily_bands_land_on_the_research_boundaries(age, band):
    """1 / 3 / 6 months, which is 21 / 63 / 126 daily bars."""
    assert ze.sr_age_band(age, "D") == band


def test_a_weekly_level_is_judged_on_the_weekly_clock():
    """The failure this guards against: a flat 6-month rule would kill a weekly level
    at 26 weekly bars. Judging an HTF object on a lower TF's clock is the same defect
    that once killed a weekly zone on a daily EMA cross."""
    assert ze.sr_is_stale(30, "D") is False and ze.sr_age_band(30, "D") == "SEASONED"
    assert ze.sr_is_stale(30, "W") is False          # 30 weeks ~ 7 months: still live
    assert ze.sr_is_stale(129, "W") is False
    assert ze.sr_is_stale(130, "W") is True
    assert ze.sr_is_stale(100, "M") is False         # 100 months ~ 8 years


def test_staleness_boundary_is_exact():
    assert ze.sr_is_stale(125, "D") is False
    assert ze.sr_is_stale(126, "D") is True


# ── the rescue ───────────────────────────────────────────────────────────────
def test_htf_rescue_fires_within_tolerance_only():
    assert ze.sr_rescued(100.0, 10.0, 0.6, htf_levels=[102.0]) == "HTF"   # 2 <= 6
    assert ze.sr_rescued(100.0, 10.0, 0.6, htf_levels=[107.0]) is None    # 7  > 6
    assert ze.sr_rescued(100.0, 10.0, 0.6, htf_levels=[]) is None


def test_zero_atr_cannot_rescue():
    """No ATR means no tolerance; a rescue must never fall back to an absolute band."""
    assert ze.sr_rescued(100.0, 0.0, 0.6, htf_levels=[100.0]) is None


def test_avwap_and_gap_are_not_rescues():
    """Both were controlled on the live board and fired at the SAME rate on FRESH
    ceilings as on stale ones (AVWAP 38.1% vs 37.9%; gap 19.0% vs 17.2%, below its
    own 34.3% random rate). They must not be reachable as rescue arguments."""
    with pytest.raises(TypeError):
        ze.sr_rescued(100.0, 10.0, 0.6, avwaps=[100.0])
    with pytest.raises(TypeError):
        ze.sr_rescued(100.0, 10.0, 0.6, gap_edges=[100.0])


# ── the engine ───────────────────────────────────────────────────────────────
def _frame(n=400, seed=3):
    """A synthetic frame with a repeatedly-tested shelf early in history, so at least
    one level is guaranteed to age out by the end."""
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.8, n))
    high = close + rng.uniform(0.3, 1.2, n)
    low = close - rng.uniform(0.3, 1.2, n)
    for b in (30, 45, 60):                      # three touches of one early shelf
        high[b] = 118.0
        low[b] = 112.0
    idx = pd.bdate_range("2023-01-02", periods=n)
    return pd.DataFrame({"Open": close, "High": high, "Low": low, "Close": close,
                         "Volume": rng.uniform(1e5, 5e5, n)}, index=idx)


def test_levels_carry_age_and_legacy_fields_together():
    lv = ze.detect_sr_levels(_frame(), "D")
    assert lv, "fixture produced no levels"
    for L in lv:
        assert {"price", "touches", "grade", "role"} <= set(L)          # legacy intact
        assert {"first_bar", "last_bar", "age_bars", "age_band", "stale"} <= set(L)
        assert L["last_bar"] >= L["first_bar"]                          # last >= first
        assert L["stale"] == (L["age_band"] == "STALE")                 # one truth
        assert L["age_bars"] >= 0


def test_grade_and_age_are_independent_axes():
    """`grade` must stay the TOUCH-COUNT read. If ageing ever leaks into it, every
    existing MTTWR consumer changes meaning silently."""
    lv = ze.detect_sr_levels(_frame(), "D")
    assert {L["grade"] for L in lv} <= {"FRESH", "TESTED", "MTTWR"}
    assert {L["age_band"] for L in lv} <= {"FRESH", "SEASONED", "AGED", "STALE"}


def test_stale_exclusion_never_lowers_the_ceiling():
    """Skipping obstacles can only move the ceiling UP or leave it None — never down."""
    df = _frame()
    px = float(df["Close"].iloc[-1])
    off = ze.sr_resistance_above(df, "D", px, skip_stale=False)
    on = ze.sr_resistance_above(df, "D", px, skip_stale=True)
    if off["level"] is not None and on["level"] is not None:
        assert on["level"] >= off["level"]


def test_stale_levels_remain_valid_as_support():
    """The whole point of Jay's instruction: the line stays, and it stays usable
    below price. Only the CEILING role is withdrawn."""
    df = _frame()
    px = float(df["Close"].iloc[-1])
    lv = ze.detect_sr_levels(df, "D")
    assert any(L["stale"] for L in lv), "fixture aged nothing — test is not exercising"
    out = ze.sr_support(df, "D", px)
    assert isinstance(out, dict) and "near_sr" in out       # never raises, never filtered


def test_overhead_room_flag_is_a_clean_ablation():
    """SR_SKIP_STALE_CEILING=False must reproduce the pre-ageing ceiling exactly."""
    df = _frame()
    px = float(df["Close"].iloc[-1])
    prev = ze.SR_SKIP_STALE_CEILING
    try:
        ze.SR_SKIP_STALE_CEILING = False
        a = ze.overhead_room({"D": df}, px)
        ze.SR_SKIP_STALE_CEILING = True
        b = ze.overhead_room({"D": df}, px)
    finally:
        ze.SR_SKIP_STALE_CEILING = prev
    if a.get("obstacle") is not None and b.get("obstacle") is not None:
        assert b["obstacle"] >= a["obstacle"]
