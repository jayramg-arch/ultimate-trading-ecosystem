"""Doc 19 (Performance Ledger) — the provenance split, which is the answer to its own caveat.

The page carries the harvesting retraction well: it says the loss was mostly a
financial-year-end tax batch of discretionary names, that the journal mixes system-entered
and hand-picked trades, and that they "cannot be separated retroactively". All true.

What it never says is that the engine now SPLITS them going forward. Provenance is the
FIRST attribution dimension in the code, the honest scoreboard foregrounds a SYSTEM-only
headline, and the rule is strict on purpose: a trade counts as system only if it carries a
true entry snapshot. That turns the caveat from a permanent disclaimer into a clock — the
record starts accruing the moment guided-exec entries begin closing.

The dimension count was also one short.

Verified in performance_attribution.py:
  DIMENSIONS[0] = ("provenance", "Provenance (System vs Discretionary)")   — 12, not 11
  _is_system()   SYSTEM iff snapshot_meta carries '|recompute'
  a deliberately-rejected looser rule ("any non-empty setup label") is documented at :255
  run_attribution reports system_trades / discretionary side by side, SYSTEM foregrounded
"""
import io

P = "docs_audit/pages/19_performance_ledger.html"
h = io.open(P, encoding="utf-8").read()
orig = h

# ── 1. eleven -> twelve, and provenance leads the list ───────────────────────
old_n = "realised P&amp;L across eleven dimensions"
assert h.count(old_n) == 1
h = h.replace(old_n, "realised P&amp;L across <b>twelve</b> dimensions")

old_dim = ('    <div class="dim"><b>The book</b>System · Sector · Trade type · Hold period · '
           'Exit reason · Trade quality</div>')
new_dim = ('    <div class="dim"><b>The book</b><b>Provenance</b> · System · Sector · Trade type · '
           'Hold period · Exit reason · Trade quality</div>')
assert h.count(old_dim) == 1, "book dimension list not found"
h = h.replace(old_dim, new_dim)

# ── 2. the provenance rule itself ────────────────────────────────────────────
anchor = '  <pre>python performance_attribution.py     # or the Attribution tab in the AUTOPSY page</pre>'
assert h.count(anchor) == 1, "run line not found"

block = '''  <div class="note safe">
    <span class="tag">Provenance — the dimension that answers section 04's caveat</span>
    <p>Provenance is the <b>first</b> cut, before sector or setup, and it asks one question:
    <em>did this system choose this trade?</em> A row counts as <b>SYSTEM</b> only when it carries
    a true entry snapshot — <code>snapshot_meta</code> containing <code>|recompute</code>, which
    only the guided-execution hook writes at the moment of entry. Everything else is
    <b>DISCRETIONARY</b>.</p>
    <p>The looser rule — <em>&ldquo;any non-empty setup label counts&rdquo;</em> — was tried and
    <b>rejected</b>. A backfilled position re-screens as of today, so a name that happens to
    trigger now would be credited to the system retroactively. That is the same flattering-the-book
    error the exit reconcile exposed, in a new place. The strict rule cost the live record a trade
    when it landed; that is what a strict rule is for.</p>
    <p>So the report prints <b>two headlines side by side</b> — SYSTEM-only and all-attributable —
    with SYSTEM foregrounded. <b>The mixed history is not separable, but it is no longer
    growing.</b> Every GM guided-exec entry that closes from here lands on the correct side of
    the line, so the caveat in section 04 has a clock on it rather than being permanent.</p>
  </div>

''' + anchor

h = h.replace(anchor, block)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 19: {len(orig)} -> {len(h)} chars")
