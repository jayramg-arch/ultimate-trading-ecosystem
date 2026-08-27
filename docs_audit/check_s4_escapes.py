"""Sweep S4 for backslashes sitting OUTSIDE a string literal.

This is the failure class that just cost a compile: a backslash is legal inside a Pine
string (an escape) and meaningless outside one, so a stray literal `\\n` used as a
statement separator parses as garbage. Grep cannot tell the two apart; splitting each
line on its quotes can.

Reports every code line whose out-of-quote segments contain a backslash, plus the
usual odd-quote and continuation checks. Run after ANY scripted edit to this file.
"""
import io
import sys

BS = chr(92)
P = sys.argv[1] if len(sys.argv) > 1 else "Section4_Entry_Trigger_v7.2.pine"

lines = io.open(P, encoding="utf-8").read().split("\n")
bad_bs, odd_q = [], []

for i, ln in enumerate(lines, 1):
    code = ln.split("//")[0] if ln.strip().startswith("//") else ln
    if ln.strip().startswith("//"):
        continue                      # a comment may say anything
    # An ESCAPED quote (\") is a legal character inside a Pine string -- alert
    # messages use it for {{plot("...")}} placeholders. A naive split on '"' counts
    # it as a boundary, mis-segments the rest of the line and reports every such
    # alertcondition as a stray backslash. Neutralise escaped quotes before
    # segmenting; the backslash we are hunting is the one OUTSIDE any string.
    probe = ln.replace(BS + '"', "\x00")
    if probe.count('"') % 2:
        odd_q.append(i)
        continue                      # unbalanced: the split below would be nonsense
    outside = probe.split('"')[::2]   # even segments are OUTSIDE quotes
    if any(BS in seg for seg in outside):
        bad_bs.append((i, ln.strip()[:90]))

print(f"{P}")
print(f"  lines                      : {len(lines)}")
print(f"  odd-quote code lines       : {odd_q if odd_q else 'none'}")
print(f"  backslash outside a string : {len(bad_bs)}")
for i, t in bad_bs[:10]:
    print(f"     {i}: {t}")

src = "\n".join(lines)
print(f"  paren delta                : {src.count('(') - src.count(')')}  (pre-existing +1 lives in a string)")
print(f"  bracket delta              : {src.count('[') - src.count(']')}")
sys.exit(1 if (bad_bs or odd_q) else 0)
