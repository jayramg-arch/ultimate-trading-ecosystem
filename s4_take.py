#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
s4_take.py — mark a reviewed name as TAKEN (or SKIPPED) and log the trade.

    python s4_take.py CHOLAFIN                          # latest review, planned entry, qty from the panel
    python s4_take.py CHOLAFIN --tf 125 --price 1768.5 --qty 20   # the actual fill
    python s4_take.py CHOLAFIN --skip "sector Stage 4"  # passed on it — say why

What it does (16-Sep-2026, Jay: "mark the md file if I take the trade, to populate the journal"):
  1. finds the latest review in logs/ai_reviews for the symbol (and TF, if given);
  2. reads the plan the reviewer settled on - R-CHECK's entry/stop and the CANON T1/T2
     (never the model's own targets), the trade type, the ruling;
  3. appends a "## TAKEN" (or "## SKIPPED") block to that .md - the file is the record;
  4. fills my_call / agreed on that row of logs/ai_review_log.csv (agreed = did your
     call match the ruling) - the scoring the log has been waiting for;
  5. TAKEN: writes the journal OPEN row through dhan_journal_v7.upsert_trade with the
     stop, both targets, Timeframe (Positional/Swing - the trade-type ladder's rung 1),
     setup, planned R:R, rationale = the review file + ruling. The upsert hook captures
     the true entry snapshot. journal_sync then only has to CONFIRM qty/avg from Dhan
     tomorrow instead of inventing a bare backfilled holding with no provenance.
  6. rebuilds the Reviewer Log page so the row shows your call.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "logs", "ai_reviews")
CSV_PATH = os.path.join(HERE, "logs", "ai_review_log.csv")
_NUM = r"([0-9]+(?:\.[0-9]+)?)"


def latest_review(symbol: str, tf: str | None) -> str | None:
    sym = symbol.upper().replace("NSE:", "")
    cands = []
    for fn in os.listdir(LOG_DIR):
        m = re.match(r"^(\d{8}_\d{4,6})_%s_([A-Za-z0-9]+)\.md$" % re.escape(sym), fn)
        if m and (tf is None or m.group(2).upper() == str(tf).upper().replace("M", "")):
            cands.append(fn)
    return sorted(cands)[-1] if cands else None


def parse_plan(txt: str) -> dict:
    body = txt.split("\n## PANEL READ\n", 1)[0]
    d: dict = {"ruling": "", "entry": None, "stop": None, "t1": None, "t2": None, "type": "positional", "setup": ""}
    m = re.search(r"\*{0,2}RULING:?\*{0,2}:?\s*\*{0,2}\s*([^\n]+)", body)
    if m:
        d["ruling"] = m.group(1).strip("* ")
    m = re.search(r"R-CHECK \(recomputed\): entry %s · stop %s" % (_NUM, _NUM), body)
    if m:
        d["entry"], d["stop"] = float(m.group(1)), float(m.group(2))
    m = re.search(r"canon (positional|swing) [0-9.]+R/[0-9.]+R: T1 %s \([0-9.]+R\) · T2 %s" % (_NUM, _NUM), body)
    if m:
        d["type"], d["t1"], d["t2"] = m.group(1), float(m.group(2)), float(m.group(3))
    m = re.search(r"^Setup \| [^A-Za-z\n]*([A-Z][A-Z\-]{2,})", txt, re.M)   # "🟢 PULLBACK — ..." -> PULLBACK
    if m:
        d["setup"] = m.group(1)
    m = re.search(r"^Qty @ [^|]*\| (\d+) sh", txt, re.M)
    d["qty"] = int(m.group(1)) if m else None
    return d


def mark_csv(fn: str, my_call: str, agreed: str) -> bool:
    if not os.path.exists(CSV_PATH):
        return False
    with open(CSV_PATH, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh)); fields = rows[0].keys() if rows else []
    hit = False
    for r in rows:
        if os.path.basename((r.get("file") or "").replace("\\", "/")) == fn:
            r["my_call"], r["agreed"] = my_call, agreed; hit = True
    if hit:
        tmp = CSV_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(fields)); w.writeheader(); w.writerows(rows)
        os.replace(tmp, CSV_PATH)
    return hit


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("symbol")
    ap.add_argument("--tf", help="75 · 125 · D (default: the latest review of the name)")
    ap.add_argument("--price", type=float, help="actual fill (default: the plan's entry)")
    ap.add_argument("--qty", type=int, help="shares (default: the panel's Qty row)")
    ap.add_argument("--sl", type=float, help="override the stop (default: the plan's)")
    ap.add_argument("--skip", metavar="WHY", help="mark SKIPPED instead of TAKEN, with a reason")
    ap.add_argument("--note", default="", help="free text into the block and the journal rationale")
    ap.add_argument("--no-journal", action="store_true", help="mark the review only")
    a = ap.parse_args()

    fn = latest_review(a.symbol, a.tf)
    if not fn:
        print("no review found for %s%s in logs/ai_reviews" % (a.symbol.upper(), (" @ " + a.tf) if a.tf else ""), file=sys.stderr)
        return 2
    path = os.path.join(LOG_DIR, fn)
    txt = open(path, encoding="utf-8").read()
    plan = parse_plan(txt)
    sym = a.symbol.upper().replace("NSE:", "")
    ruling_take = plan["ruling"].upper().startswith("TAKE")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if a.skip:
        block = "\n\n## SKIPPED · %s\n- reason: %s\n- ruling was: %s\n" % (now, a.skip, plan["ruling"] or "?")
        my_call, agreed = "SKIPPED: " + a.skip, ("N" if ruling_take else "Y")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(block)
        mark_csv(fn, my_call, agreed)
        print("%s marked SKIPPED (%s) · ruling was %s · agreed=%s" % (fn, a.skip, plan["ruling"] or "?", agreed))
    else:
        price = a.price if a.price is not None else plan["entry"]
        stop = a.sl if a.sl is not None else plan["stop"]
        qty = a.qty if a.qty is not None else plan["qty"]
        if price is None or stop is None:
            print("the review has no R-CHECK entry/stop (a WAIT/PASS plan?) - pass --price and --sl", file=sys.stderr)
            return 3
        rr = (plan["t1"] - price) / (price - stop) if (plan["t1"] and price > stop) else None
        tf_lbl = "Positional" if plan["type"] == "positional" else "Swing"
        block = ("\n\n## TAKEN · %s\n- fill %.2f × %s sh%s\n- SL %.2f (%.1f%%) · T1 %s · T2 %s · %s%s\n%s"
                 % (now, price, qty if qty is not None else "?",
                    (" (plan entry %.2f)" % plan["entry"]) if plan["entry"] and abs(price - plan["entry"]) > 1e-6 else "",
                    stop, (price - stop) / price * 100.0,
                    ("%.2f" % plan["t1"]) if plan["t1"] else "—", ("%.2f" % plan["t2"]) if plan["t2"] else "—",
                    tf_lbl, (" · %.1fR to T1" % rr) if rr else "",
                    ("- note: %s\n" % a.note) if a.note else ""))
        my_call, agreed = "TAKEN", ("Y" if ruling_take else "N")
        jid = None
        if not a.no_journal:
            try:
                import dhan_journal_v7 as dj
                sector = ""
                try:
                    import sector_lookup
                    sector = (sector_lookup.get_sector(sym) or {}).get("sector", "") or ""
                except Exception:
                    pass
                entry = {"Symbol": sym, "Type": "LONG", "StopLoss": stop, "Target1": plan["t1"], "Target2": plan["t2"],
                         "Timeframe": tf_lbl, "EntryDate": datetime.now().strftime("%Y-%m-%d"),
                         "Quantity": qty or 0, "BuyPrice": price, "Status": "OPEN", "Sector": sector,
                         "PlannedRR": round(rr, 2) if rr else None,
                         "Rationale": "S4 review %s · ruling: %s%s" % (fn, plan["ruling"] or "?", (" · " + a.note) if a.note else ""),
                         "Screenshot": os.path.relpath(path, HERE)}
                res = dj.upsert_trade(entry)
                jid = res if isinstance(res, int) else None
                if plan["setup"]:
                    try:
                        import sqlite3
                        c = sqlite3.connect(dj.DB_FILE)
                        c.execute("UPDATE journal SET setup=? WHERE symbol=? AND status='OPEN' AND (setup IS NULL OR setup='' OR setup='NONE')",
                                  (plan["setup"], sym))
                        c.commit(); c.close()
                    except Exception as e:
                        print("setup not written: %s" % e, file=sys.stderr)
                block += "- journal: OPEN row written%s\n" % ((" (id %s)" % jid) if jid else "")
            except Exception as e:
                block += "- journal: NOT written (%s)\n" % e
                print("journal write failed: %s" % e, file=sys.stderr)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(block)
        mark_csv(fn, my_call, agreed)
        print("%s marked TAKEN · %.2f × %s · SL %.2f · T1 %s · T2 %s · %s · agreed=%s%s"
              % (fn, price, qty if qty is not None else "?", stop, plan["t1"], plan["t2"], tf_lbl, agreed,
                 "" if a.no_journal else " · journal OPEN"))
    try:
        import build_review_portal
        build_review_portal.build()
    except Exception as e:
        print("portal rebuild failed: %s" % e, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
