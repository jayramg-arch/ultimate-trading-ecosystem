#!/usr/bin/env python3
"""Tournament of professional trading systems (pre-registered: docs/PREREG_pro_systems_tournament.md).

    python pro_systems_backtest.py --plumbing   2018-06..2018-12, trade COUNTS only
    python pro_systems_backtest.py --run        THE run - once
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import v2_backtest as v2   # noqa: E402  (same panel, engine pieces, costs and metrics)

OUT = os.path.join(HERE, "reports", "pro_systems")
START, SPLIT, END = v2.START, v2.SPLIT, v2.END
LIQ = v2.TURNOVER_MIN


def pro_features(p: dict, f: dict) -> dict:
    C, H, L, V = p["Close"], p["High"], p["Low"], p["Volume"]
    prev = C.shift()
    tr = np.maximum(H - L, np.maximum((H - prev).abs(), (L - prev).abs()))
    g = {}
    g["atr20"] = tr.ewm(alpha=1 / 20, adjust=False).mean()
    g["sma50"], g["sma100"] = C.rolling(50).mean(), C.rolling(100).mean()
    g["sma150"], g["sma200"] = C.rolling(150).mean(), C.rolling(200).mean()
    g["liq"] = (C * V).rolling(50).median() >= LIQ
    # Clenow: annualised exponential-regression slope x R^2 over 90 sessions
    y = np.log(C)
    t = pd.Series(np.arange(len(C), dtype=float), index=C.index)
    for lb in (60, 90, 120):                       # 90 = P1; 60/120 = PREREG_p1_robustness
        my, mt = y.rolling(lb).mean(), t.rolling(lb).mean()
        cov = y.mul(t, axis=0).rolling(lb).mean() - my.mul(mt, axis=0)
        var_t = t.rolling(lb).var(ddof=0)
        sd_y = y.rolling(lb).std(ddof=0)
        slope = cov.div(var_t, axis=0)
        r = cov.div(sd_y.mul(np.sqrt(var_t), axis=0))
        g["clenow%d" % lb] = (np.exp(slope * 252) - 1) * r ** 2
    g["clenow"] = g["clenow90"]
    g["gap90"] = C.pct_change().abs().rolling(90).max() > 0.15
    # Turtle
    g["hi55"] = C.shift(1).rolling(55).max()
    g["lo20"] = C.shift(1).rolling(20).min()
    # SEPA / CANSLIM
    g["hi50"] = C.shift(1).rolling(50).max()
    g["vavg50"] = V.shift(1).rolling(50).mean()
    g["lo52"] = C.rolling(252, min_periods=200).min()
    g["hi52"] = C.rolling(252, min_periods=200).max()
    rsw = 0.4 * (C / C.shift(63) - 1) + 0.2 * (C / C.shift(126) - 1) + 0.2 * (C / C.shift(189) - 1) \
        + 0.2 * (C / C.shift(252) - 1)
    g["rs"] = rsw.where(f["has"]).rank(axis=1, pct=True) * 100
    g["mom12_1"] = C.shift(21) / C.shift(252) - 1
    b = p["bench"]
    g["b_up200"] = b > b.rolling(200).mean()
    g["b_up50"] = b > b.rolling(50).mean()
    return g


_TABLES: dict = {}
FLOOR_START = pd.Timestamp("2024-06-03")


def weak_fundamentals(sym: str, d) -> bool:
    """PREREG_p1_fundamental_floor: point-in-time RFF read (screener_history.rff_pit); WEAK =
    quality OK and <= 2 of the 5 checks passed. A read that is not OK never excludes."""
    import screener_history as sh
    if sym not in _TABLES:
        html = sh.fetch_page(sym)
        _TABLES[sym] = sh.parse_tables(html) if html else None
    t = _TABLES[sym]
    if t is None:
        return False
    r = sh.rff_pit(t, d)
    return r["quality"] == "OK" and r["passed"] <= 2


def p1_weekly(d, cl, f, g, equity, cash, held_value: dict, floor: bool = False, bff: str | None = None,
              lookback: int = 90, top_pct: float = 0.20, risk: float = 0.001, ensemble: bool = False):
    """THE P1 weekly rules (Clenow, Stocks on the Move) - one function shared by the backtest
    and the live paper portfolio (p1_paper.py), so the two cannot drift.

    Returns (sells, buys, ranked): sells = held names to sell at the next open; buys = [(sym,
    rupee amount)] in rank order while cash lasts (new buys only when the Nifty 500 is above
    its 200-day SMA); ranked = the eligible list, best first, as a Series of scores."""
    el = (cl > g["sma100"].loc[d]) & ~g["gap90"].loc[d] & g["liq"].loc[d] & f["has"].loc[d]
    if floor:
        for s in el[el].index:
            if weak_fundamentals(s, d):
                el[s] = False
    if bff in ("weak", "strong"):                 # PREREG_p1_bff_floor
        for s in el[el].index:
            score, qual = bff_grade(s, d)
            if score is None or qual == "INSUFFICIENT":
                continue
            if (bff == "weak" and qual == "WEAK") or (bff == "strong" and score < 4):
                el[s] = False
    if ensemble:      # P1E (PREREG_p1e_ensemble_forward): mean percentile rank over 60/90/120
        sc = pd.DataFrame({lb: g["clenow%d" % lb].loc[d][el] for lb in (60, 90, 120)}).dropna()
        sc = sc.rank(pct=True).mean(axis=1).sort_values(ascending=False)
    else:
        sc = g["clenow%d" % lookback].loc[d][el].dropna().sort_values(ascending=False)
    top = set(sc.index[:max(1, math.ceil(top_pct * len(sc)))])
    sells = [s for s in held_value if s not in top]
    buys = []
    if bool(g["b_up200"].get(d, False)):
        cash = cash + sum(held_value[s] for s in sells) * (1 - v2.COST)
        for s in sc.index:
            if s in held_value:
                continue
            a = _sizes(equity, cl[s], g["atr20"].at[d, s], risk)
            if a <= 0 or a > cash:
                break
            buys.append((s, a))
            cash -= a * (1 + v2.COST)
    return sells, buys, sc


_FIN: dict = {}


def bff_grade(sym: str, d) -> tuple:
    """PREREG_p1_bff_floor: (score or None, quality) of the ANNUAL point-in-time BFF on date d."""
    import fundamental_replay as fr
    if sym not in _FIN:
        try:
            import sector_lookup as sl
            si = (sl.get_sector_index(sym) or "").upper()
            _FIN[sym] = ("BANKNIFTY" in si) or ("FINANCE" in si) or ("FINSERV" in si)
        except Exception:
            _FIN[sym] = False
    try:
        r = fr.bff_as_of(sym, str(pd.Timestamp(d).date()), is_financial=_FIN[sym], basis="annual")
    except Exception:
        return None, "INSUFFICIENT"
    return r.get("score"), str(r.get("quality") or "INSUFFICIENT")


def _sizes(equity, px, atr, risk):
    return equity * risk / atr * px if (atr == atr and atr > 0 and px == px) else 0.0


def run_sys(name, p, f, g, start, end, params: dict | None = None):
    O, L, C = p["Open"], p["Low"], p["Close"]
    days = C.index[(C.index >= start) & (C.index <= end)]
    wk, mo = v2._week_ends(days), set(pd.Series(days, index=days).groupby(days.to_period("M")).max())
    bk = v2.Book(1.0)
    pend_sell, pend_buy, eq = [], [], []
    for d in days:
        for s in pend_sell:
            if s in bk.pos:
                px = O.at[d, s]
                bk.sell(s, px if px == px else bk.pos[s]["last"])
        for s, amt, stop in pend_buy:
            px = O.at[d, s]
            if px == px and s not in bk.pos and amt > 0:
                st = None
                if stop:
                    st = px - stop[1] if stop[0] == "abs" else px * (1 - stop[1])
                bk.buy(s, px, amt, st)
        pend_sell, pend_buy = [], []
        for s in list(bk.pos):
            q, lo, op = bk.pos[s], L.at[d, s], O.at[d, s]
            if q["stop"] and lo == lo and lo <= q["stop"]:
                bk.sell(s, min(op, q["stop"]) if op == op else q["stop"])
        for s, q in bk.pos.items():
            c = C.at[d, s]
            if c == c:
                q["last"] = c
        eq.append(bk.value(C, d))
        E = eq[-1]
        cl = C.loc[d]
        sells, buys = [], []
        if name in ("P1", "P1F", "P1G", "P1S") and d in wk:
            sells, b1, _ = p1_weekly(d, cl, f, g, E, bk.cash,
                                     {s: q["sh"] * q["last"] for s, q in bk.pos.items()}, floor=(name == "P1F"),
                                     bff={"P1G": "weak", "P1S": "strong"}.get(name), **(params or {}))
            buys = [(s, a, None) for s, a in b1]
        elif name == "P2":
            for s in bk.pos:
                lo20 = g["lo20"].at[d, s]
                if cl[s] == cl[s] and lo20 == lo20 and cl[s] < lo20:
                    sells.append(s)
            free = 20 - (len(bk.pos) - len(sells))
            if free > 0:
                trig = (cl > g["hi55"].loc[d]) & (cl > g["sma200"].loc[d]) & g["liq"].loc[d] & f["has"].loc[d]
                c = [s for s in trig[trig].index if s not in bk.pos]
                c = sorted(c, key=lambda s: -(g["mom12_1"].at[d, s] if g["mom12_1"].at[d, s] == g["mom12_1"].at[d, s] else -9))
                for s in c[:free]:
                    n = g["atr20"].at[d, s]
                    buys.append((s, _sizes(E, cl[s], n, 0.005), ("abs", 2 * n)))
        elif name == "P3":
            for s in bk.pos:
                m50 = g["sma50"].at[d, s]
                if cl[s] == cl[s] and m50 == m50 and cl[s] < m50:
                    sells.append(s)
            free = 10 - (len(bk.pos) - len(sells))
            if free > 0 and bool(g["b_up50"].get(d, False)):
                tt = ((cl > g["sma150"].loc[d]) & (cl > g["sma200"].loc[d]) & (g["sma150"].loc[d] > g["sma200"].loc[d])
                      & (g["sma200"].loc[d] > g["sma200"].shift(21).loc[d]) & (g["sma50"].loc[d] > g["sma150"].loc[d])
                      & (cl > g["sma50"].loc[d]) & (cl >= 1.30 * g["lo52"].loc[d]) & (cl >= 0.75 * g["hi52"].loc[d])
                      & (g["rs"].loc[d] >= 70))
                bo = (cl > g["hi50"].loc[d]) & (p["Volume"].loc[d] >= 1.4 * g["vavg50"].loc[d])
                ok = tt & bo & g["liq"].loc[d] & f["has"].loc[d]
                c = sorted([s for s in ok[ok].index if s not in bk.pos], key=lambda s: -g["rs"].at[d, s])
                for s in c[:free]:
                    buys.append((s, E / 10, ("pct", 0.08)))
        elif name == "P4" and d in mo:
            uni = g["mom12_1"].loc[d].where(f["has"].loc[d])
            liq300 = f["turn252"].loc[d].where(f["has"].loc[d]).dropna().sort_values(ascending=False).head(300).index
            sc = uni.loc[liq300].dropna().sort_values(ascending=False)
            top = list(sc.index[:30])
            r = pd.Series(eq).pct_change().dropna().tail(126)
            rv = r.std() * math.sqrt(252) if len(r) >= 60 else 0.15
            scale = min(1.0, 0.15 / rv) if rv > 0 else 1.0
            sells = list(bk.pos)
            buys = [(s, E * scale / 30 * (1 - 2 * v2.COST), None) for s in top]
        pend_sell, pend_buy = sells, buys
    return pd.Series(eq, index=days), bk


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plumbing", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--floor", action="store_true", help="PREREG_p1_fundamental_floor: P1 vs P1F")
    ap.add_argument("--bff", action="store_true", help="PREREG_p1_bff_floor: P1 vs P1G / P1S, both halves")
    ap.add_argument("--robust", action="store_true", help="PREREG_p1_robustness: the 27-setting neighbourhood")
    a = ap.parse_args()
    if a.robust:
        p = v2.load_panel()
        f = v2.features(p)
        g = pro_features(p, f)
        rows = []
        for lb in (60, 90, 120):
            for tp in (0.10, 0.20, 0.30):
                for rk in (0.0005, 0.001, 0.002):
                    e, bk = run_sys("P1", p, f, g, START, END, params={"lookback": lb, "top_pct": tp, "risk": rk})
                    r = {"lookback": lb, "top_pct": tp, "risk_pct": rk * 100, "trades": bk.trades,
                         "centre": (lb, tp, rk) == (90, 0.20, 0.001)}
                    for half, (s0, s1) in {"full": (START, END), "H1": (START, SPLIT - pd.Timedelta(days=1)), "H2": (SPLIT, END)}.items():
                        m = v2.metrics(e.loc[s0:s1])
                        r["MAR_" + half], r["CAGR_" + half], r["DD_" + half] = m["MAR"], m["CAGR%"], m["maxDD%"]
                    rows.append(r)
                    print("L%-3d top %2d%% risk %.2f%% -> MAR %.2f / %.2f / %.2f  CAGR %.1f%%  DD %.1f%%" % (
                        lb, tp * 100, rk * 100, r["MAR_full"], r["MAR_H1"], r["MAR_H2"], r["CAGR_full"], r["DD_full"]), flush=True)
        T = pd.DataFrame(rows)
        os.makedirs(OUT, exist_ok=True)
        T.to_csv(os.path.join(OUT, "robustness.csv"), index=False)
        c = T[T.centre].iloc[0]
        nb = T[~T.centre]
        c1 = int(((nb.MAR_full > 0.48) & (nb.CAGR_full > 11.05)).sum())
        c2 = all(nb["MAR_" + h].median() >= 0.70 * c["MAR_" + h] for h in ("H1", "H2"))
        c3 = c["MAR_full"] <= 1.30 * nb.MAR_full.median()
        print("\n1. beats Mom30 MAR and Nifty CAGR: %d of 26 (need 21) -> %s" % (c1, "ok" if c1 >= 21 else "FAIL"))
        print("2. neighbour median MAR H1 %.2f (need %.2f) · H2 %.2f (need %.2f) -> %s" % (
            nb.MAR_H1.median(), 0.70 * c.MAR_H1, nb.MAR_H2.median(), 0.70 * c.MAR_H2, "ok" if c2 else "FAIL"))
        print("3. P1 MAR %.2f vs 1.30 x neighbour median %.2f -> %s" % (c.MAR_full, 1.30 * nb.MAR_full.median(), "ok" if c3 else "FAIL"))
        print("VERDICT  P1 is " + ("ROBUST (a plateau)" if (c1 >= 21 and c2 and c3) else "NOT ROBUST"))
        return 0
    if a.bff:
        p = v2.load_panel()
        f = v2.features(p)
        g = pro_features(p, f)
        T = {}
        for name in ("P1", "P1G", "P1S"):
            e, bk = run_sys(name, p, f, g, START, END)
            for half, (s0, s1) in {"full": (START, END), "H1": (START, SPLIT - pd.Timedelta(days=1)), "H2": (SPLIT, END)}.items():
                m = v2.metrics(e.loc[s0:s1])
                T[(name, half)] = m
                print(name, half, m, ("trades %d" % bk.trades) if half == "full" else "", flush=True)
        def ni(v):
            return all(T[(v, h)]["MAR"] >= 0.90 * T[("P1", h)]["MAR"] and T[(v, h)]["CAGR%"] >= T[("P1", h)]["CAGR%"] - 2.0
                       for h in ("H1", "H2"))
        h1, h2 = ni("P1G"), ni("P1S")
        pick = "P1"
        if h1:
            pick = "P1G"
        if h2 and all(T[("P1S", h)]["MAR"] > T[("P1G", h)]["MAR"] for h in ("H1", "H2")):
            pick = "P1S"
        print("H1 (weak floor) %s · H2 (strong only) %s -> live primary: %s" % (
            "PASS" if h1 else "FAIL", "PASS" if h2 else "FAIL", pick))
        return 0
    if a.floor:
        p = v2.load_panel()
        f = v2.features(p)
        g = pro_features(p, f)
        out = {}
        for name in ("P1", "P1F"):
            e, bk = run_sys(name, p, f, g, FLOOR_START, END)
            m = v2.metrics(e)
            m["trades"] = bk.trades
            out[name] = m
            print(name, m, flush=True)
        b = p["bench"].loc[FLOOR_START:END].dropna()
        print("B1", v2.metrics(b / b.iloc[0]))
        h = out["P1F"]["MAR"] >= 0.90 * out["P1"]["MAR"] and out["P1F"]["CAGR%"] >= out["P1"]["CAGR%"] - 2.0
        print("VERDICT  H " + ("PASS -> P1F (with the fundamental floor) is the live primary" if h
                               else "FAIL -> P1 is the live primary; P1F runs beside it"))
        return 0
    if not (a.plumbing or a.run):
        ap.print_help()
        return 0
    p = v2.load_panel()
    f = v2.features(p)
    g = pro_features(p, f)
    end = pd.Timestamp("2018-12-31") if a.plumbing else END
    res, trades = {}, {}
    for name in ("P1", "P2", "P3", "P4"):
        e, bk = run_sys(name, p, f, g, START, end)
        res[name], trades[name] = e, bk.trades
        print(f"{name}: trades {bk.trades}  open at end {len(bk.pos)}", flush=True)
    if a.plumbing:
        print("plumbing only - no returns printed")
        return 0
    for name in ("V2", "B3", "C"):
        e, bk = v2.run_variant(name, p, f, START, end)
        res[name], trades[name] = e, bk.trades
    res["B2"] = v2.ew_universe(p, f, START, end)
    b1 = p["bench"].loc[START:end].dropna()
    res["B1"] = b1 / b1.iloc[0]
    os.makedirs(OUT, exist_ok=True)
    pd.DataFrame({k: v / v.iloc[0] for k, v in res.items()}).to_csv(os.path.join(OUT, "equity.csv"))
    rows = []
    for name, e in res.items():
        for half, (s0, s1) in {"full": (START, end), "H1": (START, SPLIT - pd.Timedelta(days=1)), "H2": (SPLIT, end)}.items():
            m = v2.metrics(e.loc[s0:s1])
            m.update(variant=name, half=half, trades=trades.get(name) if half == "full" else None)
            rows.append(m)
    T = pd.DataFrame(rows)[["variant", "half", "CAGR%", "maxDD%", "MAR", "vol%", "Sharpe", "trades"]]
    T.to_csv(os.path.join(OUT, "metrics.csv"), index=False)
    print(T.to_string(index=False))
    h1 = T[(T.half == "H1") & T.variant.isin(["P1", "P2", "P3", "P4", "V2", "C"])].sort_values("MAR", ascending=False)
    pick = h1.iloc[0]["variant"]
    g2 = T[T.half == "H2"].set_index("variant")
    ok = g2.at[pick, "MAR"] > g2.at["B3", "MAR"] and g2.at[pick, "MAR"] > g2.at["B1", "MAR"] \
        and g2.at[pick, "CAGR%"] > g2.at["B1", "CAGR%"]
    print(f"\nH1 selection order (MAR): " + ", ".join(f"{r.variant} {r.MAR}" for r in h1.itertuples()))
    print(f"CHOSEN on H1: {pick}.  H2: MAR {g2.at[pick,'MAR']} vs B3 {g2.at['B3','MAR']} / B1 {g2.at['B1','MAR']}; "
          f"CAGR {g2.at[pick,'CAGR%']} vs B1 {g2.at['B1','CAGR%']}")
    print("VERDICT  " + pick + (" PASSES" if ok else " FAILS") + " the confirmation half")
    return 0


if __name__ == "__main__":
    sys.exit(main())
