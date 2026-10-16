#!/usr/bin/env python3
"""Weekly paper portfolio for the v2 core - P1, Clenow "Stocks on the Move" (16-Oct-2026).

Chosen by the pre-registered tournament (docs/PREREG_pro_systems_tournament.md) and run as a
PAPER portfolio for at least three months before any real money. Two books run side by side:
  P1   the system exactly as tested (the primary - PREREG_p1_fundamental_floor H failed)
  P1F  the same plus the point-in-time fundamental floor (no names with <= 2 of 5 RFF checks)

Rules come from pro_systems_backtest.p1_weekly - the SAME function the backtest runs - so the
paper books cannot drift from what was tested. Each run (nightly, auto-pilot Phase 12i):
  1. fills the orders decided at the last week-end close at the next session's OPEN;
  2. marks both books at every close since the last run;
  3. on the last session of a week, decides the next orders and writes the Monday order list
     reports/p1_paper/orders_<date>.md (+ csv).
Nothing here places an order with Dhan.

    python p1_paper.py            catch up to the last completed session
    python p1_paper.py --status   print both books
    python p1_paper.py --reset    start both books fresh (asks nothing - use deliberately)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import warnings

import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
STATE_DIR = os.path.join(HERE, "data", "p1_paper")
REPORT_DIR = os.path.join(HERE, "reports", "p1_paper")
# name -> p1_weekly options. P1 primary; P1F + fundamental floor (control); P1E the ensemble
# (PREREG_p1e_ensemble_forward, started 16-Oct-2026: mean rank of 60/90/120, top 25 %).
BOOKS = {"P1": {"floor": False}, "P1F": {"floor": True},
         "P1E": {"floor": False, "ensemble": True, "top_pct": 0.25}}
START_DATE = dt.date(2026, 10, 16)          # first signal close (a Friday)


def _io_write(path: str, text: str) -> None:
    try:
        from io_utils import atomic_write_text
        atomic_write_text(path, text)
    except Exception:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def load_state(name: str) -> dict:
    p = os.path.join(STATE_DIR, "%s.json" % name)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    import house_policy as hp
    cap = float(hp.sizing_capital()[0])
    return {"name": name, "start_capital": cap, "cash": cap, "pos": {}, "pending": None,
            "last_date": None, "history": [], "trades": []}


def save_state(st: dict) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    _io_write(os.path.join(STATE_DIR, "%s.json" % st["name"]), json.dumps(st, indent=1, default=str))


def live_panel() -> dict:
    """2 years of daily bars for the Nifty 500 list + the Nifty 500 index, same shape as
    v2_backtest's panel (P1 needs 260 bars of history per name)."""
    import data_provider as dp
    import v2_backtest as v2
    with open(os.path.join(HERE, "nifty500_symbols.json"), encoding="utf-8") as f:
        syms = json.load(f)
    syms = [str(s if isinstance(s, str) else (s.get("symbol") or s.get("Symbol"))).replace(".NS", "")
            for s in syms if s]
    bench = dp.fetch_ohlcv("^CRSLDX", period="2y", interval="1d", use_cache=True)
    cal = pd.to_datetime(bench.index)
    if getattr(cal, "tz", None) is not None:
        cal = cal.tz_localize(None)
    cal = cal.normalize()
    fr = {k: {} for k in ("Open", "High", "Low", "Close", "Volume")}
    for s in syms:
        try:
            d = dp.fetch_ohlcv(s, period="2y", interval="1d", use_cache=True)
        except Exception:
            continue
        if d is None or len(d) < v2.MIN_BARS:
            continue
        d = d.copy()
        d.index = pd.to_datetime(d.index)
        if getattr(d.index, "tz", None) is not None:
            d.index = d.index.tz_localize(None)
        d.index = d.index.normalize()
        d = d[~d.index.duplicated(keep="last")]
        for k in fr:
            fr[k][s] = d[k]
    p = {k: pd.DataFrame(v).reindex(cal) for k, v in fr.items()}
    b = bench["Close"].copy()
    b.index = cal
    p["bench"] = b
    return p


def _is_week_end(d: dt.date) -> bool:
    import nse_calendar as nc
    n = d + dt.timedelta(days=1)
    while not nc.is_trading_day(n):
        n += dt.timedelta(days=1)
    return n.isocalendar()[:2] != d.isocalendar()[:2]


def step(st: dict, p: dict, f: dict, g: dict, opts: dict) -> list:
    """Advance one book through every completed session after st['last_date']. Returns the
    order lines decided at the latest week-end close (empty if none)."""
    import pro_systems_backtest as ps
    import v2_backtest as v2
    O, C = p["Open"], p["Close"]
    days = [d for d in C.index if d.date() >= START_DATE and
            (st["last_date"] is None or d.date() > dt.date.fromisoformat(st["last_date"]))]
    orders = []
    for d in days:
        # 1. fill the pending orders at this open
        pend = st.get("pending")
        if pend:
            for s in pend.get("sells", []):
                q = st["pos"].pop(s, None)
                if q:
                    px = O.at[d, s] if s in O.columns and O.at[d, s] == O.at[d, s] else q["last"]
                    amt = q["sh"] * px
                    st["cash"] += amt * (1 - v2.COST)
                    st["trades"].append({"date": str(d.date()), "side": "SELL", "symbol": s, "price": round(px, 2),
                                         "shares": round(q["sh"], 2), "value": round(amt),
                                         "pnl": round(amt - q["sh"] * q["entry"])})
            for s, amt in pend.get("buys", []):
                px = O.at[d, s] if s in O.columns else float("nan")
                if not px == px or s in st["pos"]:
                    continue
                amt = min(amt, st["cash"] / (1 + v2.COST))
                if amt <= 0:
                    continue
                sh = amt / px
                st["cash"] -= amt * (1 + v2.COST)
                st["pos"][s] = {"sh": sh, "entry": px, "entry_date": str(d.date()), "last": px}
                st["trades"].append({"date": str(d.date()), "side": "BUY", "symbol": s, "price": round(px, 2),
                                     "shares": round(sh, 2), "value": round(amt)})
            st["pending"] = None
        # 2. mark
        for s, q in st["pos"].items():
            c = C.at[d, s] if s in C.columns else float("nan")
            if c == c:
                q["last"] = float(c)
        equity = st["cash"] + sum(q["sh"] * q["last"] for q in st["pos"].values())
        st["history"].append({"date": str(d.date()), "equity": round(equity), "cash": round(st["cash"]),
                              "positions": len(st["pos"]), "nifty500": round(float(p["bench"].get(d, float("nan"))), 1)})
        st["last_date"] = str(d.date())
        # 3. a week-end close decides the next orders
        if _is_week_end(d.date()):
            cl = C.loc[d]
            sells, buys, ranked = ps.p1_weekly(d, cl, f, g, equity, st["cash"],
                                               {s: q["sh"] * q["last"] for s, q in st["pos"].items()}, **opts)
            st["pending"] = {"decided": str(d.date()), "sells": sells, "buys": [[s, round(a)] for s, a in buys],
                             "regime_up": bool(g["b_up200"].get(d, False)), "eligible": int(len(ranked)),
                             # the top of the rank - what it would buy once the regime allows
                             "watch": [[s, round(float(v), 3), round(float(cl[s]), 2)] for s, v in ranked.head(20).items()]}
            rank_pos = {s: i + 1 for i, s in enumerate(ranked.index)}
            for s in sells:
                orders.append({"book": st["name"], "side": "SELL", "symbol": s, "rank": rank_pos.get(s, "-"),
                               "close": round(float(cl[s]), 2) if cl[s] == cl[s] else None,
                               "shares": round(st["pos"][s]["sh"], 2), "approx_value": round(st["pos"][s]["sh"] * st["pos"][s]["last"])})
            for s, a in buys:
                px = float(cl[s])
                orders.append({"book": st["name"], "side": "BUY", "symbol": s, "rank": rank_pos.get(s, "-"),
                               "close": round(px, 2), "shares": int(a // px), "approx_value": round(a),
                               "atr20": round(float(g["atr20"].at[d, s]), 2)})
    return orders


def run() -> int:
    import v2_backtest as v2
    import pro_systems_backtest as ps
    p = live_panel()
    f = v2.features(p)
    g = ps.pro_features(p, f)
    last = p["Close"].index[-1].date()
    all_orders, regime = [], None
    for name, opts in BOOKS.items():
        st = load_state(name)
        orders = step(st, p, f, g, opts)
        save_state(st)
        all_orders += orders
        if st.get("pending"):
            regime = st["pending"]["regime_up"]
        h = st["history"][-1] if st["history"] else {}
        print("%s: equity Rs %s · cash Rs %s · %d positions · last %s" % (
            name, f"{h.get('equity', 0):,}", f"{h.get('cash', 0):,}", h.get("positions", 0), st["last_date"]))
    if all_orders or regime is not None:
        os.makedirs(REPORT_DIR, exist_ok=True)
        tag = last.strftime("%Y%m%d")
        pd.DataFrame(all_orders).to_csv(os.path.join(REPORT_DIR, "orders_%s.csv" % tag), index=False)
        lines = ["# P1 weekly orders — decided at the close of %s, to execute at the next open" % last, ""]
        lines.append("Regime: Nifty 500 %s its 200-day SMA → %s." % (
            "ABOVE" if regime else "BELOW", "new buys allowed" if regime else "NO NEW BUYS this week (holdings may still be sold)"))
        for name in BOOKS:
            od = [o for o in all_orders if o["book"] == name]
            _lbl = {"P1": " (primary)", "P1F": " (with the fundamental floor)", "P1E": " (ensemble 60/90/120, top 25 %)"}
            lines += ["", "## %s%s" % (name, _lbl.get(name, ""))]
            stn = load_state(name)
            w = (stn.get("pending") or {}).get("watch") or []
            if w:
                lines.append("Top of the rank (%d eligible): " % (stn["pending"].get("eligible", 0))
                             + ", ".join("%s %.2f" % (x[0], x[1]) for x in w[:15]))
            if not od:
                lines.append("No orders.")
                continue
            lines += ["| side | symbol | rank | last close | shares | ≈ value |", "|---|---|---|---|---|---|"]
            for o in od:
                lines.append("| %s | %s | %s | %s | %s | ₹%s |" % (o["side"], o["symbol"], o["rank"], o["close"],
                                                                o["shares"], f"{o['approx_value']:,}"))
        _io_write(os.path.join(REPORT_DIR, "orders_%s.md" % tag), "\n".join(lines) + "\n")
        print("orders written: reports/p1_paper/orders_%s.md (%d lines)" % (tag, len(all_orders)))
    return 0


def status() -> int:
    for name in BOOKS:
        st = load_state(name)
        h = st["history"][-1] if st["history"] else {}
        print("== %s  start Rs %s  equity Rs %s  cash Rs %s  positions %d  last %s  pending %s" % (
            name, f"{st['start_capital']:,.0f}", f"{h.get('equity', st['cash']):,}", f"{st['cash']:,.0f}",
            len(st["pos"]), st["last_date"], bool(st.get("pending"))))
        for s, q in sorted(st["pos"].items()):
            print("   %-12s %8.2f sh @ %9.2f  now %9.2f  (%+.1f%%)" % (s, q["sh"], q["entry"], q["last"],
                                                                     (q["last"] / q["entry"] - 1) * 100))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()
    if a.reset:
        for name in BOOKS:
            fp = os.path.join(STATE_DIR, "%s.json" % name)
            if os.path.exists(fp):
                os.replace(fp, fp + ".reset_%s" % dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
        print("both books reset (old state kept as *.reset_<stamp>)")
        return 0
    if a.status:
        return status()
    return run()


if __name__ == "__main__":
    sys.exit(main())
