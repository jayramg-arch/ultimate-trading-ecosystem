# -*- coding: utf-8 -*-
"""Regression tests for the stop TRIGGER BASIS (replay.SL_BASIS, 9 Sep 2026).

Registered in docs/PREREG_close_basis_stop.md. Four stop studies have tested stop
DISTANCE; none touched the basis. Measured on run 20260909_055448, 102 of 196
stop-outs (52.0%) were bars that closed back ABOVE the stop.

What these pin:
  * "intraday" is untouched — prior runs must reproduce byte-for-byte;
  * "close" survives a wick and exits on a close-below, AT THE CLOSE (the worse fill
    is the cost of the scheme and must not be quietly modelled away);
  * the DISASTER floor still fires intraday — without it "close basis" means "no stop
    until 15:30", which is not the scheme under test;
  * close-basis applies to the INITIAL stop only; once the Chandelier ratchets, that
    leg is a resting broker order and keeps triggering intraday.
"""
from __future__ import annotations

import pandas as pd
import pytest

import replay

ENTRY, SL = 100.0, 95.0          # risk 5.0 -> disaster floor at 95 - 0.5*5 = 92.5
FLAT = [100, 100.5, 99.5, 100]   # a quiet bar that touches nothing


@pytest.fixture(autouse=True)
def _restore_basis():
    prev, prev_d = replay.SL_BASIS, replay.SL_DISASTER_MULT
    yield
    replay.SL_BASIS, replay.SL_DISASTER_MULT = prev, prev_d


def _run(bars, basis):
    replay.SL_BASIS = basis
    idx = pd.bdate_range("2025-01-01", periods=len(bars))
    df = pd.DataFrame(bars, columns=["Open", "High", "Low", "Close"], index=idx)
    df["Volume"] = 1e5
    return replay._simulate_one_trade(df, 0, ENTRY, SL, 120.0, 140.0, 25, 25,
                                      max_bars=len(bars) - 1)


def test_wick_through_the_stop_that_closes_above():
    """THE case the whole test exists for: low 94 pierces the 95 stop, close 99 is back
    above it. Intraday sells the wick; close-basis holds."""
    bars = [FLAT, [100, 100.5, 94.0, 99.0], FLAT, FLAT]
    assert _run(bars, "intraday")["hit_initial_sl"] is True
    assert _run(bars, "close")["hit_initial_sl"] is False


def test_close_below_the_stop_exits_under_both_bases():
    bars = [FLAT, [100, 100.5, 93.5, 94.0], FLAT, FLAT]
    for basis in ("intraday", "close"):
        assert _run(bars, basis)["hit_initial_sl"] is True, basis


def test_close_basis_fills_AT_THE_CLOSE_not_at_the_stop():
    """The honest cost of the scheme. A close of 94.0 against a 95.0 stop must book the
    worse price — modelling this fill at the stop would flatter the treatment by
    construction, which is precisely how a stop study goes wrong."""
    bars = [FLAT, [100, 100.5, 93.5, 94.0], FLAT, FLAT]
    intraday = _run(bars, "intraday")["realized_pct"]
    close = _run(bars, "close")["realized_pct"]
    assert close < intraday, (close, intraday)


def test_disaster_floor_still_fires_intraday_under_close_basis():
    """Low 92.0 breaches the 92.5 floor, and the bar closes back at 99. Close-basis must
    NOT save this one — the floor is a resting order and is part of the tested arm."""
    bars = [FLAT, [100, 100.5, 92.0, 99.0], FLAT, FLAT]
    r = _run(bars, "close")
    assert r["hit_initial_sl"] is True
    assert r["realized_pct"] < 0


def test_disaster_floor_scales_with_the_stop_distance():
    """A wick to 93.0 sits below the stop but ABOVE the 92.5 floor, so close-basis holds
    it; widening the multiplier must not change that, and tightening it to 1.0 makes the
    floor the stop itself, which reproduces intraday behaviour."""
    bars = [FLAT, [100, 100.5, 93.0, 99.0], FLAT, FLAT]
    replay.SL_DISASTER_MULT = 1.5
    assert _run(bars, "close")["hit_initial_sl"] is False
    replay.SL_DISASTER_MULT = 1.0            # floor == stop -> intraday equivalence
    assert _run(bars, "close")["hit_initial_sl"] is True


def test_intraday_basis_is_byte_identical_to_the_shipped_default():
    """SL_BASIS defaults to 'intraday'; every prior run must reproduce."""
    assert replay.SL_BASIS == "intraday"
    bars = [FLAT, [100, 100.5, 94.0, 99.0], [100, 106, 99, 105], FLAT]
    a = _run(bars, "intraday")
    replay.SL_BASIS = "intraday"
    b = _run(bars, "intraday")
    assert a == b


def test_close_basis_does_not_apply_once_the_trail_has_ratcheted():
    """After a strong advance the Chandelier lifts the stop above the initial one. That
    leg is a resting broker order in live use, so it must keep triggering intraday."""
    bars = [FLAT,
            [100, 130, 99, 129],          # big advance — trail ratchets above SL
            [129, 131, 100, 130],
            [130, 131, 101, 130],
            [130, 131, 102, 130]]
    r = _run(bars, "close")
    # whatever exit occurs, it must NOT be recorded as an initial-SL hit, because the
    # initial stop is no longer the live one
    assert r["hit_initial_sl"] is False


def test_a_quiet_trade_is_unaffected_by_the_basis():
    bars = [FLAT, FLAT, FLAT, FLAT]
    assert _run(bars, "intraday")["hit_initial_sl"] is False
    assert _run(bars, "close")["hit_initial_sl"] is False
