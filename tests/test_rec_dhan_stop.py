"""3x-ATR Dhan stop (12-Oct-2026, Jay): recommended resting stop + same-risk qty, carried to
v67 as the 5th Chandelier-book field."""
import house_policy as hp
import tv_push_v67_trail as t


def test_close_stop_gets_a_wider_level_and_same_risk_qty():
    # LTP 2428, ATR 116.1, stop 2305.5 (1.06 ATR) -> 2079.7; risk 122.5 x 66 = 8085 -> 23 sh
    rec, keep = hp.rec_dhan_stop(2428.0, 2305.5, 116.1, 66)
    assert abs(rec - (2428.0 - 3 * 116.1)) < 1e-9 and keep == 23


def test_far_stop_and_rounding_are_left_alone():
    assert hp.rec_dhan_stop(2041.5, 1722.5, 46.8, 58) is None            # 6.8 ATR away
    assert hp.rec_dhan_stop(790.2, 718.5, 23.9, 258) is None             # 0.1 inside the line


def test_missing_inputs_never_guess():
    assert hp.rec_dhan_stop(None, 100, 5, 10) is None
    assert hp.rec_dhan_stop(100, 90, 0, 10) is None
    assert hp.rec_dhan_stop(100, 0, 5, 10) == (85.0, None)               # no stop: level only


def test_book_field_is_positional_after_an_empty_thesis():
    rows = [{"symbol": "ABC", "window": 22, "mult": 5.0, "override": None, "anchored": False,
             "level": 90.0, "thesis": None, "stoploss": 95.0, "rec": "R85.00:6:x"},
            {"symbol": "XYZ", "window": 14, "mult": 2.0, "override": None, "anchored": False,
             "level": 90.0, "thesis": 99.0, "stoploss": 95.0, "rec": ""}]
    book = t.book_string(rows)
    assert "ABC=22,5.0000,0,T,R85.00:6:x" in book
    assert "XYZ=14,2.0000,0,T99.00" in book and "XYZ=14,2.0000,0,T99.00," not in book
