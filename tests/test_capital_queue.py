"""Capital queue (25-Sep-2026): the pieces that would break silently."""
import capital_queue as cq


def test_inr_indian_grouping():
    assert cq.inr(824460.6) == "₹8,24,461"
    assert cq.inr(12345678) == "₹1,23,45,678"
    assert cq.inr(999) == "₹999"
    assert cq.inr(-45001) == "-₹45,001"
    assert cq.inr(float("nan")) == "—"


def test_location_ladder_matches_the_reviewer():
    # at or reacting off a pattern zone = zone
    assert cq._loc_class("AT pattern 75m") == "zone"
    assert cq._loc_class("REACTING off pattern D · below EMA") == "zone"
    # a pivot shelf with confluence = a level, not a zone
    assert cq._loc_class("AT pivot+conf · below EMA") == "level"
    # approaching a zone is not being at it
    assert cq._loc_class("−2.3% → pattern D") == "weak"
    # nothing, or AVWAP/EMA only
    assert cq._loc_class("") == "weak"
    assert cq._loc_class("near EMA20") == "weak"


def test_live_means_go_or_trigger_live():
    assert cq._is_live({"S4-GO": "5/5 GO · PB", "Category": "Armed Wait · Bull"})
    assert cq._is_live({"S4-GO": "4/5 · no vol", "Category": "Buy Trigger Live · Bull"})
    assert not cq._is_live({"S4-GO": "4/5 · no loc", "Category": "Armed Wait · Bull"})
