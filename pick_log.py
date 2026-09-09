"""
pick_log.py — Live screener pick log (SQLite).

Auto-logs every pick from bull_screener / recovery_screener so we accumulate
a real-world track record over time. Built specifically because the recovery
screener can't be replayed historically (its Chartink pre-filter CSVs aren't
versioned) — going forward, every live run lands a row here, and a periodic
evaluation step fills in the N-day forward return.

Schema (pick_log.db):
  picks(log_id PK, logged_at, screener, as_of_date, symbol, catalyst,
        score, entry_close, metadata_json)
  evaluations(eval_id PK, log_id FK, evaluated_at, forward_days,
              forward_date, forward_close, return_pct)

Replay-safe: when data_provider has a pinned_date set (i.e. we're inside a
replay or validation run) the logger silently no-ops. Live calls are
identified by an unpinned data_provider.

Public API:
  log_picks(screener, picks_df, *, as_of_date=None, force=False) -> int
  load_picks(screener=None, since=None, limit=None) -> pd.DataFrame
  evaluate_pending(forward_days=30) -> int
  summarize(screener=None, since=None) -> dict
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime
from typing import Optional

import pandas as pd


HERE     = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(HERE, "pick_log.db")


# ─── Schema ───────────────────────────────────────────────────────────────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS picks (
    log_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    screener       TEXT NOT NULL,
    as_of_date     DATE NOT NULL,
    symbol         TEXT NOT NULL,
    catalyst       TEXT,
    score          REAL,
    entry_close    REAL,
    metadata_json  TEXT,
    UNIQUE(screener, as_of_date, symbol)
);
CREATE INDEX IF NOT EXISTS idx_picks_sd  ON picks(screener, as_of_date);
CREATE INDEX IF NOT EXISTS idx_picks_sym ON picks(symbol);

CREATE TABLE IF NOT EXISTS evaluations (
    eval_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id        INTEGER NOT NULL REFERENCES picks(log_id),
    evaluated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    forward_days  INTEGER NOT NULL,
    forward_date  DATE,
    forward_close REAL,
    return_pct    REAL,
    UNIQUE(log_id, forward_days)
);
CREATE INDEX IF NOT EXISTS idx_eval_log  ON evaluations(log_id);
"""


def _conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_schema(db_path: str = DB_PATH) -> None:
    with closing(_conn(db_path)) as c:
        c.executescript(SCHEMA_SQL)
        c.commit()


# ─── Replay safety ────────────────────────────────────────────────────────────
def _is_replay_context() -> bool:
    """True when data_provider has a pinned date — caller is replaying history."""
    try:
        import data_provider as _dp
        return _dp.get_pinned_date() is not None
    except Exception:
        return False


# ─── Logging ──────────────────────────────────────────────────────────────────
# Columns we strip out of the metadata_json blob because they have dedicated
# columns (or are huge / not useful as metadata).
_PROMOTED_COLS = {"Symbol", "Catalyst", "Signal_Label", "Score", "Entry"}


def log_picks(screener: str, picks_df: pd.DataFrame, *,
              as_of_date: Optional[str] = None,
              force: bool = False) -> int:
    """Append a screener's picks to the live log.

    Parameters
    ----------
    screener   : "bull" / "recovery" (any string is accepted; used for filters)
    picks_df   : DataFrame returned by run_bull_screener / run_recovery_screener.
                 Must contain a Symbol column.
    as_of_date : ISO YYYY-MM-DD; defaults to today.
    force      : when True, log even if the data_provider is pinned (replay).

    Returns: number of new rows inserted (0 if all duplicates / replay-safe skip).
    """
    if picks_df is None or picks_df.empty or "Symbol" not in picks_df.columns:
        return 0
    if not force and _is_replay_context():
        return 0

    _ensure_schema()
    if as_of_date is None:
        as_of_date = date.today().isoformat()

    inserted = 0
    with closing(_conn()) as c:
        for _, row in picks_df.iterrows():
            sym = str(row.get("Symbol", "")).strip().upper()
            if not sym:
                continue
            catalyst = (str(row.get("Catalyst", "") or "").strip()
                          or str(row.get("Signal_Label", "") or "").strip()
                          or None)
            try:
                score = float(row.get("Score")) if row.get("Score") is not None else None
            except (TypeError, ValueError):
                score = None
            try:
                entry = float(row.get("Entry")) if row.get("Entry") is not None else None
            except (TypeError, ValueError):
                entry = None

            # Pack remaining columns into metadata blob (skipping NaN values
            # and the columns we've promoted)
            meta: dict[str, object] = {}
            for col, val in row.items():
                if col in _PROMOTED_COLS:
                    continue
                if pd.isna(val):
                    continue
                # Coerce numpy types for JSON cleanliness
                if hasattr(val, "item"):
                    try: val = val.item()
                    except Exception: val = str(val)
                meta[str(col)] = val

            try:
                c.execute(
                    "INSERT INTO picks "
                    "(screener, as_of_date, symbol, catalyst, score, entry_close, metadata_json) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (screener, as_of_date, sym, catalyst, score, entry,
                     json.dumps(meta, default=str)),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                # Duplicate (same screener+date+symbol) — silently skip
                pass
        c.commit()
    return inserted


# ─── Loading ──────────────────────────────────────────────────────────────────
def load_picks(screener: Optional[str] = None,
                 since: Optional[str] = None,
                 limit: Optional[int] = None) -> pd.DataFrame:
    """Return picks (with the latest evaluation joined when present)."""
    _ensure_schema()
    where = []
    params: list = []
    if screener:
        where.append("p.screener = ?"); params.append(screener)
    if since:
        where.append("p.as_of_date >= ?"); params.append(since)
    sql = """
        SELECT p.log_id, p.logged_at, p.screener, p.as_of_date, p.symbol,
               p.catalyst, p.score, p.entry_close, p.metadata_json,
               e.forward_days, e.forward_date, e.forward_close, e.return_pct,
               e.evaluated_at
        FROM picks p
        LEFT JOIN evaluations e
          ON e.log_id = p.log_id
        AND e.eval_id = (
            SELECT MAX(eval_id) FROM evaluations e2 WHERE e2.log_id = p.log_id
        )
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY p.as_of_date DESC, p.score DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with closing(_conn()) as c:
        rows = c.execute(sql, params).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


# ─── Evaluation ───────────────────────────────────────────────────────────────
def evaluate_pending(forward_days: int = 30) -> int:
    """For every pick at least `forward_days` trading-days old without an
    evaluation at this horizon yet, compute its forward return and persist.

    Returns the number of new evaluation rows written.
    """
    _ensure_schema()
    try:
        import data_provider as _dp
        # Force live mode while we evaluate (caller may have pinned)
        prior = _dp.get_pinned_date()
        if prior is not None:
            _dp.set_pinned_date(None)
    except Exception:
        prior = None
        _dp = None
    try:
        # Find candidate picks
        with closing(_conn()) as c:
            sql = (
                "SELECT p.log_id, p.symbol, p.as_of_date, p.entry_close "
                "FROM picks p "
                "LEFT JOIN evaluations e "
                "  ON e.log_id = p.log_id AND e.forward_days = ? "
                "WHERE e.eval_id IS NULL"
            )
            candidates = c.execute(sql, (forward_days,)).fetchall()

        if not candidates or _dp is None:
            return 0

        from replay import _add_trading_days, _close_on_or_before, BENCHMARK_YF
        df_bench = _dp.fetch_ohlcv(BENCHMARK_YF, period="2y", interval="1d")

        new = 0
        with closing(_conn()) as c:
            for r in candidates:
                log_id     = r["log_id"]
                sym        = r["symbol"]
                as_of      = r["as_of_date"]
                entry      = r["entry_close"]
                forward_iso = _add_trading_days(as_of, forward_days, df_bench)
                if not forward_iso:
                    continue   # forward window not yet elapsed

                df = _dp.fetch_ohlcv(sym, period="2y", interval="1d")
                fwd_close = _close_on_or_before(df, forward_iso)
                if entry is None:
                    entry = _close_on_or_before(df, as_of)
                if entry is None or entry <= 0 or fwd_close is None:
                    continue
                ret_pct = round((fwd_close - entry) / entry * 100, 2)

                try:
                    c.execute(
                        "INSERT INTO evaluations "
                        "(log_id, forward_days, forward_date, forward_close, return_pct) "
                        "VALUES (?,?,?,?,?)",
                        (log_id, forward_days, forward_iso,
                         round(float(fwd_close), 2), ret_pct),
                    )
                    new += 1
                except sqlite3.IntegrityError:
                    pass
            c.commit()
        return new
    finally:
        if prior is not None and _dp is not None:
            _dp.set_pinned_date(prior)


# ─── Summary ──────────────────────────────────────────────────────────────────
def summarize(screener: Optional[str] = None,
                since: Optional[str] = None,
                forward_days: int = 30) -> dict:
    """Aggregate metrics for evaluated picks. Returns dict for the dashboard."""
    _ensure_schema()
    where = ["e.forward_days = ?"]
    params: list = [forward_days]
    if screener:
        where.append("p.screener = ?"); params.append(screener)
    if since:
        where.append("p.as_of_date >= ?"); params.append(since)
    sql = (
        "SELECT p.screener, p.as_of_date, p.symbol, p.score, "
        "       e.return_pct, e.forward_date "
        "FROM picks p "
        "JOIN evaluations e ON e.log_id = p.log_id "
        "WHERE " + " AND ".join(where)
    )
    with closing(_conn()) as c:
        rows = [dict(r) for r in c.execute(sql, params).fetchall()]

    if not rows:
        return {"n": 0, "screener": screener, "forward_days": forward_days}
    df = pd.DataFrame(rows)
    rets = df["return_pct"].astype(float)
    wins = (rets > 0).sum()
    return {
        "n":              len(df),
        "screener":       screener,
        "forward_days":   forward_days,
        "first_pick":     df["as_of_date"].min(),
        "last_pick":      df["as_of_date"].max(),
        "win_rate_pct":   round(wins / len(df) * 100, 1),
        "avg_return_pct":  round(float(rets.mean()), 2),
        "median_return_pct": round(float(rets.median()), 2),
        "best_pct":       round(float(rets.max()), 2),
        "worst_pct":      round(float(rets.min()), 2),
        "best_symbol":    df.loc[rets.idxmax(), "symbol"] if len(df) else None,
        "worst_symbol":   df.loc[rets.idxmin(), "symbol"] if len(df) else None,
    }


def stats() -> dict:
    """Quick health stats for the dashboard admin panel."""
    _ensure_schema()
    with closing(_conn()) as c:
        n_picks = c.execute("SELECT COUNT(*) AS n FROM picks").fetchone()["n"]
        n_eval  = c.execute("SELECT COUNT(*) AS n FROM evaluations").fetchone()["n"]
        screeners = [r["screener"] for r in c.execute(
            "SELECT DISTINCT screener FROM picks").fetchall()]
        first = c.execute(
            "SELECT MIN(as_of_date) AS d FROM picks").fetchone()["d"]
        last = c.execute(
            "SELECT MAX(as_of_date) AS d FROM picks").fetchone()["d"]
    return {
        "db_path":      DB_PATH,
        "db_exists":    os.path.exists(DB_PATH),
        "pick_count":   n_picks,
        "eval_count":   n_eval,
        "screeners":    screeners,
        "first_pick":   first,
        "last_pick":    last,
    }


__all__ = [
    "log_picks", "load_picks", "evaluate_pending", "summarize", "stats",
    "DB_PATH",
]


def main() -> int:
    import argparse, json as _json
    p = argparse.ArgumentParser(description="Pick log utilities")
    sub = p.add_subparsers(dest="cmd")
    p_eval = sub.add_parser("evaluate", help="Run evaluation on pending picks")
    p_eval.add_argument("--forward", type=int, default=30)
    p_sum  = sub.add_parser("summary", help="Print aggregate stats")
    p_sum.add_argument("--screener", default=None)
    p_sum.add_argument("--since",    default=None)
    p_sum.add_argument("--forward",  type=int, default=30)
    sub.add_parser("stats", help="Print DB stats")
    args = p.parse_args()

    if args.cmd == "evaluate":
        n = evaluate_pending(args.forward)
        print(f"[evaluate] {n} new evaluations at forward={args.forward}d")
    elif args.cmd == "summary":
        print(_json.dumps(summarize(args.screener, args.since, args.forward),
                            indent=2, default=str))
    else:
        print(_json.dumps(stats(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
