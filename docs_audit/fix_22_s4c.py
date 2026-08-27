"""Doc 22, third pass — claims that reading the whole page surfaced.

Each of these was checked at a specific line of Section4_Entry_Trigger_v7.2.pine:
  * TOC still said "five sections"
  * Mode Auto was described by the OLD off-52w heuristic; pathResolve now keys on
    the stage, a drawdown band and the board's list, and adds a NO-TRADE third state
  * the geometry classifier no longer exists (`geom` is hardcoded "—"), so both the
    "known defect" note and its troubleshooting row describe an impossible symptom
  * the location input still said price must be INSIDE or near a zone
  * "strings cannot cross" is still true of bindings, but the sector name now
    reaches S4 through a packed map in the library rather than not at all
  * "a tested zone is deleted by the lifecycle" -- demand zones are now KEPT and
    greyed, and that is what makes a reaction tradeable at all
  * the weekly-zone troubleshooting row describes behaviour that was replaced
"""
import io

P = "docs_audit/pages/22_section_four.html"
h = io.open(P, encoding="utf-8").read()
orig = h


def sub(old, new, why):
    global h
    assert h.count(old) == 1, f"anchor not unique ({h.count(old)}): {why}"
    h = h.replace(old, new)


sub('<li><a href="#panel">The five sections</a></li>',
    '<li><a href="#panel">The six sections</a></li>', "TOC")

sub("""<td><b>Auto mirrors the board's structural split</b> — Recovery only when sufficiently off the 52-week high <em>and</em> the 30-week average is unrepaired <em>and</em> price is below the 200-day. That last leg keeps a shallow bull pullback resolving Bull. The header shows what it resolved to; the other two force it</td>""",
    """<td><b>Auto resolves the path from the STAGE, not from a drawdown alone.</b> Recovery when the board's recovery list names it, <em>or</em> the 60-bar drawdown sits inside the recovery band, <em>or</em> the name is Stage 1 and below its 200-day. Everything else resolves Bull. <b>There is a third state and it outranks both:</b> Stage 3 or 4 is NO TRADE, and that applies under manual mode too — the stage is a fact, not a preference. Before that existed, a Stage-3 name was forced into one of two tradeable paths and the verdict then reasoned faithfully inside a frame it should never have entered</td>""",
    "Mode Auto")

sub("""<tr><td class="k">Pattern | Shape</td><td>The flag and geometry classifier. <b>Known defect: the two-pivot classifier calls rectangles symmetrical triangles.</b> Cosmetic — it does not touch the gate</td></tr>""",
    """<tr><td class="k">Pattern | Shape</td><td>The pattern flag. <b>The Shape half now always prints an em-dash:</b> the geometry classifier was removed from S4 to fund the pullback-aware gate and lives in the S/R + Trendline Lab, where the tuning is actually happening. Its old defect — calling rectangles symmetrical triangles — can no longer occur here</td></tr>""",
    "Pattern|Shape row")

sub("""<td><b>This is the location gate.</b> GO only fires if the close is inside or near an active zone, pivot support or anchor. Off lets a trigger fire on volume alone, regardless of where price is</td>""",
    """<td><b>This is the location gate.</b> GO fires only if price is <em>at</em> location — inside a zone, near one, or <b>reacting off one it has already tested</b>. Off lets a trigger fire on volume alone, regardless of where price is</td>""",
    "location input")

sub("""<tr><td class="k">Draw at most N zones a side</td><td class="m">3</td><td><b>Display only.</b> Never changes the gate, the counts, or a verdict</td></tr>""",
    """<tr><td class="k">Draw at most N zones a side</td><td class="m">3</td><td><b>Display only.</b> Never changes the gate, the counts, or a verdict</td></tr>
      <tr><td class="k">Use Pivot (Structural) zones + levels</td><td class="m">on</td><td><b>The master switch for every pivot-as-support use</b>, and it is not display-only. Off: no pivot zone is created, no pivot satisfies location, the pivot support lines are hidden, <em>and</em> pivots stop counting as overhead in Room, T1 and T2. That last part loosens R:R — <b>a hidden ceiling is not a cleared one</b> — and is a deliberate choice over a recorded objection. It mirrors the board setting of the same name</td></tr>
      <tr><td class="k">Tested: travel measured in</td><td class="m">ATR</td><td>How far price must travel from the proximal, after a reaction, before the zone counts as spent. <b>Zone-width is legacy and inverted</b> — it made the move needed proportional to the zone's own size, so the narrowest and most precise zones died fastest</td></tr>
      <tr><td class="k">Tested rules 2 &amp; 3: Daily zones only</td><td class="m">off</td><td>Off (the default) means the EMA20-cross and pivot-break rules apply on <b>every</b> timeframe, each zone judged against its own reference: a weekly or monthly zone against the chart EMA20, a daily or intraday zone against the <b>daily</b> EMA20. On restores the older Daily-only restriction</td></tr>""",
    "pivot master switch")

sub("""<p>A source input carries <b>one float series</b>, so strings — sector name, macro label —
    cannot cross and stay on the dashboard. And inputs are matched <b>by position</b>, so
    inserting a new input mid-list <b>drops every existing binding</b>. If the rows go blank
    after an upgrade, <b>re-bind rather than debug</b>.</p>""",
    """<p>A source input carries <b>one float series</b>, so strings cannot cross a binding.
    <b>The sector name is the exception that proves the rule:</b> it does not travel over the
    binding channel at all — the curated mapping is compiled into the shared library as a packed
    string, so S4 spends one call rather than several hundred comparisons, and a string literal
    costs one token however long it is. And inputs are matched <b>by position</b>, so inserting a
    new input mid-list <b>drops every existing binding</b>. If the rows go blank after an upgrade,
    <b>re-bind rather than debug</b>.</p>""",
    "strings cannot cross")

sub("""There is
  a second mechanism too: <b>a tested zone is deleted by the lifecycle</b>, so the very touch that
  triggered the alert can consume the zone that justified it.</p>""",
    """There is
  a second mechanism too, though it is gentler than it used to be: a demand zone that spends its
  touch budget is now <b>kept and greyed rather than deleted</b>, so you can still see where price
  reacted — it simply stops arming a trade. A normal zone gets one test; a controlling or
  high-scoring one earns two.</p>""",
    "tested zone deleted")

sub("""<tr><td class="k">A weekly zone disappeared for no reason</td><td>Old behaviour: the tested check used the <b>daily</b> average for every timeframe, so a weekly zone died on a daily cross. <b>Judge a zone on its own timeframe</b></td></tr>""",
    """<tr><td class="k">A weekly zone disappeared for no reason</td><td>The old fix was to restrict the EMA and pivot rules to daily zones. <b>That was the wrong lever:</b> the defect was the wrong <em>series</em> — the daily average adjudicating a weekly base, at daily granularity. Both rules now run on every timeframe, each zone against its own reference. Measured across thirty names, weekly survival changed by 2.3% and monthly not at all</td></tr>""",
    "weekly zone troubleshooting")

sub("""<tr><td class="k">A rectangle called a triangle</td><td>Known and unfixed: the two-pivot geometry classifier mislabels rectangles. Cosmetic — it does not touch the gate</td></tr>""",
    """<tr><td class="k">The Shape half always reads an em-dash</td><td><b>Working as designed since v7.3.</b> The geometry classifier was removed to fund the pullback-aware gate; it lives in the S/R + Trendline Lab. Its old rectangle-as-triangle defect can no longer occur here</td></tr>""",
    "geometry troubleshooting")

io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 22 pass 3: {len(orig)} -> {len(h)} chars")
