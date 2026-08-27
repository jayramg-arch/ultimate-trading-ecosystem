"""Doc 25* (Scanner Filter Map) — a fifth book, and the band collision made specific.

Two changes.

1. There are FIVE books feeding the board, not four. The fifth is Pyramid — holdings the
   auto-pilot rated ADD — and it belongs in this page's matrix precisely BECAUSE it has no
   fundamental gate: you already own the name, so its qualification happened when you
   bought it. That is the sharpest illustration of the page's own thesis (does the gate
   match the question the book is asking), and it was missing.

2. The "recovery band collision" was listed as open with no detail. It is open, and it is
   now stated with both numbers, because "two halves disagreeing about the drawdown window"
   does not tell a reader which two.

Verified:
  gm_trigger_board.py:90   PYRAMID_ARCHETYPE = "Pyramid"
  gm_trigger_board.py:228  PORTFOLIO_PICKS = "FINAL_Portfolio_Picks.csv"
  gm_trigger_board.py:133  PULLBACK_ARCHETYPES = {"Pullback", PYRAMID_ARCHETYPE}
  recovery_screener.py:172 cb_lookback_high_days = 60    Pillar 1 measures off a 60-BAR high
  recovery_screener.py:204 min_stock_correction_pct = 10 regime measures off the 52-WEEK high
"""
import io

P = "docs_audit/pages/25s_scanner_filter_map.html"
h = io.open(P, encoding="utf-8").read()
orig = h

# ── 1. the fifth book ────────────────────────────────────────────────────────
row = ('      <tr><td class="k">Pullback</td><td>The pullback finder over the full universe</td>'
       '<td>The growth score — <b>hard</b></td></tr>')
assert h.count(row) == 1, "pullback source row not found"
h = h.replace(row, row + '\n'
              '      <tr><td class="k">Pyramid</td><td>Holdings the auto-pilot rated <b>ADD</b></td>'
              '<td><b>None</b> — you already own it</td></tr>')

old_claim = "  <p>All four qualify; the board only times."
assert h.count(old_claim) == 1, "all-four line not found"
h = h.replace(old_claim, "  <p>All five qualify; the board only times.")

# titles + nav
for a, b in [("<h2><span class=\"n\">02</span>The four sources</h2>",
              "<h2><span class=\"n\">02</span>The five sources</h2>"),
             ('<a href="#four">The four sources</a>',
              '<a href="#four">The five sources</a>')]:
    assert h.count(a) == 1, f"missing: {a[:40]}"
    h = h.replace(a, b)

# ── 2. why the fifth book has no gate ────────────────────────────────────────
tail = ("  <p>All five qualify; the board only times. The question this document asks is not")
assert h.count(tail) == 1
h = h.replace(tail, '''  <div class="note">
    <span class="tag">The fifth book is the one that proves the rule</span>
    <p><b>Pyramid has no fundamental gate, and should not have one.</b> An add is not a new
    idea — the name passed its screens when you first bought it, and re-running that test today
    would either wave through what you already own or, worse, veto an add on a fundamental
    reading you did not act on at entry.</p>
    <p>What replaces the gate is the ladder: a holding only appears here when
    <b>ADD</b> is its classification, which already requires a leader at a genuine pullback
    rather than an extended one. The break-down guard still applies — arguably harder here than
    anywhere, since a structural break on a name you hold is a reason to sell, not to buy
    more.</p>
  </div>

''' + tail)

# ── 3. the band collision, with both windows named ───────────────────────────
old_coll = ('      <tr><td class="k">The recovery band collision</td><td>Open — two halves of one '
            'filter disagreeing about the drawdown window</td></tr>')
assert h.count(old_coll) == 1, "collision row not found"
new_coll = ('      <tr><td class="k">The recovery band collision</td><td><b>Open</b> — the two '
            'halves measure &ldquo;beaten down&rdquo; against <b>different highs</b>. The signal '
            'test wants 15–35% off a <b>60-bar</b> high; the regime test wants 10–40% off the '
            '<b>52-week</b> high. A name 20% below its two-month high can sit 45% below its '
            'yearly one — passing the first, failing the second, and neither number means what '
            'the other reports</td></tr>')
h = h.replace(old_coll, new_coll)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 25*: {len(orig)} -> {len(h)} chars")
