"""Test one Commander Library page against code_truth.json.

Usage:  python docs_audit/check_page.py <artifact-id-fragment>

Reports only CONTRADICTIONS -- a claim the code disproves -- plus a short list of
claims that merely look dated and want a human eye. It deliberately does not grade
prose: the audit is about facts that have moved, not style.
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from artifact_tools import content, text_of  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = r"C:\Users\jayra\Documents\GeminiVSCode"
F = json.load(io.open(os.path.join(ROOT, "docs_audit", "code_truth.json"), encoding="utf-8"))

# (label, regex, why it is wrong now)
CONTRADICTIONS = [
    ("S4 version", r"\bv(?:9\.\d+|8\.\d+|7\.\d+|6\.\d+|5\.\d+|4\.\d+)\b(?=[^%]{0,40}(?:S4|Section ?4|Entry Trigger))",
     f"S4 is now {F['s4_title']}"),
    ("S4Core version", r"S4Core/(?:1\d|2[0-3])\b", f"S4 imports S4Core/{F['s4_core_import']}"),
    ("v67 version", r"v67\.4\.(?:0\d|1\d|20)\b", f"v67 is {F['v67_title']}"),
    ("Unified version", r"Unified Ecosystem[^.]{0,20}v3\.4(?!\d)", f"Unified is {F['unified_title']}"),
    ("panel height", r"\b4[23] rows\b", f"the panel is {F['panel_rows']} rows (0..{int(F['panel_rows'])-1})"),
    ("positional targets", r"\b5R\s*/\s*10R\b|\bT1\s*=\s*5R\b|\b10R\b",
     f"POS targets are {F['POS_T1_R']}R / {F['POS_T2_R']}R"),
    ("positional targets 2/4", r"positional[^.]{0,40}\b2R\s*/\s*4R\b",
     f"POS targets are {F['POS_T1_R']}R / {F['POS_T2_R']}R (2R/4R was an interim)"),
    ("IZE flag off", r"GM_USE_IZE_ZONES[^.]{0,60}(?:False|off|not yet|pending)",
     "GM_USE_IZE_ZONES is True"),
    ("location = any zone", r"any fresh demand zone|a zone of any kind satisfies",
     "rule A2: a PATTERN zone stands alone, a PIVOT shelf needs a confirming source"),
    ("inside-only location", r"price (?:must be |is )inside (?:a|the) (?:fresh )?(?:demand )?zone",
     "a zone REACTED off also satisfies location (26-Aug)"),
    ("EMA/pivot rule daily-only", r"(?:daily zones only|only DAILY zones)",
     "tested rules 2 and 3 now run on every timeframe; only the reference changes"),
    ("geometry in S4", r"geometry classifier[^.]{0,60}S4|S4[^.]{0,60}geometry classifier",
     "the geometry classifier was removed from S4 in v7.3; it lives in the S/R + Trendline Lab"),
    ("Strike RRG live", r"Strike RRG[^.]{0,40}(?:paste|row|panel)",
     "the manual Strike-RRG paste was retired; the row is commented out"),
    ("stale milestone", r"\+2\.56%", "superseded by the 26-Jul matched-horizon fix (+0.80%) and the 29-Jul re-baseline (+0.54%)"),
    ("stale LAST_RUN", r"2026(?:0722_135745|0726_225547|0723_06\d+)",
     f"LAST_RUN is {F['LAST_RUN']}"),
    ("buystop default", r"default[^.]{0,40}buy-?stop", f"replay entry_mode defaults to {F['replay_entry_mode_default']}"),
]

WATCH = [
    ("ML win probability", r"ML win prob"),
    ("sector", r"\bsector\b"),
    ("pivot zones", r"pivot (?:zone|shelf)"),
    ("Wyckoff", r"Wyckoff"),
    ("row numbers", r"\brow \d+\b"),
]


def main(stub):
    html = content(stub)
    txt = text_of(html)
    print(f"=== {stub} === {len(html)} chars, {len(txt)} visible")
    hits = 0
    for label, pat, why in CONTRADICTIONS:
        for m in re.finditer(pat, txt, re.I):
            a = max(0, m.start() - 70)
            print(f"  [X] {label}: …{txt[a:m.end()+70]}…")
            print(f"      -> {why}")
            hits += 1
            break
    if not hits:
        print("  no automatic contradictions")
    print("  watch:", ", ".join(f"{l}={len(re.findall(p, txt, re.I))}" for l, p in WATCH))
    return hits


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1]) == 0 else 1)
