"""Doc 26 (Operating Loop) — the docs-truth check, and a ninth silent failure.

The page is accurate: the times match the scheduled jobs, and its silent-failure table
already names the binding drop after an S4 compile. Two additions, both from today.

  * a new post-close job (DOCS_TRUTH_CHECK) belongs in the cadence table beside the
    other automated ones
  * and it exists because of a NINTH silent failure the table did not have: the
    documentation going stale under a code change. That is the same shape as every
    other row — nothing announces it, and it costs a day when you act on a number the
    code stopped producing weeks ago.

Verified: docs_audit/truth_watch.py snapshots 39 facts and reports only what moved,
with the pages that cite each one.
"""
import io

P = "docs_audit/pages/26_operating_loop.html"
h = io.open(P, encoding="utf-8").read()
orig = h

# ── 1. the cadence table gains the new job ───────────────────────────────────
anchor = ('      <tr><td class="n">On code change</td><td>Re-baseline validation</td>'
          '<td>Any signal change invalidates prior walk-forward and Strategy Tester numbers</td></tr>')
addition = (anchor + '\n'
            '      <tr><td class="n">Daily, post-close</td><td>Docs truth check '
            '(<span class="m">DOCS_TRUTH_CHECK</span>)</td><td>Reports which code facts MOVED and '
            'which guide pages cite each one. Reports only — a moved fact can mean the doc is '
            'stale <em>or</em> that the code change was the mistake, and both have happened</td></tr>')
assert h.count(anchor) == 1, "cadence anchor not unique"
h = h.replace(anchor, addition)

# ── 2. the ninth silent failure ──────────────────────────────────────────────
row9 = ('      <tr><td>Every position has a resting stop</td><td>naked exposure</td></tr>')
assert h.count(row9) == 1, "silent-failure last row not found"
h = h.replace(row9, row9 + '\n'
              '      <tr><td class="n">Guides still match the code</td><td>you act on a number the '
              'code stopped producing weeks ago — the page reads fine, because nothing on it is '
              'marked wrong</td></tr>')

# retitle: it is nine now
assert h.count("eight things that fail silently") == 1
h = h.replace("eight things that fail silently", "nine things that fail silently")
assert h.count("Each of these has already cost a day or more.") == 1
h = h.replace("Each of these has already cost a day or more.",
              "Each of these has already cost a day or more.")

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"Doc 26: {len(orig)} -> {len(h)} chars")
