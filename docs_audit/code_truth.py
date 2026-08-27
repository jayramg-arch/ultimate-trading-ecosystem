"""Extract the values the Commander Library documents CLAIM, straight from the code.

Read the code, not the notes. CLAUDE.md is itself a document that drifts -- this
session already found two places where it disagreed with the source it describes.
Every fact below records the file and the line it came from so a disagreement can be
settled by opening that line rather than by argument.
"""
import io
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = r"C:\Users\jayra\Documents\GeminiVSCode"


def read(name):
    p = os.path.join(ROOT, name)
    return io.open(p, encoding="utf-8", errors="replace").read()


def first(pat, text, group=1, flags=0):
    m = re.search(pat, text, flags)
    return m.group(group) if m else None


def v67_file():
    return [f for f in os.listdir(ROOT) if "v67" in f and f.endswith(".pine")][0]


F = {}

# ── versions ──────────────────────────────────────────────────────────────────
s4 = read("Section4_Entry_Trigger_v7.2.pine")
core = read("S4Core.pine")
uni = read("Weinstein_Unified_Ecosystem_v3.4.pine")
v67n = v67_file()
v67 = read(v67n)

F["s4_title"] = first(r'indicator\("([^"]+)"', s4)
F["s4_file"] = "Section4_Entry_Trigger_v7.2.pine"
F["s4_core_import"] = first(r"import jayramg/S4Core/(\d+)", s4)
F["unified_title"] = first(r'strategy\("([^"]+)"', uni)
F["unified_file"] = "Weinstein_Unified_Ecosystem_v3.4.pine"
F["v67_title"] = first(r'indicator\("([^"]+)"', v67)
F["v67_file"] = v67n

# ── S4 panel geometry ─────────────────────────────────────────────────────────
F["panel_rows"] = first(r"^int PANEL_ROWS = (\d+)", s4, flags=re.M)
rows = {}
for line in s4.split("\n"):
    if line.lstrip().startswith("//"):
        continue
    m = re.search(r'\bf_row\(\s*(\d+),\s*(?:"([^"]*)"|([A-Za-z_]\w*))', line)
    if m:
        rows[int(m.group(1))] = (m.group(2) or "<" + m.group(3) + ">").strip()
    m = re.search(r'\bf_sec\(\s*(\d+),\s*"([^"]*)"', line)
    if m:
        rows[int(m.group(1))] = "SECTION: " + m.group(2).strip()
F["panel_order"] = [f"{k}:{v}" for k, v in sorted(rows.items())]

# ── location gate ─────────────────────────────────────────────────────────────
web = read("weinstein_commander_web_v4.0.py")
ze = read("zone_engine.py")
for k, pat, src in [
    ("GM_LOC_STRICT", r"^GM_LOC_STRICT\s*=\s*(\w+)", web),
    ("GM_PIVOT_NEEDS_CONFLUENCE", r"^GM_PIVOT_NEEDS_CONFLUENCE\s*=\s*(\w+)", web),
    ("GM_USE_IZE_ZONES", r"^GM_USE_IZE_ZONES\s*=\s*(\w+)", web),
    ("INHERIT_QUALIFICATION", r"^INHERIT_QUALIFICATION\s*=\s*(\w+)", web),
    ("TESTED_TRAVEL_ATR", r"^TESTED_TRAVEL_ATR\s*=\s*([\d.]+)", ze),
    ("APPROACH_ATR", r"^APPROACH_ATR\s*=\s*([\d.]+)", ze),
    ("TOUCH_TOL_WIDTH", r"^TOUCH_TOL_WIDTH\s*=\s*([\d.]+)", ze),
    ("DEMAND_STRONG_SCORE", r"^DEMAND_STRONG_SCORE\s*=\s*(\d+)", ze),
    ("KEEP_TESTED_DEMAND", r"^KEEP_TESTED_DEMAND\s*=\s*(\w+)", ze),
]:
    F[k] = first(pat, src, flags=re.M)

F["s4_useStructural_default"] = first(r"useStructural\s*=\s*input\.bool\((\w+)", s4)
F["s4_loc_pivot_needs_conf"] = first(r"loc_pivot_needs_confluence\s*=\s*input\.bool\((\w+)", s4)
F["s4_tested_tf_match"] = first(r"tested_tf_match\s*=\s*input\.bool\((\w+)", s4)
F["s4_testedTravelMode"] = first(r'testedTravelMode\s*=\s*input\.string\("(\w+)"', s4)

# ── targets / R-canon ─────────────────────────────────────────────────────────
bs = read("bull_screener.py")
for k in ("POS_T1_R", "POS_T2_R", "SWG_T1_R", "SWG_T2_R"):
    F[k] = first(rf"^{k}\s*=\s*float\(_os_t1\.getenv\('{k}',\s*'([\d.]+)'", bs, flags=re.M)

# ── replay / validation ───────────────────────────────────────────────────────
rp = read("replay.py")
F["replay_LOCATION_RULE"] = first(r'^LOCATION_RULE\s*=\s*"(\w+)"', rp, flags=re.M)
F["replay_STRUCTURAL_SL"] = first(r"^STRUCTURAL_SL\s*=\s*(\w+)", rp, flags=re.M)
F["replay_entry_mode_default"] = first(r'entry_mode[^=]*=\s*"(\w+)"', rp)
try:
    F["LAST_RUN"] = read(os.path.join("validation_runs", "LAST_RUN.txt")).strip().split("\n")[0]
except Exception:
    F["LAST_RUN"] = None

# ── sector map ────────────────────────────────────────────────────────────────
F["sector_map_present"] = "export sectorOf" in core
m = re.search(r"on 26-Aug-2026: (\d+) symbols, (\d+) sectors", core)
F["sector_symbols"] = m.group(1) if m else None
F["sector_count"] = m.group(2) if m else None

# ── plot budgets ──────────────────────────────────────────────────────────────
def plots(text):
    return len(re.findall(r"^(?:plot|plotshape|plotchar|plotcandle|alertcondition|hline)\(", text, re.M))


F["v67_plots"] = plots(v67)
F["unified_plots"] = plots(uni)
F["s4_plots"] = plots(s4)

# ── v67 exports (the S4 binding channel) ──────────────────────────────────────
F["v67_s4_exports"] = re.findall(r'title="(s4_\w+)"', v67)
F["bind_map_entries"] = re.findall(r'\["v67",\s*"(s4_\w+)"\]', read("tv_bind_s4_sources.js"))

# ── catalyst families the screener can emit ───────────────────────────────────
F["catalysts"] = sorted(set(re.findall(r'"(POS-[A-Z]+|SWG-[A-Z]+|REV-[A-Z]+|WYC-[A-Z]+)"', bs)))

out = os.path.join(ROOT, "docs_audit", "code_truth.json")
io.open(out, "w", encoding="utf-8").write(json.dumps(F, indent=2, ensure_ascii=False))
for k, v in F.items():
    if isinstance(v, list) and len(v) > 8:
        print(f"{k:32} [{len(v)}] {v[:6]} ...")
    else:
        print(f"{k:32} {v}")
print(f"\nwritten -> {out}")
