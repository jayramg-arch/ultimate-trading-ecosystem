"""The Bible — the zone lifecycle, which the page had one state short.

The page said zones move "fresh -> tested -> violated". That sequence is wrong in a way
that matters at the moment of the trade: it implies a zone is finished the first time
price touches it, when the whole premise of the entry is that price comes BACK to a zone,
tests it, and reacts. The reaction IS the trade. A zone that has never been touched is a
zone that has not yet proven anything.

The real lifecycle is fresh -> reacted -> spent, retirement needs a CONFIRMATION, and
violation is a separate terminal state.

Verified in zone_engine.py:
  TESTED_TRAVEL_ATR = 2.0        travel from the proximal, in the zone's OWN-TF ATR
  KEEP_TESTED_DEMAND = True      spent demand is greyed, not removed
  DEMAND_STRONG_SCORE = 75       controlling or score >= 75 earns a second test
  Zone.touch_budget()            1 test normally, 2 for those
  at_support_reacting            reacting = z.reacted and px >= z.distal
  _daily_ref()                   W/M judge against the CHART EMA20; D and intraday
                                 against the DAILY EMA20
and in Section4_Entry_Trigger_v7.2.pine: _reactD = isDemand and reacted and close >= distal.
"""
import io

P = "docs_audit/pages/bible.html"
h = io.open(P, encoding="utf-8").read()
orig = h

old = """  ageing per timeframe and moving fresh → tested → violated; alongside it, horizontal S/R levels
  that <em>weaken</em> as they are tested, three anchored VWAPs, and volume-profile levels.</p>"""

new = """  ageing per timeframe and moving <b>fresh → reacted → spent</b>; alongside it, horizontal S/R
  levels that <em>weaken</em> as they are tested, three anchored VWAPs, and volume-profile
  levels.</p>
  <div class="note">
    <span class="tag">The reaction is the trade — not the arrival</span>
    <p>A fresh zone has proven nothing. It is a place where price once left in a hurry, and
    the reason to care is the <em>next</em> visit: price returns, tests the zone, and turns.
    <b>That turn is the setup.</b> So the location gate does not ask &ldquo;is price inside a
    fresh zone&rdquo; — it accepts a zone price is sitting in, one price is approaching, and one
    price has already reacted off and not yet run away from.</p>
    <p>Retirement takes a <b>confirmation, not a touch</b>. A reacted zone is spent only once
    price travels <b>twice the zone&rsquo;s own-timeframe ATR</b> from the proximal edge, crosses
    the EMA20, or breaks the higher-timeframe pivot that framed it. Until one of those happens
    the zone is still live and still tradeable — which is exactly the window a pullback entry
    lives in. <b>Violation is a different ending</b>: price closing beyond the distal edge, which
    kills the zone outright rather than spending it.</p>
    <p>Two asymmetries are deliberate. <b>Demand gets a longer life than supply</b> — spent
    demand stays on the chart greyed, and a controlling zone or one scoring 75+ earns a
    <em>second</em> test before it retires. And the EMA20 that judges a zone is the one that
    frames it: <b>weekly and monthly zones answer to the chart&rsquo;s EMA20, daily and intraday
    zones to the daily EMA20</b>. Judging a weekly zone by a daily average retires it on noise
    it was never built to survive.</p>
  </div>"""

assert h.count(old) == 1, "location paragraph not unique"
h = h.replace(old, new)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Bible: {len(orig)} -> {len(h)} chars")
