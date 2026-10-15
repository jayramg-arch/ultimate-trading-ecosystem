#!/usr/bin/env python3
"""Daily PA recency allowance (pre-registered: docs/PREREG_pa_recency_daily.md, 15-Oct-2026).

    python pa_recency_study.py --build          scan the holdout window, write data/pa_recency_signals.csv
    python pa_recency_study.py --placebo        A/R labels shuffled (plumbing check only)
    python pa_recency_study.py --run            THE analysis - run once
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SIG = os.path.join(HERE, "data", "pa_recency_signals.csv")
WIN = 400            # bars of history handed to the battery (= pa_combo_study)
COMBO_SPAN = 521     # pa_combo_study used signal days from n - 521 (DAYS 500 + H 20 + 1)
H = 20
STOP_ATR = 4.0
DEDUP = 5
N_MIN = 100
BOOT = 2000


def _atr14(df):
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / 14, adjust=False).mean()


def _scan(sym: str) -> list[dict]:
    import data_provider as dp
    import pa_patterns as pap
    try:
        df = dp.fetch_ohlcv(sym, period="5y", interval="1d", use_cache=True)
    except Exception:
        return []
    if df is None:
        return []
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    n = len(df)
    end = n - COMBO_SPAN - H - 1          # last signal day: outcome ends before pa_combo's first signal
    if end <= WIN + 30:
        return []
    sma150 = df["Close"].rolling(150).mean()
    atr = _atr14(df)
    sig = {}

    def s_at(t):
        if t not in sig:
            x = df.iloc[max(0, t - WIN + 1):t + 1]
            try:
                sig[t] = sum(w for _n, f, w, _x in pap.detect_bull_patterns(x, "") if f)
            except Exception:
                sig[t] = 0
        return sig[t]

    out = []
    for t in range(WIN, end):
        c = float(df["Close"].iloc[t])
        s150, s150p = sma150.iloc[t], sma150.iloc[t - 20]
        if not (s150 == s150 and s150p == s150p and c > s150 and s150 > s150p):
            continue
        if s_at(t) > 0:
            cohort, age = "A", 0
        else:
            age = next((k for k in range(1, 7) if s_at(t - k) > 0), None)
            cohort = "F" if age is None else ("R" if age <= 3 else "E")
            age = age or 0
        e = float(df["Open"].iloc[t + 1])
        risk = STOP_ATR * float(atr.iloc[t])
        if not risk > 0:
            continue
        stop = e - risk
        fut = df.iloc[t + 1:t + 1 + H]
        hit = (fut["Low"] <= stop).values
        r = -1.0 if hit.any() else (float(fut["Close"].iloc[-1]) - e) / risk
        out.append({"symbol": sym, "date": str(df.index[t])[:10], "cohort": cohort,
                    "age": age, "r20": round(r, 4), "stopped": int(hit.any())})
    return out


def build(workers: int) -> int:
    with open(os.path.join(HERE, "nifty500_symbols.json"), encoding="utf-8") as f:
        syms = json.load(f)
    syms = [s if isinstance(s, str) else (s.get("symbol") or s.get("Symbol")) for s in syms]
    syms = [str(s).replace(".NS", "") for s in syms if s]
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, r in enumerate(ex.map(_scan, syms, chunksize=4), 1):
            rows.extend(r)
            if i % 25 == 0:
                print(f"{i}/{len(syms)} symbols, {len(rows)} signals", flush=True)
    pd.DataFrame(rows).to_csv(SIG, index=False)
    print("written", SIG, len(rows))
    return 0


def _dedup(d: pd.DataFrame) -> pd.DataFrame:
    keep = []
    for (_s, _c), g in d.sort_values("date").groupby(["symbol", "cohort"]):
        last = None
        for i, dt in zip(g.index, pd.to_datetime(g["date"])):
            if last is None or np.busday_count(last.date(), dt.date()) >= DEDUP:
                keep.append(i)
                last = dt
    return d.loc[keep]


def _boot_diff(x, y, rng):
    sx = {s: g["r20"].values for s, g in x.groupby("symbol")}
    sy = {s: g["r20"].values for s, g in y.groupby("symbol")}
    kx, ky = list(sx), list(sy)
    diffs = []
    for _ in range(BOOT):
        a = np.concatenate([sx[k] for k in rng.choice(kx, len(kx))])
        b = np.concatenate([sy[k] for k in rng.choice(ky, len(ky))])
        diffs.append(a.mean() - b.mean())
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def analyse(placebo: bool) -> int:
    d = pd.read_csv(SIG)
    if placebo:
        m = d["cohort"].isin(["A", "R"])
        d.loc[m, "cohort"] = np.random.default_rng(7).permutation(d.loc[m, "cohort"].values)
    d = _dedup(d)
    d["date"] = pd.to_datetime(d["date"])
    cut = d["date"].median()
    rng = np.random.default_rng(11)
    print(("PLACEBO - " if placebo else "") + f"signals after de-dup: {len(d)} · split at {cut.date()}")
    ok = []
    for name, w in (("H1st", d[d["date"] <= cut]), ("H2nd", d[d["date"] > cut])):
        print(f"\n== {name} ({w['date'].min().date()} .. {w['date'].max().date()})")
        for c in "AREF":
            g = w[w["cohort"] == c]
            if len(g):
                print(f"  {c}: n {len(g):5d}  mean {g.r20.mean():+.3f}R  median {g.r20.median():+.3f}R"
                      f"  stopped {g.stopped.mean()*100:5.1f}%")
        A, R = w[w["cohort"] == "A"], w[w["cohort"] == "R"]
        thin = min(len(A), len(R)) < N_MIN
        ci = _boot_diff(R, A, rng) if len(A) and len(R) else (np.nan, np.nan)
        dm, dmed = R.r20.mean() - A.r20.mean(), R.r20.median() - A.r20.median()
        h = (not thin) and dm >= -0.05 and dmed >= -0.10 and ci[0] > -0.15
        print(f"  R-A mean {dm:+.3f}R  CI [{ci[0]:+.3f}, {ci[1]:+.3f}]  median gap {dmed:+.3f}R"
              f"  -> {'PASS' if h else 'FAIL'}" + (" (THIN)" if thin else ""))
        ok.append(h)
    v = all(ok)
    print(f"\nVERDICT  H {'PASS' if v else 'FAIL'} -> "
          + ("Daily board gets the 1-3 bar recency allowance (capped 4/5, age tag)" if v
             else "Daily board stays last-bar only"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--placebo", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    if a.build:
        return build(a.workers)
    if a.placebo or a.run:
        return analyse(placebo=a.placebo)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
