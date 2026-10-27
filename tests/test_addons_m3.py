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
