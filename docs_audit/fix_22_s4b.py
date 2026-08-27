"""Doc 22, second pass: LOCATION semantics and the inputs that changed.

The page described location as five ranked SOURCES, which is still true, but it
predates three changes that alter what the gate actually accepts:
  * a zone price is REACTING off satisfies location -- price need not be inside it
  * APPROACHING is a named state that deliberately does NOT satisfy it
  * rule A2: a PATTERN zone stands alone, a PIVOT shelf needs a confirming source
and the pivot toggle became a master switch over every pivot-as-support use.
"""
import io

P = "docs_audit/pages/22_section_four.html"
h = io.open(P, encoding="utf-8").read()
orig = h


def sub(old, new, why=""):
    global h
    assert h.count(old) == 1, f"anchor not unique ({h.count(old)}): {why}"
    h = h.replace(old, new)


sub("II · Location &amp; quality — where are we right now",
    "II · Location, value &amp; room — are we at value, and is there room",
    "band II summary")

sub('    <span class="tag">Why a GO can still be a chase</span>',
    """    <span class="tag">Three states, not one — and only two of them are location</span>
    <p><b>Price does not have to be inside a zone.</b> That was the gate's definition until
    26 August and it was the wrong question: the tradeable moment is the <em>reaction</em> —
    price retraces into the zone, tests it once, and turns back out. The engine had been
    computing that state all along and the gate was not reading it.</p>
    <div class="tw"><table>
      <thead><tr><th>State</th><th>What it means</th><th>Satisfies L?</th></tr></thead><tbody>
        <tr><td class="k">IN</td><td>Price is inside the zone right now</td><td><b>Yes</b></td></tr>
        <tr><td class="k">REACTING</td><td>Tested once and turning up off it, and <em>not yet far away</em></td><td><b>Yes</b></td></tr>
        <tr><td class="k">APPROACHING</td><td>Descending toward an untested zone, within one ATR of it</td><td><b>No</b></td></tr>
      </tbody></table></div>
    <p><b>"Not too far away" is not a new threshold.</b> A reaction stays open only until price
    travels two ATR from the proximal, or crosses the reference EMA20 — the same rule that
    retires the zone. So the gate reads that rule back rather than restating it, which is why
    the two can never disagree.</p>
    <p><b>APPROACHING is shown and deliberately not honoured.</b> Nothing has reacted yet, so
    passing it would be buying the touch — the one habit the whole two-stage design exists to
    prevent. It earns a name on the panel so you can watch it; it does not arm anything.</p>

    <span class="tag">Rule A2 — a pivot shelf is not a leg-base-leg zone</span>
    <p>Two things get drawn as "zones" and they are not equal evidence. A <b>pattern</b> zone
    (RBR / DBR / RBD / DBD) marks where an imbalance actually happened and has a distal edge
    that defines where you are wrong. A <b>pivot</b> shelf marks where price merely turned once.
    The gate treated them identically for months while this file's own header called the pivot
    "a weaker secondary shelf — location/stop confluence, not standalone".</p>
    <p>Under rule A2 a pattern zone <b>stands alone</b>; a pivot shelf must be confirmed by an
    S/R level or an anchored VWAP. <b>Pivot levels feed the gate too</b> — a pivot line, and a
    "Pivot S→R" once price has <em>reclaimed</em> it — and they enter as pivot evidence, so A2
    still applies to them.</p>
    <p><b>The master switch.</b> Turning pivot zones off removes them everywhere: no pivot zone
    is drawn, no pivot satisfies location, the pivot support lines are hidden, and pivots stop
    counting as overhead in Room, T1 and T2. That last part is a deliberate choice of Jay's over
    a documented objection — <b>a hidden ceiling is not a cleared one</b>, so R:R will read
    better with pivots off than the chart justifies. Measured on the live board, switching them
    off takes location from roughly 44% of names to 24%.</p>
    <p class="refnote"><b>Measured, so it is not a preference dressed as a finding:</b> a
    pre-registered A/B across eighteen anchors compared any-zone, A2 and pattern-only. All three
    landed within 0.21 percentage points of each other on matched alpha — a null. What the
    tightening reliably changed was the number of trades: 221, then 88, then 51. Pattern-only is
    not better per trade; it is rarer. A2 is shipped because the evidence cannot separate them,
    so the choice falls back on which evidence you trust.</p>

    <span class="tag">Why a GO can still be a chase</span>""",
    "location states")

io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 22 pass 2: {len(orig)} -> {len(h)} chars")
