"""Doc 01 (Structure Engine) — name the module, and admit what the tests do not cover.

Section 12 is the strongest account of the drift incident anywhere in the library. Two
things it stops short of:

  * it never names `strict_trend.py`, so a reader who wants to check the claim cannot find
    the file the claim is about;
  * it says the fixes are "mutation-verified", which is true of five of the seven. The test
    file itself is explicit that fix 2 and fix 6 have no failing test behind them, because
    the real-data fixtures contain no extension event and no window-boundary case. A guide
    that reports the coverage as uniform is quietly stronger than the code.

Verified:
  strict_trend.py                        193 lines, EQ_THRESHOLD = 0.002
  tests/test_strict_trend_regression.py:162-164
      "NOT COVERED by any failing test ... fix 2 (extension re-classifies against
       prevLocked*) and fix 6 (syncBars +1)"
"""
import io

P = "docs_audit/pages/01_structure_engine.html"
h = io.open(P, encoding="utf-8").read()
orig = h

old = ("The duplicate copies collapsed into <b>one shared module</b> with all seven fixes and a "
       "regression suite, mutation-verified.")
if h.count(old) != 1:
    import re
    m = re.search(r'The duplicate copies collapsed into.*?mutation-verified\.', h, re.S)
    assert m, "resolution sentence not found"
    old = m.group(0)

new = ('The duplicate copies collapsed into <b>one shared module</b> — <code>strict_trend.py</code>, '
       'with all seven fixes and a regression suite.')

h = h.replace(old, new)

# the honest coverage note, placed right after that paragraph's section
anchor = '<h2><span class="n">13</span>'
if anchor not in h:
    # no section 13 — append before the standing-rule note instead
    import re
    m = re.search(r'<div class="note[^"]*">\s*<span class="[^"]*">Standing rule</span>', h)
    assert m, "standing-rule note not found"
    anchor = m.group(0)

note = '''<div class="note warn">
    <span class="lbl">Five of the seven fixes have a test that fails without them</span>
    <p>Each of the five was mutation-verified: revert the fix, and a test goes red. <b>Two were
    not.</b> The extension re-classification and the window-boundary offset need an extension
    event and a boundary case that the real-data fixtures happen not to contain, so nothing
    would catch a regression in either.</p>
    <p>That is stated here rather than smoothed over, because a suite whose coverage you
    believe to be uniform is more dangerous than one you know the holes in. If either of those
    two behaviours ever needs changing, the test to trust does not exist yet — write the
    fixture first.</p>
  </div>

  ''' + anchor

h = h.replace(anchor, note, 1)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 01: {len(orig)} -> {len(h)} chars")
