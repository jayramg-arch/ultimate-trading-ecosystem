# -*- coding: utf-8 -*-
"""
commander_watchlists.py — the ONE list of Commander watchlists, and the RRG Studio sync.

13-Sep-2026: Strike.Money lapsed (Jay is not renewing). Every watchlist the pipeline
used to PUSH to Strike (strike_automation.py, now in _archive/strike_money/) is
consumed by the in-house RRG Studio instead. RRG Studio is local, so there is
nothing to upload: it reads Generated_Watchlists/LATEST_<base>.txt — the same
files TradingView gets, so the two surfaces cannot disagree.

What "sync" means now:
  1. the base-name list lives HERE (it was a private copy inside strike_automation;
     RRG Studio had its own 9-entry subset — two copies, and the Studio was missing
     eight of the lists Strike received);
  2. build_manifest() writes rrg_studio/commander_screeners.json — every list with
     its symbols, source file, mtime and a fresh flag — so the Studio shows the
     COMPLETE set with its own date, and the pipeline can WARN on empty/stale lists
     the way the Strike phase used to;
  3. RRG Studio reads the manifest first and falls back to scanning the TXTs.

Run by auto-pilot Phase 6, by the Watchlist page's "Sync to RRG Studio" button, or:
    python commander_watchlists.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from typing import Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
WATCHLIST_DIR = os.path.join(HERE, "Generated_Watchlists")
MANIFEST_PATH = os.path.join(HERE, "rrg_studio", "commander_screeners.json")

# base name -> RRG Studio title. Order = display order in the Studio dropdown.
# Base names MUST match watchlist_manager.py WATCHLIST_MAP values (the TXT stems).
WATCHLISTS: List[Tuple[str, str]] = [
    ("Bull_Hunter",                 "🎯 Bull Hunter Picks"),
    ("Bull_Pullback",               "🌊 Bull Pullback Picks"),
    ("Bull_EarlyBird",              "🐣 Bull EarlyBird Picks"),
    ("Bull_StrongLeader",           "💪 Strong Leaders"),
    ("Bull_Picks_All",              "🐂 Bull Picks — all"),
    ("Catalyst_Watchlist",          "🔥 Catalyst Watchlist"),
    ("Golden_Matcher_Picks",        "🪙 Golden Matcher Picks"),
    ("Golden_Matcher_Board",        "🪙 Golden Matcher Board"),
    ("XRay_Picks",                  "🧬 X-Ray Picks"),
    ("Rec_Early_Bird",              "🌱 Recovery EarlyBird"),
    ("Rec_RS_Survivor",             "🛡️ Recovery RS Survivor"),
    ("Rec_Climax_Bounce",           "💥 Recovery Climax Bounce"),
    ("Recovery_Picks_All",          "🩹 Recovery Picks — all"),
    ("Recovery_Catalyst_Watchlist", "🔥 Recovery Catalyst Watchlist"),
    ("Bull_Screener",               "📡 Bull Screener"),
    ("Bull_Screener_Custom",        "📡 Bull Screener — custom"),
    ("Portfolio",                   "💼 Current Portfolio"),
]
WATCHLIST_BASE_NAMES = [b for b, _ in WATCHLISTS]
# The portfolio TXT is written lower-case by watchlist_manager; both spellings are tried.
_ALIASES = {"Portfolio": ["Portfolio_Current", "portfolio", "Portfolio"]}
STALE_HOURS = 30   # a LATEST_ file older than this is last session's list, say so


def _clean(sym: str) -> str:
    return sym.strip().replace("NSE:", "").replace("BSE:", "").replace(".NS", "").upper()


def load_latest(base: str) -> Tuple[List[str], str | None, float | None]:
    """(symbols, path, mtime) for LATEST_<base>.txt; ([], None, None) when absent."""
    for name in _ALIASES.get(base, [base]):
        p = os.path.join(WATCHLIST_DIR, f"LATEST_{name}.txt")
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as fh:
                    syms = [_clean(l) for l in fh if l.strip() and not l.startswith("#")]
                seen, out = set(), []
                for s in syms:
                    if s and s not in seen:
                        seen.add(s); out.append(s)
                return out, p, os.path.getmtime(p)
            except Exception:
                return [], p, None
    return [], None, None


def build_manifest() -> Dict:
    """Read every list, write the manifest, return it (with a summary block)."""
    now = dt.datetime.now()
    lists, empty, stale, missing = {}, [], [], []
    for base, title in WATCHLISTS:
        syms, path, mtime = load_latest(base)
        age_h = (now.timestamp() - mtime) / 3600.0 if mtime else None
        fresh = age_h is not None and age_h <= STALE_HOURS
        if path is None:
            missing.append(base)
        elif not syms:
            empty.append(base)
        elif not fresh:
            stale.append(base)
        lists[base] = {
            "title": title,
            "symbols": syms,
            "count": len(syms),
            "source": os.path.basename(path) if path else None,
            "as_of": dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M") if mtime else None,
            "fresh": fresh,
        }
    manifest = {
        "written": now.strftime("%Y-%m-%d %H:%M"),
        "source_dir": WATCHLIST_DIR,
        "lists": lists,
        "summary": {
            "total": len(WATCHLISTS),
            "populated": sum(1 for v in lists.values() if v["count"]),
            "empty": empty, "stale": stale, "missing": missing,
        },
    }
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    tmp = MANIFEST_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, MANIFEST_PATH)
    return manifest


def read_manifest() -> Dict | None:
    try:
        with open(MANIFEST_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def sync(verbose: bool = True) -> Dict:
    """The pipeline / button entry point. Returns the manifest summary."""
    m = build_manifest()
    s = m["summary"]
    if verbose:
        print(f"   [RRG Studio sync] {s['populated']}/{s['total']} lists populated -> "
              f"{os.path.relpath(MANIFEST_PATH, HERE)}")
        for base, v in m["lists"].items():
            flag = "" if v["fresh"] else ("  (STALE " + str(v["as_of"]) + ")" if v["as_of"] else "  (missing)")
            print(f"      {v['title']:<34} {v['count']:>4}{flag}")
        if s["empty"]:
            print(f"      [!] empty: {', '.join(s['empty'])}")
        if s["stale"]:
            print(f"      [!] stale: {', '.join(s['stale'])}")
        if s["missing"]:
            print(f"      [!] missing: {', '.join(s['missing'])}")
    return s


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    sync()
