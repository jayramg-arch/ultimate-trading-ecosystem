"""zone_engine.vp_support must compute S4Core.volumeProfile, not a cheaper cousin (AUD-PAR-09)."""
import numpy as np
import pandas as pd

import zone_engine as z


def _frame(highs, lows, vols, close=None):
    n = len(highs)
    c = close if close is not None else [(h + l) / 2 for h, l in zip(highs, lows)]
    return pd.DataFrame({"Open": c, "High": highs, "Low": lows, "Close": c, "Volume": vols})


def test_window_is_last_100_bars():
    # an extreme bar 101 bars back must not stretch the range
    h = [200.0] + [110.0] * 100
    l = [50.0] + [100.0] * 100
    r = z.vp_support(_frame(h, l, [1000.0] * 101))
    assert r["vp_val"] >= 100.0 and r["vp_vah"] <= 110.0


def test_volume_is_spread_by_overlap_not_dropped_at_typical_price():
    # 60 wide bars 100-140 and 40 narrow bars 100-101: overlap-weighting puts the POC in the
    # narrow cluster (all its volume in one row); typical-price binning would put the wide
    # bars' whole volume at 120 and move the POC there.
    h = [140.0] * 60 + [101.0] * 40
    l = [100.0] * 60 + [100.0] * 40
    r = z.vp_support(_frame(h, l, [1000.0] * 100, close=[101.0] * 100))
    assert r["vp_poc"] < 102.0


def test_value_area_edges_are_row_edges():
    h = [110.0] * 100
    l = [100.0] * 100
    r = z.vp_support(_frame(h, l, [1000.0] * 100))
    row = (110.0 - 100.0) / 40
    for k in ("vp_val", "vp_vah"):
        assert abs((r[k] - 100.0) / row - round((r[k] - 100.0) / row)) < 1e-9


def test_near_rule_is_s4s():
    h = [110.0] * 100
    l = [100.0] * 100
    base = z.vp_support(_frame(h, l, [1000.0] * 100))
    below = z.vp_support(_frame(h, l, [1000.0] * 100), price=base["vp_val"] - 0.01)
    assert not below["near_vp_val"]          # under the level is resistance, never support
