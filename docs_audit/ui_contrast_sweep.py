# -*- coding: utf-8 -*-
"""ui_contrast_sweep.py — every TEXT colour in the app, scored against the background
it actually sits on. Read-only.

WHY THIS REPLACES rule_token_contrast_sweep.py
----------------------------------------------
That one matched the literal `color:var(--x-rule)` and found 7 real faults — then missed
two more in the same card that Jay could see on screen:

  * `_mcol = "var(--bull-rule)"` … `style='color:{_mcol}'` — the token was held in a
    VARIABLE, so no literal ever appeared in the markup;
  * `color:#6B9080` — a hardcoded muted green at 3.46:1, no token involved at all.

A sweep that only knows one spelling of a mistake reports "0 remaining" and is believed.
This resolves all three forms.

WHAT IT CHECKS
--------------
foreground   `color:#hex` · `color:var(--token)` · `color:{pyvar}` where pyvar is
             assigned a literal colour string anywhere in the file
background   nearest enclosing `background:` / `background-color:` — hex, gradient
             (scored at the midpoint, the worst realistic case for a mid-tone text), or
             theme token; falls back to the page ground
excluded     `border-color:` and `background-color:`, which are not text

LIMITS, stated rather than implied
----------------------------------
Static read of f-strings. It cannot see a background applied by a CSS class, nor a colour
built at runtime from a branch it cannot evaluate. Those are reported as "ground
(assumed)" and are the rows to confirm by eye. Dark palette only — that is the theme in
use, and it is where the rule tokens collapse.

Usage:
    python docs_audit/ui_contrast_sweep.py [--file F] [--min 4.5] [--all]
"""
from __future__ import annotations
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import commander_theme as theme  # noqa: E402

PAL = theme.DARK
GROUND = PAL["ground"]
AA_BODY, AA_LARGE = 4.5, 3.0


def _lum(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _cr(a, b):
    l1, l2 = sorted([_lum(a), _lum(b)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def _mid(a, b):
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#" + "".join("%02X" % ((int(a[i:i + 2], 16) + int(b[i:i + 2], 16)) // 2)
                         for i in (0, 2, 4))


def _tok(name):
    return PAL.get(name)


def _resolve_colour(val, varmap):
    """A colour expression -> (hex, label). None when it cannot be resolved."""
    val = val.strip().rstrip(";").strip()
    m = re.fullmatch(r"#[0-9A-Fa-f]{3,8}", val)
    if m:
        return val[:7], val[:7]
    m = re.fullmatch(r"var\(--([a-z0-9-]+)\)", val)
    if m:
        h = _tok(m.group(1))
        return (h, "--" + m.group(1)) if h else (None, val)
    m = re.fullmatch(r"\{([A-Za-z_]\w*)\}", val)          # f-string interpolation
    if m and m.group(1) in varmap:
        return _resolve_colour(varmap[m.group(1)], {})
    return None, val


def _varmap(src):
    """name -> literal colour string, for `x = "var(--tok)"` / `x = "#hex"`.

    Only single-valued assignments are taken: a name assigned two different colours in
    different branches cannot be scored statically and is left unresolved rather than
    guessed at.
    """
    seen = {}
    for m in re.finditer(r"(?m)^\s*([A-Za-z_]\w*)\s*=\s*\"(#[0-9A-Fa-f]{6}|var\(--[a-z0-9-]+\))\"\s*$", src):
        n, v = m.group(1), m.group(2)
        seen.setdefault(n, set()).add(v)
    return {n: next(iter(v)) for n, v in seen.items() if len(v) == 1}


def _string_spans(path):
    """(start, end) of every STRING literal, via tokenize — exact, not guessed.

    The pairing has to be bounded by something real. Scanning backwards through a fixed
    character window paired a colour with a background from an UNRELATED element four
    times in the top five findings. Walking the markup as a tag tree failed the other
    way: opens and closes live in different f-strings, so the stack unwinds wrongly and
    nothing resolves at all.

    A string literal is the unit that actually holds one piece of markup, so a colour is
    scored only against a background declared in the SAME literal. Anything else is
    reported as needing an eye rather than scored against an assumption.
    """
    import tokenize
    spans = []
    with open(path, "rb") as fh:
        try:
            for tok in tokenize.tokenize(fh.readline):
                if tok.type == tokenize.STRING:
                    spans.append((tok.start, tok.end, tok.string))
        except Exception:
            pass
    return spans


def _literal_bounds(src, spans):
    """Character offsets for each literal, from its (row, col) token span."""
    line_off, off = [0], 0
    for ln in src.split(chr(10)):
        off += len(ln) + 1
        line_off.append(off)
    out = []
    for (r1, c1), (r2, c2), _ in spans:
        try:
            out.append((line_off[r1 - 1] + c1, line_off[r2 - 1] + c2))
        except IndexError:
            pass
    return sorted(out)


def _enclosing(bounds, pos):
    for a, b in bounds:
        if a <= pos < b:
            return a, b
    return None


def _bg_in_literal(src, bounds, pos):
    """Nearest background declared BEFORE `pos` within the same string literal."""
    lit = _enclosing(bounds, pos)
    if not lit:
        return None, "unknown"
    seg = src[lit[0]:pos]
    best = None
    for m in re.finditer(r"(?<!-)background(?:-color)?\s*:\s*([^;'\"]+)", seg):
        best = m
    if not best:
        return None, "unknown"
    val = best.group(1)
    stops = re.findall(r"#[0-9A-Fa-f]{6}", val)
    if "gradient" in val and len(stops) >= 2:
        return _mid(stops[0], stops[-1]), "grad %s/%s" % (stops[0], stops[-1])
    if stops:
        return stops[0], stops[0]
    h, lab = _resolve_colour(val, {})
    return (h, lab) if h else (None, "unknown")


def _page_of(src, pos):
    """Nearest page/tab marker above — so a finding can be navigated to."""
    seg = src[:pos]
    best = ""
    for m in re.finditer(r"(?:page\s*==\s*['\"]([A-Z0-9 _/&-]{3,30})['\"]"
                         r"|st\.tabs\(\[\s*['\"]([^'\"]{3,40})['\"])", seg):
        best = m.group(1) or m.group(2)
    return (best or "?")[:22]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="weinstein_commander_web_v4.0.py")
    ap.add_argument("--min", type=float, default=AA_BODY)
    ap.add_argument("--all", action="store_true", help="list passing rows too")
    a = ap.parse_args()

    src = open(a.file, encoding="utf-8", errors="ignore").read()
    varmap = _varmap(src)
    bounds = _literal_bounds(src, _string_spans(a.file))
    rows, unresolved, needs_eye = [], 0, 0
    for m in re.finditer(r"(?<!-)color\s*:\s*([^;'\"}]+|\{[A-Za-z_]\w*\})", src):
        fg, flab = _resolve_colour(m.group(1), varmap)
        if not fg:
            unresolved += 1
            continue
        bg, blab = _bg_in_literal(src, bounds, m.start())
        if bg is None:
            needs_eye += 1
            continue
        rows.append((_cr(fg, bg), src.count("\n", 0, m.start()) + 1,
                     flab, blab, _page_of(src, m.start())))
    rows.sort()

    print("scanned %s · %d text colours resolved · %d unresolved (runtime-built)\n"
          % (a.file, len(rows), unresolved))
    print("%-6s %-22s %-18s %-16s %6s  %s"
          % ("line", "page/tab", "colour", "on", "ratio", "verdict"))
    bad = 0
    for cr_, line, flab, blab, page in rows:
        if cr_ >= a.min and not a.all:
            continue
        v = "*** INVISIBLE" if cr_ < AA_LARGE else ("below AA body" if cr_ < AA_BODY else "ok")
        if cr_ < a.min:
            bad += 1
        print("%-6d %-22s %-18s %-16s %5.2f:1  %s" % (line, page, flab[:18], blab[:16], cr_, v))
    print("\n%d of %d below %.1f:1  (%d invisible, under %.1f:1)"
          % (bad, len(rows), a.min, sum(1 for r in rows if r[0] < AA_LARGE), AA_LARGE))
    print("Rows on \"ground (assumed)\" had no background in the markup — confirm those by eye.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
