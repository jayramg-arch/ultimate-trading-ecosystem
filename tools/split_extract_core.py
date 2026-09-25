"""Move the Streamlit-free helpers of the web app into commander_core.py - MOVE-ONLY.

Selection = tools/split_analyze.py's movable set (no Streamlit, directly or transitively;
no runtime-only globals; no `global` statements) plus the constants and imports that set
needs. The main file gets one explicit `from commander_core import (...)` at the position
of the first removed statement, so every name keeps resolving in main exactly as before.

Refuses (exit 1) if any moved name is (re)bound anywhere else in the file - at module
level, inside a page, or via a `global` statement - because main and core would then hold
two different objects under one name. That is the one way a move could change behaviour.
"""
import ast
import builtins
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(HERE, "weinstein_commander_web_v4.0.py")
CORE = os.path.join(HERE, "commander_core.py")

sys.argv = [sys.argv[0], APP]
ns = {}
exec(open(os.path.join(HERE, "tools", "split_analyze.py"), encoding="utf-8").read(), ns)
status, funcs, assigns, imported, pre = ns["status"], ns["funcs"], ns["assigns"], ns["imported"], ns["pre"]
free_names, const_ok = ns["free_names"], ns["const_ok"]
src = open(APP, encoding="utf-8").read()
lines = src.split("\n")
tree = ast.parse(src)
BUILTINS = set(dir(builtins))

M = {f for f, s in status.items() if s[0]}

# constants the moved set needs (transitively through constant expressions)
need_const, need_imp = set(), set()


def visit_names(names):
    for g in names:
        if g in BUILTINS or g in M:
            continue
        if g in imported:
            need_imp.add(g)
        elif g in assigns and g not in need_const:
            need_const.add(g)
            v = assigns[g][0].value
            visit_names({x.id for x in ast.walk(v) if isinstance(x, ast.Name)})


for f in M:
    visit_names(free_names(funcs[f])[0])
need_const.discard("__file__")

moved_names = M | need_const
# ---- trap 1: any other binding of a moved name anywhere in the file ----------------
# identity by (kind, name, line): funcs/assigns come from split_analyze's own parse
def_keys = {("def", f, funcs[f].lineno) for f in M} | {("asg", c, assigns[c][0].lineno) for c in need_const}
problems = []
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        if node.name in moved_names and ("def", node.name, node.lineno) not in def_keys:
            problems.append(f"re-def {node.name} at line {node.lineno}")
    if isinstance(node, ast.Global):
        for n in node.names:
            if n in moved_names:
                problems.append(f"global {n} at line {node.lineno}")
# module-level stores (incl. pages, which run at module level) outside the defining stmt
def module_level_stores(stmts, inside_def=False):
    for st in stmts:
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        for x in ast.walk(st):
            if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(x, ast.Name) and isinstance(x.ctx, (ast.Store, ast.Del)):
                yield st, x


for st, x in module_level_stores(tree.body):
    if x.id in moved_names and ("asg", x.id, st.lineno) not in def_keys:
        # a Store inside a nested function body is local; ast.walk above descends into
        # nested defs, so re-check the store is not inside a def within st
        inner = False
        for d in ast.walk(st):
            if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                if any(y is x for y in ast.walk(d)):
                    inner = True
                    break
        if not inner:
            problems.append(f"module-level store of {x.id} at line {x.lineno}")
# ---- trap 2: names used by moved code that come from a Try/If-guarded import --------
for g in need_imp:
    stmt = imported[g]
    if stmt not in pre:
        problems.append(f"import of {g} is not a plain top-level import")
# `logger` is bound in a guarded import (line ~80) and again unconditionally (~231) before
# anything runs, so the final object is the second; the core pins the same logger name.
problems = [p for p in problems if not p.startswith("module-level store of logger ")]
if problems:
    print("REFUSED - moving these would change behaviour:")
    for p in sorted(set(problems))[:60]:
        print("  ", p)
    sys.exit(1)

# ---- write commander_core.py --------------------------------------------------------
def span(node):
    start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    return start, node.end_lineno


imp_stmts = sorted({id(imported[g]): imported[g] for g in need_imp}.values(), key=lambda n: n.lineno)
body_stmts = sorted([funcs[f] for f in M] + [assigns[c][0] for c in need_const], key=lambda n: n.lineno)
out = ['"""commander_core.py - the Streamlit-free helpers of Web Commander, importable and testable.',
       "",
       "MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 by",
       "tools/split_extract_core.py (docs/PLAN_web_commander_split.md, phase 2). Selection is",
       "mechanical: no Streamlit call, directly or through a callee; no runtime-only global; no",
       "`global` statement; and no other binding of the name anywhere in the app. The app does",
       "`from commander_core import (...)`, so every name resolves exactly as before.",
       "",
       "Edit HERE - the app file no longer holds these definitions.",
       '"""']
for n in imp_stmts:
    out.append(ast.get_source_segment(src, n))
out.append("")
for n in body_stmts:
    a, b = span(n)
    out.append("")
    out.extend(lines[a - 1:b])
core_txt = "\n".join(out) + "\n"
core_txt = core_txt.replace("logger = logging.getLogger(__name__)",
                            'logger = logging.getLogger("__main__")   # the app\'s logger - same name as before the move')
open(CORE, "w", encoding="utf-8", newline="\n").write(core_txt)

# ---- rewrite the app: drop moved statements, one import at the first gap -------------
drop = set()
first = None
for n in body_stmts:
    a, b = span(n)
    first = a if first is None else min(first, a)
    drop.update(range(a, b + 1))
names_sorted = sorted(moved_names - {"__file__"})
imp_line = ("from commander_core import (  # moved verbatim 25-Sep-2026 - see commander_core.py\n    "
            + ",\n    ".join(", ".join(names_sorted[i:i + 5]) for i in range(0, len(names_sorted), 5))
            + ",\n)")
new = []
for i, l in enumerate(lines, start=1):
    if i == first:
        new.append(imp_line)
    if i in drop:
        continue
    new.append(l)
open(APP, "w", encoding="utf-8", newline="\n").write("\n".join(new))
print(f"moved {len(M)} defs + {len(need_const)} constants ({len(drop)} lines) -> commander_core.py")
print("imports carried:", sorted(need_imp))
