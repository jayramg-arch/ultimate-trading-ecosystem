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
    python check_universe_listing.py --prune    # also remove (writes a backup)

NSE's EQUITY_L.csv is the authority for "is it listed", not the data feed:
a feed that keeps answering is exactly how a dead instrument stays invisible.
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


def nse_listed() -> set:
    import pandas as pd
    import requests
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0",
                      "Accept-Language": "en-US,en;q=0.9"})
    s.get("https://www.nseindia.com", timeout=20)          # cookie handshake
    r = s.get(EQUITY_L, timeout=40)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = [c.strip() for c in df.columns]
    return set(df["SYMBOL"].astype(str).str.upper().str.strip())


def main() -> int:
    root = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(root, UNIVERSE)
    universe = json.load(open(path, encoding="utf-8"))

    try:
        listed = nse_listed()
    except Exception as exc:
        print(f"[universe] could not reach NSE ({exc}) — no check performed.")
        return 2                      # unknown, NOT "everything is fine"

    if len(listed) < 1000:            # sanity: a truncated list would nuke the universe
        print(f"[universe] EQUITY_L returned only {len(listed)} rows — refusing to act on it.")
        return 2

    dead = [s for s in universe if s.replace(".NS", "").upper() not in listed]
    print(f"[universe] {len(universe)} symbols · {len(listed)} listed on NSE today")
    if not dead:
        print("[universe] all symbols still listed.")
        return 0

    print(f"[universe] {len(dead)} NO LONGER LISTED: {', '.join(dead)}")
    if "--prune" not in sys.argv:
        print("[universe] report only — re-run with --prune to remove them.")
        return 1

    stamp = datetime.now().strftime("%Y%m%d")
    backup = os.path.join(root, "_archive", f"nifty500_symbols.backup_{stamp}.json")
    os.makedirs(os.path.dirname(backup), exist_ok=True)
    shutil.copy2(path, backup)
    keep = [s for s in universe if s not in dead]
    json.dump(keep, open(path, "w", encoding="utf-8"), indent=2)
    print(f"[universe] pruned {len(universe)} → {len(keep)} · backup {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
