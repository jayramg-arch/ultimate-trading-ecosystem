"""Cross-check the scan universe against NSE's own list of listed securities.

WHY (12-Aug-2026): the 11-Aug auto-pilot flagged JBCHEPHARM as scanning on
13-session-old data. It was not a feed bug and not a symbol-mapping bug - the
security had stopped trading around 23-Jul. Four sources agreed: absent from
NSE's EQUITY_L.csv, absent from Dhan's scrip master (fresh download, no ISIN
match either), and Yahoo still serving the last traded price with volume 0.

`nifty500_symbols.json` is a static file - it was 17-Apr-2026 when this was
written, four months stale - so a delisted name keeps getting scanned until
somebody notices. This makes noticing a one-command job.

    python check_universe_listing.py            # report only
    python check_universe_listing.py --prune    # remove delisted (writes a backup)
    python check_universe_listing.py --refresh  # replace with today's Nifty 500

NSE's EQUITY_L.csv is the authority for "is it listed", not the data feed:
a feed that keeps answering is exactly how a dead instrument stays invisible.

--refresh rebuilds the universe from NSE's official ind_nifty500list.csv, so
index reconstitution (names joining, not just leaving) is picked up too. It
prints the add/drop diff and verifies every ADDED name is in EQUITY_L before
writing - an index CSV listing something the exchange does not is a reason to
stop, not to add it.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
from datetime import datetime

UNIVERSE = "nifty500_symbols.json"
EQUITY_L = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
N500_LIST = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"


def _nse_csv(url: str):
    import pandas as pd
    import requests
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0",
                      "Accept-Language": "en-US,en;q=0.9"})
    s.get("https://www.nseindia.com", timeout=20)          # cookie handshake
    r = s.get(url, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = [c.strip() for c in df.columns]
    return df


def nse_listed() -> set:
    df = _nse_csv(EQUITY_L)
    return set(df["SYMBOL"].astype(str).str.upper().str.strip())


def nifty500_constituents() -> list:
    df = _nse_csv(N500_LIST)
    return sorted(set(df["Symbol"].astype(str).str.upper().str.strip()))


def _write_universe(root: str, path: str, symbols: list, old_count: int) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    backup = os.path.join(root, "_archive", f"nifty500_symbols.backup_{stamp}.json")
    os.makedirs(os.path.dirname(backup), exist_ok=True)
    if not os.path.exists(backup):        # keep the FIRST backup of the day
        shutil.copy2(path, backup)
    json.dump(symbols, open(path, "w", encoding="utf-8"), indent=2)
    print(f"[universe] {old_count} -> {len(symbols)} | backup {backup}")
    return backup


def refresh() -> int:
    """Replace the universe with today's official Nifty 500 constituents."""
    root = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(root, UNIVERSE)
    current = json.load(open(path, encoding="utf-8"))
    cur_bare = [s.replace(".NS", "").upper() for s in current]

    try:
        new = nifty500_constituents()
        listed = nse_listed()
    except Exception as exc:
        print(f"[universe] could not reach NSE ({exc}) - nothing changed.")
        return 2

    if not (400 <= len(new) <= 600):
        print(f"[universe] Nifty500 list returned {len(new)} rows - refusing to act on it.")
        return 2

    adds = sorted(set(new) - set(cur_bare))
    drops = sorted(set(cur_bare) - set(new))

    # An index CSV naming something the exchange does not list is a contradiction
    # between two NSE files. Stop and show it rather than scan a phantom.
    unlisted = [a for a in adds if a not in listed]
    if unlisted:
        print(f"[universe] ADDs missing from EQUITY_L: {', '.join(unlisted)} - nothing changed.")
        return 2

    print(f"[universe] current {len(current)} | Nifty 500 today {len(new)}")
    print(f"[universe] ADD  {len(adds)}: {', '.join(adds) if adds else '(none)'}")
    print(f"[universe] DROP {len(drops)}: {', '.join(drops) if drops else '(none)'}")
    if not adds and not drops:
        print("[universe] already current - nothing to do.")
        return 0

    _write_universe(root, path, [f"{s}.NS" for s in new], len(current))
    return 0


def main() -> int:
    if "--refresh" in sys.argv:
        return refresh()

    root = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(root, UNIVERSE)
    universe = json.load(open(path, encoding="utf-8"))

    try:
        listed = nse_listed()
    except Exception as exc:
        print(f"[universe] could not reach NSE ({exc}) - no check performed.")
        return 2                      # unknown, NOT "everything is fine"

    if len(listed) < 1000:            # sanity: a truncated list would nuke the universe
        print(f"[universe] EQUITY_L returned only {len(listed)} rows - refusing to act on it.")
        return 2

    dead = [s for s in universe if s.replace(".NS", "").upper() not in listed]
    print(f"[universe] {len(universe)} symbols | {len(listed)} listed on NSE today")
    if not dead:
        print("[universe] all symbols still listed.")
        return 0

    print(f"[universe] {len(dead)} NO LONGER LISTED: {', '.join(dead)}")
    if "--prune" not in sys.argv:
        print("[universe] report only - re-run with --prune to remove them.")
        return 1

    keep = [s for s in universe if s not in dead]
    _write_universe(root, path, keep, len(universe))
    return 0


if __name__ == "__main__":
    sys.exit(main())
