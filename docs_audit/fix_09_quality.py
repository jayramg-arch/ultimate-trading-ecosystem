"""Doc 09 (Quality on Sale) — two numbers for one target, in two modules.

The page is accurate everywhere I checked it. Its six corrections all hold at source
(rff_min_score = 5, the 15-35% drawdown BAND, the 10-40% regime band), and the trade-levels
description matches recovery_screener.py:1242 exactly.

The defect is not in the page — it is BETWEEN modules, and the page is where a reader
would meet it:

    recovery_screener.py:1242    t1 = c + risk * 2.5        the plan you READ
    bull_screener.target_r_for   REV-* -> 3.0R / 5.0R       the plan that gets PLACED

Same family, two answers. Left as-is in code deliberately: 2.5 is inside the screener's
signal output and changing it moves what the pending recovery re-baseline is measuring.
That is Jay's call, not an unattended edit — so the page states the gap and says which
number wins at the order.

Verified: bull_screener.target_r_for("REV-CB") -> (3.0, 5.0), partial_qty_for -> (25, 25).
"""
import io

P = "docs_audit/pages/09_quality_on_sale.html"
h = io.open(P, encoding="utf-8").read()
orig = h

anchor = "  <h2><span class=\"n\">07</span>The chart table</h2>"
assert h.count(anchor) == 1, "section 07 anchor not unique"

note = '''  <div class="note warn">
    <span class="tag">Known gap — the target on this row is not the target on the order</span>
    <p>The row plans <b>T1 at 2.5R</b>. The exit policy that governs recovery positions once you
    are in one plans <b>3R and 5R, taking 25% at each</b>. Same family, two numbers, two
    modules — the screener sets the level you read, the risk layer sets the legs that actually
    rest at the broker.</p>
    <p><b>At the order, the exit policy wins.</b> Treat the 2.5R here as what it is: a
    reward-plausibility check at screening time, used to grade R:R and to reject setups with no
    room. It is not the target you place.</p>
    <p>The gap is deliberate for now rather than overlooked — 2.5 sits inside the screener's
    signal output, so moving it changes what the pending recovery re-baseline measures.
    Reconciling the two is a decision to take with that run's result in hand, not before it.</p>
  </div>

''' + anchor

h = h.replace(anchor, note)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 09: {len(orig)} -> {len(h)} chars")
