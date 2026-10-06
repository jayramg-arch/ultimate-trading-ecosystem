"""daily_regime: the clock picks the right block; every step's links exist; the manual builds."""
import datetime as dt

import daily_regime as d


def _t(*a):
    return dt.datetime(*a, tzinfo=d.IST)


def test_phase_by_clock_and_calendar():
    assert d.phase_now(_t(2026, 10, 7, 8, 40)) == "pre"
    assert d.phase_now(_t(2026, 10, 7, 9, 15)) == "session"
    assert d.phase_now(_t(2026, 10, 7, 15, 30)) == "post"
    assert d.phase_now(_t(2026, 10, 10, 11, 0)) == "weekend"      # Saturday
    assert d.phase_now(_t(2026, 10, 2, 11, 0)) == "weekend"       # NSE holiday


def test_every_link_key_exists_and_every_phase_has_a_you_step():
    L = d.links("jaynuc")
    for ph in d.PHASES:
        assert any(s["who"] == "you" for s in ph["steps"]), ph["key"]
        for s in ph["steps"]:
            for k in s.get("links", []):
                assert k in L, k
    assert L["risk"][0].startswith("http://jaynuc:8501/?p=RISK%20SHIELD")


def test_manual_builds():
    h = d.build_html()
    assert "Daily Regime" in h and all(f'id="{p["key"]}"' in h for p in d.PHASES)
    assert "# DAILY REGIME" in d.build_md()
