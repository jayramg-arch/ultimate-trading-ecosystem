#!/usr/bin/env python3
"""Push the v2 status line into Commander Add-ons (module M2) on every chart tab (18-Oct-2026, Doc 42 C9).

The status line (data/v2/addon_status.txt, written nightly by p1_paper.v2_workflow) tells the
chart, for every v2 name: rank of N, the group (BUY / SELL / HOLD / WATCH), the disaster or
trailed stop, and whether the holding is real or paper. Add-ons is display only - nothing here
touches S4, its bindings or any alert.

    python tv_push_addons.py           push data/v2/addon_status.txt to every tab carrying Add-ons
    python tv_push_addons.py --check   read what each tab holds, change nothing

Exit 0 = every Add-ons tab reads back the line · 1 = a tab differs / none carries Add-ons with
M2 · 2 = TradingView not reachable or the status file missing.
"""
import argparse
import json
import os
import sys

from tv_bind_s4 import _chart_pages_every, _evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(HERE, "data", "v2", "addon_status.txt")
IN_V2 = "v2 status (pushed nightly - do not edit)"

JS = r"""
(function () {
  try {
    var chart = (window.TradingViewApi || window.tvWidget).activeChart();
    var studies = chart.getAllStudies();
    var id = null;
    for (var i = 0; i < studies.length; i++) if (studies[i].name.indexOf("Commander Add-ons") === 0) { id = studies[i].id; break; }
    if (!id) return JSON.stringify({error: "no Add-ons"});
    var st = chart.getStudyById(id);
    var want = %(want)s, title = %(title)s, inId = null;
    st.getInputsInfo().forEach(function (inp) { if (inp.name === title) inId = inp.id; });
    if (!inId) return JSON.stringify({error: "no M2 input (compile Add-ons v1.3)"});
    if (want !== null) st.setInputValues([{id: inId, value: want}]);
    var got = "";
    st.getInputValues().forEach(function (v) { if (v.id === inId) got = String(v.value == null ? "" : v.value); });
    return JSON.stringify({got: got});
  } catch (e) { return JSON.stringify({error: String(e)}); }
})()
"""


def main_push() -> int:
    argv, sys.argv = sys.argv, [sys.argv[0]]
    try:
        return main()
    finally:
        sys.argv = argv


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    want = None
    if not a.check:
        if not os.path.exists(STATUS_FILE):
            print("status file missing: %s - run p1_paper.py first" % STATUS_FILE, file=sys.stderr)
            return 2
        want = open(STATUS_FILE, encoding="utf-8").read().strip()
    tgts = _chart_pages_every()
    if not tgts:
        return 2
    js = JS % {"want": json.dumps(want), "title": json.dumps(IN_V2)}
    rc, n = 0, 0
    for t in tgts:
        cid = t["url"].split("/chart/")[1].strip("/")
        out = _evaluate(t["webSocketDebuggerUrl"], js)
        try:
            d = json.loads(out.get("value") or "{}")
        except Exception:
            d = {}
        err = str(d.get("error") or out.get("error") or "")
        if err:
            if "no Add-ons" in err:
                continue
            print("chart %s: %s" % (cid, err[:120]), file=sys.stderr)
            rc |= 1
            continue
        n += 1
        got = d.get("got", "")
        if a.check:
            print("chart %s: v2 status %d chars%s" % (cid, len(got), (" · " + got[:40]) if got else ""))
        else:
            ok = got == want
            print("chart %s: %s - %d chars" % (cid, "ok" if ok else "MISMATCH", len(got)))
            rc |= 0 if ok else 1
    if n == 0:
        print("no chart tab carries Add-ons with the M2 input - nothing pushed")
        return 1
    print("%d Add-ons tab(s) %s" % (n, "checked" if a.check else "pushed"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
