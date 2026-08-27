"""Finish the dark conversion: Streamlit's own widgets, Plotly, and the inline styles.

WHAT WENT WRONG. Phases 1-2 tokenised the STYLESHEET and I verified it by probing
stylesheet classes — .page-title, .sb-cell, pill-bull. All of those passed, so I called
it working. What I never opened was a page with real content, and that is where the
damage was: metric values, dataframes, radio labels and Plotly charts are rendered by
Streamlit and Plotly, follow their OWN theming, and stayed light while the ground went
dark. Probing the classes I had just edited only proved my edit applied to itself.

THREE FIXES, in order of how much they carry:

1. .streamlit/config.toml -> base="dark" (done separately). This is the load-bearing
   one: it themes metrics, dataframes, radios and inputs. The dataframe in particular
   is a CANVAS-based grid that CSS cannot reach at all, so config is the only lever.

2. This script — CSS for what config leaves behind, plus the Plotly template.

3. The inline sweep: 51 style= attributes hardcoding near-black text and 6 hardcoding
   white or near-white backgrounds. These are the "invisible numbers" — text painted
   #090D16 on a #0F1618 ground.

Every replacement here is bounded and reversible, and none of it touches signal logic.
"""
import io
import re

P = "weinstein_commander_web_v4.0.py"
s = io.open(P, encoding="utf-8").read()
orig = s

# ── 1 · inline near-black text -> token ──────────────────────────────────────
# These are the invisible field numbers. A literal near-black inside a style=
# attribute cannot know the ground moved.
DARK_TEXT = ["#090D16", "#0F172A", "#111827", "#000000", "#1E293B", "#334155"]
inline_text = 0
for lit in DARK_TEXT:
    # only inside a style= attribute, only as a COLOUR (not a background)
    pat = re.compile(r'(style="[^"]*?color:\s*)' + re.escape(lit), re.I)
    s, n = pat.subn(lambda m: m.group(1) + "var(--ink)", s)
    inline_text += n

# ── 2 · inline white / near-white backgrounds -> token ───────────────────────
WHITE_BG = ["#FFFFFF", "#F8FAFC", "#F1F5F9", "#F0F4F8", "#FAFAFA"]
inline_bg = 0
for lit in WHITE_BG:
    pat = re.compile(r'(style="[^"]*?background(?:-color)?:\s*)' + re.escape(lit), re.I)
    s, n = pat.subn(lambda m: m.group(1) + "var(--surface)", s)
    inline_bg += n

# ── 3 · Plotly: dark template + transparent paper ────────────────────────────
# The donut rendered on a white card because Plotly defaults to a light template and
# paints its own background. Transparent paper lets the page ground show through, so
# the chart sits ON the card instead of punching a white hole in it.
plotly_patch = '''
# ── PLOTLY DARK DEFAULT (27 Aug 2026) ────────────────────────────────────────
# Plotly does not read our CSS variables, so a chart keeps its own light template and
# paints an opaque background — which is why the sector donut appeared as a white card
# on a dark page. Setting the template ONCE here covers every figure in the app;
# per-figure overrides still win if a chart genuinely needs a different look.
try:
    import plotly.io as _pio
    import plotly.graph_objects as _pgo
    _pio.templates["commander"] = _pgo.layout.Template(
        layout=dict(
            paper_bgcolor="rgba(0,0,0,0)",   # let the card behind it show through
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=_theme.DARK["ink"], family="Inter, sans-serif"),
            xaxis=dict(gridcolor=_theme.DARK["rule"], zerolinecolor=_theme.DARK["rule"]),
            yaxis=dict(gridcolor=_theme.DARK["rule"], zerolinecolor=_theme.DARK["rule"]),
            colorway=["#56C2CC", "#45BE92", "#DCA84E", "#E9857C", "#8FA8C8",
                      "#B08FD0", "#5FBFA8", "#D09A6A"],
        )
    )
    _pio.templates.default = "plotly_dark+commander"
except Exception:
    pass   # charts still render on Plotly's own default
'''
anchor = "import commander_theme as _theme"
assert s.count(anchor) == 1, "theme import not found"
s = s.replace(anchor, anchor + "\n" + plotly_patch, 1)

# ── 4 · CSS for what config.toml leaves behind ───────────────────────────────
CLOSE = '</style>\n""", unsafe_allow_html=True)'
assert s.count(CLOSE) >= 1, "stylesheet close not found"

widget_css = '''
/* ── STREAMLIT WIDGETS (27 Aug 2026) ──────────────────────────────────────
   config.toml themes most of these; the rules below cover what it leaves behind
   and pin anything that still renders a white surface. `no white backgrounds`
   is the requirement, so the sweep is deliberately broad. */

/* metric values were the most visible break -- dark digits on a dark ground */
[data-testid="stMetricValue"] {{ color: var(--ink) !important;
    font-family: var(--mono) !important; font-variant-numeric: tabular-nums !important; }}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{ color: var(--muted) !important; }}
[data-testid="stMetricDelta"] {{ font-family: var(--mono) !important; }}
[data-testid="stMetric"] {{ background: var(--surface) !important;
    border: 1px solid var(--rule) !important; border-radius: var(--radius) !important;
    padding: 10px 14px !important; }}

/* radio / checkbox / label text */
[data-testid="stRadio"] label, [data-testid="stCheckbox"] label,
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] * {{ color: var(--ink-2) !important; }}

/* tables -- st.table and st.dataframe's non-canvas chrome */
[data-testid="stTable"], [data-testid="stTable"] table {{ background: var(--surface) !important;
    color: var(--ink) !important; }}
[data-testid="stTable"] th {{ background: var(--surface-2) !important; color: var(--muted) !important;
    border-bottom: 1px solid var(--rule) !important; }}
[data-testid="stTable"] td {{ border-bottom: 1px solid var(--rule-soft) !important;
    color: var(--ink-2) !important; }}
[data-testid="stDataFrame"], [data-testid="stDataFrameResizable"] {{
    background: var(--surface) !important; border: 1px solid var(--rule) !important; }}

/* expanders, tabs, inputs, code blocks -- all default to a light surface */
[data-testid="stExpander"] {{ background: var(--surface) !important;
    border: 1px solid var(--rule) !important; }}
[data-testid="stExpander"] summary {{ color: var(--ink) !important; }}
.stTabs [data-baseweb="tab-list"] {{ background: transparent !important; }}
.stTabs [data-baseweb="tab"] {{ color: var(--muted) !important; }}
.stTabs [aria-selected="true"] {{ color: var(--acc) !important; }}
input, textarea, select {{ background: var(--surface-2) !important; color: var(--ink) !important;
    border-color: var(--rule) !important; }}
pre, code {{ background: var(--surface-2) !important; color: var(--ink) !important; }}

/* the catch-all: anything still painting itself white */
[style*="background:#FFFFFF"], [style*="background: #FFFFFF"],
[style*="background-color:#FFFFFF"], [style*="background-color: #FFFFFF"],
[style*="background:#fff"], [style*="background: #fff"] {{
    background: var(--surface) !important; }}
[style*="color:#090D16"], [style*="color: #090D16"],
[style*="color:#0F172A"], [style*="color: #0F172A"] {{ color: var(--ink) !important; }}
'''
s = s.replace(CLOSE, widget_css + CLOSE, 1)

assert s != orig
io.open(P, "w", encoding="utf-8").write(s)
print(f"{P}: {len(orig)} -> {len(s)} chars")
print(f"  inline text colours  -> var(--ink)    : {inline_text}")
print(f"  inline backgrounds   -> var(--surface): {inline_bg}")
print(f"  plotly dark template : added")
print(f"  widget CSS block     : added")
