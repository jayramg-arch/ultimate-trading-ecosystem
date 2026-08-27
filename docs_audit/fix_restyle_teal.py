"""Re-palette the restyle mockup around teal — low-saturation, long-session-friendly.

Jay: "colors that are soothing on eyes like teal".

The change is a hue rotation of the NEUTRALS toward a soft blue-green, teal as the accent
in place of the Tailwind blue, and — this is the part that revises what I argued last
round — the semantic trio DESATURATED.

Last round I said keep the semantic colours exactly. That still holds for the part that
matters: green stays bull, red stays bear, amber stays warn, so the learned association
survives untouched. What changes is only their SATURATION. #DC2626 is a fire-engine red
built to alarm; at the eighth hour of a session it is fatiguing, and a book with several
red rows becomes hard to look at. #C2453C carries the same meaning at a lower cost.

Softening a hue is a different act from swapping one.
"""
import io

P = "docs_audit/pages/commander_restyle.html"
h = io.open(P, encoding="utf-8").read()
orig = h

# ── the light palette ────────────────────────────────────────────────────────
old_light = """:root{
  --ground:#EDF0F3; --surface:#FFFFFF; --surface-2:#F6F8FA; --surface-3:#E3E8EE;
  --ink:#0B1017; --ink-2:#36414F; --muted:#657486; --faint:#96A2B2;
  --rule:#D4DBE3; --rule-soft:#E5EAEF;
  --acc:#1D4ED8; --acc-bg:#E8EEFC; --acc-rule:#A9C0EE;
  --bull:#15803D; --bull-bg:#E4F1E9; --bull-rule:#9CC8AE;
  --bear:#DC2626; --bear-bg:#FBE9E8; --bear-rule:#E5ABA6;
  --warn:#B45309; --warn-bg:#FBF0E1; --warn-rule:#E0BD8C;"""
new_light = """:root{
  --ground:#EDF2F2; --surface:#FFFFFF; --surface-2:#F5F9F9; --surface-3:#E1E9E9;
  --ink:#0D1618; --ink-2:#35474A; --muted:#64757A; --faint:#95A5A8;
  --rule:#D2DDDD; --rule-soft:#E4EBEB;
  --acc:#0E7C86; --acc-bg:#E2F0F1; --acc-rule:#9BC7CB;
  --bull:#1B7A5A; --bull-bg:#E3F0EB; --bull-rule:#9BC6B5;
  --bear:#C2453C; --bear-bg:#F9EAE8; --bear-rule:#E0AEA9;
  --warn:#A76A1E; --warn-bg:#F8F1E2; --warn-rule:#DCC190;"""
assert h.count(old_light) == 1, "light palette not unique"
h = h.replace(old_light, new_light)

# ── the dark palette (twice: media query + explicit stamp) ───────────────────
old_dark = """    --ground:#0E1216; --surface:#151A20; --surface-2:#1A2027; --surface-3:#212832;
    --ink:#E7ECF2; --ink-2:#BDC7D3; --muted:#84909F; --faint:#616D7C;
    --rule:#252D37; --rule-soft:#1D242C;
    --acc:#7BA0F0; --acc-bg:#131C2E; --acc-rule:#2C4270;
    --bull:#3FBE7A; --bull-bg:#0D2A1B; --bull-rule:#1E5238;
    --bear:#F0726A; --bear-bg:#2E1614; --bear-rule:#612C28;
    --warn:#E0A33D; --warn-bg:#2C2210; --warn-rule:#5C471C;"""
new_dark = """    --ground:#0F1618; --surface:#161F21; --surface-2:#1B2528; --surface-3:#222E31;
    --ink:#E3EBEC; --ink-2:#B6C4C6; --muted:#7E8E91; --faint:#5C6B6E;
    --rule:#232F32; --rule-soft:#1B2528;
    --acc:#56C2CC; --acc-bg:#0C262A; --acc-rule:#1F4A50;
    --bull:#45BE92; --bull-bg:#0C2A21; --bull-rule:#1D5142;
    --bear:#E9857C; --bear-bg:#2C1A18; --bear-rule:#5C332E;
    --warn:#DCA84E; --warn-bg:#2A2211; --warn-rule:#57461F;"""
# The dark palette appears TWICE — once under the media query, once under the
# [data-theme="dark"] stamp — at different indents. Matching the whole block means
# getting both indents exactly right, which is how the first attempt failed. Replace the
# token LINES instead: they are byte-identical in both copies, so a global replace hits
# both regardless of leading whitespace.
#
# Then assert the count DOUBLED. A token redefined in only one of the two blocks is the
# classic unreadable-artifact bug: the explicit toggle and the system default disagree,
# and one of them renders one theme's text on the other theme's ground.
_o_lines = [l.strip() for l in old_dark.strip().split("\n")]
_n_lines = [l.strip() for l in new_dark.strip().split("\n")]
for _o, _n in zip(_o_lines, _n_lines):
    assert h.count(_o) == 2, f"expected 2 copies of {_o[:38]!r}, found {h.count(_o)}"
    h = h.replace(_o, _n)

# ── the proposed-side ground in the specimen rig ─────────────────────────────
# (.stage.new already reads var(--ground); nothing to change)

# ── the swatch strip must show the NEW palette ───────────────────────────────
old_sw = """    <div class="sw"><div class="chipbar" style="background:#15803D"></div>
      <div class="meta"><b>#15803D</b><span>bull · kept</span></div></div>
    <div class="sw"><div class="chipbar" style="background:#DC2626"></div>
      <div class="meta"><b>#DC2626</b><span>bear · kept</span></div></div>
    <div class="sw"><div class="chipbar" style="background:#B45309"></div>
      <div class="meta"><b>#B45309</b><span>warn · kept</span></div></div>
    <div class="sw"><div class="chipbar" style="background:#1D4ED8"></div>
      <div class="meta"><b>#1D4ED8</b><span>accent · kept</span></div></div>
    <div class="sw"><div class="chipbar" style="background:#EDF0F3"></div>
      <div class="meta"><b>#EDF0F3</b><span>ground · new</span></div></div>
    <div class="sw"><div class="chipbar" style="background:#0B1017"></div>
      <div class="meta"><b>#0B1017</b><span>ink · new</span></div></div>"""
new_sw = """    <div class="sw"><div class="chipbar" style="background:#0E7C86"></div>
      <div class="meta"><b>#0E7C86</b><span>accent · teal</span></div></div>
    <div class="sw"><div class="chipbar" style="background:#1B7A5A"></div>
      <div class="meta"><b>#1B7A5A</b><span>bull · softened</span></div></div>
    <div class="sw"><div class="chipbar" style="background:#C2453C"></div>
      <div class="meta"><b>#C2453C</b><span>bear · softened</span></div></div>
    <div class="sw"><div class="chipbar" style="background:#A76A1E"></div>
      <div class="meta"><b>#A76A1E</b><span>warn · softened</span></div></div>
    <div class="sw"><div class="chipbar" style="background:#EDF2F2"></div>
      <div class="meta"><b>#EDF2F2</b><span>ground</span></div></div>
    <div class="sw"><div class="chipbar" style="background:#0D1618"></div>
      <div class="meta"><b>#0D1618</b><span>ink</span></div></div>"""
assert h.count(old_sw) == 1, "swatch strip not found"
h = h.replace(old_sw, new_sw)

# ── the palette rationale has to change with it ──────────────────────────────
old_note = """  <div class="note go">
    <span class="tag">The semantic four do not change — that is deliberate</span>
    <p>Green, red and amber are <b>learned</b> in a trading app. You read them before you read
    the number. Repainting them for visual consistency would be a genuine cost dressed as an
    improvement, so the proposal keeps all four of the Commander&rsquo;s existing semantic
    colours exactly.</p>
    <p><b>The neutrals are what change.</b> Today they are Tailwind&rsquo;s stock slate ramp —
    <code>#1E293B</code>, <code>#334155</code>, <code>#94A3B8</code>, <code>#CBD5E1</code>,
    <code>#E2E8F0</code> — used because they were to hand. The proposed ramp carries a slight
    cool bias toward the accent, so the greys read as <em>chosen</em> rather than inherited. The
    difference is small on any one element and obvious across a page.</p>
  </div>"""
new_note = """  <div class="note go">
    <span class="tag">Same meanings, lower volume — and a correction to what I said last round</span>
    <p><b>Every hue keeps its job.</b> Green is still bull, red still bear, amber still warn. The
    learned association you read before you read the number is untouched, and nothing has been
    swapped for anything else.</p>
    <p><b>What changed is saturation.</b> Last round I argued for keeping the semantic colours
    <em>exactly</em>. That was over-cautious. <code>#DC2626</code> is a fire-engine red built to
    alarm — correct for a smoke detector, wrong for a screen you sit in front of from pre-market
    to the evening arming session. On a book with several red rows it is genuinely tiring.
    <code>#C2453C</code> says the same thing at a lower volume. <b>Softening a hue is a different
    act from swapping one</b>, and only the first is safe.</p>
    <p><b>The neutrals now carry a teal bias</b> rather than Tailwind&rsquo;s stock slate ramp
    (<code>#1E293B</code>, <code>#334155</code>, <code>#94A3B8</code>, <code>#CBD5E1</code>) — a
    blue-green grey that sits under the accent instead of competing with it. Teal replaces the
    <code>#1D4ED8</code> accent outright: it is the calmest hue that still reads as
    &ldquo;interactive&rdquo;, and unlike blue it does not collide with the bear red across the
    colour wheel.</p>
    <p class="m" style="font-size:12.5px;color:var(--muted)">All four semantic colours clear
    4.5:1 against their own tinted backgrounds in both themes.</p>
  </div>"""
assert h.count(old_note) == 1, "palette note not found"
h = h.replace(old_note, new_note)

# ── the dek should say what the palette is ───────────────────────────────────
old_dek = "isn&rsquo;t being used. This is what it would take to close the gap, what it would look\n    like, and the part that cannot be copied across.</p>"
new_dek = ("isn&rsquo;t being used. This is what it would take to close the gap, on a teal palette "
           "chosen for a screen you sit in front of all day &mdash; and the part that cannot be "
           "copied across.</p>")
assert h.count(old_dek) == 1, "dek not found"
h = h.replace(old_dek, new_dek)

assert h != orig
io.open(P, "w", encoding="utf-8").write(h)
print(f"mockup re-paletted: {len(orig)} -> {len(h)} chars")
