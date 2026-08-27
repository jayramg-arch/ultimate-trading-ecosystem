"""Split gm_pio_list and gm_rff_list back onto separate lines.

MY ERROR. In fix_s4_batch.py I used \\n as a STATEMENT separator between the two
input.string declarations. Inside a normal Python string that writes a literal
backslash-n to the file rather than a line break, so both statements landed on line
960 joined by a backslash sitting OUTSIDE any quotes — which is exactly what Pine
reported: `no viable alternative at character "\\"` at 960:640.

The \\n escapes INSIDE the tooltip text are correct and must survive; only the one
between `")` and `gm_rff_list` is wrong. So the match is anchored on that pair.

Written as a FILE rather than a bash heredoc on purpose: a heredoc de-escapes the
backslash before Python ever sees it, which is how the same mistake got made twice.
Built with chr(92) so the source carries no ambiguous escape at all.
"""
import io

BS = chr(92)          # a single backslash, unambiguously
P = "Section4_Entry_Trigger_v7.2.pine"

s = io.open(P, encoding="utf-8").read()
orig = s

bad = '")' + BS + 'ngm_rff_list = input.string('
good = '")\ngm_rff_list = input.string('

assert s.count(bad) == 1, f"separator not found (count={s.count(bad)})"
s = s.replace(bad, good)

assert s != orig
io.open(P, "w", encoding="utf-8").write(s)

# postcondition: two declarations, two lines, each self-contained
L = s.split("\n")
pio = [(i + 1, l) for i, l in enumerate(L) if l.startswith("gm_pio_list = input.string")]
rff = [(i + 1, l) for i, l in enumerate(L) if l.startswith("gm_rff_list = input.string")]
assert len(pio) == 1 and len(rff) == 1, f"expected one of each, got {len(pio)}/{len(rff)}"
for name, (ln, txt) in (("gm_pio_list", pio[0]), ("gm_rff_list", rff[0])):
    assert txt.count('"') % 2 == 0, f"{name}: odd quote count"
    assert txt.rstrip().endswith(")"), f"{name}: does not close"
    print(f"  {name}: line {ln}, {len(txt)} chars, quotes {txt.count(chr(34))}, closes OK")

# and no stray backslash outside a string anywhere on those lines
for name, (ln, txt) in (("gm_pio_list", pio[0]), ("gm_rff_list", rff[0])):
    outside = txt.split('"')[::2]          # segments OUTSIDE quotes
    assert not any(BS in seg for seg in outside), f"{name}: backslash outside a string"
print("  no backslash outside a string on either line")
