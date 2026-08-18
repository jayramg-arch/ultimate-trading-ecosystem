"""Gate 5 (R) - the RRG "BUY OK" veto on the Trigger Board.

Guards the two ways this gate dies quietly:
  1. it stops vetoing (a CSV round-trip turns False into the string "False"),
  2. it starts vetoing on ABSENT data (an unknown must never read as a verdict).
"""
import gm_trigger_board as gtb


def _ctx(rv=1.4, bar=True, sup=True):
    return {"relvol": rv, "bar_ok": bar, "support": {"at_support": sup}}


def test_unknown_fails_open():
    """None/blank/nan = could not compute -> must NOT veto (the ICICIAMC lesson)."""
    for v in (None, "", "nan", "none", "-", "—", "n/a"):
        assert gtb._rrg_ok(v) is True, v


def test_csv_roundtrip_strings_still_veto():
    """to_csv/read_csv turns the bool into text; a text 'False' must still block."""
    for v in (False, "False", "false", "0", "✗ WAIT"):
        assert gtb._rrg_ok(v) is False, v
    for v in (True, "True", "1", "✓ BUY OK"):
        assert gtb._rrg_ok(v) is True, v


def test_veto_blocks_a_clean_four_of_four():
    assert gtb.s4go_status(4, _ctx(), True, "bull", rrg_tradeable=True) == "4/4 GO"
    out = gtb.s4go_status(4, _ctx(), True, "bull", rrg_tradeable=False)
    assert out.startswith("⛔ RRG WAIT") and "4/4" in out


def test_veto_does_not_mask_a_real_gate_failure():
    """The gate count is still reported, so a blocked row stays diagnosable."""
    out = gtb.s4go_status(4, _ctx(rv=0.4), True, "bull", rrg_tradeable=False)
    assert "3/4" in out


def test_stage_veto_outranks_rrg():
    out = gtb.s4go_status(4, _ctx(), True, "bull", stage="Stage 3", rrg_tradeable=False)
    assert out.startswith("⛔ Stage 3")


def test_legacy_callers_unaffected():
    """Any call site that never passes rrg_tradeable keeps its old behaviour."""
    assert gtb.s4go_status(4, _ctx(), True, "bull") == "4/4 GO"


def test_gate_can_be_disabled():
    orig = gtb.RRG_GATE
    try:
        gtb.RRG_GATE = False
        assert gtb._rrg_ok(False) is True
    finally:
        gtb.RRG_GATE = orig
