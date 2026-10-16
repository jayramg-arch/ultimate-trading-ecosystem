#!/usr/bin/env python3
"""Render a docs/*.md file as a Library page in the house style (16-Oct-2026).

The page shell (fonts, colour tokens, light/dark theme, table and list styles) is lifted from
docs/portal/36_pca_study.html, so a new page looks like the rest of the Library. Handles the
markdown the docs use: # title, ## sections, ### sub-heads, pipe tables, - / 1. lists with
indented continuation lines, paragraphs, **bold**, *italic*, `code`.

    python tools/md_to_portal.py docs/38_Paper_Trades_Postmortem.md docs/portal/38_paper_trades_postmortem.html \
        --eyebrow "Doc 38 · Evidence · 16 Oct 2026" --dek "One-paragraph summary shown under the title"
"""
from __future__ import annotations

import argparse
import html
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(HERE, "docs", "portal", "36_pca_study.html")


def _inline(t: str) -> str:
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])", r"<i>\1</i>", t)
    return t


def _slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:60]


def convert(md: str) -> tuple[str, str]:
    lines = md.splitlines()
    title, out, i, open_sec = "", [], 0, False
    para: list[str] = []

    def flush():
        if para:
            out.append("<p>" + _inline(" ".join(x.strip() for x in para)) + "</p>")
            para.clear()

    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# ") and not title:
            title = ln[2:].strip()
            i += 1
            continue
        if ln.startswith("## "):
            flush()
            if open_sec:
                out.append("</section>")
            h = ln[3:].strip()
            out.append('<section id="%s">\n<p class="pt">%s</p>' % (_slug(h), _inline(h)))
            open_sec = True
            i += 1
            continue
        if ln.startswith("### "):
            flush()
            out.append("<h3>%s</h3>" % _inline(ln[4:].strip()))
            i += 1
            continue
        if ln.strip().startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                h = "".join("<th>%s</th>" % _inline(c) for c in rows[0])
                b = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % _inline(c) for c in r) for r in rows[1:])
                out.append('<div class="tw"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (h, b))
            continue
        m = re.match(r"^(\s*)(- |\d+\. )(.*)$", ln)
        if m and not m.group(1):
            flush()
            tag = "ol" if m.group(2)[0].isdigit() else "ul"
            items = []
            while i < len(lines):
                mm = re.match(r"^(- |\d+\. )(.*)$", lines[i])
                if mm:
                    items.append(mm.group(2).strip())
                    i += 1
                    while i < len(lines) and lines[i].startswith("  ") and lines[i].strip() \
                            and not re.match(r"^\s*(- |\d+\. )", lines[i].lstrip()[:3] + " "):
                        items[-1] += " " + lines[i].strip()
                        i += 1
                    continue
                break
            out.append('<%s class="how">%s</%s>' % (tag, "".join("<li>%s</li>" % _inline(x) for x in items), tag))
            continue
        if not ln.strip():
            flush()
            i += 1
            continue
        para.append(ln)
        i += 1
    flush()
    if open_sec:
        out.append("</section>")
    return title, "\n".join(out)


def render(md_path: str, out_path: str, eyebrow: str, dek: str) -> None:
    shell = open(SHELL, encoding="utf-8").read()
    head = shell[:shell.index('<header class="mast">')]
    with open(md_path, encoding="utf-8") as f:
        title, body = convert(f.read())
    short = re.sub(r"^\d+\s*·\s*", "", title).split("—")[0].strip()
    head = re.sub(r"<title>.*?</title>", "<title>%s</title>" % html.escape(short), head, count=1)
    # concatenation, not %-formatting: the shell's CSS is full of '%' (width:100%, etc.)
    page = (head + '<header class="mast"><div class="mast-in">\n  <p class="eyebrow">' + html.escape(eyebrow)
            + '</p>\n  <h1>' + _inline(short) + '</h1>\n  <p class="dek">' + _inline(dek)
            + '</p>\n</div></header>\n<div class="wrap"><main>\n' + body + '\n</main></div>\n'
            + '<footer><em>Source: ' + os.path.relpath(md_path, HERE).replace("\\", "/") + '.</em></footer>\n')
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print("wrote", out_path, len(page), "bytes")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("md")
    ap.add_argument("out")
    ap.add_argument("--eyebrow", required=True)
    ap.add_argument("--dek", required=True)
    a = ap.parse_args()
    render(a.md, a.out, a.eyebrow, a.dek)
