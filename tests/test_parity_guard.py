"""The parity guard blocks exactly the commits it should (see tools/hooks/parity_guard.py)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "hooks"))
import parity_guard as pg  # noqa: E402

NO_DIFF = lambda f: ""  # noqa: E731


def test_pa_patterns_alone_is_blocked():
    assert pg.check("tweak engulf", ["pa_patterns.py"], NO_DIFF)


def test_pa_patterns_with_s4core_passes():
    assert pg.check("sync", ["pa_patterns.py", "S4Core.pine"], NO_DIFF) is None


def test_pa_patterns_with_v67_passes():
    assert pg.check("sync", ["pa_patterns.py", "Weinstein and Swing Pro Dashboard v67.4.12.pine"], NO_DIFF) is None


def test_waiver_passes():
    assert pg.check("refactor\n\nPARITY-WAIVER: comment only", ["strict_trend.py"], NO_DIFF) is None


def test_bull_screener_other_function_passes():
    diff = "@@ -10,1 +10,1 @@ def classify_catalyst(df):\n-a = 1\n+a = 2\n"
    assert pg.check("x", ["bull_screener.py"], lambda f: diff) is None


def test_bull_screener_stage_function_is_blocked():
    diff = "@@ -480,1 +480,1 @@ def compute_weekly_stage_and_wks(df_w):\n-s = 1\n+s = 2\n"
    assert pg.check("x", ["bull_screener.py"], lambda f: diff)


def test_strike_cal_edit_is_blocked():
    diff = "@@ -646,3 +646,3 @@\n-STRIKE_CAL = {'ratio_a': 0.796}\n+STRIKE_CAL = {'ratio_a': 0.8}\n"
    assert pg.check("x", ["rrg_engine.py"], lambda f: diff)


def test_unrelated_commit_passes():
    assert pg.check("docs", ["docs/22.md", "gm_trigger_board.py"], NO_DIFF) is None
