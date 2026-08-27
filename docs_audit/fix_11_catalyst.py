"""Doc 11 (Catalyst Engine) — the target half of the risk policy.

The page documents catalyst-aware STOPS precisely (4.0 / 3.5 / 2.5 / 1.5 verified
against bull_screener.py) and then stops. But target_r_for and partial_qty_for live in
the same file and are just as catalyst-aware, so a reader gets half the policy and has
to guess the rest.

Worth documenting here specifically because the code's own docstring had been wrong
about it in three of four rows until today — a value that drifts inside the source is
exactly the one a guide should pin down.

Verified: POS 3R/5R 25/25 · SWG-BO/PB 2R/4R 33/33 · SWG-REV/GAP 2R/4R 50/50.
"""
import io

P = "docs_audit/pages/11_catalyst_engine.html"
h = io.open(P, encoding="utf-8").read()
orig = h

anchor = '''  <div class="note">
    <span class="tag">Verify the stop before you order</span>'''

addition = '''  <h3>The other half — catalyst-aware targets</h3>
  <p>The same file sets the <b>targets</b> by the same logic, and for the same reason: a horizon
  that justifies a wider stop also justifies a longer objective. Read the two tables together —
  a stop multiple without its target is half a policy.</p>
  <div class="tw"><table>
    <thead><tr><th>Family</th><th>T1 / T2</th><th>Partials</th><th>What happens to the rest</th></tr></thead>
    <tbody>
      <tr><td class="k">POS-* · WYC-* · REV-*</td><td class="m">3R / 5R</td><td class="m">25 / 25</td><td><b>Half the position keeps running</b> on the trail, uncapped</td></tr>
      <tr><td class="k">SWG-BO · SWG-PB</td><td class="m">2R / 4R</td><td class="m">33 / 33</td><td>A third rides on; a 1–4 week move has less left to give</td></tr>
      <tr><td class="k">SWG-REV · SWG-GAP</td><td class="m">2R / 4R</td><td class="m">50 / 50</td><td><b>Nothing rides.</b> A reversal or a gap-fill has no trend to ride</td></tr>
    </tbody>
  </table></div>
  <div class="note warn">
    <span class="tag">The R-canon, and why this table is worth pinning</span>
    <p><b>Nothing under 2R; swing 2R/4R; positional 3R/5R.</b> That is the rule the whole system
    shares — the screener, the allocator and the S4 plan row all read it from here.</p>
    <p>It is documented on this page because <b>the code's own docstring disagreed with the code</b>
    until 26 August, in three of its four rows: it claimed SWG-REV took 2R/2R and SWG-BO/PB took
    3R/5R, while the function returned 2R/4R for both. The constants were right the whole time and
    the prose beside them had simply never been updated. <b>A value that drifts inside its own
    source file is exactly the one a guide has to state independently.</b></p>
  </div>

  <div class="note">
    <span class="tag">Verify the stop before you order</span>'''

assert h.count(anchor) == 1, "insertion anchor not unique"
h = h.replace(anchor, addition)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 11: {len(orig)} -> {len(h)} chars")
