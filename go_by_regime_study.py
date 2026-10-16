#!/usr/bin/env python3
"""GO vs non-GO by market tier, forward (pre-registered: docs/PREREG_go_by_regime.md, 16-Oct-2026).

    python go_by_regime_study.py --placebo     GO/non-GO labels shuffled (H1 must be false)
    python go_by_regime_study.py --run         THE run (2027-01-15)
    python go_by_regime_study.py --count       how many rows have matured so far (no outcomes shown)
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
LOG = os.path.join(HERE, "logs", "gm_signal_log.csv")
START = "2026-10-17"
H = 10
DEDUP = 5
N_MIN = 60
BOOT = 2000


def _scores() -> pd.Series:
    import sqlite3
    import journal_path as jp
    with sqlite3.connect(jp.JOURNAL_DB) as c:
        m = pd.read_sql("select date, score from MarketRegime", c)
    m["date"] = pd.to_datetime(m["date"], errors="coerce")
    m = m.dropna().sort_values("date").drop_duplicates("date", keep="last")
    return m.set_index("date")["score"].astype(float)


def _tier(sc) -> str:
    if sc is None or pd.isna(sc):
        return "BEAR"
    return "OPEN" if sc >= 6 else ("NEUTRAL" if sc >= 3 else "BEAR")


def rows() -> pd.DataFrame:
    g = pd.read_csv(LOG)
    g = g[g["signal_date"].astype(str) >= START].copy()
    s = g["s4go"].astype(str)
    g = g[~s.str.startswith("⛔") & ~s.str.startswith("⏱")].copy()
    g["grp"] = np.where(g["s4go"].astype(str).str.match(r"5/5"), "GO", "nonGO")
    g["d"] = pd.to_datetime(g["signal_date"])
    keep = []
    for _k, x in g.sort_values(["d", "signal_time"]).groupby(["symbol", "tf", "grp"]):
        last = None
        for i, d in zip(x.index, x["d"]):
            if last is None or np.busday_count(last.date(), d.date()) >= DEDUP:
                keep.append(i)
                last = d
    return g.loc[keep]


def score(g: pd.DataFrame) -> pd.DataFrame:
    import data_provider as dp
    b = dp.fetch_ohlcv("^CRSLDX", period="2y", interval="1d", use_cache=True)["Close"]
    sc = _scores()
    cache, out = {}, []
    for _, r in g.iterrows():
        sym = str(r["symbol"])
        if sym not in cache:
            try:
                cache[sym] = dp.fetch_ohlcv(sym, period="2y", interval="1d", use_cache=True)["Close"]
            except Exception:
                cache[sym] = None
        c = cache[sym]
        if c is None or c.empty:
            continue
        p = int(c.index.searchsorted(r["d"], side="right")) - 1     # the signal date's close
        bi = int(b.index.searchsorted(r["d"], side="right")) - 1
        if p < 0 or bi < 0 or p + H >= len(c) or bi + H >= len(b):
            continue                                                 # not matured
        ex = (float(c.iloc[p + H]) / float(c.iloc[p]) - float(b.iloc[bi + H]) / float(b.iloc[bi])) * 100
        out.append({"symbol": sym, "tf": r["tf"], "grp": r["grp"], "playbook": r.get("playbook"),
                    "tier": _tier(sc.asof(r["d"]) if len(sc) else None), "ex": ex})
    return pd.DataFrame(out)


def _boot(x, y, rng):
    sx = {s: v["ex"].values for s, v in x.groupby("symbol")}
    sy = {s: v["ex"].values for s, v in y.groupby("symbol")}
    kx, ky = list(sx), list(sy)
    d = [np.concatenate([sx[k] for k in rng.choice(kx, len(kx))]).mean()
         - np.concatenate([sy[k] for k in rng.choice(ky, len(ky))]).mean() for _ in range(BOOT)]
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def analyse(placebo: bool) -> int:
    s = score(rows())
    if placebo:
        s["grp"] = np.random.default_rng(7).permutation(s["grp"].values)
    print(("PLACEBO - " if placebo else "") + f"matured rows {len(s)}")
    print(s.groupby(["tier", "grp"]).ex.agg(["count", "mean", lambda v: (v > 0).mean() * 100]).round(2))
    w = s[s["tier"].isin(["BEAR", "NEUTRAL"])]
    rng = np.random.default_rng(11)
    G, N = w[w.grp == "GO"], w[w.grp == "nonGO"]
    h1 = h2 = False
    thin = min(len(G), len(N)) < N_MIN
    if not thin:
        ci = _boot(G, N, rng)
        dm = G.ex.mean() - N.ex.mean()
        h1 = dm <= -0.50 and ci[1] < 0
        print(f"\nH1 (BEAR+NEUTRAL) GO - nonGO {dm:+.2f}pp  CI [{ci[0]:+.2f}, {ci[1]:+.2f}] -> {'TRUE' if h1 else 'false'}")
    B, P = G[G.playbook == "breakout"], G[G.playbook == "pullback"]
    if min(len(B), len(P)) >= N_MIN:
        ci2 = _boot(B, P, rng)
        d2 = B.ex.mean() - P.ex.mean()
        h2 = d2 <= -0.50 and ci2[1] < 0
        print(f"H2 breakout GO - pullback GO {d2:+.2f}pp  CI [{ci2[0]:+.2f}, {ci2[1]:+.2f}] -> {'TRUE' if h2 else 'false'}")
    else:
        print(f"H2 THIN (breakout {len(B)}, pullback {len(P)})")
    print("\nVERDICT -> " + ("suspend GO alerts in BEAR/NEUTRAL" if h1 else
                             "suppress BREAKOUT GOs in BEAR/NEUTRAL" if h2 else
                             ("THIN - rerun 2027-03-15" if thin else "no change")))
    return 0


def count() -> int:
    s = score(rows())
    print(s.groupby(["tier", "grp"]).size().to_string() if len(s) else "no matured rows yet")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--placebo", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--count", action="store_true")
    a = ap.parse_args()
    if a.count:
        return count()
    if a.placebo or a.run:
        return analyse(a.placebo)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
