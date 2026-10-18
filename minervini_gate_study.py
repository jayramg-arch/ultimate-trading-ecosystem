#!/usr/bin/env python3
"""The Minervini trend template as a v1 gate (pre-registered: docs/PREREG_minervini_gate_v1.md).

    python minervini_gate_study.py --placebo   8/8 labels shuffled (must FAIL)
    python minervini_gate_study.py --run       THE run - once

Unit and outcome are p_less_study's (same rows, de-dup, entry, stop and horizon); the 8 checks are
commander_core.minervini_checks, rebuilt as of each signal date.
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
import p_less_study as pl   # noqa: E402  (the shared unit and scoring)

N_MIN, BOOT = 60, 2000


def _rows() -> pd.DataFrame:
    d = pd.read_csv(pl.LOG, low_memory=False)
    d = d[d["signal_date"] >= pl.START].copy()
    s = d["s4go"].astype(str)
    d = d[~s.str.startswith("⏱") & s.str.match(r"5/5") & d["tf"].isin(list(pl.RULE))].copy()
    keep = []
    for _k, g in d.sort_values(["signal_date", "signal_time"]).groupby(["symbol", "tf"]):
        last = None
        for i, dt_ in zip(g.index, pd.to_datetime(g["signal_date"])):
            if last is None or np.busday_count(last.date(), dt_.date()) >= pl.DEDUP:
                keep.append(i)
                last = dt_
    return d.loc[keep]


def _weekly(daily: pd.DataFrame, upto: pd.Timestamp) -> pd.DataFrame:
    w = daily.loc[:upto].resample("W-FRI").agg({"Open": "first", "High": "max", "Low": "min",
                                                "Close": "last", "Volume": "sum"}).dropna()
    return w[w.index <= upto]                       # the week still forming at the signal is out


def template_scores(rows: pd.DataFrame) -> pd.Series:
    """v1's 8 checks as of each signal date -> score 0..8 (NaN when history is short)."""
    import data_provider as dp
    import bull_screener as bs
    import commander_core as cc

    def _load(sym):
        f = dp.fetch_ohlcv(sym, period="2y", interval="1d", use_cache=True)
        f = f[["Open", "High", "Low", "Close", "Volume"]].dropna()
        if getattr(f.index, "tz", None) is not None:
            f.index = f.index.tz_localize(None)
        return f[~f.index.duplicated(keep="last")]
    bench = _load("^CRSLDX")
    cache, out = {}, {}
    for i, r in rows.iterrows():
        sym = str(r["symbol"])
        if sym not in cache:
            try:
                cache[sym] = _load(sym)
            except Exception:
                cache[sym] = None
        f = cache[sym]
        if f is None or f.empty:
            continue
        sig = pd.Timestamp(r["signal_date"])
        h = f.loc[:sig]
        if len(h) < 230:
            continue
        c = h["Close"]
        s50, s150, s200 = c.rolling(50).mean(), c.rolling(150).mean(), c.rolling(200).mean()
        ctx = {"sma50": float(s50.iloc[-1]), "sma150": float(s150.iloc[-1]), "sma200": float(s200.iloc[-1]),
               "sma200_prev": float(s200.iloc[-22]) if len(s200) > 22 else None,
               "high52w": float(h["High"].rolling(min(252, len(h))).max().iloc[-1]),
               "low52w": float(h["Low"].rolling(min(252, len(h))).min().iloc[-1])}
        try:
            wk = bs.compute_weekly_indicators(_weekly(f, sig), _weekly(bench, sig))
            mans = float(wk["mansfield"])
        except Exception:
            mans = None
        px = float(r["cmp"]) if r["cmp"] == r["cmp"] else float(c.iloc[-1])
        out[i], _ = cc.minervini_checks(ctx, px, mans)
    return pd.Series(out)


def _boot(x, y, rng):
    sx = {s: g["r"].values for s, g in x.groupby("symbol")}
    sy = {s: g["r"].values for s, g in y.groupby("symbol")}
    kx, ky = list(sx), list(sy)
    d = [np.concatenate([sx[k] for k in rng.choice(kx, len(kx))]).mean()
         - np.concatenate([sy[k] for k in rng.choice(ky, len(ky))]).mean() for _ in range(BOOT)]
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def analyse(placebo: bool) -> int:
    rows = _rows()
    sc = template_scores(rows)
    rows = rows.loc[sc.index].copy()
    rows["tscore"] = sc.astype(int)
    rows["grp"] = np.where(rows["tscore"] >= 8, "T8", "T<=7")
    out = {}
    for path in ("bull", "recovery"):
        sub = rows[rows["path"] == path].copy()
        if placebo:
            sub["grp"] = np.random.default_rng(7).permutation(sub["grp"].values)
        s = pl._score(sub)
        s = s.merge(sub[["symbol", "tf", "signal_date", "tscore"]].rename(columns={"signal_date": "date"}),
                    on=["symbol", "tf", "date"], how="left")
        out[path] = s
    print(("PLACEBO - " if placebo else "") + "signals (5/5 GO, own clock, de-duplicated) with a template score: %d"
          % len(rows))
    for path, s in out.items():
        print("\n== %s path · matured & scored %d" % (path, len(s)))
        for g in ("T8", "T<=7"):
            y = s[s["grp"] == g]
            if len(y):
                print("  %-5s n %4d  mean %+.3fR  median %+.3fR  stopped %5.1f%%" % (
                    g, len(y), y.r.mean(), y.r.median(), y.stopped.mean() * 100))
        if not placebo:
            for lab, m in (("<=5", s.tscore <= 5), ("6", s.tscore == 6), ("7", s.tscore == 7), ("8", s.tscore == 8)):
                y = s[m]
                if len(y):
                    print("    score %-3s n %4d  mean %+.3fR  stopped %5.1f%%" % (lab, len(y), y.r.mean(), y.stopped.mean() * 100))
            for tf in pl.RULE:
                x = s[s.tf == tf]
                a, b = x[x.grp == "T8"], x[x.grp == "T<=7"]
                if len(a) and len(b):
                    print("    %-5s T8 %+.3fR (n %d) vs T<=7 %+.3fR (n %d)" % (tf, a.r.mean(), len(a), b.r.mean(), len(b)))
    s = out["bull"]
    A, B = s[s["grp"] == "T8"], s[s["grp"] == "T<=7"]
    thin = min(len(A), len(B)) < N_MIN
    ci = _boot(A, B, np.random.default_rng(11)) if len(A) and len(B) else (np.nan, np.nan)
    dm = A.r.mean() - B.r.mean() if len(A) and len(B) else np.nan
    dst = (A.stopped.mean() - B.stopped.mean()) * 100 if len(A) and len(B) else np.nan
    h = (not thin) and dm >= 0.10 and ci[0] > 0 and dst <= 5.0
    print("\nBULL  T8 n %d  T<=7 n %d  |  T8 - T<=7 mean %+.3fR  CI [%+.3f, %+.3f]  stop-out gap %+.1fpp"
          % (len(A), len(B), dm, ci[0], ci[1], dst))
    print("VERDICT  H %s" % ("PASS -> propose the template (8/8) as a bull-path gate (Jay's call, forward check)" if h
                             else ("THIN" if thin else "FAIL -> the template stays a ranking overlay")))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--placebo", action="store_true")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.placebo or a.run:
        return analyse(a.placebo)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
