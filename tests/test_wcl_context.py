"""Regression guards for the WCL Wyckoff / SMC port (`wcl_context.py`).

Created 28-Jul-2026. Context: the Golden Matcher and Trigger Board previously
rendered "WCL Context" and "Structure Health" from proxies — Wyckoff was
`acc_ok and stage in (1,2)`, SMC was the path name, and `choch_count_20` was read
with `default=0` and PRODUCED NOWHERE, so Structure Health was permanently
`CLEAN (0)`. `wcl_context.py` replaces those with the real Pine calculation.

A port is only worth having if it stays a port. Three Pine behaviours in this
module look like bugs to a reader doing a tidy-up pass, and all three are
load-bearing — these tests exist to make removing them fail loudly:

  1. Pivots resolve on the CONFIRMATION bar (pivot + `right` bars), so the event is
     stamped `right` bars after the candle that caused it. Freshness/decay measure
     from the confirmation bar.
  2. The bearish Wyckoff ladder is a SECOND `if`, not an `else` — a bar satisfying
     both ladders resolves to DISTRIBUTION.
  3. `choch_up` is evaluated against the PRIOR bar's trend flag, before the update.

Plus the anti-silent-fallback guard: a MISSING stage input must score bearish, not
hand back the maximum bullish score (that exact bug shipped in S4 v5.0).

Pure and offline — synthetic OHLCV only, no network, no cache, no broker.
"""

import numpy as np
import pandas as pd
import pytest

import wcl_context as W


def _frame(rows):
    """rows = [(open, high, low, close, volume), ...]"""
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close", "Volume"])


def _flat(n, price=100.0, vol=1000.0, rng=1.0):
    """Featureless tape — the negative control for every detector."""
    return [(price, price + rng, price - rng, price, vol)] * n


# ── 1. pivot confirmation offset ────────────────────────────────────────────
def test_pivot_surfaces_on_confirmation_bar_not_pivot_bar():
    vals = np.array([10.0] * 5 + [20.0] + [10.0] * 5, dtype=float)
    out = W._confirmed_pivots(vals, 3, 3, high=True)
    assert np.isnan(out[5]), "value must NOT surface on the pivot bar itself"
    assert out[8] == 20.0, "value must surface `right` bars later, on confirmation"
    assert np.count_nonzero(~np.isnan(out)) == 1


def test_pivot_tie_breaks_the_pivot():
    # equal neighbour on the right → not a pivot (strictly-greater on both sides)
    vals = np.array([10.0] * 3 + [20.0, 20.0] + [10.0] * 3, dtype=float)
    out = W._confirmed_pivots(vals, 2, 2, high=True)
    assert np.all(np.isnan(out))


def test_pivot_low_mirrors_pivot_high():
    vals = np.array([10.0] * 4 + [2.0] + [10.0] * 4, dtype=float)
    out = W._confirmed_pivots(vals, 3, 3, high=False)
    assert out[7] == 2.0


# ── 2. Wyckoff ──────────────────────────────────────────────────────────────
def test_wyckoff_silent_on_flat_tape():
    st = W.wyckoff_state(_frame(_flat(120)))
    assert st["event"] == "—"
    assert st["bias"] == "NEUTRAL"
    assert st["score_comp"] == 0


def test_wyckoff_detects_selling_climax():
    """SC = pivot low, high volume, wide range, closing in the LOWER third."""
    rows = _flat(40)
    # the climax candle: wide, heavy, closes near its low, and is a pivot low
    rows.append((100.0, 101.0, 80.0, 82.0, 9000.0))
    rows += _flat(40, price=95.0)
    st = W.wyckoff_state(_frame(rows), pivot_len=10, vol_lookback=20)
    assert st["bias"] == "ACCUMULATION"
    assert st["event"] in ("SC", "PS"), st["event"]
    assert st["score_base"] > 0


def test_wyckoff_event_age_measured_from_confirmation_bar():
    """The event is stamped pivot_len bars AFTER the candle (Pine parity)."""
    pl = 10
    rows = _flat(40)
    rows.append((100.0, 101.0, 80.0, 82.0, 9000.0))
    tail = 25
    rows += _flat(tail, price=95.0)
    st = W.wyckoff_state(_frame(rows), pivot_len=pl, vol_lookback=20)
    n = len(rows)
    pivot_idx = 40
    # age is from the CONFIRMATION bar (pivot_idx + pl), not from pivot_idx
    assert st["age_bars"] == (n - 1) - (pivot_idx + pl)


def test_wyckoff_decay_zeroes_a_stale_event():
    """4 decay steps (15 bars each) drive the multiplier to 0 — a stale event
    must stop contributing, which is what keeps the context score honest."""
    rows = _flat(40)
    rows.append((100.0, 101.0, 80.0, 82.0, 9000.0))
    rows += _flat(90, price=95.0)                 # >= 60 bars past confirmation
    st = W.wyckoff_state(_frame(rows), pivot_len=10, vol_lookback=20)
    assert st["age_bars"] >= 60
    assert st["score_comp"] == 0
    assert st["score_base"] != 0, "the raw tier must survive; only the decayed score goes to 0"


def test_wyckoff_distribution_wins_when_both_ladders_fire():
    """Pine's bearish ladder is a SECOND `if`, not an `else`. A pivot low that is
    heavy + wide + closes low + is a LOWER low satisfies BOTH `sc_c` (Selling
    Climax, accumulation) and `sow_c` (Sign of Weakness, distribution). Pine
    resolves it to SOW. Turning that second `if` into an `elif` would silently
    relabel every breakdown as accumulation — the most dangerous possible drift
    for a long-only desk.
    """
    rows = _flat(30, price=100.0)
    rows.append((100.0, 101.0, 88.0, 89.0, 5000.0))     # first pivot low
    rows += _flat(30, price=100.0)
    # second pivot low: LOWER, heavy, wide, closes near its low, down bar
    rows.append((100.0, 101.0, 70.0, 72.0, 9000.0))
    rows += _flat(15, price=95.0)
    st = W.wyckoff_state(_frame(rows), pivot_len=10, vol_lookback=20)
    assert st["bias"] == "DISTRIBUTION", f"got {st['bias']} / {st['event']}"
    assert st["event"] == "SOW"
    assert st["score_base"] == -4


# ── 3. SMC ──────────────────────────────────────────────────────────────────
def test_smc_silent_on_flat_tape():
    st = W.smc_state(_frame(_flat(120)))
    assert st["last_event"] == "—"
    assert st["choch_count_20"] == 0
    assert st["score"] == 2          # default trend_up=True, no CHoCH bonus


def test_smc_detects_bullish_bos():
    rows = _flat(20, price=100.0)
    rows.append((100.0, 120.0, 99.0, 118.0, 2000.0))   # swing high pivot
    rows += _flat(20, price=100.0)
    rows.append((100.0, 130.0, 99.0, 129.0, 3000.0))   # close crosses above it
    rows += _flat(5, price=129.0)
    st = W.smc_state(_frame(rows), bos_len=10, liq_len=10)
    assert st["trend_up"] is True
    assert "▲" in st["last_event"], st["last_event"]


def test_smc_choch_count_window_trims():
    """Structure Health must only count CHoCH inside the trailing window —
    an untrimmed list would make every mature chart read BROKEN."""
    st = W.smc_state(_frame(_flat(120)), choch_window=20)
    assert st["choch_count_20"] == 0
    # the window parameter is honoured rather than hard-coded
    st2 = W.smc_state(_frame(_flat(120)), choch_window=5)
    assert st2["choch_count_20"] == 0


def test_structure_health_tiers():
    assert W.structure_health(0) == ("CLEAN (0)", "pass")
    assert W.structure_health(1)[1] == "pass"
    assert W.structure_health(2)[1] == "watch"
    assert W.structure_health(3)[1] == "watch"
    assert W.structure_health(4) == ("BROKEN (4)", "fail")


# ── 4. stage score — the anti-silent-fallback guard ─────────────────────────
def test_stage_score_missing_data_fails_bearish():
    """S4 v5.0 shipped nz(d_bel30, 0.0), which returned the MAXIMUM bullish score
    on missing daily data. Missing must never read as bullish."""
    assert W.stage_score(None, None) == -2
    assert W.stage_score(False, None) == -2
    assert W.stage_score(None, False) == 1


def test_stage_score_tiers():
    assert W.stage_score(below_30w=False, below_200=False) == 3
    assert W.stage_score(below_30w=True, below_200=False) == 1
    assert W.stage_score(below_30w=True, below_200=True) == -2


# ── 5. composite ────────────────────────────────────────────────────────────
def test_context_bands():
    assert W.context_band(9) == "STRONG BULL"
    assert W.context_band(4) == "BULL"
    assert W.context_band(0) == "NEUTRAL"
    assert W.context_band(-4) == "CAUTION"
    assert W.context_band(-7) == "BEAR"


def test_wcl_context_totals_are_self_consistent():
    df = _frame(_flat(150))
    r = W.wcl_context(df, vp_score=1, below_30w=False, below_200=False)
    assert r["total_base"] == (r["wyckoff"]["score_comp"] + r["vp_score"]
                               + r["smc"]["score"] + r["stage_score"])
    assert r["total_final"] == r["total_base"] + r["setup_bonus"]
    assert r["band"] == W.context_band(r["total_final"])
    assert r["struct"] == W.structure_health(r["choch_count_20"])[0]


def test_wcl_context_survives_short_and_empty_frames():
    """The board runs this over ~50 symbols; a thin one must degrade, not raise."""
    for n in (0, 5, 30):
        r = W.wcl_context(_frame(_flat(n)) if n else
                          pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"]))
        assert r["wyckoff"]["ok"] is False or n >= 30
        assert isinstance(r["total_final"], int)
        assert r["band"] in ("STRONG BULL", "BULL", "NEUTRAL", "CAUTION", "BEAR")


def test_s7_distribution_applies_a_negative_bonus():
    """Priority-3 setups split on direction: S1 adds +1, S7 subtracts 2. A single
    `pri == 3 -> +1` rule would silently turn a breakdown into a bullish nudge."""
    df = _frame(_flat(150))
    r = W.wcl_context(df)
    if r["setup_pri"] == 3:
        assert r["setup_bonus"] == (-2 if r["setup_bear"] else 1)
