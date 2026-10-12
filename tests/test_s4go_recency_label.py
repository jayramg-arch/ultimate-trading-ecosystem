"""The S4-GO cell names the gate that is missing. When the PA-recency cap is the ONLY
reason a row stops at 4/5, it used to say "no funda" - MOREALTY 75m on 12-Oct-2026
read '4/5 · no funda · F n/a · PA 2b' for an ETF, whose F cannot fail."""
from gm_trigger_board import s4go_status


def _ctx(**kw):
    c = {"pa_patterns": [],            # nothing fires on THIS bar ...
         "pa_recent": {"sigma": 3, "age": 2},   # ... but a pattern fired 2 bars ago
         "support": {"at_support": True, "in_fresh_dz": True},
         "relvol": 1.4, "bar_ok": True}
    c.update(kw)
    return c


def test_recency_cap_alone_is_named_recent_pa_not_no_funda():
    s = s4go_status(0, _ctx(), True, "bull", fund_ok=True)
    assert s.startswith("4/5 · recent PA"), s
    assert "no funda" not in s
    assert "PA 2b" in s, "the age tag must still print"


def test_etf_recency_row_does_not_claim_a_fundamentals_failure():
    s = s4go_status(0, _ctx(), True, "bull", fund_ok=None, is_etf=True)
    assert "recent PA" in s and "no funda" not in s, s
    assert "F n/a" in s


def test_a_real_fundamentals_failure_is_still_named():
    s = s4go_status(4, _ctx(pa_recent=None, pa_patterns=[("Hammer at 50-SMA", True, 2, "")]),
                    True, "bull", fund_ok=False)
    assert "no funda" in s, s


def test_a_failing_technical_gate_still_wins_the_label():
    s = s4go_status(0, _ctx(relvol=0.3), True, "bull", fund_ok=True)
    assert "no vol" in s and "recent PA" not in s, s
