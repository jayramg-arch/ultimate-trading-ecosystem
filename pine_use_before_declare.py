"""Global-scope use-before-define check for a Pine file.

WHY: this class has now bitten twice in two days -- rs_trade_type referenced 120
lines above where it was built, and _gmBff/_gmRff/_gmRank referenced ~1,380 lines
above. Neither is a syntax error, so nothing local catches it; you find out from
the compiler, one round-trip later. A hand-written list of "names to check" caught
the first and missed the second, which is the whole problem with hand-written lists.

Scope: GLOBAL declarations only (column 0). Anything indented is inside a function
or an if-block, where Pine's own scoping rules apply and this analysis would be
wrong. Comments and string literals are stripped first so a name mentioned in prose
does not count as a use.
"""
import io
import re
import sys

P = sys.argv[1] if len(sys.argv) > 1 else \
    r"C:\Users\jayra\Documents\GeminiVSCode\Section4_Entry_Trigger_v7.2.pine"

TYPES = r"(?:int|float|bool|string|color|line|label|box|table|array|matrix|map|" \
        r"simple|series|var|varip)"


def strip(line):
    """Drop the comment tail and blank out string literals."""
    out, inq, k = [], False, 0
    while k < len(line):
        c = line[k]
        if inq:
            if c == chr(92):
                k += 2
                continue
            if c == '"':
                inq = False
            out.append(" ")
            k += 1
            continue
        if c == '"':
            inq = True
            out.append(" ")
            k += 1
            continue
        if c == "/" and k + 1 < len(line) and line[k + 1] == "/":
            break
        out.append(c)
        k += 1
    return "".join(out)


lines = io.open(P, encoding="utf-8").read().split("\n")

decl = {}      # name -> first global declaration line
for i, raw in enumerate(lines, 1):
    if raw[:1] in (" ", "\t", "") or raw.lstrip().startswith("//"):
        continue
    t = strip(raw)
    # tuple destructure:  [a, b, c] = ...
    m = re.match(r"\s*\[([^\]]+)\]\s*=", t)
    if m:
        for nm in m.group(1).split(","):
            nm = nm.strip().split()[-1]
            decl.setdefault(nm, i)
        continue
    # plain:  [type] name = ...     or     name(args) =>
    m = re.match(r"\s*(?:%s\s+)*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|=)(?!=)" % TYPES, t)
    if m:
        decl.setdefault(m.group(1), i)

bad = []
for i, raw in enumerate(lines, 1):
    # USES are checked at global scope ONLY, for the same reason declarations are.
    # An indented line is inside a function body, and a function may legitimately
    # reference a name destructured from its OWN call site further down -- that is
    # how every f_fold* in this file works. Scanning those produced 108 false
    # positives on the first run and would have buried the real ones.
    if raw[:1] in (" ", "	", "") or raw.lstrip().startswith("//"):
        continue
    t = strip(raw)
    # do not count the declaration itself as a use
    body = re.sub(r"^\s*(?:\[[^\]]+\]|(?:%s\s+)*[A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|=)(?!=)"
                  % TYPES, "", t, count=1)
    for nm in set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", body)):
        d = decl.get(nm)
        if d is not None and i < d:
            bad.append((i, nm, d))

if bad:
    print("USE BEFORE GLOBAL DECLARATION (%d):" % len(bad))
    for i, nm, d in sorted(bad)[:40]:
        print("   line %-6d uses %-18s declared at %d" % (i, nm, d))
else:
    print("no global use-before-declare found (%d global names checked)" % len(decl))
