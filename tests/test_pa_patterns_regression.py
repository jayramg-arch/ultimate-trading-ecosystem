"""Regression guards for the shared PA pattern batteries (`pa_patterns.py`).

Created 26-Jul-2026 (audit P2). Context: formal test coverage across this repo is
~0.27% and there is no CI, while the single most expensive bug class in the
project's history has been **silent catalyst blackouts** — a gate quietly becoming
unreachable (or trivially true) and nobody noticing for weeks:

  * `weinstein_setup` AND-ed a squeeze into the POS base gate — structurally
    mutually exclusive with a breakout → 0 POS picks for 24 months.
  * The VCP dry-up leg computed `(c*v)` (a VWMA of PRICE) instead of `(v*v)`
    (a VWMA of VOLUME). Price is always < a volume 50-SMA, so the leg was a
    permanent no-op and VCP fired without any volume contraction.
  * SWG-PB lost its quality gates and went from dominant to zero.

Every one of those was found by eyeballing a funnel diagnostic, months late.
These tests are the cheap mechanical version of that funnel. They are pure and
offline — synthetic OHLCV only, no network, no cache, no broker.

They deliberately assert BOTH directions (a pattern fires on its shape AND stays
silent on the negative control), because a gate that is always-true is exactly as
broken as one that is never-true, and only the two-sided test catches both.
"""

import numpy as np
import pandas as pd
import pytest

import pa_patterns as pp


# ── fixtures ──────────────────────────────────────────────────────────────────

def _frame(o, h, l, c, v):
    n = len(c)
    return pd.DataFrame(
        {"Open": o, "High": h, "Low": l, "Close": c, "Volume": v},
        index=pd.date_range("2024-01-01", periods=n, freq="B"),
    )


def synth(n=250, seed=1):
    """A generic, well-behaved uptrending series long enough for the 200-SMA."""
    rng = np.random.default_rng(seed)
    c = 100 * np.cumprod(1 + rng.normal(0.0015, 0.012, n))
    o = c * (1 + rng.normal(0, 0.003, n))
    h = np.maximum(o, c) * (1 + abs(rng.normal(0, 0.004, n)))
    l = np.minimum(o, c) * (1 - abs(rng.normal(0, 0.004, n)))
    v = rng.integers(800_000, 1_200_000, n).astype(float)
    return _frame(o, h, l, c, v)


def _fired(pats):
    return {name: bool(f) for name, f, _t, _n in pats}


# ── 1. Battery composition — the blackout guard ───────────────────────────────

BULL_PATTERNS = {
    "★★ Power Play (HTF)", "Power Play (Strong Close)", "VCP Breakout",
    "Pocket Pivot", "Bullish Engulfing (gated)", "Liq Sweep Reclaim",
    "3-Bar Bull Reversal", "Stage-2 Launch", "Inside-3 (Coil)", "True NR7",
    "Wyckoff Spring", "Gap-Up Breakout", "50SMA Undercut & Reclaim",
    "Hammer at 50-SMA", "Hammer at 200-SMA", "Breakout Confirmed",
    # 17th, added 10-Aug-2026. It was always computed, but appended only when it
    # FIRED — so this set (and the returned list) was 16 on a quiet bar and 17 on a
    # coil. That is exactly the instability this test exists to catch, and it slipped
    # through because a set built from a synthetic flat frame never sees the pattern.
    # S4's Pine grid has always shown 17 chips; Python now matches on every bar.
    "★ IB-NR7 Coil",
}

RECOVERY_PATTERNS = {
    "Climax Reversal (SC+AR)", "Wyckoff Spring", "Higher-Low / 2B",
    "Base Breakout (SOS/JAC)", "Bullish Engulfing", "Hammer at support",
    "3-Bar Bull Reversal", "Pocket Pivot", "Volume Dry-Up", "30-WMA Reclaim",
}


def test_bull_battery_composition_is_stable():
    """A pattern silently disappearing from the battery is the blackout bug.
    Both GM and S4 consume this list, so a drop here desynchronises two surfaces."""
    names = {n for n, _f, _t, _note in pp.detect_bull_patterns(synth(), stage="Stage 2")}
    assert names == BULL_PATTERNS, (
        f"bull battery changed — missing {BULL_PATTERNS - names}, "
        f"unexpected {names - BULL_PATTERNS}"
    )


def test_recovery_battery_composition_is_stable():
    names = {n for n, _f, _t, _note in pp.detect_recovery_patterns(synth())}
    assert names == RECOVERY_PATTERNS, (
        f"recovery battery changed — missing {RECOVERY_PATTERNS - names}, "
        f"unexpected {names - RECOVERY_PATTERNS}"
    )


@pytest.mark.parametrize("fn", [pp.detect_bull_patterns, pp.detect_recovery_patterns])
def test_short_series_returns_empty_not_garbage(fn):
    """<60 bars must yield nothing rather than NaN-driven false positives — the
    'silent fallback biases every signal upward' failure mode."""
    assert fn(synth().tail(30)) == []


# ── 2. VCP dry-up — guards the (c*v) -> (v*v) fix ─────────────────────────────

def test_vcp_does_not_fire_without_volume_dryup():
    """REGRESSION (bug fixed 8-Jul-2026, pa_patterns.py:311).

    The dry-up leg is a VWMA of VOLUME compared against the 50-bar volume mean.
    Written as `(c*v)` it was a VWMA of PRICE — always far below a volume average
    — so the leg was permanently True and VCP fired with no contraction at all.

    This fixture satisfies every OTHER VCP condition (clean 10-day-high breakout,
    relative volume > 1.2, close in the top of the bar) while volume EXPANDS
    monotonically into the break. A correct dry-up leg blocks it. Reverting to
    `(c*v)` makes VCP fire here and this test goes red.
    """
    n = 250
    c = np.concatenate([np.linspace(90, 100, n - 1), [108.0]])   # last bar breaks out
    o = np.concatenate([c[:-1] * 0.999, [101.0]])
    h = np.concatenate([c[:-1] * 1.004, [108.5]])
    l = np.concatenate([c[:-1] * 0.996, [100.5]])
    v = np.linspace(500_000, 3_000_000, n)                       # volume RISING, no dry-up
    pats = _fired(pp.detect_bull_patterns(_frame(o, h, l, c, v), stage="Stage 2"))
    assert pats["VCP Breakout"] is False, (
        "VCP Breakout fired on monotonically EXPANDING volume — the dry-up leg is "
        "a no-op again (check the VWMA is over VOLUME, `(v*v)`, not price `(c*v)`)."
    )


# ── 3. NR7 — two-sided ────────────────────────────────────────────────────────

def _nr7_frame(last_range_mult):
    """Flat base with a controlled final-bar range. mult<1 → narrowest of 7."""
    n = 250
    c = np.full(n, 100.0)
    o = np.full(n, 100.0)
    h = np.full(n, 101.0)
    l = np.full(n, 99.0)
    h[-1] = 100.0 + 1.0 * last_range_mult
    l[-1] = 100.0 - 1.0 * last_range_mult
    v = np.full(n, 1_000_000.0)
    return _frame(o, h, l, c, v)


def test_nr7_fires_on_narrowest_bar():
    pats = _fired(pp.detect_bull_patterns(_nr7_frame(0.3), stage="Stage 2"))
    assert pats["True NR7"] is True


def test_nr7_silent_on_widest_bar():
    """Negative control — an always-true NR7 would flood every surface."""
    pats = _fired(pp.detect_bull_patterns(_nr7_frame(3.0), stage="Stage 2"))
    assert pats["True NR7"] is False


# ── 4. Intraday suppression of weekly-anchored patterns ───────────────────────

def _htf_frame():
    """Doubles off the 40-bar low, then a tight 15-bar flag — the HTF shape."""
    n = 250
    base = np.full(n - 40, 50.0)
    ramp = np.linspace(50, 105, 25)
    flag = np.full(15, 105.0)
    c = np.concatenate([base, ramp, flag])
    o = c * 0.999
    h = c * 1.004
    l = c * 0.996
    v = np.full(n, 1_000_000.0)
    return _frame(o, h, l, c, v)


def test_htf_is_suppressed_on_intraday():
    """DNA rule: Power Play (HTF) is an 8-WEEK positional pattern and is
    meaningless on 75/125-min bars. It must fire on daily and never intraday —
    the battery is shared, so losing this gate would let a weekly pattern leak
    into the intraday trigger on both GM and S4."""
    df = _htf_frame()
    daily = _fired(pp.detect_bull_patterns(df, stage="Stage 2"))
    intra = _fired(pp.detect_bull_patterns(df, stage="Stage 2", intraday=True))
    assert daily["★★ Power Play (HTF)"] is True, "HTF fixture no longer fires on daily"
    assert intra["★★ Power Play (HTF)"] is False, "HTF leaked into the intraday battery"


def test_intraday_keeps_the_same_pattern_names():
    """Suppression is via the `fired` flag, not by dropping names — callers index
    the battery by name, so the name set must be TF-invariant."""
    df = synth()
    d = {n for n, *_ in pp.detect_bull_patterns(df, stage="Stage 2")}
    i = {n for n, *_ in pp.detect_bull_patterns(df, stage="Stage 2", intraday=True)}
    assert d == i


# ── 5. Nothing fires on a dead tape ───────────────────────────────────────────

def test_flat_tape_fires_almost_nothing():
    """A perfectly flat series has no momentum, no volume event and no reversal.
    A battery that lights up here has an always-true gate somewhere."""
    n = 250
    c = o = np.full(n, 100.0)
    h = np.full(n, 100.0)
    l = np.full(n, 100.0)
    v = np.full(n, 1_000_000.0)
    fired = [k for k, f in _fired(
        pp.detect_bull_patterns(_frame(o, h, l, c, v), stage="Stage 2")).items() if f]
    # NR7/Inside-3 are legitimately degenerate on a zero-range series (every bar
    # ties); nothing that requires a move, a breakout or a volume surge may fire.
    disallowed = set(fired) - {"True NR7", "Inside-3 (Coil)"}
    assert not disallowed, f"patterns fired on a flat tape: {sorted(disallowed)}"
