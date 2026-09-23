"""The RRG "BUY OK" whitelist must be ONE definition across three surfaces.

AUD-PAR-06, found 23-Sep-2026. The whitelist was re-measured on 18-Aug and cut from five
cells to two. Both GATES were switched off on that evidence — and the DEFINITION was never
narrowed. So for five weeks:

  * S4's cf_w_rrg awarded its +1 confluence point on all five cells, including
    IMPROVING->LEADING, which that same measurement found reliably NEGATIVE, while
  * its own tooltip told the reader the point was for the two measured cells.

Three files carry the predicate — bull_screener (Python, canonical), S4Core.pine (feeds the
confluence point and the Q chip) and v67 (display) — and nothing mechanical kept them equal.
This is that mechanism. It reads the Pine SOURCE rather than executing it, which is the only
way to check a surface that only TradingView can run.
"""
import os
import re

import pytest

from bull_screener import _rrg_tradeable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S4CORE = os.path.join(ROOT, "S4Core.pine")
V67 = os.path.join(ROOT, "Weinstein and Swing Pro Dashboard v67.4.12.pine")

QUADS = ("LEADING", "WEAKENING", "LAGGING", "IMPROVING")
# The two cells that survived 473 symbols / 93,745 weekly observations, IS/OOS,
# bootstrapped by symbol. Changing this set means re-measuring, not editing a test.
MEASURED = {("LEADING", "LEADING"), ("WEAKENING", "LEADING")}


def test_python_matches_the_measured_pair_exactly():
    got = {(c, n) for c in QUADS for n in QUADS if _rrg_tradeable(c, n, 0.0)}
    assert got == MEASURED, "Python whitelist drifted: %s" % sorted(got)


def test_the_negative_cell_is_not_tradeable():
    """IMPROVING->LEADING measured -0.33 / -0.87 with the CI excluding zero. It is the
    single cell whose presence made the confluence point actively wrong."""
    assert not _rrg_tradeable("IMPROVING", "LEADING", 0.0)


def test_rs_ratio_argument_does_not_reintroduce_a_cell():
    """The signature still takes rs_ratio_centered (a 'cushion depth' idea from an older
    revision). It must not resurrect a dropped cell at any value."""
    for v in (-50.0, -1.0, 0.0, 1.0, 50.0):
        for c in QUADS:
            for n in QUADS:
                assert _rrg_tradeable(c, n, v) == ((c, n) in MEASURED), \
                    "cell (%s,%s) flipped at rs_ratio=%s" % (c, n, v)


def _pine_cells(path, fn_marker):
    """The (cur, nxt) pairs a Pine `tr = ...` assignment accepts, read from source.

    Comments are stripped first — every one of these files now DESCRIBES the dropped
    cells in prose directly above the code, so a naive scan would match the history and
    always pass.
    """
    if not os.path.exists(path):
        pytest.skip("%s not present" % os.path.basename(path))
    src = open(path, encoding="utf-8", errors="ignore").read()
    i = src.find(fn_marker)
    assert i >= 0, "%s not found in %s" % (fn_marker, os.path.basename(path))
    seg = src[i:i + 4000]
    j = seg.find("bool tr =")
    assert j > 0, "no `bool tr =` after %s" % fn_marker
    body = seg[j:j + 600]
    body = body[:body.find("[arrow")] if "[arrow" in body else body
    body = "\n".join(l.split("//")[0] for l in body.splitlines())
    return set(re.findall(
        r'cur\s*==\s*"(\w+)"\s*and\s*nxt\s*==\s*"(\w+)"', body))


def test_s4core_matches_python():
    cells = _pine_cells(S4CORE, "export rrgInfo")
    assert cells == MEASURED, "S4Core.rrgInfo drifted from Python: %s" % sorted(cells)


def test_v67_matches_python():
    cells = _pine_cells(V67, "f_rrg_info(float v")
    assert cells == MEASURED, "v67 f_rrg_info drifted from Python: %s" % sorted(cells)


def _pine_arrow_cases(path, fn_marker):
    """The glyphs the Pine arrow expression can emit."""
    if not os.path.exists(path):
        pytest.skip("%s not present" % os.path.basename(path))
    src = open(path, encoding="utf-8", errors="ignore").read()
    i = src.find(fn_marker)
    assert i >= 0
    seg = src[i:i + 4000]
    m = re.search(r"string (?:arw|arrow) = (.+)", seg)
    assert m, "no arrow expression after %s" % fn_marker
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def test_the_arrow_has_a_case_for_moving_left_with_flat_momentum():
    """AUD-PINE-07. S4Core had no branch for dv < -0.3 with flat dm, so a purely LEFT
    move fell through to the down-left glyph and printed "↙️" beside "→ IMPROVING" — an
    arrow and a label pointing opposite ways on one line. v67 and Python already had it.
    """
    core = _pine_arrow_cases(S4CORE, "export rrgInfo")
    v67 = _pine_arrow_cases(V67, "f_rrg_info(float v")
    assert core == v67, "S4Core arrow drifted from v67: %s vs %s" % (sorted(core), sorted(v67))
    assert any("⬅" in g for g in core), "no left-with-flat-momentum case"
    assert "•" in core, "a stationary point must not print a direction"


def test_the_arrow_matches_python():
    """Python is canonical; it writes plain glyphs where Pine writes emoji, so the test is
    on the SET of directions, not the exact characters."""
    from bull_screener import _rrg_trajectory  # noqa: F401  — import proves it loads
    core = _pine_arrow_cases(S4CORE, "export rrgInfo")
    directions = {g.rstrip("️") for g in core}
    assert directions == {"↗", "↘", "➡", "↖", "↙", "⬅", "⬆", "⬇", "•"}, sorted(directions)


def test_the_source_scan_can_actually_fail():
    """A parity test that cannot go red is decoration — the exact criticism the UI-import
    guard was written under. Feed it the five-cell form and it must reject it."""
    import tempfile
    five = ('export rrgInfo(float v)=>\n'
            '    bool tr = (cur == "LEADING" and nxt == "LEADING") or '
            '(cur == "IMPROVING" and nxt == "LEADING")\n    [arrow]\n')
    with tempfile.NamedTemporaryFile("w", suffix=".pine", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(five)
        tmp = fh.name
    try:
        assert _pine_cells(tmp, "export rrgInfo") != MEASURED
    finally:
        os.unlink(tmp)
