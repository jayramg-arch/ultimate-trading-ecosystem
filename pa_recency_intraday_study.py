#!/usr/bin/env python3
"""75m / 125m PA recency allowance (pre-registered: docs/PREREG_pa_recency_intraday.md, 16-Oct-2026).

    python pa_recency_intraday_study.py --build      scan the cached 25m bars, write data/pa_recency_intraday.csv
    python pa_recency_intraday_study.py --placebo    A/R labels shuffled (plumbing check only)
    python pa_recency_intraday_study.py --run        THE analysis - run once
"""
from __future__ import annotations

import argparse
import glob
import os
import pickle
import sys
import warnings
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ICACHE = os.path.join(HERE, "validation_runs", "_intraday_cache")
SIG = os.path.join(HERE, "data", "pa_recency_intraday.csv")
WIN = 250
SESS = {75: 5, 125: 3}        # bars per session
H_SESS = 5
STOP_ATR = 1.5                # house_policy.SWING_STOP_FLOOR_ATR_D
GAP_DAYS = 12
DEDUP = 5
N_MIN = 100
BOOT = 2000


def _groups() -> dict:
    g = defaultdict(list)
    for f in glob.glob(os.path.join(ICACHE, "*.pkl")):
        g[os.path.basename(f).rsplit("_", 1)[0]].append(f)
    return dict(g)


def _scan(item) -> list[dict]:
    key, files = item
    import pa_patterns as pap
    import data_provider as dp
    parts = []
    for f in files:
        try:
            d = pickle.load(open(f, "rb"))
            if d is not None and not d.empty:
                parts.append(d)
        except Exception:
            pass
    if not parts:
        return []
    base = pd.concat(parts).sort_index()
    base = base[~base.index.duplicated(keep="first")]
    daily = None
    for sym in (key, key.replace("_", "&")):          # the cache stores '&' as '_'
        try:
            daily = dp.fetch_ohlcv(sym, period="5y", interval="1d", use_cache=True)
        except Exception:
            daily = None
        if daily is not None and not daily.empty:
            break
    if daily is None or daily.empty:
        return []
    daily = daily[["Open", "High", "Low", "Close", "Volume"]].dropna().copy()
    if getattr(daily.index, "tz", None) is not None:
        daily.index = daily.index.tz_localize(None)
    c = daily["Close"]
    sma = c.rolling(150).mean()
    tr = pd.concat([daily["High"] - daily["Low"], (daily["High"] - c.shift()).abs(),
                    (daily["Low"] - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    e20, e10 = c.ewm(span=20, adjust=False).mean(), c.ewm(span=10, adjust=False).mean()
    ddates = daily.index.date

    def ref(day):
        k = int(np.searchsorted(ddates, day)) - 1          # last COMPLETED session
        if k < 170:
            return None
        ok = c.iloc[k] > sma.iloc[k] and sma.iloc[k] > sma.iloc[k - 20]
        return ok, float(e20.iloc[k]), float(e10.iloc[k]), float(atr.iloc[k])

    out = []
    for tf in (75, 125):
        df = pap.resample_intraday(base, tf)
        if df is None or df.empty:
            continue
        df = df.copy()
        if getattr(df.index, "tz", None) is not None:
            df.index = df.index.tz_localize(None)
        df = df[df["Volume"] > 0]
        n = len(df)
        H = H_SESS * SESS[tf]
        refs, sig = {}, {}

        def s_at(j):
            if j not in sig:
                day = df.index[j].date()
                if day not in refs:
                    refs[day] = ref(day)
                rf = refs[day]
                if rf is None or j < 60:
                    sig[j] = 0
                else:
                    try:
                        p = pap.detect_bull_patterns(df.iloc[max(0, j - WIN + 1):j + 1], "", intraday=True,
                                                     ema20_ref=rf[1], ema10_ref=rf[2])
                        sig[j] = sum(t for _n, f, t, _x in p if f)
                    except Exception:
                        sig[j] = 0
            return sig[j]

        for j in range(66, n - H - 1):
            day = df.index[j].date()
            if day not in refs:
                refs[day] = ref(day)
            rf = refs[day]
            if rf is None or not rf[0]:
                continue
            if (df.index[j + H].to_pydatetime() - df.index[j + 1].to_pydatetime()).days > GAP_DAYS:
                continue
            if s_at(j) > 0:
                coh, age = "A", 0
            else:
                age = next((k for k in range(1, 7) if s_at(j - k) > 0), None)
                coh = "F" if age is None else ("R" if age <= 3 else "E")
                age = age or 0
            e = float(df["Open"].iloc[j + 1])
            risk = STOP_ATR * rf[3]
            if not risk > 0:
                continue
            fut = df.iloc[j + 1:j + 1 + H]
            hit = (fut["Low"] <= e - risk).values
            r = -1.0 if hit.any() else (float(fut["Close"].iloc[-1]) - e) / risk
            out.append({"symbol": key, "tf": tf, "ts": str(df.index[j]), "date": str(day), "cohort": coh,
                        "age": age, "r": round(r, 4), "stopped": int(hit.any())})
    return out


def build(workers: int) -> int:
    items = sorted(_groups().items())
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, r in enumerate(ex.map(_scan, items, chunksize=2), 1):
            rows.extend(r)
            if i % 20 == 0:
                print(f"{i}/{len(items)} symbols, {len(rows)} signals", flush=True)
    pd.DataFrame(rows).to_csv(SIG, index=False)
    print("written", SIG, len(rows))
    return 0


def _dedup(d: pd.DataFrame) -> pd.DataFrame:
    keep = []
    for (_s, _c), g in d.sort_values("ts").groupby(["symbol", "cohort"]):
        last = None
        for i, dt_ in zip(g.index, pd.to_datetime(g["date"])):
            if last is None or np.busday_count(last.date(), dt_.date()) >= DEDUP:
                keep.append(i)
                last = dt_
    return d.loc[keep]


def _boot_diff(x, y, rng):
    sx = {s: g["r"].values for s, g in x.groupby("symbol")}
    sy = {s: g["r"].values for s, g in y.groupby("symbol")}
    kx, ky = list(sx), list(sy)
    diffs = []
    for _ in range(BOOT):
        a = np.concatenate([sx[k] for k in rng.choice(kx, len(kx))])
        b = np.concatenate([sy[k] for k in rng.choice(ky, len(ky))])
        diffs.append(a.mean() - b.mean())
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def analyse(placebo: bool) -> int:
    allrows = pd.read_csv(SIG)
    verdict = {}
    for tf in (75, 125):
        d = allrows[allrows["tf"] == tf].copy()
        if placebo:
            m = d["cohort"].isin(["A", "R"])
            d.loc[m, "cohort"] = np.random.default_rng(7).permutation(d.loc[m, "cohort"].values)
        d = _dedup(d)
        d["date"] = pd.to_datetime(d["date"])
        cut = d["date"].median()
        rng = np.random.default_rng(11)
        print(("PLACEBO - " if placebo else "") + f"\n##### {tf}m: signals after de-dup {len(d)} · split at {cut.date()}")
        ok = []
        for name, w in (("H1st", d[d["date"] <= cut]), ("H2nd", d[d["date"] > cut])):
            print(f"== {name} ({w['date'].min().date()} .. {w['date'].max().date()})")
            for c in "AREF":
                g = w[w["cohort"] == c]
                if len(g):
                    print(f"  {c}: n {len(g):5d}  mean {g.r.mean():+.3f}R  median {g.r.median():+.3f}R"
                          f"  stopped {g.stopped.mean()*100:5.1f}%")
            A, R = w[w["cohort"] == "A"], w[w["cohort"] == "R"]
            thin = min(len(A), len(R)) < N_MIN
            ci = _boot_diff(R, A, rng) if len(A) and len(R) else (np.nan, np.nan)
            dm, dmed = R.r.mean() - A.r.mean(), R.r.median() - A.r.median()
            h = (not thin) and dm >= -0.05 and dmed >= -0.10 and ci[0] > -0.15
            print(f"  R-A mean {dm:+.3f}R  CI [{ci[0]:+.3f}, {ci[1]:+.3f}]  median gap {dmed:+.3f}R"
                  f"  -> {'PASS' if h else 'FAIL'}" + (" (THIN)" if thin else ""))
            ok.append(h)
        verdict[tf] = all(ok)
    print("\nVERDICT  " + "  ·  ".join(f"H{tf} {'PASS' if v else 'FAIL'}" for tf, v in verdict.items())
          + "  -> lift the 4/5 cap on: " + (", ".join(f"{tf}m" for tf, v in verdict.items() if v) or "none"))
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
