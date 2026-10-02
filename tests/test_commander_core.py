"""commander_core (25-Sep split phase 2): the GM stop ladder and helpers, now testable.

These pin today's behaviour so a later edit that changes a stop has to change a test too.
Numbers are worked by hand from the rule: in-zone distal -> nearest zone distal -> 10-bar
swing low, 0.5% buffer, capped at 2.5x ATR (swing) / 4.0x ATR (positional); swing when
ATR% > 4, or > 30% off the 52W high, or below the 200-DMA.
"""
import math

import commander_core as cc


def _ctx(basis, d52=-5.0, s200=80.0, cmp_=100.0):
    return {"support": {"sl_basis": dict(basis, tf="Daily")}, "dist52wh": d52,
            "sma200": s200, "cmp": cmp_}


def test_g_skips_nan_and_none():
    assert cc._g({"a": float("nan"), "b": None, "c": 3}, "a", "b", "c") == 3
    assert cc._g({}, "x", default="d") == "d"


def test_in_zone_distal_with_buffer_swing():
    # swing keeps the structural stop (no daily-ATR floor)
    sl, src = cc._plan_structural_sl(_ctx({"in_dist": 96.0, "atr": 2.0, "close": 100.0}, s200=120.0),
                                     100.0, 2.0, ret_src=True)
    assert math.isclose(sl, 96.0 * 0.995)
    assert src.startswith("zone distal (in-zone)") and "SWING" in src


def test_positional_stop_floored_at_4_daily_atr():
    # 2-Oct-2026: a positional stop is never closer than 4x DAILY ATR
    sl, src = cc._plan_structural_sl(_ctx({"in_dist": 95.0, "atr": 2.0, "close": 100.0}), 100.0, 2.0, ret_src=True)
    assert math.isclose(sl, 92.0) and "ATR(D) floor" in src and "POSITIONAL" in src


def test_intraday_basis_uses_daily_atr_for_the_floor():
    # 75m basis: chart ATR 0.7 caps the structure at 97.2; daily ATR 2.0 floors it at 92
    ctx = {"support": {"sl_basis": {"in_dist": 80.0, "atr": 0.7, "close": 100.0, "tf": "75m"}},
           "dist52wh": -5.0, "sma200": 80.0, "cmp": 100.0, "atr": 2.0}
    sl, src = cc._plan_structural_sl(ctx, 100.0, 0.7, ret_src=True)
    assert math.isclose(sl, 92.0) and "ATR(D) floor" in src


def test_far_structure_is_capped_at_4_atr_positional():
    sl, src = cc._plan_structural_sl(_ctx({"in_dist": 80.0, "atr": 2.0, "close": 100.0}), 100.0, 2.0, ret_src=True)
    assert math.isclose(sl, 92.0) and "capped at 4.0xATR" in src


def test_swing_when_atr_pct_above_4_caps_at_2_5_atr():
    sl, src = cc._plan_structural_sl(_ctx({"in_dist": 80.0, "atr": 5.0, "close": 100.0}), 100.0, 5.0, ret_src=True)
    assert math.isclose(sl, 87.5) and "SWING" in src


def test_swing_when_below_200dma():
    sl, src = cc._plan_structural_sl(_ctx({"in_dist": 80.0, "atr": 2.0, "close": 100.0}, s200=120.0),
                                     100.0, 2.0, ret_src=True)
    assert math.isclose(sl, 95.0) and "SWING" in src


def test_no_structure_falls_to_atr_and_no_atr_means_no_stop():
    sl, src = cc._plan_structural_sl(_ctx({"atr": 2.0, "close": 100.0}), 100.0, 2.0, ret_src=True)
    assert math.isclose(sl, 92.0) and "no structure below" in src
    assert cc._plan_structural_sl(_ctx({}), 100.0, None) is None


def test_zone_rungs_pick_best_inside_and_highest_nearest():
    zs = [{"zone_state": "inside", "distal": 90.0, "score": 60},
          {"zone_state": "inside", "distal": 92.0, "score": 80},
          {"near_dz_proximal": 97.0, "near_dz_distal": 94.0},
          {"near_dz_proximal": 95.0, "near_dz_distal": 93.0}]
    assert cc._gm_zone_rungs(zs) == (92.0, 94.0)
