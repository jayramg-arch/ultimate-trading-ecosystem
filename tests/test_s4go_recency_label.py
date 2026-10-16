"""The S4-GO cell names the gate that is missing. When the PA-recency cap is the ONLY
reason a row stops at 4/5, it used to say "no funda" - MOREALTY 75m on 12-Oct-2026
read '4/5 · no funda · F n/a · PA 2b' for an ETF, whose F cannot fail."""
from gm_trigger_board import s4go_status


def _ctx(**kw):
    c = {"pa_patterns": [],            # nothing fires on THIS bar ...
         "pa_recent": {"sigma": 3, "age": 2},   # ... but a pattern fired 2 bars ago
         "support": {"at_support": True, "in_fresh_dz": True},
         "relvol": 1.4, "bar_ok": True,
         "_board_tf": "75m"}
    c.update(kw)
    return c


def test_recency_row_with_every_gate_is_a_go_with_its_age():
    # 16-Oct-2026: no recency cap any more (both recency pre-registrations passed).
    s = s4go_status(0, _ctx(), True, "bull", fund_ok=True)
    assert s.startswith("5/5 GO · PA 2b"), s
    assert "no funda" not in s


def test_etf_recency_row_does_not_claim_a_fundamentals_failure():
    s = s4go_status(0, _ctx(), True, "bull", fund_ok=None, is_etf=True)
    assert s.startswith("5/5 GO") and "no funda" not in s, s
    assert "F n/a" in s


def test_a_real_fundamentals_failure_is_still_named():
    s = s4go_status(4, _ctx(pa_recent=None, pa_patterns=[("Hammer at 50-SMA", True, 2, "")]),
                    True, "bull", fund_ok=False)
    assert "no funda" in s, s


def test_a_failing_technical_gate_still_wins_the_label():
    s = s4go_status(0, _ctx(relvol=0.3), True, "bull", fund_ok=True)
    assert "no vol" in s and "recent PA" not in s, s


def test_daily_combo_bar_passes_a_weak_latest_bar():
    """16-Oct-2026: on a Daily recency row a STRONG PA->now combo passes the bar gate."""
    s = s4go_status(0, _ctx(_board_tf="Daily", bar_ok=False,
                            pa_recent={"sigma": 3, "age": 2, "grade": "strong"}), True, "bull", fund_ok=True)
    assert s.startswith("5/5 GO · PA 2b combo-bar"), s


def test_daily_weak_combo_does_not_pass_a_weak_bar():
    s = s4go_status(0, _ctx(_board_tf="Daily", bar_ok=False,
                            pa_recent={"sigma": 3, "age": 2, "grade": "weak"}), True, "bull", fund_ok=True)
    assert "weak bar" in s, s
