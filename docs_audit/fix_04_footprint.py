"""Doc 04 (Institutional Footprint) — where the FVG actually lands in the decision.

The page was NOT stale. Its section 01 already reconciles the old markdown guide
against the code, and its contribution table is correct. What it never says is that
one of its outputs — the fair value gap — feeds the LOCATION gate, and at the higher
of the two evidence grades.

Verified at Section4_Entry_Trigger_v7.2.pine:3668 —
  _locPattern = (d_zones and z_inDZ_pat) or (d_lvls and (in_d_fvg or in_w_fvg))
so a daily or weekly FVG satisfies location on its own, exactly as a leg-base-leg
zone does, while a pivot shelf must be confirmed. That is a substantive statement
about how much weight this module carries, and it belonged on this page.
"""
import io

P = "docs_audit/pages/04_footprint.html"
h = io.open(P, encoding="utf-8").read()
orig = h

anchor = "  <h2><span class=\"n\">08</span>The workflow</h2>"

addition = '''  <h3>The FVG is the one output that reaches the entry gate — at pattern grade</h3>
  <p>Everything else on this page <b>grades</b>. The fair value gap <b>gates</b>: a daily or
  weekly FVG satisfies the LOCATION pillar on its own, ranked alongside a leg-base-leg demand
  zone rather than below it.</p>
  <div class="tw"><table>
    <thead><tr><th>Evidence</th><th>Grade</th><th>What it takes to satisfy location</th></tr></thead>
    <tbody>
      <tr><td class="k">Leg-base-leg zone</td><td>Pattern</td><td><b>Stands alone</b></td></tr>
      <tr><td class="k">Fair value gap (D/W)</td><td>Pattern</td><td><b>Stands alone</b> — this module's one gating output</td></tr>
      <tr><td class="k">Pivot shelf or pivot line</td><td>Pivot</td><td>Needs a confirming S/R level or anchored VWAP</td></tr>
      <tr><td class="k">Order block · sweep · BOS · CHoCH</td><td>—</td><td><b>Never gate.</b> They grade, and the change-of-character bonus is deliberately small</td></tr>
    </tbody>
  </table></div>
  <div class="note">
    <span class="lbl">Why an unfilled gap earns that rank</span>
    <p>Both a demand zone and an unfilled gap mark <b>an imbalance that has not been resolved</b>,
    and both carry an edge that defines where you are wrong. A pivot shelf marks only that price
    turned once — which is why it is the one form of location that has to be corroborated.</p>
    <p>The practical consequence: <b>turning the levels display off does not merely hide the
    gaps, it removes a way for a name to pass location.</b> That is the opposite of how a display
    toggle usually behaves, and it is worth knowing before you switch it.</p>
  </div>

''' + anchor

assert h.count(anchor) == 1, "section 08 anchor not unique"
h = h.replace(anchor, addition)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 04: {len(orig)} -> {len(h)} chars")
