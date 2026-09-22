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
import re
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


def _tv_all(expr: str, targets: list | None = None) -> list:
    return [_tv(expr, t) for t in (targets if targets is not None else _main_targets())]


# ── PHASE-1 TAB (13-Sep-2026) ───────────────────────────────────────────────────
# For an ETF the S4 panel on its UNDERLYING INDEX is the thesis (Phase-1); the ETF's own
# chart is the tradability (Phase-2). A THIRD chart tab, carrying the S4 stack, is
# designated by S4_PHASE1_CHART=<chart id, e.g. AbCdEfGh> in .env; the reviewer switches
# only that tab to the index and reads it separately. Without the setting nothing
# changes: every tab is a main tab, as before.
PHASE1_CHART = os.getenv("S4_PHASE1_CHART", "").strip()
# ── DEDICATED REVIEW TABS (21-Sep-2026) ─────────────────────────────────────────
# By default the reviewer drives EVERY chart tab except the Phase-1 one — which are
# Jay's working tabs, so a review hijacks his chart for ~90 s (31 reviews on 18 Sep ≈
# 49 min). S4_REVIEW_CHARTS=<chart id>,<chart id> names tabs that carry the S4 and S5
# stacks for the reviewer's exclusive use; when set, ONLY those are main targets and
# his tabs are never touched. The ids are the /chart/<id>/ segment of each tab's URL;
# each must be its own layout (Make a copy — a Duplicate shares the id). Nothing here
# calls tab_switch, so a background tab is driven without ever coming to the front.
REVIEW_CHARTS = [c.strip() for c in os.getenv("S4_REVIEW_CHARTS", "").split(",") if c.strip()]
_INDEX_MAP_PATH = os.path.join(HERE, "data", "tv_index_map.json")


def _is_phase1(t: dict) -> bool:
    return bool(PHASE1_CHART) and PHASE1_CHART in t.get("url", "")


def _is_review(t: dict) -> bool:
    return any(c in t.get("url", "") for c in REVIEW_CHARTS)


def _main_targets() -> list[dict]:
    tabs = _chart_targets()
    if REVIEW_CHARTS:
        mine = [t for t in tabs if _is_review(t) and not _is_phase1(t)]
        if mine:
            return mine
        raise TVError("S4_REVIEW_CHARTS is set (%s) but no open chart tab matches — open the "
                      "review layouts, or unset it to drive every tab" % ",".join(REVIEW_CHARTS))
    return [t for t in tabs if not _is_phase1(t)]


def _phase1_target() -> dict | None:
    return next((t for t in _chart_targets() if _is_phase1(t)), None)


def index_for(symbol: str) -> dict | None:
    """{"tv": "NSE:CNXPHARMA", "underlying": "Nifty Pharma", ...} for an ETF, else None."""
    try:
        with open(_INDEX_MAP_PATH, encoding="utf-8") as fh:
            m = json.load(fh)
    except Exception:
        return None
    e = m.get(symbol.strip().upper().replace("NSE:", ""))
    return e if e and e.get("tv") else None


# 21-Sep-2026: 45 s expired on 3 of 3 batch-first reviews (CGPOWER 75/125, GOLDIETF 75) —
# every batch starts at a bar close, when TV is recalculating every study on every tab,
# and the 5 reviews that ran a minute or two later all settled. Default 90 s; env override.
SETTLE_S = int(os.getenv("S4_SETTLE_S", "90") or 90)


def switch_chart(symbol: str | None, tf: str | None, timeout_s: int | None = None,
                 targets: list | None = None) -> dict:
    """Set symbol/TF, then wait until every study has recalculated and the cell count is
    stable. Returns the READY_JS state. `targets` limits the switch to those tabs
    (default: the main tabs, i.e. everything but the Phase-1 tab)."""
    if timeout_s is None:
        timeout_s = SETTLE_S
    sym_js = 'chart.setSymbol(%s);' % json.dumps(_nse(symbol)) if symbol else ""
    res_js = 'chart.setResolution(%s);' % json.dumps(_res(tf)) if tf else ""
    want_sym = _nse(symbol) if symbol else None
    want_res = _res(tf) if tf else None
    tabs0 = targets if targets is not None else _main_targets()
    _urls = {t["url"] for t in tabs0}
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
        for r in _tv_all(SWITCH_JS % {"sym": sym_js, "res": res_js}, tabs0):
            if str(r).startswith("ERR"):
                raise TVError(r)
        time.sleep(2.0)
    last_cells, stable, t0, sts = None, 0, time.time(), []
    while time.time() - t0 < timeout_s:
        tgts = [t for t in _chart_targets() if t["url"] in _urls]
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
    """TradingView spells NSE tickers with '_' where the exchange uses '-'
    (BAJAJ-AUTO -> NSE:BAJAJ_AUTO) but KEEPS the ampersand (NSE:M&MFIN is the live
    chart symbol — tv_health_check, 10-Sep-2026; the tv-sync had the same wrong
    assumption and one holding silently never plotted). Any other spelling resolves
    to nothing and every study reports a runtime 'resolve error'."""
    s = sym.strip().upper()
    if ":" in s:
        return s                       # an exchange-qualified ticker (index map) is final
    return "NSE:" + s.replace("-", "_")


def _res(tf: str) -> str:
    t = str(tf).strip().lower().replace("m", "")
    return {"d": "1D", "1d": "1D", "daily": "1D", "w": "1W", "1w": "1W"}.get(t, t)


def read_panels(bars_n: int = BARS_N, targets: list | None = None) -> dict:
    """Merge every chart tab: S5 lives on one, S4 on the other. Symbol/TF must agree
    across tabs or the read is refused — two different names in one prompt is worse
    than no read. `targets` limits the read (default: the main tabs)."""
    reads = []
    for raw in _tv_all(READ_JS % {"n": bars_n}, targets):
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
            # 18-Sep: an index with no volume series (NIFTY_CAPITAL_MKT, NIFTY_IND_DEFENCE,
            # NIFTY200MOMENTM30) delivers 5-element bars — the Phase-1 read died on b[5].
            vol = b[5] if len(b) > 5 else 0
            L.append("  %s  %.2f %.2f %.2f %.2f  %d" % (ts, b[1], b[2], b[3], b[4], vol or 0))
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
  So: name the first obstacle and its distance and grade it TOLERABLE. It is the FIRST TEST
  of the trade, not its target. T1/T2 follow the R-canon (swing 2R/4R · positional 3R/5R)
  — when the panel's plan prints a T1 sitting ON the obstacle below 2R (tagged ·lvl), say
  so, REPLACE it with the canon T1 in your PLAN, and treat the obstacle as where you watch
  for a reaction or take a small partial at most. Never carry a sub-2R T1 into a TAKE. A near obstacle plus OTHER evidence of
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
  Options (S4 "Options OI" row) are NOT optional when the row carries numbers - name every
  field: PCR (below ~0.6 = call-heavy, bearish positioning; above ~1.2 = put-heavy; extremes
  are contrarian), max pain vs price and which way it PULLS into expiry, ATM dOI (writers
  PULLING = a sharp move is likelier; writers ADDING = pinned), and the writer strikes
  "S x / R y". The call-writer strike and max pain ABOVE price are ROOM obstacles exactly
  like a supply zone - they belong in section 3 and in the T1 discussion; the put-writer
  strike BELOW is a support shelf that belongs in the stop discussion. A plan that puts T1
  under the call wall without saying so is incomplete.
  Two OI-state readings reach you: S4's "Futures OI" row and v67's "FUTURES OI STATE".
  They can disagree - S4 pairs the DAILY OI change with the last CHART-TF bar's direction,
  v67 pairs it with the daily futures close - so on a 75m/125m chart they read different
  windows. When they differ, say so in section 8 and take v67's state for the day's
  positioning (OI is a daily series; the daily price leg is the coherent pair); keep S4's
  basis level and prose. Never report a build-up state without checking both rows.
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
ETFs — TWO PHASES when a PHASE-1 block is present:
- Phase-1 is the S4 stack on the ETF's UNDERLYING INDEX. An ETF is a bet on that index,
  so the index decides the thesis: its stage and trend stack, its location, whether ITS
  trigger fired and on what volume, its room. An index in Stage 3/4, or blocked at
  location, is NO TRADE for the ETF whatever the ETF's own chart prints. Index breadth,
  sector RRG and the index's own OI (NIFTY/BANKNIFTY/FINNIFTY have futures) live here.
- Phase-2 is the ETF's own chart: tradability. ETF volume is thin and RV runs low by
  construction; weigh the INDEX's volume for the trigger and the ETF's for whether it
  can be filled. AVWAP/VP on the ETF are execution levels; the ETF's zones are the
  index's zones scaled, so prefer the index's when they disagree. Tracking error and
  NAV premium are not on the panels — say so rather than invent them.
- HOUSE RULE (Jay, 13-Sep-2026): INDEX ARM = ETF WAIT. If the index's own S4 TRIGGER row
  is not GO — ARM, WAIT, no PA, no volume, no location, anything but GO — the ETF cannot be
  TAKE, whatever the ETF chart prints. Rule WAIT and name the index gate that is missing;
  the ETF's own trigger firing first is the normal order of events and is not a reason
  to front-run the index. An index in Stage 3/4 is NO TRADE.
- Deliberate the two as one story (index thesis → ETF entry). Where only the ETF was
  read, say the index was not read and do not infer it.
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
   beyond it, and whether T1/T2 sit beyond them. Include the derivatives ceilings where
   present: the call-writer strike, max pain if above, the futures basis if above price.
   Where a partial makes sense. (Room is information here — it is not a gate; see the
   doctrine.)
4. TRIGGER & GATES — each chip P·L·V·B·Q·F with its number (RV x/floor, bar close-%,
   which PA patterns fired and their Σ, confluence n/23, arrival style), whether this is
   a breakout-type or pullback-type trigger and therefore which volume standard applies,
   extension vs the daily EMA20, bar-ok.
5. PARTICIPATION — futures OI change and basis (long/short build-up, covering,
   unwinding; S4 row AND v67 row, flag if they differ), then options BY FIELD when the
   row has numbers: PCR and its read, max pain vs price and its pull, ATM dOI (writers
   pulling/adding), writer strikes S/R and where they sit vs the stop and T1. Then
   footprint delta on the bar and 20-bar cumulative, absorption vs bleeding, delta
   divergence. One story - and if the name is cash-only, one line saying so.
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
LEVEL VALIDATION   (EXACTLY four lines, one per level, in this order — ENTRY, STOP, T1, T2.
   Each line: the level you are proposing, then "supported by" a named fact with its NUMBER,
   then "against" a named fact with its NUMBER, then "flips if" the one observation that
   would move that level. Use the derivatives and the flow here — walls, max pain, futures
   basis, OI state, footprint delta — that is what this section is for; structure alone is
   not an answer for a level that has a wall in front of it. Where the LEVEL CHECK pre-read
   named a cap, the level you write MUST be the capped one. Where a field is absent (a
   cash-only name), write "no derivatives" rather than inventing one. One line each, no
   prose paragraphs.
   A CEILING IS NOT A TARGET. Max pain is an expiry magnet and a wall is where writers
   defend - never set T1 or T2 AT one. Scale BEFORE it. And if the reachable R to the
   nearest ceiling is under the canon floor for the trade type, the honest answer is that
   the trade is not available AT THIS ENTRY - rule WAIT for a lower entry, or PASS - not a
   sub-canon T1. A 0.4R plan is a losing trade written down politely.)
PLAN   (state the TRADE TYPE first, then entry method · stop · T1/T2 with R — the R
   canon follows the trade type: positional 3R/5R, swing 2R/4R; never write a 2R T1 on a
   positional plan. Take levels from the panel, correct them only if you say why. Do not
   label an R you have not computed from entry and stop.)
FLIPS IF   (one sentence)
"""


_OI_STATES = ("long build-up", "short build-up", "short covering", "long unwinding")


def oi_digest(read_txt: str) -> tuple[str, str]:
    """Deterministic derivatives pre-read, in the spirit of r_check: the model is not
    trusted to notice that S4's "Futures OI" row and v67's "FUTURES OI STATE" name
    different states (flash-lite wrote "v67 confirms this" against a row that said the
    opposite), nor to carry every options field into its section 5. Returns
    (note_for_prompt, line_for_output); both empty for a cash-only name."""
    low = read_txt.lower()
    s4 = v67 = ""
    m = re.search(r"^futures oi \|\s*oi\s+([a-z\- ]+?)\s+[+\-]?\d", low, re.M)
    if m:
        s4 = m.group(1).strip()
    m = re.search(r"^futures oi state \|\s*([a-z\- ]+?)\s*\(", low, re.M)
    if m:
        v67 = m.group(1).strip()
    if s4 not in _OI_STATES and v67 not in _OI_STATES:
        return "", ""
    parts, out = [], []
    if s4 and v67 and s4 != v67:
        parts.append("OI STATE CONFLICT: S4's Futures OI row says %s; v67's FUTURES OI STATE says %s. "
                     "They pair the same daily OI change with different price legs (S4: last chart-TF "
                     "bar; v67: daily futures close). Report BOTH in section 8, take v67's %s as the "
                     "day's positioning, and do not write that they agree."
                     % (s4.upper(), v67.upper(), v67.upper()))
        out.append("OI-CHECK: S4 %s vs v67 %s \u2014 CONFLICT (v67's daily read governs)" % (s4, v67))
    elif s4 and v67:
        out.append("OI-CHECK: S4 and v67 agree \u2014 %s" % s4)
    m = re.search(r"^options oi \|(.*)$", read_txt, re.M | re.I)
    if m and "no options" not in m.group(1).lower():
        fields = [f.strip() for f in re.split(r"\s*\u2502\s*", m.group(1)) if f.strip()]
        parts.append("OPTIONS FIELDS PRESENT \u2014 each must be named and read in section 5, and the "
                     "call-writer strike / max pain above price must appear in section 3 as obstacles: "
                     + " \u00b7 ".join(fields))
        out.append("OPTIONS: " + " \u00b7 ".join(fields))
    return ("\n".join(parts), "\n".join(out))


def index_gate(read_txt: str) -> tuple[str, str, bool]:
    """INDEX ARM = ETF WAIT, computed by the script. Reads the PHASE-1 block's S4
    TRIGGER row. Returns (note_for_prompt, line_for_output, blocked)."""
    m = re.search(r"^PHASE-1 · UNDERLYING INDEX of (\S+) — (\S+).*?\n(.*?)^PHASE-2 ·", read_txt, re.S | re.M)
    if not m:
        return "", "", False
    etf, idx, block = m.group(1), m.group(2), m.group(3)
    t = re.search(r"^TRIGGER \| (.*)$", block, re.M)
    if not t:
        return "", "INDEX-CHECK: %s panel had no TRIGGER row — gate not applied" % idx, False
    state = re.sub(r"\s{2,}.*", "", t.group(1)).strip()      # "GO", "no PA", "no volume" ...
    st3 = re.search(r"^VERDICT \| (.*)$", block, re.M)
    stage_no = bool(st3 and re.search(r"NO TRADE|Stage [34]", st3.group(1)))
    if stage_no:
        note = ("INDEX GATE: the underlying index %s is NO TRADE by stage on its own S4 panel. "
                "House rule: the ETF %s is NO TRADE. Do not rule TAKE or WAIT." % (idx, etf))
        return note, "INDEX-CHECK: %s is NO TRADE by stage → %s NO TRADE" % (idx, etf), True
    if state.upper().startswith("GO"):
        return ("INDEX GATE: the underlying index %s reads GO on its own S4 panel — the index "
                "thesis is live; judge the ETF on its own tradability." % idx,
                "INDEX-CHECK: %s trigger GO — ETF may be TAKE" % idx, False)
    note = ("INDEX GATE (house rule, not negotiable): the underlying index %s reads \"%s\" on its "
            "own S4 TRIGGER row, not GO. INDEX ARM = ETF WAIT: the ruling for %s cannot be TAKE "
            "or TAKE · reduced. Rule WAIT for the index trigger (%s), name what the index is "
            "missing, and keep the ETF plan as the plan-in-waiting." % (idx, state, etf, state))
    return note, "INDEX-CHECK: %s trigger \"%s\" (not GO) → %s WAIT by house rule" % (idx, state, etf), True


# ---------------------------------------------------------------------------------------
# LEVEL CHECK — do the derivatives and the flow agree with the plan's four levels?
# ---------------------------------------------------------------------------------------
# 21-Sep-2026 (P1 of the derivatives plan). The panel PRINTS the walls, the basis and the
# delta, and S4 even names them as obstacles ("T1 3640.9 (3.0R ·test 3600.0 call wall)") —
# but nothing ever CAPPED a target or resized a trade because of them, so the plan could
# promise 3.0R through a level option writers are defending. That is the gap Jay named:
# "we have not been leveraging the Futures OI, Options OI and Footprint data to validate
# the Entry, SL, T1 and T2 levels ... this is one of the major reasons I'm losing trades."
#
# DOCTRINE, unchanged: derivatives GRADE, they never GATE. Nothing here changes direction
# or vetoes a setup. It caps a target, flags a stop, and tells you the reachable R — the
# trade stays yours. The canon still applies to what remains: nothing under 2R.
#
# SCOPE: options positioning describes the NEAR-MONTH window, entry to T1. Past ~30 days
# to expiry the walls will have rolled, so T2 on a positional trade is left to structure
# and the wall check on it is reported as context, never as a cap.
#
# Reads only what the panels already carry (deriv_fields), so it is free and cannot drift
# from what Jay sees on the chart.
def _model_levels(review: str) -> dict:
    """entry/stop/t1/t2 as the MODEL wrote them in its PLAN, or {} if absent.

    The printed LEVEL CHECK must validate the plan the reader is looking at. Before the
    deliberation it can only read the PANEL's levels (that is what goes into the prompt);
    afterwards the model may have moved them — on the first live run it capped T1 at the
    call wall, exactly as instructed — and a block still quoting the panel's T1 reads as
    a contradiction of the plan printed two lines above it."""
    m = re.search(r"(?ims)^\W*PLAN\W*$(.*?)(?=^\W*FLIPS IF|\Z)", review or "")
    if not m:
        return {}
    plan, out = m.group(1), {}
    # (\d[\d,]*(?:\.\d+)?) and NOT [\d.]+ - the greedy form swallows the sentence's
    # full stop ("STOP: 3363.4." -> float("3363.4.") raises) and the level silently
    # vanishes, which is how the block ended up quoting the panel's T1 under a plan
    # that had already capped it.
    _N = r"(\d[\d,]*(?:\.\d+)?)"
    for key, pat in (("entry", r"ENTRY[^0-9\n]*" + _N),
                     ("stop",  r"STOP[^0-9\n]*" + _N),
                     ("t1",    r"\bT1\b[^0-9\n]*" + _N),
                     ("t2",    r"\bT2\b[^0-9\n]*" + _N)):
        mm = re.search(pat, plan, re.I)
        if mm:
            try:
                out[key] = float(mm.group(1).replace(",", ""))
            except Exception:
                pass
    return out


def level_check(read_txt: str, review: str = "") -> tuple[str, str]:
    """(note for the prompt, block for the printed review). Empty for a cash-only name
    with no footprint — there is nothing to validate against."""
    d = deriv_fields(read_txt)

    def f(k):
        v = str(d.get(k, "")).replace(",", "").rstrip("%")
        try:
            return float(v)
        except Exception:
            return None

    entry, stop, t1, t2 = f("entry"), f("stop"), f("t1"), f("t2")
    src = "panel"
    ml = _model_levels(review)
    if ml.get("entry") and ml.get("stop"):
        entry, stop = ml["entry"], ml["stop"]
        t1, t2 = ml.get("t1", t1), ml.get("t2", t2)
        src = "the plan above"
    cw, pw, mp = f("call_wall"), f("put_wall"), f("max_pain")
    basis_l, pcr = f("fut_basis_l"), f("pcr")
    oi_state = str(d.get("oi_state", "")).strip()
    fp_delta = str(d.get("fp_delta", "")).strip()
    fp_div = str(d.get("fp_div", "")).strip()
    dte = None
    m = re.search(r"near[- ]month|far[- ]month", read_txt, re.I)

    risk = (entry - stop) if (entry and stop and entry > stop) else None
    lines, flags, caps = [], [], []

    # ── T1 vs the call wall ───────────────────────────────────────────────────────────
    # The fattest call strike at/above spot is where writers are short gamma and defend.
    # A target BEYOND it is a target through someone else's collateral.
    if entry and t1 and cw and risk:
        if entry < cw < t1:
            r_wall = (cw - entry) / risk
            caps.append(("T1", cw, r_wall))
            lines.append("  T1 %.2f is BEYOND the call wall %.2f — reachable R to the wall is %.2fR"
                         % (t1, cw, r_wall))
            if r_wall < 2.0:
                flags.append("the reachable target (%.2fR to the wall) is under the 2R canon floor — "
                             "this is a half-size trade or a skip, not a %.1fR trade" % (r_wall, (t1 - entry) / risk))
            else:
                flags.append("scale at the wall %.2f (%.2fR), do not plan on slicing through it" % (cw, r_wall))
        elif cw and t1 and cw >= t1:
            lines.append("  T1 %.2f sits UNDER the call wall %.2f — the target is inside defended ground ✓"
                         % (t1, cw))
    # ── T2: context only, the walls will have rolled ──────────────────────────────────
    if entry and t2 and cw and t2 > cw:
        lines.append("  T2 %.2f is above the wall too — near-month positioning says nothing that far out; "
                     "T2 rests on structure" % t2)

    # ── the stop vs the put wall ──────────────────────────────────────────────────────
    # The defended floor. A stop ABOVE it is inside the zone a wash-and-hold would tag:
    # price dips to the level writers defend, recovers, and the stop is already gone.
    if entry and stop and pw:
        if stop > pw and pw > (stop - (risk or 0) * 1.5):
            lines.append("  stop %.2f sits ABOVE the put wall %.2f — a wash into the defended floor "
                         "takes you out before the level that is actually held" % (stop, pw))
            flags.append("consider the stop just BELOW the put wall %.2f if structure allows "
                         "(it widens risk — resize, do not just move it)" % pw)
        elif stop <= pw:
            lines.append("  stop %.2f is below the put wall %.2f — the defended floor is inside the trade ✓"
                         % (stop, pw))

    # ── max pain between entry and T1 ─────────────────────────────────────────────────
    if entry and t1 and mp and entry < mp < t1:
        lines.append("  max pain %.2f sits between entry and T1 — expiry pinning pulls against the "
                     "target until the series rolls" % mp)
    elif entry and mp and mp < entry:
        lines.append("  max pain %.2f is BELOW entry — the pin pulls down into expiry" % mp)

    # ── the futures long basis: trapped longs are supply on the way up ────────────────
    if entry and basis_l and t1 and entry < basis_l < t1:
        lines.append("  futures long basis %.2f lies between entry and T1 — trapped longs sell into "
                     "that level to get out flat, so expect supply there" % basis_l)
    if oi_state:
        lines.append("  futures OI: %s" % oi_state)
    if pcr is not None:
        lines.append("  PCR %.2f — %s" % (pcr, "call-heavy, rallies get capped" if pcr < 0.7
                                          else "put-heavy, writers defending the downside" if pcr > 1.3
                                          else "balanced"))

    # ── flow at the trigger ───────────────────────────────────────────────────────────
    if fp_delta:
        neg = fp_delta.startswith("-")
        lines.append("  footprint delta %s on the read bar%s" % (fp_delta, " — sellers into a long" if neg else ""))
        if neg:
            flags.append("flow does not confirm the entry (delta %s) — size down or wait for a bar "
                         "where it does" % fp_delta)
    if fp_div and "bearish" in fp_div.lower():
        flags.append("bearish delta divergence: price made the high, flow did not")

    # A CEILING IS NOT A TARGET (22-Sep-2026). On the first live run with the pre-read in
    # front of it the model parked T1 ON max pain (0.35R) and T2 ON the call wall (1.12R) -
    # it had absorbed "there is a ceiling" and lost "so this is not a trade here". The
    # ceilings cap what is REACHABLE; they do not become the plan.
    for tag, lv in (("T1", t1), ("T2", t2)):
        if not (entry and lv and risk):
            continue
        for nm, cl in (("max pain", mp), ("the call wall", cw)):
            if cl and abs(lv - cl) < 0.002 * cl:
                r = (lv - entry) / risk
                flags.append("%s is parked ON %s %.2f (%.2fR) - a ceiling is not a target; "
                             "scale before it, and if that is all the room there is, the trade "
                             "is not available at this entry" % (tag, nm, cl, r))
    if not lines:
        return "", ""
    # 22-Sep: P3 measured these rules on 195 F&O trades (2024-07 -> 2026-02) and ALL FOUR
    # hypotheses failed their pre-registered bars - H1 (T1 beyond the call wall) failed
    # BACKWARDS on the only cell whose CI excluded zero. The facts are still printed,
    # because a trader should see the wall in front of the target; the header says what
    # the evidence does and does not support so a printed fact is not read as an edge.
    head = ("LEVEL CHECK (derivatives + flow vs %s — they GRADE, never GATE; "
            "the wall/pin rules are UNVALIDATED: P3 22-Sep failed all four)" % src)
    block = "\n".join([head] + lines + (["  ⚠ " + f for f in flags] if flags else []))
    note = (block + "\n\nUse these numbers in section 5. If a cap is named above, the plan's T1 is the "
            "CAPPED level and its R is the capped R — say so explicitly, and if that R is under the "
            "2R canon floor the ruling cannot be a full-size TAKE. Do not restate the whole block; "
            "rule on it.")
    return note, block


def build_prompt(read_txt: str, pos_txt: str) -> str:
    note, _ = oi_digest(read_txt)
    ig, _, _ = index_gate(read_txt)
    if ig:
        note = (ig + "\n" + note) if note else ig
    lv, _ = level_check(read_txt)
    if lv:
        note = (note + "\n\n" + lv) if note else lv
    pre = ("PRE-READ (computed by the script, not negotiable)\n%s\n\n" % note) if note else ""
    return (pre + "POSITION CONTEXT\n%s\n\n%s\n\nDeliberate now. S4's VERDICT and SUMMARY rows above are "
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
_NUM = r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\d%]|\s*[Rx])"
# text between a tag and its price may hold an R-multiple "(2R)" or "2.0R" - skip those,
# they are not prices
_SKIP = r"(?:[^0-9]|\d+(?:\.\d+)?\s*[Rx])*?"


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
        # "125-min close above…" is a TIMEFRAME, not a price — strip TF tokens first
        ln = re.sub(r"(?i)(?<![\d.])\d{1,3}\s*-?\s*(?:mins?|minutes?|m|d|day|w|wk)(?![A-Za-z])", "", ln)
        low = ln.lower()
        body = re.sub(r"^[\s*\-•]+", "", ln)
        if entry is None and re.search(r"entry|buy-?limit|buy-?stop|limit order", low) and "stop:" not in low:
            entry = _first_num(re.sub(r"(?i)^.*?(entry|limit|buy-?stop)[^0-9]*", "", body))
        if stop is None and re.search(r"(?<![a-z-])stop", low) and "buy-stop" not in low:
            stop = _first_num(re.sub(r"(?i)^.*?stop[^0-9]*", "", body))
        # "T1/T2: 34.10 (2R) / 36.14 (4R)" — the pair form; a per-tag scan trips on the
        # digit in "T2" and misses T1 entirely
        pair = re.search(r"T1\s*/\s*T2" + _SKIP + _NUM + r"(?:[^/\n]*\(\s*([\d.]+)\s*R\))?\s*/\s*" + _NUM
                         + r"(?:[^\n(]*\(\s*([\d.]+)\s*R\))?", body)
        if pair and t1 is None and t2 is None:
            t1 = float(pair.group(1).replace(",", "")); t2 = float(pair.group(3).replace(",", ""))
            if pair.group(2): said["T1"] = float(pair.group(2))
            if pair.group(4): said["T2"] = float(pair.group(4))
            continue
        for tag in ("T1", "T2"):
            mm = re.search(tag + r"(?![/\d])" + _SKIP + _NUM + r"(?:[^\n(T]*\(\s*([\d.]+)\s*R\))?", body)
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
    pos = bool(re.search(r"(?i)positional", plan)) and not re.search(r"(?i)swing(?!\s*low)", plan.split("Type")[-1] if "Type" in plan else plan)
    c1, c2 = (3.0, 5.0) if pos else (2.0, 4.0)
    out = ["R-CHECK (recomputed): entry %.2f · stop %.2f · risk %.2f (%.1f%%)" % (entry, stop, risk, risk / entry * 100),
           "  canon %s: T1 %.2f (%.0fR) · T2 %.2f (%.0fR)  ← use these; the model's arithmetic is not reliable"
           % ("positional 3R/5R" if pos else "swing 2R/4R", entry + c1 * risk, c1, entry + c2 * risk, c2)]
    flags, floor_miss = [], False
    for tag, tv in (("T1", t1), ("T2", t2)):
        if tv is None:
            continue
        r = (tv - entry) / risk
        line = "  %s %.2f → %.2fR" % (tag, tv, r)
        if tag in said:
            line += " (model said %.1fR)" % said[tag]
            if abs(said[tag] - r) > 0.2:
                flags.append("%s R mis-stated" % tag)
        if tag == "T1" and r < c1 - 0.05:
            flags.append("T1 %.2fR is under the %.0fR %s floor" % (r, c1, "positional" if pos else "swing"))
            floor_miss = True
        out.append(line)
    ruling = _ruling_line(review).upper()
    if floor_miss and ruling.startswith("RULING: TAKE"):
        flags.append("ruling is TAKE — the reward bar is NOT met on these numbers; use the canon T1")
    if flags:
        out.append("  ⚠ " + " · ".join(flags))
    return "\n".join(out)


# ---------------------------------------------------------------------------------------
# Logging / notify
# ---------------------------------------------------------------------------------------
def lv_audit(review: str) -> str:
    """Did the model actually RULE on the four levels? (22-Sep-2026, P2.)

    P1 put the derivative facts in front of the model; a required section is only worth
    anything if its absence is noticed. This is the same idea as r_check flagging a
    mis-stated R: the script verifies the SHAPE of the answer, never its content. It
    cannot check whether the reasoning is good - only that each of the four levels was
    addressed with a number rather than skipped or hand-waved."""
    m = re.search(r"(?ims)^\W*LEVEL VALIDATION[^\n]*(.*?)(?=^\W*PLAN\W*$|\Z)", review or "")
    if not m:
        return "LV-AUDIT: the LEVEL VALIDATION block is MISSING — the four levels were not ruled on."
    body = m.group(1)
    missing = [tag for tag in ("ENTRY", "STOP", "T1", "T2")
               if not re.search(r"(?im)^\s*[-*•]?\s*\**\s*" + tag + r"\b", body)]
    nonum = [tag for tag in ("ENTRY", "STOP", "T1", "T2") if tag not in missing
             and not re.search(r"(?im)^\s*[-*•]?\s*\**\s*" + tag + r"\b[^\n]*\d", body)]
    out = []
    if missing:
        out.append("no line for " + ", ".join(missing))
    if nonum:
        out.append("no number on " + ", ".join(nonum))
    return ("LV-AUDIT: " + " · ".join(out)) if out else ""


def _ruling_line(review: str) -> str:
    for ln in review.splitlines():
        t = ln.strip().lstrip("#*• ").strip()          # flash-lite prefixes headings with ###
        if t.upper().startswith("RULING"):
            return t.rstrip("*").strip()[:160]
    return ""


DERIV_FIELDS = ["entry", "stop", "t1", "t2", "oi_state", "fut_basis", "fut_basis_l",
                "fut_basis_s", "pcr", "max_pain", "call_wall", "put_wall", "atm_doi",
                "fp_delta", "fp_cum", "fp_div"]


def deriv_fields(read_txt: str) -> dict:
    """The derivative and order-flow numbers the panels already print, pulled out as
    columns so a review can be SCORED on them later (21-Sep-2026, P0 of the derivatives
    plan). Nothing here judges; it records. Every field is "" when absent — a missing
    wall must never read as a wall at zero, and a cash-only name legitimately has none.

    These are the inputs to the level-validation rules (P1): did price respect the call
    wall on the way to T1, was the stop under the put wall, did flow confirm at entry.
    Without them in the log there is no way to answer that in three months.

    Parsed from the ROW each field belongs to, never from the whole panel: "T1 367.25
    (3.0R ...)" and the SUMMARY's prose both contain "T1", and a panel-wide search
    returned the R-multiple as the price."""
    d = {k: "" for k in DERIV_FIELDS}

    def row(name: str) -> str:
        m = re.search(r"^" + name + r"[^|]*\|(.*?)(?=\n[A-Z0-9 ]{2,40}\s*\||\Z)",
                      read_txt, re.M | re.I | re.S)
        return m.group(1) if m else ""

    def take(src: str, pat: str, key: str, grp: int = 1):
        m = re.search(pat, src, re.I)
        if m:
            d[key] = m.group(grp).strip()

    plan = row("Entry . SL . T1 . T2")
    take(plan, r"\bE\s+([\d.]+)", "entry")
    take(plan, r"\bSL\s+([\d.]+)", "stop")
    take(plan, r"\bT1\s+([\d.]+)", "t1")
    take(plan, r"\bT2\s+([\d.]+)", "t2")

    fut = row("Futures OI")
    take(fut, r"OI\s+([A-Za-z]+[ A-Za-z\-]*?)\s+[+\-]?[\d.]+%", "oi_state")
    take(fut, r"basis\s+is\s+(ABOVE|BELOW)\s+price", "fut_basis")
    take(fut, r"basis\s+L\s+([\d.]+)", "fut_basis_l")
    take(fut, r"\u00b7\s*S\s+([\d.]+)", "fut_basis_s")

    opt = row("Options OI")
    take(opt, r"PCR\s+([\d.]+)", "pcr")
    take(opt, r"Max pain\s+([\d.]+)", "max_pain")
    take(opt, r"writers\s+S\s+([\d.]+)", "put_wall")
    take(opt, r"writers\s+S\s+[\d.]+\s*\u00b7\s*R\s+([\d.]+)", "call_wall")
    take(opt, r"ATM\s*\u0394OI\s*([+\-]?[\d.]+%)", "atm_doi")

    # S5 PARTICIPATION — the reviewer merges the S5 tab, so the footprint lands here too
    take(read_txt, r"([+\-][\d.]+K?)\s+(?:buyers|sellers)", "fp_delta")
    take(read_txt, r"cum\s+\d+b\s+([+\-][\d.]+K?)", "fp_cum")
    take(read_txt, r"(bearish divergence|bullish divergence|none - price and flow point the same way)", "fp_div")
    return d


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
                        "my_call", "agreed"] + DERIV_FIELDS)
        dv = deriv_fields(read_txt)
        w.writerow([ts.strftime("%Y-%m-%d %H:%M"), sym, tf, s4v, _ruling_line(review), provider,
                    os.path.relpath(path, HERE), "", ""] + [dv[k] for k in DERIV_FIELDS])
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
def phase1_read(symbol: str | None, tf: str | None, bars_n: int) -> str:
    """The index-chart block for an ETF: switch the Phase-1 tab to the underlying index
    at the same TF, read its panels, render them under their own header. Empty string
    when the name is not an ETF, has no mapped index, or no Phase-1 tab is designated —
    and says which, so the prompt never has to guess."""
    if not symbol:
        return ""
    idx = index_for(symbol)
    if not idx:
        return ""
    p1 = _phase1_target()
    if p1 is None:
        return ("PHASE-1 · UNDERLYING INDEX %s (%s): no Phase-1 chart tab is designated "
                "(S4_PHASE1_CHART unset) — index panels NOT read.\n" % (idx["tv"], idx.get("underlying", "")))
    try:
        switch_chart(idx["tv"], tf, targets=[p1])
        d1 = read_panels(bars_n, targets=[p1])
    except TVError as e:
        return "PHASE-1 · UNDERLYING INDEX %s: read failed — %s\n" % (idx["tv"], e)
    body = render_read(d1)
    return ("=" * 78 + "\nPHASE-1 · UNDERLYING INDEX of %s — %s (%s)%s\n"
            "The index chart carries the same S4 stack. Read it as the THESIS; the ETF panels "
            "below are the TRADABILITY.\n" % (symbol.upper(), idx["tv"], idx.get("underlying", ""),
                                            ("  [%s]" % idx["note"]) if idx.get("note") else "")
            + body + "\n" + "=" * 78 + "\nPHASE-2 · THE ETF ITSELF\n")


def review_one(symbol: str | None, tf: str | None, args) -> int:
    st = switch_chart(symbol, tf)
    d = read_panels(args.bars)
    read_txt = phase1_read(symbol, tf, args.bars) + render_read(d)
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
    _, oi_txt = oi_digest(read_txt)
    _, lv_txt = level_check(read_txt, review)
    _, ig_txt, ig_block = index_gate(read_txt)
    if ig_block and re.search(r"RULING:?\**:?\s*\**\s*TAKE", review):
        # the model ruled TAKE against the house rule: overrule it in print, loudly
        ig_txt += "\n  ⚠ the model ruled TAKE — OVERRULED: WAIT (index trigger not GO)"
        review = re.sub(r"(RULING:?\**:?\s*\**\s*)TAKE[^\n]*", r"\1WAIT — index trigger not GO (house rule; model had ruled TAKE)", review, count=1)
    lva_txt = lv_audit(review)
    for extra in (rc_txt, lv_txt, lva_txt, oi_txt, ig_txt):
        if extra:
            review = review.rstrip() + "\n\n" + extra
    tf_lbl = d["res"]
    path = save_review(d["symbol"], tf_lbl, read_txt, review, prov, s4_verdict_line(d))
    head = "%s · %s · %s" % (d["symbol"], tf_lbl, prov)
    print("\n" + head + "\n" + "-" * len(head) + "\n" + review + "\n\nsaved " + os.path.relpath(path, HERE))
    if args.telegram:
        telegram(head + "\n\n" + review)
    global LAST_RESULT
    LAST_RESULT = {"rc": 0, "review": review, "path": path, "head": head, "symbol": d["symbol"], "tf": tf_lbl}
    return 0


LAST_RESULT: dict = {}


def review_symbol(symbol: str, tf: str | None = None, provider: str = "auto",
                  bars: int = BARS_N, send_telegram: bool = False) -> dict:
    """Programmatic entry (13-Sep-2026, for s4_alert_review): review ONE name and return
    {"rc", "review", "path", "head"}. Same code path as the CLI."""
    import types
    global LAST_RESULT
    LAST_RESULT = {}
    args = types.SimpleNamespace(bars=bars, dump=False, provider=provider, telegram=send_telegram)
    rc = review_one(symbol, tf, args)
    out = dict(LAST_RESULT) if LAST_RESULT else {}
    out.setdefault("rc", rc); out.setdefault("review", ""); out.setdefault("path", ""); out.setdefault("head", "")
    return out


def board_symbols(tf: str, live: bool = False) -> list[str]:
    import pandas as pd
    p = os.path.join(HERE, "gm_board_cache_%s.csv" % tf)
    if not os.path.exists(p):
        raise SystemExit("no %s" % p)
    df = pd.read_csv(p)
    # "5/5 GO ·…" today (Gate 5 added 18-Aug); "4/4 GO" on older caches. Match "N/N GO".
    m = df["S4-GO"].astype(str).str.match(r"^[0-9]/[0-9] GO")
    if live and "Category" in df.columns:
        # --live: every Buy Trigger Live row (bull AND recovery), not only 5/5. A recovery
        # turn usually reads 3/5 · no vol - dry volume IS the recovery shape - so the 5/5
        # filter alone reviewed the two recovery names that happened to clear volume and
        # skipped the rest (Jay, 13-Sep).
        m = m | df["Category"].astype(str).str.startswith("Buy Trigger Live")
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
    ap.add_argument("--live", action="store_true", help="with --board: also every 'Buy Trigger Live' row (bull + recovery), not only 5/5")
    ap.add_argument("--provider", choices=["auto", "claude", "gemini"], default="auto")
    ap.add_argument("--bars", type=int, default=BARS_N)
    ap.add_argument("--dump", action="store_true", help="print the raw panel read, no model")
    ap.add_argument("--telegram", action="store_true")
    args = ap.parse_args()

    syms: list[str | None]
    if args.board:
        syms = board_symbols(args.board, live=args.live)
        args.tf = args.tf or {"75m": "75", "125m": "125", "daily": "D"}[args.board]
        print("board %s: %d names at %s: %s" % (args.board, len(syms), "GO or Buy Trigger Live" if args.live else "GO", ", ".join(syms)))
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
    if not args.dump:
        try:
            import build_review_portal
            build_review_portal.build()          # the Reviewer Log page, always current
        except Exception as e:
            print("portal rebuild failed: %s" % e, file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
