# -*- coding: utf-8 -*-
"""Guard: Web Commander must not import a UI-HEAVY module at page-render time.

THE BUG THIS EXISTS FOR, which has now happened twice
-----------------------------------------------------
`dhan_journal_v7.py` is a full Streamlit app — it calls st.set_page_config() and paints
widgets at module level. Importing it therefore RENDERS it into whatever page triggered
the import.

10-Sep-2026: pressing RISK SHIELD showed the correct page header and then the entire
Active Trade Journal underneath it. The cause was one line inside the page block:

    import dhan_journal_v7 as _dj_d
    _dbf = _dj_d.DB_FILE          # ← the module was imported for a FILENAME

Golden Matcher was unaffected only by accident: it imports the module earlier in its own
block, so any later import that run was a cached no-op. Risk Shield was the first import
of the run, so it was the page that wore it.

There was already a comment warning about this at weinstein_commander_web_v4.0.py:184,
written after the FIRST time. Three call sites imported it anyway. A comment is not a
guard, so this is.

HOW IT DECIDES WHAT IS "UI-HEAVY"
---------------------------------
Not a hardcoded blocklist — it inspects each locally-importable module for Streamlit
calls at MODULE level. Any module that paints on import is dangerous by construction, so
a new one gets covered the day it appears.

WHAT IS ALLOWED
---------------
An import gated behind a click — an ancestor `if` whose test calls st.button /
st.form_submit_button / st.download_button. That code only runs when the user presses
something, by which point the page has already rendered and Streamlit is about to rerun
anyway. `_dj.upsert_trade` inside the guided-execution handler is the legitimate case.

An import can also be waived with an explicit `# ui-import-ok: <reason>` on the line,
so a reviewed exception is visible in the diff rather than silently permitted.
"""
from __future__ import annotations

import ast
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "weinstein_commander_web_v4.0.py")
CLICK_GATES = ("button", "form_submit_button", "download_button")


def _is_main_guard(node: ast.If) -> bool:
    """`if __name__ == "__main__":` — a CLI entry point, never executed on import.

    dhan_auth.py keeps a Streamlit-flavoured CLI block there. Counting it made the module
    look like it painted on import and put four innocent imports on the report.
    """
    t = node.test
    return (isinstance(t, ast.Compare)
            and isinstance(t.left, ast.Name) and t.left.id == "__name__"
            and len(t.comparators) == 1
            and isinstance(t.comparators[0], ast.Constant)
            and t.comparators[0].value == "__main__")


def _module_paints_on_import(name: str) -> bool:
    """True when the module makes Streamlit calls at MODULE level."""
    path = os.path.join(ROOT, name.split(".")[0] + ".py")
    if not os.path.exists(path):
        return False
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="ignore").read())
    except Exception:
        return False
    # "Paints on import" means a top-level STATEMENT that calls st.*, not merely a module
    # that mentions Streamlit. The first version walked INTO function bodies, so every
    # module with an st.* call anywhere — dhan_auth, pyramid_logic, market_data_hub —
    # came back dangerous and the guard flagged ~30 innocent imports. A guard that cries
    # wolf gets switched off, which would cost more than the bug it was written for.
    #
    # A `def`/`class` only DEFINES; a decorator (@st.cache_data) evaluates at import but
    # paints nothing. What executes AND paints is a bare expression or assignment at
    # module level, including one nested in a module-level if/with/try.
    def _paints(stmts) -> bool:
        for node in stmts:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(node, ast.If) and _is_main_guard(node):
                continue      # `if __name__ == "__main__":` never runs on import
            if isinstance(node, (ast.If, ast.With, ast.Try, ast.For, ast.While)):
                inner = []
                for attr in ("body", "orelse", "finalbody"):
                    inner += getattr(node, attr, []) or []
                for h in getattr(node, "handlers", []) or []:
                    inner += h.body
                if _paints(inner):
                    return True
                continue
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == "st"):
                    return True
        return False

    return _paints(tree.body)


def _click_gated(stack) -> bool:
    """Is any enclosing `if` conditioned on a Streamlit click?"""
    for node in stack:
        if not isinstance(node, ast.If):
            continue
        for sub in ast.walk(node.test):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                    and sub.func.attr in CLICK_GATES:
                return True
    return False


def _offending_imports(path):
    src = open(path, encoding="utf-8", errors="ignore").read()
    lines = src.split(chr(10))
    tree = ast.parse(src)
    found = []

    def walk(node, stack):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                names = ([a.name for a in child.names] if isinstance(child, ast.Import)
                         else [child.module or ""])
                for n in names:
                    if not n or not _module_paints_on_import(n):
                        continue
                    line = lines[child.lineno - 1] if child.lineno <= len(lines) else ""
                    if "ui-import-ok" in line:
                        continue
                    if not _click_gated(stack):
                        found.append((child.lineno, n, line.strip()[:70]))
            walk(child, stack + [child])

    walk(tree, [])
    return found


def test_no_ui_heavy_import_outside_a_click_handler():
    bad = _offending_imports(APP)
    assert not bad, (
        "These imports RENDER the imported app into the current page.\n"
        "Import the value you need without executing the module (see journal_db_path()), "
        "or move the import inside the click handler that needs it:\n"
        + chr(10).join("  line %d: %s   %s" % b for b in bad))


def test_the_guard_actually_detects_the_known_offender():
    """A guard that cannot see the original bug is decoration.

    Rebuilds the exact line that caused it and asserts the checker flags it — so if the
    detection is ever weakened, THIS fails rather than the guard quietly passing an
    empty scan.

    23-Sep-2026: the offender is now SYNTHETIC. dhan_journal_v7 was split
    (journal_core = data, journal_page = render()), so it no longer paints on import and
    can no longer serve as the canary. The bug SHAPE has not gone anywhere though — any
    module that paints at import time reintroduces it — so the probe now writes its own
    offender and asserts the detector still finds it.
    """
    offender = os.path.join(ROOT, "_guard_probe_ui_tmp.py")
    open(offender, "w", encoding="utf-8").write(chr(10).join([
        "import streamlit as st",
        "st.set_page_config(page_title='probe')",
        "st.title('I paint at module level')",
    ]))
    src = chr(10).join([
        "import streamlit as st",
        "page = 'RISK SHIELD'",
        "if page == 'RISK SHIELD':",
        "    import _guard_probe_ui_tmp as _dj_d",
        "    _dbf = _dj_d.DB_FILE",
    ])
    tmp = os.path.join(ROOT, "_guard_probe_tmp.py")
    open(tmp, "w", encoding="utf-8").write(src)
    try:
        assert _module_paints_on_import("_guard_probe_ui_tmp"), \
            "the probe's own offender is not detected as UI-heavy"
        assert _offending_imports(tmp), "the guard no longer detects the original bug"
    finally:
        os.remove(tmp)
        os.remove(offender)


def test_a_click_gated_import_is_allowed():
    """The legitimate pattern must NOT be flagged, or the guard gets switched off."""
    src = chr(10).join([
        "import streamlit as st",
        "if st.button('Log this trade'):",
        "    import dhan_journal_v7 as _dj",
        "    _dj.upsert_trade({})",
    ])
    tmp = os.path.join(ROOT, "_guard_probe_ok_tmp.py")
    open(tmp, "w", encoding="utf-8").write(src)
    try:
        assert not _offending_imports(tmp), "a click-gated import must be allowed"
    finally:
        os.remove(tmp)


def test_the_journal_module_no_longer_paints_on_import():
    """The premise, INVERTED on 23-Sep-2026 — and it inverted exactly the way the old
    version of this test said it would.

    It used to assert dhan_journal_v7 was UI-heavy, with the note: "If dhan_journal_v7 is
    ever split so it no longer paints on import, this test tells you the guard has become
    a no-op." That is what happened. Jay asked for the journal to be an active part of Web
    Commander, so it was split at the seam it already had:

        journal_core.py   the data layer, verbatim — safe to import anywhere
        journal_page.py   the dashboard, inside render() — draws only when called

    Both halves are now asserted UI-free ON IMPORT. That is the whole point of the split:
    the old module is what rendered the Active Trade Journal underneath Risk Shield's
    header, and what made the Golden Matcher's "Log OPEN trade" button run a live Dhan
    portfolio sync. If either regresses to painting at module level, that bug is back and
    this fails.
    """
    for mod in ("dhan_journal_v7", "journal_core", "journal_page"):
        if not os.path.exists(os.path.join(ROOT, mod + ".py")):
            pytest.skip("%s.py not present" % mod)
        assert not _module_paints_on_import(mod), \
            "%s paints at module level again — importing it will render into the caller's page" % mod
