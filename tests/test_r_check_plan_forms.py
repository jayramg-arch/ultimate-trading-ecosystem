"""R-CHECK must parse a PLAN regardless of how the model laid it out.

WHY THIS EXISTS (23-Sep-2026). `r_check` guarded its entry branch with
`"stop:" not in low`, so any plan written on ONE line with entry and stop together
never yielded an entry and the check printed "could not parse" instead of running.
It was silent: 16 of that day's 34 reviews went out unverified, and three of them
carried real R mis-statements — MOCAPITAL's T1 was labelled 3R and was 7.37R,
ANANDRATHI's T1 was labelled 2R and was 1.00R.

The plans below are VERBATIM from those reviews. A failure here means plans are
going to Telegram with their arithmetic unchecked, which is the one job this
function has.
"""
import re
import pytest

from s4_review import r_check

RAN = "R-CHECK (recomputed)"


def plan(line: str) -> str:
    return "**PLAN**\n" + line + "\n\n**FLIPS IF**\nnothing\n"


def parsed(out: str):
    """-> (entry, stop) the check actually recovered, or None if it did not run."""
    m = re.search(r"entry ([\d.]+) · stop ([\d.]+)", out or "")
    return (float(m.group(1)), float(m.group(2))) if m else None


# (id, plan line, expected entry, expected stop)
FORMS = [
    ("one_line_entry_then_stop",
     "Trade Type: POSITIONAL · Entry: Limit order at 52.45 · Stop: 51.59 · T1: 58.79 (3R) · T2: 62.39 (5R).",
     52.45, 51.59),
    ("one_line_parenthesised_entry",
     "SWING TRADE. Entry: Market Fill (27.69). Stop: 27.02 (2.4% risk). T1: 27.89 (0.7R). T2: 29.04 (4R).",
     27.69, 27.02),
    ("bare_buy_with_stop_in_parens",
     "Swing Trade (Targeting 2R): Buy 2190.0 (Stop 2103.4) · T1 2276.8 (2R)",
     2190.0, 2103.4),
    ("one_line_stop_first",
     "Stop: 51.59 · Entry: 52.45 · T1: 58.79 (3R)",
     52.45, 51.59),
    ("entry_token_owns_no_number",
     "Entry: limit order at 3636.7 · Stop: 3547.4 · T1: 3844.8 (1.2R)",
     3636.7, 3547.4),
    ("multi_line_the_form_that_always_worked",
     "**Entry:** 2930.9\n**Stop:** 2801.4\n**T1:** 3319.4 (3R)\n**T2:** 3578.4 (5R)",
     2930.9, 2801.4),
    ("buy_stop_is_an_entry_not_a_stop",
     "Buy-stop 105.5 · SL 99.0 · T1 118.5 (2R)",
     105.5, 99.0),
]


@pytest.mark.parametrize("name,line,exp_entry,exp_stop", FORMS, ids=[f[0] for f in FORMS])
def test_plan_layout_does_not_defeat_the_check(name, line, exp_entry, exp_stop):
    out = r_check(plan(line))
    assert RAN in out, f"{name}: R-CHECK did not run — {out!r}"
    assert parsed(out) == (exp_entry, exp_stop), f"{name}: wrong levels — {out!r}"


def test_it_recomputes_rather_than_believing_the_label():
    """The whole point: the model said 3R/5R, the arithmetic says otherwise."""
    out = r_check(plan(FORMS[0][1]))
    assert "T1 58.79 → 7.37R (model said 3.0R)" in out
    assert "T2 62.39 → 11.56R (model said 5.0R)" in out
    assert "mis-stated" in out


def test_a_genuinely_unparseable_plan_still_says_so():
    """Degrading loudly is the required behaviour — never a silent pass."""
    out = r_check(plan("Wait for a better location before committing capital."))
    assert "could not parse" in out


def test_no_plan_expected_on_a_pass():
    review = "**RULING:** PASS\n\n**PLAN**\nnone\n\n**FLIPS IF**\nx\n"
    assert r_check(review) == ""
