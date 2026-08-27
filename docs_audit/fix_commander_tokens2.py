"""Phase 2b — the last 51 literals in the Commander stylesheet.

Two groups, and they are different KINDS of change.

GROUP A · the semantic tint/rule pairs (safe, pure substitution)
    #DCFCE7 / #86EFAC   the bull pill's fill and border
    #FEE2E2 / #FCA5A5   bear
    #FEF3C7 / #FCD34D   warn
These already have exact token counterparts (--bull-bg / --bull-rule etc.). Mapping them
is a rename, nothing more — and it is what finally makes the pill classes dark-aware.

GROUP B · the blue gradients (a deliberate visual change)
    .sb-cell            a 3-stop blue gradient + coloured drop-shadow, per status cell
    sidebar buttons     a 2-stop tint
    the auto-pilot CTA  a 3-stop gradient
This is the flattening the mockup proposed. Three blue stops and a glow behind every
status cell is decoration competing with the numbers, and on a book with a red position
the cell tint fights the P&L colour. Flat surfaces divided by hairlines read faster and
leave colour free to MEAN something.

The auto-pilot button KEEPS a solid accent fill rather than going flat with the rest: it
is the one button on the sidebar that starts a five-minute pipeline, and it should not
look like its neighbours.
"""
import io
import re

P = "weinstein_commander_web_v4.0.py"
s = io.open(P, encoding="utf-8").read()
orig = s

OPEN = 'st.markdown("<style>" + _theme.tokens_css() + f"""'
CLOSE = '</style>\n""", unsafe_allow_html=True)'
i = s.find(OPEN)
j = s.find(CLOSE, i)
assert i > 0 and j > i, "stylesheet not located"
head, css, tail = s[:i], s[i:j], s[j:]
before = len(re.findall(r'#[0-9A-Fa-f]{6}', css))

# ── GROUP A · semantic tints ─────────────────────────────────────────────────
for lit, tok in [
    ("#DCFCE7", "var(--bull-bg)"), ("#86EFAC", "var(--bull-rule)"),
    ("#FEE2E2", "var(--bear-bg)"), ("#FCA5A5", "var(--bear-rule)"),
    ("#FEF3C7", "var(--warn-bg)"), ("#FCD34D", "var(--warn-rule)"),
]:
    css = re.sub(re.escape(lit), tok, css, flags=re.I)

# ── GROUP B · flatten the gradients ──────────────────────────────────────────
# The status cell. Direction now rides the LEFT BORDER, which is the job the gradient
# was doing badly: a tint reads as decoration, a border reads as a state.
css = re.sub(
    r"background: linear-gradient\(160deg, var\(--acc-bg\)[^;]*?\) !important;",
    "background: var(--surface) !important;",
    css)
css = re.sub(
    r"background: linear-gradient\(160deg, #EFF6FF[^;]*?\) !important;",
    "background: var(--surface) !important;",
    css)
css = re.sub(
    r"background: linear-gradient\(160deg, #DBEAFE[^;]*?\) !important;",
    "background: var(--surface-2) !important;",   # the hover state
    css)
# sidebar buttons
css = re.sub(
    r"background: linear-gradient\(160deg, #F0F9FF[^;]*?\) !important;",
    "background: var(--surface) !important;",
    css)
# the auto-pilot CTA keeps a solid accent fill -- it is not a peer of the nav buttons
css = re.sub(
    r"background: linear-gradient\(135deg, #1E40AF[^;]*?\) !important;",
    "background: var(--acc) !important;",
    css)

# whatever blue is left is a border, a shadow or a label colour
for lit, tok in [
    ("#93C5FD", "var(--rule)"),       # status-cell border
    ("#BAE6FD", "var(--rule)"),       # sidebar-button border
    ("#60A5FA", "var(--acc-rule)"),   # CTA border
    ("#3B82F6", "var(--acc)"),        # hover border / gradient tail
    ("#2563EB", "var(--acc)"),
    ("#1E40AF", "var(--acc)"),
    ("#0C4A6E", "var(--acc)"),        # sidebar-button label
    ("#EFF6FF", "var(--surface)"),
    ("#DBEAFE", "var(--surface-2)"),
    ("#BFDBFE", "var(--surface-3)"),
    ("#F0F9FF", "var(--surface)"),
    ("#E0F2FE", "var(--surface-2)"),
]:
    css = re.sub(re.escape(lit), tok, css, flags=re.I)

# The coloured drop-shadows went with the gradients. rgba() blues cannot be tokenised
# without a --shadow token, and a glow per cell was the other half of the noise, so they
# collapse to one neutral shadow.
css = re.sub(r"box-shadow: 0 0 14px rgba\(59,130,246,[0-9.]+\), ", "box-shadow: ", css)
css = re.sub(r"box-shadow: 0 2px 6px rgba\(59,130,246,[0-9.]+\)",
             "box-shadow: 0 1px 2px rgba(0,0,0,0.05)", css)

after = len(re.findall(r'#[0-9A-Fa-f]{6}', css))
s = head + css + tail
assert s != orig
io.open(P, "w", encoding="utf-8").write(s)
print(f"stylesheet literals: {before} -> {after}")
print(f"var() refs now: {len(re.findall(r'var\(--', css))}")
