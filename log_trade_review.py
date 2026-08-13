#!/usr/bin/env python3
"""Log one pre-trade review — what the system said, what you did, and why.

The point is NOT record-keeping. It is that an override you have to write down
is an override you can count later, and an uncounted override is
indistinguishable from a mistake forever. See docs/24_Pre_Trade_Review_Recipe.md.

    python log_trade_review.py NETWEB --verdict "ARM: no PA, V 0.72" \
        --call "bought anyway at 4850" --override "weekly base is tighter than the 75m shows"

    python log_trade_review.py NETWEB --verdict "GO 4/4" --call "took it"
        (no --override = you followed the system. Log these too - without the
         control group the file proves nothing.)

Writes logs/trade_reviews.csv. Append-only; never rewrites a prior row.
"""

from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "logs", "trade_reviews.csv")
FIELDS = ["ts", "symbol", "system_verdict", "my_call", "overrode", "override_reason", "note"]


def log_review(symbol: str, verdict: str, call: str, override: str = "", note: str = "") -> str:
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    new = not os.path.exists(LOG)
    row = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "symbol": (symbol or "").upper().replace("NSE:", "").replace(".NS", "").strip(),
        "system_verdict": verdict.strip(),
        "my_call": call.strip(),
        "overrode": "Y" if override.strip() else "N",
        "override_reason": override.strip(),
        "note": note.strip(),
    }
    # utf-8-sig so the rupee sign and arrows survive a double-click into Excel.
    with open(LOG, "a", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)
    return LOG


def summary() -> str:
    """Counts only. The outcome join belongs with the journal, not here."""
    if not os.path.exists(LOG):
        return "No reviews logged yet."
    try:
        with open(LOG, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
    except Exception as exc:
        return f"Could not read {LOG}: {exc}"
    n = len(rows)
    o = sum(1 for r in rows if (r.get("overrode") or "").upper() == "Y")
    pct = (o / n * 100) if n else 0.0
    return (f"{n} reviews logged · {o} overrides ({pct:.0f}%) · {n - o} followed the system\n"
            f"  {LOG}\n"
            f"  Outcomes: join on symbol+date against the journal - this file "
            f"deliberately records only the DECISION, so the two stay independent.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Log a pre-trade review decision.")
    ap.add_argument("symbol", nargs="?", help="NSE symbol")
    ap.add_argument("--verdict", default="", help="what S4/GM said, short")
    ap.add_argument("--call", default="", help="what you did")
    ap.add_argument("--override", default="", help="why you went against it (omit if you did not)")
    ap.add_argument("--note", default="", help="anything else worth keeping")
    ap.add_argument("--summary", action="store_true", help="counts so far, log nothing")
    a = ap.parse_args()

    if a.summary or not a.symbol:
        print(summary())
        return 0
    if not a.verdict or not a.call:
        print("Both --verdict and --call are required. A row with only a symbol "
              "records nothing worth reviewing later.")
        return 1
    path = log_review(a.symbol, a.verdict, a.call, a.override, a.note)
    print(f"  logged {a.symbol.upper()} -> {path}")
    if a.override:
        print("  OVERRIDE recorded. It counts now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
