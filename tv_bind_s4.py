#!/usr/bin/env python3
"""Re-bind S4's input.source fields from the terminal — no Claude session needed.

WHY: TradingView drops every source binding on EVERY recompile of S4 (measured 7-Aug-2026:
after a compile that changed no inputs at all, 0 of 18 survived). Eighteen dropdowns by hand
each time is how the panel silently reverts to reading `close` and prints "-" in half its
rows. The JS lives in tv_bind_s4_sources.js; this drives it over the Chrome DevTools
Protocol that TradingView Desktop already exposes on port 9222.

REQUIRES TradingView Desktop launched with --remote-debugging-port=9222
(LAUNCH_TRADINGVIEW_CDP.bat). If it was started normally, the port is closed and this exits
with a clear message rather than a stack trace.

USAGE
    python tv_bind_s4.py            # bind, print the per-field report
    python tv_bind_s4.py --check    # report current binding state, change nothing

Exit codes: 0 bound/clean · 1 nothing to bind or a plot missing · 2 cannot reach TradingView.
"""
import argparse
import json
import os
import sys

import requests
import websocket                     # websocket-client

HERE = os.path.dirname(os.path.abspath(__file__))
JS_FILE = os.path.join(HERE, "tv_bind_s4_sources.js")
CDP = "http://localhost:9222"

# Read-only probe. Deliberately NOT a copy of the MAP in the .js — one definition of the
# mapping, in the file that owns it. This only counts bound-vs-unbound.
CHECK_JS = r"""
(function(){try{
  var chart=(window.TradingViewApi||window.tvWidget).activeChart();
  var ss=chart.getAllStudies();
  function f(p){for(var i=0;i<ss.length;i++)if(p(ss[i].name))return ss[i];return null;}
  var s4m=f(function(n){return n.indexOf("Section 4")===0;});
  if(!s4m)return JSON.stringify({error:"S4 not on this chart",studies:ss.map(function(s){return s.name;})});
  var s4=chart.getStudyById(s4m.id),vals={};
  s4.getInputValues().forEach(function(v){vals[v.id]=v.value;});
  var bound=[],unbound=[];
  s4.getInputsInfo().forEach(function(inp){
    if(String(inp.type)!=="source")return;
    if(inp.name.indexOf("v67:")!==0&&inp.name.indexOf("Zigzag:")!==0&&inp.name.indexOf("Unified:")!==0)return;
    var v=vals[inp.id];
    (typeof v==="string"&&v.indexOf("$")>-1?bound:unbound).push(inp.name);
  });
  return JSON.stringify({study:s4m.name,bound:bound.length,unbound:unbound.length,unboundList:unbound});
}catch(e){return JSON.stringify({error:String(e&&e.message||e)});}})();
"""


def _chart_targets_all():
    """EVERY TradingView chart page (13-Sep-2026): with a third S4 tab (Phase-1, the
    index chart) the old first-page pick bound whichever tab /json listed first -
    often the S5 tab, where there is no S4 to bind - and the new tab was never touched.
    Dedup by layout id: a duplicated tab of one layout is the same chart twice."""
    try:
        targets = requests.get(f"{CDP}/json", timeout=5).json()
    except Exception as e:
        print(f"Cannot reach TradingView's debug port at {CDP} ({e}).\n"
              f"Start it with LAUNCH_TRADINGVIEW_CDP.bat "
              f"(--remote-debugging-port=9222).", file=sys.stderr)
        return []
    pages, seen = [], set()
    for t in targets:
        u = str(t.get("url", ""))
        if t.get("type") == "page" and "/chart/" in u and u not in seen:
            seen.add(u); pages.append(t)
    return sorted(pages, key=lambda t: t["url"])


def _chart_target():
    """The TradingView chart page among the CDP targets."""
    try:
        targets = requests.get(f"{CDP}/json", timeout=5).json()
    except Exception as e:
        print(f"Cannot reach TradingView's debug port at {CDP} ({e}).\n"
              f"Start it with LAUNCH_TRADINGVIEW_CDP.bat "
              f"(--remote-debugging-port=9222).", file=sys.stderr)
        return None
    pages = [t for t in targets
             if t.get("type") == "page" and "tradingview.com" in str(t.get("url", ""))]
    if not pages:
        print("TradingView is running but no chart page was found. Open a chart first.",
              file=sys.stderr)
        return None
    # /chart/ pages first — a logged-in session can also have news/screener tabs open.
    pages.sort(key=lambda t: 0 if "/chart/" in str(t.get("url", "")) else 1)
    return pages[0]


def _evaluate(ws_url: str, expression: str):
    # suppress_origin: websocket-client sends an Origin header by default, and Chrome's
    # DevTools endpoint rejects any CDP socket carrying one ("Rejected an incoming WebSocket
    # connection from the http://localhost:9222 origin"). The alternative is relaunching
    # TradingView with --remote-allow-origins=*, which weakens the browser for every client;
    # not sending the header is the same fix on our side only.
    ws = websocket.create_connection(ws_url, timeout=60, suppress_origin=True)
    try:
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                            "params": {"expression": expression,
                                       "returnByValue": True,
                                       "awaitPromise": False}}))
        # CDP interleaves unsolicited events with the reply; take the first frame whose
        # id matches ours rather than assuming the reply comes back first.
        for _ in range(50):
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                if "error" in msg:
                    return {"error": msg["error"]}
                res = msg.get("result", {})
                if res.get("exceptionDetails"):
                    return {"error": str(res["exceptionDetails"])}
                return {"value": res.get("result", {}).get("value")}
        return {"error": "no matching CDP reply in 50 frames"}
    finally:
        ws.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="report the current binding state and change nothing")
    args = ap.parse_args()

    tgts = _chart_targets_all()
    if not tgts:
        print("TradingView is running but no chart page was found. Open a chart first.",
              file=sys.stderr)
        return 2
    if not args.check and not os.path.exists(JS_FILE):
        print(f"missing {JS_FILE}", file=sys.stderr); return 2
    js = open(JS_FILE, encoding="utf-8").read() if not args.check else ""

    rc, n_s4 = 0, 0
    for tgt in tgts:
        cid = tgt["url"].split("/chart/")[1].strip("/")
        # is S4 on this tab at all? (the S5 tab is a legitimate no)
        probe = _evaluate(tgt["webSocketDebuggerUrl"], CHECK_JS)
        try:
            d = json.loads(probe.get("value") or "{}")
        except Exception:
            d = {}
        if "error" in probe or d.get("error"):
            print(f"chart {cid}: no S4 here ({(d.get('error') or probe.get('error') or '')!s:.60}) - skipped")
            continue
        n_s4 += 1
        if args.check:
            print(f"chart {cid}: {d['study']}\n  bound {d['bound']} · unbound {d['unbound']}")
            for nm in d.get("unboundList", []):
                print(f"    UNBOUND  {nm}")
            rc |= 0 if d["unbound"] == 0 else 1
            continue
        out = _evaluate(tgt["webSocketDebuggerUrl"], js)
        if "error" in out:
            print(f"chart {cid}: ERROR {out['error']}", file=sys.stderr); rc |= 2; continue
        txt = str(out["value"] or "")
        print(f"chart {cid}: {txt}")
        # "bound 18/18 | mismatches: none" is the success shape; anything else is a problem
        # worth a non-zero exit so this can sit in a .bat chain after a compile.
        rc |= 0 if ("mismatches: none" in txt and "MISSING PLOT" not in txt) else 1
    if n_s4 == 0:
        print("no chart tab carries S4 - nothing bound", file=sys.stderr); return 2
    print(f"{n_s4} S4 tab(s) {'checked' if args.check else 'bound'}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
