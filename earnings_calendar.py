"""earnings_calendar.py — next earnings date per symbol, for the ladder and the reviewer.

22-Sep-2026. `pyramid_logic.classify()` has carried an "earnings within 3 days -> TRIM"
rung since 7-Jul and it has been **silent the whole time**: the rung is guarded, and
nothing ever fed it a date. A position walking into its results print at full size is
exactly the avoidable loss that rung was written for.

WHY yfinance AND NOT THE TRADINGVIEW MCP. The ladder runs HEADLESS - inside the 16:30
pipeline and inside Risk Shield - and a headless job cannot call an MCP server; MCP tools
exist only inside a Claude session. The TradingView connector is also rate-limited in beta
(429 after a handful of calls, measured 22-Sep) and routed NSE symbols at the /america/
scanner on the earnings endpoint. So the feed is yfinance, which is already the documented
fundamentals fallback here, works from cron, and answers for NSE names:
    BAJFINANCE 2026-11-16 · COALINDIA 2026-10-29 (both accessors agree).
The connector stays useful as an occasional cross-check, not as the source.

MISSING IS NEVER ZERO. A name with no date returns None and the caller must treat that as
"unknown", never as "no earnings soon" - the whole point of the rung is the day it lands.
NAM-INDIA legitimately has no date on yfinance today; it must not read as safe.

    python earnings_calendar.py              refresh the cache for the open book
    python earnings_calendar.py --symbols A,B
    python earnings_calendar.py --show       print what is cached
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import warnings
import journal_path as _jp  # AUD-INT-14: one owner of the journal location

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "earnings_dates.json")
STALE_DAYS = 3          # a date fetched more than this long ago is re-fetched


def _canon(sym: str) -> str:
    s = str(sym).upper().strip().replace("NSE:", "")
    return s.replace("_", "-")          # TV spells NAM-INDIA as NAM_INDIA


def load() -> dict:
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(d: dict) -> None:
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1, sort_keys=True)
    os.replace(tmp, CACHE)


def _fetch_one(sym: str) -> str | None:
    """Next earnings date at or after today, ISO, or None. Two accessors: `calendar`
    is the cheap one; `get_earnings_dates` is the fallback when it comes back empty."""
    import pandas as pd
    import yfinance as yf
    t = yf.Ticker(_canon(sym) + ".NS")
    today = dt.date.today()
    try:
        cal = t.calendar
        vals = cal.get("Earnings Date") if isinstance(cal, dict) else None
        for v in (vals or []):
            d = v if isinstance(v, dt.date) else pd.to_datetime(v).date()
            if d >= today:
                return d.isoformat()
    except Exception:
        pass
    try:
        df = t.get_earnings_dates(limit=12)
        if df is not None and len(df):
            idx = pd.to_datetime(df.index).tz_localize(None)
            fut = [d.date() for d in idx if d.date() >= today]
            if fut:
                return min(fut).isoformat()
    except Exception:
        pass
    return None


def refresh(symbols: list[str], force: bool = False) -> dict:
    cache = load()
    today = dt.date.today().isoformat()
    for s in symbols:
        k = _canon(s)
        row = cache.get(k) or {}
        if not force and row.get("checked"):
            age = (dt.date.today() - dt.date.fromisoformat(row["checked"])).days
            if age < STALE_DAYS:
                continue
        cache[k] = {"date": _fetch_one(k), "checked": today}
    _save(cache)
    return cache


def next_earnings(sym: str) -> str | None:
    """ISO date or None. Read-only: never fetches, so it is safe inside a per-row loop."""
    row = load().get(_canon(sym)) or {}
    d = row.get("date")
    if not d:
        return None
    try:
        return d if dt.date.fromisoformat(d) >= dt.date.today() else None
    except Exception:
        return None


def days_to_earnings(sym: str) -> int | None:
    d = next_earnings(sym)
    if not d:
        return None
    return (dt.date.fromisoformat(d) - dt.date.today()).days


def note(sym: str) -> str:
    """One phrase for a panel/review line. '' when unknown - never 'no earnings'."""
    n = days_to_earnings(sym)
    if n is None:
        return ""
    if n == 0:
        return "earnings TODAY"
    if n == 1:
        return "earnings TOMORROW"
    return "earnings in %dd (%s)" % (n, next_earnings(sym))


def open_positions() -> list[str]:
    import sqlite3
    try:
        c = sqlite3.connect(_jp.JOURNAL_DB)
        return sorted({r[0] for r in c.execute(
            "SELECT DISTINCT symbol FROM journal WHERE UPPER(status)='OPEN'") if r[0]})
    except Exception as e:
        print("journal unreadable: %s" % e, file=sys.stderr)
        return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", help="comma-separated; default = the open book")
    ap.add_argument("--force", action="store_true", help="re-fetch even if freshly cached")
    ap.add_argument("--show", action="store_true", help="print the cache and exit")
    a = ap.parse_args()
    os.chdir(HERE)
    if a.show:
        c = load()
        for k in sorted(c):
            print("%-14s %s  (checked %s)" % (k, c[k].get("date") or "—", c[k].get("checked")))
        print("%d symbols cached" % len(c))
        return 0
    syms = [s.strip() for s in a.symbols.split(",")] if a.symbols else open_positions()
    if not syms:
        print("no symbols", file=sys.stderr)
        return 1
    c = refresh(syms, a.force)
    known = [s for s in syms if (c.get(_canon(s)) or {}).get("date")]
    print("%d symbols · %d with a date · %d unknown -> %s"
          % (len(syms), len(known), len(syms) - len(known), os.path.relpath(CACHE, HERE)))
    for s in sorted(syms, key=lambda x: (days_to_earnings(x) is None, days_to_earnings(x) or 0)):
        n = days_to_earnings(s)
        if n is not None and n <= 14:
            print("   %-14s %s" % (_canon(s), note(s)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
