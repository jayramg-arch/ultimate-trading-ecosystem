"""PA-recency behaviour of the board's S4-GO gate (Jay, 31-Jul-2026).

An NSE session is 5 x 75-min bars, so a pattern that fires at 10:30 is invisible
to a last-bar-only read by 11:45. Since the GM board is where the S4-GO shortlist
is filtered, that name is lost for the day.

These tests pin the SHAPE of the fix, because the obvious version of it is a known
bug: the v5.0 Pine "sticky PA window" was reverted in v5.2 for summing patterns
ACROSS bars (a Sigma describing no real bar) and printing GO while its own gate
chips read fail. So:
  - recency may satisfy the PA gate ALONE (a pattern is a structural event)
  - volume / location / bar-strength stay strictly on the LIVE bar
  - the age is ALWAYS printed; "5/5 GO" stays reserved for a live-bar alignment

Runs under pytest OR as a plain script (pytest is not in the TradingData venv):
    python tests/test_s4go_recency.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gm_trigger_board import s4go_status as _gtb_s4go_status  # noqa: E402

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


LIVE = {"support": {"at_support": True}, "relvol": 1.4, "bar_ok": True}


def ctx(**kw):
    d = dict(LIVE)
    d.update(kw)
    return d


# ── the behaviour that was missing ───────────────────────────────────────────
def test_live_pa_is_unannotated_go():
    assert _status(5, ctx(), True) == "5/5 GO"


def test_recent_pa_is_findable_but_capped_below_four_of_four():
    """Recency keeps the name on the board — it does NOT let it claim a GO.

    24-Aug-2026, Jay: "a discrepancy of 1 or 2 gates is ok, but not 3 out of 4
    failing." S4 has no recency allowance at all; it reads the current bar only.
    So a recency row differs from the chart by the PA gate BY CONSTRUCTION, and
    "5/5" is the one label that promises the chart will agree. Cap it.

    The name still ranks above a genuine 3/4 in practice because the age tag is
    printed and the watch value is intact — what is gone is the false promise."""
    out = _status(0, ctx(pa_recent={"age": 2, "sigma": 5}), True)
    assert out.startswith("4/5"), out
    assert "PA 2b" in out, out
    assert not out.startswith("5/5"), "a 2-bar-old trigger must never read as a GO"


def test_only_a_live_pa_can_reach_four_of_four():
    """The complement, so the cap cannot be quietly widened to everything."""
    assert _status(5, ctx(), True) == "5/5 GO"


def test_without_recency_the_same_name_is_lost():
    """Regression guard — this is the pre-fix behaviour."""
    assert _status(0, ctx(), True) == "4/5 · no PA"  # loc+vol+bar pass; PA is the only miss


def test_age_shown_on_partial_scores_too():
    out = _status(0, ctx(pa_recent={"age": 1, "sigma": 3}, relvol=0.4), True)
    assert out.startswith("4/5") and "PA 1b" in out, out


# ── the v5.2 failure modes that must NOT come back ───────────────────────────
def test_recency_does_not_rescue_volume():
    """Only the PA gate may be satisfied by history. Volume is a bar property."""
    out = _status(0, ctx(pa_recent={"age": 2, "sigma": 5}, relvol=0.3), True)
    assert out.startswith("4/5") and "no vol" in out, out


def test_recency_does_not_rescue_location():
    out = _status(0, ctx(pa_recent={"age": 2, "sigma": 5},
                             support={"at_support": False}), True)
    assert out.startswith("4/5") and "no loc" in out, out


def test_recency_does_not_rescue_a_weak_bar():
    out = _status(0, ctx(pa_recent={"age": 2, "sigma": 5}, bar_ok=False), True)
    assert out.startswith("4/5") and "weak bar" in out, out


def test_live_pa_never_borrows_an_age():
    """A live battery must describe the live bar — recency is not consulted."""
    assert _status(5, ctx(pa_recent={"age": 2, "sigma": 9}), True) == "5/5 GO"


def test_zero_sigma_recency_is_not_a_fire():
    assert _status(0, ctx(pa_recent={"age": 2, "sigma": 0}), True) == "4/5 · no PA"


def test_malformed_recency_is_ignored_not_crashed():
    for bad in (None, {}, "recent", [], {"age": 2}):
        assert _status(0, ctx(pa_recent=bad), True) == "4/5 · no PA", bad


# ── path separation: the two batteries must not cross-feed ───────────────────
# These assert on the STEM plus the absence of the recency token, not on the whole
# cell. What is under test is path separation — one battery's recency must never feed
# the other path — and an exact-equality assertion also pins every DISPLAY suffix, so a
# tag that changes no behaviour (⚠unval, ⚠role, ↑D) reads as a broken contract. It did:
# adding the recovery unvalidated tag failed this file while the separation it guards
# was untouched. Gate semantics stay pinned; cosmetics do not.
def test_recovery_path_reads_the_recovery_recency():
    c = ctx(recovery_pa_recent={"age": 1, "sigma": 4})
    assert "PA 1b" in _status(0, c, True, path="recovery")
    _bull = _status(0, c, True, path="bull")
    assert _bull.startswith("4/5 · no PA") and "PA 1b" not in _bull


def test_bull_path_reads_the_bull_recency():
    c = ctx(pa_recent={"age": 1, "sigma": 4})
    assert "PA 1b" in _status(0, c, True, path="bull")
    _rec = _status(0, c, True, path="recovery")
    assert _rec.startswith("4/5 · no PA") and "PA 1b" not in _rec


def test_default_path_is_bull():
    assert "PA 1b" in _status(0, ctx(pa_recent={"age": 1, "sigma": 4}), True)


# ── unchanged contracts ──────────────────────────────────────────────────────
def test_no_read_still_reports_na():
    assert _status(0, {"support": {"at_support": True}}, False) == "n/a"


if __name__ == "__main__":
    fails = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError as e:
                fails.append(f"{name}: {e or 'assertion failed'}")
    print(f"{len(fails)} failed")
    for f in fails:
        print("  ", f)
    print("PASS" if not fails else "FAIL")
    raise SystemExit(1 if fails else 0)
