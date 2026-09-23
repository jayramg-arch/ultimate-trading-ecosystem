"""REV-03 / REV-04: a failed review must say why, and a withheld S5 section must be
named to the model rather than left to its imagination.

WHY (23-Sep-2026 audit of that day's 35 alerts):
  REV-03  BAJAJ_AUTO 125 logged `review rc 1` and nothing else — no .md, no Reviewer
          Log row, no reason. The reason existed (review_one prints it to stderr) but
          stderr goes to the receiver console, which does not persist.
  REV-04  CPPLUS 125 wrote "S5 confirms ... the geometry is clean" on a read whose
          I · GEOMETRY was withheld. SYSTEM already said "do not guess them"; a rule
          that names nothing is easy to read past.
"""
import io

import s4_review
from s4_review import build_prompt
from s4_alert_review import _err_tail


# --------------------------------------------------------------------- REV-03
def test_err_tail_recovers_the_reason_a_review_failed():
    buf = io.StringIO()
    buf.write("some warning\n\n")
    buf.write("S4 is not on this chart (tables found: ['Volume']). Add it and re-run.\n")
    out = _err_tail(buf)
    assert "S4 is not on this chart" in out
    assert "\n" not in out, "must flatten onto one log line"


def test_err_tail_keeps_only_the_tail_and_is_bounded():
    buf = io.StringIO()
    for i in range(50):
        buf.write("line %d\n" % i)
    out = _err_tail(buf, n=3)
    assert out == "line 47 | line 48 | line 49"
    assert len(_err_tail(io.StringIO("x" * 5000), n=3)) <= 400


def test_err_tail_is_silent_when_stderr_was_empty():
    assert _err_tail(io.StringIO("")) == ""
    assert _err_tail(io.StringIO("\n  \n")) == ""


def test_the_failure_branch_reports_the_reason(monkeypatch):
    """rc != 0 must put the stderr tail in the log line, not just the code."""
    import sys
    import s4_alert_review as ar

    def fake_review(sr, symbol, tf):
        print("S4 is not on this chart (tables found: []). Add it and re-run.",
              file=sys.stderr)
        return {"rc": 1, "review": "", "path": ""}

    # _run's finally block rebuilds the REAL Reviewer Log page. Caught on the first
    # run of this test, which rewrote docs/portal/31_reviewer_log_v2.html — the class
    # of side effect tests/conftest.py exists to prevent.
    import build_review_portal
    monkeypatch.setattr(build_review_portal, "build", lambda *a, **k: None)

    logged = []
    monkeypatch.setattr(ar, "_review_with_retry", fake_review)
    monkeypatch.setattr(ar, "_log", lambda m: logged.append(m))
    monkeypatch.setattr(ar, "_status", lambda *a, **k: None)
    monkeypatch.setattr(ar, "RESTORE", False)
    monkeypatch.setattr(s4_review, "telegram", lambda *a, **k: True)

    ar._run("BAJAJ_AUTO", "125", "test")

    fail = [m for m in logged if "rc 1" in m]
    assert fail, "no rc line logged at all: %r" % logged
    assert "S4 is not on this chart" in fail[0], \
        "rc logged without the reason — the REV-03 bug is back: %r" % fail[0]


# --------------------------------------------------------------------- REV-04
WITHHELD_READ = """======== S5 Analysis Panel v1.5 ========
I · GEOMETRY — [withheld: not yet fine-tuned]
II · LEVELS — [withheld: not yet fine-tuned]
III · PARTICIPATION     —  Who is actually trading it?
Order flow | +103 buyers
VI · READ — [withheld: not yet fine-tuned]
"""


def test_prompt_names_the_withheld_sections():
    p = build_prompt(WITHHELD_READ, "no position")
    assert "S5 SECTIONS WITHHELD ON THIS READ" in p
    for sec in ("I · GEOMETRY", "II · LEVELS", "VI · READ"):
        assert sec in p.split("S5 SECTIONS WITHHELD ON THIS READ")[1].splitlines()[0], \
            "%s not named" % sec


def test_it_forbids_the_exact_phrasing_that_slipped_through():
    p = build_prompt(WITHHELD_READ, "no position")
    assert "not even to" in p and "clean" in p, \
        "the 'do not call it clean' clause is what CPPLUS 125 walked past"


def test_nothing_is_claimed_when_nothing_is_withheld():
    p = build_prompt("======== S5 ========\nIII · PARTICIPATION — all present\n", "x")
    assert "WITHHELD ON THIS READ" not in p
