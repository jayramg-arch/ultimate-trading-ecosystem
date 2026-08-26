"""Generate the Pine sector map in S4Core from sectors.db. Regenerate, never hand-edit."""
import sqlite3, io
try:
    from dhan_ohlcv import canonical_nse_symbol as _canon
except Exception:
    _canon = None

def fix(x):
    x = (x or "").strip().upper()
    if _canon:
        try:
            return (_canon(x) or x).upper()
        except Exception:
            return x
    return x

c = sqlite3.connect("sectors.db")
meta = {r[0]: (r[1] or r[0]) for r in c.execute("SELECT sector_index, display_name FROM sector_meta")}
raw = list(c.execute("SELECT symbol, sector_index, source, confidence FROM stock_sector "
                     "WHERE symbol IS NOT NULL AND sector_index IS NOT NULL"))

def rank(src, si, conf):
    return (0 if str(src).startswith("user_") else 1,
            0 if str(si).startswith("NSE:") else 1,
            0 if str(conf) == "curated" else 1)

best, seen = {}, {}
for sym, si, src, conf in raw:
    k = fix(sym)
    seen.setdefault(k, set()).add(si)
    if k not in best or rank(src, si, conf) < best[k][1]:
        best[k] = ((sym, si), rank(src, si, conf))
for k in sorted(seen):
    if len(seen[k]) > 1:
        print(f"  CONFLICT {k}: {sorted(seen[k])}  -> kept {best[k][0][1]} (row '{best[k][0][0]}')")

pairs = sorted((k, v[0][1]) for k, v in best.items())
idxs = sorted({si for _, si in pairs}); code = {si: i for i, si in enumerate(idxs)}
names = [meta.get(si, str(si)) for si in idxs]
syms = [s for s, _ in pairs]; codes = [str(code[si]) for _, si in pairs]

def chunks(seq, n=90):
    return [",".join(seq[i:i+n]) for i in range(0, len(seq), n)]

def emit(var, lits):
    out = []
    for i, ch in enumerate(lits):
        tail = "," if i < len(lits) - 1 else ""
        pre = f"        string {var} = " if i == 0 else f"        {var} += "
        out.append(f'{pre}"{ch}{tail}"')
    return "\n".join(out)

pine = f'''
// ─────────────────────────────────────────────────────────────────────────────
// SECTOR MAP — Jay's curated NSE stock→sector database, generated from sectors.db
// on 26-Aug-2026: {len(syms)} symbols, {len(names)} sectors.
//
// WHY IT LIVES HERE: a library compiles separately, so the calling script spends ONE
// call, not {len(syms)} comparisons. And a STRING LITERAL costs ONE compiled token however
// long it is — which is why the map is packed into literals rather than a switch or
// array.from() (array.from would also blow the 254-argument limit at this size).
//
// Built with successive += rather than one wrapped str.split(...) argument: a
// continuation line indented by a multiple of 4 parses as a new block in Pine, a trap
// this codebase has hit before.
//
// Symbols are canonicalised through dhan_ohlcv.canonical_nse_symbol at generation
// time, so separator variants (ARE_M, L_T, M_M) become the real NSE ticker and match
// syminfo.ticker. Where that merge collided on two sectors the generator resolves by
// precedence (user_* source > NSE: index > curated > auto) and PRINTS the collision.
//
// REGENERATE with _gen_sector_tmp.py — sectors.db is the source of truth.
// An unknown symbol returns "" so the caller can fall back and the absence stays
// visible. Never guess a sector.
// ─────────────────────────────────────────────────────────────────────────────
// @function    Sector for an NSE symbol, from the curated mapping.
// @param sym   Bare NSE symbol, e.g. syminfo.ticker ("RELIANCE", "M&M").
// @returns     Display sector name, or "" when the symbol is not mapped.
export sectorOf(string sym) =>
    // The arrays are function-LOCAL vars, not globals: Pine forbids a function
    // assigning to a global ("Cannot modify global variable in function"), and a
    // library export is still a function. `var` inside the body gives the same
    // build-once behaviour with a legal scope.
    var array<string> _secSym = na
    var array<string> _secCod = na
    var array<string> _secNam = na
    if na(_secSym)
{emit("_a", chunks(syms))}
{emit("_b", chunks(codes))}
        _secSym := str.split(_a, ",")
        _secCod := str.split(_b, ",")
        _secNam := str.split("{",".join(names)}", ",")
    string _out = ""
    if not na(sym) and array.size(_secSym) > 0
        int _i = array.indexof(_secSym, str.upper(sym))
        if _i >= 0
            int _c = math.round(nz(str.tonumber(array.get(_secCod, _i)), -1))
            if _c >= 0 and _c < array.size(_secNam)
                _out := array.get(_secNam, _c)
    _out
'''
# Replace the block in S4Core rather than appending a second copy.
core = io.open('S4Core.pine', encoding='utf-8').read()
mark = '// SECTOR MAP'
if mark in core:
    core = core[:core.index(mark)]
hdr = core.rstrip(chr(10))
io.open('S4Core.pine', 'w', encoding='utf-8').write(hdr + chr(10) + pine)
print(f"symbols={len(syms)} sectors={len(names)} chunks={len(chunks(syms))}")
