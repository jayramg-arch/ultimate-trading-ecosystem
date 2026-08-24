"""The breakout/pullback playbook split (5-Aug-2026).

The bug being pinned: S4 and the board graded the same candle against two different
setups' standards because neither knew which setup it was. A breakout must expand on
heavy volume and close strong; a pullback enters on volume dry-up with a bar that only
holds the zone. One gate cannot be neutral between them.

Each test below has been checked to go RED when the relevant change is reverted — a test
that passes under the old code would pin nothing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gm_trigger_board import (_pullback_ctx, s4go_status, s4_pullback_list,
                              PULLBACK_ARCHETYPES, BREAKOUT_ARCHETYPES)


def ctx(patterns, at_support=True, relvol=0.6, bar_ok=False, zone=True):
    return {
        "pa_patterns": [(n, True, 2, "") for n in patterns],
        "support": {"at_support": at_support, "in_fresh_dz": zone},
        "relvol": relvol, "bar_ok": bar_ok,
    }


# ── the hole the archetype handoff closes ────────────────────────────────────
def test_strong_close_reversal_loses_pullback_treatment_by_inference():
    """A reversal bar off a demand zone that CLOSES STRONG fires the Strong-Close
    pattern, which counts as expansion — so the textbook pullback entry disqualified
    itself from pullback treatment. This is the inference's blind spot."""
    c = ctx(["Hammer at 50-SMA", "Power Play (Strong Close)"])
    assert _pullback_ctx(c, "bull") is False


def test_known_archetype_overrides_that_inference():
    c = ctx(["Hammer at 50-SMA", "Power Play (Strong Close)"])
    assert _pullback_ctx(c, "bull", archetypes=["Pullback"]) is True


def test_known_pullback_flips_the_volume_gate_ONLY():
    """RV 0.6 fails the breakout floor (1.0) and passes the pullback floor (0.5),
    so knowing the setup is worth exactly ONE gate.

    It used to be worth two: the bar gate returned a free True on every pullback
    row, on the reasoning that a pullback bar only has to HOLD the zone. But
    "still in the zone" is g_loc — the gate was counting one fact twice, so the
    board could not disagree with itself. S4:3660 tests a real bar
    (close > distal or close >= open); ctx has no distal, so the board mirrors the
    bar-strength read it does have. Removed 24-Aug-2026: 13 of 16 4/4 rows on the
    125m board were taking this pass, and it was one of the two faults behind
    board 4/4 vs S4 1/4."""
    c = ctx(["Hammer at 50-SMA", "Power Play (Strong Close)"])
    assert s4go_status(4, c, True, "bull").startswith("2/4")
    _known = s4go_status(4, c, True, "bull", archetypes=["Pullback"])
    assert _known.startswith("3/4"), _known
    assert "weak bar" in _known, "the weak bar must still be NAMED, not absorbed"


def test_a_pullback_with_a_clean_bar_does_reach_four_of_four():
    """The complement: the volume relaxation is intact, only the freebie is gone."""
    c = ctx(["Hammer at 50-SMA", "Power Play (Strong Close)"], bar_ok=True)
    assert s4go_status(4, c, True, "bull", archetypes=["Pullback"]).startswith("4/4")


# ── the discipline that is NOT relaxed ───────────────────────────────────────
def test_known_pullback_still_requires_a_demand_zone():
    """The zone requirement is what keeps the lower volume floor honest — without it
    the relaxation would apply to any random quiet bar."""
    c = ctx(["Hammer at 50-SMA"], zone=False)
    c["support"] = {"at_support": True}          # at a location, but no demand zone
    assert _pullback_ctx(c, "bull", archetypes=["Pullback"]) is False


def test_breakout_archetype_excludes_a_name_from_the_pullback_branch():
    """A name on BOTH screens is genuinely ambiguous; the breakout claim wins here and
    the pattern inference is left to tie-break, rather than a coin-flip."""
    c = ctx(["Hammer at 50-SMA", "Power Play (Strong Close)"])
    assert _pullback_ctx(c, "bull", archetypes=["Pullback", "Breakout"]) is False


def test_recovery_path_is_untouched():
    """The recovery battery is a different set entirely — the split must not reach it."""
    c = ctx(["Hammer at 50-SMA"])
    assert _pullback_ctx(c, "recovery", archetypes=["Pullback"]) is False


def test_inference_still_works_without_any_archetype():
    """S4 runs standalone on charts and the board carries catalyst-scan names with no
    setup archetype. Neither may lose pullback detection."""
    assert _pullback_ctx(ctx(["True NR7", "Pocket Pivot"]), "bull") is True


# ── the handoff itself ───────────────────────────────────────────────────────
def test_pullback_list_selects_pullback_only_names():
    uni = {
        "AAA": {"archetypes": ["Pullback"]},
        "BBB": {"archetypes": ["Pullback", "Breakout"]},   # ambiguous -> excluded
        "CCC": {"archetypes": ["Breakout"]},
        "DDD": {"archetypes": ["Pyramid"]},                # ADD = pullback location
        "EEE": {"archetypes": []},
    }
    assert s4_pullback_list(uni) == "AAA,DDD"


def test_archetype_sets_do_not_overlap():
    """An archetype in both sets would make the exclusion self-cancelling."""
    assert not (PULLBACK_ARCHETYPES & BREAKOUT_ARCHETYPES)
