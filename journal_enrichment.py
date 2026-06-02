# journal_enrichment.py
# Lean entry-signal snapshot for the trade journal (Phase 0 companion).
# ---------------------------------------------------------------------------
# WHAT
#   Adds 6 curated entry-time signal columns to the journal and captures them
#   for trades — so performance_attribution.py can finally attribute by Stage /
#   RS / Alpha / Setup, the gap it surfaced.
#
#       setup            — catalyst / setup label (POS-BO, SWG-PB, REV-…)
#       entry_stage      — Weinstein stage 1-4 at entry
#       entry_alpha      — Alpha Score at entry
#       entry_rs         — Mansfield / JdK RS-Ratio at entry
#       entry_conviction — pick-time conviction (Golden / matcher)
#       snapshot_meta    — "<YYYY-MM-DD>|<source>"  (recompute | backfill)
#
# ZERO DRIFT
#   The signal values come from bull_screener.screen_symbol() — the canonical
#   Python mirror of the Pine Dashboard v67 surface. No second implementation.
#
# HONESTY
#   For trades already OPEN, true entry-time signal state is unrecoverable.
#   A backfill captures TODAY's state and stamps snapshot_meta with "backfill"
#   so it is never mistaken for a genuine entry snapshot. Only NEW trades get
#   "recompute" at the actual entry.
#
# INVOCATION (via launch_script from Web Commander, or CLI)
#   python journal_enrichment.py --mode backfill        # all OPEN trades missing a snapshot
#   python journal_enrichment.py --mode backfill --force # re-snapshot every OPEN trade
#   python journal_enrichment.py --mode symbol --symbol RELIANCE --trade-id 12
# ---------------------------------------------------------------------------

import os
import sys
import argparse
import sqlite3
from datetime import date

import pandas as pd

if hasattr(sys.stdout, "encoding") and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(_DIR, "trade_journal_v6.db")
GOLDEN_CSV = os.path.join(_DIR, "MASTER_Golden_Picks.csv")

# New columns (name -> SQLite type). Single source of truth for the migration;
# mirrored in dhan_journal_v7.init_db / migrate_db.
NEW_COLUMNS = [
    ("setup",            "TEXT"),
    ("entry_stage",      "INTEGER"),
    ("entry_alpha",      "INTEGER"),
    ("entry_rs",         "REAL"),
    ("entry_conviction", "REAL"),
    ("snapshot_meta",    "TEXT"),
]


# ── Schema migration (idempotent, non-destructive) ──────────────────────────
def ensure_schema(db_file=DB_FILE):
    """Add the 6 snapshot columns if absent. Safe to run repeatedly."""
    if not os.path.exists(db_file):
        raise FileNotFoundError(f"Journal DB not found: {db_file}")
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute("PRAGMA table_info(journal)")
    existing = {row[1] for row in c.fetchall()}
    added = []
    for name, sqltype in NEW_COLUMNS:
        if name not in existing:
            c.execute(f"ALTER TABLE journal ADD COLUMN {name} {sqltype}")
            added.append(name)
    conn.commit()
    conn.close()
    return added


# ── Signal source (lazy imports keep migration usable without heavy deps) ────
_BENCH_CACHE = {}

def _load_benchmark():
    """Weekly benchmark frame (^CRSLDX) for Mansfield RS — same as the screener."""
    if "w" in _BENCH_CACHE:
        return _BENCH_CACHE["w"]
    import bull_screener as bs
    try:
        import data_provider as dp
        df_bench = bs._flatten_cols(dp.fetch_ohlcv(bs.BENCHMARK_YF, period="3y", interval="1wk"))
    except Exception:
        import yfinance as yf
        df_bench = bs._flatten_cols(
            yf.download(bs.BENCHMARK_YF, period="3y", interval="1wk",
                        auto_adjust=True, progress=False))
    _BENCH_CACHE["w"] = df_bench
    return df_bench


def _conviction_for(symbol):
    """Pick-time conviction from the latest Golden picks, if present."""
    if not os.path.exists(GOLDEN_CSV):
        return None
    try:
        df = pd.read_csv(GOLDEN_CSV)
        m = df[df["Symbol"].astype(str).str.upper() == symbol.upper()]
        if not m.empty and "Conviction" in m.columns:
            return float(m["Conviction"].iloc[0])
    except Exception:
        pass
    return None


def snapshot_symbol(symbol, source="recompute"):
    """Compute the lean entry snapshot for one symbol.

    Returns a dict of the 6 columns, or None if the symbol can't be screened
    (insufficient history / data error). We use force_output=True so a snapshot
    is produced even when the name isn't a *current* qualifier — we want the
    state, not a pass/fail.
    """
    import bull_screener as bs
    df_bench = _load_benchmark()
    rec = bs.screen_symbol(symbol, df_bench, force_output=True)
    if not rec:
        return None
    _setup = rec.get("Catalyst")
    if _setup is None or str(_setup).strip().lower() in ("", "none", "nan"):
        _setup = "NONE"   # not a fresh catalyst trigger at snapshot time
    return {
        "setup":            _setup,
        "entry_stage":      _as_int(rec.get("Stage")),
        "entry_alpha":      _as_int(rec.get("Alpha")),
        "entry_rs":         _as_float(rec.get("JdK_RS_Ratio")),
        "entry_conviction": _conviction_for(symbol),
        "snapshot_meta":    f"{date.today().isoformat()}|{source}",
    }


def _as_int(v):
    try: return int(round(float(v)))
    except (TypeError, ValueError): return None

def _as_float(v):
    try: return round(float(v), 2)
    except (TypeError, ValueError): return None


# ── Writers ─────────────────────────────────────────────────────────────────
def write_snapshot(trade_id, snap, db_file=DB_FILE):
    """UPDATE the 6 columns on one journal row."""
    cols = [k for k in snap.keys()]
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute(f"UPDATE journal SET {', '.join(f'{k} = ?' for k in cols)} WHERE id = ?",
              [snap[k] for k in cols] + [trade_id])
    conn.commit()
    conn.close()


def backfill_open_trades(db_file=DB_FILE, force=False):
    """Snapshot every OPEN trade (only those missing a snapshot unless --force).

    Stamps source='backfill' — these are as-of-today, NOT true entry-time.
    """
    ensure_schema(db_file)
    conn = sqlite3.connect(db_file)
    df = pd.read_sql_query("SELECT id, symbol, setup FROM journal WHERE status = 'OPEN'", conn)
    conn.close()

    if df.empty:
        print("ℹ️  No OPEN trades to snapshot.")
        return {"updated": 0, "skipped": 0, "failed": 0}

    if not force:
        df = df[df["setup"].isna() | (df["setup"].astype(str).str.strip() == "")]

    updated = failed = 0
    print(f"▸ Backfilling {len(df)} OPEN trade(s)  (source=backfill, as-of-today)\n")
    for _, row in df.iterrows():
        sym = str(row["symbol"])
        snap = snapshot_symbol(sym, source="backfill")
        if snap is None:
            print(f"    ✗ {sym:<14} could not screen (insufficient data)")
            failed += 1
            continue
        write_snapshot(int(row["id"]), snap, db_file)
        conv = "" if snap["entry_conviction"] is None else f" conv={snap['entry_conviction']}"
        print(f"    ✓ {sym:<14} {str(snap['setup']):<10} "
              f"stage={snap['entry_stage']} alpha={snap['entry_alpha']} "
              f"rs={snap['entry_rs']}{conv}")
        updated += 1

    skipped = 0  # (only-missing filter already removed them from df)
    print(f"\n  Updated {updated} · Failed {failed}")
    return {"updated": updated, "skipped": skipped, "failed": failed}


# ── Entry point ─────────────────────────────────────────────────────────────
def main(argv=None):
    ap = argparse.ArgumentParser(description="Lean journal entry-signal snapshot.")
    ap.add_argument("--mode", choices=["backfill", "symbol", "migrate"], default="backfill")
    ap.add_argument("--symbol", help="symbol for --mode symbol")
    ap.add_argument("--trade-id", type=int, help="journal id for --mode symbol")
    ap.add_argument("--source", default="recompute", help="snapshot_meta source tag")
    ap.add_argument("--force", action="store_true", help="re-snapshot even if present")
    ap.add_argument("--db", default=DB_FILE)
    args = ap.parse_args(argv)

    if args.mode == "migrate":
        added = ensure_schema(args.db)
        print(f"Schema OK. Added columns: {added or 'none (already present)'}")
        return 0

    if args.mode == "symbol":
        if not args.symbol or args.trade_id is None:
            ap.error("--mode symbol requires --symbol and --trade-id")
        ensure_schema(args.db)
        snap = snapshot_symbol(args.symbol, source=args.source)
        if snap is None:
            print(f"✗ Could not screen {args.symbol}")
            return 1
        write_snapshot(args.trade_id, snap, args.db)
        print(f"✓ Snapshot written to trade {args.trade_id}: {snap}")
        return 0

    # default: backfill
    backfill_open_trades(args.db, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
