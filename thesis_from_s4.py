#!/usr/bin/env python3
"""Thesis SL for the portfolio from S4's own invalidation level (13-Oct-2026, Jay).

On 12 Oct every holding's thesis was migrated as thesis = its Dhan stop (single tier), so
the thesis was a copy of an order, not a structural level. This reads S4's INVAL for each
OPEN holding - the close that proves the idea wrong, printed on the Entry row - on the
Daily timeframe for EVERY trade (13-Oct-2026, Jay: risk/trade management is limited to the
Daily timeframe - swing names still time their ENTRY on 75m/125m), and PROPOSES it as the thesis.

    python thesis_from_s4.py              read S4 for every holding, write the proposal
    python thesis_from_s4.py --apply      write the reviewed proposal's thesis values
    python thesis_from_s4.py --ratchet    nightly: RAISE each thesis to S4's Daily INVAL (never lower)
    python thesis_from_s4.py --ratchet --dry-run   show the moves, write nothing

THE RATCHET (30-Oct-2026, Jay). The 13-Oct snapshot was then frozen, so on a winner the thesis
went stale and was overtaken by the trail (ANANDRATHI: thesis 2015.9 under a 2036.5 Dhan stop).
Nightly (auto-pilot Phase 12b4a, before the thesis alerts and the v67 push) the thesis is RAISED
to S4's Daily INVAL when that is higher AND at least RATCHET_MIN_ATR x ATR14 below the close.
It is NEVER lowered - lowering an invalidation is widening a stop, which stays a manual edit
under the sell-first rule. A level inside the 1xATR band is skipped, never capped (a capped
level is not a structural level). v2 holdings (POS-V2) and holdings with no thesis are skipped.
Every reading is appended to logs/thesis_ratchet.csv; Phase 12k's nightly stop-history row then
shows a move as THESIS up. Never places or moves an order.

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
RATCHET_LOG = os.path.join(HERE, "logs", "thesis_ratchet.csv")
RATCHET_MIN_ATR = float(os.getenv("THESIS_RATCHET_MIN_ATR", "1.0"))   # gap to the close, x ATR14
RATCHET_MIN_STEP = 0.001                                                # ignore moves under 0.1%
INVAL_RE = re.compile(r"INVAL\s+([\d,]+(?:\.\d+)?)\s*([^│|(]*)")


def _reviewer_tab():
    import s4_review as s
    ids = [x.strip() for x in os.getenv("S4_REVIEW_CHARTS", "").split(",") if x.strip()]
    want = ids[0] if ids else "5G9rwG8B"
    return [t for t in s._chart_targets() if want in t["url"]]


def _holdings():
    import journal_path
    con = sqlite3.connect(journal_path.JOURNAL_DB)
    rows = con.execute("SELECT id, symbol, timeframe, buy_price, stoploss, thesis_sl, setup FROM journal "
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
    for rid, sym, tf, buy, stop, thesis, _setup in _holdings():
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


def _read_inval(s, sym, tgt):
    """(INVAL, basis) off S4's Entry row on the Daily chart, or (None, reason)."""
    s.switch_chart(sym, "D", targets=tgt)
    m = INVAL_RE.search(s.render_read(s.read_panels(targets=tgt)))
    if not m:
        return None, "S4 printed no INVAL"
    return float(m.group(1).replace(",", "")), m.group(2).strip()


def ratchet_decision(thesis_now, inval, close, atr):
    """(new_thesis or None, verdict). Pure - the rule in one place, unit-tested."""
    if inval is None:
        return None, "no-inval"
    if thesis_now is None or not thesis_now > 0:
        return None, "no-thesis"
    if not (close and close > 0 and atr and atr > 0):
        return None, "no-price"
    if inval <= thesis_now * (1 + RATCHET_MIN_STEP):
        return None, "kept (S4 INVAL not higher)"
    if inval > close - RATCHET_MIN_ATR * atr:
        return None, "skipped (INVAL within %gxATR of the close)" % RATCHET_MIN_ATR
    return round(float(inval), 2), "raised"


def ratchet(dry_run: bool = False) -> int:
    import s4_review as s
    import journal_path
    tgt = _reviewer_tab()
    if not tgt:
        print("S4 Reviewer tab not open - thesis ratchet skipped (TradingView with the debug port)")
        return 2
    holds = _holdings()
    try:
        import dhan_ohlcv
        live = dhan_ohlcv.fetch_ltp([h[1] for h in holds]) or {}
    except Exception:
        live = {}
    try:
        import ai_risk_manager as arm
    except Exception:
        arm = None
    moves, rows = [], []
    for rid, sym, tf, buy, stop, thesis, setup in holds:
        if str(setup or "").upper().startswith("POS-V2"):
            continue
        close = live.get(sym) or _ltp(sym)
        try:
            atr = float(arm.get_atr(sym) or 0) if arm else 0.0
        except Exception:
            atr = 0.0
        try:
            inval, basis = _read_inval(s, sym, tgt)
        except Exception as e:
            inval, basis = None, "read failed: %s" % str(e)[:80]
        th = float(thesis) if thesis not in (None, "") else None
        new, verdict = ratchet_decision(th, inval, close, atr)
        print("%-12s thesis %-9s S4 INVAL %-9s close %-9s ATR %-7s -> %s%s" % (
            sym, th, inval, close, round(atr, 2) if atr else None, verdict,
            (" %s" % new) if new else ""))
        rows.append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "symbol": sym,
                     "thesis_was": th, "s4_inval": inval, "basis": (basis or "")[:80],
                     "close": close, "atr": round(atr, 2) if atr else None,
                     "new_thesis": new, "verdict": verdict, "dry_run": int(dry_run)})
        if new:
            moves.append((rid, sym, th, new))
    if moves and not dry_run:
        bak = journal_path.JOURNAL_DB.replace(
            ".db", "_backup_%s_thesis_ratchet.db" % datetime.now().strftime("%Y%m%d_%H%M"))
        shutil.copy2(journal_path.JOURNAL_DB, bak)
        con = sqlite3.connect(journal_path.JOURNAL_DB)
        for rid, sym, th, new in moves:      # the WHERE re-checks "never lower" at write time
            con.execute("UPDATE journal SET thesis_sl=? WHERE id=? AND UPPER(status)='OPEN' "
                        "AND (thesis_sl IS NULL OR thesis_sl < ?)", (new, int(rid), new))
        con.commit()
        con.close()
    if rows:
        os.makedirs(os.path.dirname(RATCHET_LOG), exist_ok=True)
        new_file = not os.path.exists(RATCHET_LOG)
        with open(RATCHET_LOG, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            if new_file:
                w.writeheader()
            w.writerows(rows)
    print("%sthesis ratchet: %d raised of %d (%s)" % (
        "DRY RUN - " if dry_run else "", len(moves), len(rows),
        ", ".join("%s %s->%s" % (m[1], m[2], m[3]) for m in moves) or "none"))
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
    ap.add_argument("--ratchet", action="store_true",
                    help="raise each thesis to S4's Daily INVAL, never lower")
    ap.add_argument("--dry-run", action="store_true", help="with --ratchet: show the moves, write nothing")
    a = ap.parse_args()
    if a.ratchet:
        return ratchet(a.dry_run)
    return apply(a.include_single) if a.apply else propose()


if __name__ == "__main__":
    sys.exit(main())
