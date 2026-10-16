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
    my, mt = y.rolling(90).mean(), t.rolling(90).mean()
    cov = y.mul(t, axis=0).rolling(90).mean() - my.mul(mt, axis=0)
    var_t = t.rolling(90).var(ddof=0)
    sd_y = y.rolling(90).std(ddof=0)
    slope = cov.div(var_t, axis=0)
    r = cov.div(sd_y.mul(np.sqrt(var_t), axis=0))
    g["clenow"] = (np.exp(slope * 252) - 1) * r ** 2
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


def _sizes(equity, px, atr, risk):
    return equity * risk / atr * px if (atr == atr and atr > 0 and px == px) else 0.0


def run_sys(name, p, f, g, start, end):
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
        if name == "P1" and d in wk:
            el = (cl > g["sma100"].loc[d]) & ~g["gap90"].loc[d] & g["liq"].loc[d] & f["has"].loc[d]
            sc = g["clenow"].loc[d][el].dropna().sort_values(ascending=False)
            top = set(sc.index[:max(1, math.ceil(0.2 * len(sc)))])
            sells = [s for s in bk.pos if s not in top]
            if bool(g["b_up200"].get(d, False)):
                cash = bk.cash + sum(bk.pos[s]["sh"] * bk.pos[s]["last"] for s in sells) * (1 - v2.COST)
                for s in sc.index:
                    if s in bk.pos:
                        continue
                    a = _sizes(E, cl[s], g["atr20"].at[d, s], 0.001)
                    if a <= 0 or a > cash:
                        break
                    buys.append((s, a, None))
                    cash -= a * (1 + v2.COST)
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
    a = ap.parse_args()
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
