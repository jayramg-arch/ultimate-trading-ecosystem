"""S4 panel batch — Jay's items 1 and 3-8.

TOKEN BUDGET IS THE CONSTRAINT. S4 compiles at ~100,069 of 100,256, so there is roughly
190 tokens of headroom and this batch has to fit inside it. The rule that makes that
possible: a STRING LITERAL costs one token however long it is, while every ternary,
concat and call costs. So wherever a dot can be folded into an existing literal it is
free, and a new ternary is only spent where no literal exists to carry it.

  #3  merge_cells indices     0 tokens   (three integer literals)
  #4  WCL setup ticks         0 tokens   (literal swap)
  #5  Volume Profile ticks    0 tokens   (literal swap)
  #6  CPR / MVWAP / VCP dots  0 tokens   (folded into existing ternary branches)
      ADX dot                ~6 tokens   (one new ternary, reusing the row's own test)
  #7  Intraday dots           0 tokens   (literal swap inside the existing ternary)
  #8  Arrival / delta dots   ~12 tokens  (two new ternaries)
  #1  Piotroski              ~40 tokens  (one input, two calls, one concat)

#3 IS A REAL BUG, not styling. TRIGGER/STATUS/VERDICT are written to rows 31/32/33 but
merge_cells is called on 33/34/35 -- the indices were never updated when the panel was
renumbered for the RE10040 fix. So those three value cells are NEVER merged (the column
dividers keep showing through, which is the "black grid") while rows 33/34/35 get merged
by accident.
"""
import io

P = "Section4_Entry_Trigger_v7.2.pine"
s = io.open(P, encoding="utf-8").read()
orig = s
did = {}


def sub(old, new, key, count=1):
    global s
    n = s.count(old)
    assert n == count, f"{key}: expected {count} match(es), found {n} for {old[:60]!r}"
    s = s.replace(old, new)
    did[key] = did.get(key, 0) + n


# ── #3 · merge the rows the cells are actually on ────────────────────────────
sub("    table.merge_cells(pnl, 1, 33, PA_LAST_COL, 33)",
    "    table.merge_cells(pnl, 1, 31, PA_LAST_COL, 31)   // TRIGGER lives on 31",
    "3 TRIGGER merge")
sub("    table.merge_cells(pnl, 1, 34, PA_LAST_COL, 34)",
    "    table.merge_cells(pnl, 1, 32, PA_LAST_COL, 32)   // STATUS lives on 32",
    "3 STATUS merge")
sub("        table.merge_cells(pnl, 1, 35, PA_LAST_COL, 35)",
    "        table.merge_cells(pnl, 1, 33, PA_LAST_COL, 33)   // VERDICT lives on 33",
    "3 VERDICT merge")

# ── #4 · WCL setup: tick -> dot, matching the GM-rank vocabulary ─────────────
for lit in ('"✓ S2 — Spring/LPS Reversal"', '"✓ S1 — OB Retest + VP Support"',
            '"✓ S5 — Stage 2 Continuation > VAH"'):
    sub(lit, lit.replace("✓", "🟢"), "4 WCL setup")

# ── #5 · Volume Profile: tick/cross -> the panel's own dot vocabulary ────────
#   🟢 accepted above value · ⚪ inside but below the POC · 🔴 below value entirely
sub('"✓ ABOVE VAH"', '"🟢 ABOVE VAH"', "5 VP")
sub('"✓ IN VA (upper)"', '"🟢 IN VA (upper)"', "5 VP")
sub('"✗ IN VA (lower)"', '"⚪ IN VA (lower)"', "5 VP")
sub('"✗ BELOW VAL"', '"🔴 BELOW VAL"', "5 VP")

# ── #6 · Momentum & value ────────────────────────────────────────────────────
# CPR / MVWAP / VCP dots ride inside ternary branches that already exist, so they
# cost nothing. Above the pivot is constructive, below it is not.
sub('"CPR —"', '"⚪ CPR —"', "6 CPR")
sub('"above CPR "', '"🟢 above CPR "', "6 CPR")
sub('"below CPR "', '"🔴 below CPR "', "6 CPR")
sub('"MVWAP —"', '"⚪ MVWAP —"', "6 MVWAP")
sub('"above MVWAP "', '"🟢 above MVWAP "', "6 MVWAP")
sub('"below MVWAP "', '"🔴 below MVWAP "', "6 MVWAP")
sub('"  │  VCP " + (kVCP ? "✓" : "·")', '"  │  VCP " + (kVCP ? "🟢" : "⚪")', "6 VCP")

# ADX is the one value with no existing ternary to fold into, so it buys one. The test
# is the SAME one the row's colour already uses, so the dot and the colour cannot
# disagree -- the rule the status strip follows.
sub('string _momTxt = "ADX " + str.tostring(_adxV, "0.0")',
    'string _momTxt = (_adxV >= 25.0 and _diP > _diM ? "🟢 " : _adxV < 20.0 ? "⚪ " : "🔴 ")'
    ' + "ADX " + str.tostring(_adxV, "0.0")',
    "6 ADX")
# ATR carries a neutral dot: it is a volatility MEASURE, not a verdict -- there is no
# level of it that is good or bad on its own, and a green/red here would imply one.
sub('+ "  │  ATR " + (_atrPct > 0 ? str.tostring(_atrPct, "0.0") + "%" : "—")',
    '+ "  │  ⚪ ATR " + (_atrPct > 0 ? str.tostring(_atrPct, "0.0") + "%" : "—")',
    "6 ATR")

# ── #6b · Price vs EMA20 (the extension band) ───────────────────────────────
# Same rule: the dot rides the band literals, which already exist.
sub('_xa >= ext_atr_max ? "LATE"', '_xa >= ext_atr_max ? "🔴 LATE"', "6 EMA band")
sub('_xa >= ext_warn_atr ? "EXTENDED" : _xa >= ext_band_hi ? "CHASING"',
    '_xa >= ext_warn_atr ? "🔴 EXTENDED" : _xa >= ext_band_hi ? "⚪ CHASING"', "6 EMA band")
sub('_xa >= ext_band_lo ? "SWEET SPOT" : "EARLY"',
    '_xa >= ext_band_lo ? "🟢 SWEET SPOT" : "⚪ EARLY"', "6 EMA band")
sub('ema_txt := "RESISTANCE (hit head)"', 'ema_txt := "🔴 RESISTANCE (hit head)"', "6 EMA state")
sub('ema_txt := "SUPPORT (bounced)"', 'ema_txt := "🟢 SUPPORT (bounced)"', "6 EMA state")
sub('ema_txt := "NEAR (" + str.tostring(_emaDist, "0.0") + "%)"',
    'ema_txt := "⚪ NEAR (" + str.tostring(_emaDist, "0.0") + "%)"', "6 EMA state")

# ── #7 · Intraday: red on the one state that means "nothing is happening" ───
sub('(intra_ok_v ? (require_squeeze ? "GO 10EMA+sqz" : "GO 10EMA") : '
    '(ema_reclaim[_so] ? "10EMA ok" : (sqz_on[_so] ? "sqz ON, wait EMA" : "wait")))',
    '(intra_ok_v ? (require_squeeze ? "🟢 GO 10EMA+sqz" : "🟢 GO 10EMA") : '
    '(ema_reclaim[_so] ? "⚪ 10EMA ok" : (sqz_on[_so] ? "⚪ sqz ON, wait EMA" : "🔴 wait")))',
    "7 intraday")

# ── #8 · Arrival · Δ ────────────────────────────────────────────────────────
# FAST into demand tends to reject, GRIND tends to bleed through -- so the dots are
# not decoration, they are the read. Delta follows the same logic on absorption.
sub('string _arrTxt = (_arS == "—") ? "— (not at a zone)" : (_arS + ',
    'string _arrTxt = (_arS == "—") ? "— (not at a zone)" : '
    '((_arS == "FAST" ? "🟢 " : _arS == "GRIND" ? "🔴 " : "⚪ ") + _arS + ',
    "8 arrival")
sub('+ "  │  " + of_read[_so])',
    '+ "  │  " + (str.contains(of_read[_so], "ABSORB") ? "🟢 " : '
    'str.contains(of_read[_so], "BLEED") ? "🔴 " : "⚪ ") + of_read[_so])',
    "8 delta")

# ── #1 · Piotroski F-Score, carried from the GM like BFF/RFF/RANK ───────────
# One more bundle section rather than new machinery: the same core.bundleSection reader
# and the same core.fundScore parser the other three already use, so no library change
# and no publish cycle. Pine cannot compute an F-Score -- it needs nine fundamental
# comparisons against the prior year, and request.financial() is capped at five calls.
sub('gm_rff_list = input.string("", "GM: RFF scores  (SYM:n, paste from the Golden Matcher)"',
    'gm_pio_list = input.string("", "GM: Piotroski F-Score  (SYM:n, paste from the Golden Matcher)",'
    ' group=grpPA, tooltip="The Piotroski F-Score (0-9) the X-Ray computed. Nine pass/fail'
    ' fundamental tests -- profitability, leverage and operating efficiency, each against'
    ' the PRIOR year. Pine cannot compute it: that is far more than the five'
    ' request.financial() calls TradingView allows, and the board has already paid for it.\\n\\n'
    'Format: SYM:n pairs - RELIANCE:7, TECHM:5.\\n\\n'
    '7-9 is strong, 4-6 middling, 0-3 weak. DISPLAY ONLY: it never gates and never scores.'
    ' Absent renders an em-dash, because unscored and scored-badly are different facts.")\\n'
    'gm_rff_list = input.string("", "GM: RFF scores  (SYM:n, paste from the Golden Matcher)"',
    "1 piotroski input")

sub('float _rnkV = core.fundScore(_gmRank, syminfo.ticker)',
    'float _rnkV = core.fundScore(_gmRank, syminfo.ticker)\n'
    'float _pioV = core.fundScore(f_gmPick(gm_pio_list, "PIO"), syminfo.ticker)',
    "1 piotroski value")

sub('"  │  BFF " + (na(_bffV) ? "—" : str.tostring(_bffV, "0") + (_bffV >= 4 ? " 🟢" : " ⚪"))',
    '"  │  BFF " + (na(_bffV) ? "—" : str.tostring(_bffV, "0") + (_bffV >= 4 ? " 🟢" : " ⚪"))'
    ' + "  │  F " + (na(_pioV) ? "—" : str.tostring(_pioV, "0") + "/9"'
    ' + (_pioV >= 7 ? " 🟢" : _pioV >= 4 ? " ⚪" : " 🔴"))',
    "1 piotroski display")

assert s != orig
io.open(P, "w", encoding="utf-8").write(s)
for k in sorted(did):
    print(f"  {did[k]:2}x  {k}")
print(f"  ({sum(did.values())} edits)")
