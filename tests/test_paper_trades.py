"""Paper trades (13-Oct-2026): every TAKE taken the way Jay trades it - Risk Allocator
quantity, OCO-1 at T1, OCO-2 at T2, a stop-only runner, thesis close / hard SL / house
trail. These pin the scoring rules the page states."""
import pandas as pd

import paper_trades as pt


def _bars(rows):
    idx = pd.date_range("2026-10-01", periods=len(rows), freq="D")
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"], index=idx)


def test_ruling_word_reads_every_logged_spelling():
    for s in ("RULING: TAKE", "**RULING:** TAKE · REDUCED", "RULING**: TAKE", "TAKE"):
        assert pt._ruling_word(s) == "TAKE"
    assert pt._ruling_word("RULING: WAIT for a close above 916") == "WAIT"


def test_allocator_legs_and_minimum_one_share():
    assert pt.legs(40, "positional") == (10, 10, 20)      # 25 / 25 / runner
    assert pt.legs(30, "swing") == (9, 9, 12)             # 33 / 33 / runner
    assert pt.legs(3, "positional") == (1, 1, 1)          # Allocator v2.6: no empty leg


def test_hard_sl_before_target_on_a_two_way_bar_in_rupees():
    df = _bars([[100, 101, 99, 100], [100, 111, 94, 105]])
    s = pt.simulate(df, 0, 100.0, 95.0, 110.0, 120.0, None, True, 10, 10, 20)
    assert s["exit"] == "hard SL" and s["total"] == 40 * (95 - 100) and s["R"] == -1.0
    assert s["oco1"] == "stopped" and s["runner"] == "stopped"


def test_thesis_close_exits_every_remaining_leg():
    # thesis 98 above stop 95: bar 1 wicks to 96, closes 99 (no exit); bar 2 closes 97 -> exit all
    df = _bars([[100, 101, 99, 100], [100, 101, 96, 99], [99, 100, 96.5, 97]])
    s = pt.simulate(df, 0, 100.0, 95.0, 110.0, 120.0, 98.0, True, 10, 10, 20)
    assert s["exit"] == "thesis" and s["total"] == 40 * (97 - 100)
    h = pt.simulate(df, 0, 100.0, 95.0, 110.0, 120.0, 98.0, False, 10, 10, 20)
    assert h["exit"] == "open"                            # hard-SL-only policy is still in


def test_targets_book_their_oco_and_the_runner_marks_to_close():
    df = _bars([[100, 101, 99, 100], [100, 111, 99, 108], [108, 121, 107, 115]])
    s = pt.simulate(df, 0, 100.0, 95.0, 110.0, 120.0, None, True, 10, 10, 20)
    assert s["oco1"] == "T1 booked" and s["oco2"] == "T2 booked" and s["runner"] == "open"
    assert s["realised"] == 10 * 10 + 10 * 20 and s["unrealised"] == 20 * 15


def test_trail_is_tighten_only_and_closes_the_runner():
    # a steady rise, then a drop: the 2-bar / 1x trail climbs and takes the runner out
    df = _bars([[100, 101, 99, 100], [100, 106, 100, 105], [105, 111, 104, 110],
                [110, 116, 109, 115], [115, 115, 101, 102]])
    s = pt.simulate(df, 0, 100.0, 90.0, None, None, None, True, 0, 0, 10, trail=(2, 1.0))
    assert s["exit"] == "trail SL" and s["total"] > 0 and s["trail_stop"] > 90.0


def test_inr_uses_indian_grouping():
    assert pt.inr(123456) == "₹1,23,456" and pt.inr(-2982) == "-₹2,982" and pt.inr(None) == "—"


def test_missing_targets_take_the_house_canon():
    lv = {"entry": 100.0, "stop": 90.0, "t1": None, "t2": None, "type": "positional", "src": "review"}
    pt._canon_fill(lv)
    assert (lv["t1"], lv["t2"]) == (130.0, 150.0) and "canon" in lv["src"]
