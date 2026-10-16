#!/usr/bin/env python3
"""Does the PA gate select better trades? (pre-registered: docs/PREREG_pa_selects.md, 16-Oct-2026).

    python pa_select_study.py --build      scan 2018-05..2023-04, write data/pa_select_signals.csv
    python pa_select_study.py --placebo    A/F labels shuffled (H must FAIL)
    python pa_select_study.py --run        THE analysis - run once
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
from pa_recency_study import _atr14, _dedup, _boot_diff   # noqa: E402  (same helpers, same rules)

SIG = os.path.join(HERE, "data", "pa_select_signals.csv")
WIN = 400
H = 20
STOP_ATR = 4.0
LAST_SIGNAL = pd.Timestamp("2023-04-28")
N_MIN = 100
MIN_EDGE = 0.10


def _scan(sym: str) -> list[dict]:
    import data_provider as dp
    import pa_patterns as pap
    try:
        df = dp.fetch_ohlcv(sym, period="10y", interval="1d", use_cache=True)
    except Exception:
        return []
    if df is None or len(df) < WIN + 60:
        return []
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    end = int(np.searchsorted(df.index.values, np.datetime64(LAST_SIGNAL), side="right"))
    end = min(end, len(df) - H - 1)
    if end <= WIN:
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
        fut = df.iloc[t + 1:t + 1 + H]
        hit = (fut["Low"] <= e - risk).values
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


def analyse(placebo: bool) -> int:
    d = pd.read_csv(SIG)
    if placebo:
        m = d["cohort"].isin(["A", "F"])
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
        A, F = w[w["cohort"] == "A"], w[w["cohort"] == "F"]
        thin = min(len(A), len(F)) < N_MIN
        ci = _boot_diff(A, F, rng) if len(A) and len(F) else (np.nan, np.nan)
        dm, dmed = A.r20.mean() - F.r20.mean(), A.r20.median() - F.r20.median()
        h = (not thin) and dm >= MIN_EDGE and dmed >= 0 and ci[0] > 0
        print(f"  A-F mean {dm:+.3f}R  CI [{ci[0]:+.3f}, {ci[1]:+.3f}]  median gap {dmed:+.3f}R"
              f"  -> {'PASS' if h else 'FAIL'}" + (" (THIN)" if thin else ""))
        ok.append(h)
    v = all(ok)
    print(f"\nVERDICT  H {'PASS' if v else 'FAIL'} -> "
          + ("the PA gate selects: keep it as a filter" if v
             else "the PA gate is a TIMING cue, not a selector (no code change from this test)"))
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
