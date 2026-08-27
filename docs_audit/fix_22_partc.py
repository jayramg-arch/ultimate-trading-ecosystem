"""Doc 22 (Section Four) — add PART C, the field-by-field panel reference.

Jay: a trader reading the S4 panel should not need to open anything else. The markdown
guide got PART C (1,248 lines, all 41 rows); this puts the same reference on the page,
in the page's own design system — no new classes, no new colours.

It is added as a separate GROUP in the TOC ("The field reference") rather than folded
into the existing sections, because the existing §03-§08 are the *narrative* read and
this is the *lookup*. The two answer different questions and a reader arriving to check
one cell should not have to read an argument first.

Every value verified at source in Section4_Entry_Trigger_v7.2.pine / S4Core.pine.
"""
import io

P = "docs_audit/pages/22_section_four.html"
h = io.open(P, encoding="utf-8").read()
orig = h

# ── 1. TOC group ─────────────────────────────────────────────────────────────
toc_anchor = '''  <p>Operating it</p>'''
assert h.count(toc_anchor) == 1, "TOC anchor not unique"

toc_new = '''  <p>The field reference</p>
  <ol>
    <li><a href="#lang">The four languages</a></li>
    <li><a href="#rowsI">Band I — every row</a></li>
    <li><a href="#rowsII">Band II — every row</a></li>
    <li><a href="#rowsIII">Band III — every row</a></li>
    <li><a href="#rowsIV">Bands IV–VI — every row</a></li>
    <li><a href="#states">Panels you will see</a></li>
    <li><a href="#misread">Misreadings</a></li>
  </ol>
''' + toc_anchor
h = h.replace(toc_anchor, toc_new)

# ── 2. the sections themselves, before </main> ───────────────────────────────
tail = '''
</main>'''
assert h.count(tail) == 1, "main close not unique"

body = r'''
<section id="lang">
  <h2><span class="n">14</span>The four languages</h2>
  <p>The panel says everything four ways at once. Learn these and most rows explain
  themselves. <b>This block and the four that follow are a reference</b> — the sections above
  are the argument, this is the lookup.</p>

  <div class="tw"><table>
    <thead><tr><th>Glyph</th><th>Means</th><th>Never means</th></tr></thead>
    <tbody>
      <tr><td class="k">🟢</td><td>This leg <b>passed</b></td><td>“good trade”</td></tr>
      <tr><td class="k">⚪</td><td>This leg <b>did not pass</b>, and that is normal</td><td>broken, or an error</td></tr>
      <tr><td class="k">🔴</td><td>Passed a threshold <em>in the wrong direction</em> — an active warning</td><td>mere absence</td></tr>
      <tr><td class="k">⛔</td><td>A <b>hard block</b>. Price is somewhere you should not buy</td><td>“weak”</td></tr>
      <tr><td class="k">⚠️</td><td>A <b>caveat</b>: tradeable, but something is against you</td><td>a block</td></tr>
      <tr><td class="k">★</td><td><b>Controlling</b> — the strongest instance of its kind</td><td>a favourite</td></tr>
      <tr><td class="k">⚡</td><td><b>FVG-backed</b> — a fair-value gap supports this zone</td><td>“fast”</td></tr>
      <tr><td class="k">⏱</td><td>Optional <b>timing</b> confirmation fired</td><td>a required gate</td></tr>
      <tr><td class="k">—</td><td><b>Not measured.</b> No data, or not applicable</td><td>zero, or failed</td></tr>
      <tr><td class="k">~</td><td><b>Inferred</b>, not drawn — a shape read off pivots</td><td>a chart object you can see</td></tr>
    </tbody>
  </table></div>

  <div class="note no">
    <span class="tag">The distinction that costs the most money</span>
    <p><b>An em-dash is not a white dot.</b> <code>⚪</code> means the engine looked and the
    answer was no. <code>—</code> means the engine <em>could not look</em>. A beginner reads
    both as “bad”, throws away good setups on missing data — or worse, treats an unmeasured
    leg as a passed one.</p>
  </div>

  <div class="tw"><table>
    <thead><tr><th>Colour</th><th>Reading</th></tr></thead>
    <tbody>
      <tr><td class="k">Green</td><td>Good, and acted on</td></tr>
      <tr><td class="k">Teal</td><td>Present but partial</td></tr>
      <tr><td class="k">Amber</td><td><b>Waiting</b> or <b>caution</b> — armed, not wrong</td></tr>
      <tr><td class="k">Red</td><td>Actively against the trade</td></tr>
      <tr><td class="k">Grey</td><td>Off, unbound, or not applicable</td></tr>
    </tbody>
  </table></div>
  <p>Colour grades the <em>level</em>; the dot carries pass/fail. <b>Amber is the colour you
  will see most and it is not a failure state</b> — a panel that is amber everywhere is a panel
  doing its job, watching something that has not triggered.</p>

  <p><b>Separators.</b> A pipe <code>│</code> divides <em>fields</em> — different facts. A
  middle dot <code>·</code> divides <em>values inside one field</em>. When you are scanning
  fast, pipes are where you are allowed to stop reading.</p>

  <div class="note">
    <span class="tag">Which bar you are looking at</span>
    <p>With <b>closed-candle on (the default)</b> every row reads the <b>last CLOSED bar</b>. A
    pattern that appears mid-bar will not show until it survives the close, and the distances in
    the S/R and AVWAP rows are measured from that <em>closed</em> bar — so a row can read
    <code>−2.0%</code> while live price is 3% away. That is correct: the gate was evaluated at
    the closed bar and the row must agree with the gate it reports.</p>
    <p><b>The panel is a photograph of the last completed bar, and every number on it is
    internally consistent with that moment.</b></p>
  </div>
</section>

<section id="rowsI">
  <h2><span class="n">15</span>Band I — Macro &amp; context, every row</h2>
  <p>Whether the name deserves your attention today. Almost entirely <b>weekly</b> information,
  because the framework underneath is Weinstein stage analysis and a stage is a weekly fact.
  Row 0 is the header — <code>S4 v10.0 │ core/24</code>. Check it after every recompile; a
  mismatch means the library did not publish.</p>

  <h3>Row 2 · Structure basis</h3>
  <p class="m">Stage 2 (14w leg/38w macro) │ &gt;30WMA ↑ &gt;50 ↑ &gt;200 uptrend │ RFF 5 🟢 │ BFF 4 🟢</p>
  <div class="tw"><table>
    <thead><tr><th>Field</th><th>Values</th><th>Meaning</th></tr></thead>
    <tbody>
      <tr><td class="k">Stage N</td><td class="m">1 · 2 · 3 · 4</td><td>The Weinstein stage</td></tr>
      <tr><td class="k">(Xw / Yw)</td><td class="m">integers</td><td>Weeks the current leg has run, and the macro trend age</td></tr>
      <tr><td class="k">30WMA / 50 / 200</td><td class="m">&gt; or &lt; plus ↑ ↓ →</td><td>Price above/below each average, and that average’s slope</td></tr>
      <tr><td class="k">trend word</td><td class="m">uptrend · downtrend · sideways</td><td>The composite read of the three</td></tr>
      <tr><td class="k">RFF n</td><td class="m">0–6 or —</td><td>Recovery fundamentals. 🟢 at ≥4. The <b>hard gate</b> for recovery trades</td></tr>
      <tr><td class="k">BFF n</td><td class="m">0–6 or —</td><td>Bull fundamentals. <b>Display-only</b>; never blocks</td></tr>
      <tr><td class="k">ETF variant</td><td class="m">ETF ₹12.4Cr │ NAV +0.3% 🟢</td><td>On an ETF, liquidity and premium replace RFF/BFF</td></tr>
    </tbody>
  </table></div>

  <p><b>The four stages.</b> Derived from exactly two facts: where price sits against its
  <b>30-week average</b>, and whether that average is rising or falling. Nothing else.</p>
  <div class="tw"><table>
    <thead><tr><th></th><th>30WMA rising</th><th>30WMA falling</th></tr></thead>
    <tbody>
      <tr><td class="k">Price above</td><td><b>Stage 2</b> — advancing. <em>The only stage you buy</em></td><td><b>Stage 3</b> — topping</td></tr>
      <tr><td class="k">Price below</td><td><b>Stage 1</b> — basing</td><td><b>Stage 4</b> — declining</td></tr>
    </tbody>
  </table></div>
  <p><b>Stage 3 is the dangerous one</b>: price is still above the average, and the average has
  already rolled over. The chart still <em>looks</em> strong while the structure has broken
  underneath — which is where most late entries happen. Thirty weeks is roughly seven months of
  business, long enough that noise cannot flip it; the <em>slope</em> is the part beginners drop,
  and dropping it is exactly what turns a Stage 3 into a Stage 1 in your head.</p>
  <p><b>Stage 3 or 4 and the engine refuses outright</b> — the verdict reads <code>NO TRADE —
  Stage 3</code> however perfect everything below looks. That is not conservatism: a plan
  reasoned inside the wrong frame is worse than no plan, because it is a plan.</p>

  <h3>Row 3 · Minervini template N/8</h3>
  <p>Every leg prints its own dot, passes and failures both — a list of only the failures answers
  “which of the eight does this have?” by subtraction, which is not a checklist you can read.</p>
  <div class="tw"><table>
    <thead><tr><th>Leg</th><th>Passes when</th><th>Why it is in the list</th></tr></thead>
    <tbody>
      <tr><td class="k">&gt;150/200</td><td>Above both the 150- and 200-day</td><td>The basic definition of “in an uptrend”</td></tr>
      <tr><td class="k">150&gt;200</td><td>The 150 sits above the 200</td><td>The uptrend is <em>ordered</em>, not a spike</td></tr>
      <tr><td class="k">200 rising</td><td>The 200-day has been rising</td><td>A flat 200 is a range, not a trend</td></tr>
      <tr><td class="k">50-stack</td><td>The 50 above both 150 and 200</td><td>Short-term strength leads; the stack is intact</td></tr>
      <tr><td class="k">&gt;50</td><td>Price above the 50-day</td><td>Price is leading its own averages</td></tr>
      <tr><td class="k">+30% off low</td><td>≥30% above the 52-week low</td><td>The base is behind it, not ahead</td></tr>
      <tr><td class="k">within 25% of high</td><td>Within 25% of the 52-week high</td><td>Leaders trade near highs; laggards do not</td></tr>
      <tr><td class="k">RS &gt; index</td><td>Relative strength beats the benchmark</td><td>Outperformance, not just participation</td></tr>
    </tbody>
  </table></div>
  <p>A <code>~</code> after the count means the RS leg is unbound and the score is out of 7.
  <b>6/8 or 7/8 is normal and often better for entries</b> — the leg that most often fails is
  <em>within 25% of high</em>, and a name 30% off its high passing everything else is a base,
  not a broken stock. Below 6/8, ask <em>which</em>: <code>200 rising</code> failing is
  structurally serious; <code>+30% off low</code> failing on a Stage-1 recovery is expected.</p>

  <h3>Row 4 · WCL context · structure</h3>
  <div class="tw"><table>
    <thead><tr><th>Half</th><th>Values</th><th>Meaning</th></tr></thead>
    <tbody>
      <tr><td class="k">Context</td><td class="m">BULLISH · NEUTRAL · BEARISH (+n)</td><td>Composite Wyckoff/structure score; 🟢 at ≥4</td></tr>
      <tr><td class="k">Setup</td><td class="m">S1–S8 plus a name</td><td>Which context setup is active</td></tr>
      <tr><td class="k">Structure Health</td><td class="m">CLEAN · CHOPPY · BROKEN (n)</td><td>Character changes in the last 20 bars</td></tr>
    </tbody>
  </table></div>
  <div class="note no">
    <span class="tag">Structure Health is effectively two-valued</span>
    <p>Banded 0–1 CLEAN, 2–3 CHOPPY, 4+ BROKEN — but <b>measured across the board universe the
    count has never reached three</b>. So CHOPPY means <em>exactly two</em> and BROKEN cannot
    occur. Read <b>CLEAN as the ordinary state</b>, not a clean bill of health, and treat CHOPPY
    as the real warning — it is the top of the scale, not the middle.</p>
    <p>Wyckoff was tested twice as a trading input here — as a veto and as a score — and
    <b>rejected both times</b>. Roughly half of qualified breakout candidates read DISTRIBUTION
    at signal time, because Wyckoff events fire at high-volume pivot highs, which is structurally
    what a breakout looks like. This row <em>describes</em>; it does not decide.</p>
  </div>

  <h3>Row 5 · RS (vs N500 / <em>Sector</em>)</h3>
  <p>The row title names the sector the second half is measured against.</p>
  <div class="tw"><table>
    <thead><tr><th>Level</th><th>Direction</th><th>Colour</th><th>Reading</th></tr></thead>
    <tbody>
      <tr><td class="k">Positive</td><td>Rising</td><td>Green</td><td>Outperforming <b>and pulling away</b> — the best state</td></tr>
      <tr><td class="k">Positive</td><td>Declining</td><td>Amber</td><td>Still ahead but <b>giving it back</b> — leadership fading</td></tr>
      <tr><td class="k">Negative</td><td>Rising</td><td>Teal</td><td>Behind but <b>closing</b> — the improving case</td></tr>
      <tr><td class="k">Negative</td><td>Declining</td><td>Red</td><td>Behind and losing more</td></tr>
    </tbody>
  </table></div>
  <p>Absolute price says what a stock did; relative strength says whether it did better than the
  alternatives. In a falling market a stock that drops less is a leader, and only RS sees that.
  Benchmarked against the Nifty 500 <em>and</em> the sector, because a name can lead the market
  while lagging its own group — which usually means the <em>group</em> is carrying it.</p>

  <h3>Row 6 · RRG (vs N500)</h3>
  <p class="m">LEADING ↗ +12 │ strengthening │ 🟢 BUY OK (RS-Ratio 104.2)</p>
  <p>Plot relative strength against relative momentum and you get four quadrants, cycling
  clockwise: <b>IMPROVING → LEADING → WEAKENING → LAGGING</b>. LEADING is strong and still
  gaining; WEAKENING is strong but losing momentum, often the top of a move; IMPROVING is the
  recovery quadrant. RS-Ratio of 100 means matching the index.</p>
  <div class="note no">
    <span class="tag">Why BUY OK never vetoes</span>
    <p>Measured on 473 symbols across 93,745 weekly observations. Only <code>LEADING→LEADING</code>
    and <code>WEAKENING→LEADING</code> survived; the intuitive <code>IMPROVING→LEADING</code>
    transition is <b>reliably negative</b> and cancels what the others earn. Net value:
    <b>+0.12pp at four weeks, +0.00pp at twelve.</b> The flag shows on the chip and grades — it
    is not a gate. Do not decline a trade on it alone.</p>
  </div>
  <p><b>Row 5 and Row 6 are deliberately separate.</b> RS is the <em>level</em>, RRG is the
  <em>direction of rotation</em>; they fail independently and are acted on differently —
  <b>RS ranks a name, the quadrant times it.</b></p>

  <h3>Row 7 · Sector · Futures OI</h3>
  <p>Open interest is the number of contracts outstanding. It only means anything read
  <em>against price direction</em>:</p>
  <div class="tw"><table>
    <thead><tr><th>Price</th><th>OI</th><th>State</th><th>What it means</th></tr></thead>
    <tbody>
      <tr><td class="k">Up</td><td>Up</td><td><b>Long build-up</b></td><td>New money buying. A breakout here has fuel</td></tr>
      <tr><td class="k">Up</td><td>Down</td><td><b>Short covering</b></td><td>The rally is shorts <em>exiting</em>, not new buying. <b>Fades are common — do not chase</b></td></tr>
      <tr><td class="k">Down</td><td>Up</td><td><b>Short build-up</b></td><td>Fresh shorts pressing. Expect supply into strength</td></tr>
      <tr><td class="k">Down</td><td>Down</td><td><b>Long unwinding</b></td><td>Holders leaving without new sellers. Weak, not a short signal</td></tr>
      <tr><td class="k">—</td><td>—</td><td class="m">no F&amp;O</td><td>Cash-only stock. No positioning read</td></tr>
    </tbody>
  </table></div>
  <p>Price alone cannot separate new conviction from position-closing: two identical green
  candles mean opposite things depending on whether positions opened or closed to produce them.
  <b>Short covering is the trap this row exists to catch</b> — it looks exactly like a breakout
  and has no one left to buy. <em>Sector Stage</em> is the same 2×2 applied to the sector index;
  a Stage-2 stock in a Stage-4 sector is swimming against its own group.</p>

  <h3>Rows 8 &amp; 9 · Signal · Quality · RSI, and ML win probability</h3>
  <p>Row 8 carries three values bound from the v67 dashboard: its action signal, its asset-quality
  read, and daily RSI(14). <b>RSI in one line:</b> it compares average gains to average losses
  over 14 days and returns 0–100 — but <b>in a Stage-2 trend RSI stays high for months</b>, and
  selling at 70 is how you exit every winner early. Its useful reading is <em>divergence</em>:
  price making a new high while RSI does not.</p>
  <p>Row 9 prints the model’s win probability and the board rank —
  <span class="m">41.3% │ GM rank 72.4 🟢</span>.</p>
  <div class="note">
    <span class="tag">Why 40% is a good number</span>
    <p>This is a trend-following system: it wins less than half the time and makes money on the
    size of the winners. Measured, about <b>88% of positional exits come via the trail</b>, and
    the median trade <em>loses</em> to the index. A 40% win probability attached to a 3:1 payoff
    is a good trade. Green starts at 40%, amber at 35% — <b>do not read it like a school
    mark</b>. GM rank is never red: a low rank is a ranking, not a fault.</p>
    <p><code>— unbound</code> is the most common panel fault. <code>input.source</code> binds by
    <em>position</em> and <b>TradingView drops every binding on every recompile</b>. Re-run the
    bind script. Nothing is broken.</p>
  </div>
</section>

<section id="rowsII">
  <h2><span class="n">16</span>Band II — Location, value &amp; room, every row</h2>
  <div class="note go">
    <span class="tag">The idea the whole band rests on</span>
    <p>A <b>zone</b> is a price area where a large order once left unfilled demand behind. Price
    leaving it violently is the evidence; price <em>returning</em> is the opportunity. The trade
    is not “price is in a zone” — it is <b>price returned, tested the zone, and turned</b>. That
    turn is the setup.</p>
  </div>

  <h3>Row 11 · Zones (MTF)</h3>
  <div class="tw"><table>
    <thead><tr><th>Value</th><th>Meaning</th></tr></thead>
    <tbody>
      <tr><td class="k m">IN DEMAND</td><td>Price is inside a demand zone right now</td></tr>
      <tr><td class="k m">REACTING off DZ</td><td>Tested a demand zone and turned up off it — <b>the tradeable state</b></td></tr>
      <tr><td class="k m">IN SUPPLY</td><td>Inside a supply zone. Overhead sellers</td></tr>
      <tr><td class="k m">between zones</td><td>Open space. Neither support nor resistance nearby</td></tr>
      <tr><td class="k m">★ctrl · ⚡ · ×2TF</td><td>Controlling zone · FVG-backed · nested across 2 timeframes</td></tr>
      <tr><td class="k m">n DZ / n SZ live</td><td>Live demand and supply counts on the chart</td></tr>
    </tbody>
  </table></div>
  <p><b>The lifecycle</b> — <code>fresh → reacted → spent</code>, with <code>violated</code> as a
  separate ending.</p>
  <div class="tw"><table>
    <thead><tr><th>State</th><th>Meaning</th></tr></thead>
    <tbody>
      <tr><td class="k">Fresh</td><td>Never tested. It has proven nothing yet</td></tr>
      <tr><td class="k">Reacted</td><td>Price came back, tested it, turned. <b>This is the trade</b></td></tr>
      <tr><td class="k">Spent</td><td>Retired — but only after a <b>confirmation</b>: travel of twice the zone’s own-TF ATR, <em>or</em> an EMA20 cross, <em>or</em> a break of the HTF pivot that framed it. Until one happens it is still live and still tradeable</td></tr>
      <tr><td class="k">Violated</td><td>Price <em>closed</em> beyond the far edge. Deleted, not spent</td></tr>
    </tbody>
  </table></div>
  <p>Two asymmetries are deliberate: <b>demand outlives supply</b> — spent demand stays greyed,
  and a controlling or high-scoring zone earns a <em>second</em> test — and the EMA20 that judges
  a zone is the one that frames it: <b>weekly and monthly zones answer to the chart’s EMA20;
  daily and intraday zones answer to the daily EMA20.</b></p>

  <h3>Row 12 · Support Zone</h3>
  <p class="m">DZ ⚡ │ D:FVG W:Piv AVWAP EMA20 VAL ~Fib0.618</p>
  <div class="tw"><table>
    <thead><tr><th>Type</th><th>In plain terms</th></tr></thead>
    <tbody>
      <tr><td class="k">FVG</td><td>A three-bar gap price moved through so fast nobody traded inside it. Those tend to get revisited</td></tr>
      <tr><td class="k">Piv</td><td>A swing low price has previously turned at. Price memory</td></tr>
      <tr><td class="k">AVWAP</td><td>An anchored volume-weighted average price (Row 22)</td></tr>
      <tr><td class="k">EMA20</td><td>The 20-period exponential average — dynamic support in a trend</td></tr>
      <tr><td class="k">VAL / POC</td><td>Value-area low and point of control from the volume profile</td></tr>
      <tr><td class="k">~Fib</td><td>A Fibonacci retracement. The <code>~</code> means inferred, not drawn</td></tr>
    </tbody>
  </table></div>
  <p>One support is a level. <b>Three or more stacked in a tight band is confluence</b>, and
  confluence is what makes a stop meaningful — you are not betting on one line holding, you are
  betting on several failing at once.</p>

  <h3>Row 13 · S/R (nearest)</h3>
  <p class="m">S 1718.00 (−2.1%) | R 1802.50 (+2.7%) │ COILING under 1802.50 → breakout watch</p>
  <p><b>The timeframe tag is not decoration.</b> A stop resting on a <b>weekly</b> level is a
  deeper distal — a wider stop — which means <b>size down</b>. The same number off a
  <b>daily</b> shelf is a tighter stop and a bigger position. Reading <code>1718.00 −2.1%</code>
  without knowing which is how a position gets mis-sized. <code>man</code> = your own drawn
  level, which outranks the automatic pair.</p>
  <p>A far distance is honest, not a bug: on a strong trender there may be no qualified two-touch
  level nearby. The row <b>greys past 8%</b> — real, but not a stop you would use.</p>
  <div class="tw"><table>
    <thead><tr><th></th><th>A level</th><th>A demand zone</th></tr></thead>
    <tbody>
      <tr><td class="k">Models</td><td>Price <b>memory</b></td><td>Unfilled <b>orders</b></td></tr>
      <tr><td class="k">A touch</td><td><b>Weakens</b> it — heavily tested means primed to break</td><td><b>Spends</b> it — the fuel is consumed</td></tr>
      <tr><td class="k">A close beyond</td><td><b>Flips</b> it. Broken support becomes resistance and stays</td><td><b>Deletes</b> it</td></tr>
    </tbody>
  </table></div>
  <p>This is why a level tested four times and a zone tested once say opposite things about their
  own reliability — and why the picker deliberately <b>discards</b> the most over-tested levels
  and reports them separately as <code>COILING</code>. A level price keeps grinding on is a
  breakout candidate, not a floor.</p>

  <h3>Rows 14–16 · Trendlines, Volume Profile, Momentum &amp; value</h3>
  <p><b>Row 14</b> reads <code>off</code>, the sensed prices, or <code>not sensed</code> — the
  last meaning the toggle is on but the source is unwired. Wiring a trendline is three manual
  steps with no other feedback, which is the entire reason the row exists.</p>
  <p><b>Row 15</b> answers “where did the money actually change hands?”. The <b>POC</b> is the
  fairest price in the window; the <b>value area</b> holds ~70% of volume.
  <code>✓ ABOVE VAH</code> (strongest) → <code>✓ IN VA (upper)</code> →
  <code>✗ IN VA (lower)</code> → <code>✗ BELOW VAL</code>. This is the one component of the
  Wyckoff/SMC block that earned its place, firing on roughly 18% of names.</p>
  <p><b>Row 16</b> — <span class="m">ADX 27.4 +DI (31/18) │ ATR 2.4% │ above CPR │ above MVWAP │ VCP ✓</span></p>
  <div class="tw"><table>
    <thead><tr><th>Reading</th><th>Meaning</th></tr></thead>
    <tbody>
      <tr><td class="k">ADX &lt; 20</td><td>No trend. Price is ranging</td></tr>
      <tr><td class="k">ADX 20–25</td><td>A trend forming</td></tr>
      <tr><td class="k">ADX &gt; 25</td><td>A real trend — the row goes green here, <em>and</em> only when +DI leads</td></tr>
      <tr><td class="k">ADX &gt; 40</td><td>Strong, possibly extended</td></tr>
    </tbody>
  </table></div>
  <p><b>ADX says nothing about direction</b> — that is +DI versus −DI. <code>ADX 30 −DI</code> is
  a strong <em>downtrend</em>. <b>ATR as a percent</b> makes volatility comparable across stocks
  and drives everything downstream: the stop is a multiple of ATR, and position size is risk
  divided by that stop, so a 6% ATR name gets a much smaller position than a 1.5% one for the
  same rupee risk. <b>VCP</b> is successive pullbacks getting shallower on falling volume —
  sellers exhausting.</p>

  <h3>Row 17 · Extension vs EMA20</h3>
  <p class="m">EXTENDED 2.8×ATR above ⚡para late-stage 50D +3.1× base 5 ⚠ │ above EMA20 by 4.2%</p>
  <p>Bands run <code>AT VALUE</code> → <code>NORMAL</code> → <code>EXTENDED</code> →
  <code>FAR</code>. Tags: <code>⚡para</code> parabolic arrival · <code>climax-vol</code> extended
  <em>and</em> volume ≥3× · <code>late-stage</code> the leg has run ≥40 weeks ·
  <code>base n ⚠</code> how many consolidations this advance has already built.</p>
  <p><b>Why extension matters more than almost anything here.</b> Your stop is placed by
  structure, so the further price sits from that structure the wider the stop and the worse the
  reward-to-risk — before considering that extended price mean-reverts. Bases one and two are the
  highest-quality buy points; by base four or five the move is widely recognised and failure
  rates climb.</p>
  <div class="note no">
    <span class="tag">Warns at 2.5×ATR, over-extended at 4.0 — and neither is a gate</span>
    <p>Extension <b>never blocks a GO</b>, deliberately, under the anti-Holy-Grail rule: pile
    every quality test into the trigger and you get a signal that never fires. It feeds the
    <b>verdict</b>, where a GO while extended is downgraded to <code>CAUTION —
    momentum/chase</code>. <b>So you will sometimes see a green TRIGGER row above an amber
    verdict — and the verdict is the one judging the trade.</b></p>
  </div>

  <h3>Row 18 · Location (L) — a required gate</h3>
  <p class="m">REACTING off pattern — 🟢Zone ⚪D/W-lvl 🟢AVWAP ⚪EMA20 🟢S/R</p>
  <div class="tw"><table>
    <thead><tr><th>Headline</th><th>Meaning</th></tr></thead>
    <tbody>
      <tr><td class="k m">NOT AT LOCATION</td><td>Nothing supports price here. <b>The L gate fails</b></td></tr>
      <tr><td class="k m">AT pattern zone</td><td>Inside a leg-base-leg pattern zone</td></tr>
      <tr><td class="k m">AT pivot zone</td><td>Inside a pivot shelf — weaker evidence</td></tr>
      <tr><td class="k m">REACTING off pattern</td><td>Tested a pattern zone and turned. <b>The strongest read</b></td></tr>
      <tr><td class="k m">REACTING off pivot</td><td>Tested a pivot shelf and turned</td></tr>
      <tr><td class="k m">AT LOCATION</td><td>Supported, but by one of the other sources</td></tr>
    </tbody>
  </table></div>
  <p>The five dots name <em>which</em> sources support price. Any one satisfies the gate.
  “AT LOCATION” alone was not enough because it read identically for a zone price sits inside, a
  zone price is reacting off, and a bare pivot shelf — <b>three different trades</b>. Pattern
  outranks pivot when both fire.</p>
  <p><b>Weak location:</b> if the only support is AVWAP or EMA20 — no zone, no S/R — the verdict
  downgrades to <code>CAUTION — momentum/chase</code>. Those two are dynamic curves that follow
  price, so they are nearly always “nearby” and cannot on their own mean you are at value.</p>

  <h3>Row 19 · Room for Trade</h3>
  <div class="tw"><table>
    <thead><tr><th>Value</th><th>Meaning</th></tr></thead>
    <tbody>
      <tr><td class="k m">CLEAR n%</td><td>Clear space to the first obstacle. Green if R:R ≥ 2</td></tr>
      <tr><td class="k m">⚠️ NO ROOM n%</td><td>The first obstacle sits <b>below your T1</b></td></tr>
      <tr><td class="k m">⛔ IN SUPPLY</td><td>Price is inside a supply zone. <b>Hard block</b></td></tr>
      <tr><td class="k m">spent SZ &lt;price&gt;</td><td>A <b>retired</b> supply zone sits nearer than the live obstacle</td></tr>
    </tbody>
  </table></div>
  <p>Reward is not “wherever T1 lands” — it is the distance to the first thing that will stop
  you, measured across six sources. Pivot ceilings are labelled <code>Pv·</code> and ranked last,
  a pivot shelf being weaker than a supply zone. The <code>spent SZ</code> caveat is
  <b>deliberately never folded into the number</b>: house doctrine says a tested zone is
  consumed, so it must not silently shrink your R.</p>
</section>

<section id="rowsIII">
  <h2><span class="n">17</span>Band III — Execution &amp; timing, every row</h2>
  <p>Band II said <em>where</em>. This band says <em>now</em>.</p>

  <h3>Row 21 · Intraday</h3>
  <p><code>off</code> → <code>wait</code> → <code>sqz ON, wait EMA</code> →
  <code>10EMA ok</code> → <code>GO 10EMA</code> / <code>GO 10EMA+sqz</code>. A <b>squeeze</b> is
  a volatility contraction — Bollinger Bands inside Keltner Channels — meaning the market has
  coiled; coils resolve with expansion and the direction of the reclaim is the tell. This is
  <b>optional timing</b> (<code>⏱</code>), never a required gate.</p>

  <h3>Row 22 · AVWAP</h3>
  <p class="m">🟢TRIGGER R2G&gt;BO │ nearest 1724.50 (−1.2%) │ L·BO·Gap … │ 🟢pinch 0.8%</p>
  <p>A normal VWAP resets daily. An <b>anchored</b> one starts at a chosen event and runs
  forward, giving the true average price paid by everyone who bought since. Above it, those
  buyers are collectively in profit — and they tend to defend it.</p>
  <div class="tw"><table>
    <thead><tr><th>Anchor</th><th>Why this one</th></tr></thead>
    <tbody>
      <tr><td class="k">52-week Low</td><td>Where the last cycle of sellers gave up</td></tr>
      <tr><td class="k">Breakout day</td><td>Where the current advance began — the average price of the buyers who started the trend</td></tr>
      <tr><td class="k">Gap-up day</td><td>Where a repricing happened</td></tr>
    </tbody>
  </table></div>
  <p><b>R2G</b> (“reclaim to green”) means price fell below the breakout AVWAP and reclaimed it —
  the failed-breakdown reversal, and the stronger of the two triggers. A <b>pinch</b> — all three
  anchors converging — is high conviction: three separate cohorts share one average price, so a
  break flushes all three at once. Note this is a <em>dynamic curve</em>, not a drawn line; the
  static horizontals are Row 13, a different engine.</p>

  <h3>Rows 23–25 · Pattern | Shape, the battery, and combos</h3>
  <p>Row 23 separates a <b>drawn</b> pattern from an <b>inferred</b> <code>~shape</code> read off
  the last four pivots. The <code>~</code> exists to stop the geometry read being mistaken for
  something on the chart — and the two-pivot classifier is known to be coarse, having called
  obvious rectangles “symmetrical triangles”. Treat it as a hint.</p>
  <p>Row 24 is the <b>P gate</b>: every pattern in the active battery, ranked by contribution.
  The bull battery carries 17 (HTF weight 4; VCP, LAU, GAP, SPR at 3; SC, BC, PP, U50, LIQ, ENG,
  3BR, H50, H200, IN3, IBN at 2; NR7 at 1) and the recovery battery 10 (CLIMAX, SPR, 2B, SOS,
  30WMA at 3; ENG, HSUP, 3BR, PP at 2; VDU at 1). <b>Which battery runs is decided by the stage
  2×2</b> — Stage 2 resolves Bull, Stage 1 Recovery, Stage 3/4 no trade at all.</p>
  <div class="note">
    <span class="tag">Σ grades; it does not gate</span>
    <p>A single weight-4 pattern is not the same as four weight-1 patterns, so Σ is a
    <b>quality</b> measure rather than a count. <b>The gate is simply: did at least one pattern
    fire?</b></p>
  </div>
  <p>Row 25 names multi-pattern <b>stories</b> with the age of the context leg — the part Σ
  cannot show, and the part that says whether the story is still fresh:
  <code>COILED SPRING</code> · <code>INSTITUTIONAL IGNITION</code> · <code>BEAR TRAP</code> ·
  <code>CAPITULATION FLOOR</code> · <code>STRUCTURE SHIFT</code>. A combo is the strongest single
  line on the panel when it fires, because it is a <em>sequence</em> rather than a
  coincidence.</p>

  <h3>Row 26 · Bar (B) — a required gate</h3>
  <p>Passes when the bar closed <b>green</b> OR closed in the <b>upper half of its range</b>.
  Both the colour and the close position are always stated.</p>
  <div class="tw"><table>
    <thead><tr><th>Reason</th><th>Meaning</th></tr></thead>
    <tbody>
      <tr><td class="k m">— green close</td><td>Closed above its open</td></tr>
      <tr><td class="k m">— shakeout: red body but closed strong</td><td>Red bar, upper-half close. The lows were rejected — fine for a long</td></tr>
      <tr><td class="k m">— red and closed in the lower half</td><td>Sold into the close. <b>Vetoed</b></td></tr>
    </tbody>
  </table></div>
  <p>A pattern can fire on a bar that made a new high then collapsed into the close — that is
  distribution wearing a breakout’s clothes. <b>Where a bar closes within its range is who won
  the day.</b> The asymmetry is deliberate: a red bar with a long <em>lower</em> wick is a
  shakeout, and calling it bearish would be the mirror of the mistake this row already avoids in
  the other direction.</p>

  <h3>Rows 27–29 · Arrival · Δ, Volume, Confluence</h3>
  <p><b>Row 27.</b> <code>FAST</code> price arriving into demand tends to produce a sharp
  rejection — sellers overshot. <code>GRIND</code> is absorbing the zone and tends to bleed
  through. <b>Same level, opposite outcomes</b>, and only the approach tells you which. The delta
  is a <em>proxy</em> — no TradingView plan exposes real aggressor data to Pine — so it grades
  and never gates.</p>
  <p><b>Row 28 is the V gate.</b> RV is this bar’s volume over a baseline: ≥1.25 <code>strong</code>,
  ≥1.00 <code>ok</code>, below <code>thin</code>. A breakout on thin volume means nobody showed
  up, and those fail back into the range at a high rate.</p>
  <div class="note no">
    <span class="tag">Two measured facts about RV</span>
    <p><b>It is time-of-day biased.</b> Across 14,466 bar-observations the V gate passes
    <b>48% at 10:30 and about 18% midday</b> — a 2.8× swing from the clock alone, because the
    baseline mixes every bar of the day. A midday RV of 0.9 is not the same evidence as a 10:30
    RV of 0.9.</p>
    <p><b>Pullback entries legitimately have lower volume.</b> At-value bars print a median RV of
    <b>0.63</b> against <b>1.35</b> on breakout bars, and a 1.0 floor rejects 78% of them. That is
    why the pullback branch exists: a contraction pattern inside a demand zone with no expansion
    pattern drops the floor to 0.5 and changes the bar test to “held the zone”. Those rows are
    tagged <code>·PB</code>.</p>
  </div>
  <p><b>Row 29</b> ranks nineteen supporting factors — AVWAP, Intra, ⚡FVG, Ctrl, S/R, TL, Flag,
  EMA20, @AVWAP, Fib, Pinch, RV+, Rnd, D-PA, Arrival, Δ+, WCL, RRG, MTF. <b>Confluence grades; it
  does not gate.</b> Its practical use is <em>ranking</em> — when four names ping in a session,
  it is how you choose which to work first. <code>★strong</code> appears at <b>6</b>, and that too
  is a read-out. One caveat: the round-number term is retained at weight 1, but the effect was
  tested and <b>did not replicate</b> — it flipped sign on an independent sample.</p>
</section>

<section id="rowsIV">
  <h2><span class="n">18</span>Bands IV–VI — decision, plan, portfolio</h2>

  <h3>Row 31 · TRIGGER</h3>
  <p class="m">GO 🟢P 🟢L 🟢V 🟢B ⚪R ⏱ ·PB Bull ★strong</p>
  <p>The headline names the <em>first failing gate</em>: <code>GO</code> · <code>no PA</code> ·
  <code>no location</code> · <code>no volume</code> · <code>below EMA20</code> ·
  <code>weak/red bar</code>.</p>
  <div class="gatebox">
    <p><b>GO = P AND L AND V AND B.</b> <code>R</code> is shown and never counted — a
    <code>?</code> on it means the trail source is unbound.</p>
  </div>
  <p>Trailing tags: <code>⏱</code> optional timing fired · <code>·PB</code> the pullback branch is
  active · <code>Bull</code>/<code>Rec</code> which path · <code>★strong</code> high confluence ·
  a role tag when a pattern’s kind mismatches its location.</p>

  <h3>Row 32 · STATUS</h3>
  <p>One sentence: the ruling plus what to do. The distinction that earns the row its place is
  <code>GO — arm buy-limit @ trigger close on the pullback</code> versus <code>GO — buy-limit @
  this bar’s close (fills at MARKET)</code>. “Buy the retest” sounds disciplined; <b>on the
  trigger bar itself there is no retest to wait for</b>, and saying otherwise is false
  comfort.</p>

  <h3>Row 33 · VERDICT</h3>
  <p>Four lines — <b>ruling · why · the one caveat · the action</b> — weighing the entire panel,
  not just the gates.</p>
  <div class="tw"><table>
    <thead><tr><th>Ruling</th><th>Meaning</th></tr></thead>
    <tbody>
      <tr><td class="k m">NO TRADE — Stage 3/4</td><td><b>Outranks everything.</b> Wrong structural frame</td></tr>
      <tr><td class="k m">NOT TRADEABLE</td><td>Blocked <em>and</em> in supply — clearing one gate will not make this a trade</td></tr>
      <tr><td class="k m">NOT TRADEABLE - ETF at +21% to NAV</td><td>You would book the loss on entry</td></tr>
      <tr><td class="k m">TAKE IT</td><td>Clean. Gates and the reward test both pass</td></tr>
      <tr><td class="k m">TAKE IT — PULLBACK TO VALUE</td><td>The best case: at value, triggered, with room</td></tr>
      <tr><td class="k m">ARM — PULLBACK TO VALUE</td><td>Right location, reward does not yet clear the bar</td></tr>
      <tr><td class="k m">BREAKOUT PIVOT</td><td>Do <b>not</b> buy in the band. Arm a buy-stop above it; blue sky beyond</td></tr>
      <tr><td class="k m">CLEAR TO BREAK</td><td>The overhead is a level to break <em>toward</em> the target, not a rejection</td></tr>
      <tr><td class="k m">CAUTION — momentum/chase</td><td>Triggered on weak location, or while extended</td></tr>
      <tr><td class="k m">SKIP — clean trigger, no room</td><td>Everything fired; there is nowhere to go</td></tr>
      <tr><td class="k m">SKIP — payoff too thin</td><td>Reward does not clear the applicable gate</td></tr>
      <tr><td class="k m">LOW QUALITY</td><td>Grinding arrival with bleeding delta — wait for a better tap</td></tr>
      <tr><td class="k m">ARM</td><td>Not triggered. Names the one missing gate</td></tr>
    </tbody>
  </table></div>
  <div class="note no">
    <span class="tag">The reward gate depends on the trade type — and they are not peers</span>
    <p>A <b>swing</b> trade must clear <b>R:R ≥ 2.0</b>; a <b>positional</b> trade must clear
    <b>ROI to T1 ≥ 20%</b>. The definitions differ — swing targets 5–8% over 8–12 weeks,
    positional 10–30% over 6–8 months — so applying both would be incoherent.</p>
    <p><b>A known tension, stated rather than hidden:</b> a positional T1 sits at 5R, so ROI to T1
    is 5 × risk%. With a 2.3% stop that is 11.5%, and <b>the 20% positional rule is unreachable
    whenever risk% is below 4%</b>. The two positional rules contradict by construction.</p>
  </div>

  <h3>Rows 35–37 · The plan</h3>
  <p><b>These print only on a GO</b> — before that they read <code>wait for GO</code>,
  deliberately. A plan on an untriggered setup is fiction, and reading one is how a watch
  candidate becomes a position.</p>
  <p><b>The trigger-bar latch.</b> The plan anchors to the bar the trigger <em>fired</em> on and
  does not move while the signal stays true. Without it a “retest limit” ratchets upward with
  price — <b>a limit that follows price is a market order wearing a limit’s clothes</b>, which is
  exactly what confirmation was meant to prevent. <code>trig 3b ago</code> tells you how far
  behind price the anchor sits; past a set age it re-latches, because a limit far behind an
  advancing market never fills.</p>
  <div class="note">
    <span class="tag">R-multiples, the one number that matters</span>
    <p>1R is your risk — entry to stop. A 2R target makes twice what you risked. It is the only
    comparable unit across stocks: a 3% move on a quiet name and a 9% move on a volatile one can
    both be exactly 2R.</p>
    <p><b>The canon in force:</b> positional (POS/WYC/REV) <b>3R and 5R</b> taking 25% at each;
    swing breakouts <b>2R and 4R</b> at 33%; swing reversals and gaps <b>2R/4R</b> at 50%.
    Positional therefore keeps <b>half the position</b> running past T2 on an uncapped trail —
    that is where a trend trade earns its keep.</p>
    <p><b>Stop ≠ invalidation.</b> The stop is where you get out; the invalidation is where the
    <em>reason you bought</em> stops being true. Usually different prices, and the invalidation is
    ranked by severity: zone distal, then swing low, then S/R, then EMA20.</p>
  </div>
  <p><b>Sizing.</b> <code>Shares = (Capital × Risk%) ÷ (Entry − Stop)</code>. Risk a fixed
  fraction per trade and let the stop distance decide the count, so a wide stop automatically
  produces a small position. <b>This is the mechanism that makes a losing streak
  survivable.</b></p>

  <h3>Rows 39–40 · Portfolio</h3>
  <p>Present only when the v67 slot is bound. These are a <b>bound snapshot, not a live
  recomputation</b> — v67 owns the slots, the levels and the ladder, so they cannot drift from
  its panel or from Risk Shield. <b>If the chart disagrees with the Pyramid page, the page is
  live and the chart is a photograph.</b></p>

  <h3>The SUMMARY column</h3>
  <p>The right-hand column reads the entire panel as <b>one judgement</b> — trend stack,
  leadership, location, participation, geometry, direction — and says what the combination
  <em>means</em>. It deliberately prints no value that appears above it. VERDICT is the short
  ruling; SUMMARY is the long-form read. It is a column rather than a row because a Pine table
  cell does not auto-wrap: full-width, it stretched the panel across the monitor.</p>
</section>

<section id="states">
  <h2><span class="n">19</span>Panels you will actually see</h2>
  <p>Individual rows are easy. The skill is the combination.</p>

  <div class="note go">
    <span class="tag">The A+ pullback — the one to wait for</span>
    <p class="m">Stage 2 · 7/8 · RS Positive Rising · RRG LEADING<br>
    AT VALUE 0.8×ATR · REACTING off pattern · CLEAR 8.2%<br>
    Σ+3 VCP · RV 0.7 thin ·PB · Bar OK · TRIGGER GO 🟢P🟢L🟢V🟢B<br>
    VERDICT: TAKE IT — PULLBACK TO VALUE ★strong</p>
    <p>Everything aligns <em>and price is at value</em>. Note RV is 0.7 — thin — and that is
    correct: this is the pullback branch, where dry volume is the feature. Size normally.</p>
  </div>

  <div class="note no">
    <span class="tag">The chase — the one that feels best and pays worst</span>
    <p class="m">Stage 2 · 8/8 · RS Positive Rising<br>
    EXTENDED 3.1×ATR ⚡para · AT LOCATION (⚪Zone ⚪S/R 🟢EMA20)<br>
    RV 2.1 strong · Bar OK · Σ+3 · TRIGGER GO 🟢P🟢L🟢V🟢B<br>
    VERDICT: CAUTION — momentum/chase</p>
    <p>Every gate passed and the context is perfect. <b>It is still a bad entry</b>: 3.1×ATR
    extended, and the only thing holding it up is the EMA20 — a curve that follows price. The stop
    must sit at real structure far below, so R:R is poor before the trade starts.
    <b>This panel is why the verdict weighs more than the gates.</b></p>
  </div>

  <div class="note no">
    <span class="tag">The trap — a breakout with nobody behind it</span>
    <p class="m">Stage 2 · OI Short covering +2.1% · RV 1.9 strong · Bar OK · GAP fired</p>
    <p>Volume looks excellent. It is shorts closing, not new buyers arriving — and when they
    finish, the bid disappears. <b>Row 7 is the only row that can see this.</b></p>
  </div>

  <div class="note no">
    <span class="tag">The false comfort — right structure, wrong stage</span>
    <p class="m">Stage 3 · 8/8 Minervini · RS Positive · Σ+6 · RV 1.6<br>
    VERDICT: NO TRADE — Stage 3</p>
    <p>Every quality metric is excellent and the 30-week average has rolled over. <b>This is the
    most dangerous panel on the list</b>, because everything you would normally check says buy.
    The stage veto exists precisely for it.</p>
  </div>

  <div class="note">
    <span class="tag">The armed watch — the normal state</span>
    <p class="m">Stage 2 · REACTING off pivot · CLEAR 6.1%<br>
    TRIGGER no volume 🟢P🟢L⚪V🟢B (RV 0.82/1.00) · VERDICT: ARM</p>
    <p>Nothing is wrong. Three of four gates hold and one is missing. <b>This is what most panels
    look like most of the time.</b> Set the alert and go do something else.</p>
  </div>

  <div class="note go">
    <span class="tag">The ninety-second read, in order</span>
    <p><b>Stage</b> → not 2 or 1, stop · <b>template, RS, RRG</b> → is this a leader ·
    <b>OI</b> → short covering? · <b>extension</b> → past 2.5×ATR you are late ·
    <b>location</b> → NOT AT LOCATION means no trade · <b>room</b> → in supply, nothing to win ·
    <b>the gates</b> → which chip is dark · <b>the verdict</b> → it already weighed all of it ·
    <b>the plan</b> → only if it says take it.</p>
    <p><b>Steps one to six decide the trade; seven to nine decide the timing.</b> Beginners invert
    this and read the verdict first.</p>
  </div>
</section>

<section id="misread">
  <h2><span class="n">20</span>Misreadings that cost money</h2>
  <div class="tw"><table>
    <thead><tr><th>The mistake</th><th>What is actually true</th></tr></thead>
    <tbody>
      <tr><td class="k">Reading <code>—</code> as a failure</td><td>It means <b>not measured</b>. Missing data is not evidence</td></tr>
      <tr><td class="k">Treating Σ as the gate</td><td>Σ grades. The gate is “did one pattern fire”</td></tr>
      <tr><td class="k">Buying because TRIGGER says GO</td><td>GO is four mechanical gates. The <b>verdict</b> weighs quality, location and room</td></tr>
      <tr><td class="k">Selling because RSI &gt; 70</td><td>In a Stage-2 trend RSI stays high for months. This is how you exit every winner early</td></tr>
      <tr><td class="k">Trusting Structure Health CLEAN</td><td>CLEAN is the ordinary state; the count has never reached 3</td></tr>
      <tr><td class="k">Reading a plan on a non-GO panel</td><td>It says <code>wait for GO</code> for a reason</td></tr>
      <tr><td class="k">Taking IMPROVING → LEADING as a buy</td><td>Measured <b>negative</b>. Only LEADING→LEADING and WEAKENING→LEADING survived</td></tr>
      <tr><td class="k">Assuming the panel shows live price</td><td>With closed-candle on it is the last <b>closed</b> bar, and every number agrees with that moment</td></tr>
      <tr><td class="k">Panicking at <code>— unbound</code></td><td>You recompiled. Re-run the bind script</td></tr>
      <tr><td class="k">Buying the touch of a zone</td><td>The <b>reaction</b> is the trade. <code>IN DEMAND</code> is not <code>REACTING off DZ</code></td></tr>
      <tr><td class="k">Reading a stop as an invalidation</td><td>The stop is where you exit; invalidation is where the thesis dies</td></tr>
      <tr><td class="k">Comparing RV across the session</td><td>RV is time-of-day biased: ~48% pass at 10:30, ~18% midday</td></tr>
    </tbody>
  </table></div>
  <div class="note go">
    <span class="tag">The three worth memorising</span>
    <p><b>1 · Stage decides everything.</b> Price against the 30-week average, and that average’s
    slope. Stage 3 and 4 are refused outright.</p>
    <p><b>2 · The reaction is the trade, not the arrival.</b> A fresh zone has proven nothing.
    Price returning, testing and turning is the setup.</p>
    <p><b>3 · GO is timing, not permission.</b> Four gates say something is firing now. Whether it
    is worth firing on is Band II’s answer, and the verdict’s.</p>
  </div>
</section>
''' + tail

h = h.replace(tail, body)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 22: {len(orig)} -> {len(h)} chars")
