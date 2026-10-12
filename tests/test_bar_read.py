"""Latest-bar read (12-Oct-2026): weak / neutral / strong on the last closed trigger bar.
Board Bar column + Commander_Addons_v1.0.pine (M1) + H2 of the rejection pre-registration."""
import os
import re

import numpy as np
import pandas as pd

import gm_trigger_board as gtb
import rejection_test as rt

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_green_bar_with_long_top_wick_is_weak():
    # o 100, c 102 (green), h 110, l 99: top wick 8/11 = 73%
    g, cpos, wick = gtb.bar_grade(100, 110, 99, 102)
    assert g == "weak" and wick > 0.5


def test_close_in_lower_third_is_weak():
    assert gtb.bar_grade(105, 106, 100, 101)[0] == "weak"


def test_strong_and_neutral():
    assert gtb.bar_grade(100, 105, 99, 104.5)[0] == "strong"      # close 92%, wick 8%
    assert gtb.bar_grade(100, 106, 99, 103)[0] == "neutral"       # close 57%, wick 43%


def test_zero_range_or_missing_is_blank():
    assert gtb.bar_grade(100, 100, 100, 100) is None
    assert gtb.bar_read({}) == ""
    assert gtb.bar_read({"bar": {"o": 100, "h": 110, "l": 99, "c": 102}}) == "Weak.C:27%.TW:73%"


def test_pa_bar_shown_beside_the_latest_bar():
    # PA fired 2 bars back on a weak bar; the latest closed bar is strong
    ctx = {"bar": {"o": 100, "h": 105, "l": 99, "c": 104.5},
           "pa_recent": {"age": 2, "sigma": 3, "bar": {"o": 100, "h": 110, "l": 99, "c": 102}}}
    assert gtb.bar_read(ctx) == "now Strong.C:92%.TW:8% · PA 2b Weak.C:27%.TW:73%"
    # the recovery path reads its own recency record, not the bull one
    assert gtb.bar_read(ctx, "recovery") == "Strong.C:92%.TW:8%"
    # PA on the latest bar (no recency record): one grade only
    assert gtb.bar_read({"bar": ctx["bar"]}) == "Strong.C:92%.TW:8%"


def test_pine_constants_match_python():
    src = open(os.path.join(HERE, "Commander_Addons_v1.0.pine"), encoding="utf-8").read()
    want = {"WEAK_CLOSE_POS": gtb.BAR_WEAK_CLOSE_POS, "WEAK_TOP_WICK": gtb.BAR_WEAK_TOP_WICK,
            "STRONG_CLOSE_POS": gtb.BAR_STRONG_CLOSE_POS, "STRONG_TOP_WICK": gtb.BAR_STRONG_TOP_WICK}
    for name, val in want.items():
        m = re.search(r"^%s\s*=\s*([0-9./ ]+)$" % name, src, re.M)
        assert m, name
        assert abs(eval(m.group(1)) - val) < 1e-12, name       # simple arithmetic literal only


def test_scorer_counts_h2_and_refuses_below_threshold(tmp_path, monkeypatch, capsys):
    rows = []
    for i in range(10):
        weak = i % 2 == 0
        rows.append({"logged": "2026-10-13 10:35", "tf": "75m", "symbol": "S%d" % i, "bar_ts": "2026-10-13",
                     "plan": "positional", "s4go": "5/5 GO", "rej": 0, "rej_level": "",
                     "o": 100, "h": 110 if weak else 105, "l": 99, "c": 102 if weak else 104.5,
                     "entry": 102, "sl": 95})
    rows.append(dict(rows[0], logged="2026-10-12 12:00", symbol="OLD"))     # before registration
    p = tmp_path / "ledger.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    monkeypatch.setattr(rt, "LEDGER", str(p))
    monkeypatch.setattr(rt, "outcome", lambda r, n: 1.0)
    monkeypatch.setattr("sys.argv", ["rejection_test.py", "--run"])
    assert rt.main() == 1                                       # 5 + 5 is below 30 + 30
    out = capsys.readouterr().out
    assert "ledger rows after registration: 10" in out and "H2 weak   5 · not-weak   5" in out
    assert np.isnan(rt._weak({"o": 1, "h": 1, "l": 1, "c": 1}))
