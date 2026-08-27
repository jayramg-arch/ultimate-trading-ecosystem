"""Nightly guard: tell me when the CODE moves under the documentation.

The Commander Library went stale silently. Nothing was wrong with the pages when they
were written -- the code changed underneath them, and nobody was watching the gap. A
one-off audit fixes the backlog and does nothing about the next one.

So this snapshots the same facts code_truth.py extracts, diffs them against the last
run, and reports only what MOVED, together with the pages that cite it. Staleness
becomes an alert instead of a discovery.

Deliberately does NOT edit anything. It reports; a human decides whether the doc
needs to change or whether the code change was the mistake -- both have happened.

Run:  python docs_audit/truth_watch.py            (report; exit 1 if anything moved)
      python docs_audit/truth_watch.py --accept   (adopt current state as the baseline)
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TRUTH = os.path.join(HERE, "code_truth.json")
BASE = os.path.join(HERE, "truth_baseline.json")

# Which page cites which fact. Kept by hand because it encodes a judgement -- "this
# document would be WRONG if this value changed" -- that no scanner can infer.
CITED_BY = {
    # ── the 27-Aug cross-module pairs ──
    # These are watched in PAIRS on purpose. Each is a number that two modules
    # answer independently, so the failure mode is not "a value went stale" but
    # "one of two values moved and the other did not". If either side of a pair
    # moves, re-read BOTH pages before editing: the gap may have been closed, or
    # it may have widened.
    "rev_screener_t1_r": ["09 Quality on Sale", "18 Trade Funnel"],
    "rev_canon_t1_r": ["09 Quality on Sale", "18 Trade Funnel", "10 Position Sizer"],
    "rff_min_score": ["09 Quality on Sale", "25* Scanner Filter Map"],
    "cb_lookback_high_days": ["09 Quality on Sale", "25* Scanner Filter Map"],
    "cb_drawdown_band": ["09 Quality on Sale", "25* Scanner Filter Map"],
    "stock_correction_min": ["09 Quality on Sale", "25* Scanner Filter Map"],
    "sector_db_rows": ["21 RS / Auto-Sector"],
    "choch_window": ["02 Wyckoff", "15 Context Layers"],

    "s4_title": ["22 Section Four"],
    "s4_core_import": ["22 Section Four"],
    "v67_title": ["08 Swing Pro Dashboard", "22 Section Four"],
    "unified_title": ["13 Unified Ecosystem"],
    "panel_rows": ["22 Section Four"],
    "panel_order": ["22 Section Four"],
    "GM_LOC_STRICT": ["23 Golden Matcher", "25 Golden Rules"],
    "GM_PIVOT_NEEDS_CONFLUENCE": ["23 Golden Matcher", "25 Golden Rules", "22 Section Four"],
    "GM_USE_IZE_ZONES": ["23 Golden Matcher"],
    "INHERIT_QUALIFICATION": ["23 Golden Matcher"],
    "TESTED_TRAVEL_ATR": ["22 Section Four", "04 Institutional Footprint"],
    "APPROACH_ATR": ["22 Section Four", "23 Golden Matcher"],
    "TOUCH_TOL_WIDTH": ["04 Institutional Footprint"],
    "DEMAND_STRONG_SCORE": ["22 Section Four", "04 Institutional Footprint"],
    "KEEP_TESTED_DEMAND": ["22 Section Four", "25 Golden Rules"],
    "s4_useStructural_default": ["22 Section Four", "23 Golden Matcher"],
    "s4_tested_tf_match": ["22 Section Four"],
    "s4_testedTravelMode": ["22 Section Four"],
    "POS_T1_R": ["10 Position Sizer", "11 Catalyst Engine", "13 Unified Ecosystem", "18 Trade Funnel"],
    "POS_T2_R": ["10 Position Sizer", "11 Catalyst Engine", "13 Unified Ecosystem", "18 Trade Funnel"],
    "SWG_T1_R": ["10 Position Sizer", "11 Catalyst Engine"],
    "SWG_T2_R": ["10 Position Sizer", "11 Catalyst Engine"],
    "replay_LOCATION_RULE": ["27 Backtest Court", "16 Honesty Layer"],
    "replay_STRUCTURAL_SL": ["27 Backtest Court"],
    "replay_entry_mode_default": ["27 Backtest Court", "22 Section Four", "25 Golden Rules"],
    "LAST_RUN": ["16 Honesty Layer", "27 Backtest Court"],
    "sector_symbols": ["22 Section Four", "21 RS / Auto-Sector"],
    "v67_s4_exports": ["08 Swing Pro Dashboard", "22 Section Four"],
    "bind_map_entries": ["22 Section Four"],
    "catalysts": ["11 Catalyst Engine", "13 Unified Ecosystem", "18 Trade Funnel"],
}


def refresh():
    r = subprocess.run([sys.executable, os.path.join(HERE, "code_truth.py")],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print("[X] code_truth.py failed:\n" + (r.stderr or "")[-800:])
        sys.exit(2)
    return json.load(io.open(TRUTH, encoding="utf-8"))


def main():
    cur = refresh()
    if "--accept" in sys.argv or not os.path.exists(BASE):
        io.open(BASE, "w", encoding="utf-8").write(json.dumps(cur, indent=2, ensure_ascii=False))
        print(f"baseline written: {len(cur)} facts")
        return 0

    old = json.load(io.open(BASE, encoding="utf-8"))
    moved = []
    for k in sorted(set(old) | set(cur)):
        a, b = old.get(k), cur.get(k)
        if a != b:
            moved.append((k, a, b))

    if not moved:
        print(f"OK — all {len(cur)} facts unchanged since the baseline")
        return 0

    print("=" * 74)
    print(f"  CODE MOVED UNDER THE DOCS — {len(moved)} fact(s)")
    print("=" * 74)
    pages = set()
    for k, a, b in moved:
        def short(v):
            s = json.dumps(v, ensure_ascii=False)
            return s if len(s) <= 60 else s[:57] + "…"
        cites = CITED_BY.get(k, [])
        pages.update(cites)
        print(f"\n  {k}")
        print(f"     was: {short(a)}")
        print(f"     now: {short(b)}")
        print(f"     cited by: {', '.join(cites) if cites else '(no page mapped — add one to CITED_BY)'}")
    print("\n" + "-" * 74)
    print("PAGES TO RE-CHECK: " + (", ".join(sorted(pages)) if pages else "none mapped"))
    print("Run docs_audit/rank_pages.py, fix, then re-run with --accept to re-baseline.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
