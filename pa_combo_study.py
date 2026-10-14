#!/usr/bin/env python3
"""PA -> now combo study (pre-registered: docs/PREREG_pa_combo.md, 14-Oct-2026).

    python pa_combo_study.py --build            scan nifty500, write data/pa_combo_signals.csv
    python pa_combo_study.py --placebo          analyse with cohort labels shuffled (debug)
    python pa_combo_study.py --run              THE analysis - run once
    python pa_combo_study.py --forward          count the live Daily-board ledger rows

The combo is gm_trigger_board.pa_combo - the function the board uses - so the study and
the board cannot read a different candle.
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
SIG = os.path.join(HERE, "data", "pa_combo_signals.csv")
LEDGER = os.path.join(HERE, "logs", "pa_combo_ledger.csv")
DAYS = 500            # ~2 years of signal days
WIN = 400             # bars of history handed to the battery on each day
LOOK = 3
H = 20                # outcome horizon, sessions
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
    import gm_trigger_board as gtb
    try:
        df = dp.fetch_ohlcv(sym, period="5y", interval="1d", use_cache=True)
    except Exception:
        return []
    if df is None or len(df) < WIN + DAYS // 4:
        return []
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    n = len(df)
    sma150 = df["Close"].rolling(150).mean()
    atr = _atr14(df)
    start = max(WIN, n - DAYS - H - 1)
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
    for t in range(start, n - H - 1):
        c = float(df["Close"].iloc[t])
        s150, s150p = sma150.iloc[t], sma150.iloc[t - 20]
        if not (s150 == s150 and s150p == s150p and c > s150 and s150 > s150p):
            continue
        st = s_at(t)
        cohort, pc = None, None
        if st > 0:
            cohort = "A"
        elif any(s_at(t - k) > 0 for k in range(1, LOOK + 1)):
            x = df.iloc[max(0, t - WIN + 1):t + 1]
            pc = gtb.pa_combo(x, pap.detect_bull_patterns, "")
            if pc is None:
                continue
            if pc["grade"] == "strong" and pc["held"] and pc["kept_low"]:
                cohort = "B"
            elif pc["grade"] == "weak":
                cohort = "C"
            else:
                cohort = "D"
        else:
            continue
        e = float(df["Open"].iloc[t + 1])
        stop = e - STOP_ATR * float(atr.iloc[t])
        risk = e - stop
        if not risk > 0:
            continue
        fut = df.iloc[t + 1:t + 1 + H]
        hit = (fut["Low"] <= stop).values
        r = -1.0 if hit.any() else (float(fut["Close"].iloc[-1]) - e) / risk
        out.append({"symbol": sym, "date": str(df.index[t])[:10], "cohort": cohort,
                    "age": pc["age"] if pc else 0, "grade": pc["grade"] if pc else "",
                    "cpos": round(pc["cpos"], 3) if pc else "", "r20": round(r, 4),
                    "stopped": int(hit.any())})
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


def _boot_diff(x: pd.DataFrame, y: pd.DataFrame, rng) -> tuple[float, float]:
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
        rng0 = np.random.default_rng(7)
        m = d["cohort"].isin(["B", "C", "D"])
        d.loc[m, "cohort"] = rng0.permutation(d.loc[m, "cohort"].values)
    d = _dedup(d)
    d["date"] = pd.to_datetime(d["date"])
    cut = d["date"].quantile(0.6)
    rng = np.random.default_rng(11)
    print(("PLACEBO - " if placebo else "") + f"signals after de-dup: {len(d)} · split at {cut.date()}")
    res = {}
    for name, w in (("IS", d[d["date"] <= cut]), ("OOS", d[d["date"] > cut])):
        print(f"\n== {name} ({w['date'].min().date()} .. {w['date'].max().date()})")
        for c in "ABCD":
            g = w[w["cohort"] == c]
            if len(g):
                print(f"  {c}: n {len(g):5d}  mean {g.r20.mean():+.3f}R  median {g.r20.median():+.3f}R"
                      f"  stopped {g.stopped.mean()*100:5.1f}%")
        A, B, C = (w[w["cohort"] == k] for k in "ABC")
        thin = min(len(A), len(B), len(C)) < N_MIN
        ab = _boot_diff(B, A, rng) if len(A) and len(B) else (np.nan, np.nan)
        bc = _boot_diff(B, C, rng) if len(B) and len(C) else (np.nan, np.nan)
        h1 = (not thin and B.r20.mean() - A.r20.mean() >= -0.05
              and B.r20.median() >= A.r20.median() - 0.10 and ab[0] > -0.15)
        h2 = (not thin and B.r20.mean() - C.r20.mean() >= 0.15 and bc[0] > 0)
        print(f"  B-A mean {B.r20.mean() - A.r20.mean():+.3f}R  CI [{ab[0]:+.3f}, {ab[1]:+.3f}]"
              f"  median gap {B.r20.median() - A.r20.median():+.3f}R  -> H1 {'PASS' if h1 else 'FAIL'}"
              + (" (THIN)" if thin else ""))
        print(f"  B-C mean {B.r20.mean() - C.r20.mean():+.3f}R  CI [{bc[0]:+.3f}, {bc[1]:+.3f}]"
              f"  -> H2 {'PASS' if h2 else 'FAIL'}" + (" (THIN)" if thin else ""))
        res[name] = (h1, h2)
    h1 = all(v[0] for v in res.values())
    h2 = all(v[1] for v in res.values())
    print(f"\nVERDICT  H1 {'PASS' if h1 else 'FAIL'} · H2 {'PASS' if h2 else 'FAIL'} -> "
          + ("PROMOTE (board + S4)" if h1 and h2 else
             "recency only, grade adds nothing" if h1 else "stays display-only"))
    return 0


def forward() -> int:
    if not os.path.exists(LEDGER):
        print("no ledger rows yet"); return 0
    d = pd.read_csv(LEDGER).drop_duplicates(["symbol", "bar_ts"])
    print(f"forward ledger: {len(d)} rows, {d['bar_ts'].nunique()} sessions")
    print(d.groupby("grade").size().to_dict())
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--placebo", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--forward", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    if a.build:
        return build(a.workers)
    if a.forward:
        return forward()
    if a.placebo or a.run:
        return analyse(placebo=a.placebo)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
