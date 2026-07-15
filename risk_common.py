"""Shared risk primitives — single source of truth for stop/trail logic used by
the Risk Shield page (weinstein_commander_web_v4.0.py), the Pyramid/Trim manager
(pyramid_logic.py) AND the GTT auto-trail (gtt_auto_shield --trail), so the
surfaces can never drift.

Pure computation (pandas/numpy only — no Streamlit), safe to import anywhere.

Catalyst-aware Chandelier trail = validated "Risk Allocator v2.0" set:
    POS 4.5 · WYC 3.5 · REV 2.5 · SWG 1.5   (+0.5 in a bear regime)
Level = 22-bar highest CLOSE − ATR(22, EWM α=1/22) × multiplier.

HOUSE-STANDARD RULING (Jay, 14-Jul-2026 Risk Shield audit): the TRAIL deliberately
uses the 22-bar window on highest CLOSE — NOT the DNA's 14-day ATR (that mandate
applies to INITIAL stop sizing) and NOT the textbook highest-HIGH. Rationale: the
validation campaign's hardest lesson was that tight stops on long holds give back
found edge; 14-bar/highest-high is strictly tighter and more reactive. Changing
this formula requires a replay.py A/B (22-close vs 14-high) FIRST — never an
aesthetic edit. Other engines converge onto THIS module (P2 reconciliation), not
the other way around.
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


def chandelier_exit(high: pd.Series, low: pd.Series, close: pd.Series,
                    setup: str = "", bear: bool = False,
                    cap_protect: bool = False, custom_mult=None,
                    above200: bool = True):
    """Catalyst-aware Chandelier trailing-stop level.

    Multiplier precedence (identical to the Risk Shield page):
      1. valid custom override (>0)           → "custom"
      2. catalyst-aware set (trail_mult_for)  → "<setup/family>"
      3. heuristic fallback (4.5 bull / 5.0 bear)
      4. cap-protect (portfolio drawdown)     → 2.5, overrides all of the above

    Returns (level, multiplier, source) or (None, None, None) when there are
    fewer than 22 bars.
    """
    if close is None or len(close) < 22:
        return (None, None, None)

    highest_close_22 = float(close.rolling(22).max().iloc[-1])
    tr = pd.concat([high - low,
                    (high - close.shift(1)).abs(),
                    (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr_22 = float(tr.ewm(alpha=1 / 22, adjust=False).mean().iloc[-1])

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

    if np.isnan(highest_close_22) or np.isnan(atr_22):
        return (None, None, None)
    return (float(highest_close_22 - atr_22 * mult), float(mult), src)
