"""Rejection at the level (12-Oct-2026): the trigger bar probed a level that passed location
and closed back above it, upper half. Display-only board mark + the pre-registered test."""
from gm_trigger_board import rejection_read


def _ctx(o, h, l, c, levels):
    return {"bar": {"o": o, "h": h, "l": l, "c": c, "ts": "x"}, "support": {"loc_levels": levels}}


def test_probe_and_close_back_above_is_a_rejection():
    ok, txt, lv = rejection_read(_ctx(101, 104, 98, 103.5, [(100.0, "zone D")]))
    assert ok and lv == 100.0 and "zone D" in txt


def test_low_a_little_short_of_the_level_still_counts():
    # range 6, tol 10% = 0.6: low 100.4 counts for a level at 100
    assert rejection_read(_ctx(101, 106, 100.4, 105, [(100.0, "S/R D")]))[0]


def test_never_reached_the_level_is_not():
    assert not rejection_read(_ctx(103, 106, 102, 105, [(100.0, "zone D")]))[0]


def test_closed_below_the_level_is_not():
    assert not rejection_read(_ctx(101, 102, 97, 99.5, [(100.0, "zone D")]))[0]


def test_weak_close_is_not():
    # touched and closed above the level, but in the lower half of the bar
    assert not rejection_read(_ctx(103, 108, 99, 101, [(100.0, "zone D")]))[0]


def test_unknown_bar_or_no_levels_is_blank_not_a_guess():
    assert rejection_read({}) == (False, "", None)
    assert rejection_read(_ctx(101, 104, 98, 103.5, [])) == (False, "", None)
