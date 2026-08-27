"""Doc 13 (Unified Ecosystem) — the Wyckoff markers that were added on 26 Aug.

This page was NOT stale: its entry-shapes table listed exactly the ten marks the
script plotted, and its R-canon table already carried the Was/Now migration. What
changed is the code — four Wyckoff plotshapes were added, closing a gap where the
strategy could fire, size and trade a WYC edge while leaving no mark on the chart.

Verified against Weinstein_Unified_Ecosystem_v3.4.pine: the four triggers are mutually
exclusive by construction (each carries `not wyc_has_*` clauses for the others), so at
most one prints per bar. Plot budget 26 -> 30 of 64.
"""
import io

P = "docs_audit/pages/13_unified.html"
h = io.open(P, encoding="utf-8").read()
orig = h

anchor = ('<tr><td class="m">PRE-S2</td><td>yellow dot above the bar</td>'
          '<td><b>Early stage-2 warning — not an entry</b></td></tr>')

addition = ('<tr><td class="m">SPRING</td><td>teal</td><td>Wyckoff spring</td></tr>\n'
            '      <tr><td class="m">SPR+SOS</td><td>teal</td><td>Spring confirmed by a sign of strength — the strongest of the four</td></tr>\n'
            '      <tr><td class="m">SOS</td><td>teal</td><td>Sign of strength, no spring</td></tr>\n'
            '      <tr><td class="m">JAC</td><td>teal</td><td>Jump across the creek</td></tr>\n'
            '      <tr><td class="m">PRE-S2</td><td>yellow dot above the bar</td>'
            '<td><b>Early stage-2 warning — not an entry</b></td></tr>')

assert h.count(anchor) == 1, "entry-shapes anchor not unique"
h = h.replace(anchor, addition)

# a note after that table, explaining why they were absent
tail = "</table></div>"
i = h.find(anchor.split("<tr>")[0])  # not used; locate table end after the addition
i = h.find("PRE-S2")
j = h.find("</table>", i)
k = h.find("</div>", j) + len("</div>")

note = '''
  <div class="note">
    <span class="lbl">Why the Wyckoff marks are new, and what their absence meant</span>
    <p>The four teal marks were added on <b>26 August</b>. Until then the strategy could
    <em>fire, size and trade</em> a Wyckoff edge while leaving <b>no mark on the chart at all</b>:
    v3.4 added the triggers, entries, stops and targets, v3.4.2 added the panel row, and the
    plotshapes were simply never written. Ten catalysts were drawn and Wyckoff was not one of
    them.</p>
    <p>They are teal to separate the accumulation family from the red / purple / blue recovery
    marks, and <b>at most one can print per bar</b> — the four triggers exclude each other by
    construction, so SPR+SOS never appears alongside a bare SPRING.</p>
  </div>'''

h = h[:k] + note + h[k:]

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 13: {len(orig)} -> {len(h)} chars")
