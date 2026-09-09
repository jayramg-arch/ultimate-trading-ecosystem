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
# ce_strike and oi_state added 1-Sep-2026 so the options read can be TESTED rather than
# believed. Both blank for a cash-only name, which is most of the board - a blank here
# means "no options exist", not "not recorded". Appended at the END so every row already
# written keeps its shape.
FIELDS = ["ts", "symbol", "system_verdict", "my_call", "overrode", "override_reason",
          "note", "ce_strike", "oi_state"]


def _migrate_header() -> None:
    """Widen an existing log to the current FIELDS, padding old rows with blanks.

    A header is only written when the file is NEW, so adding a column meant appending
    nine values under a seven-column header - the extra values land under DictReader's
    None key and the new columns read as missing. Caught by the round-trip test, not by
    review: every old row still parsed perfectly, which is exactly what makes this kind of
    corruption survive.

    This file is append-only and hand-written over weeks; there is no way to rebuild it.
    So: back up first, write through a temp file, and replace atomically - a half-written
    log is worse than an un-migrated one. Any failure leaves the original untouched.
    """
    try:
        with open(LOG, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
            have = (csv.DictReader(open(LOG, encoding="utf-8-sig")).fieldnames) or []
    except Exception:
        return                              # unreadable: leave it entirely alone
    if have == FIELDS:
        return
    missing = [f for f in FIELDS if f not in have]
    if not missing:
        return                              # reordered or extra columns: not ours to fix
    import shutil
    bak = LOG + ".bak"
    tmp = LOG + ".tmp"
    try:
        shutil.copy(LOG, bak)
        with open(tmp, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({k: (r.get(k) or "") for k in FIELDS})
        os.replace(tmp, LOG)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return


def log_review(symbol: str, verdict: str, call: str, override: str = "", note: str = "",
               ce_strike: str = "", oi_state: str = "") -> str:
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    new = not os.path.exists(LOG)
    if not new:
        _migrate_header()
    row = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "symbol": (symbol or "").upper().replace("NSE:", "").replace(".NS", "").strip(),
        "system_verdict": verdict.strip(),
        "my_call": call.strip(),
        "overrode": "Y" if override.strip() else "N",
        "override_reason": override.strip(),
        "note": note.strip(),
        # Read off the S4 panel: ce_strike from the Options OI row's "writers R", oi_state
        # from the Futures OI row. Blank when the name has no options.
        "ce_strike": (ce_strike or "").strip(),
        "oi_state": (oi_state or "").strip(),
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
    # The options columns are only worth carrying if the summary eventually reads them,
    # so it counts coverage now and says plainly that it cannot conclude anything yet.
    # A sample this small answering a directional question is how a story becomes a
    # "finding" without ever being tested.
    withopt = sum(1 for r in rows if (r.get("ce_strike") or "").strip())
    chased = sum(1 for r in rows if "cover" in (r.get("oi_state") or "").lower())
    opt = ""
    if withopt:
        opt = (f"\n  Options read on {withopt} of {n} rows"
               + (f" · {chased} taken on short covering" if chased else "")
               + ("\n  Not enough rows to conclude anything - the entered-below-CE-writers "
                  "question needs ~20 F&O rows with outcomes joined."
                  if withopt < 20 else
                  "\n  Enough rows to test: split by entry above/below ce_strike and compare "
                  "realised R against the journal."))
    return (f"{n} reviews logged · {o} overrides ({pct:.0f}%) · {n - o} followed the system"
            + opt + f"\n  {LOG}\n"
            f"  Outcomes: join on symbol+date against the journal - this file "
            f"deliberately records only the DECISION, so the two stay independent.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Log a pre-trade review decision.")
    ap.add_argument("symbol", nargs="?", help="NSE symbol")
    ap.add_argument("--verdict", default="", help="what S4/GM said, short")
    ap.add_argument("--call", default="", help="what you did")
    ap.add_argument("--override", default="", help="why you went against it (omit if you did not)")
    ap.add_argument("--note", default="", help="anything else worth keeping")
    ap.add_argument("--ce-strike", default="",
                    help="max CALL-OI strike from the S4 Options OI row (blank if no options)")
    ap.add_argument("--oi-state", default="",
                    help="futures OI state: long build-up / short covering / "
                         "short build-up / long unwinding")
    ap.add_argument("--summary", action="store_true", help="counts so far, log nothing")
    a = ap.parse_args()

    if a.summary or not a.symbol:
        print(summary())
        return 0
    if not a.verdict or not a.call:
        print("Both --verdict and --call are required. A row with only a symbol "
              "records nothing worth reviewing later.")
        return 1
    path = log_review(a.symbol, a.verdict, a.call, a.override, a.note,
                      a.ce_strike, a.oi_state)
    print(f"  logged {a.symbol.upper()} -> {path}")
    if a.override:
        print("  OVERRIDE recorded. It counts now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
