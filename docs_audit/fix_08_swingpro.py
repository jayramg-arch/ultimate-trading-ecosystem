"""Doc 08 (Swing Pro Dashboard) — what this surface EXPORTS, and the ML scorer.

The page documents the dashboard as a reading surface and its ownership rule, both
accurately. What it never says is that this file is also the binding CHANNEL: Section
Four reads twenty-five hidden numeric plots from it, so a recompile here silently
blanks rows over there. That belongs in "what this surface owns" — exporting is a form
of ownership, and it is the one with a failure mode.

The ML scorer moved here on 26 August for a concrete reason worth recording: it lived
in the strategy indicator, but the dashboard already owned five of its six inputs and
was already the channel, so binding beats a second channel to a second script.

Verified against the v67 file: 25 s4_* exports, 40 of 64 plot slots used.
"""
import io

P = "docs_audit/pages/08_swing_pro.html"
h = io.open(P, encoding="utf-8").read()
orig = h

anchor = '''</section>

<section id="day">
  <h2><span class="n">09</span>The daily loop</h2>'''

addition = '''  <h3>It is also the binding channel — and that is a kind of ownership</h3>
  <p>Section Four does not re-derive the fields above; it <b>reads them off this file</b> through
  twenty-five hidden numeric plots. That makes the dashboard the single source for stage, relative
  strength, rotation, sector and the pyramid rung across two surfaces — a field that is imported
  cannot drift from the one it was imported from.</p>
  <div class="note warn">
    <span class="lbl">The failure mode this creates, and how it presents</span>
    <p><b>Bindings are matched by POSITION and are dropped on every recompile</b> — of either
    script. Nothing errors: an unbound source silently reads the price series, so the far side
    shows a plausible-looking number rather than a blank. That is why re-binding is a step in the
    compile ritual and not a debugging response.</p>
    <p>Two structural limits worth knowing before designing anything around it. <b>Only floats
    cross</b> — a string cannot, which is why the sector NAME reaches Section Four through a packed
    map compiled into the shared library rather than over this channel. And <b>plot slots are
    finite</b>: this file uses 40 of its 64, and the exports account for 25 of them.</p>
  </div>

  <h3>The ML win probability — computed here, read elsewhere</h3>
  <p>A logistic scorer over six inputs — daily RSI, ATR as a percent of price, Bollinger width,
  relative strength against the index, the asset-quality score and the drawdown from the 52-week
  high. It is <b>computed on this surface and bound across</b> to Section Four's panel.</p>
  <p>It was moved here on 26 August rather than kept in the strategy indicator, because
  <b>this file already owned five of the six inputs and was already the channel</b> — the
  alternative meant a second binding channel to a second script, re-bound after every compile of
  either. One trap was avoided in the port: the two files scale relative strength differently, one
  centred on zero and one on a hundred, and feeding the raw value across would have shifted every
  score by a quarter of a point without any visible symptom.</p>
  <div class="note stop">
    <span class="lbl">Read it as a ranking, not a probability</span>
    <p><b>The six coefficients have never been validated out-of-sample in this system.</b> A
    reading of 38% does not mean thirty-eight trades in a hundred worked — it means this name
    ranks below one reading 60%. Use it to order a shortlist; do not use it to size anything.</p>
  </div>
</section>

<section id="day">
  <h2><span class="n">09</span>The daily loop</h2>'''

assert h.count(anchor) == 1, "section 09 anchor not unique"
h = h.replace(anchor, addition)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 08: {len(orig)} -> {len(h)} chars")
