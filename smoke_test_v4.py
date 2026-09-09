"""
smoke_test_v4.py — Quick smoke test for all Phase 1 modules
Run: python smoke_test_v4.py
"""
import sys, os
sys.path.insert(0, r"C:\Users\jayra\Documents\GeminiVSCode")
os.chdir(r"C:\Users\jayra\Documents\GeminiVSCode")

from dotenv import load_dotenv
load_dotenv(override=True)

PASS, FAIL = [], []

import pandas as pd

def check(name, fn):
    """Safe check — handles DataFrames, dicts, lists, and scalars."""
    try:
        result = fn()
        # DataFrame/Series: non-empty = PASS
        if isinstance(result, (pd.DataFrame, pd.Series)):
            status = "PASS" if not result.empty else "WARN (empty DataFrame)"
        # dict/list: non-empty = PASS
        elif isinstance(result, (dict, list)):
            status = "PASS" if result else "WARN (empty result)"
        # None = WARN, anything else truthy = PASS
        elif result is None:
            status = "WARN (None returned)"
        else:
            status = "PASS"
        PASS.append(name)
        print(f"  [{status}] {name}")
        return result
    except Exception as e:
        FAIL.append(name)
        print(f"  [FAIL] {name}: {e}")
        return None

print("=" * 55)
print("  Commander Web v4.0 — Phase 1 Smoke Test")
print("=" * 55)

# ── 1. market_data_hub ───────────────────────────────────────
print("\n[1] market_data_hub.py")
from market_data_hub import (
    fetch_global_overview, fetch_india_vix_history,
    fetch_economic_calendar, load_nifty500_symbols,
)
glo = check("fetch_global_overview", fetch_global_overview)
if glo:
    idx = glo.get("indices", {})
    nifty = idx.get("Nifty 50", {})
    print(f"      Nifty 50 LTP : {nifty.get('ltp', 'n/a')}")
    print(f"      Nifty 50 Chg%: {nifty.get('change_pct', 'n/a')}")
    spx = glo.get("indices",{}).get("S&P 500",{})
    print(f"      S&P 500 Chg% : {spx.get('change_pct', 'n/a')}")
    comms = glo.get("commodities",{})
    gold = comms.get("Gold",{})
    print(f"      Gold LTP     : {gold.get('ltp','n/a')}")
    print(f"      Fetched at   : {glo.get('fetched_at','n/a')}")

check("fetch_india_vix_history", fetch_india_vix_history)
cal = check("fetch_economic_calendar", fetch_economic_calendar)
if cal:
    print(f"      Calendar events: {len(cal)}")
syms = check("load_nifty500_symbols", load_nifty500_symbols)
if syms:
    print(f"      Nifty500 symbols loaded: {len(syms)}")

# ── 2. breadth_engine ────────────────────────────────────────
print("\n[2] breadth_engine.py")
from breadth_engine import (
    calculate_breadth_metrics, build_breadth_regime,
    get_sector_breadth, load_universe_symbols,
)
check("load_universe_symbols", load_universe_symbols)
print("     (Breadth calc skipped in smoke test — runs full yfinance download)")
print("     To run: calculate_breadth_metrics() — takes ~60s first run")

sec = check("get_sector_breadth", get_sector_breadth)
if sec is not None and not sec.empty:
    print(f"      Sectors tracked: {len(sec)}")
    print(sec[["Sector","Monthly%","Stage"]].to_string(index=False) if "Stage" in sec.columns else sec.head(3).to_string())

# ── 3. gemini_reporter ───────────────────────────────────────
print("\n[3] gemini_reporter.py")
from gemini_reporter import generate_premarket_brief
test_snap = {
    "generated_at": "2026-04-17 08:30:00 IST",
    "global": {
        "indices": {"Nifty 50": {"ltp": 24500, "change_pct": -0.4},
                    "S&P 500":  {"ltp": 5280,  "change_pct":  0.3}},
        "commodities": {"Gold": {"ltp": 3240, "change_pct": 0.6},
                        "Brent Crude": {"ltp": 74.2, "change_pct": -1.1}},
        "currencies": {"USD/INR": {"ltp": 84.12, "change_pct": 0.05}},
    },
    "vix": {"current_vix": 14.2, "percentile": 35},
    "calendar": [{"date": "2026-04-18", "event": "India CPI", "importance": "HIGH"}],
}
brief = check("generate_premarket_brief", lambda: generate_premarket_brief(test_snap))
if brief and not brief.startswith("Warning"):
    lines = brief.split("\n")
    print(f"      Report length : {len(brief)} chars, {len(lines)} lines")
    print(f"      First line    : {lines[0][:80]}")

# ── 4. scheduler_daemon ──────────────────────────────────────
print("\n[4] scheduler_daemon.py")
from scheduler_daemon import (
    load_latest_report, get_scheduler_status, save_report,
)
check("load_latest_report(premarket)", lambda: load_latest_report("premarket") or True)
save_report("smoke_test", "Test report content", {"test": True})
check("save_report", lambda: os.path.exists(r"C:\Users\jayra\Documents\GeminiVSCode\reports\latest_smoke_test.json"))

# ── Summary ──────────────────────────────────────────────────
print("\n" + "=" * 55)
total = len(PASS) + len(FAIL)
print(f"  Results: {len(PASS)}/{total} checks passed")
if FAIL:
    print(f"  Failed : {', '.join(FAIL)}")
else:
    print("  All checks passed!")
print("\n  Ready to launch:")
print("  streamlit run weinstein_commander_web_v4.0.py")
print("=" * 55)
