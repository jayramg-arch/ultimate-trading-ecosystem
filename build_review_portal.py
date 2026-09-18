# -*- coding: utf-8 -*-
"""
build_review_portal.py — The Reviewer Log: every AI review, one page, newest day first.

Reads logs/ai_reviews/*.md (written by s4_review.py) plus logs/ai_review_log.csv (the
S4 verdict, the ruling line, and Jay's my_call / agreed scoring) and renders
docs/portal/31_reviewer_log_v2.html. Regenerated automatically after every review
(s4_alert_review) and at the end of auto-pilot Phase 12; run by hand any time:

    python build_review_portal.py

Retention: nothing is deleted. These are the forward record - the ruling before the
outcome was known - and the scoring columns are the only way the log can ever say
whether the model deserves the trust. The page handles age by presentation: today's
reviews open, older days collapsed, a filter box for symbol / ruling / TF.
"""
from __future__ import annotations

import csv
import html
import os
import re
import sys
from collections import OrderedDict
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "logs", "ai_reviews")
CSV_PATH = os.path.join(HERE, "logs", "ai_review_log.csv")
OUT = os.path.join(HERE, "docs", "portal", "31_reviewer_log_v2.html")   # 18-Sep: new file = new artifact URL (the 2 MB v1 was too costly to republish)

_FN = re.compile(r"^(\d{8})_(\d{4})(\d{2})?_([A-Z0-9&_\-]+)_([A-Za-z0-9]+)\.md$")


def _ruling_class(ruling: str) -> str:
    r = (ruling or "").upper()
    if "NO TRADE" in r:
        return "notrade"
    if r.startswith("TAKE"):
        return "reduced" if "REDUCED" in r else "take"
    if r.startswith("WAIT"):
        return "wait"
    if r.startswith("PASS"):
        return "pass"
    return "other"


def _md_inline(t: str) -> str:
    t = html.escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


def md_to_html(md: str) -> str:
    """Just enough Markdown for the reviews: ###, **, lists, paragraphs, ---."""
    out, para, in_list = [], [], False
    def flush():
        nonlocal para
        if para:
            out.append("<p>" + "<br>".join(_md_inline(x) for x in para) + "</p>")
            para = []
    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush()
            if in_list:
                out.append("</ul>"); in_list = False
            continue
        if line.startswith("### ") or line.startswith("## "):
            flush()
            if in_list:
                out.append("</ul>"); in_list = False
            hd = line.split(" ", 1)[1]
            cls = ' class="taken"' if hd.startswith("TAKEN") else (' class="skipped"' if hd.startswith("SKIPPED") else "")
            out.append("<h4%s>%s</h4>" % (cls, _md_inline(hd)))
        elif line.strip() == "---":
            flush()
            if in_list:
                out.append("</ul>"); in_list = False
            out.append("<hr>")
        elif re.match(r"^\s*(?:[-*•]|\d+\.)\s+", line):
            flush()
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append("<li>%s</li>" % _md_inline(re.sub(r"^\s*(?:[-*•]|\d+\.)\s+", "", line)))
        elif re.match(r"^(R-CHECK|OI-CHECK|OPTIONS|INDEX-CHECK)", line) or line.startswith("  "):
            flush()
            if in_list:
                out.append("</ul>"); in_list = False
            out.append('<div class="chk">%s</div>' % html.escape(line))
        else:
            para.append(line)
    flush()
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def load_csv() -> dict:
    rows = {}
    if not os.path.exists(CSV_PATH):
        return rows
    with open(CSV_PATH, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            key = os.path.basename((r.get("file") or "").replace("\\", "/"))
            if key:
                rows[key] = r
    return rows


def load_reviews() -> list[dict]:
    meta = load_csv()
    items = []
    for fn in os.listdir(LOG_DIR) if os.path.isdir(LOG_DIR) else []:
        m = _FN.match(fn)
        if not m:
            continue
        d, hm, sec, sym, tf = m.groups()
        try:
            txt = open(os.path.join(LOG_DIR, fn), encoding="utf-8").read()
        except Exception:
            continue
        body, _, panel = txt.partition("\n## PANEL READ\n")
        body = re.sub(r"^# .*?\n", "", body, count=1).strip()
        body = re.sub(r"\n---\s*$", "", body)
        panel = panel.strip().strip("`").strip()
        r = meta.get(fn, {})
        ruling = ""
        mm = re.search(r"\*{0,2}RULING:?\*{0,2}:?\s*\*{0,2}\s*([^\n]+)", body)
        if mm:
            ruling = mm.group(1).strip("* ")
        elif r.get("ai_ruling"):
            ruling = r["ai_ruling"].replace("RULING:", "").strip("* ")
        s4 = (r.get("s4_verdict") or "").replace("TRIGGER | ", "").strip()
        checks = [l for l in body.splitlines() if re.match(r"^(R-CHECK|OI-CHECK|INDEX-CHECK)", l)]
        warn = any("⚠" in l for l in body.splitlines() if l.startswith("  "))
        phase1 = "PHASE-1 · UNDERLYING INDEX of" in panel and "index panels NOT read" not in panel
        items.append({
            "file": fn, "date": "%s-%s-%s" % (d[:4], d[4:6], d[6:]),
            "time": "%s:%s" % (hm[:2], hm[2:]), "symbol": sym, "tf": tf,
            "ruling": ruling, "rclass": _ruling_class(ruling), "s4": s4,
            "provider": (r.get("provider") or "").replace("gemini:", ""),
            "my_call": (r.get("my_call") or "").strip(), "agreed": (r.get("agreed") or "").strip(),
            "checks": checks, "warn": warn, "phase1": phase1,
            "body_html": md_to_html(body), "panel": panel,
        })
    items.sort(key=lambda x: (x["date"], x["time"], x["file"]), reverse=True)
    return items


CSS = """
:root{--ground:#F2F3F5;--surface:#FFFFFF;--surface-2:#F7F8FA;--surface-3:#ECEEF1;--ink:#101418;--ink-2:#3B444F;
--muted:#6B7480;--faint:#98A1AC;--rule:#D9DEE4;--rule-soft:#E8ECF0;--acc:#0F6E86;--acc-bg:#E2F0F4;
--take:#0F7A66;--take-bg:#E4F2EE;--reduced:#5B7A1F;--reduced-bg:#EDF3E0;--wait:#9A5B00;--wait-bg:#FBF0DE;
--pass:#44566C;--pass-bg:#E9EDF2;--notrade:#A32B4E;--notrade-bg:#FBE8ED;--warn:#B4551A;
--mono:'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,monospace;--disp:'Archivo','Helvetica Neue',Arial,sans-serif;
--body:'Newsreader',Georgia,'Times New Roman',serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--ground:#101317;--surface:#171B20;--surface-2:#1C2127;--surface-3:#222831;
--ink:#E8ECF1;--ink-2:#BFC7D1;--muted:#8792A0;--faint:#69737F;--rule:#272E37;--rule-soft:#20262E;--acc:#3FA3BD;--acc-bg:#12303A;
--take:#2BB39A;--take-bg:#12302A;--reduced:#9BC24A;--reduced-bg:#26311A;--wait:#E0A23C;--wait-bg:#3A2C10;--pass:#9AA8BB;--pass-bg:#20262E;
--notrade:#E56A8C;--notrade-bg:#3A1A25;--warn:#E8894A}}
:root[data-theme="dark"]{--ground:#101317;--surface:#171B20;--surface-2:#1C2127;--surface-3:#222831;--ink:#E8ECF1;--ink-2:#BFC7D1;
--muted:#8792A0;--faint:#69737F;--rule:#272E37;--rule-soft:#20262E;--acc:#3FA3BD;--acc-bg:#12303A;--take:#2BB39A;--take-bg:#12302A;
--reduced:#9BC24A;--reduced-bg:#26311A;--wait:#E0A23C;--wait-bg:#3A2C10;--pass:#9AA8BB;--pass-bg:#20262E;--notrade:#E56A8C;--notrade-bg:#3A1A25;--warn:#E8894A}
*{box-sizing:border-box}body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--body);font-size:16px;line-height:1.55}
.mast{border-bottom:1px solid var(--rule);background:var(--surface)}.mast-in{max-width:1120px;margin:0 auto;padding:34px 24px 26px}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--acc);margin:0 0 10px}
h1{font-family:var(--disp);font-weight:700;font-size:38px;letter-spacing:-.02em;margin:0 0 10px;line-height:1.05;text-wrap:balance}
.dek{font-size:17px;color:var(--ink-2);max-width:66ch;margin:0 0 20px}
.counts{display:flex;flex-wrap:wrap;gap:28px}.count b{font-family:var(--disp);font-size:26px;display:block;line-height:1;color:var(--ink);font-variant-numeric:tabular-nums}
.count span{font-family:var(--mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.wrap{max-width:1120px;margin:0 auto;padding:22px 24px 60px}
.tools{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 18px}
.tools input{font-family:var(--mono);font-size:13px;padding:8px 12px;border:1px solid var(--rule);border-radius:3px;background:var(--surface);color:var(--ink);min-width:260px}
.chip{font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;padding:4px 10px;border-radius:2px;border:1px solid var(--rule);background:var(--surface);color:var(--muted);cursor:pointer}
.chip.on{border-color:var(--acc);color:var(--acc);background:var(--acc-bg)}
details.day{border:1px solid var(--rule);background:var(--surface);border-radius:3px;margin:0 0 14px}
details.day>summary{list-style:none;cursor:pointer;padding:12px 16px;display:flex;align-items:center;gap:14px;font-family:var(--disp);font-weight:600;font-size:17px}
details.day>summary::-webkit-details-marker{display:none}details.day>summary .n{font-family:var(--mono);font-size:11px;color:var(--muted);letter-spacing:.1em;text-transform:uppercase;font-weight:500}
details.day>summary .tally{margin-left:auto;display:flex;gap:6px}
.rev{border-top:1px solid var(--rule-soft);padding:10px 16px 12px}
.rev summary{list-style:none;cursor:pointer;display:grid;grid-template-columns:52px 120px 46px 1fr auto;gap:12px;align-items:center;font-size:14px}
.rev summary::-webkit-details-marker{display:none}
.t{font-family:var(--mono);font-size:12px;color:var(--faint);font-variant-numeric:tabular-nums}.sym{font-family:var(--disp);font-weight:700;font-size:15px;color:var(--ink)}
.tf{font-family:var(--mono);font-size:11px;color:var(--muted)}.rul{color:var(--ink-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pill{font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;padding:2.5px 8px;border-radius:2px;border:1px solid;white-space:nowrap}
.pill.take{color:var(--take);background:var(--take-bg);border-color:var(--take)}.pill.reduced{color:var(--reduced);background:var(--reduced-bg);border-color:var(--reduced)}
.pill.wait{color:var(--wait);background:var(--wait-bg);border-color:var(--wait)}.pill.pass{color:var(--pass);background:var(--pass-bg);border-color:var(--pass)}
.pill.notrade{color:var(--notrade);background:var(--notrade-bg);border-color:var(--notrade)}.pill.other{color:var(--muted);background:var(--surface-3);border-color:var(--rule)}
.pill.mine{color:var(--acc);background:var(--acc-bg);border-color:var(--acc)}
.s4{font-family:var(--mono);font-size:11.5px;color:var(--muted);margin:6px 0 0 64px}.s4 b{color:var(--ink-2);font-weight:500}
.body{margin:10px 0 0 64px;max-width:78ch;font-size:15px;color:var(--ink-2)}.body h4{font-family:var(--disp);font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--acc);margin:16px 0 6px}.body h4.taken{color:var(--take)}.body h4.skipped{color:var(--pass)}
.body p{margin:0 0 8px}.body ul{margin:0 0 8px 18px;padding:0}.body li{margin:0 0 3px}.body b{color:var(--ink)}.body hr{border:0;border-top:1px solid var(--rule-soft);margin:12px 0}
.body code{font-family:var(--mono);font-size:.9em;background:var(--surface-3);padding:0 4px;border-radius:2px}
.chk{font-family:var(--mono);font-size:12px;color:var(--ink-2);background:var(--surface-2);border-left:3px solid var(--acc);padding:4px 10px;margin:4px 0;white-space:pre-wrap}
.chk.w{border-left-color:var(--warn)}
details.panel{margin:12px 0 0 64px}details.panel summary{font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);cursor:pointer}
details.panel pre{font-family:var(--mono);font-size:11px;line-height:1.45;background:var(--surface-2);border:1px solid var(--rule);padding:12px;overflow-x:auto;max-height:520px;color:var(--ink-2)}
.older{font-family:var(--mono);font-size:11px;color:var(--faint);margin:6px 0 0}
.src{margin:10px 0 0 64px;font-family:var(--mono);font-size:11px;color:var(--muted)}.src a{color:var(--acc);text-decoration:none;border-bottom:1px solid var(--rule)}
.hid{display:none}
.note{border:1px solid var(--rule);border-left:3px solid var(--muted);background:var(--surface);padding:14px 18px;border-radius:3px;margin:24px 0 0;font-size:15px;color:var(--ink-2)}
.note b{color:var(--ink)}
footer{border-top:1px solid var(--rule);background:var(--surface);font-family:var(--mono);font-size:11px;color:var(--muted)}.foot-in{max-width:1120px;margin:0 auto;padding:22px 24px;display:flex;flex-wrap:wrap;gap:16px;justify-content:space-between}
@media (max-width:720px){.rev summary{grid-template-columns:48px 1fr auto;}.rev summary .tf,.rev summary .rul{display:none}.s4,.body,.src,details.panel{margin-left:0}}
"""

JS = """
const q=document.getElementById('q');const chips=[...document.querySelectorAll('.chip')];let flt='';
function apply(){const s=q.value.trim().toLowerCase();document.querySelectorAll('details.rev').forEach(r=>{
 const hay=r.dataset.hay;const ok=(!s||hay.includes(s))&&(!flt||r.dataset.rc===flt);r.classList.toggle('hid',!ok);});
 document.querySelectorAll('details.day').forEach(d=>{const vis=[...d.querySelectorAll('details.rev')].filter(r=>!r.classList.contains('hid')).length;
 d.classList.toggle('hid',vis===0);d.querySelector('.vis').textContent=vis;});}
q.addEventListener('input',apply);chips.forEach(c=>c.addEventListener('click',()=>{const on=c.classList.contains('on');chips.forEach(x=>x.classList.remove('on'));
 flt=on?'':c.dataset.rc;if(!on)c.classList.add('on');apply();}));
"""


FULL_DAYS = 7   # days that carry the full deliberation on the page; older rows are compact


def render(items: list[dict]) -> str:
    days: "OrderedDict[str, list]" = OrderedDict()
    for it in items:
        days.setdefault(it["date"], []).append(it)
    n = len(items)
    tally = {k: sum(1 for i in items if i["rclass"] == k) for k in ("take", "reduced", "wait", "pass", "notrade")}
    scored = sum(1 for i in items if i["my_call"] or i["agreed"])
    agreed = sum(1 for i in items if i["agreed"].lower() in ("y", "yes", "1", "true"))
    out = ['<meta charset="utf-8"><title>The Reviewer Log</title>',
           '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
           '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&display=swap">',
           "<style>%s</style>" % CSS,
           '<header class="mast"><div class="mast-in"><p class="eyebrow">Weinstein Commander · GM + S4 · AI reviewer</p>',
           "<h1>The Reviewer Log</h1>",
           '<p class="dek">Every deliberation the reviewer has written off the S4 / S5 panels — ruling, case for and against, plan, and the script\'s own R / OI / index checks — newest day first. The panel read each one was made from is in its <code>.md</code> under <code>logs/ai_reviews/</code>, linked on the row.</p>',
           '<div class="counts"><div class="count"><b>%d</b><span>Reviews</span></div><div class="count"><b>%d</b><span>Days</span></div>'
           '<div class="count"><b>%d</b><span>Take</span></div><div class="count"><b>%d</b><span>Take · reduced</span></div>'
           '<div class="count"><b>%d</b><span>Wait</span></div><div class="count"><b>%d</b><span>Pass / No trade</span></div>'
           '<div class="count"><b>%d</b><span>Scored by Jay</span></div>%s</div></div></header>'
           % (n, len(days), tally["take"], tally["reduced"], tally["wait"], tally["pass"] + tally["notrade"], scored,
              ('<div class="count"><b>%d</b><span>Agreed</span></div>' % agreed) if scored else ""),
           '<div class="wrap"><div class="tools"><input id="q" type="search" placeholder="filter · symbol, ruling, TF, date…">',
           ''.join('<span class="chip" data-rc="%s">%s</span>' % (k, lbl) for k, lbl in
                   (("take", "Take"), ("reduced", "Reduced"), ("wait", "Wait"), ("pass", "Pass"), ("notrade", "No trade"))),
           "</div>"]
    for di, (day, revs) in enumerate(days.items()):
        dt = datetime.strptime(day, "%Y-%m-%d")
        t = {k: sum(1 for i in revs if i["rclass"] == k) for k in ("take", "reduced", "wait", "pass", "notrade")}
        tal = "".join('<span class="pill %s">%d</span>' % (k, v) for k, v in t.items() if v)
        out.append('<details class="day"%s><summary><span>%s</span><span class="n"><span class="vis">%d</span> reviews</span><span class="tally">%s</span></summary>'
                   % (" open" if di == 0 else "", dt.strftime("%A, %d %B %Y"), len(revs), tal))
        for it in revs:
            hay = html.escape(" ".join([it["symbol"], it["tf"], it["ruling"], it["date"], it["s4"], it["my_call"]]).lower(), quote=True)
            mine = ('<span class="pill mine">%s%s</span>' % (html.escape(it["my_call"]), (" · " + ("agreed" if it["agreed"].lower() in ("y", "yes", "1", "true") else "disagreed")) if it["agreed"] else "")) if (it["my_call"] or it["agreed"]) else ""
            p1 = '<span class="pill other">index read</span>' if it["phase1"] else ""
            out.append('<details class="rev" data-rc="%s" data-hay="%s"><summary><span class="t">%s</span><span class="sym">%s</span><span class="tf">%s</span>'
                       '<span class="rul">%s</span><span style="display:flex;gap:6px;align-items:center"><span class="pill %s">%s</span>%s%s</span></summary>'
                       % (it["rclass"], hay, it["time"], html.escape(it["symbol"]), html.escape(it["tf"] + ("m" if it["tf"].isdigit() else "")),
                          html.escape(it["ruling"]), it["rclass"],
                          {"take": "take", "reduced": "reduced", "wait": "wait", "pass": "pass", "notrade": "no trade", "other": "—"}[it["rclass"]], p1, mine))
            if it["s4"]:
                out.append('<div class="s4">S4 at read: <b>%s</b>%s</div>' % (html.escape(it["s4"]), (" · " + html.escape(it["provider"])) if it["provider"] else ""))
            # 18-Sep: only the last FULL_DAYS days carry the full deliberation; older rows keep
            # the ruling, the script's checks and the .md link, so the page stays a few hundred
            # KB however long the log runs (it had reached 2 MB in a week).
            if di < FULL_DAYS:
                body = it["body_html"].replace('<div class="chk">', '<div class="chk w">') if it["warn"] else it["body_html"]
            else:
                body = "".join('<div class="chk%s">%s</div>' % (" w" if "⚠" in c else "", html.escape(c)) for c in it["checks"]) or '<p class="older">older review — full text in the .md</p>'
            out.append('<div class="body">%s</div>' % body)
            # 18-Sep: the panel read is NOT embedded any more. With it the page ran to 2 MB and
            # grew ~20 KB per review, which made every republish of the artifact prohibitively
            # expensive; the read lives in the .md and is one click away on disk.
            # relative, so the link resolves from file:// on disk AND over SERVE_PORTAL.bat (:8502)
            out.append('<div class="src">panel read · <a href="../../logs/ai_reviews/%s">%s</a></div>'
                       % (html.escape(it["file"]), html.escape(it["file"])))
            out.append("</details>")
        out.append("</details>")
    out.append('<div class="note"><b>Nothing here is ever deleted.</b> Each review is the ruling as written before the outcome was known; the '
               '<code>my_call</code> / <code>agreed</code> columns in <code>logs/ai_review_log.csv</code> are how the log will one day say whether '
               'the model earned its place. This page is regenerated after every review and every evening run '
               '(<code>build_review_portal.py</code>); the published copy is a snapshot.</div></div>')
    out.append('<footer><div class="foot-in"><span>The Reviewer Log · logs/ai_reviews · built %s IST</span><span>%d reviews · flash-lite unless noted</span></div></footer>'
               % (datetime.now().strftime("%d %b %Y %H:%M"), n))
    out.append("<script>%s</script>" % JS)
    return "\n".join(out)


def build() -> str:
    items = load_reviews()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(render(items))
    os.replace(tmp, OUT)
    return OUT


if __name__ == "__main__":
    p = build()
    print("reviewer log -> %s" % os.path.relpath(p, HERE))
