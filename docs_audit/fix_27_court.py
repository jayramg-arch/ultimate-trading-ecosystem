"""Doc 27 (Backtest Court) — two re-baselines the page predates, and the location A/B.

Section 08 is a PRESENT-TENSE claim ("what the harness currently says"), which is the
one shape of statement that cannot age gracefully. It was well hedged at +0.5 to
+1.0%, but two correctness re-baselines have landed since, and the second of them
matters more than the number: it showed the headline was carried by a single trade.

LAST_RUN checked from validation_runs/LAST_RUN.txt = 20260819_112959.
"""
import io

P = "docs_audit/pages/27_backtest_court.html"
h = io.open(P, encoding="utf-8").read()
orig = h

anchor = """  <div class="note">
    <span class="tag">The honest read</span>
    <p>The correctness fixes made the measurement trustworthy; <b>they did not create an
    edge</b>. Plan around <b>+1%, not +5%</b>. And note the standing recommendation:
    30 positional trades logged through guided execution would tell us more than another
    backtest, because live execution is the one thing this harness structurally cannot
    measure.</p>
  </div>"""

replacement = """  <div class="note">
    <span class="tag">The honest read</span>
    <p>The correctness fixes made the measurement trustworthy; <b>they did not create an
    edge</b>. Plan around <b>+1%, not +5%</b>. And note the standing recommendation:
    30 positional trades logged through guided execution would tell us more than another
    backtest, because live execution is the one thing this harness structurally cannot
    measure.</p>
  </div>

  <h3>Two re-baselines since — and the second one changes how to read the first</h3>
  <div class="tw"><table>
    <thead><tr><th>Run</th><th>What changed in the code</th><th>Mean matched α</th><th>P(α&gt;0)</th></tr></thead>
    <tbody>
      <tr><td>26 Jul</td><td>The matched-horizon fix</td><td class="num">+0.80%</td><td class="num">81.9%</td></tr>
      <tr><td>29 Jul</td><td>Strict-trend port corrected (stage gate)</td><td class="num">+0.54%</td><td class="num">40.3%</td></tr>
      <tr><td>19 Aug</td><td>RRG unified · forming-week dropped</td><td class="num">+0.30%</td><td class="num">46.1%</td></tr>
    </tbody>
  </table></div>
  <div class="note warn">
    <span class="tag">The 29 July result is the one to absorb</span>
    <p><b>456 of 464 picks were byte-identical</b> before and after the stage fix — 2.4% of the
    book moved. Yet the headline fell from +0.80% to +0.54% and the cumulative alpha went
    <b>+15.08% → −3.55%</b>, because <b>one anchor</b> held one trade at <b>+79.35%</b> that the
    corrected stage gate now blocks. Remove that single trade and the aggregate flips.</p>
    <p>So do not read it as "the fix broke the edge". Read it as: <b>the edge was never
    statistically distinguishable from zero, and the point estimate was being held up by one
    outlier in a five-pick anchor.</b> Both runs' confidence intervals straddle zero — the earlier
    one did too. <b>Judge the FIX on parity and the STRATEGY on the new number; they are separate
    questions.</b></p>
  </div>
  <div class="note">
    <span class="tag">26 Aug — the location rule, pre-registered and null</span>
    <p>Any-zone, rule A2 and pattern-only compared over eighteen anchors on identical candidates:
    <b>−0.44%</b>, <b>−0.54%</b>, <b>−0.65%</b> mean matched alpha — a spread of <b>0.21
    percentage points</b> across arms that share most of their trades, which the pre-registration
    had already defined as a null. Filled trades fell <b>221 → 88 → 51</b>.</p>
    <p><b>Tightening location buys fewer trades, not better ones.</b> The first run of this test
    was mis-specified — the S/R and AVWAP fallbacks ran for every arm, so "pattern-only" still
    admitted names with no zone at all — and it returned the answer the hypothesis wanted. That
    version was discarded before anything was read from it, which is the only reason the null
    stands.</p>
  </div>"""

assert h.count(anchor) == 1, "section 08 anchor not unique"
h = h.replace(anchor, replacement)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 27: {len(orig)} -> {len(h)} chars")
