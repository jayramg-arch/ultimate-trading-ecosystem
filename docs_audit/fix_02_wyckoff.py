"""Doc 02 (Wyckoff) — the port's third output, and the two states it can never reach.

Section 07 describes the port well but stops at two of its three outputs. The third is
Structure Health, and it is the one most likely to be misread, because it looks like a
four-state quality reading and behaves like a two-state one.

  wcl_context.structure_health()  0-1 CLEAN · 2-3 CHOPPY · 4+ BROKEN
  ...and its own docstring records the measurement: the count NEVER reached 3, so
  CHOPPY means exactly 2, and BROKEN is unreachable.

That matters because Structure Health feeds the board's overall score and, per the live
tooltip, caps position size at CHOPPY. A reader who sees CLEAN on nearly every name may
conclude the market is unusually orderly; the truth is the scale is compressed.

The module was also unnamed, same as Doc 01 — a reader cannot check what they cannot find.

Verified:
  wcl_context.py:76        CHOCH_WINDOW = 20
  wcl_context.py:309-320   structure_health(), with the 0/38 measurement in its docstring
  weinstein_commander_web_v4.0.py:13909  tooltip still offers "BROKEN (4+ CHoCHs)"
  gm_trigger_board.py:699  Structure Health is a term in the risk/quality leg of the score
"""
import io

P = "docs_audit/pages/02_wyckoff.html"
h = io.open(P, encoding="utf-8").read()
orig = h

anchor = '<h2><span class="n">08</span>'
assert h.count(anchor) == 1, "section 08 anchor not unique"

note = '''<div class="note warn">
    <span class="lbl">The port's third output — and why it reads CLEAN almost always</span>
    <p>The same module — <code>wcl_context.py</code> — also produces <b>Structure Health</b>, a
    count of structure-shift events in the trailing twenty bars. It is banded
    <b>CLEAN</b> (0–1), <b>CHOPPY</b> (2–3) and <b>BROKEN</b> (4+), and it is used: it is a term
    in the board's risk-and-quality leg, and it caps position size once it leaves CLEAN.</p>
    <p><b>Two of those four numbers never occur.</b> Measured across the board universe, the
    count never reached three — distribution tops out at two. So in practice <b>CHOPPY means
    exactly two events, and BROKEN is unreachable.</b> A gate keyed on three or more would
    never fire once, which is exactly the kind of dead condition that reads as a working
    safeguard until you check it.</p>
    <p>So read CLEAN as <em>the ordinary state</em>, not as a clean bill of health, and treat a
    CHOPPY as the meaningful signal — it is the top of the scale, not the middle of it. This is
    also the shape of the two rejections in section 02: Wyckoff describes what price has done,
    and it keeps failing when asked to decide what to do next.</p>
  </div>

  ''' + anchor

h = h.replace(anchor, note)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 02: {len(orig)} -> {len(h)} chars")
