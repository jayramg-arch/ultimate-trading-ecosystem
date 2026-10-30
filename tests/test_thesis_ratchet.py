"""The thesis ratchet (30-Oct-2026): raise to S4's Daily INVAL, never lower, never inside 1xATR."""
import thesis_from_s4 as t


def test_raises_when_higher_and_clear_of_the_close():
    assert t.ratchet_decision(2015.9, 2150.0, 2270.0, 50.0) == (2150.0, "raised")


def test_never_lowers():
    new, why = t.ratchet_decision(2015.9, 1980.0, 2270.0, 50.0)
    assert new is None and why.startswith("kept")


def test_tiny_step_ignored():
    new, _ = t.ratchet_decision(2000.0, 2001.0, 2270.0, 50.0)
    assert new is None


def test_inside_one_atr_is_skipped_not_capped():
    new, why = t.ratchet_decision(2015.9, 2240.0, 2270.0, 50.0)
    assert new is None and why.startswith("skipped")


def test_missing_inputs():
    assert t.ratchet_decision(2015.9, None, 2270.0, 50.0)[1] == "no-inval"
    assert t.ratchet_decision(None, 2150.0, 2270.0, 50.0)[1] == "no-thesis"
    assert t.ratchet_decision(2015.9, 2150.0, None, 50.0)[1] == "no-price"
    assert t.ratchet_decision(2015.9, 2150.0, 2270.0, 0)[1] == "no-price"
