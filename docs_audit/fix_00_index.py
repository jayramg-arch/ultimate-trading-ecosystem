"""The library index — add the audit report, and fix a stale count.

Two changes:

  * "14 Published pages" in the header strip was left behind: all 24 are published, and
    the section head two lines below already says "24 of 24". A count that disagrees with
    the count beside it is the index's own version of the drift this audit was about.
  * the audit report gets a card. It is filed ahead of the guides rather than among them
    because it is a document ABOUT the library, not a guide in it — and because a reader
    arriving after a code change wants the provenance note before they trust a page.

Uses the page's existing card markup and its own --evidence spine token, so nothing new
enters the design system.
"""
import io

P = "docs_audit/pages/00_library_index.html"
h = io.open(P, encoding="utf-8").read()
orig = h

# ── 1. the stale count ───────────────────────────────────────────────────────
old_ct = '<div class="count"><b>14</b><span>Published pages</span></div>'
assert h.count(old_ct) == 1, "count strip not found"
h = h.replace(old_ct, '<div class="count"><b>24</b><span>Published pages</span></div>')

# ── 2. the audit card, ahead of the guides ───────────────────────────────────
anchor = '''  <div class="sec-head">
    <h2>Published pages</h2><div class="rule"></div><span class="ct">24 of 24</span>
  </div>'''
assert h.count(anchor) == 1, "published-pages head not unique"

block = '''  <div class="sec-head">
    <h2>Provenance</h2><div class="rule"></div><span class="ct">checked 27 Aug</span>
  </div>

  <a class="card" style="--spine:var(--evidence)"
     href="https://claude.ai/code/artifact/a436bfba-a6dd-401d-ae19-41d4b94fac6e">
    <div class="spine"></div>
    <div class="card-b">
      <p class="card-n">Audit · 27 August 2026</p>
      <p class="card-t">The Library Audit</p>
      <p class="card-d">All 24 guides checked against source rather than against the notes.
      What had drifted, two cross-module gaps left open on purpose, the plan to close them —
      and the three scripts that now watch 47 code values so a page cannot go quietly stale
      again.</p>
      <div class="card-m"><span>Read when a number looks wrong</span><span class="go">Open →</span></div>
    </div>
  </a>

''' + anchor

h = h.replace(anchor, block)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"index: {len(orig)} -> {len(h)} chars")
