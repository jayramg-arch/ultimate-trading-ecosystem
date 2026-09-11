#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s4_review.py — AI deliberation over the S4 + S5 panels on the live TradingView chart.

WHAT IT DOES
    Reads every cell of the S4 and S5 panel tables (plus their drawn labels/lines/boxes and
    the last N bars) straight off TradingView Desktop over the Chrome DevTools Protocol,
    hands ALL of it to a model, and asks for a deliberated ruling — not an echo of S4's
    VERDICT row. The S4 verdict/summary go in LAST, labelled as one mechanical opinion.

    S4's SUMMARY column is a fixed template; it can restate rows but cannot weigh one
    against another (RV 0.72 on a pullback into a monthly zone is not the failure RV 0.72
    on a breakout is). This is the deliberation layer the panel does not have.

HOW IT READS THE PANEL (discovered 11-Sep-2026, verified byte-for-byte against the
TradingView MCP's data_get_pine_tables on CGPOWER/125)
    chart.getStudyById(id)._study.graphics().dwgtablecells()
        -> Map -> collection -> _primitivesDataById (Map id -> cell)
    cell = {tid, row, col, t (text), tt (tooltip), ...}      cells arrive UNORDERED
    Same shape for dwglabels() / dwglines() / dwgboxes(). Bars from
    mainSeries().bars().valueAt(i) -> [t, o, h, l, c, v].
    These are TradingView internals. A desktop update can rename them; every accessor
    fails LOUDLY ("panel path not found") rather than returning an empty panel.

REQUIRES
    TradingView Desktop launched with --remote-debugging-port=9222
    (LAUNCH_TRADINGVIEW_CDP.bat), the chart open with S4 (and ideally S5) VISIBLE.
    GEMINI_API_KEY in .env — default model gemini-3.1-flash-lite (Jay's pick, 11-Sep; the tier the rest of the
    app uses). --provider claude is opt-in only (S4_REVIEW_ANTHROPIC_KEY, claude-opus-5).
    Override with S4_REVIEW_GEMINI_MODEL / S4_REVIEW_MODEL. Never reads ANTHROPIC_MODEL/BASE_URL.

USAGE
    python s4_review.py                       # whatever the chart shows now
    python s4_review.py TITAN --tf 75         # switch symbol/TF first, wait for recalc
    python s4_review.py --symbols A,B,C --tf 125
    python s4_review.py --board 75m           # every N/N GO row of gm_board_cache_75m.csv
    python s4_review.py --dump                # print the raw panel read, no model call
    python s4_review.py TITAN --telegram      # also post the review to Telegram

OUTPUT
    Review printed; full text saved to logs/ai_reviews/<ts>_<SYMBOL>_<tf>.md; one row
    appended to logs/ai_review_log.csv. Jay's own call still goes in trade_reviews.csv —
    that file scores HIS eyes vs the system; this one scores the model's.

RULES BAKED INTO THE PROMPT (agreed 11-Sep-2026)
    * read every field; S4's ruling is one input, weighed last
    * case FOR before case AGAINST; fatal vs tolerable, named
    * a GO with a clean panel is a TAKE unless a NAMED fatal factor exists
    * every PASS must name the one change that makes it a TAKE, else it is a WAIT
    * it may talk Jay OUT of a trade; it never talks him INTO one that is not armed
    * the trader's chart-read has veto — the ruling is advice, logged for scoring
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # cp1252 under Task Scheduler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tv_bind_s4 import _evaluate, CDP as _CDP              # noqa: E402  (same CDP channel)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(HERE, ".env"))
except Exception:
    pass

LOG_DIR = os.path.join(HERE, "logs", "ai_reviews")
LOG_CSV = os.path.join(HERE, "logs", "ai_review_log.csv")
BARS_N = 60
# Deliberately NOT ANTHROPIC_MODEL / ANTHROPIC_BASE_URL: the Claude Code shell exports those
# pointing at its own proxy (11-Sep-2026: model "minimax-m2.5-free", key rejected). This
# script has its own knobs so an unattended run never inherits a session's plumbing.
DEFAULT_MODEL = os.getenv("S4_REVIEW_MODEL", "claude-opus-5")
CLAUDE_BASE = (os.getenv("S4_REVIEW_BASE_URL") or "https://api.anthropic.com").rstrip("/")
# Same tier ai_provider_manager.ask_llm already pays for. Jay's call (11-Sep): cost first;
# Claude stays opt-in via --provider claude and is never in the auto path.
GEMINI_MODEL = os.getenv("S4_REVIEW_GEMINI_MODEL", "gemini-3.1-flash-lite")


# ---------------------------------------------------------------------------------------
# JS that runs inside the TradingView page
# ---------------------------------------------------------------------------------------
READ_JS = r"""
(function(){try{
  var chart=(window.TradingViewApi||window.tvWidget).activeChart();
  var studies=chart.getAllStudies();
  function walk(x,acc){ if(!x)return; if(x._primitivesDataById){x._primitivesDataById.forEach(function(v){acc.push(v);});return;}
                        if(x.forEach)x.forEach(function(v){walk(v,acc);}); }
  function prims(g,name){ var a=[]; if(typeof g[name]!=="function")return a; walk(g[name](),a); return a; }
  var out={symbol:chart.symbol(),res:chart.resolution(),studies:[],errors:[]};
  studies.forEach(function(s){
    var api=chart.getStudyById(s.id); var st=api&&api._study;
    if(!st||typeof st.graphics!=="function"){ return; }
    var g=st.graphics();
    var cells=prims(g,"dwgtablecells").map(function(v){return {tid:v.tid,row:v.row,col:v.col,t:v.t||"",tt:v.tt||""};});
    if(!cells.length) return;
    var labels=prims(g,"dwglabels").map(function(v){return {y:v.y,t:v.t||"",tt:v.tt||""};});
    var lines=prims(g,"dwglines").map(function(v){return {y1:v.y1,y2:v.y2,x1:v.x1,x2:v.x2};});
    var boxes=prims(g,"dwgboxes").map(function(v){return {y1:v.y1,y2:v.y2,t:v.t||""};});
    out.studies.push({name:s.name,id:s.id,loading:!!(api.isLoading&&api.isLoading()),
                      cells:cells,labels:labels,lines:lines,boxes:boxes});
  });
  try{
    var w=null; for(var i=0;i<studies.length;i++){var a=chart.getStudyById(studies[i].id); if(a&&a._chartWidget){w=a._chartWidget;break;}}
    if(w){ var m=w.model(); var mm=(m.model?m.model():m); var b=mm.mainSeries().bars();
           var last=b.lastIndex(), bars=[]; for(var j=Math.max(b.firstIndex(),last-%(n)d+1); j<=last; j++){var v=b.valueAt(j); if(v)bars.push(v);}
           out.bars=bars; }
  }catch(e){ out.errors.push("bars: "+String(e&&e.message||e)); }
  return JSON.stringify(out);
}catch(e){return JSON.stringify({error:String(e&&e.message||e)});}})();
"""

SWITCH_JS = r"""
(function(){try{
  var chart=(window.TradingViewApi||window.tvWidget).activeChart();
  %(sym)s
  %(res)s
  return "ok";
}catch(e){return "ERR "+String(e&&e.message||e);}})();
"""

READY_JS = r"""
(function(){try{
  var chart=(window.TradingViewApi||window.tvWidget).activeChart();
  var n=0, loading=false, resolveErr=false;
  chart.getAllStudies().forEach(function(s){var a=chart.getStudyById(s.id);
    if(a&&a.isLoading&&a.isLoading())loading=true;
    try{var e=a.status&&a.status(); if(e&&e.errorDescription&&/resolve/i.test(e.errorDescription.error||""))resolveErr=true;}catch(x){}
    var st=a&&a._study; if(st&&st.graphics){var g=st.graphics(); if(g.dwgtablecells){g.dwgtablecells().forEach(function(c){
      if(c._primitivesDataById)n+=c._primitivesDataById.size; else if(c.forEach)c.forEach(function(cc){if(cc._primitivesDataById)n+=cc._primitivesDataById.size;});});}}});
  return JSON.stringify({symbol:chart.symbol(),res:chart.resolution(),loading:loading,cells:n,resolveErr:resolveErr});
}catch(e){return JSON.stringify({error:String(e&&e.message||e)});}})();
"""


class TVError(RuntimeError):
    pass


def _chart_targets() -> list[dict]:
    """EVERY open chart tab. Jay keeps two: one with S5, one with v67/Unified/Zigzag/S4.
    Reading only the first (as tv_bind_s4 does) would see one panel and miss the other."""
    try:
        targets = requests.get(_CDP + "/json", timeout=5).json()
    except Exception as e:
        raise TVError("TradingView not reachable on :9222 (%s) — LAUNCH_TRADINGVIEW_CDP.bat" % e)
    pages = [t for t in targets if t.get("type") == "page" and "/chart/" in str(t.get("url", ""))]
    if not pages:
        raise TVError("TradingView is running but no chart tab is open.")
    # /json reorders between calls and can list one page twice — a settle loop that
    # compares per-tab cell counts positionally never stabilises. Fixed order, one per URL.
    seen, out = set(), []
    for t in sorted(pages, key=lambda t: t.get("id", "")):
        if t["url"] not in seen:
            seen.add(t["url"]); out.append(t)
    return out


def _tv(expr: str, tgt: dict | None = None):
    if tgt is None:
        tgt = _chart_targets()[0]
    out = _evaluate(tgt["webSocketDebuggerUrl"], expr)
    if "error" in out:
        raise TVError(str(out["error"]))
    return out["value"]


def _tv_all(expr: str) -> list:
    return [_tv(expr, t) for t in _chart_targets()]


def switch_chart(symbol: str | None, tf: str | None, timeout_s: int = 45) -> dict:
    """Set symbol/TF, then wait until every study has recalculated and the cell count is
    stable. Returns the READY_JS state."""
    sym_js = 'chart.setSymbol(%s);' % json.dumps(_nse(symbol)) if symbol else ""
    res_js = 'chart.setResolution(%s);' % json.dumps(_res(tf)) if tf else ""
    want_sym = _nse(symbol) if symbol else None
    want_res = _res(tf) if tf else None
    tabs0 = _chart_targets()
    n_tabs = len(tabs0)
    # A tab that carried a panel BEFORE the switch must carry one after. Mid-recalc the S4
    # tab reports 0 cells with isLoading false (11-Sep: NEULANDLAB read "S4 not on chart",
    # BAJAJ-AUTO never settled) — an empty panel is "not ready", never "no panel".
    had_cells = {}
    for t in tabs0:
        try:
            had_cells[t["url"]] = json.loads(_tv(READY_JS, t)).get("cells", 0) > 0
        except Exception:
            had_cells[t["url"]] = False
    if sym_js or res_js:
        for r in _tv_all(SWITCH_JS % {"sym": sym_js, "res": res_js}):
            if str(r).startswith("ERR"):
                raise TVError(r)
        time.sleep(2.0)
    last_cells, stable, t0, sts = None, 0, time.time(), []
    while time.time() - t0 < timeout_s:
        tgts = _chart_targets()
        if len(tgts) < n_tabs:          # a tab drops off /json while it navigates
            time.sleep(1.5); continue
        sts = []
        for tgt in tgts:
            st = json.loads(_tv(READY_JS, tgt))
            if st.get("error"):
                raise TVError(st["error"])
            if st.get("resolveErr"):
                raise TVError("%s does not resolve on TradingView (studies report 'resolve error') "
                              "— check the ticker spelling" % st["symbol"])
            # a tab that did not take the switch (11-Sep: HONASA, one tab stayed on
            # CGPOWER) gets it re-asserted rather than waited on
            if (want_sym and st["symbol"] != want_sym) or (want_res and st["res"] != want_res):
                _tv(SWITCH_JS % {"sym": sym_js, "res": res_js}, tgt)
            if had_cells.get(tgt["url"]) and st["cells"] == 0:
                st["loading"] = True          # empty where a panel used to be = still busy
            sts.append(st)
        # a tab with no tables (a bare chart) must not hold the wait hostage; the tabs
        # that carry panels must all agree on symbol/TF and be done recalculating
        ok = all((want_sym is None or st["symbol"] == want_sym)
                 and (want_res is None or st["res"] == want_res)
                 and not st["loading"] for st in sts) and any(st["cells"] > 0 for st in sts)
        cells = [st["cells"] for st in sts]
        stable = stable + 1 if (ok and cells == last_cells) else 0
        last_cells = cells
        if stable >= 2:
            return sts[0]
        time.sleep(1.5)
    raise TVError("charts did not settle within %ds (last state %s)" % (timeout_s, sts))


def _nse(sym: str) -> str:
    """TradingView spells NSE tickers with '_' where the exchange uses '-' or '&'
    (BAJAJ-AUTO -> NSE:BAJAJ_AUTO, M&M -> NSE:M_M). Any other spelling resolves to
    nothing and every study on the chart reports a runtime 'resolve error'."""
    s = sym.strip().upper().replace("-", "_").replace("&", "_")
    return s if ":" in s else "NSE:" + s


def _res(tf: str) -> str:
    t = str(tf).strip().lower().replace("m", "")
    return {"d": "1D", "1d": "1D", "daily": "1D", "w": "1W", "1w": "1W"}.get(t, t)


def read_panels(bars_n: int = BARS_N) -> dict:
    """Merge every chart tab: S5 lives on one, S4 on the other. Symbol/TF must agree
    across tabs or the read is refused — two different names in one prompt is worse
    than no read."""
    reads = []
    for raw in _tv_all(READ_JS % {"n": bars_n}):
        r = json.loads(raw)
        if r.get("error"):
            raise TVError(r["error"])
        reads.append(r)
    d = reads[0]
    for r in reads[1:]:
        if (r["symbol"], r["res"]) != (d["symbol"], d["res"]):
            raise TVError("chart tabs disagree: %s·%s vs %s·%s — pass a symbol and --tf so "
                          "both are switched together" % (d["symbol"], d["res"], r["symbol"], r["res"]))
        seen = {s["name"] for s in d["studies"]}
        d["studies"] += [s for s in r["studies"] if s["name"] not in seen]
        if not d.get("bars") and r.get("bars"):
            d["bars"] = r["bars"]
        d["errors"] += r.get("errors", [])
    if not d.get("studies"):
        raise TVError("panel path not found — no study exposed table cells. Either S4/S5 "
                      "are not on this chart, or TradingView renamed its internals.")
    for s in d["studies"]:
        s["cells"].sort(key=lambda c: (c["tid"], c["row"], c["col"]))
    return d


# ---------------------------------------------------------------------------------------
# Rendering the read for the model (and for --dump)
# ---------------------------------------------------------------------------------------
def _table_rows(cells: list[dict]) -> list[str]:
    rows: dict[tuple, dict] = {}
    for c in cells:
        rows.setdefault((c["tid"], c["row"]), {})[c["col"]] = c
    out = []
    for key in sorted(rows):
        cols = rows[key]
        parts = []
        for col in sorted(cols):
            t = cols[col]["t"].strip()
            tt = cols[col]["tt"].strip()
            if t or tt:
                parts.append(t + (("  ⟨tip: %s⟩" % tt.replace("\n", " / ")) if tt else ""))
        if parts:
            out.append(" | ".join(parts))
    return out


# S5 sections withheld from the model until Jay has fine-tuned them (11-Sep-2026: the
# geometry classifier printed "Descending triangle · upper 4928 · lower 4968 · width -1.0x
# ATR" on TITAN — upper below lower). Rows from a header in this set up to the next section
# header are dropped, and S5's drawn labels/lines (the same levels) go with them.
S5_SKIP_SECTIONS = ("I · GEOMETRY", "II · LEVELS", "VI · READ")   # READ is the geometry in prose


def _is_s5(name: str) -> bool:
    return name.startswith("S5")


def _filter_s5_rows(rows: list[str]) -> list[str]:
    out, skipping = [], False
    for r in rows:
        head = r.strip()
        is_hdr = len(head) > 3 and head[:6].strip()[:1] in "IVX" and " · " in head[:12]
        if is_hdr:
            skipping = any(head.startswith(k) for k in S5_SKIP_SECTIONS)
            if skipping:
                out.append(head.split("—")[0].strip() + " — [withheld: not yet fine-tuned]")
                continue
        if not skipping:
            out.append(r)
    return out


def _is_s4(name: str) -> bool:
    return name.startswith("Section 4") or name.startswith("S4 ")


def render_read(d: dict) -> str:
    L = ["CHART: %s · %s   read %s IST" % (d["symbol"], d["res"], datetime.now().strftime("%Y-%m-%d %H:%M"))]
    for s in sorted(d["studies"], key=lambda s: 0 if _is_s4(s["name"]) else 1):
        L.append("")
        L.append("=" * 8 + " %s " % s["name"] + "=" * 8)
        rows = _table_rows(s["cells"])
        if _is_s5(s["name"]):
            L.extend(_filter_s5_rows(rows))
            continue                      # its labels/lines ARE the withheld levels
        L.extend(rows)
        if s["labels"]:
            L.append("-- drawn labels (price · text)")
            for lb in sorted(s["labels"], key=lambda x: -(x["y"] or 0))[:40]:
                L.append("  %.2f  %s" % (lb["y"], lb["t"].replace("\n", " / ")))
        hz = [ln for ln in s["lines"] if ln["y1"] == ln["y2"]]
        if hz:
            L.append("-- horizontal lines: " + ", ".join("%.2f" % ln["y1"] for ln in sorted(hz, key=lambda x: -x["y1"])[:30]))
        if s["boxes"]:
            L.append("-- boxes (hi–lo · text)")
            for b in sorted(s["boxes"], key=lambda x: -max(x["y1"], x["y2"]))[:30]:
                L.append("  %.2f–%.2f  %s" % (max(b["y1"], b["y2"]), min(b["y1"], b["y2"]), b["t"].replace("\n", " / ")))
    bars = d.get("bars") or []
    if bars:
        L.append("")
        L.append("-- last %d bars (%s)  time · O H L C V" % (len(bars), d["res"]))
        for b in bars:
            ts = datetime.fromtimestamp(b[0]).strftime("%d-%b %H:%M")
            L.append("  %s  %.2f %.2f %.2f %.2f  %d" % (ts, b[1], b[2], b[3], b[4], b[5] or 0))
    if d.get("errors"):
        L.append("-- read errors: " + "; ".join(d["errors"]))
    return "\n".join(L)


def s4_verdict_line(d: dict) -> str:
    """The S4 VERDICT row text, for the log — NOT for the model's anchor."""
    for s in d["studies"]:
        if not _is_s4(s["name"]):
            continue
        for r in _table_rows(s["cells"]):
            if r.upper().startswith("VERDICT") or r.upper().startswith("TRIGGER"):
                return r[:220]
    return ""


# ---------------------------------------------------------------------------------------
# Position context (held? pyramid class?) — cheap file reads, never blocking
# ---------------------------------------------------------------------------------------
def position_context(symbol: str) -> str:
    sym = symbol.split(":")[-1].upper()
    lines = []
    try:
        import pyramid_logic
        df = pyramid_logic.load_open_positions()
        if not df.empty:
            row = df[df["symbol"].astype(str).str.upper() == sym]
            if not row.empty:
                r = row.iloc[0]
                lines.append("HELD: qty %s @ %.2f · stop %s · target %s · %s · setup %s · %s days"
                             % (int(r["quantity"]), r["buy_price"], r["stoploss"], r["target"],
                                r.get("timeframe") or "?", r.get("setup") or "?", r.get("days_held")))
    except Exception as e:
        lines.append("journal read failed: %s" % e)
    try:
        import pandas as pd
        p = os.path.join(HERE, "FINAL_Portfolio_Picks.csv")
        if os.path.exists(p):
            pf = pd.read_csv(p)
            row = pf[pf["Symbol"].astype(str).str.upper() == sym]
            if not row.empty:
                r = row.iloc[0]
                lines.append("PYRAMID: %s · R %s · add-SL %s · %s"
                             % (r.get("Pyr_Class"), r.get("R_Mult"), r.get("Add_SL"), r.get("Pyr_Trigger")))
    except Exception as e:
        lines.append("portfolio picks read failed: %s" % e)
    return "\n".join(lines) if lines else "NOT HELD — this would be a new entry."


# ---------------------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------------------
SYSTEM = """You are a senior NSE price-action trader sitting beside Jay, an independent systematic
swing/positional trader (Weinstein stage analysis, Minervini leadership, supply/demand zones,
S/R with ageing, 75/125-min triggers inside a daily/weekly context). You are his second pair of
eyes, not a tip service and not a compliance officer.

You are given the COMPLETE contents of his S4 Entry Trigger panel and S5 Analysis panel from
the live chart, the drawn levels, the last bars, and whether he already holds the name.

YOUR JOB IS TO DELIBERATE, NOT TO ECHO. S4 already prints a mechanical VERDICT and SUMMARY —
they are a fixed template that restates rows and cannot weigh one against another. Treat them
as ONE opinion among the inputs, considered LAST. Read every field yourself.

HOW TO WEIGH (this desk's doctrine, measured on its own trades):
- Context outranks trigger: Stage 2 with rising 30-WMA, RS leadership, RRG LEADING/IMPROVING,
  sector not Stage 4 — these decide whether a trigger is worth taking at all.
- Location is the gate that expires. A FRESH demand zone (untested), a controlling zone, a
  Monthly/Weekly zone containing price, an S/R level with few tests — strong. Tested zones,
  MTTWR levels, AVWAP/EMA-only location — weak. "Weak location" GO is a momentum chase.
- Volume is CONTEXT-DEPENDENT: a breakout needs RV ≥ 1.0 and a pullback into a zone does NOT
  (median RV on at-value bars is 0.63, and low RV there is not predictive of failure). Do not
  fail a pullback for breakout volume. Do fail a breakout for RV < 1.
- Room — INFORMATION, NEVER A VETO ON ITS OWN. Measured 11-Sep-2026 on 331 GO-timed trades
  (docs/PREREG_room_obstacle_class.md): 77% had < 1R to the first obstacle, and those trades
  did NOT do worse (mean +0.21R vs -0.17R for the rest; hit-T1 identical). The first
  obstacle — whatever its class: Daily S/R, pivot, supply band, weekly level — was punched
  through 63-77% of the time. Blue sky (no obstacle) was the WORST bucket.
  So: name the first obstacle and its distance, use it to anchor T1 / a partial, note that
  T1/T2 may sit beyond it, and grade it TOLERABLE. A near obstacle plus OTHER evidence of
  supply (bleeding delta into it, a rejection wick at it, a call wall with heavy OI, Stage 3
  context) can add up to FATAL — the obstacle alone never does. Do not write "no room" as
  a deciding factor.
- Extension: > 2.5 ATR above the daily EMA20 is a warning, > 4 is a veto for a fresh entry;
  wait for the pullback the panel names.
- Trade type decides the reward bar: swing 2R/4R, positional 3R/5R. Nothing under 2R.
- A Stage 3/4 name is NO TRADE regardless of the trigger. Blue-sky Stage-2 leaders inside a
  supply band near ATH are continuation pivots (buy the break above, not here), not SKIPs.
PARTICIPATION — use these ACTIVELY, they are where the panel earns its keep, not decoration:
- Futures OI (S4 OI row, "positioning basis"): price↑ OI↑ = LONG BUILD-UP, the strongest
  confirmation of a trigger. price↓ OI↑ = SHORT BUILD-UP: sellers pressing — a pullback buy
  needs a stronger location, but if a trigger then fires ON VOLUME those shorts are the fuel.
  price↑ OI↓ = SHORT COVERING: weaker than a long build, expect it to fade without follow-
  through. price↓ OI↓ = LONG UNWINDING: exhaustion, often the last leg of a pullback.
  Options where shown: a call wall / max-pain above is a ROOM obstacle like a supply zone;
  a put wall below is support; PCR extremes are contrarian.
- AVWAP (Low / BO / Gap anchors): price above a RISING AVWAP = buyers since that anchor are in
  profit and defending; a reclaim of AVWAP-BO on volume is a legitimate trigger; a rejection
  from below it is a fail. AVWAP is LOCATION only in confluence with a zone/level, never
  alone — alone it is a momentum chase.
- Volume Profile (POC/VAH/VAL): inside the value area = rotation, POC is the magnet, VAL is
  the buy location, VAH the first obstacle. Close ABOVE VAH on volume = acceptance/imbalance,
  a breakout that can travel; a poke above VAH that closes back inside = rejection. HVN =
  support/resistance, LVN = fast travel (little room-cost, little support).
- Footprint / order-flow delta: positive delta on a DOWN bar at a level = ABSORPTION (buyers
  taking what sellers offer — location confirmed); negative delta on an UP bar at a high =
  BLEEDING/distribution (the breakout is being sold into). Cumulative 20-bar delta is the
  trend of participation; a delta divergence at a new low/high is a reversal tell. Use delta
  to BREAK TIES the price gates leave open (RV borderline, tested vs fresh zone) — it is a
  bar-level proxy, so it grades, it does not veto on its own.
- Read participation as ONE story: e.g. short build-up + absorption at VAL + AVWAP-Low
  holding = trapped shorts on a defended floor (strong long); long build-up + bleeding
  delta above VAH = late longs being distributed to (fade the GO).
- S5's remaining sections are explanatory: use them to resolve S4's ambiguities (is the
  low RV a pullback or a fade? does the delta support the level?). Sections marked
  [withheld] are not available — do not guess them.

TONE RULES — these are not optional:
1. Case FOR first, honestly weighted. Then case AGAINST, each risk marked FATAL or TOLERABLE.
2. A GO with a clean context and location is a TAKE. "Risks remain" is never a reason to pass.
3. Say what a GOOD version of this setup looks like and how close this one is.
4. Every PASS must name the ONE change that makes it a TAKE. If you cannot, it is a WAIT.
5. You may talk him OUT of a trade the panel armed. You never talk him INTO one it did not.
6. Where S4's own rows contradict each other (e.g. "in a demand zone" vs "between zones"),
   say so and say which you believe and why.
7. His chart-read has veto. End with what would make you change your mind.
8. Only reason from what is in the read. If S4 or S5 is absent, say "S4 not on chart" in
   WHERE S4 IS TOO BLUNT and never infer what it would have said. A field showing "-" or
   "n/a" is unknown, not neutral and not a fail.

OUTPUT — three parts, these exact headings. Part 1 is a full ANALYSIS of the panels, written
as a trader walking a colleague through the chart: every section gets a short paragraph
(3-6 sentences) that quotes the panel's numbers and says what they MEAN, not just what
they are. Part 2 deliberates. Part 3 recommends. Do not skip a section — if the panel has
nothing for it, say so in one line.

ANALYSIS
1. CONTEXT & TREND STACK — stage (weekly 2×2), 30-WMA/50-DMA/200-DMA position and slope,
   weekly/daily/chart-TF trend agreement or conflict, RS vs N500 and sector, RRG quadrant
   and direction, sector stage, catalyst/setup type. What kind of trade is this allowed
   to be?
2. LOCATION — every zone containing or near price by TF (fresh/tested/controlling,
   score, distal), S/R levels with tests and age, AVWAP anchors and whether price is
   above/below them, Volume-Profile VAL/POC/VAH, daily EMA20 distance. Is this a place
   where buyers have shown up before, or dead air?
3. ROOM & OBSTACLES — first obstacle above, what it is, distance in % and R, the next one
   beyond it, and whether T1/T2 sit beyond them. Where a partial makes sense. (Room is
   information here — it is not a gate; see the doctrine.)
4. TRIGGER & GATES — each chip P·L·V·B·Q·F with its number (RV x/floor, bar close-%,
   which PA patterns fired and their Σ, confluence n/23, arrival style), whether this is
   a breakout-type or pullback-type trigger and therefore which volume standard applies,
   extension vs the daily EMA20, bar-ok.
5. PARTICIPATION — futures OI change and basis (long/short build-up, covering,
   unwinding), options (PCR, max pain, call/put walls) where shown, footprint delta on
   the bar and 20-bar cumulative, absorption vs bleeding, delta divergence. One story.
6. STRUCTURE (S5) — whatever S5 sections are present: Wyckoff / sweep / range-edge, and
   anything not marked withheld.
7. THE PANEL'S OWN PLAN — entry method as printed (and whether it is a real retest or a
   market fill), stop and its basis, T1/T2 with R, trade type, house gates (2R / 20%).
   Is the plan coherent with the analysis above?
8. CONTRADICTIONS — anywhere the panel disagrees with itself (S4 vs v67 vs S5, or two S4
   rows), and which side you believe.

DELIBERATION
CASE FOR   (weighted, best points first)
CASE AGAINST   (each line ends with [FATAL] or [TOLERABLE]; FATAL means it alone blocks the trade)
WHERE S4 IS TOO BLUNT   (what its mechanical ruling gets wrong or misses, and what a GOOD
   version of this setup would look like vs how close this one is)

RECOMMENDATION
RULING: TAKE | TAKE · reduced size | WAIT for <specific bar/level/event> | PASS | NO TRADE (stage)
DECIDING FACTOR   (one sentence)
PLAN   (entry method · stop · T1/T2 with R · trade type — take from the panel, correct it only if you say why)
FLIPS IF   (one sentence)
"""


def build_prompt(read_txt: str, pos_txt: str) -> str:
    return ("POSITION CONTEXT\n%s\n\n%s\n\nDeliberate now. S4's VERDICT and SUMMARY rows above are "
            "one mechanical opinion; weigh them last." % (pos_txt, read_txt))


# ---------------------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------------------
def ask_claude(prompt: str, model: str = DEFAULT_MODEL) -> str:
    key = os.getenv("S4_REVIEW_ANTHROPIC_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("S4_REVIEW_ANTHROPIC_KEY / ANTHROPIC_API_KEY not set")
    r = requests.post(CLAUDE_BASE + "/v1/messages",
                      headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                               "content-type": "application/json"},
                      json={"model": model, "max_tokens": 2500, "system": SYSTEM,
                            "messages": [{"role": "user", "content": prompt}]},
                      timeout=180)
    if r.status_code != 200:
        raise RuntimeError("Claude %s: %s" % (r.status_code, r.text[:300]))
    return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text").strip()


def ask_gemini(prompt: str, model: str = GEMINI_MODEL) -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    from google import genai
    client = genai.Client(api_key=key, http_options={"timeout": 180_000})
    resp = client.models.generate_content(model=model, contents=SYSTEM + "\n\n" + prompt)
    return (getattr(resp, "text", "") or "").strip()


def deliberate(prompt: str, provider: str) -> tuple[str, str]:
    order = {"auto": ["gemini"], "claude": ["claude"], "gemini": ["gemini"]}[provider]
    errs = []
    for p in order:
        try:
            txt = ask_claude(prompt) if p == "claude" else ask_gemini(prompt)
            if txt:
                return txt, p + (":" + DEFAULT_MODEL if p == "claude" else ":" + GEMINI_MODEL)
        except Exception as e:
            errs.append("%s: %s" % (p, e))
    raise RuntimeError("no model answered — " + " | ".join(errs))


# ---------------------------------------------------------------------------------------
# R-check — the model's judgement is worth having, its arithmetic is not (flash-lite wrote
# "T1 13.28 (1.5R)" on entry 13.07 / stop 12.60, which is 0.45R). Recompute from the PLAN
# it printed and append the truth; never edit the model's text.
# ---------------------------------------------------------------------------------------
_NUM = r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\d%])"


def _first_num(txt: str):
    m = __import__("re").search(_NUM, txt)
    return float(m.group(1).replace(",", "")) if m else None


def r_check(review: str, min_r: float = 2.0) -> str:
    import re
    m = re.search(r"(?ims)^\W*PLAN\W*$(.*?)(?=^\W*FLIPS IF|\Z)", review)
    if not m:
        return ""
    plan = m.group(1)
    entry = stop = t1 = t2 = None
    said = {}
    for ln in plan.splitlines():
        low = ln.lower()
        body = re.sub(r"^[\s*\-•]+", "", ln)
        if entry is None and re.search(r"entry|buy-?limit|buy-?stop|limit order", low) and "stop:" not in low:
            entry = _first_num(re.sub(r"(?i)^.*?(entry|limit|buy-?stop)[^0-9]*", "", body))
        if stop is None and re.search(r"(?<![a-z-])stop", low) and "buy-stop" not in low:
            stop = _first_num(re.sub(r"(?i)^.*?stop[^0-9]*", "", body))
        for tag in ("T1", "T2"):
            mm = re.search(tag + r"[^0-9]*" + _NUM + r"(?:[^\n(]*\(\s*([\d.]+)\s*R)?", body)
            if mm and (tag == "T1" and t1 is None or tag == "T2" and t2 is None):
                v = float(mm.group(1).replace(",", ""))
                if tag == "T1": t1 = v
                else: t2 = v
                if mm.group(2): said[tag] = float(mm.group(2))
    if entry is None or stop is None or entry <= stop:
        ru = _ruling_line(review).upper()
        if ru.startswith("RULING: PASS") or ru.startswith("RULING: NO TRADE"):
            return ""                                   # no plan expected on a pass
        return "R-CHECK: could not parse entry/stop from PLAN — verify the numbers by hand."
    risk = entry - stop
    out = ["R-CHECK (recomputed): entry %.2f · stop %.2f · risk %.2f (%.1f%%)" % (entry, stop, risk, risk / entry * 100)]
    flags = []
    for tag, tv in (("T1", t1), ("T2", t2)):
        if tv is None:
            continue
        r = (tv - entry) / risk
        line = "  %s %.2f → %.2fR" % (tag, tv, r)
        if tag in said:
            line += " (model said %.1fR)" % said[tag]
            if abs(said[tag] - r) > 0.2:
                flags.append("%s R mis-stated" % tag)
        if tag == "T1" and r < min_r:
            flags.append("T1 %.2fR is under the %.0fR floor" % (r, min_r))
        out.append(line)
    ruling = _ruling_line(review).upper()
    if flags and ruling.startswith("RULING: TAKE"):
        flags.append("ruling is TAKE — the reward bar is NOT met on these numbers")
    if flags:
        out.append("  ⚠ " + " · ".join(flags))
    return "\n".join(out)


# ---------------------------------------------------------------------------------------
# Logging / notify
# ---------------------------------------------------------------------------------------
def _ruling_line(review: str) -> str:
    for ln in review.splitlines():
        t = ln.strip().lstrip("#*• ").strip()          # flash-lite prefixes headings with ###
        if t.upper().startswith("RULING"):
            return t.rstrip("*").strip()[:160]
    return ""


def save_review(symbol: str, tf: str, read_txt: str, review: str, provider: str, s4v: str) -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now()
    sym = symbol.split(":")[-1]
    path = os.path.join(LOG_DIR, "%s_%s_%s.md" % (ts.strftime("%Y%m%d_%H%M%S"), sym, tf))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# %s · %s · %s\n\n%s\n\n---\n\n## PANEL READ\n\n```\n%s\n```\n"
                 % (sym, tf, ts.strftime("%Y-%m-%d %H:%M IST"), review, read_txt))
    new = not os.path.exists(LOG_CSV)
    with open(LOG_CSV, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["ts", "symbol", "tf", "s4_verdict", "ai_ruling", "provider", "file",
                        "my_call", "agreed"])
        w.writerow([ts.strftime("%Y-%m-%d %H:%M"), sym, tf, s4v, _ruling_line(review), provider,
                    os.path.relpath(path, HERE), "", ""])
    return path


def telegram(text: str) -> bool:
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return False
    ok = True
    for i in range(0, len(text), 3900):
        r = requests.post("https://api.telegram.org/bot%s/sendMessage" % tok,
                          json={"chat_id": chat, "text": text[i:i + 3900]}, timeout=20)
        ok = ok and r.status_code == 200
    return ok


# ---------------------------------------------------------------------------------------
def review_one(symbol: str | None, tf: str | None, args) -> int:
    st = switch_chart(symbol, tf)
    d = read_panels(args.bars)
    read_txt = render_read(d)
    if args.dump:
        print(read_txt)
        return 0
    names = [s["name"] for s in d["studies"]]
    if not any(_is_s4(n) for n in names):
        print("S4 is not on this chart (tables found: %s). Add it and re-run." % names, file=sys.stderr)
        return 1
    pos_txt = position_context(d["symbol"])
    review, prov = deliberate(build_prompt(read_txt, pos_txt), args.provider)
    rc_txt = r_check(review)
    if rc_txt:
        review = review.rstrip() + "\n\n" + rc_txt
    tf_lbl = d["res"]
    path = save_review(d["symbol"], tf_lbl, read_txt, review, prov, s4_verdict_line(d))
    head = "%s · %s · %s" % (d["symbol"], tf_lbl, prov)
    print("\n" + head + "\n" + "-" * len(head) + "\n" + review + "\n\nsaved " + os.path.relpath(path, HERE))
    if args.telegram:
        telegram(head + "\n\n" + review)
    return 0


def board_symbols(tf: str) -> list[str]:
    import pandas as pd
    p = os.path.join(HERE, "gm_board_cache_%s.csv" % tf)
    if not os.path.exists(p):
        raise SystemExit("no %s" % p)
    df = pd.read_csv(p)
    # "5/5 GO ·…" today (Gate 5 added 18-Aug); "4/4 GO" on older caches. Match "N/N GO".
    m = df["S4-GO"].astype(str).str.match(r"^[0-9]/[0-9] GO")
    import datetime as _dt
    age_h = (time.time() - os.path.getmtime(p)) / 3600
    print("board %s built %s (%.1fh ago)%s" % (tf, _dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%d-%b %H:%M"),
          age_h, "  ⚠ STALE — rebuild it" if age_h > 6 else ""))
    return df.loc[m, "Symbol"].astype(str).tolist()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("symbol", nargs="?", help="NSE symbol; omit to read the chart as-is")
    ap.add_argument("--tf", help="75 · 125 · D (omit = keep the chart's TF)")
    ap.add_argument("--symbols", help="comma list, reviewed in sequence")
    ap.add_argument("--board", choices=["75m", "125m", "daily"], help="every N/N GO row of that board")
    ap.add_argument("--provider", choices=["auto", "claude", "gemini"], default="auto")
    ap.add_argument("--bars", type=int, default=BARS_N)
    ap.add_argument("--dump", action="store_true", help="print the raw panel read, no model")
    ap.add_argument("--telegram", action="store_true")
    args = ap.parse_args()

    syms: list[str | None]
    if args.board:
        syms = board_symbols(args.board)
        args.tf = args.tf or {"75m": "75", "125m": "125", "daily": "D"}[args.board]
        print("board %s: %d names at GO: %s" % (args.board, len(syms), ", ".join(syms)))
    elif args.symbols:
        syms = [s for s in args.symbols.split(",") if s.strip()]
    else:
        syms = [args.symbol]

    rc, failed = 0, []
    for s in syms:
        try:
            rc |= review_one(s, args.tf, args)
        except TVError as e:
            if "not reachable" in str(e) or "no chart tab" in str(e):
                print("TV: %s" % e, file=sys.stderr); return 2
            print("TV: %s — %s" % (s, e), file=sys.stderr); failed.append(s); rc |= 1
        except Exception as e:
            print("%s: %s" % (s, e), file=sys.stderr); failed.append(s); rc |= 1
    if failed:
        print("\nnot reviewed: %s  (re-run with --symbols %s)" % (", ".join(failed), ",".join(failed)))
    return rc


if __name__ == "__main__":
    sys.exit(main())
