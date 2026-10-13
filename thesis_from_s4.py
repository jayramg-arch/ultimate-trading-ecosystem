#!/usr/bin/env python3
"""Thesis SL for the portfolio from S4's own invalidation level (13-Oct-2026, Jay).

On 12 Oct every holding's thesis was migrated as thesis = its Dhan stop (single tier), so
the thesis was a copy of an order, not a structural level. This reads S4's INVAL for each
OPEN holding - the close that proves the idea wrong, printed on the Entry row - on the
Daily timeframe for EVERY trade (13-Oct-2026, Jay: risk/trade management is limited to the
Daily timeframe - swing names still time their ENTRY on 75m/125m), and PROPOSES it as the thesis.

    python thesis_from_s4.py              read S4 for every holding, write the proposal
    python thesis_from_s4.py --apply      write the reviewed proposal's thesis values

It drives ONLY the S4 Reviewer tab (S4_REVIEW_CHARTS' first id, else 5G9rwG8B) - never
Jay's tabs. Nothing is written to the journal without --apply, and --apply writes only
rows marked 'two-tier' (INVAL between the Dhan stop and price) unless --include-single.
A journal backup is taken before any write. Never places or moves an order.

Proposal verdicts:
  two-tier         Dhan stop < INVAL < price - the thesis becomes the close-basis exit, the
                   Dhan stop the disaster stop (v67 draws both; a thesis alert is set nightly)
  below-dhan-stop  INVAL <= Dhan stop - the order fires first; thesis would be superseded
  already-broken   INVAL >= price - S4's own invalidation is already through; review the hold
  no-inval         S4 printed no INVAL on this name
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "reports", "thesis_proposal_%s.csv" % datetime.now().strftime("%Y%m%d"))
INVAL_RE = re.compile(r"INVAL\s+([\d,]+(?:\.\d+)?)\s*([^│|(]*)")


def _reviewer_tab():
    import s4_review as s
    ids = [x.strip() for x in os.getenv("S4_REVIEW_CHARTS", "").split(",") if x.strip()]
    want = ids[0] if ids else "5G9rwG8B"
    return [t for t in s._chart_targets() if want in t["url"]]


def _holdings():
    import journal_path
    con = sqlite3.connect(journal_path.JOURNAL_DB)
    rows = con.execute("SELECT id, symbol, timeframe, buy_price, stoploss, thesis_sl FROM journal "
                       "WHERE UPPER(status)='OPEN' ORDER BY symbol").fetchall()
    con.close()
    return rows


def _ltp(sym):
    try:
        import data_provider as dp
        d = dp.fetch_ohlcv(sym, period="1mo", interval="1d", use_cache=True)
        return float(d["Close"].iloc[-1])
    except Exception:
        return None


def propose() -> int:
    import s4_review as s
    tgt = _reviewer_tab()
    if not tgt:
        print("S4 Reviewer tab not open - open it (TradingView with the debug port) and re-run")
        return 2
    out = []
    for rid, sym, tf, buy, stop, thesis in _holdings():
        clock = "D"          # management is Daily for every trade (13-Oct-2026)
        rec = {"id": rid, "symbol": sym, "clock": clock, "ltp": _ltp(sym), "dhan_sl": stop,
               "thesis_now": thesis, "s4_inval": "", "basis": "", "verdict": "no-inval"}
        try:
            s.switch_chart(sym, clock, targets=tgt)
            txt = s.render_read(s.read_panels(targets=tgt))
            m = INVAL_RE.search(txt)
            if m:
                inv = float(m.group(1).replace(",", ""))
                rec.update(s4_inval=inv, basis=m.group(2).strip())
                ltp = rec["ltp"]
                if ltp and inv >= ltp:
                    rec["verdict"] = "already-broken"
                elif stop and inv <= float(stop):
                    rec["verdict"] = "below-dhan-stop"
                else:
                    rec["verdict"] = "two-tier"
        except Exception as e:
            rec["verdict"] = "read-failed"
            rec["basis"] = str(e)[:120]
        out.append(rec)
        print("%-12s %-3s ltp %-9s dhan %-9s INVAL %-9s %-16s %s" % (
            sym, clock, rec["ltp"], stop, rec["s4_inval"], rec["verdict"], rec["basis"][:60]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader(); w.writerows(out)
    print("\nproposal: %s - review it, then run with --apply" % OUT)
    return 0


def apply(include_single: bool) -> int:
    if not os.path.exists(OUT):
        print("no proposal for today - run without --apply first"); return 2
    import journal_path
    rows = list(csv.DictReader(open(OUT, encoding="utf-8")))
    ok = {"two-tier"} | ({"below-dhan-stop"} if include_single else set())
    todo = [r for r in rows if r["verdict"] in ok and r["s4_inval"]]
    if not todo:
        print("nothing to write"); return 0
    bak = journal_path.JOURNAL_DB.replace(".db", "_backup_%s_thesis_s4.db" % datetime.now().strftime("%Y%m%d_%H%M"))
    shutil.copy2(journal_path.JOURNAL_DB, bak)
    con = sqlite3.connect(journal_path.JOURNAL_DB)
    for r in todo:
        con.execute("UPDATE journal SET thesis_sl=? WHERE id=? AND UPPER(status)='OPEN'",
                    (float(r["s4_inval"]), int(r["id"])))
        print("thesis %-12s %s -> %s (%s)" % (r["symbol"], r["thesis_now"], r["s4_inval"], r["basis"]))
    con.commit(); con.close()
    print("\nwritten %d · backup %s" % (len(todo), bak))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--include-single", action="store_true",
                    help="also write INVALs that sit at/below the Dhan stop (single tier)")
    a = ap.parse_args()
    return apply(a.include_single) if a.apply else propose()


if __name__ == "__main__":
    sys.exit(main())
