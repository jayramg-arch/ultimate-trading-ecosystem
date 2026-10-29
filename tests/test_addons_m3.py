"""Commander Add-ons M3 (candlesticks at key levels, 27-Oct-2026).

M3 calls S4's own S/R engine (core.srLevels) so "a key level" on the chart is the level S4
prints. That only holds while M3 imports the SAME S4Core version and passes S4's default S/R
settings, and while the binder knows M3's Zigzag inputs. These tests fail when either drifts.
"""
import glob
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDONS = os.path.join(HERE, "Commander_Addons_v1.0.pine")
BINDER = os.path.join(HERE, "tv_bind_s4_sources.js")


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def _s4_file():
    hits = [p for p in glob.glob(os.path.join(HERE, "*.pine"))
            if re.search(r'indicator\("Section 4', _read(p))]
    hits = [p for p in hits if "import jayramg/S4Core/" in _read(p)]
    assert hits, "no S4 file with an S4Core import found"
    return max(hits, key=os.path.getmtime)


def _import_ver(src):
    m = re.search(r"^import jayramg/S4Core/(\d+) as core", src, re.M)
    assert m, "no S4Core import"
    return int(m.group(1))


def test_same_s4core_version_as_s4():
    assert _import_ver(_read(ADDONS)) == _import_ver(_read(_s4_file()))


def test_sr_constants_equal_s4_defaults():
    s4 = _read(_s4_file())
    ad = _read(ADDONS)

    def s4_default(name):
        m = re.search(r"^%s\s*=\s*input\.\w+\(([^,]+)," % re.escape(name), s4, re.M)
        assert m, name
        return m.group(1).strip()

    def m3_const(name):
        m = re.search(r"^%s\s*=\s*(\S+)" % re.escape(name), ad, re.M)
        assert m, name
        return m.group(1).strip()

    pairs = {"SR_PV": "sr_pv", "SR_POOL": "sr_pool", "SR_TOL": "sr_tol",
             "SR_MINSPACE": "sr_minspace", "SR_MINTOUCH": "sr_min_touch",
             "SR_WICKTOUCH": "sr_wick_touch", "SR_WICKFIT": "sr_wick_fit"}
    for c, i in pairs.items():
        assert m3_const(c) == s4_default(i), (c, m3_const(c), s4_default(i))


def test_binder_knows_m3_inputs():
    ad, js = _read(ADDONS), _read(BINDER)
    for title in ("M3 · Zigzag trend (chart TF)", "M3 · Zigzag trend (weekly)"):
        assert 'input.source(close, "%s"' % title in ad
        assert '"%s"' % title in js


def test_candidate_tables_line_up():
    # The 11 candidate arrays are indexed together; a missing entry shifts every name.
    ad = _read(ADDONS)
    for name in ("M3_BU_CD", "M3_BE_CD", "M3_BU_NM", "M3_BE_NM", "M3_NB", "M3_CF", "M3_BU_NT", "M3_BE_NT"):
        m = re.search(r"%s\s*=\s*array\.from\((.*)\)\s*$" % name, ad, re.M)
        assert m, name
        items = re.findall(r'"[^"]*"|[^,\s][^,]*', m.group(1))
        assert len(items) == 11, (name, len(items))


# ---- v1.5 export to S4 (27-Oct-2026) --------------------------------------------------
CORE = os.path.join(HERE, "S4Core.pine")


def _arr(src, name):
    m = re.search(r"%s\s*=\s*array\.from\((.*?)\)\s*$" % re.escape(name), src, re.M)
    assert m, name
    return re.findall(r'"([^"]*)"', m.group(1))


def test_s4core_names_equal_addons_names():
    # S4Core.candleRead decodes the pattern by its position in Add-ons' list.
    ad, core = _read(ADDONS), _read(CORE)
    body = core[core.index("export candleRead("):]
    assert _arr(body, "array<string> nmBu") == _arr(ad, "M3_BU_NM")
    assert _arr(body, "array<string> nmBe") == _arr(ad, "M3_BE_NM")


def test_s4_candle_inputs_bound_and_appended_last():
    s4, ad, js = _read(_s4_file()), _read(ADDONS), _read(BINDER)
    pairs = {"Add-ons: candle code": "s4_candleCode", "Add-ons: candle level": "s4_candleLvl",
             "Add-ons: candle trigger": "s4_candleTrig"}
    for title, plot in pairs.items():
        assert 'input.source(close, "%s"' % title in s4
        assert '"%s":' % title in js and '"%s"' % plot in js
        assert 'plot(' in ad and '"%s"' % plot in ad
    last_input = max(m.start() for m in re.finditer(r"= input\.", s4))
    assert s4.rfind('"Add-ons: candle trigger"') >= last_input


def _encode(dirn, idx, st, age, kind, trend):
    return dirn * (1e7 + (idx + 1) + 100 * st + 1000 * min(age, 99) + 1e5 * kind + 1e6 * (trend + 1))


def _decode(code):
    # Python mirror of S4Core.candleRead's arithmetic.
    import math
    r = abs(code) - 1e7
    tr = int(math.floor(r / 1e6 + 1e-9)); r -= tr * 1e6
    kind = int(math.floor(r / 1e5 + 1e-9)); r -= kind * 1e5
    age = int(math.floor(r / 1000 + 1e-9)); r -= age * 1000
    st = int(math.floor(r / 100 + 1e-9))
    idx = int(round(r - st * 100)) - 1
    return (1 if code > 0 else -1, idx, st, age, kind, tr - 1)


def test_code_round_trips_in_float32():
    import itertools
    import struct
    for d, i, s, a, k, t in itertools.product((1, -1), range(11), range(4), (0, 1, 7, 99), range(1, 7), (-1, 0, 1)):
        c = _encode(d, i, s, a, k, t)
        c32 = struct.unpack("f", struct.pack("f", c))[0]
        assert _decode(c32) == (d, i, s, a, k, t)
        assert 1e7 < abs(c32) < 2 ** 24


def test_encoder_matches_addons_source():
    ad = _read(ADDONS)
    assert "1e7 + (q.idx + 1) + 100 * q.st + 1000 * math.min(age, 99) + 1e5 * q.kind + 1e6 * (q.trd + 1)" in ad
