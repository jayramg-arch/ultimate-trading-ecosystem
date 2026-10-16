#!/usr/bin/env python3
"""The tournament on a survivorship-corrected universe (pre-registered: docs/PREREG_survivorship_tournament.md).

    python survivorship_backtest.py --panel     fetch ~2,950 NSE EQ/BE names (10y daily) -> data/surv_panel.pkl
    python survivorship_backtest.py --members   print the point-in-time universe sizes (no returns)
    python survivorship_backtest.py --run       THE run - once
"""
from __future__ import annotations

import argparse
import os
import pickle
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import v2_backtest as v2            # noqa: E402
import pro_systems_backtest as ps   # noqa: E402

PANEL = os.path.join(HERE, "data", "surv_panel.pkl")
OUT = os.path.join(HERE, "reports", "survivorship")
TOP_N, TURN_WIN = 500, 126


def symbols() -> list[str]:
    m = pd.read_csv(os.path.join(HERE, "data", "dhan_scrip_master.csv"), low_memory=False)
    e = m[(m.SEM_EXM_EXCH_ID == "NSE") & (m.SEM_INSTRUMENT_NAME == "EQUITY") & m.SEM_SERIES.isin(["EQ", "BE"])]
    return sorted(set(e.SEM_TRADING_SYMBOL.astype(str)))


def build_panel() -> None:
    import data_provider as dp
    bench = dp.fetch_ohlcv("^CRSLDX", period="10y", interval="1d", use_cache=False)
    cal = pd.to_datetime(bench.index)
    if getattr(cal, "tz", None) is not None:
        cal = cal.tz_localize(None)
    cal = cal.normalize()
    fr = {k: {} for k in ("Open", "High", "Low", "Close", "Volume")}
    syms = symbols()
    for i, s in enumerate(syms, 1):
        try:
            d = dp.fetch_ohlcv(s, period="10y", interval="1d", use_cache=True)
        except Exception:
            d = None
        if d is not None and len(d) >= v2.MIN_BARS:
            d = d.copy()
            d.index = pd.to_datetime(d.index)
            if getattr(d.index, "tz", None) is not None:
                d.index = d.index.tz_localize(None)
            d.index = d.index.normalize()
            d = d[~d.index.duplicated(keep="last")]
            for k in fr:
                fr[k][s] = d[k].astype("float32")
        if i % 100 == 0:
            print(f"  {i}/{len(syms)}  kept {len(fr['Close'])}", flush=True)
    p = {k: pd.DataFrame(v).reindex(cal) for k, v in fr.items()}
    b = bench["Close"].copy()
    b.index = cal
    p["bench"] = b
    os.makedirs(os.path.dirname(PANEL), exist_ok=True)
    pickle.dump(p, open(PANEL, "wb"))
    print("panel:", p["Close"].shape)


def membership(p: dict) -> pd.DataFrame:
    """Point-in-time universe: at each June/December month-end, the TOP_N names by median
    turnover over the previous TURN_WIN sessions (>= MIN_BARS history), held for six months."""
    C, V = p["Close"].astype(float), p["Volume"].astype(float)
    turn = (C * V).rolling(TURN_WIN, min_periods=100).median()
    has = C.notna().cumsum() >= v2.MIN_BARS
    idx = C.index
    me = pd.Series(idx, index=idx).groupby(idx.to_period("M")).max()
    rebal = [d for k, d in me.items() if k.month in (6, 12)]
    mem = pd.DataFrame(False, index=idx, columns=C.columns)
    for i, d in enumerate(rebal):
        t = turn.loc[d].where(has.loc[d]).dropna().sort_values(ascending=False)
        top = t.index[:TOP_N]
        nxt = rebal[i + 1] if i + 1 < len(rebal) else idx[-1] + pd.Timedelta(days=1)
        rows = (idx > d) & (idx <= nxt)
        mem.loc[rows, top] = True
    return mem


def load() -> tuple[dict, pd.DataFrame]:
    p = pickle.load(open(PANEL, "rb"))
    mem = membership(p)
    keep = mem.columns[mem.any()]
    for k in ("Open", "High", "Low", "Close", "Volume"):
        p[k] = p[k][keep].astype(float)
    return p, mem[keep]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--panel", action="store_true")
    ap.add_argument("--members", action="store_true")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.panel:
        build_panel()
        return 0
    if not (a.members or a.run):
        ap.print_help()
        return 0
    p, mem = load()
    if a.members:
        today_list = set(v2.load_panel()["Close"].columns)
        for d in ("2018-07-02", "2020-07-01", "2022-07-01", "2024-07-01", "2026-07-01"):
            i = mem.index.searchsorted(pd.Timestamp(d))
            row = mem.iloc[i]
            names = set(row[row].index)
            print(d, "members", len(names), "| also in TODAY's Nifty 500:", len(names & today_list))
        print("names ever a member:", mem.shape[1])
        return 0
    f = v2.features(p)
    f["has"] = f["has"] & mem                 # point-in-time membership everywhere 'has' is read
    f["elig"] = f["elig"] & mem
    g = ps.pro_features(p, f)
    res = {}
    for name in ("V2", "B3"):
        e, _ = v2.run_variant(name, p, f, v2.START, v2.END)
        res[name] = e
    e, _ = ps.run_sys("P1", p, f, g, v2.START, v2.END)
    res["P1"] = e
    e, _ = ps.run_sys("P1", p, f, g, v2.START, v2.END, params={"ensemble": True, "top_pct": 0.25})
    res["P1E (descriptive)"] = e
    res["B2"] = v2.ew_universe(p, f, v2.START, v2.END)
    b1 = p["bench"].loc[v2.START:v2.END].dropna()
    res["B1"] = b1 / b1.iloc[0]
    rows = []
    for name, e in res.items():
        for half, (s0, s1) in {"full": (v2.START, v2.END), "H1": (v2.START, v2.SPLIT - pd.Timedelta(days=1)),
                               "H2": (v2.SPLIT, v2.END)}.items():
            m = v2.metrics(e.loc[s0:s1])
            m.update(variant=name, half=half)
            rows.append(m)
    T = pd.DataFrame(rows)[["variant", "half", "CAGR%", "maxDD%", "MAR", "vol%", "Sharpe"]]
    os.makedirs(OUT, exist_ok=True)
    T.to_csv(os.path.join(OUT, "metrics.csv"), index=False)
    pd.DataFrame({k: v / v.iloc[0] for k, v in res.items()}).to_csv(os.path.join(OUT, "equity.csv"))
    print(T.to_string(index=False))
    G = {h: T[T.half == h].set_index("variant") for h in ("full", "H1", "H2")}
    ok = all(G[h].at["P1", "MAR"] > G[h].at["B1", "MAR"] and G[h].at["P1", "MAR"] > G[h].at["B3", "MAR"]
             for h in ("H1", "H2")) and G["full"].at["P1", "CAGR%"] > G["full"].at["B1", "CAGR%"]
    print("\nVERDICT  P1 " + ("SURVIVES the survivorship correction" if ok else "DOES NOT SURVIVE the survivorship correction"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
