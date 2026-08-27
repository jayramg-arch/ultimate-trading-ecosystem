"""Doc 25 (Golden Rules) — bring the location doctrine up to the 26-Aug code.

What was actually wrong, checked against zone_engine.py and the S4 Pine:
  * "a tested zone is deleted by the lifecycle" -- demand zones are now KEPT and
    greyed, and that change is what makes the reaction tradeable at all
  * the page had no notion of the three location STATES, so it read as though price
    had to be inside a zone
  * rule A2 and the pivot master switch are doctrine, not settings trivia -- Jay's
    own preference for pattern zones is what they encode

Deliberately NOT changed: both "+2.56%" citations. The staleness checker flagged them
and it was wrong -- each frames the number as the superseded figure it is, which is
exactly how a retired result should be cited. Narrowed the checker instead.
"""
import io

P = "docs_audit/pages/25_golden_rules.html"
h = io.open(P, encoding="utf-8").read()
orig = h


def sub(old, new, why):
    global h
    assert h.count(old) == 1, f"anchor ({h.count(old)}): {why}"
    h = h.replace(old, new)


sub("""There is a second route too: a <b>tested zone is
     deleted</b> by the lifecycle, so the touch that fired the alert can consume the zone that
     justified it.</p>""",
    """There is a second route too, though it is gentler
     than it used to be: a demand zone that spends its touch budget is <b>kept and greyed</b>
     rather than deleted — visible, but no longer arming a trade. A normal zone gets one test;
     a controlling or high-scoring one earns two. So the touch that fired the alert can still
     retire the zone that justified it, it just leaves the evidence on the chart.</p>""",
    "tested zone lifecycle")

sub("""        <li><b>Tests WEAKEN a level.</b> 1 = fresh · 2–5 = tested · <b>6+ = spent, and a breakout candidate</b>.</li>""",
    """        <li><b>Tests WEAKEN a level.</b> 1 = fresh · 2–5 = tested · <b>6+ = spent, and a breakout candidate</b>.</li>
        <li><b>Price does not have to be INSIDE the zone.</b> Three states, and only two of
        them are location: <b>IN</b> (price is in it), <b>REACTING</b> (tested once, turning
        up off it, and not yet far away) and <b>APPROACHING</b> (descending toward an untested
        one). The first two arm a trade. <b>The third never does</b> — nothing has reacted yet,
        so taking it is buying the touch.</li>
        <li><b>"Not too far away" is not a judgement call.</b> A reaction stays open only until
        price travels two ATR from the proximal, or crosses the reference average — the same
        rule that retires the zone. The gate reads that rule back rather than inventing a
        second one, which is why the two can never disagree.</li>
        <li><b>A pivot shelf must be confirmed; a pattern zone stands alone.</b> Rule A2. A
        pivot line and a reclaimed "Pivot S→R" count as pivot evidence too, so the same
        requirement applies to them. If you want none of it, the pivot switch turns off zones,
        location, the lines <em>and</em> the overhead — but note that last part <b>flatters
        R:R</b>, because a hidden ceiling is not a cleared one.</li>""",
    "location states")

# the measurements section is where a null result belongs
sub("""  <h2>The behavioural rules</h2>""",
    """  <div class="note"><span class="lbl">26 Aug — the location rule was measured, and it was a null</span>
    <p>A pre-registered A/B across eighteen anchors compared <b>any-zone</b>, <b>A2</b> and
    <b>pattern-only</b> on matched alpha. All three landed within <b>0.21 percentage points</b>
    of each other — a null. What tightening reliably changed was the number of trades:
    <b>221 → 88 → 51</b>. Pattern-only is not better per trade; it is rarer.</p>
    <p><b>So the choice of location rule is a doctrine call, not an evidence call.</b> A2 ships
    because the measurement cannot separate the three, which leaves the decision resting on
    which evidence you trust — and a leg-base-leg zone marks an imbalance while a pivot marks
    one turn. That is the honest reason, and it is worth more than a number that does not exist.</p>
  </div>

  <h2>The behavioural rules</h2>""",
    "A/B null")

io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 25: {len(orig)} -> {len(h)} chars")
