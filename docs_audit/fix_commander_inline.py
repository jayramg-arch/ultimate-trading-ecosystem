"""Phase 4 — the inline sweep, brought forward because the ground moved.

I meant to defer this and do it page by page. That is the right plan when the app is
still light and each page can be checked in isolation. It stopped being the right plan
the moment the ground went dark: every literal left behind is now a contrast bug, and
a half-swept app is the one state worse than either end.

WHY THE FIRST PASS MISSED THESE. Two reasons, both mine:

  1. The regex was anchored on style=" — DOUBLE quotes. A large share of this file's
     inline styles use SINGLE quotes (`div style='...'`), and those were invisible to
     it. 51 substitutions looked like a complete sweep and was about a third of one.

  2. The colour list was too short. I listed the near-blacks but not the mid-greys
     (#475569, #94A3B8) or the old accent (#1D4ED8) — all perfectly legible on a light
     ground and all too dark on #0F1618.

So this pass is quote-agnostic and works off the full old-palette map, covering colour,
background and border in one go.
"""
import io
import re

P = "weinstein_commander_web_v4.0.py"
s = io.open(P, encoding="utf-8").read()
orig = s

# old literal -> token. Ordered so no key is a prefix of another.
CMAP = {
    # text, darkest first
    "#000000": "var(--ink)", "#090D16": "var(--ink)", "#0F172A": "var(--ink)",
    "#111827": "var(--ink)",
    "#1E293B": "var(--ink-2)", "#334155": "var(--ink-2)", "#1F2937": "var(--ink-2)",
    "#475569": "var(--muted)", "#64748B": "var(--muted)", "#6B7280": "var(--muted)",
    "#94A3B8": "var(--faint)", "#9CA3AF": "var(--faint)",
    # structure
    "#CBD5E1": "var(--rule)", "#E2E8F0": "var(--rule)", "#D1D5DB": "var(--rule)",
    "#F1F5F9": "var(--surface-2)", "#F8FAFC": "var(--surface-2)",
    "#F0F4F8": "var(--ground)", "#FFFFFF": "var(--surface)",
    # accent
    "#1D4ED8": "var(--acc)", "#1E3A8A": "var(--acc)", "#2563EB": "var(--acc)",
    "#3B82F6": "var(--acc)", "#1E40AF": "var(--acc)", "#0C4A6E": "var(--acc)",
    # semantic
    "#15803D": "var(--bull)", "#10B981": "var(--bull)", "#059669": "var(--bull)",
    "#166534": "var(--bull)",
    "#DC2626": "var(--bear)", "#EF4444": "var(--bear)", "#991B1B": "var(--bear)",
    "#B91C1C": "var(--bear)",
    "#B45309": "var(--warn)", "#F59E0B": "var(--warn)", "#FF9800": "var(--warn)",
    "#D97706": "var(--warn)", "#92400E": "var(--warn)",
}

# Only inside a CSS property we understand, and QUOTE-AGNOSTIC. Matching the property
# name rather than the enclosing attribute is what makes single vs double quotes stop
# mattering — and it also keeps the sweep off anything that merely looks like a colour
# (a ticker, a hash in a comment, an f-string expression).
PROPS = r"(?:color|background|background-color|border-color|border|border-top|" \
        r"border-bottom|border-left|border-right|fill|stroke|outline-color)"

counts = {}
for lit, tok in CMAP.items():
    pat = re.compile(r"(" + PROPS + r"\s*:\s*(?:[^;\"'{}]*?\s)?)" + re.escape(lit) + r"\b",
                     re.I)
    s, n = pat.subn(lambda m: m.group(1) + tok, s)
    if n:
        counts[lit] = n

# Plotly and other Python-side colour arguments are NOT swept here: they are passed to
# a library that has never heard of a CSS variable, and `marker_color="var(--bull)"`
# renders nothing at all. Those were handled separately by the template + the explicit
# paper/plot background pass.

s2 = s
assert s2 != orig
io.open(P, "w", encoding="utf-8").write(s2)

tot = sum(counts.values())
for k, v in sorted(counts.items(), key=lambda x: -x[1])[:14]:
    print(f"  {v:4}x  {k}  ->  {CMAP[k]}")
print(f"  ({len(counts)} distinct literals, {tot} substitutions)")
