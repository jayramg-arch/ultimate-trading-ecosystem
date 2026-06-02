# journal_sync.py
# Daily journal <-> Dhan holdings reconciliation.
# ---------------------------------------------------------------------------
# PURPOSE
#   Keep the trade journal's OPEN positions in lockstep with the live Dhan
#   book, so the journal never drifts from reality (the 2 Jun audit found the
#   journal missing GESHIP/NESTLEIND/NAM-INDIA, holding a stale-OPEN DMART, and
#   carrying wrong quantities).
#
# WHAT IT DOES (per run)
#   1. ADD    — a live holding with no OPEN journal row -> insert OPEN row
#               (+ one as-of-today 'backfill' signal snapshot).
#   2. UPDATE — a matched OPEN row whose qty/avg differs from Dhan -> correct it.
#   3. CLOSE  — an OPEN journal row no longer in the live book -> mark CLOSED,
#               but ONLY when the Dhan trade history shows a completing SELL
#               (authoritative exit price/date). Otherwise FLAG, never force.
#
# SAFETY (this writes to the production journal)
#   - Aborts entirely if the holdings fetch fails OR returns an empty book
#     (an API hiccup must never be read as "everything was sold").
#   - Cash-park instruments (LIQUID*) are ignored on both sides.
#   - --dry-run prints the plan and writes nothing.
#   - --no-close skips the CLOSE step (add/update only).
#
# INVOCATION
#   python journal_sync.py --dry-run       # preview
#   python journal_sync.py                 # apply
#   (scheduled daily post-market via Windows Task Scheduler)
# ---------------------------------------------------------------------------

import os
import sys
import argparse
import sqlite3
from datetime import date

import pandas as pd
from dotenv import load_dotenv

if hasattr(sys.stdout, "encoding") and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

load_dotenv(override=True)

_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(_DIR, "trade_journal_v6.db")


def _is_cash_park(sym):
    return "LIQUID" in str(sym).upper()


# ── Live book ───────────────────────────────────────────────────────────────
def _live_holdings():
    """Return {SYMBOL: {'qty','avg','ltp'}} from Dhan, or None on failure.

    None is the abort signal — the caller must NOT touch the journal when the
    book can't be trusted.
    """
    try:
        from dhan_auth import ensure_valid_token
        from dhanhq import dhanhq
        tok = ensure_valid_token()
        cid = os.getenv("DHAN_CLIENT_ID")
        if not tok or not cid:
            print("✗ No valid Dhan token/client id — aborting sync (journal untouched).")
            return None
        dhan = dhanhq(client_id=cid, access_token=tok)
        resp = dhan.get_holdings()
        if resp.get("status") != "success":
            print(f"✗ Holdings fetch not successful ({resp.get('remarks')}) — aborting.")
            return None
        data = resp.get("data") or []
        out = {}
        for it in data:
            sym = str(it.get("tradingSymbol") or "").upper().strip()
            qty = it.get("totalQty") or it.get("netQty") or 0
            if not sym or qty == 0 or _is_cash_park(sym):
                continue
            out[sym] = {
                "qty": float(qty),
                "avg": float(it.get("avgCostPrice") or 0) or None,
                "ltp": float(it.get("lastTradedPrice") or 0) or None,
            }
        return out
    except Exception as e:
        print(f"✗ Holdings fetch raised ({e}) — aborting sync (journal untouched).")
        return None


def _norm(sym):
    try:
        from ai_reconcile_engine import normalize_symbol
        return normalize_symbol(sym)
    except Exception:
        return str(sym).upper().strip()


# ── Exit lookup for CLOSE step ──────────────────────────────────────────────
def _completed_exits():
    """{normsym: (exit_price, exit_date)} of round-trips completed per Dhan
    trade history — authoritative source for closing exited positions."""
    try:
        import ai_reconcile_engine as r
        api = r.fetch_trade_history()
        if api is None or api.empty:
            return {}
        mc = r.process_trade_history(api)
        out = {}
        for _, m in mc.iterrows():
            out[_norm(m["Symbol"])] = (float(m["Exit Price"]), str(m["Exit Date"]))
        return out
    except Exception as e:
        print(f"  (exit lookup unavailable: {e})")
        return {}


# ── Core sync ───────────────────────────────────────────────────────────────
def sync(db_file=DB_FILE, dry_run=False, do_close=True):
    live = _live_holdings()
    if not live:                      # None (error) OR empty book -> abort
        if live == {}:
            print("✗ Live book is EMPTY — refusing to close all positions. Aborting.")
        return {"status": "aborted", "added": 0, "updated": 0, "closed": 0, "flagged": []}

    import journal_enrichment as je
    je.ensure_schema(db_file)

    conn = sqlite3.connect(db_file)
    opens = pd.read_sql_query(
        "SELECT id,symbol,quantity,buy_price FROM journal WHERE status='OPEN'", conn)
    open_by_norm = {_norm(r["symbol"]): r for _, r in opens.iterrows()}
    live_by_norm = {_norm(s): (s, v) for s, v in live.items()}

    added = updated = closed = 0
    flagged = []
    plan = []

    # 1 & 2 — ADD / UPDATE from the live book
    for nsym, (sym, v) in live_by_norm.items():
        if nsym in open_by_norm:
            row = open_by_norm[nsym]
            new_qty, new_avg = v["qty"], v["avg"]
            qty_diff = abs(float(row["quantity"] or 0) - new_qty) > 1e-6
            avg_diff = new_avg and abs(float(row["buy_price"] or 0) - new_avg) > 0.01
            if qty_diff or avg_diff:
                plan.append(f"UPDATE {sym:<14} qty {row['quantity']}->{new_qty}"
                            + (f", avg {round(float(row['buy_price'] or 0),2)}->{round(new_avg,2)}" if avg_diff else ""))
                if not dry_run:
                    conn.execute("UPDATE journal SET quantity=?, buy_price=COALESCE(?,buy_price) WHERE id=?",
                                 (new_qty, new_avg, int(row["id"])))
                updated += 1
        else:
            plan.append(f"ADD    {sym:<14} qty {v['qty']} @ {v['avg']}")
            if not dry_run:
                cur = conn.execute(
                    "INSERT INTO journal (symbol,status,quantity,buy_price,entry_date,trade_type) "
                    "VALUES (?,?,?,?,?,?)",
                    (sym, "OPEN", v["qty"], v["avg"], date.today().isoformat(), "Positional"))
                new_id = cur.lastrowid
                conn.commit()
                try:    # one as-of-today snapshot for the freshly-tracked holding
                    snap = je.snapshot_symbol(sym, source="backfill")
                    if snap:
                        je.write_snapshot(new_id, snap, db_file)
                except Exception as _se:
                    print(f"  (snapshot skipped for {sym}: {_se})")
            added += 1

    # 3 — CLOSE journal OPENs no longer in the live book (only with a real exit)
    if do_close:
        exits = _completed_exits() if (open_by_norm.keys() - live_by_norm.keys()) else {}
        for nsym, row in open_by_norm.items():
            if nsym in live_by_norm or _is_cash_park(row["symbol"]):
                continue
            if nsym in exits:
                ep, ed = exits[nsym]
                plan.append(f"CLOSE  {row['symbol']:<14} exit {ep} @ {ed}")
                if not dry_run:
                    conn.execute("UPDATE journal SET status='CLOSED', exit_price=?, exit_date=? WHERE id=?",
                                 (ep, ed, int(row["id"])))
                closed += 1
            else:
                flagged.append(str(row["symbol"]))

    if not dry_run:
        conn.commit()
    conn.close()

    # Report
    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Journal ↔ Dhan holdings sync — {date.today().isoformat()}")
    print(f"  Live holdings: {len(live)} | Journal OPEN: {len(opens)}")
    for line in plan:
        print("   ", line)
    if flagged:
        print("  ⚠ FLAGGED (OPEN in journal, not in live book, no completing exit found — review):")
        print("     " + ", ".join(flagged))
    print(f"\n  {'Would ' if dry_run else ''}ADD {added} · UPDATE {updated} · CLOSE {closed} · FLAG {len(flagged)}")
    return {"status": "ok", "added": added, "updated": updated,
            "closed": closed, "flagged": flagged}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Daily journal <-> Dhan holdings sync.")
    ap.add_argument("--dry-run", action="store_true", help="preview only, write nothing")
    ap.add_argument("--no-close", action="store_true", help="skip closing exited positions")
    ap.add_argument("--db", default=DB_FILE)
    args = ap.parse_args(argv)
    res = sync(db_file=args.db, dry_run=args.dry_run, do_close=not args.no_close)
    return 0 if res["status"] in ("ok", "aborted") else 1


if __name__ == "__main__":
    sys.exit(main())
