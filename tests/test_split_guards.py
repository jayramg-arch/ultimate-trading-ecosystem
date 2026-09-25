"""Split guards (25-Sep, plan phase 4): the router stays a router and every page is wired."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "weinstein_commander_web_v4.0.py")
PAGES = os.path.join(ROOT, "commander_pages")

ROUTER_MAX_LINES = 4600        # 4,309 on 25-Sep-2026; grow the pages, not the router
PAGE_MAX_LINES = 3100          # RISK SHIELD is ~2,990; a page past this is two pages


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def test_router_line_budget():
    n = _read(APP).count("\n") + 1
    assert n <= ROUTER_MAX_LINES, f"router is {n} lines - move logic into a page or commander_core"


def test_every_routed_page_exists_and_every_page_is_routed():
    routed = re.findall(r'commander_pages\.run\("([a-z0-9_]+)", globals\(\)\)', _read(APP))
    files = {f[:-3] for f in os.listdir(PAGES) if f.endswith(".py") and f != "__init__.py"}
    assert len(routed) == 22 and len(set(routed)) == 22
    assert set(routed) == files


def test_page_files_keep_the_verbatim_shape():
    for f in sorted(os.listdir(PAGES)):
        if not f.endswith(".py") or f == "__init__.py":
            continue
        txt = _read(os.path.join(PAGES, f))
        assert "\nif True:\n" in txt, f"{f}: body must stay under `if True:` (no re-indent)"
        assert txt.count("\n") <= PAGE_MAX_LINES, f"{f} is over {PAGE_MAX_LINES} lines"
        compile(txt, f, "exec")


def test_core_imports_without_a_running_app():
    import commander_core  # noqa: F401  - Streamlit-free by construction


def test_pages_read_shared_state_through_app_state():
    """Split phase 1 (25-Sep): pages read balance / sys_status / total_cap / the journal and
    holdings frames through the frozen `app_state`, never as bare router globals - a bare
    name is one assignment away from silently changing the value for every later page."""
    import io
    import tokenize
    import commander_context as cc
    bad = []
    for f in sorted(os.listdir(PAGES)):
        if not f.endswith(".py") or f == "__init__.py":
            continue
        src = _read(os.path.join(PAGES, f))
        toks = [t for t in tokenize.generate_tokens(io.StringIO(src).readline)
                if t.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT,
                                  tokenize.INDENT, tokenize.DEDENT)]
        for i, t in enumerate(toks):
            if t.type == tokenize.NAME and t.string in cc.SHARED_NAMES:
                prev = toks[i - 1].string if i else ""
                nxt = toks[i + 1].string if i + 1 < len(toks) else ""
                if prev != "." and not (nxt == "=" and prev in ("(", ",")):
                    bad.append(f"{f}:{t.start[0]} {t.string}")
    assert not bad, "bare shared names (use app_state.<name>): " + ", ".join(bad)


def test_app_state_is_frozen():
    import dataclasses
    import pandas as pd
    import commander_context as cc
    s = cc.Ctx(1.0, "SYSTEM ONLINE", 2.0, True, pd.DataFrame(), pd.DataFrame())
    try:
        s.total_cap = 3.0
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("app_state must be frozen")
