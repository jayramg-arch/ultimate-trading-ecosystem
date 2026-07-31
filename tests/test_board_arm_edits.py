"""Grid arm/disarm write-back — the shared path used by BOTH board renderers.

Execs the ACTUAL `_gm_apply_arm_edits` source out of weinstein_commander_web_v4.0.py
(the app is a Streamlit script and cannot be imported), so these go red if the
shipped code drifts.

The function is shared on purpose: the data_editor and the streaming AG-Grid must
not snapshot different plans for the same click.

Runs under pytest OR standalone:  python tests/test_board_arm_edits.py
"""
import importlib
import io
import os
import re
import sys
import tempfile
import textwrap

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gm_armed  # noqa: E402
import gm_trigger_board as gtb  # noqa: E402

_APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "weinstein_commander_web_v4.0.py")


def _grab(name):
    lines = io.open(_APP, encoding="utf-8").read().split("\n")
    start = next(i for i, l in enumerate(lines) if re.match(r"\s*def %s\(" % name, l))
    ind = len(lines[start]) - len(lines[start].lstrip())
    out = [lines[start]]
    for l in lines[start + 1:]:
        if l.strip() and (len(l) - len(l.lstrip())) <= ind:
            break
        out.append(l)
    return textwrap.dedent("\n".join(out))


class _St:
    """Minimal Streamlit stand-in: only session_state is touched by this function."""
    session_state = {}


class _Log:
    def warning(self, *a, **k):
        pass


def build():
    """Fresh register + a fresh exec of the shipped function."""
    importlib.reload(gm_armed)
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)
    gm_armed._STORE = path
    sys.modules["gm_armed"] = gm_armed
    ns = {"st": _St, "_gm_logger": _Log(), "_gtb": gtb}
    exec(_grab("_gm_apply_arm_edits"), ns)
    _St.session_state = {}
    return ns["_gm_apply_arm_edits"], gm_armed


ROW = {
    "Symbol": "APOLLOHOSP", "Arm": True, "Path": "Bull", "Archetype": "Pullback, Armed",
    "Category": "Buy Trigger Live · Bull", "Entry": 7180.0, "SL": 6980.0, "T1": 7520.0,
    "R:R": 1.7, "ΣPA": 5, "S4-GO": "4/4 GO", "CMP": 7195.0,
}


def df(**kw):
    r = dict(ROW)
    r.update(kw)
    return pd.DataFrame([r])


# ── the core behaviour ───────────────────────────────────────────────────────
def test_ticking_arm_records_the_plan_from_that_row():
    apply, A = build()
    assert apply(df()) is True
    rec = A.get("APOLLOHOSP")
    assert rec["status"] == "ARMED"
    assert rec["trigger"] == 7180.0 and rec["sl"] == 6980.0 and rec["t1"] == 7520.0
    assert rec["s4go"] == "4/4 GO" and rec["sigma_pa"] == 5
    assert rec["cmp_at_arm"] == 7195.0


def test_the_armed_badge_is_not_recorded_as_a_thesis():
    """Archetype cells carry the 'Armed' badge; re-arming must not accrete it."""
    apply, A = build()
    apply(df())
    assert A.get("APOLLOHOSP")["archetypes"] == ["Pullback"]


def test_path_comes_from_the_row():
    apply, A = build()
    apply(df(Path="Recovery"))
    assert A.get("APOLLOHOSP")["path"] == "recovery"


def test_unticking_disarms():
    apply, A = build()
    apply(df())
    assert apply(df(Arm=False)) is True
    assert not A.is_armed("APOLLOHOSP")
    assert A.load()["APOLLOHOSP"]["status"] == "CANCELLED"


def test_no_change_is_not_a_write():
    """Must be idempotent — a rerun re-submits the whole grid every time."""
    apply, A = build()
    apply(df())
    before = A.get("APOLLOHOSP")["armed_at"]
    assert apply(df()) is False, "re-submitting an unchanged grid must not rewrite"
    assert A.get("APOLLOHOSP")["armed_at"] == before


def test_unticking_something_never_armed_is_a_noop():
    apply, A = build()
    assert apply(df(Arm=False)) is False
    assert A.load() == {}


# ── the cached-frame refresh (the tick must not visibly revert) ──────────────
def test_session_board_frame_is_patched_so_the_tick_sticks():
    apply, A = build()
    _St.session_state["gm_board_df"] = pd.DataFrame(
        [{"Symbol": "APOLLOHOSP", "Arm": False, "Armed": ""},
         {"Symbol": "TITAN", "Arm": False, "Armed": ""}])
    apply(df())
    out = _St.session_state["gm_board_df"]
    assert bool(out.loc[out.Symbol == "APOLLOHOSP", "Arm"].iloc[0]) is True
    assert out.loc[out.Symbol == "APOLLOHOSP", "Armed"].iloc[0].startswith("0d")
    assert bool(out.loc[out.Symbol == "TITAN", "Arm"].iloc[0]) is False, "must not touch others"


def test_missing_session_frame_does_not_break_the_write():
    apply, A = build()
    _St.session_state.pop("gm_board_df", None)
    assert apply(df()) is True and A.is_armed("APOLLOHOSP")


# ── robustness ───────────────────────────────────────────────────────────────
def test_frame_without_an_arm_column_is_ignored():
    apply, _ = build()
    assert apply(pd.DataFrame([{"Symbol": "X"}])) is False


def test_none_frame_is_ignored():
    apply, _ = build()
    assert apply(None) is False


def test_blank_symbol_rows_are_skipped():
    apply, A = build()
    assert apply(df(Symbol="")) is False and A.load() == {}


def test_one_bad_row_does_not_stop_the_others():
    apply, A = build()
    bad = dict(ROW); bad["Symbol"] = "GOODNAME"
    frame = pd.DataFrame([dict(ROW, Symbol=""), bad])
    assert apply(frame) is True
    assert A.is_armed("GOODNAME")


def test_symbol_variants_resolve_to_one_record():
    apply, A = build()
    apply(df(Symbol="APOLLOHOSP.NS"))
    assert A.is_armed("APOLLOHOSP")
    # unticking under the bare form must find the same record
    assert apply(df(Symbol="APOLLOHOSP", Arm=False)) is True
    assert not A.is_armed("APOLLOHOSP.NS")


if __name__ == "__main__":
    fails = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError as e:
                fails.append(f"{name}: {e or 'assertion failed'}")
            except Exception as e:
                fails.append(f"{name}: {type(e).__name__}: {e}")
    print(f"{len(fails)} failed")
    for f in fails:
        print("  ", f)
    print("PASS" if not fails else "FAIL")
    raise SystemExit(1 if fails else 0)
