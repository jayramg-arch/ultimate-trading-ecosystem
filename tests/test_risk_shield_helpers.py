"""Characterization tests for the Risk Shield trade-type + AI-honesty helpers.

These exec the ACTUAL source of `_rs_trade_type` / `_rs_type_badge` / `_rs_ai_card`
out of weinstein_commander_web_v4.0.py, so they go red if the shipped code drifts.
The app is a Streamlit script and cannot be imported, hence the extraction.

Pins the 31-Jul-2026 ruling (Jay): Risk Shield owns the trade type, and the AI
block must never present a failed LLM call as analysis. Before this, the tile
badge was parsed out of the model's own "[Positional]"/"[Swing]" prefix while the
Rec SL/T1/T2 multipliers used Python's `is_swing` — two evaluators of one rule —
and the OCO copy defaulted a missing ws_score to 0 (=> SWING) while the
Unprotected copy defaulted it to 100 (=> POSITIONAL).

Runs under pytest OR as a plain script (pytest is not installed in the
TradingData venv):  python tests/test_risk_shield_helpers.py
"""
import io
import os
import re
import textwrap

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP = os.path.join(_ROOT, "weinstein_commander_web_v4.0.py")
SRC = io.open(_APP, encoding="utf-8").read()


def _grab(name):
    """The def line plus every following blank-or-deeper-indented line."""
    lines = SRC.split("\n")
    start = next(i for i, l in enumerate(lines) if re.match(r"\s*def %s\(" % name, l))
    ind = len(lines[start]) - len(lines[start].lstrip())
    out = [lines[start]]
    for l in lines[start + 1:]:
        if l.strip() and (len(l) - len(l.lstrip())) <= ind:
            break
        out.append(l)
    return textwrap.dedent("\n".join(out))


class _FakeSt:
    session_state = {}


_NS = {"st": _FakeSt}
for _fn in ("_rs_trade_type", "_rs_type_badge", "_rs_ai_card"):
    exec(_grab(_fn), _NS)

tt = _NS["_rs_trade_type"]
badge = _NS["_rs_type_badge"]
card = _NS["_rs_ai_card"]


# ── trade type: ONE rule, owned by Risk Shield ────────────────────────────────
def test_stable_stage2_is_positional():
    assert tt({"atr_pct": 2.0, "dist_from_200": 10, "ws_score": 72}) == (False, "POSITIONAL")


def test_each_swing_trigger_fires():
    assert tt({"atr_pct": 5.1, "dist_from_200": 10, "ws_score": 72}) == (True, "SWING")
    assert tt({"atr_pct": 2.0, "dist_from_200": 41, "ws_score": 72}) == (True, "SWING")
    assert tt({"atr_pct": 2.0, "dist_from_200": 10, "ws_score": 45}) == (True, "SWING")


def test_missing_score_is_not_swing():
    """The divergence the two old copies disagreed on. A score we never computed
    must not be read as trend decay."""
    assert tt({"atr_pct": 2.0, "dist_from_200": 10}) == (False, "POSITIONAL")


def test_score_zero_is_a_real_zero():
    """...but a genuine 0 still means decay — the guard must be `is None`, not falsy."""
    assert tt({"atr_pct": 2.0, "dist_from_200": 10, "ws_score": 0}) == (True, "SWING")


def test_undeterminable_is_unknown_not_a_guess():
    assert tt(None) == (None, "UNKNOWN")
    assert tt({"atr_pct": 0, "ws_score": 72}) == (None, "UNKNOWN")
    assert tt({"atr_pct": float("nan")}) == (None, "UNKNOWN")


# ── badge: rendered from the engine, and honest about what it doesn't know ─────
def test_unknown_type_is_visible():
    assert "TYPE UNKNOWN" in badge("UNKNOWN")
    assert "TYPE UNKNOWN" in badge(None)


def test_badge_colours_track_the_type():
    assert ">SWING<" in badge("SWING") and "#8957e5" in badge("SWING")
    assert ">POSITIONAL<" in badge("POSITIONAL") and "#238636" in badge("POSITIONAL")


def test_inferred_type_is_marked_and_determined_type_is_not():
    assert "opacity" in badge("SWING?") and ">SWING?<" in badge("SWING?")
    assert "opacity" not in badge("SWING")


# ── AI card: a failed call must not wear the analysis header ──────────────────
def test_llm_failure_is_styled_as_failure():
    out = card("⚠ AI UNAVAILABLE — the LLM call failed. No analysis was generated for this position.")
    assert "No AI analysis" in out and "#f85149" in out
    assert "🤖 <b>AI:</b>" not in out


def test_thread_level_failure_also_caught():
    assert "No AI analysis" in card("AI review unavailable.")


def test_pending_is_distinct_from_failed():
    assert "not run yet" in card("AI analysis pending. Click 'Run AI Analysis' to generate.")


def test_real_analysis_renders_and_strips_stray_tags():
    _FakeSt.session_state = {}
    out = card("[Positional] Holding above a rising 200-SMA.")
    assert "🤖 <b>AI:</b>" in out and "Holding above" in out
    assert "[Positional]" not in out
    assert "generated" not in out


def test_generation_stamp_shown_when_recorded():
    _FakeSt.session_state = {"ai_cache_ts": "31 Jul 09:14"}
    assert "generated 31 Jul 09:14" in card("Trend intact.")
    _FakeSt.session_state = {}


def test_empty_renders_nothing():
    assert card("") == ""


if __name__ == "__main__":
    _fails = []
    for _name, _fn in sorted(list(globals().items())):
        if _name.startswith("test_") and callable(_fn):
            try:
                _fn()
            except AssertionError as _e:
                _fails.append(f"{_name}: {_e or 'assertion failed'}")
    print(f"{len(_fails)} failed")
    for _f in _fails:
        print("  ", _f)
    print("PASS" if not _fails else "FAIL")
    raise SystemExit(1 if _fails else 0)
