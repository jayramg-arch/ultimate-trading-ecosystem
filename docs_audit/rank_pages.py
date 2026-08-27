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
    ("positional 5R/10R", r"\b5R\s*/\s*10R\b|\bT1\s*=\s*5R\b"),
    ("positional 2R/4R", r"positional[^.]{0,40}\b2R\s*/\s*4R\b"),
    ("stale milestone +2.56%", r"\+2\.56%"),
    ("stale LAST_RUN", r"2026(?:0722_135745|0726_225547|0723_06\d{4})"),
    ("v67 old version", r"v67\.4\.(?:0\d|1\d|20)\b"),
    ("S4Core old version", r"S4Core/(?:1\d|2[0-3])\b"),
    ("Unified v3.4", r"Unified[^.]{0,24}v3\.4(?!\d)"),
    ("five panel bands", r"five bands|five sections|five panel"),
    ("tested zone deleted", r"tested zone is deleted|tested\s*→\s*(?:deleted|violated)\b"),
    # Must not match the INPUT NAMED "Tested rules 2 & 3: Daily zones only", which is
    # followed by the correct explanation -- a false positive here sends me rewriting
    # text that is already right.
    ("EMA rule daily-only", r"(?<!: )(?<!:)only DAILY zones|rules?[^.]{0,30}apply only to daily"),
    ("geometry live in S4", r"geometry classifier(?![^.]{0,40}removed)"),
    ("buy-stop default", r"default[^.]{0,30}buy-?stop"),
    ("Strike RRG live", r"Strike RRG[^.]{0,30}(?:paste|panel|row)"),
    ("matched = design window", r"benchmark[^.]{0,50}(?:design|full) window"),
]

# Things the code now does. Absence is a gap, not an error -- hence the lighter weight.
MISSING = [
    ("ML win probability", r"ML win prob"),
    ("REACTING location", r"REACTING|reacting off"),
    ("rule A2 / pivot confluence", r"rule A2|pivot[^.]{0,30}confluence"),
    ("sector map", r"sector map|curated sector|sectors\.db"),
    ("pivot master switch", r"pivot[^.]{0,40}(?:master switch|toggle)"),
    ("Momentum & value row", r"Momentum &amp; value|Momentum & value|CPR pivot"),
    ("location A/B null", r"location[^.]{0,40}(?:null|A/B)"),
]


LOCAL = {"6b9eef4f": "22_section_four.html"}


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
    con = [n for n, p in CONTRADICT if re.search(p, t, re.I)]
    mis = [n for n, p in MISSING if not re.search(p, t, re.I)]
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
