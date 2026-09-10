# -*- coding: utf-8 -*-
"""rule_token_contrast_sweep.py — find *-rule tokens used as TEXT colour and score
each one against the background it actually sits on.

READ-ONLY. Reports; changes nothing.

WHY
---
commander_theme.py:64 states the contract: "surface* are grounds and ink*/muted/faint
are text". The *-rule tokens are RULES AND BORDERS. Used as a text colour on a coloured
card they render near-black on near-black: the Risk Shield OCO card had its two headers
at 1.35:1 and 1.53:1, below even the 3:1 large-text floor, and Jay read them as "very
faint" rather than as broken.

That one was found by eye. This finds the rest.

METHOD, and its limits
----------------------
For each `color:var(--X-rule)` the sweep walks BACKWARDS through the enclosing markup for
the nearest `background:`/`background-color:` declaration and resolves it — hex, gradient
(both stops, scored at the midpoint), or theme token. When none is found the element sits
on the page ground and is scored against that.

This is a static read of f-strings, so it cannot see backgrounds applied by a CSS class
or set from a variable. Those show as "ground (assumed)" and are the cases to eyeball.
Dark mode only: it is the theme Jay runs, and the dark palette is where rule tokens
collapse (in LIGHT mode the same tokens are pale and fail against a WHITE card instead).

Usage:  python docs_audit/rule_token_contrast_sweep.py [--file <path>] [--min 4.5]
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


def _lum(h: str) -> float:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _cr(a: str, b: str) -> float:
    l1, l2 = sorted([_lum(a), _lum(b)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def _mid(a: str, b: str) -> str:
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#" + "".join("%02X" % ((int(a[i:i + 2], 16) + int(b[i:i + 2], 16)) // 2)
                         for i in (0, 2, 4))


def _resolve(colour: str) -> str | None:
    """A hex, or a var(--token) that the dark palette knows."""
    colour = colour.strip().rstrip(";").strip()
    m = re.fullmatch(r"#[0-9A-Fa-f]{3,8}", colour)
    if m:
        return colour[:7]
    m = re.fullmatch(r"var\(--([a-z0-9-]+)\)", colour)
    if m and m.group(1) in PAL:
        return PAL[m.group(1)]
    return None


def _background_before(text: str, pos: int, window: int = 1200):
    """Nearest background declaration before `pos`. Returns (hex, description)."""
    seg = text[max(0, pos - window):pos]
    best = None
    for m in re.finditer(r"background(?:-color)?\s*:\s*([^;'\"]+)", seg):
        best = m
    if not best:
        return GROUND, "ground (assumed)"
    val = best.group(1)
    stops = re.findall(r"#[0-9A-Fa-f]{6}", val)
    if "gradient" in val and len(stops) >= 2:
        return _mid(stops[0], stops[-1]), "gradient %s->%s" % (stops[0], stops[-1])
    if stops:
        return stops[0], stops[0]
    r = _resolve(val)
    if r:
        return r, val.strip()
    return GROUND, "unresolved: %s" % val.strip()[:28]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="weinstein_commander_web_v4.0.py")
    ap.add_argument("--min", type=float, default=4.5)
    a = ap.parse_args()

    src = open(a.file, encoding="utf-8", errors="ignore").read()
    # (?<!-) so `border-color:var(--x-rule)` -- a LEGITIMATE border use -- is not
    # counted as text. Without it the sweep flags its own false positives.
    hits = list(re.finditer(r"(?<!-)color\s*:\s*var\(--([a-z]+)-rule\)", src))
    print("scanned %s  ·  %d uses of a *-rule token as TEXT colour\n" % (a.file, len(hits)))
    if not hits:
        print("none — nothing to review.")
        return 0

    rows = []
    for m in hits:
        tok = m.group(1) + "-rule"
        fg = PAL.get(tok)
        if not fg:
            continue
        bg, desc = _background_before(src, m.start())
        line = src.count("\n", 0, m.start()) + 1
        rows.append((_cr(fg, bg), line, tok, fg, bg, desc,
                     PAL.get(m.group(1), "")))
    rows.sort()

    print("%-6s %-11s %-8s %-22s %6s  %s" % ("line", "token", "fg", "background", "ratio", "verdict"))
    bad = 0
    for cr_, line, tok, fg, bg, desc, acc in rows:
        if cr_ < 3.0:
            v, bad = "*** INVISIBLE", bad + 1
        elif cr_ < a.min:
            v, bad = "below AA body", bad + 1
        else:
            v = "ok"
        fix = ""
        if cr_ < a.min and acc:
            fix = "  -> --%s (%.2f:1)" % (tok.replace("-rule", ""), _cr(acc, bg))
        print("%-6d %-11s %-8s %-22s %5.2f:1  %s%s" % (line, tok, fg, desc[:22], cr_, v, fix))

    print("\n%d of %d below %.1f:1." % (bad, len(rows), a.min))
    print("A background shown as \"ground (assumed)\" was not found in the markup — those")
    print("are the ones to confirm by eye rather than trust this number.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
