"""Analyse the pre-page region of the web app: which top-level functions are PURE (no
Streamlit calls, no runtime-only globals, directly or transitively) and so can move to an
importable core module without changing behaviour. Read-only; prints a report."""
import ast
import builtins
import sys

APP = sys.argv[1] if len(sys.argv) > 1 else "weinstein_commander_web_v4.0.py"
src = open(APP, encoding="utf-8").read()
tree = ast.parse(src)
body = tree.body
chain_idx = max(i for i, n in enumerate(body) if isinstance(n, ast.If))
pre = body[:chain_idx]

BUILTINS = set(dir(builtins))
imported, funcs, assigns, other = {}, {}, {}, []
for n in pre:
    if isinstance(n, (ast.Import, ast.ImportFrom)):
        for a in n.names:
            imported[(a.asname or a.name).split(".")[0]] = n
    elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
        funcs[n.name] = n
    elif isinstance(n, (ast.Assign, ast.AnnAssign)):
        tg = n.targets if isinstance(n, ast.Assign) else [n.target]
        for t in tg:
            for x in ast.walk(t):
                if isinstance(x, ast.Name):
                    assigns.setdefault(x.id, []).append(n)
    else:
        other.append(n)


def free_names(fn):
    """Global names a function loads (params/locals excluded, crude but conservative)."""
    local = set()
    for a in ast.walk(fn):                 # every arg: the def, nested defs, lambdas
        if isinstance(a, ast.arg):
            local.add(a.arg)
    for x in ast.walk(fn):
        if isinstance(x, ast.Name) and isinstance(x.ctx, (ast.Store, ast.Del)):
            local.add(x.id)
        elif isinstance(x, (ast.FunctionDef, ast.ClassDef)) and x is not fn:
            local.add(x.name)
        elif isinstance(x, (ast.Import, ast.ImportFrom)):
            for a in x.names:
                local.add((a.asname or a.name).split(".")[0])
        elif isinstance(x, ast.ExceptHandler) and x.name:
            local.add(x.name)
    glob = set()
    for x in ast.walk(fn):
        if isinstance(x, ast.Global):
            glob |= set(x.names)
    loads = {x.id for x in ast.walk(fn) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load)}
    return (loads - local) | glob, glob


def uses_st(fn):
    for x in ast.walk(fn):
        if isinstance(x, ast.Name) and x.id in ("st", "st_components", "_theme"):
            return True
    for d in getattr(fn, "decorator_list", []):
        if "st" in ast.unparse(d):
            return True
    return False


# A constant is movable if its value only references builtins / imported modules / other
# movable constants and is assigned exactly once.
def const_ok(name, seen=None):
    seen = seen or set()
    if name in seen:
        return False
    nodes = assigns.get(name, [])
    if len(nodes) != 1:
        return False
    v = nodes[0].value
    if v is None:
        return False
    for x in ast.walk(v):
        if isinstance(x, ast.Name):
            if x.id in BUILTINS or x.id in imported and x.id not in ("st",):
                continue
            if x.id == "__file__":
                continue
            if x.id in assigns and const_ok(x.id, seen | {name}):
                continue
            if x.id in funcs:
                continue
            return False
    return True


status = {}


def movable(name, stack=()):
    if name in status:
        return status[name]
    if name in stack:
        return True                     # recursion inside the candidate set
    fn = funcs[name]
    if uses_st(fn):
        status[name] = (False, "uses Streamlit")
        return status[name]
    fnames, glob = free_names(fn)
    if glob:
        status[name] = (False, f"global stmt {sorted(glob)}")
        return status[name]
    for g in sorted(fnames):
        if g in BUILTINS:
            continue
        if g in imported:
            if g in ("st", "st_components", "_theme"):
                status[name] = (False, "uses Streamlit"); return status[name]
            continue
        if g in funcs:
            ok = movable(g, stack + (name,))
            if not ok[0]:
                status[name] = (False, f"calls {g} ({ok[1]})")
                return status[name]
            continue
        if g in assigns and const_ok(g):
            continue
        status[name] = (False, f"runtime global {g}")
        return status[name]
    status[name] = (True, "")
    return status[name]


for f in funcs:
    movable(f)
mv = [f for f, s in status.items() if s[0]]
st_ = [f for f, s in status.items() if not s[0]]
lines_mv = sum(funcs[f].end_lineno - funcs[f].lineno + 1 for f in mv)
print(f"pre-page top-level: {len(pre)} stmts, {len(funcs)} defs, {len(imported)} import names")
print(f"MOVABLE: {len(mv)} defs, {lines_mv} lines")
print(f"STAY:    {len(st_)} defs")
from collections import Counter
print(Counter(s[1].split(" (")[0].split(" ")[0] + " " + (s[1].split(" ")[1] if len(s[1].split(" ")) > 1 else "") for f, s in status.items() if not s[0]).most_common(12))
key = ["compute_workflow", "compute_recovery_workflow", "compute_decision", "_plan_structural_sl",
       "_house_initial_stop", "_gm_sl_basis", "_gm_zone_rungs", "_g", "minervini_checks",
       "section_structure", "render_technical_board"]
for k in key:
    if k in status:
        print(f"  {k:28s} {status[k]}")
