#!/usr/bin/env python3
"""v2 rank -> portfolio backtest against the benchmarks (pre-registered: docs/PREREG_v2_rank_portfolio.md).

    python v2_backtest.py --panel        build/refresh the price panel cache (data/v2_panel.pkl)
    python v2_backtest.py --plumbing     2018-06..2018-12 only, trade COUNTS (no returns)
    python v2_backtest.py --run          THE run - once
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PANEL = os.path.join(HERE, "data", "v2_panel.pkl")
OUT = os.path.join(HERE, "reports", "v2_backtest")
START, SPLIT, END = pd.Timestamp("2018-06-01"), pd.Timestamp("2022-08-01"), pd.Timestamp("2026-10-16")
COST = 0.0025
SLOTS, SLOTS_WEAK, SELL_RANK = 15, 7, 45
STOP_ATR, CH_WIN, CH_MULT = 4.0, 22, 4.5
MIN_BARS = 260
TURNOVER_MIN = 5e7          # Rs 5 crore median daily turnover


# ── data ─────────────────────────────────────────────────────────────────────
def build_panel() -> dict:
    import data_provider as dp
    with open(os.path.join(HERE, "nifty500_symbols.json"), encoding="utf-8") as f:
        syms = json.load(f)
    syms = [str(s if isinstance(s, str) else (s.get("symbol") or s.get("Symbol"))).replace(".NS", "")
            for s in syms if s]
    bench = dp.fetch_ohlcv("^CRSLDX", period="10y", interval="1d", use_cache=True)
    cal = pd.DatetimeIndex(pd.to_datetime(bench.index).tz_localize(None) if getattr(bench.index, "tz", None)
                           else pd.to_datetime(bench.index)).normalize()
    fr = {k: {} for k in ("Open", "High", "Low", "Close", "Volume")}
    for i, s in enumerate(syms, 1):
        try:
            d = dp.fetch_ohlcv(s, period="10y", interval="1d", use_cache=True)
        except Exception:
            continue
        if d is None or len(d) < MIN_BARS:
            continue
        d = d.copy()
        d.index = pd.to_datetime(d.index)
        if getattr(d.index, "tz", None) is not None:
            d.index = d.index.tz_localize(None)
        d.index = d.index.normalize()
        d = d[~d.index.duplicated(keep="last")]
        for k in fr:
            fr[k][s] = d[k]
        if i % 50 == 0:
            print(f"  {i}/{len(syms)}", flush=True)
    p = {k: pd.DataFrame(v).reindex(cal) for k, v in fr.items()}
    b = bench.copy()
    b.index = cal
    p["bench"] = b["Close"]
    p["nifty50"] = dp.fetch_ohlcv("^NSEI", period="10y", interval="1d", use_cache=True)["Close"]
    p["nifty50"].index = pd.to_datetime(p["nifty50"].index).normalize()
    p["nifty50"] = p["nifty50"].reindex(cal)
    os.makedirs(os.path.dirname(PANEL), exist_ok=True)
    pickle.dump(p, open(PANEL, "wb"))
    print("panel:", p["Close"].shape)
    return p


def load_panel() -> dict:
    return pickle.load(open(PANEL, "rb")) if os.path.exists(PANEL) else build_panel()


def features(p: dict) -> dict:
    C, H, L, V = p["Close"], p["High"], p["Low"], p["Volume"]
    ret = C.pct_change()
    vol = ret.rolling(252, min_periods=200).std() * np.sqrt(252)
    prev = C.shift()
    tr = np.maximum(H - L, np.maximum((H - prev).abs(), (L - prev).abs()))
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    sma50, sma150, sma200 = C.rolling(50).mean(), C.rolling(150).mean(), C.rolling(200).mean()
    f = {
        "atr": atr,
        "mom12": (C / C.shift(252) - 1) / vol,
        "mom6": (C / C.shift(126) - 1) / vol,
        "prox": C / C.rolling(252, min_periods=200).max(),
        "trend": (C > sma50).astype(float).where(sma50.notna()).rolling(126, min_periods=100).mean(),
        "elig": (C > sma200) & (sma200 > sma200.shift(20)) & (C > sma50)
                & ((C * V).rolling(50).median() >= TURNOVER_MIN) & (C.notna().cumsum() >= MIN_BARS),
        "trig_elig": (C > sma150) & (sma150 > sma150.shift(20)),
        "turn252": (C * V).rolling(252, min_periods=200).median(),
        "has": C.notna().cumsum() >= MIN_BARS,
        "regime_up": p["bench"] > p["bench"].rolling(200).mean(),
    }
    return f


# ── a minimal portfolio engine ───────────────────────────────────────────────
class Book:
    def __init__(self, cash=1.0):
        self.cash = cash
        self.pos = {}            # sym -> dict(sh, entry, stop, hi)
        self.trades = 0
        self.traded = 0.0

    def value(self, C, d):
        v = self.cash
        for s, q in self.pos.items():
            px = C.at[d, s]
            v += q["sh"] * (px if px == px else q["last"])
        return v

    def sell(self, s, px):
        q = self.pos.pop(s)
        amt = q["sh"] * px
        self.cash += amt * (1 - COST)
        self.trades += 1
        self.traded += amt

    def buy(self, s, px, amount, stop=None):
        amount = min(amount, self.cash / (1 + COST))
        if amount <= 0 or not px > 0:
            return
        sh = amount / px
        self.cash -= amount * (1 + COST)
        self.pos[s] = {"sh": sh, "entry": px, "stop": stop, "hi": px, "last": px}
        self.trades += 1
        self.traded += amount


def _week_ends(idx):
    s = pd.Series(idx, index=idx)
    return set(s.groupby(idx.to_period("W")).max())


def _semi_ends(idx):
    s = pd.Series(idx, index=idx)
    me = s.groupby(idx.to_period("M")).max()
    return set(v for k, v in me.items() if k.month in (6, 12))


def run_variant(name, p, f, start, end, seed=None, plumbing=False):
    O, H, L, C = p["Open"], p["High"], p["Low"], p["Close"]
    days = C.index[(C.index >= start) & (C.index <= end)]
    wk = _week_ends(days)
    semi = _semi_ends(days)
    rng = np.random.default_rng(seed) if seed is not None else None
    trig = _trigger_signals() if name == "C" else None
    bk = Book(1.0)
    pend_sell, pend_buy = [], []         # executed at the next open
    eq = []
    for d in days:
        # 1. orders from the last signal close, at this open
        for s in pend_sell:
            if s in bk.pos:
                px = O.at[d, s]
                bk.sell(s, px if px == px else bk.pos[s]["last"])
        for s, amt, k_stop in pend_buy:
            px = O.at[d, s]
            if px == px and s not in bk.pos:
                stop = (px - k_stop) if k_stop else None
                bk.buy(s, px, amt, stop)
        pend_sell, pend_buy = [], []
        # 2. intraday stops
        for s in list(bk.pos):
            q = bk.pos[s]
            lo, op = L.at[d, s], O.at[d, s]
            if q["stop"] and lo == lo and lo <= q["stop"]:
                bk.sell(s, min(op, q["stop"]) if op == op else q["stop"])
        # 3. mark
        for s, q in bk.pos.items():
            c = C.at[d, s]
            if c == c:
                q["last"] = c
                q.setdefault("closes", []).append(c)
                q["hi"] = max(q["closes"][-CH_WIN:])          # 22-session highest close, since entry
                q["n"] = q.get("n", 0) + 1
        eq.append(bk.value(C, d))
        # 4. signals at this close
        if name == "C":
            ps, pb = _sig_trigger(bk, d, C, f, trig)
        elif name in ("V2", "R") and d in wk:
            ps, pb = _sig_v2(bk, d, C, f, eq[-1], rng if name == "R" else None)
        elif name == "B3" and d in semi:
            ps, pb = _sig_mom30(bk, d, C, f, eq[-1])
        else:
            ps, pb = [], []
        pend_sell, pend_buy = ps, pb
    e = pd.Series(eq, index=days)
    return e, bk


def _sig_v2(bk, d, C, f, equity, rng):
    el = f["elig"].loc[d]
    el = el[el].index
    sc = pd.DataFrame({k: f[k].loc[d, el] for k in ("mom12", "mom6", "prox", "trend")}).dropna()
    comp = sc.rank(pct=True).mean(axis=1).sort_values(ascending=False)
    ranked = list(comp.index)
    pos_rank = {s: i + 1 for i, s in enumerate(ranked)}
    sells = []
    for s in bk.pos:
        if s not in comp.index:
            sells.append(s)                                  # no longer eligible
        elif rng is None and pos_rank[s] > SELL_RANK:
            sells.append(s)
    target = SLOTS if bool(f["regime_up"].get(d, False)) else SLOTS_WEAK
    free = target - (len(bk.pos) - len(sells))
    buys = []
    if free > 0:
        pool = [s for s in ranked if s not in bk.pos]
        if rng is not None:
            pool = list(rng.permutation(pool)) if pool else []
        for s in pool[:free]:
            atr = f["atr"].at[d, s]
            buys.append((s, equity / SLOTS, STOP_ATR * atr if atr == atr else None))
    return sells, buys


def _sig_mom30(bk, d, C, f, equity):
    has = f["has"].loc[d]
    t = f["turn252"].loc[d][has].dropna().sort_values(ascending=False).head(200).index
    sc = pd.DataFrame({"a": f["mom6"].loc[d, t], "b": f["mom12"].loc[d, t]}).dropna()
    z = ((sc - sc.mean()) / sc.std()).mean(axis=1).sort_values(ascending=False)
    top = list(z.index[:30])
    sells = list(bk.pos)                                     # full rebalance to equal weight
    buys = [(s, equity / 30 * (1 - 2 * COST), None) for s in top]
    return sells, buys


def _trigger_signals() -> dict:
    out = {}
    for fn in ("pa_select_signals.csv", "pa_recency_signals.csv", "pa_combo_signals.csv"):
        fp = os.path.join(HERE, "data", fn)
        if not os.path.exists(fp):
            continue
        x = pd.read_csv(fp, usecols=["symbol", "date", "cohort"])
        x = x[x["cohort"] == "A"]
        for s, dd in zip(x["symbol"], pd.to_datetime(x["date"])):
            out.setdefault(dd.normalize(), set()).add(s)
    return out


def _sig_trigger(bk, d, C, f, trig):
    sells = []
    for s, q in bk.pos.items():
        c = C.at[d, s]
        atr = f["atr"].at[d, s]
        if c == c and atr == atr:
            ch = q["hi"] - CH_MULT * atr if q.get("n", 0) >= 1 else None
            if ch is not None and c < ch:
                sells.append(s)
    free = SLOTS - (len(bk.pos) - len(sells))
    buys = []
    if free > 0:
        cands = sorted(s for s in trig.get(d, ()) if s not in bk.pos and s in C.columns)
        equity = bk.value(C, d)
        for s in cands[:free]:
            atr = f["atr"].at[d, s]
            buys.append((s, equity / SLOTS, STOP_ATR * atr if atr == atr else None))
    return sells, buys


# ── metrics ──────────────────────────────────────────────────────────────────
def metrics(e: pd.Series) -> dict:
    e = e.dropna()
    if len(e) < 20:
        return {}
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    cagr = (e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1 if yrs > 0 else np.nan
    dd = (e / e.cummax() - 1).min()
    w = e.resample("W").last().pct_change().dropna()
    return {"CAGR%": round(cagr * 100, 2), "maxDD%": round(dd * 100, 2),
            "MAR": round(cagr / abs(dd), 2) if dd < 0 else np.nan,
            "vol%": round(w.std() * np.sqrt(52) * 100, 2),
            "Sharpe": round(w.mean() / w.std() * np.sqrt(52), 2) if w.std() > 0 else np.nan}


def ew_universe(p, f, start, end):
    C = p["Close"]
    r = C.pct_change().where(f["has"].shift().fillna(False))
    m = r.mean(axis=1)
    days = C.index[(C.index >= start) & (C.index <= end)]
    return (1 + m.loc[days].fillna(0)).cumprod()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--panel", action="store_true")
    ap.add_argument("--plumbing", action="store_true")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.panel:
        build_panel()
        return 0
    if not (a.plumbing or a.run):
        ap.print_help()
        return 0
    p = load_panel()
    f = features(p)
    end = pd.Timestamp("2018-12-31") if a.plumbing else END
    res, books = {}, {}
    for name in ("V2", "B3", "C"):
        e, bk = run_variant(name, p, f, START, end)
        res[name], books[name] = e, bk
        print(f"{name}: trades {bk.trades}  open positions at end {len(bk.pos)}", flush=True)
    if a.plumbing:
        print("plumbing only - no returns printed")
        return 0
    rs = []
    for sd in range(20):
        e, _ = run_variant("R", p, f, START, end, seed=sd)
        rs.append(e / e.iloc[0])
    res["R"] = pd.concat(rs, axis=1).mean(axis=1)
    res["B2"] = ew_universe(p, f, START, end)
    b1 = p["bench"].loc[START:end].dropna()
    res["B1"] = b1 / b1.iloc[0]
    os.makedirs(OUT, exist_ok=True)
    pd.DataFrame({k: v / v.iloc[0] for k, v in res.items()}).to_csv(os.path.join(OUT, "equity.csv"))
    rows = []
    for name, e in res.items():
        for half, (s0, s1) in {"full": (START, end), "H1": (START, SPLIT), "H2": (SPLIT, end)}.items():
            m = metrics(e.loc[s0:s1])
            m.update(variant=name, half=half)
            if name in books and half == "full":
                avg = (e / e.iloc[0]).mean()
                m["trades"] = books[name].trades
            rows.append(m)
    T = pd.DataFrame(rows)[["variant", "half", "CAGR%", "maxDD%", "MAR", "vol%", "Sharpe"] +
                           (["trades"] if "trades" in pd.DataFrame(rows) else [])]
    T.to_csv(os.path.join(OUT, "metrics.csv"), index=False)
    print(T.to_string(index=False))
    ok = True
    for h in ("H1", "H2"):
        g = T[T.half == h].set_index("variant")
        c = (g.at["V2", "MAR"] > g.at["B2", "MAR"]) and (g.at["V2", "MAR"] > g.at["B3", "MAR"]) \
            and (g.at["V2", "CAGR%"] > g.at["B1", "CAGR%"])
        print(f"{h}: V2 MAR {g.at['V2','MAR']} vs B2 {g.at['B2','MAR']} / B3 {g.at['B3','MAR']}; "
              f"CAGR {g.at['V2','CAGR%']} vs B1 {g.at['B1','CAGR%']} -> {'pass' if c else 'FAIL'}")
        ok = ok and c
    print("\nVERDICT  V2 " + ("PASSES" if ok else "FAILS") + " the pre-registered rule")
    return 0


if __name__ == "__main__":
    sys.exit(main())
