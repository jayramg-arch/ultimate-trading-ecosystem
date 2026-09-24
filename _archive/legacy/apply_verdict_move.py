# -*- coding: utf-8 -*-
"""S4 side of the verdictRead migration. RUN ONLY AFTER S4Core is published.

    python apply_verdict_move.py <core_version>       e.g.  python apply_verdict_move.py 16

Replaces S4's 184-line VERDICT ladder (5406-5589) with a single call into the
library, and bumps the import to the version you actually published. Split from
the S4Core edit deliberately: bumping an import to a version that does not exist
yet is how four compiles were burned in one day (see library-version-sequencing).
"""
import io, re, sys

if len(sys.argv) != 2 or not sys.argv[1].isdigit():
    raise SystemExit("usage: python apply_verdict_move.py <published S4Core version, digits only>")
VER = sys.argv[1]
P = r"C:\Users\jayra\Documents\GeminiVSCode\Section4_Entry_Trigger_v7.2.pine"
src = io.open(P, encoding="utf-8").read()
lines = src.split("\n")

start, end = 5406, 5589
assert lines[start-1].strip() == 'string _L1 = ""', "start anchor moved: " + lines[start-1][:60]
assert lines[end-1].lstrip().startswith("_aVer := _L1"), "end anchor moved: " + lines[end-1][:60]

PARAMS = ("C_NO C_OK C_WARN _act _atValue _band_r _blk _blueSky _cl_r _degTxt _extTxt _extV _off52v "
          "_ovh _pbLvl _qArrBad _qArrGood _qExt _qLocWeak _qRoomBad _qSupply _roomWord _so_high "
          "_stage2ok any_pa_v cf_strong cf_v go_v is_rec_v momentum_clear pl_entry pl_rr1 pl_t1 "
          "stage_n stage_skip support_v trigAge trigHi tt_swing use_retest").split()

call = ["    // VERDICT - the 184-line ruling ladder now lives in S4Core.verdictRead (24-Aug-2026,",
        "    // Jay: \"free up the tokens on S4\"). A library body compiles separately, so the whole",
        "    // block's cost left this file; only this call remains. Behaviour is byte-identical -",
        "    // it was a verbatim lift, and the branch ORDER is what decides the ruling.",
        "    // Params are POSITIONAL: keep this list in the library's declared order, and add any",
        "    // new one at the END so nothing already here shifts.",
        "    [_aVerL, _anColL] = core.verdictRead("]
cur = "        "
for i, p in enumerate(PARAMS):
    piece = p + (", " if i < len(PARAMS)-1 else ")")
    if len(cur) + len(piece) > 100:
        call.append(cur); cur = "      " + piece      # 6 spaces - not a multiple of 4
    else:
        cur += piece
call.append(cur)
call += ["    _aVer  := _aVerL",
         "    _anCol := _anColL"]

out = lines[:start-1] + call + lines[end:]
src2 = "\n".join(out)
src2, n = re.subn(r"^import jayramg/S4Core/\d+ as core$",
                  "import jayramg/S4Core/%s as core" % VER, src2, flags=re.M)
assert n == 1, "import line not found"

# postcondition sweep BEFORE writing
code = [l for l in src2.split("\n") if l.strip() and not l.strip().startswith("//")]
assert not [l for l in code if l.count('"') % 2], "odd-quote code line introduced"
d = 0
for l in code:
    q = False
    for ch in l:
        if ch == '"': q = not q
        elif not q and ch in "([": d += 1
        elif not q and ch in ")]": d -= 1
assert d == 0, "paren depth %d" % d
# CODE lines only. A comment at v7.2:406 reads "f_row(14/15/16/17)" while
# documenting the panel layout, so a raw scan reports a false duplicate.
_code = "\n".join(l for l in src2.split("\n") if not l.strip().startswith("//"))
rows = re.findall(r"f_row\(\s*(\d+)", _code)
assert len(rows) == len(set(rows)), "duplicate f_row id"

io.open(P, "w", encoding="utf-8").write(src2)
print("S4 patched: %d lines -> %d (import -> S4Core/%s)" % (len(lines), len(out), VER))
print("removed %d lines from the main body" % (len(lines) - len(out)))
