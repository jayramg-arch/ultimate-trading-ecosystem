"""strict_trend.py — THE pivot-zigzag strict-trend engine, one definition.

Faithful port of `f_getStrictTrend` / `f_classifyHigh` / `f_classifyLow` as they
stand in **Weinstein and Swing Pro Dashboard v67.4.12** (which is itself declared a
mirror of *Wesinstein Swing Zigzag [Strict v6.3]* — "must remain bit-identical to
it… no independent evolution", dashboard line ~420).

WHY THIS MODULE EXISTS (29-Jul-2026)
------------------------------------
`bull_screener.compute_strict_trend` and `recovery_screener.compute_strict_trend`
were byte-identical copies of a **v1.4-era port**, frozen before the Zigzag v6.2/v6.3
fixes were propagated into Pine. Both then fed
`compute_weekly_stage_and_wks`, whose state machine carries two UNCONDITIONAL
overrides keyed on this function's output:

    if tDir ==  1 and stage == 4 -> stage 1     # rescues a downtrend into a base
    if tDir == -1 and stage == 2 -> stage 3

so every strict-trend error became a wrong Weinstein stage digit — and because
`stage in (1, 2)` is a hard screening gate (`stage_ok`), genuine Stage-4 names were
passing the gate and reaching the Golden Matcher board. Jay found it by diffing the
board's Stage column against the v67 dashboard on 29-Jul-2026.

THE SIX DIVERGENCES FIXED HERE (old Python -> Pine v67.1/v6.3)
--------------------------------------------------------------
1. EH/EL threshold 0.001 -> **0.002**. Canonical is the Zigzag v6.3 default
   (`eq_pct = 0.2` %) and the dashboard input default (`eq_threshold_dash = 0.002`).
   NOTE the dashboard's own header comment at line ~427 claims 0.005 — that comment
   is STALE; the input default is authoritative. Python was 2x tighter than canonical,
   so it classified as HH/LL what Pine calls EH/EL.
2. Extension path re-classifies against **prevLockedHigh/prevLockedLow**, not
   lockedHigh/lockedLow (which hold THIS direction's initial price). Old Python used
   the latter, producing false HH/LL when an extending pivot overshot.
3. Trend confirmation is **strict**: only HH-after-HL and LL-after-LH confirm.
   EH/EL always -> SIDEWAYS. Old Python let EL confirm an uptrend and EH a downtrend,
   which is the single biggest source of spurious tDir = +/-1.
4. Projection block reads the **confirmed** lastLowClass/lastHighClass instead of
   re-classifying from the projection extremes.
5. Projection block is **gated by activePivotType** — only the developing side is
   evaluated. Old Python evaluated both branches off locked values, so a name could
   flip trend on the wrong side.
6. syncBars = bar_index - activePivotIndex **+ 1**, so the projection window includes
   the pivot bar itself. Old Python omitted the +1 and started one bar late.

PLUS a seventh, which the changelog does not list and only shows up by reading the
body: the **asymmetric bootstrap**. Pine's pivot-LOW section opens with
`activePivotType == "H" or na(activePivotType)`; old Python had only
`== "H"`, so with no pivot yet established the first-ever swing LOW was silently
dropped. This is the same defect the 14-Jun-2026 Zigzag audit fixed in Pine (v6.2 ->
v6.3, Section 2 seed branch) — Python never received it. It biases any series whose
history opens in a downtrend.

KNOWN, DELIBERATE APPROXIMATION
-------------------------------
Pivot detection uses "unique extreme within the window" to stand in for Pine's
`ta.pivothigh` / `ta.pivotlow`. This is inherited from the original port and is NOT
part of the seven fixes above; it has not been bar-verified against Pine. If a
residual disagreement survives this port, look here first.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Canonical equal-pivot tolerance. Zigzag v6.3 `eq_pct = 0.2` % -> 0.002, and the
# dashboard's `eq_threshold_dash` input default. Keep these three in lockstep.
EQ_THRESHOLD: float = 0.002


def classify_high(new_high: float, prev_high: float, eq: float = EQ_THRESHOLD) -> str:
    """Mirror of f_classifyHigh. Defaults to 'HH' when there is no reference."""
    if prev_high is None or pd.isna(prev_high) or prev_high <= 0:
        return "HH"
    if abs(new_high - prev_high) / prev_high < eq:
        return "EH"
    return "LH" if new_high < prev_high else "HH"


def classify_low(new_low: float, prev_low: float, eq: float = EQ_THRESHOLD) -> str:
    """Mirror of f_classifyLow. Defaults to 'LL' when there is no reference."""
    if prev_low is None or pd.isna(prev_low) or prev_low <= 0:
        return "LL"
    if abs(new_low - prev_low) / prev_low < eq:
        return "EL"
    return "HL" if new_low > prev_low else "LL"


def compute_strict_trend(high: pd.Series, low: pd.Series,
                         piv_left: int = 2, piv_right: int = 2,
                         eq: float = EQ_THRESHOLD) -> pd.Series:
    """Per-bar strict trend: +1 up, -1 down, 0 sideways.

    Signature is unchanged from the previous in-screener version so existing call
    sites keep working; only the RESULT changes (that is the point of the port).
    """
    n = len(high)
    out = pd.Series(0, index=high.index, dtype=int)
    if n < (piv_left + piv_right + 1):
        return out

    h = high.to_numpy(dtype=float)
    l = low.to_numpy(dtype=float)

    trend_state = 0
    locked_high = np.nan
    locked_low = np.nan
    prev_locked_high = np.nan          # fix 2
    prev_locked_low = np.nan
    last_high_class = None             # Pine `na`
    last_low_class = None
    active_type = None                 # Pine `na`
    active_price = np.nan
    active_index = -1                  # Pine `na` -> syncBars falls back to 1

    for i in range(piv_left + piv_right, n):
        p = i - piv_right              # == Pine bar_index[right]

        win_h = h[p - piv_left: p + piv_right + 1]
        is_ph = (h[p] == win_h.max()) and ((win_h == h[p]).sum() == 1)
        win_l = l[p - piv_left: p + piv_right + 1]
        is_pl = (l[p] == win_l.min()) and ((win_l == l[p]).sum() == 1)

        # ---- 1. New pivot HIGH -------------------------------------------------
        if is_ph:
            v = h[p]
            if active_type == "H" and v > active_price:
                # EXTENDING: re-classify against the PREVIOUS structural high (fix 2)
                active_price = v
                active_index = p
                last_high_class = classify_high(v, prev_locked_high, eq)
            elif active_type == "L" or active_type is None:
                if active_type == "L":
                    locked_low = active_price
                h_class = classify_high(v, locked_high, eq)
                # fix 3 — strict only; EH -> sideways
                if h_class == "HH":
                    new_trend = 1 if last_low_class == "HL" else 0
                elif h_class == "LH":
                    new_trend = -1 if last_low_class == "LL" else 0
                else:
                    new_trend = 0
                trend_state = new_trend
                prev_locked_high = locked_high
                locked_high = v
                last_high_class = h_class
                active_price = v
                active_index = p
                active_type = "H"

        # ---- 2. New pivot LOW --------------------------------------------------
        if is_pl:
            v = l[p]
            if active_type == "L" and v < active_price:
                active_price = v
                active_index = p
                last_low_class = classify_low(v, prev_locked_low, eq)
            elif active_type == "H" or active_type is None:   # fix 7: the na seed
                if active_type == "H":
                    locked_high = active_price
                l_class = classify_low(v, locked_low, eq)
                if l_class == "LL":
                    new_trend = -1 if last_high_class == "LH" else 0
                elif l_class == "HL":
                    new_trend = 1 if last_high_class == "HH" else 0
                else:
                    new_trend = 0
                trend_state = new_trend
                prev_locked_low = locked_low
                locked_low = v
                last_low_class = l_class
                active_price = v
                active_index = p
                active_type = "L"

        # ---- 3. Live trend sync (projection BoS) -------------------------------
        # fix 6: +1 so the window captures the pivot bar itself.
        sync_bars = 1 if active_index < 0 else max(1, i - active_index + 1)
        proj_low = l[i - sync_bars + 1: i + 1].min()
        proj_high = h[i - sync_bars + 1: i + 1].max()

        # fix 5: gated by the developing side; fix 4: opposite side uses the
        # CONFIRMED class, never a re-classification of the projection.
        if active_type == "L" and classify_high(proj_high, locked_high, eq) == "HH":
            dev_low = "HL" if last_low_class is None else last_low_class
            trend_state = 1 if dev_low == "HL" else 0
        elif active_type == "H" and classify_low(proj_low, locked_low, eq) == "LL":
            dev_high = "LH" if last_high_class is None else last_high_class
            trend_state = -1 if dev_high == "LH" else 0

        out.iloc[i] = trend_state

    return out
