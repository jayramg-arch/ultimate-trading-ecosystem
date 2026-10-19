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


MIN_DAYS_ANNUAL = 90          # an annualised number from fewer calendar days is noise - shown as "too early"


def metrics(S: pd.DataFrame | None = None) -> dict:
    """{system: {...}} from the equity series: days, TWR (from the NAV), CAGR (>= 90 days), max
    drawdown of the NAV, annualised volatility and beta of daily NAV returns vs the Nifty 500,
    the index's return over the same days, excess return, MAR, worst calendar month, time
    invested (mean market value / equity)."""
    S = series() if S is None else S
    out = {}
    if S is None or not len(S):
        return out
    S = S.copy()
    S["date"] = pd.to_datetime(S["date"])
    for s, g in S.groupby("system"):
        g = g.sort_values("date").set_index("date")
        nav = g["nav"].astype(float)
        days = int((g.index[-1] - g.index[0]).days)
        twr = float(nav.iloc[-1] / nav.iloc[0] - 1)
        b = g["bench"].astype(float)
        bret = float(b.iloc[-1] / b.iloc[0] - 1) if b.notna().all() and b.iloc[0] else None
        cagr = (1 + twr) ** (365.0 / days) - 1 if days >= MIN_DAYS_ANNUAL else None
        dd = float((nav / nav.cummax() - 1).min())
        r = nav.pct_change().dropna()
        rb = b.pct_change().reindex(r.index)
        vol = float(r.std() * (252 ** 0.5)) if len(r) > 5 else None
        beta = float(r.cov(rb) / rb.var()) if len(r) > 20 and rb.var() and rb.var() > 0 else None
        m = nav.resample("ME").last()
        mret = m.pct_change().dropna()
        out[s] = {"start": str(g.index[0].date()), "last": str(g.index[-1].date()), "days": days,
                  "equity": float(g["equity"].iloc[-1]), "twr": twr, "cagr": cagr, "bench": bret,
                  "excess": (twr - bret) if bret is not None else None, "max_dd": dd, "vol": vol, "beta": beta,
                  "mar": (cagr / abs(dd)) if (cagr is not None and dd < 0) else None,
                  "worst_month": float(mret.min()) if len(mret) else None,
                  "invested": float((g["mv"] / g["equity"].where(g["equity"] > 0)).mean()),
                  "n": int(g["n"].iloc[-1])}
    return out


# The capital-move rule (Jay, 19-Oct-2026; docs/PREREG_capital_move.md - fixed before any live result):
MOVE_MIN_MONTHS = 6           # no earlier than 6 months after v2's first real buy
MOVE_MIN_CLOSED = 25          # and at least 25 closed v2 trades
MOVE_EDGE_PP = 5.0            # v2's annualised TWR beats v1's by >= 5 percentage points a year
MOVE_FRACTION = 1.0 / 3.0     # then move one-third of v1's capital to v2


def capital_rule(m: dict | None = None, ledger: dict | None = None, today: dt.date | None = None) -> dict:
    """Evaluate the pre-registered capital-move rule. Returns {"checks": [(label, ok|None, note)],
    "verdict": text}. ok None = cannot be judged yet."""
    import v2_ledger as vl
    m = metrics() if m is None else m
    ledger = vl.load() if ledger is None else ledger
    today = today or dt.date.today()
    dates = [str(q.get("entry_date"))[:10] for q in ledger["open"].values()] + \
            [str(c.get("entry_date"))[:10] for c in ledger["closed"]]
    first = min(dates) if dates else None
    months = ((today - dt.date.fromisoformat(first)).days / 30.44) if first else 0.0
    n_closed = len(ledger["closed"])
    v1, v2 = m.get("v1") or {}, m.get("v2") or {}
    edge = ((v2["cagr"] - v1["cagr"]) * 100) if (v2.get("cagr") is not None and v1.get("cagr") is not None) else None
    checks = [
        ("≥ %d months since v2's first real buy" % MOVE_MIN_MONTHS, months >= MOVE_MIN_MONTHS if first else False,
         ("first buy %s · %.1f months" % (first, months)) if first else "no v2 buy yet"),
        ("≥ %d closed v2 trades" % MOVE_MIN_CLOSED, n_closed >= MOVE_MIN_CLOSED, "%d closed" % n_closed),
        ("v2's annualised TWR beats v1-system's by ≥ %g pp" % MOVE_EDGE_PP,
         (edge >= MOVE_EDGE_PP) if edge is not None else None,
         ("v2 %+.1f %% vs v1 %+.1f %% a year (%+.1f pp)" % (v2["cagr"] * 100, v1["cagr"] * 100, edge))
         if edge is not None else "needs %d days of both series" % MIN_DAYS_ANNUAL),
        ("v2's max drawdown no worse than v1's", (v2["max_dd"] >= v1["max_dd"]) if (v2 and v1) else None,
         ("v2 %.1f %% vs v1 %.1f %%" % (v2["max_dd"] * 100, v1["max_dd"] * 100)) if (v2 and v1) else "no series yet"),
        ("v2 beat the Nifty 500 over the same days", (v2["excess"] > 0) if v2.get("excess") is not None else None,
         ("v2 %+.1f %% vs index %+.1f %%" % (v2["twr"] * 100, v2["bench"] * 100)) if v2.get("excess") is not None else "no series yet"),
    ]
    oks = [c[1] for c in checks]
    if all(o is True for o in oks):
        verdict = "MOVE one-third of v1's capital to v2 (all five conditions hold)"
    elif any(o is False for o in oks[2:]):
        verdict = "NO MOVE - re-check next quarter (a performance condition fails)"
    else:
        verdict = "NOT YET - re-check quarterly once the minimums are met"
    return {"checks": checks, "verdict": verdict, "first_buy": first, "months": months, "closed": n_closed}


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
