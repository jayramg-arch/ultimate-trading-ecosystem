"""Doc 16 (Honesty Layer) — the GO-gate replay, and the parity defect it hid.

The page documents replay.py as a buy-at-anchor simulator, which is half of it: the
same file also replays the live GO gate, and that half had drifted from the surfaces
it claims to model. A methods document is exactly where that belongs — the risk is
not that a number is stale but that a reader trusts a measurement of the wrong thing.

Checked against replay.py: LOCATION_RULE, STRUCTURAL_SL, entry_mode default.
"""
import io

P = "docs_audit/pages/16_honesty_layer.html"
h = io.open(P, encoding="utf-8").read()
orig = h

anchor = """Conflating the two once produced a false panic that the stop was too tight.</p>
  </div>
</section>"""

addition = """Conflating the two once produced a false panic that the stop was too tight.</p>
  </div>

  <h3>The other half — replaying the live GO gate</h3>
  <p>The same file replays the <b>four-gate GO</b> against historical bars, so the entry the
  board and Section Four would actually have produced can be measured rather than assumed. Three
  switches decide what it models, and each has a default that is a claim about the live system:</p>
  <div class="tw"><table>
    <thead><tr><th>Switch</th><th>Default</th><th>What it asserts</th></tr></thead><tbody>
      <tr><td class="k"><code>LOCATION_RULE</code></td><td class="m">a2</td><td>A pattern zone stands alone; a pivot shelf needs a confirming source. Set <code>any</code> to reproduce a pre-26-Aug run</td></tr>
      <tr><td class="k"><code>entry_mode</code></td><td class="m">retest</td><td>A limit at the trigger bar's close, not a buy-stop above its high — measured, and it beat the buy-stop across every family</td></tr>
      <tr><td class="k"><code>STRUCTURAL_SL</code></td><td class="m">False</td><td>The structure-anchored stop is available and <b>not</b> used: it had the best mean and passed the OOS gate, and was still rejected because the median went from −0.48R to −1.01R and stop-outs from 11.8% to 52.7%</td></tr>
    </tbody></table></div>
  <div class="note warn">
    <span class="lbl">The defect this exposed, and the general lesson</span>
    <p>Until 26 August <code>replay</code> ran the <b>legacy</b> location rule while the live
    surfaces had moved to A2. Every GO-gate run since 11 August therefore measured
    <b>a gate the system was no longer using</b> — and nothing about the output looked wrong,
    because a simulator that models the wrong rule faithfully still produces clean numbers.</p>
    <p><b>The general form is worth more than the instance:</b> when a harness and a live surface
    encode the same rule twice, they will drift, and the drift is invisible from the results. The
    only defence is to make the default track production and to say so where the default is
    written — which is why the table above states what each one asserts rather than only what it
    is set to.</p>
  </div>
  <p class="refnote">Measured with those switches: the location rule itself is a <b>null</b>.
  Any-zone, A2 and pattern-only landed within <b>0.21 percentage points</b> on matched alpha across
  eighteen anchors, while the trade count fell 221 → 88 → 51. Tightening location buys fewer
  trades, not better ones.</p>
</section>"""

assert h.count(anchor) == 1, "insertion anchor not unique"
h = h.replace(anchor, addition)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 16: {len(orig)} -> {len(h)} chars")
