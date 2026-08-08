"""pine_sweep — static checks for Pine v6 sources, run BEFORE handing a file over to compile.

Every check here exists because the same mistake cost a real compile cycle. Pine has no
local compiler, so each round-trip is a manual paste-and-wait; a check that catches one
error pays for itself immediately.

  1 odd-quote lines      — a string literal broken across lines. Usually a generator that
                           expanded "\\n" into a REAL newline (bash heredoc de-escaping,
                           or a Python "\n" in a non-raw string). Bit three times in a day.
  2 paren balance        — mismatched parens, typically from a line-anchored regex edit
                           that removed the first line of a WRAPPED statement.
  3 qualifier-on-decl    — `simple int x = ...` at statement level. Legal only in a
                           function PARAMETER signature; anywhere else it is the
                           "Can't parse pine" runtime error with no line number.
  4 declaration order    — a function body referencing a global declared BELOW it, or a
                           global used before its own declaration. Pine resolves top-down.
  5 shadowing            — a local re-declaring a global name; the compiler warns, and the
                           two can silently be different reads of the same thing.
  6 tuple arity          — `[a, b, c] = f()` where f returns a different count. Comma
                           counting must be paren-aware: nz(x, 0.0) contains a comma.
  7 const-string inputs  — input(group=/title=) fed from anything but a literal. A function
                           return is `simple`, and input() demands `const`.
  8 generator leakage    — NL / ind / Q left in the output by a code generator.

Usage:  python pine_sweep.py <file.pine> [more.pine ...]
Exit 1 if anything is flagged, so it can gate a workflow.
"""
from __future__ import annotations

import re
import sys

STR = re.compile(r'"(?:\\.|[^"\\])*"')
FN_DECL = re.compile(r"^([A-Za-z_]\w*)\s*\(([^)]*)\)\s*=>")
GLOBAL_ASSIGN = re.compile(r"^(?:var\s+|varip\s+)?(?:(?:simple|series|const)\s+)?"
                           r"(?:bool|int|float|string|color|line|label|box|table|array|matrix|map)?\s*"
                           r"([A-Za-z_]\w*)\s*=(?!=)")
TUPLE_ASSIGN = re.compile(r"^\[([^\]]+)\]\s*=\s*(.+)$")
QUALIFIER_DECL = re.compile(r"^\s*(simple|series|const)\s+(int|float|bool|string|color)\s+[A-Za-z_]\w*\s*=(?!=)")
IDENT = re.compile(r"(?<![A-Za-z0-9_.])([A-Za-z_]\w*)(?![A-Za-z0-9_])")

# Pine namespaces and keywords are never user globals; skip them wholesale.
SKIP_PREFIX = ("ta.", "math.", "str.", "array.", "matrix.", "map.", "request.", "syminfo.",
               "timeframe.", "barstate.", "color.", "label.", "line.", "box.", "table.",
               "input.", "strategy.", "chart.", "session.", "display.", "format.",
               "location.", "shape.", "size.", "xloc.", "yloc.", "extend.", "plot.",
               "hline.", "order.", "alert.", "currency.", "dayofweek.", "adjustment.",
               "barmerge.", "scale.", "text.", "font.", "position.", "earnings.",
               "dividends.", "splits.", "math", "runtime.")
KEYWORDS = {"if", "else", "for", "while", "switch", "and", "or", "not", "true", "false",
            "na", "var", "varip", "int", "float", "bool", "string", "color", "line",
            "label", "box", "table", "array", "matrix", "map", "series", "simple",
            "const", "input", "export", "import", "method", "type", "enum", "to", "by",
            "break", "continue", "return", "open", "high", "low", "close", "volume",
            "time", "bar_index", "hl2", "hlc3", "ohlc4", "hlcc4", "plot", "plotshape",
            "plotchar", "bgcolor", "fill", "hline", "alertcondition", "indicator",
            "library", "strategy", "nz", "max_bars_back"}


def split_top(text: str) -> list[str]:
    """Split on top-level commas only — nz(d_htf, 0.0) is ONE element, not two."""
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [x.strip() for x in out if x.strip()]


def strip_code(line: str) -> str:
    """Comment- and string-free version of a line, for structural checks."""
    return STR.sub('""', line).split("//")[0]


INPUT_MANIFEST_DIR = ".pine_input_manifest"


def _input_names(lines):
    """Ordered list of input() variable names — the thing TradingView numbers."""
    import re
    pat = re.compile(r"^([A-Za-z_]\w*)\s*=\s*input(?:\.\w+)?\s*\(")
    return [m.group(1) for l in lines if (m := pat.match(l))]


def check_input_manifest(path, lines):
    """DELETING OR REORDERING AN INPUT SILENTLY DESTROYS EVERY SOURCE BINDING.

    TradingView saves study inputs as {in_N: value} where N is POSITIONAL — assigned
    by declaration order. Delete an input and every id after it shifts down, so saved
    values land on the wrong input or nowhere. On 7-Aug-2026 removing five unused
    manual-box inputs to reclaim ~500 compiled tokens shifted the v67 import fields
    from in_244.. to in_242.. and wiped all 18 source bindings — which had been
    diagnosed for hours as "TradingView drops bindings on every recompile". It does
    not; it drops them when the NUMBERING moves.

    APPENDING is safe (existing ids keep their numbers). Deleting and reordering are
    not. Inputs are also nearly free in tokens — the cost of that box was its DRAWING
    body, not its five declarations — so when tokens are needed, cut the body and
    leave the inputs declared and inert.

    Compares against the manifest recorded on the last clean sweep. First run just
    records. Delete the manifest file to re-baseline deliberately.
    """
    import os, json
    names = _input_names(lines)
    if not names:
        return []
    base = os.path.basename(path)
    d = os.path.join(os.path.dirname(os.path.abspath(path)), INPUT_MANIFEST_DIR)
    f = os.path.join(d, base + ".json")
    try:
        os.makedirs(d, exist_ok=True)
        if not os.path.exists(f):
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(names, fh, indent=1)
            return []                      # first run: record, do not accuse
        with open(f, encoding="utf-8") as fh:
            old = json.load(fh)
    except Exception:
        return []                          # never let bookkeeping fail a sweep

    issues = []
    gone = [n for n in old if n not in names]
    # Reorder = the shared names appear in a different relative order than before.
    kept_old = [n for n in old if n in names]
    kept_new = [n for n in names if n in old]
    if gone:
        first = names.index(kept_new[0]) if kept_new else 0
        issues.append("INPUTS DELETED (%d): %s — every input id after the first one"
                      % (len(gone), ", ".join(gone[:6])))
        issues.append("   shifts, which silently voids EVERY input.source binding. "
                      "Re-declare them inert, or accept a full rebind.")
    elif kept_old != kept_new:
        for a, b in zip(kept_old, kept_new):
            if a != b:
                issues.append("INPUTS REORDERED at `%s` (was `%s`) — same effect as a "
                              "deletion: ids shift and source bindings void." % (b, a))
                break
    if not issues:
        try:
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(names, fh, indent=1)   # append-only change: re-baseline
        except Exception:
            pass
    return issues

def sweep(path: str) -> list[str]:
    lines = open(path, encoding="utf-8").read().split("\n")
    issues: list[str] = []

    # ── 1 odd quotes ────────────────────────────────────────────────────────
    for i, l in enumerate(lines):
        if l.split("//")[0].replace('\\"', "").count('"') % 2:
            issues.append(f"{i+1}: odd number of quotes — string literal split across lines?")

    # ── 2 paren balance ─────────────────────────────────────────────────────
    depth = 0
    for i, l in enumerate(lines):
        s = strip_code(l)
        depth += s.count("(") - s.count(")")
        if depth < 0:
            issues.append(f"{i+1}: paren depth went negative — extra ')'")
            depth = 0
    if depth:
        issues.append(f"EOF: paren depth {depth:+d} — unclosed '('")

    # ── 3 qualifier on a declaration ────────────────────────────────────────
    for i, l in enumerate(lines):
        if QUALIFIER_DECL.match(l) and not FN_DECL.match(l.strip()):
            issues.append(f"{i+1}: `{l.strip()[:48]}` — simple/series/const is legal only "
                          f"in a function parameter list")

    # ── collect globals and functions ───────────────────────────────────────
    globals_at: dict[str, int] = {}
    funcs: list[tuple[str, int, int, set[str]]] = []   # name, decl line, body end, params
    i = 0
    while i < len(lines):
        l = lines[i]
        if not l or l[0].isspace() or l.lstrip().startswith("//"):
            i += 1
            continue
        code = strip_code(l)
        m = FN_DECL.match(code)
        if m:
            params = {p.strip().split()[-1] for p in split_top(m.group(2)) if p.strip()}
            j = i + 1
            while j < len(lines) and (not lines[j].strip() or lines[j][:1].isspace()):
                j += 1
            funcs.append((m.group(1), i + 1, j, params))
            globals_at.setdefault(m.group(1), i + 1)
            i = j
            continue
        mt = TUPLE_ASSIGN.match(code)
        if mt:
            for n in split_top(mt.group(1)):
                globals_at.setdefault(re.sub(r"^.*\s", "", n), i + 1)
        else:
            ma = GLOBAL_ASSIGN.match(code)
            if ma:
                globals_at.setdefault(ma.group(1), i + 1)
        i += 1

    # ── 4 declaration order ─────────────────────────────────────────────────
    for name, decl_ln, body_end, params in funcs:
        local: set[str] = set(params)
        for k in range(decl_ln, body_end):
            code = strip_code(lines[k])
            mt = TUPLE_ASSIGN.match(code.strip())
            if mt:
                local |= {re.sub(r"^.*\s", "", n) for n in split_top(mt.group(1))}
            ma = GLOBAL_ASSIGN.match(code.strip())
            if ma:
                local.add(ma.group(1))
        for k in range(decl_ln, body_end):
            code = strip_code(lines[k])
            if code.lstrip().startswith("//"):
                continue
            for tok in IDENT.findall(code):
                if tok in KEYWORDS or tok in local or tok.startswith(SKIP_PREFIX):
                    continue
                at = globals_at.get(tok)
                if at and at > decl_ln:
                    issues.append(f"{k+1}: function `{name}` (line {decl_ln}) uses `{tok}`, "
                                  f"declared later at line {at} — Pine resolves top-down")
                    local.add(tok)          # report once per function, not per use

    # Names a fold-function declares locally AND returns in its own tuple are not
    # shadowing: the local is scoped to the function, the global comes from the
    # destructure of that same call. Flagging them buried 137 real-looking issues
    # when v9.5 folded 11 declaration runs to get under the main-body cap.
    folded = set()
    for l in lines:
        m = re.match(r'^\[([^\]]+)\]\s*=\s*f_fold\d+\(\)', l.strip())
        if m:
            folded.update(x.strip() for x in m.group(1).split(','))
    # ── 5 shadowing ─────────────────────────────────────────────────────────
    for i, l in enumerate(lines):
        if not l[:1].isspace():
            continue
        m = re.match(r"\s+(?:var\s+)?(?:bool|int|float|string|color)\s+([A-Za-z_]\w*)\s*=(?!=)",
                     strip_code(l))
        if m and m.group(1) in globals_at and m.group(1) not in folded:
            issues.append(f"{i+1}: local `{m.group(1)}` shadows a global "
                          f"(line {globals_at[m.group(1)]})")

    # ── 6 tuple arity for [a,b] = f() where f is local ──────────────────────
    fn_ret: dict[str, int] = {}
    for name, decl_ln, body_end, _ in funcs:
        for k in range(body_end - 1, decl_ln - 1, -1):
            s = lines[k].strip()
            if s.startswith("[") and s.endswith("]"):
                fn_ret[name] = len(split_top(s[1:-1]))
                break
    for i, l in enumerate(lines):
        mt = TUPLE_ASSIGN.match(strip_code(l).strip())
        if not mt:
            continue
        callee = re.match(r"([A-Za-z_]\w*)\s*\(", mt.group(2).strip())
        if callee and callee.group(1) in fn_ret:
            want, got = fn_ret[callee.group(1)], len(split_top(mt.group(1)))
            if want != got:
                issues.append(f"{i+1}: `{callee.group(1)}` returns {want} values, "
                              f"{got} names destructured")

    # ── 7 input(group=/title=) must be a const literal ──────────────────────
    for i, l in enumerate(lines):
        for kw in ("group=", "title="):
            m = re.search(re.escape(kw) + r"([A-Za-z_]\w*)", strip_code(l))
            if m and m.group(1) in globals_at:
                at = globals_at[m.group(1)]
                src = strip_code(lines[at - 1])
                if not re.search(r"=\s*\"", src):
                    issues.append(f"{i+1}: input({kw}{m.group(1)}) — `{m.group(1)}` is not a "
                                  f"string literal (line {at}); input() needs a CONST string")

    # ── 8 generator leakage ─────────────────────────────────────────────────
    for i, l in enumerate(lines):
        code = strip_code(l)
        if re.search(r"(?<![A-Za-z0-9_])(NL|ind)(?![A-Za-z0-9_])", code) and "=" in code:
            issues.append(f"{i+1}: `NL`/`ind` in output — code-generator variable leaked")

    issues.extend(check_nested_quote(lines))
    issues.extend(check_input_manifest(path, lines))
    return issues


def check_nested_quote(lines):
    """A quote INSIDE a string literal closes it early, and the line still has an EVEN
    quote count — so the odd-quote check passes and the compiler fails somewhere past
    the real fault. Cost a compile round-trip on S4 v9.4:
        tooltip=... the ...-> LEADING... read.   ->  Syntax error at input ">"
    Heuristic: after a title=/tooltip=/shorttitle= literal closes, the next non-space
    character must be a comma or a closing paren. Anything else means the literal ended
    somewhere the author did not intend.
    """
    import re
    pat = re.compile(r'(tooltip|title|shorttitle)\s*=\s*"')
    out = []
    for n, l in enumerate(lines, 1):
        for m in pat.finditer(l):
            j = l.find(chr(34), m.end() - 1) + 1
            e = l.find(chr(34), j)
            if e < 0:
                continue
            nxt = l[e + 1:e + 2]
            if nxt and nxt not in ",) ":
                out.append("%d: string literal ends early -> %s" % (n, l[max(0, e - 30):e + 20]))
    return out

def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    bad = 0
    for path in argv[1:]:
        issues = sweep(path)
        head = path.split("\\")[-1].split("/")[-1]
        if issues:
            bad = 1
            print(f"\n{head}: {len(issues)} issue(s)")
            for s in issues[:40]:
                print(f"   {s}")
            if len(issues) > 40:
                print(f"   … {len(issues)-40} more")
        else:
            print(f"{head}: clean")
    return bad


if __name__ == "__main__":
    sys.exit(main(sys.argv))
