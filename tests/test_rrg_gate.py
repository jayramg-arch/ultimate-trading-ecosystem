"""Gate 5 (R) - the RRG "BUY OK" signal on the Trigger Board.

STATE (18-Aug-2026): DISPLAY-ONLY. The veto is off because the re-measure found the
whitelist worth +0.12pp (4w) / +0.00pp (12w) once the cells were recomputed on the RRG
Studio calibration - IMPROVING->LEADING is reliably negative and cancels what
LEADING->LEADING earns. Jay eyeballs LEADING->LEADING and WEAKENING->LEADING instead.

These tests pin the three ways this can rot:
  1. the display tag disappears when the veto is off (then there is nothing to eyeball),
  2. an unknown starts reading as a verdict,
  3. the veto path breaks while nobody is using it, so re-enabling it silently fails.
"""
import gm_trigger_board as gtb
import pytest


def _ctx(rv=1.4, bar=True, sup=True):
    return {"relvol": rv, "bar_ok": bar, "support": {"at_support": sup}}


@pytest.fixture
def veto_on():
    orig = gtb.RRG_GATE
    gtb.RRG_GATE = True
    yield
    gtb.RRG_GATE = orig


# --- default state: display only ------------------------------------------------
def test_veto_is_off_by_default():
    assert gtb.RRG_GATE is False


def test_not_tradeable_still_reaches_go_but_is_TAGGED():
    """The whole point of display-only: the name trades, and you can still see the flag."""
    out = gtb.s4go_status(4, _ctx(), True, "bull", rrg_tradeable=False)
    assert out.startswith("4/4 GO") and "RRG·" in out


def test_tradeable_is_not_tagged():
    assert "RRG·" not in gtb.s4go_status(4, _ctx(), True, "bull", rrg_tradeable=True)


def test_tag_survives_alongside_a_real_gate_failure():
    out = gtb.s4go_status(4, _ctx(rv=0.4), True, "bull", rrg_tradeable=False)
    assert "3/4" in out and "RRG·" in out


# --- unknown must never become a verdict ----------------------------------------
def test_unknown_is_neither_vetoed_nor_tagged():
    for v in (None, "", "nan", "none", "-", "—", "n/a"):
        out = gtb.s4go_status(4, _ctx(), True, "bull", rrg_tradeable=v)
        assert out == "4/4 GO", (v, out)


def test_csv_roundtrip_strings_are_still_understood():
    """to_csv/read_csv turns the bool into text; the coercion must survive it."""
    for v in (False, "False", "false", "0", "✗ WAIT"):
        assert gtb._rrg_ok_raw(v) is False, v
    for v in (True, "True", "1", "✓ BUY OK"):
        assert gtb._rrg_ok_raw(v) is True, v


# --- the veto path must still work if it is ever switched back on ---------------
def test_veto_blocks_when_re_enabled(veto_on):
    out = gtb.s4go_status(4, _ctx(), True, "bull", rrg_tradeable=False)
    assert out.startswith("⛔ RRG WAIT") and "4/4" in out


def test_veto_does_not_fire_on_unknown_when_re_enabled(veto_on):
    assert gtb.s4go_status(4, _ctx(), True, "bull", rrg_tradeable=None) == "4/4 GO"


def test_stage_veto_outranks_rrg(veto_on):
    out = gtb.s4go_status(4, _ctx(), True, "bull", stage="Stage 3", rrg_tradeable=False)
    assert out.startswith("⛔ Stage 3")


def test_legacy_callers_unaffected():
    assert gtb.s4go_status(4, _ctx(), True, "bull") == "4/4 GO"
