"""Rank the Commander Library pages by how much the code has moved under them.

The point is to order the remaining work by EVIDENCE rather than by guess. A page
that describes mathematics (a pivot definition, a Wyckoff event) can be years old and
still correct; a page that describes a live gate can be stale in a week. Only the
second kind needs urgent attention, and only measurement can tell them apart.

Score = contradictions (a claim the code disproves, weight 10)
      + missing-topic hits (a thing the code now does that the page never mentions,
        weight 3 -- lighter, because absence is not error)

Reads the saved artifact copies; run the Artifact read for each page first.
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from artifact_tools import TOOLRES, content, text_of  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = r"C:\Users\jayra\Documents\GeminiVSCode"
F = json.load(io.open(os.path.join(ROOT, "docs_audit", "code_truth.json"), encoding="utf-8"))

PAGES = {
    "bfa433a3": "25 Golden Rules", "22d57e0f": "26 Operating Loop",
    "30193746": "27 Backtest Court", "577f5e2e": "24 Pre-Trade Gate",
    "886ba1e4": "18 Trade Funnel", "33787741": "Bible", "53aee9e9": "16 Honesty Layer",
    "b733f279": "19 Performance Ledger", "bb8770c5": "23 Golden Matcher",
    "6b9eef4f": "22 Section Four", "b6b75a40": "07 Mission Control",
    "c97d2473": "08 Swing Pro Dashboard", "863499fe": "11 Catalyst Engine",
    "ae4e28ea": "09 Quality on Sale", "0aa8c4bb": "13 Unified Ecosystem",
    "5144c644": "21 RS / Auto-Sector", "48fa58a2": "25* Scanner Filter Map",
    "259f16cd": "01 Structure Engine", "d6b98046": "02 Wyckoff",
    "5613c1cc": "03 Volume Profile", "50a2b6ce": "04 Institutional Footprint",
    "79c4e8aa": "20 Markup Engine", "d52f6dcd": "15 Context Layers",
    "6682471c": "10 Position Sizer",
}

# A claim the code disproves. Kept narrow on purpose: a false positive here sends me
# rewriting prose that was already right.
CONTRADICT = [
    # Only a claim that the CURRENT targets are 5R/10R. A page citing the old
    # numbers to say they MOVED is doing the right thing.
    ("positional 5R/10R", r"(?:targets? (?:are|is)|currently|uses)[^.]{0,30}\b5R\s*/\s*10R\b"),
    # 2R/4R is the SWING canon, so "positional ... 2R/4R" is only wrong when it
    # assigns them to positional rather than contrasting the two.
    ("positional 2R/4R", r"positional[^.]{0,24}(?:targets?|T1)[^.]{0,16}\b2R\s*/\s*4R\b"),
    # Same rule: only when +2.56% is offered as the CURRENT figure.
    ("stale milestone +2.56%", r"(?:alpha (?:is|of)|edge of|delivers|currently)[^.]{0,20}\+2\.56%"),
    ("stale LAST_RUN", r"2026(?:0722_135745|0726_225547|0723_06\d{4})"),
    ("v67 old version", r"v67\.4\.(?:0\d|1\d|20)\b"),
    ("S4Core old version", r"S4Core/(?:1\d|2[0-3])\b"),
    ("Unified v3.4", r"Unified[^.]{0,24}v3\.4(?!\d)"),
    ("five panel bands", r"five bands|five sections|five panel"),
    ("tested zone deleted", r"tested zone is deleted|tested\s*→\s*(?:deleted|violated)\b"),
    # Must not match the INPUT NAMED "Tested rules 2 & 3: Daily zones only", which is
    # followed by the correct explanation -- a false positive here sends me rewriting
    # text that is already right.
    ("EMA rule daily-only", r"(?<!: )(?<!:)\bonly DAILY zones\b|rules?[^.]{0,30}apply only to daily"),
    ("geometry live in S4", r"geometry classifier(?![^.]{0,40}removed)"),
    ("buy-stop default", r"default[^.]{0,30}buy-?stop"),
    ("Strike RRG live", r"Strike RRG[^.]{0,30}(?:paste|panel|row)"),
    ("matched = design window", r"benchmark[^.]{0,50}(?:design|full) window"),
    # Was only in check_page.py, never here — a mutation test caught the omission.
    ("panel height", r"\b4[23] rows\b|panel is 4[23]\b"),
]

# Things the code now does. Absence is a gap, not an error -- hence the lighter weight.
MISSING = [
    ("ML win probability", r"ML win prob"),
    ("REACTING location", r"REACTING|reacting off"),
    ("rule A2 / pivot confluence", r"rule A2|pivot[^.]{0,30}confluence"),
    ("sector map", r"sector map|curated (?:sector|mapping)|sectors\.db"),
    ("pivot master switch", r"pivot[^.]{0,40}(?:master switch|toggle)|turning pivots off|pivot switch|pivots off in settings"),
    ("Momentum & value row", r"Momentum &amp; value|Momentum & value|CPR pivot"),
    ("location A/B null", r"pre-registered A/?B|location[^.]{0,40}(?:null|A/B)|within 0\.21 percentage"),
]


# Which page OWES which topic. Absence is only a gap where the page is the topic's
# home; everywhere else it is correct editorial scope.

# A shell heredoc once turned every \b in a pattern into a literal backspace (0x08).
# The regex stayed valid and simply never matched, so the rule looked healthy while
# catching nothing. Fail loudly instead.
for _n, _p in CONTRADICT + MISSING:
    assert not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", _p), (
        f"control character in pattern {_n!r} — a shell escape was mangled: {_p!r}")

# Words that mark a claim as HISTORY rather than an assertion. See _retired_guard.py.
_RETIRED = re.compile(
    r"retired|artifact|superseded|no longer|used to|was the old|old behaviour|"
    # "moved" removed 26-Aug: a mutation test proved it suppressed a GENUINE stale
    # claim, because ordinary prose says "moved" constantly. A retirement marker
    # has to be a word that only appears when describing history.
    r"replaced|discarded|before the fix|pre-\w+ behaviour|legacy|"
    r"versus retest|against retest|not because",
    re.I)


def _retired_context(text, match, span=220):
    """True when the match sits inside retirement language — the page is describing
    the old value, not claiming it."""
    a = max(0, match.start() - span)
    b = min(len(text), match.end() + span)
    return bool(_RETIRED.search(text[a:b]))


OWES = {
    "6b9eef4f": {"ML win probability", "REACTING location", "rule A2 / pivot confluence",
                 "sector map", "pivot master switch", "Momentum & value row",
                 "location A/B null"},                       # 22 Section Four
    # ML win probability is an S4 panel row bound from the dashboard, not a board
    # column — the board does not owe it.
    "bb8770c5": {"REACTING location", "rule A2 / pivot confluence",
                 "pivot master switch", "location A/B null"},  # 23 Golden Matcher
    "bfa433a3": {"REACTING location", "rule A2 / pivot confluence", "pivot master switch",
                 "location A/B null"},                       # 25 Golden Rules
    "30193746": {"location A/B null"},                       # 27 Backtest Court
    "53aee9e9": {"location A/B null"},                       # 16 Honesty Layer
    "c97d2473": {"ML win probability", "sector map"},        # 08 Swing Pro Dashboard
    "5144c644": {"sector map"},                              # 21 RS / Auto-Sector
    # 04 covers the SMC engine (order blocks, FVGs, sweeps, BOS) — NOT the
    # leg-base-leg zone lifecycle, which S4 owns. Assigning it those topics was a
    # scoping error on my part; it owes neither.
    "50a2b6ce": set(),                                        # 04 Inst. Footprint
    "886ba1e4": {"REACTING location"},                       # 18 Trade Funnel
    # 24 QUOTES the gates verbatim by design and never interprets them, so it owes
    # the procedural consequence of an expiring gate, not the semantics.
    "577f5e2e": set(),                                        # 24 Pre-Trade Gate
}

LOCAL = {
    "6b9eef4f": "22_section_four.html",
    "bfa433a3": "25_golden_rules.html",
    "bb8770c5": "23_golden_matcher.html",
    "6682471c": "10_position_sizer.html",
    "53aee9e9": "16_honesty_layer.html",
    "30193746": "27_backtest_court.html",
    "863499fe": "11_catalyst_engine.html",
    "0aa8c4bb": "13_unified.html",
    "c97d2473": "08_swing_pro.html",
    "50a2b6ce": "04_footprint.html",
    "886ba1e4": "18_trade_funnel.html",
    "577f5e2e": "24_pretrade_gate.html",
    "22d57e0f": "26_operating_loop.html",
    "33787741": "bible.html",
    "b733f279": "19_performance_ledger.html",
    "b6b75a40": "07_mission_control.html",
    "ae4e28ea": "09_quality_on_sale.html",
    "5144c644": "21_rs_autosector.html",
    "48fa58a2": "25s_scanner_filter_map.html",
    "259f16cd": "01_structure_engine.html",
    "d6b98046": "02_wyckoff.html",
    "5613c1cc": "03_volume_profile.html",
    "79c4e8aa": "20_markup_engine.html",
    "d52f6dcd": "15_context_layers.html",
}


def score(stub):
    """Prefer an already-updated local copy: once a page is rewritten, scoring the
    stale published snapshot would keep reporting work that is already done."""
    try:
        lp = LOCAL.get(stub)
        if lp and os.path.exists(os.path.join(ROOT, "docs_audit", "pages", lp)):
            t = text_of(io.open(os.path.join(ROOT, "docs_audit", "pages", lp), encoding="utf-8").read())
        else:
            t = text_of(content(stub))
    except Exception as e:
        return None, [], [], str(e)
    con = [n for n, p in CONTRADICT
           if any(not _retired_context(t, m) for m in re.finditer(p, t, re.I))]
    owed = OWES.get(stub, set())
    mis = [n for n, p in MISSING if n in owed and not re.search(p, t, re.I)]
    return len(con) * 10 + len(mis) * 3, con, mis, None


rows = []
for stub, name in PAGES.items():
    sc, con, mis, err = score(stub)
    rows.append((sc, name, stub, con, mis, err))

have = [r for r in rows if r[0] is not None]
missing = [r for r in rows if r[0] is None]
have.sort(key=lambda r: -r[0])

print(f"{'SCORE':>5}  {'PAGE':<28} CONTRADICTIONS / GAPS")
print("-" * 96)
for sc, name, stub, con, mis, _ in have:
    bits = []
    if con:
        bits.append("X " + ", ".join(con))
    if mis:
        bits.append("gap: " + ", ".join(mis[:4]) + ("…" if len(mis) > 4 else ""))
    print(f"{sc:>5}  {name:<28} {' | '.join(bits)[:64]}")
if missing:
    print(f"\nnot yet fetched ({len(missing)}): " + ", ".join(r[1] for r in missing))
