"""Paper trades (13-Oct-2026): every TAKE taken on paper and walked to thesis / hard SL /
T1 / T2. These pin the scoring rules the page states."""
import pandas as pd

import paper_trades as pt


def _bars(rows):
    idx = pd.date_range("2026-10-01", periods=len(rows), freq="D")
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"], index=idx)


def test_ruling_word_reads_every_logged_spelling():
    for s in ("RULING: TAKE", "**RULING:** TAKE · REDUCED", "RULING**: TAKE", "TAKE"):
        assert pt._ruling_word(s) == "TAKE"
    assert pt._ruling_word("RULING: WAIT for a close above 916") == "WAIT"


def test_hard_sl_is_scored_before_a_target_on_the_same_bar():
    # fill bar 0 at 100, stop 95, T1 110: bar 1 trades 94-111 -> stop first, -1R
    df = _bars([[100, 101, 99, 100], [100, 111, 94, 105]])
    ev, r, done = pt._walk(df, 0, 100.0, 95.0, 110.0, 120.0, None, True, 0.25, 0.25)
    assert done and ev["exit"] == "hard SL" and r == -1.0 and ev["t1_hit"] == ""


def test_thesis_exits_only_on_a_close_below_it():
    # thesis 98 above stop 95: bar 1 wicks to 96 but closes 99 (no exit); bar 2 closes 97 -> exit
    df = _bars([[100, 101, 99, 100], [100, 101, 96, 99], [99, 100, 96.5, 97]])
    ev, r, done = pt._walk(df, 0, 100.0, 95.0, 110.0, 120.0, 98.0, True, 0.25, 0.25)
    assert done and ev["exit"] == "thesis" and abs(r - (-0.6)) < 1e-9
    # hard-only policy ignores the thesis and is still open
    ev, r, done = pt._walk(df, 0, 100.0, 95.0, 110.0, 120.0, 98.0, False, 0.25, 0.25)
    assert not done and ev["exit"] == "open"


def test_partials_book_at_t1_and_t2_then_the_rest_marks_to_close():
    # R = 5: T1 110 (2R), T2 120 (4R); last close 115 (3R) for the remaining 50%
    df = _bars([[100, 101, 99, 100], [100, 111, 99, 108], [108, 121, 107, 115]])
    ev, r, done = pt._walk(df, 0, 100.0, 95.0, 110.0, 120.0, None, True, 0.25, 0.25)
    assert not done and ev["t1_hit"] and ev["t2_hit"]
    assert abs(r - (0.25 * 2 + 0.25 * 4 + 0.5 * 3)) < 1e-9


def test_missing_targets_take_the_house_canon():
    lv = {"entry": 100.0, "stop": 90.0, "t1": None, "t2": None, "type": "positional", "src": "review"}
    pt._canon_fill(lv)
    assert (lv["t1"], lv["t2"]) == (130.0, 150.0) and "canon" in lv["src"]
    lv = {"entry": 100.0, "stop": 95.0, "t1": None, "t2": None, "type": "swing", "src": ""}
    pt._canon_fill(lv)
    assert (lv["t1"], lv["t2"]) == (110.0, 120.0)
