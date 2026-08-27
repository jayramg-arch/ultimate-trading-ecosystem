"""Doc 18 (Trade Funnel) — the exit tables, which the page itself flagged as legacy.

This page already knew: it says the targets moved "5R/10R -> 3R/5R" and then adds that
"their body tables still show the legacy values — as does the exit section here". The
defect was named and left standing, which is worse than not knowing: a reader who skims
the table gets a number the page disowned two screens earlier.

Two things were wrong, not one. The tables carried +2.5R / 30% and +3.5R, and the
summary line said "3R/5R at 33%" — which conflates the families: 3R/5R is positional at
25/25, while 33/33 belongs to the swing breakout pair at 2R/4R.

Verified in code:
  bull_screener.target_r_for / partial_qty_for
    POS-* · WYC-* · REV-*  -> 3R / 5R, partials 25 / 25
    SWG-BO · SWG-PB        -> 2R / 4R, partials 33 / 33
    SWG-REV · SWG-GAP      -> 2R / 4R, partials 50 / 50
  risk_common.trail_mult_for    POS 4.5 · WYC 3.5 · REV 2.5 · SWG 1.5 (+0.5 in a bear tape)
  risk_common.trail_window_for  SWG 14 bars · POS/WYC/REV 22 bars

Anchors deliberately avoid line breaks: the source wraps mid-sentence, and a multi-line
anchor is how the last three attempts at this failed.
"""
import io

P = "docs_audit/pages/18_trade_funnel.html"
h = io.open(P, encoding="utf-8").read()
orig = h

# ── 1. the summary line that conflated the two families ──────────────────────
old_sum = "targets 5R/10R→3R/5R at 33%"
new_sum = ("targets 5R/10R→3R/5R for positional at 25/25, and 2R/4R for swing at 33/33 "
           "— two families, two answers")
assert h.count(old_sum) == 1, "summary line not found"
h = h.replace(old_sum, new_sum)

# ── 2. the admission, which is no longer true of this page ───────────────────
old_admit = "show the legacy values — as does the exit section here."
new_admit = ("show the legacy values. <b>The exit tables on this page were rebuilt directly "
             "from the code on 26 Aug.</b>")
assert h.count(old_admit) == 1, "admission not found"
h = h.replace(old_admit, new_admit)

# ── 3. rebuild both exit tables from the code ────────────────────────────────
i = h.find("Bull track")
j = h.find("Recovery regime-change override")
assert 0 < i < j, "exit tables not located"

tables = '''Bull track</h4>
  <div class="tw"><table>
    <thead><tr><th>Edge</th><th>T1</th><th>Take</th><th>T2</th><th>Take</th><th>Trail after T2</th><th>Time stop</th></tr></thead>
    <tbody>
      <tr><td class="k">POS-BO</td><td class="m">3R</td><td class="m">25%</td><td class="m">5R</td><td class="m">25%</td><td>Chandelier · 22-bar · ATR×4.5 (+0.5 bear)</td><td>6 wk if &lt; 0.5R</td></tr>
      <tr><td class="k">POS-ACCUM</td><td class="m">3R</td><td class="m">25%</td><td class="m">5R</td><td class="m">25%</td><td>Chandelier · 22-bar · ATR×4.5</td><td>6 wk if &lt; 0.5R</td></tr>
      <tr><td class="k">SWG-BO</td><td class="m">2R</td><td class="m">33%</td><td class="m">4R</td><td class="m">33%</td><td>Chandelier · 14-bar · ATR×1.5</td><td>10d if &lt; 0.5R</td></tr>
      <tr><td class="k">SWG-PB</td><td class="m">2R</td><td class="m">33%</td><td class="m">4R</td><td class="m">33%</td><td>Chandelier · 14-bar · ATR×1.5</td><td>10d if &lt; 0.5R</td></tr>
      <tr><td class="k">SWG-GAP</td><td class="m">2R</td><td class="m">50%</td><td class="m">4R</td><td class="m">50%</td><td><b>Nothing rides</b> — fully out at T2</td><td>10d</td></tr>
      <tr><td class="k">SWG-REV</td><td class="m">2R</td><td class="m">50%</td><td class="m">4R</td><td class="m">50%</td><td><b>Nothing rides</b> — fully out at T2</td><td>5d by design</td></tr>
    </tbody>
  </table></div>
  <div class="note">
    <span class="lbl">Read the partials, not just the targets</span>
    <p>The percentages are the policy, not a detail. <b>Positional keeps HALF the position running
    past T2</b> on an uncapped trail — that is where a trend trade earns its keep, and it is why
    its targets sit further out. The swing breakout pair leaves a third on. <b>The two fast
    families leave nothing</b>, because a gap-fill and a reversion have no trend to ride.</p>
    <p>The trail is <b>trade-type aware in two ways at once</b>: the multiple comes from the
    catalyst family, the lookback from the horizon — 22 bars positional, 14 swing. The anchor and
    its volatility unit have to sit on the same clock, or the stop means something different from
    one bar to the next.</p>
  </div>

  <h4>Recovery track</h4>
  <div class="tw"><table>
    <thead><tr><th>Edge</th><th>Initial SL</th><th>T1</th><th>Take</th><th>T2</th><th>Trail after T2</th><th>Time stop</th></tr></thead>
    <tbody>
      <tr><td class="k">REV-CB</td><td>Climax low − 0.5×ATR</td><td class="m">3R</td><td class="m">25%</td><td class="m">5R</td><td>Chandelier · 22-bar · ATR×2.5</td><td>15d</td></tr>
      <tr><td class="k">REV-RS</td><td>Higher low − pad</td><td class="m">3R</td><td class="m">25%</td><td class="m">5R</td><td>Chandelier · 22-bar · ATR×2.5</td><td>15d</td></tr>
      <tr><td class="k">REV-EARLY</td><td>NR7 low − pad</td><td class="m">3R</td><td class="m">25%</td><td class="m">5R</td><td>Chandelier · 22-bar · ATR×2.5</td><td>15d</td></tr>
      <tr><td class="k">WYC-*</td><td>Base low − 0.3×ATR</td><td class="m">3R</td><td class="m">25%</td><td class="m">5R</td><td>Chandelier · 22-bar · ATR×3.5</td><td>positional clock</td></tr>
    </tbody>
  </table></div>
  <div class="note warn">
    <span class="lbl">Breakeven lock still applies to every edge</span>
    <p>Once T1 fills, the stop floor moves to the entry price. <b>The runner cannot turn into a
    loss.</b> That rule sits above the table and is not catalyst-specific.</p>
  </div>

  <h4>'''

h = h[:i] + tables + h[j:]

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 18: {len(orig)} -> {len(h)} chars")
