# -*- coding: utf-8 -*-
"""S4 side of the baseCount wiring. RUN ONLY AFTER S4Core is published.

    python apply_basecount.py <core_version>       e.g.  python apply_basecount.py 19

Splits from the S4Core edit for the same reason apply_verdict_move.py did:
bumping an import to a version that does not exist yet burned four compiles in
one day. The version is an argument and the script refuses to run without it.
"""
import io, re, sys

if len(sys.argv) != 2 or not sys.argv[1].isdigit():
    raise SystemExit("usage: python apply_basecount.py <published S4Core version>")
VER = sys.argv[1]
P = r"C:\Users\jayra\Documents\GeminiVSCode\Section4_Entry_Trigger_v7.2.pine"
s = io.open(P, encoding="utf-8").read()
orig = s

# ── 1) inputs ────────────────────────────────────────────────────────────────
anchor = "ext_band_lo = input.float(1.0,"
ins = (
'// BASE COUNT (24-Aug-2026, Jay parameter #2). Rides the EXISTING weekly\n'
'// request.security - no new call. See S4Core.baseCount for the counting rule and\n'
'// its known low-side bias. DISPLAY ONLY: there is no validation run carrying a base\n'
'// count yet, so unlike the extension bands it has no measured threshold and must not\n'
'// gate anything. The 4+ warning below is Jay\'s stated convention, not a fitted number.\n'
'base_min_wks = input.int(5, "Base: weeks of stall that form one", group=grpPZ, minval=2, maxval=15, tooltip="Weeks without a new high before the stall counts as a base. Weinstein bases run 5+ weeks; below about 4 you start counting ordinary pullbacks as bases.")\n'
'base_warn_n = input.int(4, "Base: warn at buy point number", group=grpPZ, minval=2, maxval=8, tooltip="Jay\'s convention: bases 1-2 safest, 3 needs a tighter stop, 4-5 is late and institutions are likely distributing into the strength. Not a fitted threshold - no run has measured base count against outcomes yet.")\n'
)
assert s.count(anchor) == 1, "input anchor"
s = s.replace(anchor, ins + anchor)

# ── 2) the weekly bundle carries it out ──────────────────────────────────────
old = "    (wcross ? 1.0 : 0.0)[_ow]"
new = ("    // baseCount rides this bundle rather than opening a second weekly call. Same\n"
       "    // [_ow] confirm offset as w_cross, so both read the last CLOSED week.\n"
       "    [_bc, _bIn, _bFlat] = core.baseCount(30, 4, base_min_wks)\n"
       "    [(wcross ? 1.0 : 0.0)[_ow], _bc[_ow], _bIn[_ow], _bFlat[_ow]]")
assert s.count(old) == 1, "f_weekly return anchor"
s = s.replace(old, new)

old = ('w_cross = request.security(syminfo.tickerid, "W", f_weekly(), barmerge.gaps_off,'
       " barmerge.lookahead_off)")
new = ('[w_cross, wk_baseN, wk_inBase, wk_baseWks] = request.security(syminfo.tickerid, "W",'
       " f_weekly(), barmerge.gaps_off, barmerge.lookahead_off)")
assert s.count(old) == 1, "w_cross anchor"
s = s.replace(old, new)

# ── 3) on the extension field, beside the other maturity tags ────────────────
old = ('      + (na(ext_sma50_atr) ? "" : "  50D " + (ext_sma50_atr >= 0.0 ? "+" : "")'
       ' + str.tostring(ext_sma50_atr, "0.0") + "\u00d7")')
new = (old + "\n"
       '      + (nz(wk_baseN, 0.0) < 1.0 ? "" : "  base " + str.tostring(wk_baseN, "0")'
       ' + (wk_baseN >= base_warn_n ? " \u26a0" : ""))')
assert s.count(old) == 1, "tag anchor"
s = s.replace(old, new)

s, n = re.subn(r"^import jayramg/S4Core/\d+ as core$",
               "import jayramg/S4Core/%s as core" % VER, s, flags=re.M)
assert n == 1, "import line not found"

# ── postcondition sweep BEFORE writing ───────────────────────────────────────
code = [l for l in s.split("\n") if l.strip() and not l.strip().startswith("//")]
assert not [l for l in code if l.count('"') % 2], "odd-quote code line"
d = 0
for l in code:
    q = False
    for ch in l:
        if ch == '"': q = not q
        elif not q and ch in "([": d += 1
        elif not q and ch in ")]": d -= 1
assert d == 0, "paren depth %d" % d
_c = "\n".join(l for l in code)
rows = re.findall(r"f_row\(\s*(\d+)", _c)
assert len(rows) == len(set(rows)), "duplicate f_row id"
# tuple arity on the weekly destructure
lhs = [l for l in code if l.startswith("[w_cross,")][0]
assert lhs[1:lhs.index("]")].count(",") == 3, "weekly destructure arity"

assert s != orig
io.open(P, "w", encoding="utf-8").write(s)
print("S4 wired to baseCount (import -> S4Core/%s)" % VER)
