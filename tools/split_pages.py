"""Move each `if/elif page == '...'` body of the web app into commander_pages/<slug>.py.

MOVE-ONLY, and PROVEN: after writing, the tool puts every page body back where it came
from and requires the result to equal the original file byte for byte. If it does not,
nothing is written (docs/PLAN_web_commander_split.md, phase 3).

A page file is the original lines VERBATIM under `if True:` - nothing is re-indented, so
multi-line strings (the page HTML) are untouched - and the app runs it with
commander_pages.run(slug, globals()): the same globals, the same st.stop(), the same order.
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(HERE, "weinstein_commander_web_v4.0.py")
PKG = os.path.join(HERE, "commander_pages")
HEADER = [
    "# commander_pages/{slug}.py - the {name} page of Web Commander.",
    "#",
    "# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,",
    "# docs/PLAN_web_commander_split.md phase 3). The app runs this file with",
    "# commander_pages.run('{slug}', globals()), so it sees exactly the globals it saw inline.",
    "# The body stays under `if True:` so no line was re-indented. Edit the page HERE.",
    "if True:",
]
MARK = "    commander_pages.run(\"{slug}\", globals())   # page body: commander_pages/{slug}.py"

src = open(APP, encoding="utf-8").read()
if "commander_pages.run(" in src:
    sys.exit("already split")
lines = src.split("\n")
tree = ast.parse(src)
chain = [n for n in tree.body if isinstance(n, ast.If)][-1]

branches = []
k = chain
while True:
    test = ast.get_source_segment(src, k.test)
    m = re.fullmatch(r"page == '([^']+)'", test.strip())
    if not m:
        sys.exit(f"unexpected branch test: {test}")
    # the body runs from the line after `if/elif ...:` to the last body statement
    branches.append((m.group(1), k.lineno + 1, k.body[-1].end_lineno))
    if len(k.orelse) == 1 and isinstance(k.orelse[0], ast.If):
        k = k.orelse[0]
    else:
        if k.orelse:
            sys.exit("final else branch - not handled")
        break


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


# header lines must sit exactly on the `if/elif` lines we recorded
for name, a, b in branches:
    head = lines[a - 2].strip()
    if not (head.startswith(("if page ==", "elif page ==")) and head.endswith(":")):
        sys.exit(f"{name}: line {a - 1} is not the branch header: {head!r}")

pages = {}
new = list(lines)
for name, a, b in reversed(branches):
    s = slug(name)
    body = lines[a - 1:b]
    pages[s] = (name, body)
    new[a - 1:b] = [MARK.format(slug=s)]

# the runner import, immediately before the chain
chain_line = chain.lineno
new.insert(chain_line - 1, "import commander_pages   # the 22 page bodies (25-Sep-2026) - see commander_pages/__init__.py")

# ---- PROOF: reassemble and compare -----------------------------------------------------
re_lines = []
for l in new:
    if l.startswith("import commander_pages   #"):
        continue
    m = re.fullmatch(r'    commander_pages\.run\("([a-z0-9_]+)", globals\(\)\)   # page body: .*', l)
    if m:
        re_lines.extend(pages[m.group(1)][1])
    else:
        re_lines.append(l)
if "\n".join(re_lines) != src:
    sys.exit("PROOF FAILED - reassembly differs from the original; nothing written")

os.makedirs(PKG, exist_ok=True)
for s, (name, body) in pages.items():
    hdr = [h.format(slug=s, name=name) for h in HEADER]
    open(os.path.join(PKG, s + ".py"), "w", encoding="utf-8", newline="\n").write(
        "\n".join(hdr + body) + "\n")
open(APP, "w", encoding="utf-8", newline="\n").write("\n".join(new))
print(f"{len(pages)} pages moved; reassembly == original: PROVEN")
for name, a, b in branches:
    print(f"  {slug(name):16s} {b - a + 1:5d} lines")
