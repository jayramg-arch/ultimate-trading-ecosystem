"""
pa_field_validator.py — Python port of the Price Action cascade from
``Weinstein and Swing Pro Dashboard v67.4.8.pine`` (lines ~2735-3196) plus
its v67.4.7 post-cascade decorators (base-count tier adjustment + volume tag).

Purpose
-------
Provide a faithful, vectorised pandas implementation of the PA cascade so the
validation framework (validation.py / replay.py) can measure per-state alpha
with *catalyst-aware* forward windows. The cascade emits a ``paState`` /
``paTier`` / ``paColor`` triple per bar — identical semantics to Pine — that
can be joined onto trade entries.

Hard rules carried over from the project memory file
``memory/validation_window_mismatch_warning.md``:

* NEVER measure positional setups (VCP BO, Gap-Up BO, Stage-2 Launch, HTF)
  on a single 30-day window. Use the per-state horizons in
  ``FWD_DAYS_BY_PA_STATE`` below.
* Reversal setups (Hammer / Engulf / Spring) need 10–60d depending on tier.
* Coil/inside states are resolution-conditional — the consumer must measure
  forward returns FROM the breakout bar, not from the coil bar.

Faithful-port discipline
------------------------
Every detector mirrors the Pine expression line-for-line. Where Pine uses a
stateful ``var`` (base-count tracker, liquidity-sweep lockout) we keep a
per-row loop because the recursion genuinely requires it. Everything else is
pandas-vectorised.

Simplifications vs Pine (each marked with a ``# TODO:`` in code):

* ``vcp_ok`` — approximated as ``atr10 < atr40 * 0.75`` (matches v1.0
  strategy / dashboard's ``isContraction``). Dashboard's ``f_is_vcp`` adds a
  multi-base depth check — not yet ported.
* ``dLockH`` — approximated as ``high.rolling(20).max().shift(1)``. Pine's
  ``f_daily_super_bundle_internal`` uses a strict-trend locked high.
* ``stageID == "STAGE 2 (UP)"`` proxy — close > 30-WMA AND 30-WMA rising.
  Affects ``pa_s2_launch`` gate and the ``baseCount`` reset trigger.
* RSI divergence, EMA20 daily-on-intraday overlay, earnings, and other
  non-PA dashboard rows are out of scope.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# CANONICAL CATALYST-AWARE HORIZON MAPPING
# Mirrors ``f_default_horizon`` in Weinstein_PA_Field_Strategy_v1.0.pine
# (lines 83-93) and extends to every cascade state in v67.4.8.
# ----------------------------------------------------------------------------
FWD_DAYS_BY_PA_STATE: dict[str, int] = {
    # ─── Strongest override ────────────────────────────────────────────────
    "POWER_PLAY_HTF":           180,   # +4. Stage-2 launch leg (8w+15bar)

    # ─── Tier +3 (institutional launch / catalyst) ────────────────────────
    "SPRING":                   120,   # Wyckoff base-build, multi-month
    "GAP_UP_BO":                 90,   # Minervini institutional gap
    "VCP_BO":                    90,   # tight base breakout
    "STAGE_2_LAUNCH":           180,   # weekly 30WMA cross

    # ─── Tier +2 (confirmed continuation / institutional defense) ─────────
    "BREAKOUT_CONFIRMED":        90,
    "UNDERCUT_50SMA":            45,
    "POCKET_PIVOT":              30,
    "OUTSIDE_BAR_BULL":          15,
    "LIQ_SWEEP_RECLAIM":         20,
    "BULL_ENGULF":               20,
    "THREE_BAR_REV":             20,
    "POWER_PLAY_STRONG_CLOSE":   15,
    "HAMMER_AT_200SMA":          60,
    "HAMMER_AT_50SMA":           30,
    "IB_NR7_COIL":               10,   # resolution-conditional — measure from BO

    # ─── Tier +1 (early signal / coil) ────────────────────────────────────
    "BREAKOUT_UNCONFIRMED":      20,
    "CONSOLIDATION_TIGHT":       20,
    "FLAT_BASE":                 30,
    "INSIDE_3":                  10,
    "TRUE_NR7":                  10,
    "INSIDE_BAR":                 7,
    "HAMMER_REVERSAL":           15,

    # ─── Tier 0 ───────────────────────────────────────────────────────────
    "NORMAL":                    30,

    # ─── Tier -1 / -2 (warning states; for asymmetric measurement) ────────
    "SELLING_TAIL":              15,
    "FAILED_BO":                 30,
    "DISTRIBUTION_DAY":          30,
    "BEAR_ENGULF":               20,
    "SHOOTING_STAR_RESIST":      20,
}


def fwd_days_for_pa_state(state: str | None, default: int = 30) -> int:
    """Lookup helper mirroring replay.fwd_days_for_catalyst."""
    if not state:
        return default
    return FWD_DAYS_BY_PA_STATE.get(state, default)


# ============================================================================
# DETECTOR PORTS — Pine v67.4.8 lines 2849-2993
# ============================================================================
def compute_pa_detectors(df: pd.DataFrame,
                         benchmark: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Add every PA detector boolean column to ``df``.

    Ports Pine v67.4.8 lines 2849-2993 (detector definitions) plus the helper
    columns the cascade and decorators need (curRelVol, dMA50, dMA200,
    weekly 30-WMA via W-FRI resample, etc.).

    Parameters
    ----------
    df : DataFrame indexed by date with lower-case columns
        ['open','high','low','close','volume']. Upper-case columns are also
        accepted and normalised.
    benchmark : optional — not yet used in the cascade itself; reserved for
        future Stage-2 confirmation (Mansfield RS gate).

    Returns
    -------
    DataFrame copy with all helper + detector columns appended.
    """
    out = df.copy()
    # Normalise column case
    rename = {c: c.lower() for c in out.columns}
    out = out.rename(columns=rename)
    for col in ("open", "high", "low", "close", "volume"):
        if col not in out.columns:
            raise KeyError(f"compute_pa_detectors: missing column '{col}'")

    o, h, l, c, v = out["open"], out["high"], out["low"], out["close"], out["volume"]
    rng = h - l
    body_hi = pd.concat([o, c], axis=1).max(axis=1)
    body_lo = pd.concat([o, c], axis=1).min(axis=1)
    body = body_hi - body_lo
    upper_wick = h - body_hi
    lower_wick = body_lo - l

    # ── Indicator helpers ────────────────────────────────────────────────
    atr_val = _atr(h, l, c, 14)
    atr10 = _atr(h, l, c, 10)
    atr40 = _atr(h, l, c, 40)
    dma50 = c.rolling(50).mean()
    dma200 = c.rolling(200).mean()
    vavg = v.rolling(50).mean()
    cur_rel_vol = (v / vavg).where(vavg > 0, 0.0)

    ema10 = c.ewm(span=10, adjust=False).mean()
    ema20 = c.ewm(span=20, adjust=False).mean()
    in_downtrend_ctx = (c < ema10) & (ema10 < ema20)        # Pine line 2859
    in_uptrend_ctx = (c > ema10) & (ema10 > ema20)          # Pine line 2963

    h52 = h.rolling(252).max()

    # dLockH — Pine line 2117 approx (here: simple 20d high shifted)
    # TODO: upgrade to f_daily_super_bundle_internal's strict-trend locked high.
    d_lock_h = h.rolling(20).max().shift(1)
    has_lock_h = d_lock_h.notna()

    # vcp_ok — faithful port of dashboard's f_is_vcp (Pine line 2710-2715):
    #   is_tight = atr_10 < SMA(atr_10, 50) * mult       (NOT atr10 vs atr40!)
    #   is_dry   = VWMA(volume, 5) < SMA(volume, 50)
    #   vcp_ok   = is_tight AND is_dry
    # v67.4.9 FIX: prior port used atr10 < atr40*0.75 — a completely different
    # formula that never fires (0 firings ever on RELIANCE 5y). The dashboard
    # actually uses a self-referential tight-vs-average-atr10 check, which is
    # what Minervini's VCP describes.
    vcp_mult = 0.75
    sma_atr10_50 = atr10.rolling(50).mean()
    is_tight = atr10.notna() & sma_atr10_50.notna() & (sma_atr10_50 > 0) & (atr10 < sma_atr10_50 * vcp_mult)
    # VWMA(volume, 5) — volume-weighted MA of volume = sum(v*v)/sum(v) over 5
    vwma_v5_num = (v * v).rolling(5).sum()
    vwma_v5_den = v.rolling(5).sum()
    vwma_v5 = vwma_v5_num / vwma_v5_den.replace(0, np.nan)
    sma_v50 = v.rolling(50).mean()
    is_dry = vwma_v5.notna() & sma_v50.notna() & (vwma_v5 < sma_v50)
    vcp_ok = (is_tight & is_dry).fillna(False)

    # ── Stage-2 proxy (used by pa_s2_launch + baseCount) ────────────────
    # TODO: real Weinstein stage classification (30W slope + price position +
    # Mansfield RS gate). For now: close > 30WMA AND 30WMA rising over 4w.
    weekly_30wma_daily, w_s2_cross_daily = _weekly_30wma_and_cross(c)
    stage2_up = (c > weekly_30wma_daily) & (weekly_30wma_daily > weekly_30wma_daily.shift(20))

    # ── NR7 (Pine lines 2862-2869) — true strict-< NR over last 6 prior bars ─
    pa_nr7 = pd.Series(True, index=out.index)
    for i in range(1, 7):
        pa_nr7 &= rng < rng.shift(i)
    pa_nr7 = pa_nr7.fillna(False)

    # ── Inside / Inside-3 (Pine 2872-2873) ──────────────────────────────
    pa_inside = (h < h.shift(1)) & (l > l.shift(1))
    pa_inside3 = (
        pa_inside
        & (h.shift(1) < h.shift(2)) & (l.shift(1) > l.shift(2))
        & (h.shift(2) < h.shift(3)) & (l.shift(2) > l.shift(3))
    )

    # ── Pocket Pivot (Pine 2876-2883) ───────────────────────────────────
    # max down-volume of last 10 bars (down = close[j] < close[j+1])
    max_down_vol = pd.Series(0.0, index=out.index)
    for j in range(1, 11):
        is_down = c.shift(j) < c.shift(j + 1)
        max_down_vol = pd.concat([
            max_down_vol,
            v.shift(j).where(is_down, 0.0),
        ], axis=1).max(axis=1)
    pp_upper_half = (c - l) >= (rng * 0.5)
    pa_pocket = (
        (c > c.shift(1))
        & (c > o)
        & (max_down_vol > 0)
        & (v > max_down_vol)
        & dma50.notna()
        & (c > dma50)
        & pp_upper_half
    ).fillna(False)

    # ── Engulfing (Pine 2887-2889) ──────────────────────────────────────
    # v67.4.11 B6 GATE: tightened from relvol>1.2 to relvol>2.0 AND prior-bar
    # RSI(14)<40. Empirically verified to raise bull-regime alpha from -0.21%
    # to +1.35% and bear-regime from +2.93% to +6.92%. See dashboard v67.4.11
    # changelog for the multi-variant comparison.
    raw_bull_engulf = (
        (c.shift(1) < o.shift(1))
        & (c > o)
        & (o <= c.shift(1))
        & (c >= o.shift(1))
    )
    # Wilder RSI(14)
    _delta = c.diff()
    _gain = _delta.where(_delta > 0, 0.0).ewm(alpha=1.0 / 14, adjust=False).mean()
    _loss = (-_delta.where(_delta < 0, 0.0)).ewm(alpha=1.0 / 14, adjust=False).mean()
    _rs = _gain / _loss.replace(0, np.nan)
    _rsi14 = 100 - (100 / (1 + _rs))
    _rsi_prev_oversold = _rsi14.shift(1) < 40
    pa_bull_engulf = (raw_bull_engulf & in_downtrend_ctx & (cur_rel_vol > 2.0) & _rsi_prev_oversold).fillna(False)
    pa_bear_engulf = (
        (c.shift(1) > o.shift(1))
        & (c < o)
        & (o >= c.shift(1))
        & (c <= o.shift(1))
    ).fillna(False)

    # ── Hammer (Pine 2898) ──────────────────────────────────────────────
    pa_hammer = (
        (rng > 0)
        & (lower_wick > body * 2)
        & (upper_wick < body)
        & (body_hi >= l + rng * 0.66)
    ).fillna(False)

    # ── Wyckoff Spring (Pine 2904-2906) ─────────────────────────────────
    l50 = l.rolling(50).min()
    vol_sma50 = v.rolling(50).mean()
    pa_spring = (
        l50.shift(1).notna()
        & (l < l50.shift(1))
        & (c > l50.shift(1))
        & (c > o)
        & (v < vol_sma50)
    ).fillna(False)

    # ── Failed Breakout (Pine 2911-2912) ────────────────────────────────
    # v67.4.9 FIX #2: dLockH includes close[1] in its rolling max, so
    # close[1] > dLockH was structurally impossible. Use dLockH[1].
    bo_buf = atr_val * 0.5
    d_lock_h_ref = d_lock_h.shift(1)
    pa_failed_bo = (
        d_lock_h_ref.notna()
        & (c < d_lock_h_ref)
        & (c.shift(1) > (d_lock_h_ref + bo_buf))
        & (h.shift(1) > (d_lock_h_ref + bo_buf))
        & (cur_rel_vol > 1.0)
    ).fillna(False)

    # ── 3-Bar Bullish Reversal (Pine 2915) ──────────────────────────────
    max3h = pd.concat([h.shift(1), h.shift(2), h.shift(3)], axis=1).max(axis=1)
    pa_3bar_rev = (
        (l.shift(1) < l.shift(2))
        & (l.shift(2) < l.shift(3))
        & (c > max3h)
    ).fillna(False)

    # ── Distribution Day (Pine 2920) ────────────────────────────────────
    pa_distrib = (
        (c < c.shift(1) * 0.998)
        & (v > v.shift(1))
        & ((h - l) > atr_val)
    ).fillna(False)

    # ── Flat Base (Pine 2923-2925) ──────────────────────────────────────
    h25 = h.rolling(25).max()
    l25 = l.rolling(25).min()
    pa_flat_base = ((l25 > 0) & ((h25 - l25) / l25 < 0.12)).fillna(False)

    # ── Stage-2 Launch (Pine 2931-2932) ─────────────────────────────────
    pa_s2_launch = (stage2_up & w_s2_cross_daily & (cur_rel_vol > 1.25)).fillna(False)

    # ── SMC Liquidity Sweep w/ lockout (Pine 2939-2945) ─────────────────
    c_s50 = c.rolling(50).mean()
    c_vol_sma50 = v.rolling(50).mean()
    c_low5 = l.rolling(5).min()
    raw_liq_sweep = (c_low5 < c_s50) & (c > c_s50) & (v > c_vol_sma50 * 1.5)
    raw_liq_sweep = raw_liq_sweep.fillna(False)
    liq_sweep_lockout = 10  # matches Pine default
    c_liq_sweep = _stateful_lockout(raw_liq_sweep, liq_sweep_lockout)

    # ── VCP Breakout (Pine 2948-2949) ───────────────────────────────────
    # v67.4.9 FIX #1: use PRIOR-bar vcp_ok. The breakout bar is by definition
    # an expansion bar (close>10dHigh, wide range, vol spike) — atr10 spikes
    # on it, making atr10<atr40*0.75 false on the very bar we want to fire.
    # The Minervini sequence is "tight → break"; check contraction BEFORE.
    pa_10d_high_1 = h.rolling(10).max().shift(1)
    pa_vcp_bo = (
        vcp_ok.shift(1).fillna(False).astype(bool)
        & (c > pa_10d_high_1)
        & (cur_rel_vol > 1.2)
        & ((c - l) > (rng * 0.60))
    ).fillna(False)

    # ── Anti-algo Breakout (Pine 2952-2955) ─────────────────────────────
    close_near_high = (c - l) > (rng * 0.75)
    vol_confirm = cur_rel_vol > 1.25
    is_true_breakout = (has_lock_h & (c > d_lock_h) & close_near_high & vol_confirm).fillna(False)

    # ── Shooting Star (Pine 2968-2970) ──────────────────────────────────
    ss_shape = (rng > 0) & (upper_wick > body * 2) & (lower_wick < body) & (body_lo <= l + rng * 0.33)
    ss_extended = (
        (h52.notna() & (h52 > 0) & ((c / h52) > 0.95))
        | (dma50.notna() & (dma50 > 0) & (((c - dma50) / dma50) > 0.15))
    )
    pa_shooting_star = (ss_shape & in_uptrend_ctx & ss_extended).fillna(False)

    # ── Outside Bar Bullish (Pine 2974) ─────────────────────────────────
    pa_outside_bull = (
        (h > h.shift(1)) & (l < l.shift(1)) & (c > h.shift(1)) & (c > o)
    ).fillna(False)

    # ── Gap-Up Breakout (Pine 2978) ─────────────────────────────────────
    pa_gap_up_bo = (
        has_lock_h
        & (o > h.shift(1))
        & (c > d_lock_h)
        & (c > o)
        & vol_confirm
    ).fillna(False)

    # ── IB-NR7 Coil (Pine 2982) ─────────────────────────────────────────
    pa_ib_nr7 = (pa_inside & pa_nr7).fillna(False)

    # ── Hammer at 50/200 (Pine 2986-2989) ───────────────────────────────
    near_dma50 = dma50.notna() & (dma50 > 0) & ((l - dma50).abs() / dma50 <= 0.015)
    near_dma200 = dma200.notna() & (dma200 > 0) & ((l - dma200).abs() / dma200 <= 0.020)
    pa_hammer_at_50 = (pa_hammer & near_dma50 & (c > dma50) & (cur_rel_vol > 1.0)).fillna(False)
    pa_hammer_at_200 = (pa_hammer & near_dma200 & (c > dma200) & (cur_rel_vol > 1.0)).fillna(False)

    # ── 50SMA Undercut & Rally (Pine 2993) ──────────────────────────────
    pa_50sma_undercut = (
        dma50.notna() & (dma50 > 0)
        & (l < dma50) & (c > dma50) & (c > o)
        & (cur_rel_vol > 1.25)
    ).fillna(False)

    # ── Power Play (Strong Close) — inline branch in Pine cascade ───────
    pa_power_strong = (
        (c > o) & ((c - l) > (h - c) * 3) & (cur_rel_vol > 1.0)
    ).fillna(False)

    # ── Selling Tail — inline branch in Pine cascade ────────────────────
    pa_selling_tail = ((c < o) & ((h - c) > (c - l) * 3)).fillna(False)

    # ── HTF override (Pine 3161-3164) ───────────────────────────────────
    low8w = l.rolling(40).min()
    big_move = ((c - low8w) / low8w) > 1.0
    consolidation = (
        (h.rolling(15).max() - l.rolling(15).min()) / l.rolling(15).min() < 0.20
    )
    pa_htf = (big_move & consolidation & (c > dma50)).fillna(False)

    # ── Base count tracker (Pine 3002-3019) — genuinely stateful ────────
    base_count = _base_count_tracker(h, l, c, stage2_up)

    # ── Attach all detector + helper columns ────────────────────────────
    out["cur_rel_vol"] = cur_rel_vol
    out["dma50"] = dma50
    out["dma200"] = dma200
    out["atr_val"] = atr_val
    out["d_lock_h"] = d_lock_h
    out["stage2_up"] = stage2_up
    out["base_count"] = base_count

    out["pa_vcp_bo"] = pa_vcp_bo
    out["pa_gap_up_bo"] = pa_gap_up_bo
    out["pa_s2_launch"] = pa_s2_launch
    out["pa_50sma_undercut"] = pa_50sma_undercut
    out["pa_hammer"] = pa_hammer
    out["pa_hammer_at_50"] = pa_hammer_at_50
    out["pa_hammer_at_200"] = pa_hammer_at_200
    out["pa_spring"] = pa_spring
    out["pa_failed_bo"] = pa_failed_bo
    out["pa_bull_engulf"] = pa_bull_engulf
    out["pa_bear_engulf"] = pa_bear_engulf
    out["pa_shooting_star"] = pa_shooting_star
    out["pa_outside_bull"] = pa_outside_bull
    out["pa_3bar_rev"] = pa_3bar_rev
    out["pa_distrib"] = pa_distrib
    out["pa_flat_base"] = pa_flat_base
    out["pa_pocket"] = pa_pocket
    out["pa_nr7"] = pa_nr7
    out["pa_inside"] = pa_inside
    out["pa_inside3"] = pa_inside3
    out["pa_ib_nr7"] = pa_ib_nr7
    out["pa_liq_sweep"] = c_liq_sweep
    out["pa_true_breakout"] = is_true_breakout
    out["pa_power_strong"] = pa_power_strong
    out["pa_selling_tail"] = pa_selling_tail
    out["pa_htf"] = pa_htf
    out["pa_in_downtrend_ctx"] = in_downtrend_ctx.fillna(False)
    out["pa_in_uptrend_ctx"] = in_uptrend_ctx.fillna(False)
    out["pa_has_lock_h"] = has_lock_h.fillna(False)
    return out


# ============================================================================
# CASCADE — Pine v67.4.8 lines 3024-3158
# ============================================================================
def apply_pa_cascade(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the priority if/else chain to set paState_str / paTier / paColor_str.

    Ports Pine v67.4.8 lines 3024-3158 (main cascade) + 3160-3168 (HTF override).
    Cascade ordering is identical to Pine: bearish warnings first, then
    Tier +3 catalysts, Tier +2 confirmations, Tier +1 coils, then default.

    Operates on rows that already have ``compute_pa_detectors`` output.
    """
    n = len(df)
    state = np.full(n, "NORMAL", dtype=object)
    tier = np.zeros(n, dtype=np.int8)
    color = np.full(n, "gray", dtype=object)

    # Pull arrays once
    def col(name):
        return df[name].to_numpy() if name in df.columns else np.zeros(n, dtype=bool)

    failed_bo = col("pa_failed_bo")
    distrib = col("pa_distrib")
    bear_engulf = col("pa_bear_engulf")
    dma50 = df["dma50"].to_numpy()
    c_arr = df["close"].to_numpy()
    shooting_star = col("pa_shooting_star")
    spring = col("pa_spring")
    gap_up_bo = col("pa_gap_up_bo")
    vcp_bo = col("pa_vcp_bo")
    s2_launch = col("pa_s2_launch")
    true_breakout = col("pa_true_breakout")
    undercut = col("pa_50sma_undercut")
    pocket = col("pa_pocket")
    outside_bull = col("pa_outside_bull")
    liq_sweep = col("pa_liq_sweep")
    bull_engulf = col("pa_bull_engulf")
    three_bar = col("pa_3bar_rev")
    power_strong = col("pa_power_strong")
    has_lock_h = col("pa_has_lock_h")
    d_lock_h = df["d_lock_h"].to_numpy()
    flat_base = col("pa_flat_base")
    ib_nr7 = col("pa_ib_nr7")
    inside3 = col("pa_inside3")
    nr7 = col("pa_nr7")
    inside = col("pa_inside")
    hammer_200 = col("pa_hammer_at_200")
    hammer_50 = col("pa_hammer_at_50")
    hammer = col("pa_hammer")
    in_downtrend = col("pa_in_downtrend_ctx")
    selling_tail = col("pa_selling_tail")
    htf = col("pa_htf")
    base_count = df["base_count"].to_numpy()

    for i in range(n):
        # Lock-H proximity helpers used by tier-1 branches
        breakout_unconf = (
            has_lock_h[i] and not np.isnan(d_lock_h[i])
            and c_arr[i] > d_lock_h[i]
        )
        consolidation_tight = (
            has_lock_h[i] and not np.isnan(d_lock_h[i])
            and c_arr[i] < d_lock_h[i] and c_arr[i] > (d_lock_h[i] * 0.95)
        )

        # ── Cascade (priority order EXACTLY matches Pine 3025-3158) ──────
        if failed_bo[i]:
            st, t, col_ = "FAILED_BO", -2, "red"
        elif distrib[i]:
            st, t, col_ = "DISTRIBUTION_DAY", -2, "red"
        elif bear_engulf[i] and not np.isnan(dma50[i]) and c_arr[i] < dma50[i]:
            st, t, col_ = "BEAR_ENGULF", -2, "red"
        elif shooting_star[i]:
            st, t, col_ = "SHOOTING_STAR_RESIST", -2, "red"
        elif spring[i]:
            st, t, col_ = "SPRING", 3, "green_bright"
        elif gap_up_bo[i]:
            st, t, col_ = "GAP_UP_BO", 3, "green_bright"
        elif vcp_bo[i]:
            st, t, col_ = "VCP_BO", 3, "green_bright"
        elif s2_launch[i]:
            st, t, col_ = "STAGE_2_LAUNCH", 3, "teal"
        elif true_breakout[i]:
            st, t, col_ = "BREAKOUT_CONFIRMED", 2, "teal"
        elif undercut[i]:
            st, t, col_ = "UNDERCUT_50SMA", 2, "green_bright"
        elif pocket[i]:
            st, t, col_ = "POCKET_PIVOT", 2, "teal"
        # v67.4.10: OUTSIDE_BAR_BULL demoted from Tier +2 to Tier +1 — moved
        # below the Tier +2 group. N500 measured +0.46% pred alpha, weakest
        # of all Tier +2 detectors and beaten by HAMMER_REVERSAL (+0.70%) at
        # Tier +1. Same change as dashboard v67.4.10.
        elif liq_sweep[i]:
            st, t, col_ = "LIQ_SWEEP_RECLAIM", 2, "aqua"
        elif bull_engulf[i]:
            st, t, col_ = "BULL_ENGULF", 2, "teal"
        elif three_bar[i]:
            st, t, col_ = "THREE_BAR_REV", 2, "teal"
        elif power_strong[i]:
            st, t, col_ = "POWER_PLAY_STRONG_CLOSE", 2, "teal"
        elif breakout_unconf:
            st, t, col_ = "BREAKOUT_UNCONFIRMED", 1, "orange"
        elif consolidation_tight:
            st, t, col_ = "CONSOLIDATION_TIGHT", 1, "blue"
        elif flat_base[i]:
            st, t, col_ = "FLAT_BASE", 1, "blue"
        elif ib_nr7[i]:
            st, t, col_ = "IB_NR7_COIL", 2, "teal"
        elif inside3[i]:
            st, t, col_ = "INSIDE_3", 1, "orange"
        elif nr7[i]:
            st, t, col_ = "TRUE_NR7", 1, "orange"
        elif inside[i]:
            st, t, col_ = "INSIDE_BAR", 1, "orange"
        elif outside_bull[i]:
            # v67.4.10: demoted from Tier +2 (was between POCKET_PIVOT and
            # LIQ_SWEEP_RECLAIM). Still flagged with star-equivalent in
            # dashboard display, but no longer earns Tier +2 score weight.
            st, t, col_ = "OUTSIDE_BAR_BULL", 1, "teal"
        elif hammer_200[i]:
            st, t, col_ = "HAMMER_AT_200SMA", 2, "green_bright"
        elif hammer_50[i]:
            st, t, col_ = "HAMMER_AT_50SMA", 2, "teal"
        elif hammer[i] and in_downtrend[i]:
            st, t, col_ = "HAMMER_REVERSAL", 1, "teal"
        elif selling_tail[i]:
            st, t, col_ = "SELLING_TAIL", -1, "orange"
        else:
            st, t, col_ = "NORMAL", 0, "gray"

        # ── HTF override (Pine 3165-3168) ───────────────────────────────
        if htf[i]:
            st, t, col_ = "POWER_PLAY_HTF", 4, "fuchsia"

        state[i] = st
        tier[i] = t
        color[i] = col_

    out = df.copy()
    out["paState_str"] = state
    out["paTier"] = tier
    out["paColor_str"] = color
    return out


# ============================================================================
# POST-CASCADE DECORATORS — Pine v67.4.7 lines 3171-3196
# ============================================================================
def apply_decorators(df: pd.DataFrame) -> pd.DataFrame:
    """Apply base-count tier adjustment + volume tag.

    Ports Pine v67.4.8 lines 3170-3196. Two decorators run AFTER the HTF
    override so they see the final paTier/paState.

    1. Base-count tier adjustment — demotes breakout-class tiers when
       baseCount is elevated (B3 → -1 tier, B4+ → -2 tier). HTF (Tier 4)
       is exempt; only bullish breakout/launch class affected.
    2. Volume-confirmation tag — appends ``_VOL_HI`` / ``_VOL_INST`` /
       ``_VOL_LOW`` to actionable patterns (|paTier|≥1) based on curRelVol.
       Pine appends "(Vol+)" / "(Vol++)" / "(Low Vol)" strings; we use
       underscored suffixes so downstream state lookup stays exact.

    NOTE: the volume suffix is OPTIONAL metadata — consumers wanting to
    look up FWD_DAYS_BY_PA_STATE should strip the suffix first via
    ``base_state(s)``.
    """
    out = df.copy()
    state = out["paState_str"].to_numpy(copy=True)
    tier = out["paTier"].to_numpy(copy=True)
    rel_vol = out["cur_rel_vol"].to_numpy()
    base_cnt = out["base_count"].to_numpy()

    # Breakout/launch class membership (Pine 3175)
    is_bo_class_mask = np.array([
        (2 <= t < 4) and ("BO" in s or "BREAKOUT" in s or "LAUNCH" in s)
        for s, t in zip(state, tier)
    ])

    for i in range(len(out)):
        if is_bo_class_mask[i]:
            bc = base_cnt[i]
            if bc == 3:
                state[i] = state[i] + "_LATE_STAGE"
                tier[i] -= 1
            elif bc >= 4:
                state[i] = state[i] + f"_VLATE_B{int(bc)}"
                tier[i] -= 2

        # Volume tag (Pine 3190-3196). |tier|≥1 only.
        if abs(tier[i]) >= 1:
            rv = rel_vol[i]
            if not np.isnan(rv):
                if rv >= 2.0:
                    state[i] = state[i] + "_VOL_INST"
                elif rv >= 1.5:
                    state[i] = state[i] + "_VOL_HI"
                elif rv < 0.7:
                    state[i] = state[i] + "_VOL_LOW"

    out["paState_str"] = state
    out["paTier"] = tier
    return out


def base_state(state: str) -> str:
    """Strip decorator suffixes for a clean FWD_DAYS_BY_PA_STATE lookup."""
    if not state:
        return state
    for suffix in ("_VOL_INST", "_VOL_HI", "_VOL_LOW", "_LATE_STAGE"):
        if state.endswith(suffix):
            state = state[: -len(suffix)]
    # _VLATE_B<n> — variable
    if "_VLATE_B" in state:
        state = state.split("_VLATE_B")[0]
    return state


# ============================================================================
# INTERNAL HELPERS
# ============================================================================
def _atr(h: pd.Series, l: pd.Series, c: pd.Series, length: int) -> pd.Series:
    """Wilder's ATR — matches Pine ta.atr(length)."""
    prev_close = c.shift(1)
    tr = pd.concat([
        (h - l).abs(),
        (h - prev_close).abs(),
        (l - prev_close).abs(),
    ], axis=1).max(axis=1)
    # Pine ta.atr uses RMA (Wilder smoothing) = EMA with alpha=1/length
    return tr.ewm(alpha=1.0 / length, adjust=False).mean()


def _weekly_30wma_and_cross(daily_close: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Resample close to W-FRI, compute 30-WMA, detect crossover, ffill to daily.

    Returns (weekly_30wma_aligned_to_daily, weekly_crossover_daily_flag).
    The crossover flag fires on the daily bar that *closes the week* in which
    Pine's request.security("W", ta.crossover(...)) would have fired.
    """
    wk = daily_close.resample("W-FRI").last().dropna()
    wma30 = wk.rolling(30).mean()
    crossover = (wk > wma30) & (wk.shift(1) <= wma30.shift(1))
    # ffill weekly values back onto daily index
    wma30_daily = wma30.reindex(daily_close.index, method="ffill")
    crossover_daily = crossover.reindex(daily_close.index, method="ffill").fillna(False)
    # Make the cross fire only on the actual week-close day in the daily index
    # (avoid the ffill spreading "True" across the whole following week).
    week_close_days = set(wk.index)
    crossover_daily = pd.Series(
        [bool(crossover.get(idx, False)) if idx in week_close_days else False
         for idx in daily_close.index],
        index=daily_close.index,
    )
    return wma30_daily, crossover_daily


def _stateful_lockout(raw_signal: pd.Series, lockout_bars: int) -> pd.Series:
    """Replicate Pine's ``var int barsSinceX`` lockout pattern.

    raw_signal=True only counts if more than ``lockout_bars`` have passed
    since the last accepted fire. Matches Pine v67.2 FIX #7 (dashboard 2943-2945).
    """
    arr = raw_signal.fillna(False).to_numpy()
    out = np.zeros(len(arr), dtype=bool)
    bars_since = 10**6
    for i in range(len(arr)):
        if arr[i] and bars_since > lockout_bars:
            out[i] = True
            bars_since = 0
        else:
            bars_since += 1
    return pd.Series(out, index=raw_signal.index)


def _base_count_tracker(h: pd.Series, l: pd.Series, c: pd.Series,
                        stage2_up: pd.Series) -> pd.Series:
    """Port of Pine v67.4.6 base count state machine (lines 3002-3019).

    Resets to 1 on fresh Stage 1→2 transition. Increments on prior-base-high
    reclaim after ≥7% pullback.
    """
    n = len(c)
    out = np.zeros(n, dtype=np.int32)
    base_count = 0
    base_track_high = np.nan
    pullback_occurred = False

    s2_arr = stage2_up.fillna(False).to_numpy()
    h_arr = h.to_numpy()
    l_arr = l.to_numpy()
    c_arr = c.to_numpy()

    for i in range(n):
        fresh_s2 = bool(s2_arr[i]) and (i == 0 or not bool(s2_arr[i - 1]))
        if fresh_s2:
            base_count = 1
            base_track_high = h_arr[i]
            pullback_occurred = False
        elif not np.isnan(base_track_high):
            if l_arr[i] < base_track_high * 0.93:
                pullback_occurred = True
            if pullback_occurred and c_arr[i] > base_track_high:
                base_count += 1
                base_track_high = h_arr[i]
                pullback_occurred = False
            elif h_arr[i] > base_track_high and not pullback_occurred:
                base_track_high = h_arr[i]
        out[i] = base_count
    return pd.Series(out, index=c.index)


# ============================================================================
# SMOKE TEST
# ============================================================================
if __name__ == "__main__":
    import sys

    try:
        import data_provider as _dp
    except Exception as e:
        print(f"[smoke] data_provider import failed: {e}")
        sys.exit(1)

    sym = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    print(f"[smoke] symbol={sym} — fetching 2y daily…")

    try:
        raw = _dp.fetch_ohlcv(sym, period="2y", interval="1d")
    except Exception as e:
        print(f"[smoke] fetch failed: {e}")
        sys.exit(1)

    if raw is None or raw.empty:
        print("[smoke] empty DataFrame — cache miss or fetch failure.")
        sys.exit(1)

    df = compute_pa_detectors(raw)
    df = apply_pa_cascade(df)
    df = apply_decorators(df)

    cols_to_show = ["close", "cur_rel_vol", "base_count",
                    "paState_str", "paTier", "paColor_str"]
    available = [c for c in cols_to_show if c in df.columns]
    print(df.tail(20)[available].to_string())

    # Quick distribution sanity
    print("\n[smoke] paState distribution (last 252 bars):")
    print(df["paState_str"].apply(base_state).tail(252).value_counts().head(15))
