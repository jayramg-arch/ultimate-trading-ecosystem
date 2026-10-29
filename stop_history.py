"""stop_history.py - every move of every stop, so widening shows up as a habit (28-Oct-2026).

Jay: "my stop losses are still being hit, and I'm not sticking to my risk rule, due to
constant widening of my stop losses." A stop widened once is a decision; a stop widened four
times on the same trade is a habit, and it only shows when the moves are recorded.

One row per holding per session in logs/stop_history.csv:
  date, symbol, qty, avg, ltp, atr, initial, thesis, disaster, chand, source
  source = 'dhan'   the nightly snapshot (auto-pilot Phase 12k): the RESTING Dhan stop
           'backup' a dated journal backup (trade_journal_v6.backup_YYYYMMDD.db), back-filled
                    once; the stop there is the journal stoploss, synced from Dhan at 16:30
           'page'   a thesis or planned quantity saved on the SL Dashboard (logged at once)

events() turns consecutive rows into moves:
  WIDENED    the Dhan stop moved DOWN (more rupees at risk at the stop, same shares)
  TIGHTENED  the Dhan stop moved UP
  THESIS ↓ / THESIS ↑   the thesis level moved
and summary() rolls them up per holding: how many widenings, the rupees each one added at the
holding's quantity, and where the stop sits now against the initial SL.
Nothing here places or moves an order.
"""
from __future__ import annotations

import glob
import os
import re
import sqlite3
from datetime import datetime

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(HERE, "logs", "stop_history.csv")
COLS = ["date", "symbol", "qty", "avg", "ltp", "atr", "initial", "thesis", "disaster", "chand", "source"]
MOVE_TOL = 0.002          # a stop that moved less than 0.2% is rounding (tick/limit edits), not a move


def _f(x):
    try:
        v = float(x)
        return v if v == v and v > 0 else None
    except (TypeError, ValueError):
        return None


def load() -> pd.DataFrame:
    if not os.path.exists(HIST):
        return pd.DataFrame(columns=COLS)
    df = pd.read_csv(HIST)
    for c in COLS:
        if c not in df.columns:
            df[c] = None
    return df[COLS]


def _save(df: pd.DataFrame) -> None:
    from io_utils import atomic_write_text
    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    atomic_write_text(HIST, df[COLS].to_csv(index=False))


def _upsert(rows: list[dict]) -> int:
    """Add rows; a row for the same (date, symbol, source) replaces the old one."""
    if not rows:
        return 0
    old = load()
    new = pd.DataFrame(rows, columns=COLS)
    key = set(zip(new["date"], new["symbol"], new["source"]))
    keep = old[[(d, s, src) not in key for d, s, src in zip(old["date"], old["symbol"], old["source"])]]
    out = pd.concat([keep, new], ignore_index=True).sort_values(["symbol", "date", "source"])
    _save(out)
    return len(new)


def record_board(df: pd.DataFrame, date: str | None = None, source: str = "dhan") -> int:
    """Snapshot an sl_board.build() frame as today's row per holding."""
    date = date or datetime.now().strftime("%Y-%m-%d")
    rows = [{"date": date, "symbol": r.symbol, "qty": r.qty, "avg": r.avg, "ltp": r.ltp, "atr": r.atr,
             "initial": r.initial, "thesis": r.thesis, "disaster": r.disaster, "chand": r.chand,
             "source": source} for r in df.itertuples()]
    return _upsert(rows)


def record_page_edit(symbol: str, qty, avg, thesis, disaster) -> int:
    """A thesis saved on the SL Dashboard, logged the moment it is saved."""
    return _upsert([{"date": datetime.now().strftime("%Y-%m-%d"), "symbol": symbol, "qty": qty, "avg": avg,
                     "ltp": None, "atr": None, "initial": None, "thesis": thesis, "disaster": disaster,
                     "chand": None, "source": "page"}])


def backfill_from_backups(force: bool = False) -> int:
    """One row per holding per dated journal backup (trade_journal_v6.backup_YYYYMMDD.db).
    Only the plain daily backups - the *_tag ones are mid-session safety copies."""
    have = load()
    done = set(have.loc[have["source"] == "backup", "date"]) if not force else set()
    rows = []
    for p in sorted(glob.glob(os.path.join(HERE, "trade_journal_v6.backup_*.db"))):
        m = re.search(r"backup_(\d{8})\.db$", p)
        if not m:
            continue
        d = datetime.strptime(m.group(1), "%Y%m%d").strftime("%Y-%m-%d")
        if d in done:
            continue
        try:
            con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            cols = {r[1] for r in con.execute("PRAGMA table_info(journal)")}
            js = con.execute("SELECT * FROM journal WHERE UPPER(status)='OPEN'").fetchall()
            con.close()
        except Exception:
            continue
        for r in js:
            sym = str(r["symbol"]).strip().upper()
            if sym.startswith("LIQUID") or str(r["setup"] if "setup" in cols else "").upper().startswith("POS-V2"):
                continue
            rows.append({"date": d, "symbol": sym, "qty": _f(r["quantity"]), "avg": _f(r["buy_price"]),
                         "ltp": None, "atr": None,
                         "initial": _f(r["initial_sl"]) if "initial_sl" in cols else None,
                         "thesis": _f(r["thesis_sl"]) if "thesis_sl" in cols else None,
                         "disaster": _f(r["stoploss"]), "chand": None, "source": "backup"})
    return _upsert(rows)


def _series(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (symbol, date): the nightly Dhan snapshot wins over a backup on the same day,
    a page edit only supplies the thesis it saved."""
    if df.empty:
        return df
    rank = {"dhan": 0, "backup": 1, "page": 2}
    d = df.copy()
    d["_r"] = d["source"].map(rank).fillna(3)
    d = d.sort_values(["symbol", "date", "_r"])
    out = []
    for (sym, date), g in d.groupby(["symbol", "date"], sort=True):
        base = g.iloc[0].to_dict()
        for c in ("thesis", "disaster", "qty", "avg", "initial"):
            if base.get(c) is None or base.get(c) != base.get(c):
                vals = g[c].dropna()
                if len(vals):
                    base[c] = vals.iloc[0]
        page = g[g["source"] == "page"]
        if len(page) and page["thesis"].notna().any():
            base["thesis"] = page["thesis"].dropna().iloc[-1]
        out.append(base)
    return pd.DataFrame(out).drop(columns=["_r"])


def events(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Consecutive-row moves per holding. Rupees = shares held x the price move."""
    s = _series(load() if df is None else df)
    ev = []
    for sym, g in s.groupby("symbol"):
        g = g.sort_values("date")
        prev = None
        for r in g.to_dict("records"):
            if prev is not None:
                q = _f(r.get("qty")) or _f(prev.get("qty")) or 0
                a, b = _f(prev.get("disaster")), _f(r.get("disaster"))
                if a and b and abs(b - a) / a > MOVE_TOL:
                    kind = "WIDENED" if b < a else "TIGHTENED"
                    ev.append({"date": r["date"], "symbol": sym, "kind": kind, "from": a, "to": b,
                               "pct": (b / a - 1) * 100, "rupees": q * (a - b),
                               "below_entry": bool(_f(r.get("avg")) and b < _f(r.get("avg"))),
                               "qty_from": _f(prev.get("qty")), "qty_to": _f(r.get("qty")),
                               "avg": _f(r.get("avg"))})
                ta, tb = _f(prev.get("thesis")), _f(r.get("thesis"))
                if ta and tb and abs(tb - ta) / ta > MOVE_TOL:
                    ev.append({"date": r["date"], "symbol": sym, "kind": "THESIS ↓" if tb < ta else "THESIS ↑",
                               "from": ta, "to": tb, "pct": (tb / ta - 1) * 100, "rupees": q * (ta - tb),
                               "below_entry": bool(_f(r.get("avg")) and tb < _f(r.get("avg"))),
                               "qty_from": _f(prev.get("qty")), "qty_to": _f(r.get("qty")),
                               "avg": _f(r.get("avg"))})
            prev = r
    return pd.DataFrame(ev, columns=EVENT_COLS)


EVENT_COLS = ["date", "symbol", "kind", "from", "to", "pct", "rupees", "below_entry",
              "qty_from", "qty_to", "avg"]


def unmatched_widenings(ev: pd.DataFrame | None = None, budget_for=None) -> pd.DataFrame:
    """WIDENED moves where the shares held after the move did NOT fit the per-trade rule at the
    new stop (29-Oct-2026: the same test stop_guard enforces - gap_risk.lower_stop_qty, from
    cost, 5% slack). A widening that stays above cost locks a profit and is never flagged.
    budget_for(symbol) -> rupees; default = house sizing capital x house_policy.risk_pct_for."""
    from gap_risk import lower_stop_qty
    ev = events() if ev is None else ev
    if ev.empty:
        return ev.assign(allowed=pd.Series(dtype=float), sell_first=pd.Series(dtype=float))
    if budget_for is None:
        import house_policy as hp
        cap, _ = hp.sizing_capital()

        def budget_for(sym):
            return cap * hp.risk_pct_for(sym) / 100.0
    w = ev[ev["kind"] == "WIDENED"].copy()
    rows = []
    for r in w.to_dict("records"):
        q, avg = _f(r.get("qty_to")) or _f(r.get("qty_from")), _f(r.get("avg"))
        if not (q and avg) or r["to"] >= avg:
            continue
        allowed, sell = lower_stop_qty(q, avg, r["to"], budget_for(r["symbol"]) * 1.05)
        if allowed is not None and q > allowed:
            rows.append({**r, "allowed": allowed, "sell_first": sell})
    return pd.DataFrame(rows, columns=list(ev.columns) + ["allowed", "sell_first"])


def digest_lines(days: int = 20) -> list[str]:
    """Evening digest: stops widened WITHOUT the quantity cut that pays for them - on the
    latest recorded day, and over the last `days` recorded days, open holdings only."""
    s = _series(load())
    if s.empty:
        return ["STOP DISCIPLINE: no stop history yet"]
    dates = sorted(s["date"].unique())
    last, window = dates[-1], set(dates[-days:])
    open_syms = set(s[s["date"] == last]["symbol"])
    u = unmatched_widenings()
    u = u[u["symbol"].isin(open_syms)] if len(u) else u
    today = u[u["date"] == last] if len(u) else u
    win = u[u["date"].isin(window)] if len(u) else u
    L = [f"STOP DISCIPLINE ({last}): {len(today)} stop(s) widened today without the qty cut; "
         f"{len(win)} in the last {len(window)} recorded days"
         + (f", Rs {win['rupees'].clip(lower=0).sum():,.0f} of risk added" if len(win) else "")]
    for r in today.to_dict("records"):
        L.append(f"  {r['symbol']}: {r['from']:g} -> {r['to']:g} with {int(r['qty_to'] or 0)} sh - the rule "
                 f"allows {int(r['allowed'])} at that stop, sell {int(r['sell_first'])}")
    return L


def summary(ev: pd.DataFrame | None = None, open_syms: list[str] | None = None) -> pd.DataFrame:
    """Per holding: widenings, tightenings, rupees added by widening, thesis moves down."""
    ev = events() if ev is None else ev
    rows = []
    syms = open_syms if open_syms is not None else sorted(ev["symbol"].unique()) if len(ev) else []
    for sym in syms:
        e = ev[ev["symbol"] == sym]
        w = e[e["kind"] == "WIDENED"]
        rows.append({"symbol": sym, "widened": len(w),
                     "widened_below_entry": int(w["below_entry"].sum()) if len(w) else 0,
                     "tightened": int((e["kind"] == "TIGHTENED").sum()),
                     "thesis_down": int((e["kind"] == "THESIS ↓").sum()),
                     "risk_added": float(w["rupees"].clip(lower=0).sum()) if len(w) else 0.0,
                     "last_move": e["date"].max() if len(e) else ""})
    return pd.DataFrame(rows)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Record today's stops (and back-fill from journal backups).")
    ap.add_argument("--backfill", action="store_true", help="read the dated journal backups first")
    ap.add_argument("--no-record", action="store_true", help="skip today's live snapshot")
    a = ap.parse_args()
    if a.backfill:
        print(f"back-filled {backfill_from_backups()} rows from journal backups")
    if not a.no_record:
        import sl_board
        df, meta = sl_board.build()
        if not meta.get("orders_ok"):
            print("Dhan order book unreadable - today's snapshot NOT recorded (it would log journal stops as Dhan's)")
            return 1
        print(f"recorded {record_board(df)} holdings for {datetime.now():%Y-%m-%d}")
    s = summary()
    w = s[s["widened"] > 0] if len(s) else s
    print(f"{len(w)} holding(s) with a widened stop on record" +
          ("" if w.empty else ": " + ", ".join(f"{r.symbol} x{r.widened}" for r in w.itertuples())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
