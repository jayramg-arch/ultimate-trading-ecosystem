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
    S4_REVIEW_ANTHROPIC_KEY (or ANTHROPIC_API_KEY) in .env — primary, claude-opus-5;
    GEMINI_API_KEY as fallback (gemini-3.1-pro-preview). Override with S4_REVIEW_MODEL /
    S4_REVIEW_GEMINI_MODEL / S4_REVIEW_BASE_URL. Never reads ANTHROPIC_MODEL/BASE_URL.

USAGE
    python s4_review.py                       # whatever the chart shows now
    python s4_review.py TITAN --tf 75         # switch symbol/TF first, wait for recalc
    python s4_review.py --symbols A,B,C --tf 125
    python s4_review.py --board 75m           # every 4/4 row of gm_board_cache_75m.csv
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
from tv_bind_s4 import _chart_target, _evaluate            # noqa: E402  (same CDP channel)

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
GEMINI_MODEL = os.getenv("S4_REVIEW_GEMINI_MODEL", "gemini-3.1-pro-preview")


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
  var n=0, loading=false;
  chart.getAllStudies().forEach(function(s){var a=chart.getStudyById(s.id);
    if(a&&a.isLoading&&a.isLoading())loading=true;
    var st=a&&a._study; if(st&&st.graphics){var g=st.graphics(); if(g.dwgtablecells){g.dwgtablecells().forEach(function(c){
      if(c._primitivesDataById)n+=c._primitivesDataById.size; else if(c.forEach)c.forEach(function(cc){if(cc._primitivesDataById)n+=cc._primitivesDataById.size;});});}}});
  return JSON.stringify({symbol:chart.symbol(),res:chart.resolution(),loading:loading,cells:n});
}catch(e){return JSON.stringify({error:String(e&&e.message||e)});}})();
"""


class TVError(RuntimeError):
    pass


def _tv(expr: str):
    tgt = _chart_target()
    if not tgt:
        raise TVError("TradingView not reachable on :9222 — LAUNCH_TRADINGVIEW_CDP.bat")
    out = _evaluate(tgt["webSocketDebuggerUrl"], expr)
    if "error" in out:
        raise TVError(str(out["error"]))
    return out["value"]


def switch_chart(symbol: str | None, tf: str | None, timeout_s: int = 45) -> dict:
    """Set symbol/TF, then wait until every study has recalculated and the cell count is
    stable. Returns the READY_JS state."""
    sym_js = 'chart.setSymbol(%s);' % json.dumps(_nse(symbol)) if symbol else ""
    res_js = 'chart.setResolution(%s);' % json.dumps(_res(tf)) if tf else ""
    if sym_js or res_js:
        r = _tv(SWITCH_JS % {"sym": sym_js, "res": res_js})
        if str(r).startswith("ERR"):
            raise TVError(r)
        time.sleep(2.0)
    want_sym = _nse(symbol) if symbol else None
    want_res = _res(tf) if tf else None
    last_cells, stable, t0 = -1, 0, time.time()
    while time.time() - t0 < timeout_s:
        st = json.loads(_tv(READY_JS))
        if st.get("error"):
            raise TVError(st["error"])
        ok = ((want_sym is None or st["symbol"] == want_sym)
              and (want_res is None or st["res"] == want_res)
              and not st["loading"] and st["cells"] > 0)
        stable = stable + 1 if (ok and st["cells"] == last_cells) else 0
        last_cells = st["cells"]
        if stable >= 2:
            return st
        time.sleep(1.5)
    raise TVError("chart did not settle within %ds (last state %s)" % (timeout_s, st))


def _nse(sym: str) -> str:
    s = sym.strip().upper()
    return s if ":" in s else "NSE:" + s


def _res(tf: str) -> str:
    t = str(tf).strip().lower().replace("m", "")
    return {"d": "1D", "1d": "1D", "daily": "1D", "w": "1W", "1w": "1W"}.get(t, t)


def read_panels(bars_n: int = BARS_N) -> dict:
    raw = _tv(READ_JS % {"n": bars_n})
    d = json.loads(raw)
    if d.get("error"):
        raise TVError(d["error"])
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


def _is_s4(name: str) -> bool:
    return name.startswith("Section 4") or name.startswith("S4 ")


def render_read(d: dict) -> str:
    L = ["CHART: %s · %s   read %s IST" % (d["symbol"], d["res"], datetime.now().strftime("%Y-%m-%d %H:%M"))]
    for s in sorted(d["studies"], key=lambda s: 0 if _is_s4(s["name"]) else 1):
        L.append("")
        L.append("=" * 8 + " %s " % s["name"] + "=" * 8)
        L.extend(_table_rows(s["cells"]))
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
- Room: measured to the FIRST obstacle. Under 1R to a supply zone or fresh resistance is
  fatal for a new entry; a pivot shelf (Pv·) or MTTWR level is a weaker ceiling than a zone.
- Extension: > 2.5 ATR above the daily EMA20 is a warning, > 4 is a veto for a fresh entry;
  wait for the pullback the panel names.
- Trade type decides the reward bar: swing 2R/4R, positional 3R/5R. Nothing under 2R.
- A Stage 3/4 name is NO TRADE regardless of the trigger. Blue-sky Stage-2 leaders inside a
  supply band near ATH are continuation pivots (buy the break above, not here), not SKIPs.
- S5's geometry, order flow and READ are explanatory: use them to resolve S4's ambiguities
  (e.g. is the low RV a pullback or a fade? does order-flow divergence support the level?).

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

OUTPUT — exactly these headings, terse, numbers quoted from the panel:
CASE FOR
CASE AGAINST   (each line ends with [FATAL] or [TOLERABLE])
WHERE S4 IS TOO BLUNT
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
    order = {"auto": ["claude", "gemini"], "claude": ["claude"], "gemini": ["gemini"]}[provider]
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
# Logging / notify
# ---------------------------------------------------------------------------------------
def _ruling_line(review: str) -> str:
    for ln in review.splitlines():
        if ln.strip().upper().startswith("RULING"):
            return ln.strip()[:160]
    return ""


def save_review(symbol: str, tf: str, read_txt: str, review: str, provider: str, s4v: str) -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now()
    sym = symbol.split(":")[-1]
    path = os.path.join(LOG_DIR, "%s_%s_%s.md" % (ts.strftime("%Y%m%d_%H%M"), sym, tf))
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
    m = df["S4-GO"].astype(str).str.startswith("4/4")
    return df.loc[m, "Symbol"].astype(str).tolist()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("symbol", nargs="?", help="NSE symbol; omit to read the chart as-is")
    ap.add_argument("--tf", help="75 · 125 · D (omit = keep the chart's TF)")
    ap.add_argument("--symbols", help="comma list, reviewed in sequence")
    ap.add_argument("--board", choices=["75m", "125m", "daily"], help="all 4/4 rows of that board")
    ap.add_argument("--provider", choices=["auto", "claude", "gemini"], default="auto")
    ap.add_argument("--bars", type=int, default=BARS_N)
    ap.add_argument("--dump", action="store_true", help="print the raw panel read, no model")
    ap.add_argument("--telegram", action="store_true")
    args = ap.parse_args()

    syms: list[str | None]
    if args.board:
        syms = board_symbols(args.board)
        args.tf = args.tf or {"75m": "75", "125m": "125", "daily": "D"}[args.board]
        print("board %s: %d names at 4/4" % (args.board, len(syms)))
    elif args.symbols:
        syms = [s for s in args.symbols.split(",") if s.strip()]
    else:
        syms = [args.symbol]

    rc = 0
    for s in syms:
        try:
            rc |= review_one(s, args.tf, args)
        except TVError as e:
            print("TV: %s" % e, file=sys.stderr); return 2
        except Exception as e:
            print("%s: %s" % (s, e), file=sys.stderr); rc |= 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
