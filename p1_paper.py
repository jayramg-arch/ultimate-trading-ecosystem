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
         "P1E": {"floor": False, "ensemble": True, "top_pct": 0.25},
         # 17-Oct-2026 (Jay, Doc 41): the v2 system routed through the reviewer - P1E's rules, but a
         # buy is skipped when the reviewer's latest ruling on the name since the decision is
         # WAIT or PASS. P1E vs P1ER measures what the reviewer adds to the v2 system.
         "P1ER": {"floor": False, "ensemble": True, "top_pct": 0.25, "reviewed": True},
         # 18-Oct-2026 (PREREG_v2_house_rules, engine v2_house.py): P1ES = P1E + a resting 4xATR14
         # disaster stop (Q5); V2H = P1E + the house rules Jay kept on 18-Oct (Wednesday rebalance, the
         # stop, tax-aware runners + risk trims, ETF sleeve). The exposure tiers and F&O priority were
         # DROPPED after the registered run showed they carry the cost. V2H obeys the reviewer as a
         # one-week deferral. P1E stays the candidate; both run forward.
         "P1ES": {"house": "P1ES"},
         "V2H": {"house": "V2H", "reviewed": True}}
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


def live_panel(extra: list | None = None) -> dict:
    """2 years of daily bars for the Nifty 500 list + the Nifty 500 index, same shape as
    v2_backtest's panel (P1 needs 260 bars of history per name)."""
    import data_provider as dp
    import v2_backtest as v2
    with open(os.path.join(HERE, "nifty500_symbols.json"), encoding="utf-8") as f:
        syms = json.load(f)
    syms = [str(s if isinstance(s, str) else (s.get("symbol") or s.get("Symbol"))).replace(".NS", "")
            for s in syms if s]
    syms += [s for s in (extra or []) if s not in syms]
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
    opts = dict(opts)
    reviewed = opts.pop("reviewed", False)
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
            rulings = {}
            if reviewed:
                try:
                    import v2_core
                    rulings = v2_core.latest_reviews(pend.get("decided"))
                except Exception:
                    rulings = {}
            for s, amt in pend.get("buys", []):
                if reviewed and rulings.get(s) in ("WAIT", "PASS"):
                    st["trades"].append({"date": str(d.date()), "side": "SKIP", "symbol": s,
                                         "reason": "reviewer " + rulings[s]})
                    continue
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


def summary_text(test: bool = False) -> str:
    """The Friday Telegram summary (16-Oct-2026, Jay): each book's equity and orders, the regime,
    the Nifty 500 over the same span and the top of the rank. Plain text, one screen."""
    def inr(v):
        s_ = "%d" % round(abs(v))
        if len(s_) > 3:
            head, tail = s_[:-3], s_[-3:]
            parts = []
            while len(head) > 2:
                parts.insert(0, head[-2:])
                head = head[:-2]
            if head:
                parts.insert(0, head)
            s_ = ",".join(parts) + "," + tail
        return ("-" if v < 0 else "") + "Rs " + s_
    lines, regime, decided, watch, n500 = [], None, None, [], None
    # v2 system first (P1E, then P1ER through the reviewer), research controls after (17-Oct-2026)
    for name in [b for b in ("P1E", "P1ER", "P1ES", "V2H", "P1", "P1F") if b in BOOKS]:
        st = load_state(name)
        h = st["history"][-1] if st["history"] else {}
        eq = h.get("equity", st["cash"])
        pend = st.get("pending") or {}
        if pend and name in ("P1E", "P1ER", "P1", "P1F"):
            regime, decided = pend.get("regime_up"), pend.get("decided")
            if not watch:
                watch = [w[0] for w in pend.get("watch", [])[:8]]
        nb = len(pend.get("buys", [])) if pend else 0
        ns = len(pend.get("sells", [])) if pend else 0
        lines.append("%s  %s (%+.2f%%)  %d held · next: buy %d / sell %d" % (
            name, inr(eq), (eq / st["start_capital"] - 1) * 100, len(st["pos"]), nb, ns))
        if pend and name == "V2H" and pend.get("fill"):
            lines.append("    decided %s, fills at the open of %s" % (pend.get("decided"), pend.get("fill")))
        if st["history"] and len(st["history"]) > 1 and n500 is None:
            a, b = st["history"][0].get("nifty500"), st["history"][-1].get("nifty500")
            if a and b:
                n500 = (b / a - 1) * 100
    head = "%sv2 PAPER BOOKS - week to %s" % ("[TEST] " if test else "", decided or "-")
    rg = ("Nifty 500 ABOVE its 200-day SMA - buys allowed" if regime else
          "Nifty 500 BELOW its 200-day SMA - no new buys")
    body = [head, rg] + lines
    if n500 is not None:
        body.append("Nifty 500 over the same span: %+.2f%%" % n500)
    if watch:
        body.append("Top of the rank: " + ", ".join(watch))
    body.append("Orders: reports/p1_paper/orders_%s.md (paper only - nothing goes to Dhan)"
                % (decided or "").replace("-", ""))
    return "\n".join(body)


def send_summary(test: bool = False) -> bool:
    txt = summary_text(test)
    print(txt)
    if os.getenv("P1_TELEGRAM", "1") == "0":
        return False
    try:
        import s4_review
        return bool(s4_review.telegram(txt))
    except Exception as e:
        print("telegram failed: %s" % e)
        return False


def write_board(p, f, g) -> None:
    """data/v2/board.csv - the v2 system's ranked list at the last close (P1E's rules): rank,
    score, close, ATR, whether it is inside the top-25 % cut, held by P1E, and the weekly action."""
    import math
    import v2_core
    import pro_systems_backtest as ps
    d = p["Close"].index[-1]
    cl = p["Close"].loc[d]
    st = load_state(v2_core.PRIMARY)
    held = set(st["pos"])
    _s, _b, ranked = ps.p1_weekly(d, cl, f, g, 1.0, 0.0, {s: 0.0 for s in held}, ensemble=True, top_pct=0.25)
    n = len(ranked)
    cut = max(1, math.ceil(0.25 * n))
    pend = st.get("pending") or {}
    buys = {b[0] for b in pend.get("buys", [])}
    sells = set(pend.get("sells", []))
    try:                                  # F&O tag - display only (18-Oct: the buy priority was dropped)
        _fh = pd.read_csv(os.path.join(HERE, "data", "fno_history.csv"), usecols=["date", "symbol"])
        fno = set(_fh.loc[_fh["date"] == _fh["date"].max(), "symbol"].astype(str).str.upper())
    except Exception:
        fno = set()
    rows = []
    for i, (sym, sc) in enumerate(ranked.items(), 1):
        rows.append({"as_of": str(d.date()), "rank": i, "symbol": sym, "score": round(float(sc), 4),
                     "close": round(float(cl[sym]), 2), "atr20": round(float(g["atr20"].at[d, sym]), 2),
                     "in_cut": i <= cut, "held": sym in held, "fno": sym in fno, "eligible": n,
                     "regime_up": bool(g["b_up200"].get(d, False)),
                     "action": "BUY" if sym in buys else ("SELL" if sym in sells else ("HOLD" if sym in held else "-"))})
    for sym in sells - set(ranked.index):
        rows.append({"as_of": str(d.date()), "rank": None, "symbol": sym, "score": None, "close": None,
                     "atr20": None, "in_cut": False, "held": True, "eligible": n,
                     "regime_up": bool(g["b_up200"].get(d, False)), "action": "SELL"})
    os.makedirs(v2_core.V2_DIR, exist_ok=True)
    _io_write(v2_core.BOARD, pd.DataFrame(rows).to_csv(index=False, lineterminator="\n"))
    try:                                  # one copy per session: the Rank & Universe page diffs them (19-Oct)
        _hd = os.path.join(v2_core.V2_DIR, "board_history")
        os.makedirs(_hd, exist_ok=True)
        _io_write(os.path.join(_hd, "board_%s.csv" % d.date()), pd.DataFrame(rows).to_csv(index=False, lineterminator="\n"))
    except Exception as e:
        print("v2 board history not written: %s" % e)
    print("v2 board: %d ranked (top-25%% cut %d) as of %s" % (n, cut, d.date()))


# ── the v2 workflow for REAL money (18-Oct-2026, Doc 41 §10) ─────────────────
V2_WATCHLIST = os.path.join(HERE, "FINAL_V2_WATCHLIST.csv")      # -> TradingView "V2_System-DDMONYY"
V2_STATUS = os.path.join(HERE, "data", "v2", "addon_status.txt")  # -> Add-ons M2 input (tv_push_addons)
V2_REGIME = os.path.join(HERE, "data", "v2", "regime_last.json")


def _inr(v: float) -> str:
    """Indian grouping, the house format: Rs 10,00,000."""
    n = int(round(abs(v)))
    s_ = str(n)
    if len(s_) > 3:
        head, tail = s_[:-3], s_[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s_ = ",".join(parts) + "," + tail
    return ("-" if v < 0 else "") + "₹" + s_


def v2_capital() -> float:
    """Real money in the v2 system: one-third of the house sizing capital (Doc 40 §3, Jay 18-Oct);
    V2_CAPITAL in .env overrides."""
    import house_policy as hp
    v = os.getenv("V2_CAPITAL")
    return float(v) if v else float(hp.sizing_capital()[0]) / 3.0


def real_v2_positions(C, d) -> tuple[dict, float]:
    """Your real v2 book from the v2 ledger (v2_ledger.py - v2's OWN shares, including slices of
    holdings shared with the current system), reconciled against the journal first: a holding no
    longer OPEN in the journal was sold in full, so its slice is closed. Returns (positions in the
    shape decide() reads, realised P&L of closed slices)."""
    import sqlite3
    import journal_path as jp
    import v2_ledger as vl
    import v2_house as vh
    try:
        con = sqlite3.connect(jp.JOURNAL_DB)
        J = pd.read_sql_query("SELECT symbol, status, quantity, exit_price, exit_date FROM journal", con)
        con.close()
        for n in vl.reconcile(J):
            print("v2 ledger: " + n)
    except Exception as e:
        print("v2 ledger: journal unreadable (%s) - not reconciled" % e)
    pool = vh.etf_pool()
    pos = {}
    for s, q in vl.load()["open"].items():
        last = float(C.at[d, s]) if s in C.columns and C.at[d, s] == C.at[d, s] else float(q["entry"])
        pos[s] = {"sh": float(q["sh"]), "entry": float(q["entry"]), "entry_date": pd.Timestamp(q["entry_date"]),
                  "last": last, "kind": "etf" if s in pool else "stock", "stop": float(q.get("stop") or 0) or None,
                  "shared": bool(q.get("shared"))}
    return pos, vl.realised()


def v2_exit_watch(real: dict, C, hctx: dict, d, ranked, n_cut: int, uni: set, surv: dict, etf_pool: set) -> list:
    """One line per REAL v2 holding that fails one of Clenow's exits at today's close: below its
    100-day average, a one-day move beyond 15 %, ranked outside the buy cut (stocks), not in the
    Nifty 500, or under NSE surveillance. Empty = nothing to flag."""
    out = []
    g = hctx["g"]
    for s, q in sorted(real.items()):
        if s not in C.columns:
            out.append("%s: no price today - check it by hand" % s)
            continue
        why = []
        c = float(C.at[d, s]) if C.at[d, s] == C.at[d, s] else float("nan")
        ma = float(g["sma100"].at[d, s]) if s in g["sma100"].columns else float("nan")
        if c == c and ma == ma and c < ma:
            why.append("closed %s below its 100-day average %s (%.1f %%)" % (_inr(c), _inr(ma), (c / ma - 1) * 100))
        prev = C[s].loc[:d].dropna()
        if len(prev) >= 2:
            mv = float(prev.iloc[-1] / prev.iloc[-2] - 1)
            if abs(mv) > 0.15:
                why.append("moved %+.1f %% today (beyond 15 %% - ineligible for 90 days)" % (mv * 100))
        if s not in etf_pool:
            rk = ranked.get(s) if len(ranked) else None
            if n_cut and (rk is None or rk != rk):
                why.append("not ranked (ineligible today)")
            elif n_cut and rk > n_cut:
                why.append("ranked %d, outside the cut of %d" % (int(rk), n_cut))
            if uni and s not in uni:
                why.append("no longer in the Nifty 500")
        if s in surv:
            why.append("NSE surveillance: %s" % surv[s])
        if why:
            out.append("%s: %s" % (s, "; ".join(why)))
    return out


def v2_workflow(p, hctx, decided_today: bool) -> list:
    """Orders for YOUR v2 book (on a V2H decision day), the TradingView watchlist, the Add-ons
    status line and the regime-turn alert. Returns the order-sheet lines for the real book."""
    import v2_house as vh
    d = p["Close"].index[-1]
    C = p["Close"]
    st = load_state("V2H")
    pend = st.get("pending") or {}
    real, realised = real_v2_positions(C, d)
    cap = v2_capital()
    invested = sum(q["sh"] * q["last"] for q in real.values())
    cost = sum(q["sh"] * q["entry"] for q in real.values())
    equity = cap + realised + (invested - cost)
    cash = equity - invested
    lines, rows, status = [], [], {}
    a14 = hctx["f"]["atr"].loc[d]
    r = None
    # names the CURRENT system holds: one owner per holding (Doc 42 §7 decision 2) - v2 does not open
    # a second position; its pick is a confirmation for the current system's pyramid ladder instead
    v1_held = set()
    try:
        import trade_class as _tc
        import house_policy as _hpx
        _j = _tc.open_positions()
        v1_held = set(_j.loc[~_j["setup"].map(_hpx.is_v2), "symbol"].astype(str).str.upper())
    except Exception:
        pass
    if decided_today:
        # Jay 18-Oct (Doc 42 §8 D2): v2 MAY pyramid onto a current-system holding - no exclusion
        r = vh.decide(d, hctx, vh.BOOK_FLAGS["V2H"], equity, cash, real, int(st.get("n_dec", 1)))
        lines += ["", "## YOUR v2 ORDERS — real money (v2 capital %s, equity %s, %d held)" % (
            _inr(cap), _inr(equity), len(real)),
                  "Decided at the close of %s · place at the open of %s · nothing is sent to Dhan." % (
                      pend.get("decided"), pend.get("fill")),
                  "Check the reviewer's ruling on the 🧭 v2 page first: WAIT / PASS = skip that buy this week.",
                  "Order type (Doc 42 D3): a LIMIT at Tuesday's close + 1 %, cancelled if unfilled by 10:00.", ""]
        if not (r["sells"] or r["trims"] or r["buys"] or r.get("adds")):
            lines.append("No orders for your book this week.")
        else:
            # Clenow's rules (Jay 19-Oct): no stop, no targets. A buy of a name the current system
            # holds is a CONVERT (PREREG_pyramid_slices_vs_convert): v2 takes the holding, resized
            # to its target at once; the v1 stop order is cancelled.
            lines += ["| order | symbol | shares | ≈ value | note |", "|---|---|---|---|---|"]
            cash_in, cash_out = 0.0, 0.0
            for s in r["sells"]:
                v = real[s]["sh"] * real[s]["last"]
                cash_in += v
                lines.append("| SELL | %s | %d | %s | v2 exit · record: `python v2_take.py %s --sell --price P` |"
                             % (s, real[s]["sh"], _inr(v), s))
            for s, sh in r["trims"]:
                v = sh * real[s]["last"]
                cash_in += v
                lines.append("| RESIZE ↓ | %s | %d | %s | back to equal risk · `v2_take.py %s --sell --price P --qty %d` |"
                             % (s, int(sh), _inr(v), s, int(sh)))
            rung, held_q = {}, {}
            try:                          # the current system's ladder rung per holding (Phase 5, last night)
                _pp = pd.read_csv(os.path.join(HERE, "FINAL_Portfolio_Picks.csv"))
                rung = dict(zip(_pp["Symbol"].astype(str).str.upper(), _pp["Pyr_Class"].astype(str)))
            except Exception:
                pass
            try:
                held_q = dict(zip(_j["symbol"].astype(str).str.upper(), pd.to_numeric(_j["quantity"], errors="coerce")))
            except Exception:
                pass
            for s, amt, k in r["buys"]:
                px = float(C.at[d, s])
                tgt = int(amt // px)
                if s in v1_held:          # CONVERT a current-system holding
                    q = int(held_q.get(s) or 0)
                    rg = rung.get(s, "?")
                    if q >= tgt:
                        act = "SELL %d of your %d at the open, keep %d" % (q - tgt, q, tgt)
                        cash_in += (q - tgt) * px
                        rec = "--keep %d" % tgt
                    else:
                        act = "keep all %d, BUY %d more" % (q, tgt - q)
                        cash_out += (tgt - q) * px
                        rec = "--keep %d --bought %d" % (q, tgt - q)
                    lines.append("| CONVERT | %s | %d | %s | %s · CANCEL the v1 stop order · current-system rung "
                                 "**%s** · record: `python v2_take.py %s --convert --price P %s` |"
                                 % (s, tgt, _inr(tgt * px), act, rg, s, rec))
                else:
                    cash_out += tgt * px
                    lines.append("| BUY%s | %s | %d | %s | no stop · record: `python v2_take.py %s --price P --qty Q` |"
                                 % (" ETF" if k == "etf" else "", s, tgt, _inr(tgt * px), s))
            for s, amt in r.get("adds", []):
                px = float(C.at[d, s])
                cash_out += amt
                lines.append("| RESIZE ↑ | %s | %d | %s | back to equal risk · `v2_take.py %s --price P --qty %d` |"
                             % (s, int(amt // px), _inr(amt), s, int(amt // px)))
            lines += ["", "Cash: buys need %s, sales release %s → have **%s** free at Dhan before the open "
                          "(sale proceeds may not be usable the same morning - fund the buys in full to be safe)."
                      % (_inr(cash_out), _inr(cash_in), _inr(max(0.0, cash_out)))]
        if r.get("skipped"):
            lines.append("Skipped by the borrowed v1 rules: " + ", ".join("%s (%s)" % kv for kv in r["skipped"].items()))
        if r.get("etf_premium_out"):
            lines.append("Out of the ETF pool on NAV premium: " + ", ".join(r["etf_premium_out"]))
        if r.get("surveillance_out"):
            lines.append("Out of the pool on NSE surveillance (no buy; a holding is sold): " +
                         ", ".join("%s (%s)" % kv for kv in sorted(r["surveillance_out"].items())))
        if hctx.get("surv_out") is None:
            lines.append("⚠ NSE surveillance list unavailable (%s) - check ASM / price band on nseindia.com "
                         "before placing a buy." % hctx.get("surv_note", "unknown"))
    # the TradingView list + the chart status: buys, sells, your holdings, then the top of the rank
    ranked = pd.Series(dtype=float)
    try:
        import v2_core
        b = v2_core.board()
        ranked = b.set_index("symbol")["rank"] if len(b) else ranked
        n_el = int(b["eligible"].iloc[0]) if len(b) else 0
        n_cut = int(b["in_cut"].astype(str).str.lower().eq("true").sum()) if len(b) else 0
    except Exception:
        n_el, n_cut = 0, 0
    try:                                 # Nifty 500 membership (refreshed nightly, Phase 0.6)
        _uni = {x.replace(".NS", "").upper() for x in json.load(open(os.path.join(HERE, "nifty500_symbols.json")))}
    except Exception:
        _uni = set()
    _etf_pool = set(vh.etf_pool())
    _surv = hctx.get("surv_out") or {}
    buys = [x[0] for x in pend.get("buys", [])] + ([s for s, _a, _k in r["buys"]] if r else [])
    sells = list(pend.get("sells", [])) + (list(r["sells"]) if r else [])
    held_paper = set(st.get("pos", {}))
    order = []
    for sec, names in (("BUY", buys), ("SELL", sells), ("HOLD", list(real) + sorted(held_paper)),
                       ("WATCH", list(ranked.sort_values().index[:30]) if len(ranked) else [])):
        for s in names:
            if s not in [o[0] for o in order]:
                order.append((s, sec))
    as_of = str(d.date())
    for s, sec in order:
        rk = ranked.get(s)
        q = real.get(s) or st.get("pos", {}).get(s) or {}
        stp = q.get("stop")
        if stp is None and sec == "BUY" and s in C.columns and vh.BOOK_FLAGS["V2H"].get("stop"):
            stp = float(C.at[d, s]) - vh.H["stop_atr"] * float(a14.get(s, float("nan")))
        rows.append({"Symbol": s, "Section": sec, "Rank": "" if rk is None or rk != rk else int(rk),
                     "Stop": "" if stp is None or stp != stp else round(float(stp), 2),
                     "Held": "real" if s in real else ("paper" if s in held_paper else "")})
        # fields: rank/eligible ; group ; stop (empty - v2 has none) ; held ; buy cut ; flags
        # flags: X = not in the Nifty 500 (sold at the next rebalance), S = NSE surveillance,
        #        1 = the CURRENT system (v1) holds it - a v2 buy would CONVERT it (19-Oct)
        _fl = ("X" if (_uni and s not in _uni and s not in _etf_pool) else "") + ("S" if s in _surv else "") \
            + ("1" if s in v1_held else "")
        status[s] = "%s/%s;%s;%s;%s;%s;%s" % ("" if rk is None or rk != rk else int(rk), n_el, sec,
                                              "" if stp is None or stp != stp else "%.2f" % stp,
                                              "real" if s in real else ("paper" if s in held_paper else ""),
                                              n_cut or "", _fl)
    _io_write(V2_WATCHLIST, pd.DataFrame(rows, columns=["Symbol", "Section", "Rank", "Stop", "Held"]).to_csv(index=False, lineterminator="\n"))
    items = []
    for s, v in status.items():
        items.append("%s:%s" % (s, v))
        alias = s.replace("-", "_").replace("&", "_")
        if alias != s:
            items.append("%s:%s" % (alias, v))
    os.makedirs(os.path.dirname(V2_STATUS), exist_ok=True)
    fill = pend.get("fill") or ""
    _io_write(V2_STATUS, "_ASOF:%s;%s,%s\n" % (as_of, fill, ",".join(items)))
    # the regime-turn alert: the day the Nifty 500 crosses its 200-day SMA, say so once
    up = bool(hctx["g"]["b_up200"].get(d, False))
    try:
        last = json.load(open(V2_REGIME, encoding="utf-8")).get("up")
    except Exception:
        last = None
    if last is not None and bool(last) != up:
        msg = ("v2: Nifty 500 closed %s its 200-day SMA on %s. %s" % (
            "ABOVE" if up else "BELOW", as_of,
            "New v2 buys are allowed from the next Wednesday rebalance." if up else
            "No new v2 buys until it closes back above; holdings stay and follow Clenow's exits (rank, 100-day average, 15 % gap, index, surveillance)."))
        print(msg)
        if os.getenv("P1_TELEGRAM", "1") != "0":
            try:
                import s4_review
                s4_review.telegram(msg)
            except Exception as e:
                print("regime alert not sent: %s" % e)
    _io_write(V2_REGIME, json.dumps({"up": up, "date": as_of}))
    # EXIT WATCH (Jay 19-Oct-2026): v2 holdings have no stop, so every night each REAL holding is
    # read against Clenow's exits. v2 only acts on the Tuesday close - this is the heads-up.
    watch = v2_exit_watch(real, C, hctx, d, ranked, n_cut, _uni, _surv, _etf_pool)
    if watch:
        msg = "v2 exit watch (%s close) - sold at the next rebalance open unless it recovers by the decision close (Tuesday, or Monday when Tuesday is a holiday):\n%s" % (
            as_of, "\n".join("• " + w for w in watch))
        print(msg)
        lines += ["", "## v2 EXIT WATCH", ""] + ["- " + w for w in watch]
        if os.getenv("P1_TELEGRAM", "1") != "0":
            try:
                import s4_review
                s4_review.telegram(msg)
            except Exception as e:
                print("exit watch not sent: %s" % e)
    print("v2 watchlist: %d names (%s) · status line %d items · real book %d held, equity %s" % (
        len(rows), ", ".join("%s %d" % (k, sum(1 for _s, x in order if x == k)) for k in ("BUY", "SELL", "HOLD", "WATCH")),
        len(items), len(real), _inr(equity)))
    return lines


def run() -> int:
    import v2_backtest as v2
    import pro_systems_backtest as ps
    import v2_house as vh
    etfs = list(vh.etf_pool())
    p = live_panel(etfs)
    etfs = [s for s in etfs if s in p["Close"].columns]
    stocks = [s for s in p["Close"].columns if s not in set(etfs)]
    f = v2.features(p)
    f["has"].loc[:, etfs] = False            # ETFs never enter the STOCK rank (P1/P1E/house alike)
    g = ps.pro_features(p, f)
    hctx = None
    last = p["Close"].index[-1].date()
    all_orders, regime = [], None
    new_decision = False
    decided_books = []
    for name, opts in BOOKS.items():
        st = load_state(name)
        before = (st.get("pending") or {}).get("decided")
        if opts.get("house"):
            if hctx is None:
                hctx = vh.live_context(p, f, g, stocks, etfs)
            orders = vh.step_live(st, p, hctx, vh.BOOK_FLAGS[opts["house"]], START_DATE,
                                  reviewed=bool(opts.get("reviewed")))
        else:
            orders = step(st, p, f, g, opts)
        if (st.get("pending") or {}).get("decided") not in (None, before):
            new_decision = True
            decided_books.append(name)
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
            _lbl = {"P1": " (research control - the tournament winner)", "P1F": " (research control - fundamental floor)",
                    "P1E": " (v2 primary - ensemble 60/90/120, top 25 %)", "P1ER": " (v2 + reviewer - P1E skipping WAIT/PASS)",
                    "P1ES": " (P1E + 4×ATR disaster stop)",
                    "V2H": " (house rules - Wednesday rebalance, 4×ATR stop, tax-aware runners + trims, ETF sleeve)"}
            lines += ["", "## %s%s" % (name, _lbl.get(name, ""))]
            stn = load_state(name)
            pn = stn.get("pending") or {}
            if pn.get("fill"):
                lines.append("Decided %s, fills at the open of %s%s." % (pn.get("decided"), pn.get("fill"),
                             (" · regime score %s (%s)" % (pn["score"], pn.get("tier"))) if pn.get("score") is not None else ""))
            if pn.get("etf_watch"):
                lines.append("ETF rank: " + ", ".join("%s %.2f" % (x[0], x[1]) for x in pn["etf_watch"]))
            if pn.get("etf_premium_out"):
                lines.append("Out of the ETF pool on NAV premium: " + ", ".join(
                    "%s (%s)" % (k, v) for k, v in pn["etf_premium_out"].items()))
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
    try:
        write_board(p, f, g)
    except Exception as e:
        print("v2 board not written: %s" % e)
    try:                                  # the real-money workflow (Doc 41 §10)
        real_lines = v2_workflow(p, hctx, "V2H" in decided_books) if hctx is not None else []
        if real_lines:
            fp = os.path.join(REPORT_DIR, "orders_%s.md" % last.strftime("%Y%m%d"))
            prev = open(fp, encoding="utf-8").read() if os.path.exists(fp) else ""
            _io_write(fp, prev + "\n".join(real_lines) + "\n")
    except Exception as e:
        print("v2 workflow failed: %s" % e)
    if os.getenv("V2_PUSH_ADDONS", "1") != "0":
        try:                              # the chart's v2 status line (Add-ons M2) - best effort
            import tv_push_addons
            tv_push_addons.main_push()
        except Exception as e:
            print("Add-ons v2 status not pushed: %s" % e)
    if new_decision:                      # a decision was made in THIS run - say so once
        try:                              # reviews: P1E's Friday buys (P1ER) and V2H's Tuesday buys
            import v2_core
            syms = []
            for b in ("P1E", "V2H"):
                if b in decided_books:
                    syms += [x[0] for x in (load_state(b).get("pending") or {}).get("buys", []) if x[0] not in syms]
            print(v2_core.queue_reviews(syms))
        except Exception as e:
            print("v2 reviews not queued: %s" % e)
        send_summary()
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
    ap.add_argument("--telegram-test", action="store_true", help="send the current summary, marked [TEST]")
    a = ap.parse_args()
    if a.telegram_test:
        return 0 if send_summary(test=True) else 1
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
