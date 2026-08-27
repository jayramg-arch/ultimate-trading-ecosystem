"""Doc 23 (Golden Matcher) — the location rule and the columns that carry it.

Checked against weinstein_commander_web_v4.0.py and gm_trigger_board.py. The page had
no notion of rule A2, the three location states, or the two columns that now express
them — and it did not record the defect that made the Daily tab disagree with the
intraday tabs for weeks, which is the kind of thing a reader needs precisely because
it looked like a data problem rather than a code one.
"""
import io

P = "docs_audit/pages/23_golden_matcher.html"
h = io.open(P, encoding="utf-8").read()
orig = h


def sub(old, new, why):
    global h
    assert h.count(old) == 1, f"anchor ({h.count(old)}): {why}"
    h = h.replace(old, new)


# ── the Loc / →Zone columns ───────────────────────────────────────────────────
sub("""<tr><td class="k">Entry · SL · T1 · R:R</td>""",
    """<tr><td class="k">Loc</td><td>Not a tick — <b>it names the state and the kind of evidence</b>.
      <code>AT pattern D</code> · <code>REACTING off pattern D</code> · <code>AT pivot+conf</code> ·
      <code>pivot only ✗</code> · <code>APPROACHING pattern D −0.5%</code> · <code>−2.3% → pattern D</code>.
      Three different trades used to read identically as "AT"; they no longer do</td></tr>
      <tr><td class="k">→Zone</td><td>Distance to the nearest <b>fresh pattern zone below price</b>,
      or 0 when price is already at one. <b>Pivots are deliberately excluded</b> — a queue built from
      pivot shelves would recreate the problem one step earlier. This turns a strict gate from an
      apparent signal shortage into a watch list: measured across 76 names, <b>82.9% HAVE a fresh
      pattern zone but only 3.9% have price inside one</b>. The zones are not scarce; price is
      rarely at them</td></tr>
      <tr><td class="k">Entry · SL · T1 · R:R</td>""",
    "Loc and Zone columns")

# ── rule A2 into the gates section ────────────────────────────────────────────
sub("""  <h2><span class="n">10</span>The guided execution</h2>""",
    """  <div class="note">
    <span class="lbl">What LOCATION actually accepts — three states and two kinds of evidence</span>
    <p><b>Price does not have to be inside a zone.</b> <code>IN</code> and <code>REACTING</code>
    (tested once, turning up off it, and not yet two ATR away) both satisfy the gate;
    <code>APPROACHING</code> is named on the board and deliberately does <b>not</b> — nothing has
    reacted yet, so honouring it would be buying the touch.</p>
    <p><b>Rule A2 governs the kind.</b> A pattern zone stands alone; a pivot shelf must be
    confirmed by an S/R level or an anchored VWAP. Pivot <em>levels</em> — a pivot line, or a
    "Pivot S→R" once price has reclaimed it — count as pivot evidence and inherit the same
    requirement. Turning pivots off in settings removes them from zones, location, the drawn lines
    <b>and</b> the overhead used by Room; that last part <b>flatters R:R</b>, so it is a deliberate
    trade rather than a free tightening.</p>
    <p class="small"><b>Measured, and it did not settle the question:</b> a pre-registered A/B over
    eighteen anchors put any-zone, A2 and pattern-only within <b>0.21 percentage points</b> of each
    other on matched alpha — a null — while the trade count fell <b>221 → 88 → 51</b>. Pattern-only
    is rarer, not better. A2 ships because the evidence cannot separate them.</p>
  </div>

  <h2><span class="n">10</span>The guided execution</h2>""",
    "A2 note")

# ── the Daily-tab defect ──────────────────────────────────────────────────────
sub("""  <h2><span class="n">13</span>Troubleshooting</h2>""",
    """  <div class="note bad">
    <span class="lbl">26 Aug — why the Daily tab used to disagree with 75m and 125m</span>
    <p>The whole strict-location block — rule A2, the strict flag, and every <code>loc_*</code>
    field — sat inside a branch that only ran for <b>75m and 125m</b>. So the Daily tab silently
    kept the <em>old saturated gate</em>: 19 "Buy Trigger Live" against 13 on 75m, names scoring
    4/4 while sitting 11% below their nearest zone, and a blank Loc column because the keys it
    reads were never set.</p>
    <p><b>It presented as a data problem and was a scoping one.</b> The fix was to extract the rule
    into one function called on both paths rather than copy it — a second copy is how the two
    drifted in the first place. Daily now passes location on <b>47%</b> of names with a 9-pattern /
    9-pivot split, the same shape as the intraday tabs.</p>
  </div>

  <h2><span class="n">13</span>Troubleshooting</h2>""",
    "daily tab defect")

io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 23: {len(orig)} -> {len(h)} chars")
