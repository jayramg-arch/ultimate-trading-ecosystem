#!/usr/bin/env python3
"""Push the two Golden Matcher bundles into S4 on EVERY chart tab that carries it.

21-Sep-2026. The bundles are `input.string`s, so each S4 instance (S4 Phase-2, S4
Reviewer, S4 Phase-1) holds its own copy: six pastes a day by hand, and a missed
paste does not blank a field - it leaves LAST session's list applied to today's
board, silently. This writes both inputs on every S4 tab over the same CDP path
BIND_S4_SOURCES uses (setInputValues on the study), then reads them back.

    python tv_push_bundles.py               push gm_bundles/latest.txt
    python tv_push_bundles.py --check       show what each tab currently holds
    python tv_push_bundles.py --file X      push a different bundle file

Bundle file layout (gm_evening_headless.write_bundles): comment lines start with #;
the first non-comment line is bundle 1 (the ONE-PASTE union), the second is bundle 2
(options OI). Either may be empty - an empty push CLEARS the field, which is the
correct thing for a section that produced nothing (S4 reads an empty section as
"no list", not "keep the old one").

Exit 0 = every S4 tab reads back both values · 1 = a tab differs / no S4 tab ·
2 = TradingView not reachable or bundle file missing.
"""
import argparse
import json
import os
import sys

from tv_bind_s4 import _chart_targets_all, _evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE_FILE = os.path.join(HERE, "gm_bundles", "latest.txt")

IN1 = "GM: ONE-PASTE bundle (all lists)"
IN2 = "GM: bundle 2 — options OI"         # em-dash, exactly as the input title

# Study lookup as tv_bind_s4_sources.js does it; values are injected as JSON literals.
JS = r"""
(function () {
  try {
    var chart = (window.TradingViewApi || window.tvWidget).activeChart();
    var studies = chart.getAllStudies();
    var id = null;
    for (var i = 0; i < studies.length; i++) if (studies[i].name.indexOf("Section 4") === 0) { id = studies[i].id; break; }
    if (!id) return JSON.stringify({error: "S4 not on this chart"});
    var s4 = chart.getStudyById(id);
    var want = %(want)s;                       // {inputTitle: value} or {} for --check
    var ids = {};
    var titles = %(titles)s;
    s4.getInputsInfo().forEach(function (inp) { if (titles.indexOf(inp.name) >= 0) ids[inp.name] = inp.id; });
    var missing = Object.keys(want).filter(function (k) { return !(k in ids); });
    if (missing.length) return JSON.stringify({error: "input not found: " + missing.join(" / ")});
    if (Object.keys(want).length) {
      s4.setInputValues(Object.keys(want).map(function (k) { return {id: ids[k], value: want[k]}; }));
    }
    var got = {};
    s4.getInputValues().forEach(function (v) { got[v.id] = v.value; });
    var out = {study: s4.name || studies.filter(function(s){return s.id===id;})[0].name};
    Object.keys(ids).forEach(function (k) { out[k] = String(got[ids[k]] == null ? "" : got[ids[k]]); });
    return JSON.stringify(out);
  } catch (e) { return JSON.stringify({error: String(e)}); }
})()
"""


def read_bundles(path: str) -> tuple[str, str]:
    lines = [l.rstrip("\r\n") for l in open(path, encoding="utf-8")]
    body = [l for l in lines if not l.lstrip().startswith("#")]
    body = [l for l in body if l.strip()] + ["", ""]
    return body[0], body[1]


def main_push(path: str = BUNDLE_FILE) -> int:
    """Programmatic entry (the evening run): push `path`, return the CLI exit code."""
    argv, sys.argv = sys.argv, [sys.argv[0], "--file", path]
    try:
        return main()
    finally:
        sys.argv = argv


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="read what each tab holds, change nothing")
    ap.add_argument("--file", default=BUNDLE_FILE)
    a = ap.parse_args()

    want = {}
    if not a.check:
        if not os.path.exists(a.file):
            print(f"bundle file missing: {a.file} - run the Evening run first", file=sys.stderr); return 2
        b1, b2 = read_bundles(a.file)
        want = {IN1: b1, IN2: b2}
        print(f"bundle 1: {len(b1)} chars ({b1.count('|') + (1 if b1 else 0)} sections) · bundle 2: {len(b2)} chars")
        if not b1:
            print("bundle 1 is EMPTY - refusing to blank every S4 tab; check gm_bundles/latest.txt", file=sys.stderr); return 2

    tgts = _chart_targets_all()
    if not tgts:
        return 2
    js = JS % {"want": json.dumps(want, ensure_ascii=False), "titles": json.dumps([IN1, IN2], ensure_ascii=False)}
    rc, n = 0, 0
    for t in tgts:
        cid = t["url"].split("/chart/")[1].strip("/")
        out = _evaluate(t["webSocketDebuggerUrl"], js)
        try:
            d = json.loads(out.get("value") or "{}")
        except Exception:
            d = {}
        if "error" in out or d.get("error"):
            msg = str(d.get("error") or out.get("error"))
            if "S4 not on this chart" in msg:
                print(f"chart {cid}: no S4 - skipped")
            else:
                print(f"chart {cid}: ERROR {msg[:120]}", file=sys.stderr); rc |= 1
            continue
        n += 1
        g1, g2 = d.get(IN1, ""), d.get(IN2, "")
        if a.check:
            print(f"chart {cid}: bundle 1 {len(g1)} chars · bundle 2 {len(g2)} chars")
            continue
        ok = (g1 == want[IN1]) and (g2 == want[IN2])
        print(f"chart {cid}: {'ok' if ok else 'MISMATCH'} - bundle 1 {len(g1)} chars · bundle 2 {len(g2)} chars")
        rc |= 0 if ok else 1
    if n == 0:
        print("no chart tab carries S4 - nothing pushed", file=sys.stderr); return 1
    print(f"{n} S4 tab(s) {'checked' if a.check else 'pushed'}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
