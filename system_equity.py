#!/usr/bin/env python3
"""Daily equity of each system's REAL book - v1, v2 and the legacy book (Jay, 19-Oct-2026).

The v1-vs-v2 comparison needs drawdown and time-weighted return, which cannot be rebuilt later
from a journal that only keeps the current quantity. So every evening one row per system is
appended to logs/system_equity.csv:

    date, system, mv, cash, equity, flow, nav, n, unclassified, bench

  mv      market value of the open holdings of that origin at the session close
  cash    the system's cash: its capital, plus sale proceeds, less purchases, plus interest
  equity  mv + cash
  flow    external money that day (capital moves / top-ups from data/system_transfers.csv, and a
          holding re-classified from one origin to another) - excluded from the return
  nav     time-weighted index, 1.0 at the start: nav x (equity - flow) / previous equity

Capital (Jay, 18/19-Oct): v2 = p1_paper.v2_capital() (sizing capital / 3); v1 = sizing capital
less v2's; legacy = what its holdings were worth on the first day (it never gets new money).
Cash earns IDLE_CASH_RATE (the ICICI sweep-in FD, 6.75 %) in every system, so a system that sits
in cash is not penalised for it.

v2's holdings and fills come from its ledger (data/v2/real_book.json); v1 and legacy from the
journal's `origin` (trade_origin.py), with buys and sells detected from the change in each row's
quantity since the last snapshot - a new row is bought at its buy price, a closed row sold at its
exit price, a quantity change between them at that day's close. Rows with no origin count as v1
and are reported as unclassified.

    python system_equity.py            append today's row (idempotent: a date is written once)
    python system_equity.py --show     print the series
    python system_equity.py --rebuild  start over from today (keeps the old file as .bak)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sqlite3
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_DIR = os.environ.get("SYSTEM_EQUITY_DIR")          # tests: everything under one folder
OUT = os.path.join(_DIR or os.path.join(HERE, "logs"), "system_equity.csv")
STATE = os.path.join(_DIR or os.path.join(HERE, "data"), "system_equity_state.json")
TRANSFERS = os.path.join(_DIR or os.path.join(HERE, "data"), "system_transfers.csv")
IDLE_CASH_RATE = 0.0675
SYSTEMS = ("v1", "v2", "legacy")
COLS = ["date", "system", "mv", "cash", "equity", "flow", "nav", "n", "unclassified", "bench"]


def _close(sym: str, day: dt.date) -> float | None:
    """The close of `day` (or the last close before it) from the house data provider."""
    try:
        import data_provider as dp
        d = dp.fetch_ohlcv(sym, period="3mo", interval="1d", use_cache=True)
        if d is None or not len(d):
            return None
        d = d.copy()
        d.index = pd.to_datetime(d.index)
        if getattr(d.index, "tz", None) is not None:
            d.index = d.index.tz_localize(None)
        s = d["Close"].dropna()
        s = s[s.index.normalize() <= pd.Timestamp(day)]
        return float(s.iloc[-1]) if len(s) else None
    except Exception:
        return None


def _journal_rows(db: str) -> list:
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(journal)")]
        has_o = "origin" in cols
        q = "SELECT id, symbol, status, quantity, buy_price, exit_price, exit_date, setup%s FROM journal" % (
            ", origin" if has_o else "")
        return [dict(r) for r in con.execute(q)]
    finally:
        con.close()


def _transfers(day: dt.date) -> dict:
    """{system: amount} external money dated `day` (positive = money into that system)."""
    out = {s: 0.0 for s in SYSTEMS}
    if not os.path.exists(TRANSFERS):
        return out
    try:
        t = pd.read_csv(TRANSFERS)
        t = t[pd.to_datetime(t["date"]).dt.date == day]
        for _, r in t.iterrows():
            if str(r["system"]) in out:
                out[str(r["system"])] += float(r["amount"])
    except Exception:
        pass
    return out


def _load_state() -> dict | None:
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except Exception:
        return None


def _save_state(st: dict) -> None:
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    txt = json.dumps(st, indent=1, default=str)
    try:
        from io_utils import atomic_write_text
        atomic_write_text(STATE, txt)
    except Exception:
        open(STATE, "w", encoding="utf-8").write(txt)


def snapshot(day: dt.date | None = None, db: str | None = None) -> list:
    """Compute and append the rows for `day` (default: the last completed NSE session).
    Returns the rows written ([] when that date is already in the file)."""
    import house_policy as hp
    import journal_path as jp
    import nse_calendar as nc
    import p1_paper as pp
    import v2_ledger as vl
    day = day or nc.last_completed_session()
    db = db or jp.JOURNAL_DB
    if os.path.exists(OUT):
        prev = pd.read_csv(OUT)
        if str(day) in set(prev["date"].astype(str)):
            return []
    st = _load_state()
    rows = _journal_rows(db)
    v2cap = float(pp.v2_capital())
    sizing = float(hp.sizing_capital()[0])
    # ── v1 / legacy from the journal ────────────────────────────────────────────
    open_now = {}
    unclassified = 0
    for r in rows:
        if str(r["status"]).upper() != "OPEN" or str(r.get("setup") or "").upper().startswith("POS-V2"):
            continue
        o = r.get("origin") if r.get("origin") in ("v1", "legacy") else None
        if o is None:
            unclassified += 1
            o = "v1"
        open_now[str(r["id"])] = {"symbol": r["symbol"], "qty": float(r["quantity"] or 0),
                                  "buy": float(r["buy_price"] or 0), "origin": o}
    px = {}
    for k, v in open_now.items():
        if v["symbol"] not in px:
            px[v["symbol"]] = _close(v["symbol"], day)
    mv = {s: 0.0 for s in SYSTEMS}
    n = {s: 0 for s in SYSTEMS}
    for k, v in open_now.items():
        p = px.get(v["symbol"]) or v["buy"]
        mv[v["origin"]] += v["qty"] * p
        n[v["origin"]] += 1
    # ── v2 from its ledger ──────────────────────────────────────────────────────
    book = vl.load()
    v2_open_cost = 0.0
    for s, q in book["open"].items():
        p = _close(s, day) or float(q["entry"])
        mv["v2"] += float(q["sh"]) * p
        v2_open_cost += float(q["sh"]) * float(q["entry"])
        n["v2"] += 1
    v2_realised = vl.realised()
    flows = _transfers(day)                     # external money: into that system's cash
    rflow = {s: 0.0 for s in SYSTEMS}           # a holding re-classified between origins
    bench = _close("^CRSLDX", day)
    if st is None:
        # first day: v1 holds its book at market and the rest of its capital as cash
        cash = {"v1": sizing - v2cap - mv["v1"], "legacy": 0.0}
        st = {"start": str(day), "last": None, "rows": {}, "cash": cash, "v2_flows": 0.0,
              "v2_yield": 0.0, "equity": {}, "nav": {s: 1.0 for s in SYSTEMS}}
    else:
        last = dt.date.fromisoformat(st["last"])
        days = max(0, (day - last).days)
        # interest on yesterday's cash, then today's trades move cash between cash and holdings
        for s in ("v1", "legacy"):
            st["cash"][s] += max(0.0, st["cash"][s]) * IDLE_CASH_RATE * days / 365.0
        prev_v2_cash = st.get("v2_cash_prev", v2cap)
        st["v2_yield"] += max(0.0, prev_v2_cash) * IDLE_CASH_RATE * days / 365.0
        old = st["rows"]
        closed_px = {str(r["id"]): float(r["exit_price"] or 0) for r in rows if str(r["status"]).upper() == "CLOSED"}
        for k, v in open_now.items():
            p = px.get(v["symbol"]) or v["buy"]
            if k not in old:                                       # a new holding: bought
                st["cash"][v["origin"]] -= v["qty"] * v["buy"]
                continue
            o = old[k]
            if o["origin"] != v["origin"]:                          # re-classified by Jay: a transfer
                val = o["qty"] * p                                  # value moves, cash does not
                rflow[o["origin"]] -= val
                rflow[v["origin"]] += val
            dq = v["qty"] - o["qty"]
            if abs(dq) > 1e-9:                                      # bought / sold part at the close
                st["cash"][v["origin"]] -= dq * p
        for k, o in old.items():
            if k not in open_now:                                   # closed (or converted): sold
                xp = closed_px.get(k) or (px.get(o["symbol"]) or 0.0)
                st["cash"][o["origin"]] += o["qty"] * xp
        for s in ("v1", "legacy"):
            st["cash"][s] += flows[s]
        st["v2_flows"] += flows["v2"]
    v2_cash = v2cap + st["v2_flows"] + v2_realised - v2_open_cost + st["v2_yield"]
    st["v2_cash_prev"] = v2_cash
    cash = {"v1": st["cash"]["v1"], "legacy": st["cash"]["legacy"], "v2": v2_cash}
    out = []
    for s in SYSTEMS:
        eq = mv[s] + cash[s]
        fl = flows[s] + rflow[s]
        prev_eq = st["equity"].get(s)
        if prev_eq and prev_eq > 0:
            st["nav"][s] = st["nav"][s] * (eq - fl) / prev_eq
        out.append({"date": str(day), "system": s, "mv": round(mv[s], 2), "cash": round(cash[s], 2),
                    "equity": round(eq, 2), "flow": round(fl, 2), "nav": round(st["nav"][s], 6),
                    "n": n[s], "unclassified": unclassified if s == "v1" else 0,
                    "bench": round(bench, 2) if bench else None})
        st["equity"][s] = eq
    st["rows"] = open_now
    st["last"] = str(day)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    new = pd.DataFrame(out, columns=COLS)
    if os.path.exists(OUT):
        new = pd.concat([pd.read_csv(OUT), new], ignore_index=True)
    txt = new.to_csv(index=False, lineterminator="\n")
    try:
        from io_utils import atomic_write_text
        atomic_write_text(OUT, txt)
    except Exception:
        open(OUT, "w", encoding="utf-8", newline="").write(txt)
    _save_state(st)
    return out


def series() -> pd.DataFrame:
    return pd.read_csv(OUT) if os.path.exists(OUT) else pd.DataFrame(columns=COLS)


def main() -> int:
    if "--show" in sys.argv:
        print(series().to_string(index=False))
        return 0
    if "--rebuild" in sys.argv:
        for p in (OUT, STATE):
            if os.path.exists(p):
                shutil.move(p, p + ".bak")
    rows = snapshot()
    if not rows:
        print("system equity: this date is already recorded")
        return 0
    for r in rows:
        print("%(date)s %(system)-6s equity %(equity)14.0f  mv %(mv)12.0f  cash %(cash)12.0f  nav %(nav).4f  n %(n)s" % r)
    if rows[0]["unclassified"]:
        print("UNCLASSIFIED open rows: %d - mark them on the v1-vs-v2 page" % rows[0]["unclassified"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
