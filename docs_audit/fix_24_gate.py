"""Doc 24 (Pre-Trade Gate) — the one gate that can be stale by the time you read it.

The page is a procedure and it is accurate: five rules, a fixed reply shape, a written
override. What it never says is that one of the four gates it quotes verbatim is
TIME-DEPENDENT, which matters here more than anywhere else — this review happens
minutes to hours after the alert, and the rule "quote the panel verbatim" is exactly
what turns a legitimately-expired gate into an apparent contradiction.

It does NOT owe an explanation of location semantics — that is Doc 22's job, and the
page's whole discipline is quoting rather than interpreting. What it owes is the
procedural consequence.

Verified against Section4_Entry_Trigger_v7.2.pine: P, V and B are properties of the
trigger bar and are fixed once it closes; L is "price is at a level right now".
"""
import io

P = "docs_audit/pages/24_pretrade_gate.html"
h = io.open(P, encoding="utf-8").read()
orig = h

anchor = "05</span>The override sentence"

addition = '''<span class="n">04b</span>Three gates are frozen. One is not.</h2>
  <p>The review happens <em>after</em> the alert — sometimes minutes, sometimes an hour. That gap
  matters, because the four gates do not age the same way.</p>
  <div class="tw"><table>
    <thead><tr><th>Gate</th><th>Nature</th><th>Still true when you read it?</th></tr></thead>
    <tbody>
      <tr><td class="k">P · pattern</td><td>A pattern <em>formed</em> on that bar</td><td><b>Yes</b></td></tr>
      <tr><td class="k">V · volume</td><td>A property of that bar</td><td><b>Yes</b></td></tr>
      <tr><td class="k">B · bar</td><td>A property of that bar</td><td><b>Yes</b></td></tr>
      <tr><td class="k">L · location</td><td><em>Price is at a level right now</em></td><td><b>No — price moves off it</b></td></tr>
    </tbody>
  </table></div>
  <div class="note">
    <span class="lbl">What this changes about the review, and what it does not</span>
    <p>An alert can be <b>correct at 10:30</b> and the panel read <code>L·</code> when you open it
    at 11:45. <b>Neither is wrong.</b> You are reading a snapshot taken after the event, and the
    trade's premise was "buy at the level" — so if location has gone, the premise has gone with
    it, and no amount of the other three gates replaces it.</p>
    <p><b>The rules do not bend for this.</b> Quote the panel verbatim, as it reads now — an
    expired L is still an L✗, not "it was fine earlier". What changes is only the diagnosis: this
    is the one gate where a failure can mean <em>you arrived late</em> rather than <em>the setup
    was never there</em>, and those call for different responses. The first is a missed window;
    the second is a rejected candidate.</p>
  </div>

  <h2><span class="n">05</span>The override sentence'''

assert h.count(anchor) == 1, "section 05 anchor not unique"
h = h.replace(anchor, addition)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 24: {len(orig)} -> {len(h)} chars")
