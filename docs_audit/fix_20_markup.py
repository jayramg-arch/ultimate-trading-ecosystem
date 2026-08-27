"""Doc 20 (Markup Engine) — the boundary with the zone engine.

The page is accurate and its touch rule is right. What it never says is that a reader
running this alongside the entry trigger has TWO kinds of horizontal object on one chart,
and they answer the same event in opposite ways:

  a LEVEL is price memory   — tested weakens the read, a close beyond FLIPS it and it
                              stays on the chart forever (this page's throwback memory)
  a ZONE is fuel            — a reaction spends it, and a close beyond the distal DELETES it

Both behaviours are correct for what they model, and the asymmetry is deliberate. It is
worth stating once, on the page most likely to be read while both are loaded, because the
natural instinct on seeing them disagree is to "fix" one of them.

Verified:
  zone_engine.py   TESTED_TRAVEL_ATR / KEEP_TESTED_DEMAND / violation deletes
  this page, §04   "a just-broken line is frozen rather than discarded"
"""
import io

P = "docs_audit/pages/20_markup_engine.html"
h = io.open(P, encoding="utf-8").read()
orig = h

anchor = '<h2><span class="n">05</span>'
assert h.count(anchor) == 1, "section 05 anchor not unique"

note = '''<div class="note">
    <span class="lbl">Levels and zones are not the same object — do not reconcile them</span>
    <p>With the entry trigger loaded you have two kinds of horizontal on one chart, and they
    answer a touch in opposite ways. That is intentional.</p>
    <div class="tw"><table>
      <thead><tr><th></th><th>A level, here</th><th>A demand zone, on the entry trigger</th></tr></thead>
      <tbody>
        <tr><td class="k">What it models</td><td>Price <b>memory</b></td><td>Unfilled <b>orders</b></td></tr>
        <tr><td class="k">A touch</td><td><b>Weakens</b> the read — repeatedly tested is a break candidate, not a fortress</td><td><b>Spends</b> it — the reaction is the trade, and the fuel is consumed</td></tr>
        <tr><td class="k">A close beyond</td><td><b>Flips</b> it. Broken support becomes resistance and stays on the chart</td><td><b>Deletes</b> it. There is nothing left to react to</td></tr>
      </tbody>
    </table></div>
    <p>So a line that has been tested four times and a zone that has been tested once are
    telling you opposite things about their own reliability, and both are right. <b>The one
    that disagrees with your instinct is usually the one worth reading.</b></p>
  </div>

  ''' + anchor

h = h.replace(anchor, note)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 20: {len(orig)} -> {len(h)} chars")
