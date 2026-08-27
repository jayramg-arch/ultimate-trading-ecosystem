"""Bring Doc 22 (Section Four) up to the code as of 26-Aug-2026.

Everything replaced here was checked against Section4_Entry_Trigger_v7.2.pine, not
against the session notes. What had moved:
  * the panel is SIX bands, not five -- VI PORTFOLIO was never documented
  * band II is no longer "Location & quality": it now holds Momentum & value and
    Room for Trade, and the section title in the Pine was corrected to match
  * Minervini, ML win probability and Momentum & value rows did not exist here
  * RS and RRG are two rows, not one, and the sector NAME now titles the RS row
  * Room for Trade moved out of band IV; Confluence moved into band III
  * LOCATION: a zone REACTED off now satisfies the gate, APPROACHING is a named
    watch state that deliberately does NOT, and rule A2 governs pivots
"""
import io

P = "docs_audit/pages/22_section_four.html"
h = io.open(P, encoding="utf-8").read()
orig = h


def sub(old, new, why=""):
    global h
    assert h.count(old) == 1, f"anchor not unique ({h.count(old)}): {why or old[:60]}"
    h = h.replace(old, new)


# ── 1. five bands -> six ──────────────────────────────────────────────────────
sub("sectioned into five bands</b>", "sectioned into six bands</b>")

# ── 2. band cards II, III, IV; add VI ─────────────────────────────────────────
sub("""      <p class="h">Decision synthesis</p>
      <p>What is the ruling? Room for trade, confluence score, the four gate chips, and the
      <b>VERDICT</b>.</p></div></div>
    <div class="pband"><div class="num">V</div><div class="bd">
      <p class="h">Plan &amp; risk</p>
      <p>How do we execute? Entry, stop, targets and quantity — <b>printed only on GO</b>.</p></div></div>
  </div>""",
    """      <p class="h">Decision synthesis</p>
      <p>What is the ruling? The four gate chips, the STATUS line and the
      <b>VERDICT</b>. Room and confluence used to live here and were moved
      <em>earlier</em> — see the note below.</p></div></div>
    <div class="pband"><div class="num">V</div><div class="bd">
      <p class="h">Plan &amp; risk</p>
      <p>How do we execute? Entry, stop, targets and quantity — <b>printed only on GO</b>.</p></div></div>
    <div class="pband"><div class="num">VI</div><div class="bd">
      <p class="h">Portfolio</p>
      <p>What do I already own here, and what does the ladder say? The v67 slot and the
      position state — <b>only meaningful on a name you hold</b>.</p></div></div>
  </div>
  <p class="refnote"><b>Two rows moved earlier on 26 Aug, and the reason is the same for both.</b>
  Room for Trade sat in band IV, <em>after</em> the whole pattern battery — but it is a hard
  structural filter the verdict already treats as NOT TRADEABLE, so discovering an overhead wall
  after parsing seventeen tokens was wasted work. It now ends band II. Confluence moved the other
  way, into band III: it <em>scores the evidence you just read</em>, so sitting in the decision
  band separated it from what it summarises.</p>""",
    "band cards")

# ── 3. band I table: Minervini, split RS/RRG, ML row ──────────────────────────
sub("""      <tr><td class="k">RS · RRG</td><td>Relative strength against the index and the sector, plus the rotation quadrant. <b>Wording is identical to the dashboard by design</b>, and the quadrant is derived from the same pair the dashboard classifies with — so it <em>is</em> the dashboard's quadrant, not a second opinion</td></tr>""",
    """      <tr><td class="k">Minervini template</td><td>The eight-point SEPA trend template, scored as a count so a name missing one leg is distinguishable from one missing five. <b>It grades — it never touches the GO decision.</b> Criterion 8 is the one approximation: Minervini ranks relative strength across the whole market and Pine cannot compute a cross-sectional rank, so the local proxy is the RS-Ratio against the Nifty 500. When the dashboard is <b>not bound</b> that criterion is dropped from the denominator and the row reads <b>/7~</b> rather than scoring a silent miss</td></tr>
      <tr><td class="k">RS (vs N500 / <em>sector</em>)</td><td>Relative strength against the index and against the sector. <b>The sector NAME titles the row</b> — read from the curated mapping, so you can see <em>which</em> sector the "Sec:" half is measured against. Note this row answers <b>direction</b> (is RS rising), which is not the same question as Minervini's criterion 8, which answers <b>level</b> (is RS above the index). A name recovering from underperformance reads <em>rising</em> here and still fails there — that is the IMPROVING quadrant, not a contradiction</td></tr>
      <tr><td class="k">RRG (vs N500)</td><td>The rotation quadrant and its trajectory, plus a green or red dot for tradeable. <b>Kept as its own row deliberately</b> — RS ranks a name, the quadrant times it, and they fail independently. The quadrant is derived from the same pair the dashboard classifies with, so it <em>is</em> the dashboard's quadrant, not a second opinion</td></tr>""",
    "RS/RRG split")

sub("""<tr><td class="k">Signal · Quality · RSI</td><td>The dashboard's action signal, asset quality and daily momentum. <code>not bound</code> means <b>the bindings are missing, not that the data is absent</b></td></tr>""",
    """<tr><td class="k">Signal · Quality · RSI</td><td>The dashboard's action signal, asset quality and daily momentum. <code>not bound</code> means <b>the bindings are missing, not that the data is absent</b>. <b>This row is the binding canary</b> — it is the one that tells you a recompile dropped the sources</td></tr>
      <tr><td class="k">ML win probability</td><td>A logistic scorer of six inputs, computed in the dashboard and bound across — plus the <b>GM rank</b>, which moved here because both are <em>scores of the setup</em> rather than facts about its structure. <b>Read it as a ranking, not a probability:</b> the six coefficients have never been validated out-of-sample in this system, so 38% does not mean thirty-eight trades in a hundred worked. Reads <b>— unbound</b> rather than a plausible number when the source is missing, because an unbound input returns the price, which is never null</td></tr>""",
    "ML row")

# ── 4. band II: Momentum & value, Room for Trade ──────────────────────────────
sub("""<tr><td class="k">Volume Profile</td><td>Value-area and point-of-control position. <b>The one composite component that earned its place</b> — it contributes on roughly a fifth of names</td></tr>""",
    """<tr><td class="k">Volume Profile</td><td>Value-area and point-of-control position. <b>The one composite component that earned its place</b> — it contributes on roughly a fifth of names</td></tr>
      <tr><td class="k">Momentum &amp; value</td><td>ADX with the directional pair, ATR as a percent of price, price against the <b>daily CPR pivot</b> and the <b>monthly VWAP</b>, and the VCP flag. Both those references are also drawn on the chart. The CPR is built from the <em>previous completed session</em>, so it cannot repaint intraday. It sits in this band rather than with the intraday rows because CPR and monthly VWAP are <b>value</b> references — they set up the extension question the next two rows answer</td></tr>""",
    "momentum row")

sub("""  <details class="ref"><summary>III · Execution &amp; timing — are the triggers firing</summary>""",
    """  </div></div></details>
  <details class="ref" open><summary>II · continued — the filter that ends the band</summary><div class="rb">
  <div class="tw"><table>
    <thead><tr><th>Row</th><th>How to use it</th></tr></thead><tbody>
      <tr><td class="k">Room for Trade</td><td>Distance to the first real obstacle overhead, in percent and in R, or <b>BLUE SKY</b> when there is nothing above. Measured to the <em>first</em> obstacle from six sources, not to a convenient one — a pivot ceiling is labelled as such and ranked last, because a swing high is weaker evidence than a supply zone. <b>This is a hard filter and it ends the band on purpose:</b> if there is no room, nothing in the next band can rescue the trade</td></tr>
    </tbody></table></div></div></details>

  <details class="ref"><summary>III · Execution &amp; timing — are the triggers firing</summary>""",
    "room row")

# ── 5. band III gains Confluence ──────────────────────────────────────────────
h_before = h
h = h.replace("""  <details class="ref"><summary>IV · Decision synthesis — the ruling</summary>""",
    """  </div></div></details>
  <details class="ref"><summary>III · continued — the evidence score</summary><div class="rb">
  <div class="tw"><table>
    <thead><tr><th>Row</th><th>How to use it</th></tr></thead><tbody>
      <tr><td class="k">Confluence</td><td>A ranked breakdown of every factor that contributed, out of the maximum available. It <b>grades, it never gates</b>. It moved into this band from the decision band because it scores the evidence you have just finished reading — sitting after the verdict separated it from its own inputs</td></tr>
    </tbody></table></div></div></details>

  <details class="ref"><summary>IV · Decision synthesis — the ruling</summary>""", 1)
assert h != h_before, "band IV anchor not found"

io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 22 updated: {len(orig)} -> {len(h)} chars")
