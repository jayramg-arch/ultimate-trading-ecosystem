#!/usr/bin/env python3
"""P-less 5/5 on the live boards (pre-registered: docs/PREREG_p_less_forward.md, 16-Oct-2026).

    python p_less_study.py --placebo                 GO/NOP labels shuffled (plumbing check)
    python p_less_study.py --run                     THE first run (16 Oct)
    python p_less_study.py --run --after 2026-10-16  the forward confirmation (15 Dec)
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
START = "2026-08-18"
RULE = {"Daily": (4.0, 20), "75m": (1.5, 5), "125m": (1.5, 5)}   # stop x ATR(D), horizon sessions
DEDUP = 5
N_MIN = 60
BOOT = 2000


def _rows(after: str | None) -> pd.DataFrame:
    d = pd.read_csv(LOG)
    d = d[d["signal_date"] >= START].copy()
    if after:
        d = d[d["signal_date"] > after]
    s = d["s4go"].astype(str)
    own = ~s.str.startswith("⏱")
    d["grp"] = None
    d.loc[own & s.str.match(r"5/5"), "grp"] = "GO"
    d.loc[own & s.str.contains("4/5 · no PA", regex=False), "grp"] = "NOP"
    d = d[d["grp"].notna() & d["tf"].isin(list(RULE))]
    keep = []
    for (_s, _t, _g), g in d.sort_values(["signal_date", "signal_time"]).groupby(["symbol", "tf", "grp"]):
        last = None
        for i, dt_ in zip(g.index, pd.to_datetime(g["signal_date"])):
            if last is None or np.busday_count(last.date(), dt_.date()) >= DEDUP:
                keep.append(i)
                last = dt_
    return d.loc[keep]


def _score(d: pd.DataFrame) -> pd.DataFrame:
    import data_provider as dp
    out = []
    cache = {}
    for _, r in d.iterrows():
        sym = str(r["symbol"])
        if sym not in cache:
            try:
                f = dp.fetch_ohlcv(sym, period="1y", interval="1d", use_cache=True)
                f = f[["Open", "High", "Low", "Close"]].dropna()
                if getattr(f.index, "tz", None) is not None:
                    f.index = f.index.tz_localize(None)
                h, l, c = f["High"], f["Low"], f["Close"]
                tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
                f["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
                cache[sym] = f
            except Exception:
                cache[sym] = None
        f = cache[sym]
        if f is None or f.empty:
            continue
        k_atr, H = RULE[r["tf"]]
        sig = pd.Timestamp(r["signal_date"])
        pos = int(np.searchsorted(f.index.values, np.datetime64(sig), side="right"))   # first session AFTER
        if pos < 1 or pos + H > len(f):
            continue                                                                   # not matured
        e = float(f["Open"].iloc[pos])
        risk = k_atr * float(f["atr"].iloc[pos - 1])
        if not risk > 0:
            continue
        fut = f.iloc[pos:pos + H]
        hit = (fut["Low"] <= e - risk).values
        rr = -1.0 if hit.any() else (float(fut["Close"].iloc[-1]) - e) / risk
        out.append({"symbol": sym, "tf": r["tf"], "grp": r["grp"], "date": r["signal_date"],
                    "r": round(rr, 4), "stopped": int(hit.any())})
    return pd.DataFrame(out)


def _boot(x, y, rng):
    sx = {s: g["r"].values for s, g in x.groupby("symbol")}
    sy = {s: g["r"].values for s, g in y.groupby("symbol")}
    kx, ky = list(sx), list(sy)
    diffs = [np.concatenate([sx[k] for k in rng.choice(kx, len(kx))]).mean()
             - np.concatenate([sy[k] for k in rng.choice(ky, len(ky))]).mean() for _ in range(BOOT)]
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def analyse(placebo: bool, after: str | None) -> int:
    rows = _rows(after)
    if placebo:
        rows["grp"] = np.random.default_rng(7).permutation(rows["grp"].values)
    s = _score(rows)
    print(("PLACEBO - " if placebo else "") + f"rows after de-dup {len(rows)} · matured & scored {len(s)}"
          + (f" · signals after {after}" if after else ""))
    for tf in RULE:
        x = s[s["tf"] == tf]
        for g in ("GO", "NOP"):
            y = x[x["grp"] == g]
            if len(y):
                print(f"  {tf:5} {g:3}: n {len(y):4d}  mean {y.r.mean():+.3f}R  median {y.r.median():+.3f}R  stopped {y.stopped.mean()*100:5.1f}%")
    G, N = s[s["grp"] == "GO"], s[s["grp"] == "NOP"]
    thin = min(len(G), len(N)) < N_MIN
    ci = _boot(N, G, np.random.default_rng(11)) if len(G) and len(N) else (np.nan, np.nan)
    dm = N.r.mean() - G.r.mean() if len(G) and len(N) else np.nan
    dmed = N.r.median() - G.r.median() if len(G) and len(N) else np.nan
    # AMENDMENT 1 (16-Oct, before the real run): the median gap false-failed 9/40 placebo
    # shuffles (45% of outcomes sit at exactly -1R); replaced by the stop-out rate gap.
    dst = (N.stopped.mean() - G.stopped.mean()) * 100 if len(G) and len(N) else np.nan
    h = (not thin) and dm >= -0.10 and dst <= 10.0 and ci[0] > -0.30
    print(f"\nPOOLED  GO n {len(G)}  NOP n {len(N)}  |  NOP-GO mean {dm:+.3f}R  CI [{ci[0]:+.3f}, {ci[1]:+.3f}]"
          f"  stop-out gap {dst:+.1f}pp  (median gap {dmed:+.3f}R, descriptive)")
    print(f"VERDICT  H {'PASS' if h else ('THIN' if thin else 'FAIL')} -> "
          + ("P-less is supported on the live boards; turning P into a tag is Jay's call" if h
             else "P stays a gate"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--placebo", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--after", default=None)
    a = ap.parse_args()
    if a.placebo or a.run:
        return analyse(a.placebo, a.after)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
