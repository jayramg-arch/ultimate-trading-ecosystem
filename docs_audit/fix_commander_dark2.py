"""Eight reported breaks. Root causes, not symptom patches.

Jay's list, and what each one actually was:

1 · LOGO ON WHITE          The sidebar logo card is `background: var(--ink);
                           color: var(--surface)` — a DELIBERATE INVERSION that made
                           sense on a light page (dark card, white text) and inverts
                           into a glaring white block on a dark one. I looked at this
                           exact pattern last round, saw the STEP badges using it, and
                           called it "intentional". It is intentional for a 44px badge
                           and wrong for anything larger. 27 instances.

3 · HEATMAP GRADIENTS      Gradient stops still carry light literals (#E2E8F0, #D1FAE5,
4 · WHITE TILES            #A7F3D0, #F3E8FF …) that no earlier sweep mapped, because I
6 · GM BOARD TEXT          only ever enumerated the Tailwind slate ramp. 99 light
                           literals remained.

5 · SCREEN SHAKING         MINE, and not a colour bug. I put `border: 1px solid` on
                           [data-testid="stDataFrame"]. With use_container_width=True
                           the grid measures its container, the border adds 2px, that
                           overflows, a scrollbar appears, the container narrows, and
                           it measures again — a layout feedback loop. Borders that
                           affect layout do not belong on a self-measuring widget;
                           an inset box-shadow draws the same line and occupies no space.

7 · WHITE BUTTONS          Buttons Streamlit renders outside div[data-testid="stButton"]
                           — form submits, download buttons, popovers — were never in
                           the selector list.

8 · HOVER EATS THE TEXT    The hover rule set the BUTTON's colour but not its inner
                           <p>/<span>. The base rule styles those children explicitly,
                           so on hover Streamlit's own colour wins on the child and the
                           label goes dark on a dark ground. A rule that styles children
                           needs a hover variant for the children too.

2 · TOP-ROW COLOUR CODING  An enhancement, not a bug: the status cells get a semantic
                           tint and left border driven by the state they are already
                           displaying.
"""
import io
import re

P = "weinstein_commander_web_v4.0.py"
s = io.open(P, encoding="utf-8").read()
orig = s
report = {}

# ── 1 · un-invert the ink-background cards ───────────────────────────────────
# An inverted card has to become a SURFACE card, not simply swap tokens, or it
# just inverts the other way on a light theme.
n = 0
s, c = re.subn(r"background:\s*linear-gradient\(135deg,\s*var\(--ink-2\)\s*0%,\s*var\(--ink\)\s*100%\)",
               "background: linear-gradient(135deg, var(--surface-2) 0%, var(--surface-3) 100%)", s)
n += c
s, c = re.subn(r"background:\s*var\(--ink\)\s*;", "background: var(--surface-3);", s); n += c
s, c = re.subn(r"background:\s*var\(--ink-2\)\s*;", "background: var(--surface-2);", s); n += c
# their text and borders followed the inversion
s, c = re.subn(r"color:\s*var\(--surface\)\s*;", "color: var(--ink);", s); n += c
s, c = re.subn(r"border:\s*1\.5px solid var\(--ink-2\)", "border: 1.5px solid var(--rule)", s); n += c
s, c = re.subn(r"border-bottom:\s*1px solid var\(--ink-2\)", "border-bottom: 1px solid var(--rule)", s); n += c
report["1 · un-inverted cards"] = n

# ── 3/4/6 · the light literals no sweep had enumerated ───────────────────────
LIGHT = {
    "#E2E8F0": "var(--surface-3)", "#F1F5F9": "var(--surface-2)", "#F5F3FF": "var(--surface-2)",
    "#D1FAE5": "var(--bull-bg)", "#A7F3D0": "var(--bull-rule)", "#99FFCC": "var(--bull-bg)",
    "#BBF7D0": "var(--bull-rule)", "#34D399": "var(--bull)", "#4ADE80": "var(--bull)",
    "#F3E8FF": "var(--acc-bg)", "#E9D5FF": "var(--acc-bg)", "#D8B4FE": "var(--acc-rule)",
    "#C4B5FD": "var(--acc-rule)", "#7DD3FC": "var(--acc-rule)", "#22D3EE": "var(--acc)",
    "#FECDD3": "var(--bear-bg)", "#FFB3B3": "var(--bear-rule)", "#FF9999": "var(--bear-rule)",
    "#FFB74D": "var(--warn)", "#FBBF24": "var(--warn)", "#ADBAC7": "var(--faint)",
}
PLOTLY = re.compile(r'marker_color|line_color|font_color|fillcolor|bgcolor|colorway|'
                    r'color_discrete|marker=|line=dict|font=dict|_pio\.|_pgo\.|go\.|px\.|'
                    r'gridcolor|zerolinecolor', re.I)
out, n = [], 0
for line in s.split("\n"):
    if PLOTLY.search(line):
        out.append(line); continue
    for lit, tok in LIGHT.items():
        if lit.lower() in line.lower():
            n += len(re.findall(re.escape(lit), line, re.I))
            line = re.sub(re.escape(lit), tok, line, flags=re.I)
    out.append(line)
s = "\n".join(out)
report["3/4/6 · light literals"] = n

# ── 5 · the shake ────────────────────────────────────────────────────────────
# A border changes the box; an inset shadow does not. On a widget that measures its
# own container to set its width, that difference is a render loop vs a clean line.
before = s
s = s.replace(
    '[data-testid="stDataFrame"], [data-testid="stDataFrameResizable"] {{\n'
    '    background: var(--surface) !important; border: 1px solid var(--rule) !important; }}',
    '[data-testid="stDataFrame"], [data-testid="stDataFrameResizable"] {{\n'
    '    background: var(--surface) !important;\n'
    '    /* NOT `border` -- see the header note. use_container_width measures the box,\n'
    '       and a border that changes the box makes it measure again, forever. */\n'
    '    box-shadow: inset 0 0 0 1px var(--rule) !important; }}')
report["5 · dataframe shake"] = 1 if s != before else 0

# ── 7/8 · buttons Streamlit renders elsewhere, and the hover children ────────
CLOSE = '</style>\n""", unsafe_allow_html=True)'
assert s.count(CLOSE) >= 1
btn_css = '''
/* ── BUTTONS, ROUND 2 (27 Aug 2026) ───────────────────────────────────────
   Two gaps from the first pass.

   (a) Not every button is a div[data-testid="stButton"] > button. Form submits,
       download buttons, popovers and link buttons each get their own testid, and
       none of them were in the selector list -- so they kept a white ground.

   (b) The base rule styles the button's inner <p>/<span> explicitly. A hover rule
       that only sets the BUTTON's colour therefore loses on the child, and the
       label goes dark on a dark ground -- the disappearing text. Anything styled
       on the parent has to be re-stated for the children on hover. */
div[data-testid="stButton"] > button,
div[data-testid="stFormSubmitButton"] > button,
div[data-testid="stDownloadButton"] > button,
div[data-testid="stPopover"] > button,
div[data-testid="stLinkButton"] > a,
button[kind="secondary"], button[kind="tertiary"], button[kind="secondaryFormSubmit"] {{
    background: var(--surface) !important;
    border: 1.5px solid var(--rule) !important;
    color: var(--acc) !important;
}}
div[data-testid="stButton"] > button:hover,
div[data-testid="stButton"] > button:hover p,
div[data-testid="stButton"] > button:hover span,
div[data-testid="stButton"] > button:hover div,
div[data-testid="stFormSubmitButton"] > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover p,
div[data-testid="stDownloadButton"] > button:hover,
div[data-testid="stDownloadButton"] > button:hover p,
button[kind="secondary"]:hover, button[kind="secondary"]:hover p,
button[kind="secondary"]:hover span {{
    background: var(--surface-2) !important;
    color: var(--acc) !important;
    -webkit-text-fill-color: var(--acc) !important;   /* Streamlit paints some labels with this */
}}
button[kind="primary"]:hover, button[kind="primary"]:hover p,
button[kind="primary"]:hover span {{
    color: var(--ground) !important;
    -webkit-text-fill-color: var(--ground) !important;
}}
/* focus must stay visible -- hover is not the only way in */
div[data-testid="stButton"] > button:focus-visible {{
    outline: 2px solid var(--acc) !important; outline-offset: 2px !important; }}

/* ── STATUS STRIP COLOUR CODING (Jay's #2) ────────────────────────────────
   The cells already carry their state in the VALUE's colour. Promoting it to the
   cell's own tint + left border means the strip reads at a glance instead of
   needing the number parsed. Driven by a class the renderer sets, so the tint can
   never disagree with the text beside it. */
.sb-cell.is-bull {{ background: var(--bull-bg) !important;
    border-left: 3px solid var(--bull) !important; }}
.sb-cell.is-bear {{ background: var(--bear-bg) !important;
    border-left: 3px solid var(--bear) !important; }}
.sb-cell.is-warn {{ background: var(--warn-bg) !important;
    border-left: 3px solid var(--warn) !important; }}
.sb-cell.is-neut {{ border-left: 3px solid var(--rule) !important; }}
'''
s = s.replace(CLOSE, btn_css + CLOSE, 1)
report["7/8 · buttons + status classes"] = 1

assert s != orig
io.open(P, "w", encoding="utf-8").write(s)
for k, v in report.items():
    print(f"  {k}: {v}")
