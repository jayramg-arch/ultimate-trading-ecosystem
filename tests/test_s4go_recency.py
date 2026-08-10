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
  - the age is ALWAYS printed; "4/4 GO" stays reserved for a live-bar alignment

Runs under pytest OR as a plain script (pytest is not in the TradingData venv):
    python tests/test_s4go_recency.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gm_trigger_board import s4go_status  # noqa: E402

LIVE = {"support": {"at_support": True}, "relvol": 1.4, "bar_ok": True}


def ctx(**kw):
    d = dict(LIVE)
    d.update(kw)
    return d


# ── the behaviour that was missing ───────────────────────────────────────────
def test_live_pa_is_unannotated_go():
    assert s4go_status(5, ctx(), True) == "4/4 GO"


def test_recent_pa_reaches_four_of_four_but_is_labelled():
    """The whole point: this name is findable again, and sorts with the GOs."""
    out = s4go_status(0, ctx(pa_recent={"age": 2, "sigma": 5}), True)
    assert out.startswith("4/4"), out
    assert "PA 2b" in out, out
    assert out != "4/4 GO", "a 2-bar-old trigger must not read as live"


def test_without_recency_the_same_name_is_lost():
    """Regression guard — this is the pre-fix behaviour."""
    assert s4go_status(0, ctx(), True) == "3/4 · no PA"  # loc+vol+bar pass; PA is the only miss


def test_age_shown_on_partial_scores_too():
    out = s4go_status(0, ctx(pa_recent={"age": 1, "sigma": 3}, relvol=0.4), True)
    assert out.startswith("3/4") and "PA 1b" in out, out


# ── the v5.2 failure modes that must NOT come back ───────────────────────────
def test_recency_does_not_rescue_volume():
    """Only the PA gate may be satisfied by history. Volume is a bar property."""
    out = s4go_status(0, ctx(pa_recent={"age": 2, "sigma": 5}, relvol=0.3), True)
    assert out.startswith("3/4") and "no vol" in out, out


def test_recency_does_not_rescue_location():
    out = s4go_status(0, ctx(pa_recent={"age": 2, "sigma": 5},
                             support={"at_support": False}), True)
    assert out.startswith("3/4") and "no loc" in out, out


def test_recency_does_not_rescue_a_weak_bar():
    out = s4go_status(0, ctx(pa_recent={"age": 2, "sigma": 5}, bar_ok=False), True)
    assert out.startswith("3/4") and "weak bar" in out, out


def test_live_pa_never_borrows_an_age():
    """A live battery must describe the live bar — recency is not consulted."""
    assert s4go_status(5, ctx(pa_recent={"age": 2, "sigma": 9}), True) == "4/4 GO"


def test_zero_sigma_recency_is_not_a_fire():
    assert s4go_status(0, ctx(pa_recent={"age": 2, "sigma": 0}), True) == "3/4 · no PA"


def test_malformed_recency_is_ignored_not_crashed():
    for bad in (None, {}, "recent", [], {"age": 2}):
        assert s4go_status(0, ctx(pa_recent=bad), True) == "3/4 · no PA", bad


# ── path separation: the two batteries must not cross-feed ───────────────────
# These assert on the STEM plus the absence of the recency token, not on the whole
# cell. What is under test is path separation — one battery's recency must never feed
# the other path — and an exact-equality assertion also pins every DISPLAY suffix, so a
# tag that changes no behaviour (⚠unval, ⚠role, ↑D) reads as a broken contract. It did:
# adding the recovery unvalidated tag failed this file while the separation it guards
# was untouched. Gate semantics stay pinned; cosmetics do not.
def test_recovery_path_reads_the_recovery_recency():
    c = ctx(recovery_pa_recent={"age": 1, "sigma": 4})
    assert "PA 1b" in s4go_status(0, c, True, path="recovery")
    _bull = s4go_status(0, c, True, path="bull")
    assert _bull.startswith("3/4 · no PA") and "PA 1b" not in _bull


def test_bull_path_reads_the_bull_recency():
    c = ctx(pa_recent={"age": 1, "sigma": 4})
    assert "PA 1b" in s4go_status(0, c, True, path="bull")
    _rec = s4go_status(0, c, True, path="recovery")
    assert _rec.startswith("3/4 · no PA") and "PA 1b" not in _rec


def test_default_path_is_bull():
    assert "PA 1b" in s4go_status(0, ctx(pa_recent={"age": 1, "sigma": 4}), True)


# ── unchanged contracts ──────────────────────────────────────────────────────
def test_no_read_still_reports_na():
    assert s4go_status(0, {"support": {"at_support": True}}, False) == "n/a"


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
