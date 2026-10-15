#!/usr/bin/env python3
"""Strategic Daily Briefing as a Library page + a Markdown file (15-Oct-2026, Jay).

    python briefing_page.py          build from market_intel.json + Strategic_Briefing_AI.md

Writes
  docs/portal/37_strategic_briefing.html   the latest briefing, in the Library's own look
  reports/briefing/Strategic_Briefing_YYYYMMDD.md   a dated Markdown copy (kept)

The numbers come from market_intel.json (quant_analyst, book = briefing_book: live Dhan
holdings + the journal's plan fields). The AI section is Strategic_Briefing_AI.md (Gemini),
shown as written. Run by workflow_strategic_briefing.py after the PDF.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
INTEL = os.path.join(HERE, "market_intel.json")
AI_MD = os.path.join(HERE, "Strategic_Briefing_AI.md")
PAGE = os.path.join(HERE, "docs", "portal", "37_strategic_briefing.html")
MD_DIR = os.path.join(HERE, "reports", "briefing")
SECTOR_CAP = 25.0


def inr(v, dec=0) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "–"
    neg, v = v < 0, abs(v)
    whole, _, frac = f"{v:.{dec}f}".partition(".")
    if len(whole) > 3:
        head, tail, parts = whole[:-3], whole[-3:], []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        whole = ",".join(([head] if head else []) + parts + [tail])
    return ("-" if neg else "") + whole + ("." + frac if frac else "")


def _css() -> str:
    """The Library's <head> + <style>, taken from Doc 26 so every page reads the same."""
    p = os.path.join(HERE, "docs", "portal", "26_operating_loop.html")
    try:
        s = open(p, encoding="utf-8").read()
        return s[: s.index("</style>") + len("</style>")].replace(
            "<title>GM + S4 Operating Loop</title>", "<title>Strategic Briefing</title>")
    except Exception:
        return '<meta charset="utf-8">\n<title>Strategic Briefing</title>'


def _inline(t: str) -> str:
    t = html.escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", t)
    t = re.sub(r"`([^`]+)`", r'<span class="m">\1</span>', t)
    return t


def md_to_html(md: str) -> str:
    """Enough Markdown for the AI briefing: headings, bold/italic, lists, tables, rules."""
    out, para, lst, tbl = [], [], None, []

    def flush_para():
        nonlocal para
        if para:
            out.append("<p>" + " ".join(_inline(x) for x in para) + "</p>")
            para = []

    def flush_list():
        nonlocal lst
        if lst:
            out.append(f"</{lst}>")
            lst = None

    def flush_tbl():
        nonlocal tbl
        if tbl:
            rows = [r for r in tbl if not re.match(r"^\|?\s*:?-{2,}", r.replace(" ", ""))]
            cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
            h = "".join(f"<th>{_inline(c)}</th>" for c in cells[0])
            b = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in cells[1:])
            out.append(f'<div class="tw"><table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>')
            tbl = []

    for raw in md.splitlines():
        line = raw.rstrip()
        if line.strip().startswith("|"):
            flush_para(); flush_list()
            tbl.append(line)
            continue
        flush_tbl()
        if not line.strip():
            flush_para(); flush_list()
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            flush_para(); flush_list()
            lvl = min(len(m.group(1)) + 1, 4)
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
        elif line.strip() in ("---", "***"):
            flush_para(); flush_list()
            out.append("<hr>")
        elif re.match(r"^\s*(?:[-*•])\s+", line):
            flush_para()
            if lst != "ul":
                flush_list(); out.append("<ul>"); lst = "ul"
            out.append(f"<li>{_inline(re.sub(r'^\s*[-*•]\s+', '', line))}</li>")
        elif re.match(r"^\s*\d+\.\s+", line):
            flush_para()
            if lst != "ol":
                flush_list(); out.append("<ol>"); lst = "ol"
            out.append(f"<li>{_inline(re.sub(r'^\s*\d+\.\s+', '', line))}</li>")
        else:
            flush_list()
            para.append(line.strip())
    flush_tbl(); flush_para(); flush_list()
    return "\n".join(out)


def _rows(intel: dict) -> tuple[list[dict], dict]:
    rows, tot = [], {"inv": 0.0, "val": 0.0}
    for i in intel.get("Portfolio") or []:
        p, t = i.get("Position") or {}, i.get("Technical") or {}
        inv, val = float(p.get("Invested") or 0), float(p.get("CurrentValue") or 0)
        tot["inv"] += inv
        tot["val"] += val
        cmp_, th = float(i.get("CMP") or 0), p.get("ThesisSL")
        th_gap = ((cmp_ - float(th)) / cmp_ * 100) if (th and cmp_) else None
        rows.append({"sym": i.get("Symbol"), "sector": (i.get("Fundamental") or {}).get("Sector") or "Unassigned",
                     "plan": p.get("Plan") or "–", "stage": t.get("Stage") or "–", "rs": t.get("RS_Rating"),
                     "cmp": cmp_, "avg": p.get("AvgPrice"), "qty": p.get("Qty"), "inv": inv, "val": val,
                     "pnl_pct": p.get("PnL_pct"), "r": p.get("R"), "dsl": p.get("DhanSL"), "th": th,
                     "ini": p.get("InitialSL"), "th_gap": th_gap,
                     "verdict": (i.get("Analysis") or {}).get("Verdict") or "–"})
    rows.sort(key=lambda r: -r["val"])
    return rows, tot


def _flag(r: dict) -> str:
    out = []
    st = str(r["stage"]).upper()
    if "4" in st:
        out.append("Stage 4")
    elif "3" in st:
        out.append("Stage 3")
    if r["th_gap"] is not None and r["th_gap"] <= 1.0:
        out.append("at/below thesis" if r["th_gap"] <= 0 else "within 1% of thesis")
    if r["r"] is not None and r["r"] <= -1.0:
        out.append("beyond -1R")
    return " · ".join(out)


def build() -> int:
    if not os.path.exists(INTEL):
        print("market_intel.json not found - run quant_analyst.py first")
        return 2
    intel = json.load(open(INTEL, encoding="utf-8"))
    ai = open(AI_MD, encoding="utf-8").read() if os.path.exists(AI_MD) else ""
    acc, macro = intel.get("Account") or {}, intel.get("Macro") or {}
    rows, tot = _rows(intel)
    pnl = tot["val"] - tot["inv"]
    pnl_pct = pnl / tot["inv"] * 100 if tot["inv"] else 0.0
    cash = float(acc.get("AvailableCash") or 0)
    stamp = str(intel.get("Timestamp") or "")
    day = (stamp[:10] or dt.date.today().isoformat())
    sec = {}
    for r in rows:
        sec[r["sector"]] = sec.get(r["sector"], 0.0) + r["val"]
    secs = sorted(sec.items(), key=lambda x: -x[1])
    flagged = [r for r in rows if _flag(r)]
    n2 = sum(1 for r in rows if "2" in str(r["stage"]))
    n3 = sum(1 for r in rows if "3" in str(r["stage"]))
    n4 = sum(1 for r in rows if "4" in str(r["stage"]))
    nifty, vix = macro.get("Nifty 50") or {}, macro.get("India VIX") or {}
    ctx = (acc.get("Context") or "").strip()

    # ---------------------------------------------------------------- Markdown copy ----
    md = [f"# Strategic Daily Briefing — {day}", "",
          f"*Book: {len(rows)} positions from {acc.get('BookSource', 'dhan')} · generated {stamp}*", "",
          "## The book", "",
          "| Invested (cost) | Market value | Unrealised P&L | Cash | Stage 2 / 3 / 4 |",
          "|---|---|---|---|---|",
          f"| ₹{inr(tot['inv'])} | ₹{inr(tot['val'])} | ₹{inr(pnl)} ({pnl_pct:+.1f}%) | ₹{inr(cash)} | {n2} / {n3} / {n4} |", "",
          "## Market", "",
          f"- Nifty 50: {nifty.get('Trend')} ({nifty.get('Change')}%) · India VIX {vix.get('Current')}"]
    if ctx:
        md += ["", "```", ctx, "```"]
    md += ["", "## Risk first", ""]
    md += ([f"- **{r['sym']}** — {_flag(r)}" for r in flagged] or ["- Nothing flagged."])
    md += ["", "## Positions", "",
           "| Asset | Sector | Plan | Stage | RS | CMP | Avg | P&L | R | Dhan SL | Thesis | Initial | Value |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['sym']} | {r['sector']} | {r['plan']} | {r['stage']} | {r['rs']} | {inr(r['cmp'], 2)} | "
                  f"{inr(r['avg'], 2)} | {(r['pnl_pct'] or 0):+.1f}% | "
                  f"{('%+.2f' % r['r']) if r['r'] is not None else '–'} | {inr(r['dsl'], 2)} | {inr(r['th'], 2)} | "
                  f"{inr(r['ini'], 2)} | ₹{inr(r['val'])} |")
    md += ["", "## Sector weights", "", "| Sector | Value | Weight |", "|---|---|---|"]
    md += [f"| {k} | ₹{inr(v)} | {v / tot['val'] * 100:.1f}%{' ⚠ over 25%' if v / tot['val'] * 100 > SECTOR_CAP else ''} |"
           for k, v in secs] if tot["val"] else []
    if ai.strip():
        md += ["", "---", "", "## AI briefing (Gemini)", "", ai.strip()]
    md_txt = "\n".join(md) + "\n"
    os.makedirs(MD_DIR, exist_ok=True)
    md_path = os.path.join(MD_DIR, f"Strategic_Briefing_{day.replace('-', '')}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_txt)

    # ---------------------------------------------------------------- Library page -----
    e = html.escape
    def tile(lbl, val, sub=""):
        return (f'<div class="kp"><p class="kl">{e(lbl)}</p><p class="kv">{val}</p>'
                + (f'<p class="ks">{sub}</p>' if sub else "") + "</div>")
    pcls = "up" if pnl >= 0 else "dn"
    pos_rows = "".join(
        f"<tr><td class='nm'>{e(r['sym'])}</td><td>{e(r['sector'])}</td><td>{e(r['plan'])}</td>"
        f"<td>{e(str(r['stage']))}</td><td class='n'>{e(str(r['rs']))}</td><td class='n'>{inr(r['cmp'], 2)}</td>"
        f"<td class='n'>{inr(r['avg'], 2)}</td>"
        f"<td class='n {'up' if (r['pnl_pct'] or 0) >= 0 else 'dn'}'>{(r['pnl_pct'] or 0):+.1f}%</td>"
        f"<td class='n'>{('%+.2f' % r['r']) if r['r'] is not None else '–'}</td>"
        f"<td class='n'>{inr(r['dsl'], 2)}</td><td class='n'>{inr(r['th'], 2)}</td><td class='n'>{inr(r['ini'], 2)}</td>"
        f"<td class='n'>₹{inr(r['val'])}</td><td>{e(_flag(r))}</td></tr>" for r in rows)
    sec_rows = "".join(
        f"<tr><td>{e(k)}</td><td class='n'>₹{inr(v)}</td><td class='n'>{v / tot['val'] * 100:.1f}%</td>"
        f"<td><div class='bar'><span style='width:{min(v / tot['val'] * 100 / 40 * 100, 100):.0f}%'"
        f"{' class=over' if v / tot['val'] * 100 > SECTOR_CAP else ''}></span></div></td></tr>"
        for k, v in secs) if tot["val"] else ""
    risk = "".join(f"<li><b>{e(r['sym'])}</b> — {e(_flag(r))}</li>" for r in flagged) or "<li>Nothing flagged.</li>"
    page = [_css(), """
<style>
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:18px 0 0}
.kp{background:var(--surface);border:1px solid var(--rule);padding:10px 12px}
.kl{font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3,#777);margin:0}
.kv{font-family:var(--mono);font-size:20px;font-weight:700;margin:4px 0 0}
.ks{font-size:12px;margin:2px 0 0;color:var(--ink-2)}
.up{color:#1f8a5b}.dn{color:#c0392b}
td.n,th.n{text-align:right;font-family:var(--mono);white-space:nowrap}
td.nm{font-weight:700;white-space:nowrap}
.bar{background:var(--surface-2,#eee);height:8px;width:160px;border-radius:2px}
.bar span{display:block;height:8px;background:#2f7d7a;border-radius:2px}
.bar span.over{background:#c0392b}
pre.ctx{white-space:pre-wrap;font-size:12.5px;background:var(--surface);border:1px solid var(--rule);padding:10px 12px}
.ai h2,.ai h3,.ai h4{margin-top:18px}
</style>""",
            f"""<header class="mast"><div class="mast-in">
  <p class="eyebrow">Doc 37 · Daily · {e(day)}</p>
  <h1>Strategic Briefing</h1>
  <p class="dek">The book as it stands this morning — {len(rows)} positions from {e(str(acc.get('BookSource', 'dhan')))},
  their stops and stage — the market and the exposure rule, and the AI read. Rebuilt every time
  <b>Market Briefing</b> runs on the Dashboard. A dated Markdown copy sits in <span class="m">reports/briefing/</span>.</p>
  <div class="kpis">{tile('Invested (cost)', '₹' + inr(tot['inv']))}{tile('Market value', '₹' + inr(tot['val']))}
  {tile('Unrealised P&L', f"<span class='{pcls}'>₹{inr(pnl)}</span>", f"{pnl_pct:+.1f}%")}
  {tile('Cash', '₹' + inr(cash))}{tile('Stage 2 / 3 / 4', f'{n2} / {n3} / {n4}')}</div>
</div></header>
<div class="wrap"><main>
<section><p class="pt">Market</p><h2>The tape and the exposure rule</h2>
  <p>Nifty 50: {e(str(nifty.get('Trend')))} ({e(str(nifty.get('Change')))}%) · India VIX {e(str(vix.get('Current')))}</p>
  {f'<pre class="ctx">{e(ctx)}</pre>' if ctx else ''}
</section>
<section><p class="pt">Risk first</p><h2>What needs a decision</h2>
  <p class="lede">Stage 3 or 4, at or within 1% of the thesis (a Daily close below it is the exit), or beyond −1R.</p>
  <ul>{risk}</ul>
</section>
<section><p class="pt">Positions</p><h2>The book, largest first</h2>
  <div class="tw"><table><thead><tr><th>Asset</th><th>Sector</th><th>Plan</th><th>Stage</th><th class="n">RS</th>
  <th class="n">CMP</th><th class="n">Avg</th><th class="n">P&amp;L</th><th class="n">R</th><th class="n">Dhan SL</th>
  <th class="n">Thesis</th><th class="n">Initial</th><th class="n">Value</th><th>Flag</th></tr></thead>
  <tbody>{pos_rows}</tbody></table></div>
</section>
<section><p class="pt">Concentration</p><h2>Sector weights</h2>
  <p class="lede">By market value. The house cap is {SECTOR_CAP:.0f}% per sector (red bar = over).</p>
  <div class="tw"><table><thead><tr><th>Sector</th><th class="n">Value</th><th class="n">Weight</th><th></th></tr></thead>
  <tbody>{sec_rows}</tbody></table></div>
</section>
<section class="ai"><p class="pt">AI read</p><h2>Gemini's briefing</h2>
  {md_to_html(ai) if ai.strip() else '<p>No AI briefing this run (Strategic_Briefing_AI.md missing).</p>'}
</section>
<footer><em>Generated by briefing_page.py from market_intel.json and Strategic_Briefing_AI.md · {e(stamp)}.</em>
Markdown copy: <span class="m">{e(os.path.relpath(md_path, HERE))}</span></footer>
</main></div>
"""]
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write("".join(page))
    print(f"[OK] {PAGE}\n[OK] {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(build())
