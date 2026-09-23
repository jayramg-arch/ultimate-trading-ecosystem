"""The cash-name LEVEL CHECK, and the volume profile it stands on.

Half the board is cash-only and used to get no level validation at all — LEVEL CHECK
printed "no options" and fell through to footprint delta. These tests pin the two things
that would silently break it:

  1. the profile maths (a wrong POC is invisible in prose — it just reads plausible), and
  2. that the cash branch fires ONLY for cash names and never disturbs the F&O path.

Parameters come from docs/PREREG_cash_levels.md and are deliberately NOT asserted against
magic numbers here; the test builds a distribution whose answer is known by construction.
"""
import numpy as np
import pandas as pd

import volume_profile as vp
from s4_review import _cash_levels, _cash_level_lines, level_check


def _frame(prices, vols=None, n_each=1):
    """Daily bars where each price is traded n_each times with a given volume."""
    rows = []
    for p, v in zip(prices, vols or [1000] * len(prices)):
        for _ in range(n_each):
            rows.append({"High": p + 0.5, "Low": p - 0.5, "Close": p, "Volume": v})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ profile maths
def test_poc_lands_where_the_volume_is():
    """One price traded on 10x the volume must be the POC — if this drifts, every cash
    'magnet' line is quietly wrong and still reads fine."""
    prices = list(np.linspace(100, 200, 60))
    vols = [1000] * 60
    vols[30] = 50_000                       # 100 + 100*30/59 ~= 150.8
    out = vp.profile(_frame(prices, vols))
    assert out, "no profile produced"
    assert abs(out["poc"] - prices[30]) < 3.0, out["poc"]


def test_value_area_brackets_the_poc_and_is_narrower_than_the_range():
    out = vp.profile(_frame(list(np.linspace(100, 200, 80))))
    assert out["val"] < out["poc"] < out["vah"]
    assert (out["vah"] - out["val"]) < (200 - 100), "value area is not narrower than the range"


def test_hvns_are_the_busy_bins_only():
    prices = list(np.linspace(100, 200, 60))
    vols = [1000] * 60
    for i in (10, 40):
        vols[i] = 40_000
    out = vp.profile(_frame(prices, vols))
    assert out["hvns"], "no HVN found where two bins carry 40x the volume"
    assert len(out["hvns"]) < 25, "everything is an HVN — the threshold is not biting"


def test_a_short_frame_returns_nothing_rather_than_a_guess():
    assert vp.profile(_frame([100, 101, 102])) == {}
    assert vp.profile(None) == {}


def test_avwap_bo_anchors_on_the_breakout_and_sits_in_its_range():
    base = [100 + i * 0.1 for i in range(60)]
    prices = base + [120] + [121 + i * 0.1 for i in range(20)]
    vols = [1000] * 60 + [90_000] + [1200] * 20
    a = vp.avwap_bo(_frame(prices, vols))
    assert a is not None, "no breakout anchor found on a 90x-volume new high"
    assert 115 <= a <= 125, a


# ------------------------------------------------------- panel parsing (the fallback)
PANEL = (
    "CHART: NSE:TESTSYM · 75\n"
    "Volume Profile | BELOW VAL (POC 2204.8)\n"
    "S/R (nearest) | S 2163.1 ·D  |   R 2221.7 ·D\n"
    "Divergence · VA | none   ·   POC 2170.0  VAH 2180.0  VAL 2160.0\n"
    "AVWAP | nearest 1703.9  |  L·BO·Gap 1534.5  |  2198.9  |  1703.9\n"
)


def test_panel_parse_takes_one_coherent_profile():
    """S4's row and S5's row are DIFFERENT profiles (POC 2204.8 vs 2170.0). Mixing them
    would put the POC above the VAH, which is impossible by construction."""
    c = _cash_levels(PANEL)
    assert c["poc"] == 2170.0 and c["vah"] == 2180.0 and c["val"] == 2160.0
    assert c["val"] < c["poc"] < c["vah"]
    assert c["sr_below"] == 2163.1 and c["sr_above"] == 2221.7
    assert c["avwap_bo"] == 2198.9, "BO is the MIDDLE anchor of L·BO·Gap"


# ------------------------------------------------------------------ the rules
def test_cash_branch_fires_only_without_options_and_leaves_fno_alone(monkeypatch):
    fno = ("CHART: NSE:FNOSYM · 75\n"
           "Entry · SL · T1 · T2 | E 100.0 | SL 90.0 | T1 130.0 | T2 150.0\n"
           "Options OI | PCR 0.57 · Max pain 120.0 · writers S 95.0 · R 125.0\n")
    monkeypatch.setattr("s4_review.deriv_fields", lambda _t: {
        "entry": "100", "stop": "90", "t1": "130", "t2": "150",
        "call_wall": "125", "put_wall": "95", "max_pain": "120",
        "oi_state": "", "fut_basis_l": "", "pcr": "0.57", "fp_delta": "", "fp_div": ""})
    _, block = level_check(fno)
    assert "CASH PROXY" not in block, "the cash branch fired on an F&O name"
    assert "call wall" in block


def test_cash_output_is_labelled_unvalidated_and_backward_looking(monkeypatch):
    monkeypatch.setattr("s4_review.deriv_fields", lambda _t: {
        "entry": "2173", "stop": "2103.4", "t1": "2381.7", "t2": "2520.8",
        "call_wall": "", "put_wall": "", "max_pain": "",
        "oi_state": "", "fut_basis_l": "", "pcr": "", "fp_delta": "", "fp_div": ""})
    monkeypatch.setattr("volume_profile.structural_levels", lambda *a, **k: {
        "poc": 1785.0, "vah": 2090.0, "val": 1703.0, "hvns": [2067.0, 2186.0],
        "src": "120d daily profile", "avwap_bo": 2148.0})
    _, block = level_check("CHART: NSE:CASHSYM · 75\n")
    assert "CASH PROXY" in block
    # the honesty clauses are the point of the header, not decoration
    assert "BACKWARD-looking" in block and "UNVALIDATED" in block
    assert "never" in block and "GATE" in block


def test_cash_branch_uses_a_near_price_shelf(monkeypatch):
    """Amendment 1, end to end: the floor quoted must be the HVN at 2067, never VAL 1703."""
    monkeypatch.setattr("s4_review.deriv_fields", lambda _t: {
        "entry": "2173", "stop": "2103.4", "t1": "2381.7", "t2": "",
        "call_wall": "", "put_wall": "", "max_pain": "",
        "oi_state": "", "fut_basis_l": "", "pcr": "", "fp_delta": "", "fp_div": ""})
    monkeypatch.setattr("volume_profile.structural_levels", lambda *a, **k: {
        "poc": 1785.0, "vah": 2090.0, "val": 1703.0, "hvns": [2067.0, 2186.0],
        "src": "120d daily profile", "avwap_bo": 2148.0})
    _, block = level_check("CHART: NSE:CASHSYM · 75\n")
    assert "2067" in block, "the near-price shelf is not being used as the floor"
    assert "1703" not in block, "VAL 22% away is being quoted as the floor again"
    assert "HVN 2186" in block, "the ceiling should be the shelf just above entry"
