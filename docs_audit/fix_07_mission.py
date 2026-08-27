"""Doc 07 (Mission Control) — the navigation map, which had drifted from the sidebar.

This is the page a reader uses to FIND things, so a wrong map is worse here than a wrong
number: it sends you looking in a group that does not exist. Six errors, checked against
NAV_GROUPS in weinstein_commander_web_v4.0.py:1400-1442.

  * CONTROL CENTER — the first group in the sidebar — was missing entirely, and its members
    were scattered: DASHBOARD filed under Daily Intel, PORTFOLIO under Discovery, COMMAND
    under Execution.
  * RISK SHIELD missing. It is where open positions are actually managed.
  * ACTION CENTER missing.
  * GOLDEN MATCHER missing from Execution — the most-used page in the daily loop.

Also corrected: PYRAMID is no longer a page of its own. Pyramid/trim classification is
computed inside RISK SHIELD (:16042, `import pyramid_logic as pl`), so looking for a
sidebar entry finds nothing.

Verified group-by-group against NAV_GROUPS; EXTERNAL_PAGES vs inline noted at :1387.
"""
import io

P = "docs_audit/pages/07_mission_control.html"
h = io.open(P, encoding="utf-8").read()
orig = h

i = h.find('<div class="groups">')
j = h.find('</div>\n  <div class="note">', i)
assert 0 < i < j, "groups block not located"

groups = '''<div class="groups">

    <div class="grp"><div class="hd"><p class="t">🎛️ Control Centre</p><p class="w">What you own, right now</p></div>
      <div class="pgs">
        <div class="pg"><span class="n">DASHBOARD</span><span class="j">Your open book — health vitals, live P&amp;L, exit scan, correlation risk</span></div>
        <div class="pg"><span class="n">PORTFOLIO</span><span class="j">Factor exposure, value-at-risk, stress tests</span></div>
        <div class="pg"><span class="n">COMMAND</span><span class="j">Trade management — exit and trail engines, GTT book, alerts, agents</span></div>
        <div class="pg"><span class="n">RISK SHIELD</span><span class="j">Position-by-position stop management, and the pyramid / trim ladder</span></div>
        <div class="pg"><span class="n">ACTION CENTER</span><span class="j">Everything pending that wants a decision, in one list</span></div>
      </div></div>

    <div class="grp"><div class="hd"><p class="t">🩺 State of Market</p><p class="w">First, always</p></div>
      <div class="pgs">
        <div class="pg"><span class="n">MACRO</span><span class="j">Global risk, VIX, currencies, commodities, sector rotation</span></div>
        <div class="pg"><span class="n">BREADTH</span><span class="j">Index internals — regime score, advance/decline, McClellan, stage map</span></div>
        <div class="pg"><span class="n">NEWS</span><span class="j">Live feeds plus paid analyst recommendations, filterable per stock</span></div>
      </div></div>

    <div class="grp"><div class="hd"><p class="t">📅 Daily Intel</p><p class="w">Before the open · after the close</p></div>
      <div class="pgs">
        <div class="pg"><span class="n">PRE-MARKET</span><span class="j">Overnight pulse, calendar, options positioning, the AI brief</span></div>
        <div class="pg"><span class="n">POST-MARKET</span><span class="j">EOD summary, provisional flows, top movers</span></div>
      </div></div>

    <div class="grp"><div class="hd"><p class="t">🔍 Discovery</p><p class="w">Finding candidates</p></div>
      <div class="pgs">
        <div class="pg"><span class="n">HUNTER</span><span class="j">The screening engine — bull, recovery, matcher, batch X-ray</span></div>
        <div class="pg"><span class="n">WATCHLIST</span><span class="j">Generate and sync lists, smart rank, sector database, track record</span></div>
        <div class="pg"><span class="n">X-RAY</span><span class="j">Single-stock fundamental deep dive with scorecards</span></div>
        <div class="pg"><span class="n">ETF</span><span class="j">Rotation, asset-class regime, liquidity scoring</span></div>
      </div></div>

    <div class="grp"><div class="hd"><p class="t">⚡ Execution</p><p class="w">Live, during the session</p></div>
      <div class="pgs">
        <div class="pg"><span class="n">GOLDEN MATCHER</span><span class="j">The trigger board and the single-symbol decision path — where the day's shortlist is armed</span></div>
        <div class="pg"><span class="n">OPTIONS</span><span class="j">Live chain — put-call ratio, max pain, open interest, volatility skew</span></div>
        <div class="pg"><span class="n">TV SIDECAR</span><span class="j">Quick quote, key levels and a small chart beside your real chart</span></div>
      </div></div>

    <div class="grp"><div class="hd"><p class="t">🔬 Analysis</p><p class="w">Evenings and weekends</p></div>
      <div class="pgs">
        <div class="pg"><span class="n">AUTOPSY</span><span class="j">Closed-trade post-mortem and performance attribution</span></div>
        <div class="pg"><span class="n">BACKTEST</span><span class="j">Forward-return analysis of screener signals</span></div>
        <div class="pg"><span class="n">AI LAB</span><span class="j">Pre-flight scoring, analysis, auto-pilot, weekly report</span></div>
      </div></div>

    <div class="grp"><div class="hd"><p class="t">📁 Records</p><p class="w">The permanent record</p></div>
      <div class="pgs">
        <div class="pg"><span class="n">JOURNAL</span><span class="j">The full trade journal</span></div>
      </div></div>

  '''

h = h[:i] + groups + h[j:]

# ── the two things a reader looks for and does not find ──────────────────────
anchor = '    <span class="tag">The sidebar\'s one-click button</span>'
assert h.count(anchor) == 1, "auto-pilot note not found"

note = '''    <span class="tag">Two pages that are not where you would look for them</span>
    <p><b>There is no PYRAMID page.</b> The add / trim / reduce ladder is computed inside
    <b>RISK SHIELD</b>, which is the right place for it — an add is a decision about a position
    you already hold, and it has to be read next to that position's stop, not on a screen of its
    own.</p>
    <p><b>GOLDEN MATCHER sits under Execution, not Discovery</b>, and the distinction is the
    whole architecture: <em>the watchlists qualify, the board times</em>. By the time a name
    reaches the board it has already been chosen. What is left is when.</p>
  </div>

  <div class="note">
''' + anchor

h = h.replace(anchor, note)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 07: {len(orig)} -> {len(h)} chars")
