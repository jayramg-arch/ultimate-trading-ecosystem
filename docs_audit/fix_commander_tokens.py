"""Phases 1 + 2 of the Commander restyle: inject the token layer, then point the
existing 35 classes at it.

PHASE 1 — the stylesheet's own @import and the hardcoded font stacks are replaced by
`commander_theme.tokens_css()`, concatenated in ahead of the rules.

PHASE 2 — every literal colour INSIDE the stylesheet becomes a var() reference. This
alone re-themes all 40 `page-title` / `metric-card` call sites and switches dark mode on
for every one of them at once.

SCOPE DISCIPLINE. The replacement is bounded to the stylesheet — from the opening
st.markdown call to its closing triple quote. The 338 inline style= attributes elsewhere
in the file are phase 4 and are NOT touched here; a global search-and-replace over an
18,733-line trading app is exactly the kind of edit that looks fine and breaks a page
nobody opens until Monday.

THE F-STRING TRAP. The stylesheet is an f-string, so every CSS brace in it is DOUBLED
(open-open / close-close). tokens_css() returns SINGLE braces and is concatenated rather
than interpolated, so it must stay outside the f-string. Getting this backwards renders
literal braces into the page.
"""
import io
import re

P = "weinstein_commander_web_v4.0.py"
s = io.open(P, encoding="utf-8").read()
orig = s

OPEN = 'st.markdown(f"""\n<style>'
CLOSE = '</style>\n""", unsafe_allow_html=True)'
i = s.find(OPEN)
j = s.find(CLOSE, i)
assert i > 0 and j > i, "main stylesheet block not located"
head, css, tail = s[:i], s[i:j], s[j:]

# ── PHASE 1 · the token layer ────────────────────────────────────────────────
old_import = re.search(r"@import url\('https://fonts\.googleapis\.com[^']+'\);\n", css)
assert old_import, "@import not found"
css = css.replace(old_import.group(0), "")

new_open = (
    'st.markdown("<style>" + _theme.tokens_css() + f"""'
)
assert css.startswith(OPEN)
css = new_open + css[len(OPEN):]

# ── PHASE 2 · literals -> tokens, inside the stylesheet only ─────────────────
# Ordered longest-first so no mapping is a prefix of another. Each entry is a colour
# the stylesheet actually used; the comment is what it was doing.
CMAP = [
    ("#F0F4F8", "var(--ground)"),        # app background
    ("#E2E8F0", "var(--surface-3)"),     # sidebar / statusbar ground
    ("#FFFFFF", "var(--surface)"),       # cards
    ("#F8FAFC", "var(--surface-2)"),     # subtle fills
    ("#F1F5F9", "var(--surface-2)"),     # scrollbar track
    ("#090D16", "var(--ink)"),           # primary text
    ("#0F172A", "var(--ink)"),           # primary text (2nd literal)
    ("#1E293B", "var(--ink-2)"),         # secondary text
    ("#334155", "var(--ink-2)"),         # secondary text (2nd literal)
    ("#475569", "var(--muted)"),         # muted text
    ("#64748B", "var(--muted)"),         # muted text / scrollbar thumb hover
    ("#94A3B8", "var(--faint)"),         # faint text / borders
    ("#CBD5E1", "var(--rule)"),          # card borders
    ("#1D4ED8", "var(--acc)"),           # accent
    ("#1E3A8A", "var(--acc)"),           # accent (dark variant)
    ("#15803D", "var(--bull)"),
    ("#10B981", "var(--bull)"),
    ("#DC2626", "var(--bear)"),
    ("#EF4444", "var(--bear)"),
    ("#B45309", "var(--warn)"),
    ("#F59E0B", "var(--warn)"),
    ("#FF9800", "var(--warn)"),
]
subs = {}
for lit, tok in CMAP:
    n = len(re.findall(re.escape(lit), css, re.I))
    if n:
        css = re.sub(re.escape(lit), tok, css, flags=re.I)
        subs[lit] = n

# font stacks -> tokens
FMAP = [
    ("'Rajdhani',sans-serif", "var(--disp)"),
    ("'Rajdhani', sans-serif", "var(--disp)"),
    ("'JetBrains Mono',monospace", "var(--mono)"),
    ("'JetBrains Mono', monospace", "var(--mono)"),
    ("'Inter', sans-serif", "var(--body)"),
    ("'Inter',sans-serif", "var(--body)"),
]
for lit, tok in FMAP:
    if lit in css:
        subs[lit] = css.count(lit)
        css = css.replace(lit, tok)

s = head + css + tail

# ── the import, next to the other local imports ──────────────────────────────
anchor = "import streamlit as st"
assert s.count(anchor) >= 1, "streamlit import not found"
if "import commander_theme as _theme" not in s:
    s = s.replace(anchor, anchor + "\nimport commander_theme as _theme", 1)

assert s != orig
io.open(P, "w", encoding="utf-8").write(s)

print(f"{P}: {len(orig)} -> {len(s)} chars")
for k, v in sorted(subs.items(), key=lambda x: -x[1]):
    print(f"  {v:4}x  {k}")
print(f"  {sum(subs.values())} substitutions, stylesheet only")
