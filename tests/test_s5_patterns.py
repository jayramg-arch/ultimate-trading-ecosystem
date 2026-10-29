"""S5 v1.8 chart patterns (27-Oct-2026).

The patterns tag each one with the primary trend from S4's own 30-WMA 2x2, and the panel row
must stay in section I, which the reviewer skips - patterns are a visual aid, never a grade.
These tests fail when either drifts.
"""
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S5 = os.path.join(HERE, "S5_Analysis_Panel_v1.3.pine")


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def _s4_file():
    import glob
    hits = [p for p in glob.glob(os.path.join(HERE, "*.pine"))
            if re.search(r'indicator\("Section 4', _read(p)) and "import jayramg/S4Core/" in _read(p)]
    assert hits
    return max(hits, key=os.path.getmtime)


def test_flat_band_equals_s4_default():
    s4 = re.search(r"^wma_flat_pct\s*=\s*input\.float\(([^,]+),", _read(_s4_file()), re.M)
    s5 = re.search(r"^CP_WMA_FLAT\s*=\s*(\S+)", _read(S5), re.M)
    assert s4 and s5
    assert float(s4.group(1)) == float(s5.group(1))


def test_s5_uses_s4_stage_inputs():
    # same MA (Daily SMA150 = 30-WMA) and the same 10-bar slope as S4Core.dailyPA
    src = _read(S5)
    assert "ta.sma(close, 150)" in src and "(_s - _s[10]) / _s * 100.0" in src


def _rows_and_sections():
    src = _read(S5)
    body = src[src.index("if show_s5p and barstate.islast"):]
    rows = {}
    for m in re.finditer(r'f_s5(row|sec)\((\d+),\s*"([^"]*)"', body):
        rows[int(m.group(2))] = (m.group(1), m.group(3))
    return rows


def _section_of(rows, r):
    heads = sorted((n, t) for n, (k, t) in rows.items() if k == "sec" and n < r)
    return heads[-1][1].strip()


def test_reviewer_sees_the_pattern_rows_but_not_the_geometry():
    # 27-Oct-2026 (S5 v1.9, Jay): the chart pattern feeds the reviewer; the geometry
    # classifier rows in the same sections stay withheld until tuned.
    import s4_review
    rows = _rows_and_sections()
    shown = {t: n for n, (k, t) in rows.items() if k == "row" and t in s4_review.S5_SHOWN_ROWS}
    assert set(shown) == {"Chart pattern", "PATTERN READ"}
    lines = []
    for n in sorted(rows):
        k, t = rows[n]
        lines.append(t if k == "sec" else "%s | value" % t)
    out = s4_review._filter_s5_rows(lines)
    assert "Chart pattern | value" in out and "PATTERN READ | value" in out
    for geo in ("Shape", "Boundaries", "Resistance", "Support", "READ"):
        assert "%s | value" % geo not in out, geo
    # the two rows really do sit in withheld sections - that is why they are whitelisted
    for t, n in shown.items():
        sec = _section_of(rows, n)
        assert any(sec.startswith(k) for k in s4_review.S5_SKIP_SECTIONS), (t, sec)


def test_pattern_read_parses_s4_candle_and_s5_pattern():
    import s4_review
    txt = ("Intraday 75 │ Pattern | ok   │   🕯 Hammer ? at Daily S/R 98.5 · last bar · PENDING -\n"
           "close above 101 · ↺ counter-trend  —  a long lower wick with the close near the high\n"
           "Chart pattern | Cup with handle   ·   TARGET REACHED 140 (broke out at 120)\n")
    got = s4_review.pattern_read(txt)
    assert got == {"candle": "Hammer @ Daily S/R 98.5", "candle_state": "pending",
                   "chart_pattern": "Cup with handle", "pattern_state": "target reached"}
    assert s4_review.pattern_read("nothing here") == dict.fromkeys(s4_review.PATTERN_FIELDS, "")


def test_panel_rows_unique_and_fit_the_table():
    src = _read(S5)
    body = src[src.index("if show_s5p and barstate.islast"):]
    nums = [int(n) for n in re.findall(r"f_s5(?:row|sec)\((\d+),", body)]
    assert len(nums) == len(set(nums))
    size = int(re.search(r"table\.new\(f_s5pos\(\), 2, (\d+)", src).group(1))
    assert max(nums) < size


def test_pattern_inputs_come_after_every_existing_input():
    # TradingView keeps saved settings by input POSITION; new inputs go last.
    src = _read(S5)
    first_cp = src.index("cp_on     = input.bool(")
    assert src.rfind("s5pSize   = input.string(") < first_cp
    assert "= input." not in src[src.index("var table s5p"):]
