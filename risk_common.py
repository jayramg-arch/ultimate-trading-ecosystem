"""Shared risk primitives — single source of truth for stop/trail logic used by
the Risk Shield page (weinstein_commander_web_v4.0.py), the Pyramid/Trim manager
(pyramid_logic.py) AND the GTT auto-trail (gtt_auto_shield --trail), so the
surfaces can never drift.

Pure computation (pandas/numpy only — no Streamlit), safe to import anywhere.

Catalyst-aware Chandelier trail = validated "Risk Allocator v2.0" set:
    POS 4.5 · WYC 3.5 · REV 2.5 · SWG 1.5   (+0.5 in a bear regime)
Level = N-bar highest CLOSE − ATR(N, EWM α=1/N) × multiplier.

HOUSE-STANDARD RULING (Jay, 14-Jul-2026 Risk Shield audit, refined same day):
the trail window N is TRADE-TYPE aware — the Chandelier runs on the trade's clock:
    SWING      → N = 14  (highest-close-14 − ATR14 × mult)
    POSITIONAL → N = 22  (highest-close-22 − ATR22 × mult)   [the long-standing house trail]
Anchor window and ATR length are deliberately PAIRED (same clock). Trade type is
sensed from the journal `setup` prefix (SWG→swing; POS/WYC/REV→positional) unless
the caller passes explicit knowledge (journal Timeframe); unknown → positional 22
(preserves prior behavior). Anchor stays highest CLOSE, not the textbook HIGH —
the validation campaign's hardest lesson was that tight stops on long holds give
back found edge. Changing the anchor/close convention requires a replay.py A/B
FIRST — never an aesthetic edit. Other engines converge onto THIS module (P2
reconciliation), not the other way around.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def trail_mult_for(setup, bear: bool):
    """Catalyst-aware ATR multiplier for the Chandelier trail. Returns
    (multiplier, family) or (None, None) if the setup prefix isn't recognised."""
    for pfx, m in (("POS", 4.5), ("WYC", 3.5), ("REV", 2.5), ("SWG", 1.5)):
        if str(setup or "").startswith(pfx):
            return (m + (0.5 if bear else 0.0)), pfx
    return None, None


def trail_window_for(setup, swing=None) -> int:
    """Trade-type-aware Chandelier window (Jay, 14-Jul-2026): SWING → 14,
    POSITIONAL → 22. `swing` (True/False) is the caller's explicit knowledge
    (journal Timeframe); when None, sense it from the setup prefix (SWG → swing;
    POS/WYC/REV → positional); unknown → positional 22 (prior behavior)."""
    if swing is None:
        s = str(setup or "")
        if s.startswith("SWG"):
            swing = True
        elif s.startswith(("POS", "WYC", "REV")):
            swing = False
    return 14 if swing else 22


def chandelier_exit(high: pd.Series, low: pd.Series, close: pd.Series,
                    setup: str = "", bear: bool = False,
                    cap_protect: bool = False, custom_mult=None,
                    above200: bool = True, swing=None):
    """Catalyst-aware, trade-type-aware Chandelier trailing-stop level.

    Window/ATR clock (paired): swing → 14-bar, positional → 22-bar — see
    trail_window_for(). Multiplier precedence (identical to the Risk Shield page):
      1. valid custom override (>0)           → "custom"
      2. catalyst-aware set (trail_mult_for)  → "<setup/family>"
      3. heuristic fallback (4.5 bull / 5.0 bear)
      4. cap-protect (portfolio drawdown)     → 2.5, overrides all of the above

    Returns (level, multiplier, source) or (None, None, None) when there are
    fewer than N bars.
    """
    n = trail_window_for(setup, swing)
    if close is None or len(close) < n:
        return (None, None, None)

    highest_close_n = float(close.rolling(n).max().iloc[-1])
    tr = pd.concat([high - low,
                    (high - close.shift(1)).abs(),
                    (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr_n = float(tr.ewm(alpha=1 / n, adjust=False).mean().iloc[-1])

    invalid_custom = custom_mult is not None and not (isinstance(custom_mult, (int, float)) and custom_mult > 0)
    if custom_mult is not None and not invalid_custom:
        mult, src = float(custom_mult), "custom"
    else:
        cat_mult, cat_fam = trail_mult_for(setup, bear)
        if cat_mult is not None:
            mult, src = cat_mult, (str(setup) or cat_fam)
        else:
            mult = 4.5 if above200 else 5.0
            src = "heuristic-bull" if above200 else "heuristic-bear"
        if cap_protect:
            mult, src = 2.5, "cap-protect"

    if np.isnan(highest_close_n) or np.isnan(atr_n):
        return (None, None, None)
    return (float(highest_close_n - atr_n * mult), float(mult), src)
