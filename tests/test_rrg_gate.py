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
from gm_trigger_board import s4go_status as _gtb_s4go_status
import pytest

# ---- GATE COUNT (updated 10-Sep-2026) ---------------------------------------
# s4go_status counted FOUR gates when these tests were written. A FIFTH -
# fundamentals - was added on 2-Sep-2026 (gm_trigger_board:1226). It had always
# been APPLIED; it simply was not COUNTED, so the board read "four of four" where
# the chart showed five chips and an UNSCORED name looked identical to a verified
# one. The code is right; these expectations were stale.
#
# These tests are about PA recency / the RRG tag / the playbook split, so the
# fundamental gate is held PASSING and kept out of the way. Without that, every
# assertion here would also carry an unrelated " . F?" tag (fund_ok=None passes
# but annotates), which is noise in tests that are not about fundamentals.
def _status(*a, **kw):
    """s4go_status with fundamentals pinned PASS, so these tests isolate the
    technical gates. Pass fund_ok explicitly to override."""
    kw.setdefault("fund_ok", True)
    return _gtb_s4go_status(*a, **kw)



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
    out = _status(4, _ctx(), True, "bull", rrg_tradeable=False)
    assert out.startswith("5/5 GO") and "RRG·" in out


def test_tradeable_is_not_tagged():
    assert "RRG·" not in _status(4, _ctx(), True, "bull", rrg_tradeable=True)


def test_tag_survives_alongside_a_real_gate_failure():
    out = _status(4, _ctx(rv=0.4), True, "bull", rrg_tradeable=False)
    assert "4/5" in out and "RRG·" in out


# --- unknown must never become a verdict ----------------------------------------
def test_unknown_is_neither_vetoed_nor_tagged():
    for v in (None, "", "nan", "none", "-", "—", "n/a"):
        out = _status(4, _ctx(), True, "bull", rrg_tradeable=v)
        assert out == "5/5 GO", (v, out)


def test_csv_roundtrip_strings_are_still_understood():
    """to_csv/read_csv turns the bool into text; the coercion must survive it."""
    for v in (False, "False", "false", "0", "✗ WAIT"):
        assert gtb._rrg_ok_raw(v) is False, v
    for v in (True, "True", "1", "✓ BUY OK"):
        assert gtb._rrg_ok_raw(v) is True, v


# --- the veto path must still work if it is ever switched back on ---------------
def test_veto_blocks_when_re_enabled(veto_on):
    out = _status(4, _ctx(), True, "bull", rrg_tradeable=False)
    assert out.startswith("⛔ RRG WAIT") and "5/5" in out


def test_veto_does_not_fire_on_unknown_when_re_enabled(veto_on):
    assert _status(4, _ctx(), True, "bull", rrg_tradeable=None) == "5/5 GO"


def test_stage_veto_outranks_rrg(veto_on):
    out = _status(4, _ctx(), True, "bull", stage="Stage 3", rrg_tradeable=False)
    assert out.startswith("⛔ Stage 3")


def test_legacy_callers_unaffected():
    assert _status(4, _ctx(), True, "bull") == "5/5 GO"


# ── GATE 6 (F) — the fundamental floor ───────────────────────────────────────
# Added 10-Sep-2026. The fifth gate went in on 2-Sep and NOTHING covered its
# behaviour: the 22 tests it broke all failed on the SCORE STRING ("4/4" vs
# "5/5"), not on what the gate does. A tri-state gate with no test is how the
# next silent change gets through, so this pins the contract itself.
def test_fund_gate_is_tri_state():
    """True passes clean · None passes but ANNOTATES · False fails.

    The annotation is the point of the None branch: an unscored name must stay
    distinguishable from a verified one, which is exactly what counting F fixed.
    """
    ok = _status(4, _ctx(), True, "bull", fund_ok=True)
    unknown = gtb.s4go_status(4, _ctx(), True, "bull", fund_ok=None)
    bad = gtb.s4go_status(4, _ctx(), True, "bull", fund_ok=False)

    assert ok.startswith("5/5 GO") and "F?" not in ok
    assert unknown.startswith("5/5 GO") and "F?" in unknown      # passes, but flagged
    assert not bad.startswith("5/5")                             # one gate short


def test_fund_false_costs_exactly_one_gate():
    """A failing fundamental floor must remove ONE gate, not silently pass and not
    collapse the whole score — the difference between a floor and a veto."""
    ok = gtb.s4go_status(4, _ctx(), True, "bull", fund_ok=True)
    bad = gtb.s4go_status(4, _ctx(), True, "bull", fund_ok=False)
    assert ok.split("/")[0] == "5" and bad.split("/")[0] == "4"
    assert ok.split("/")[1].split()[0] == bad.split("/")[1].split()[0] == "5"
