"""followthrough_d2.py - scorer for docs/PREREG_followthrough_D2.md (registered 2-Oct-2026).

Does a positional trade with no follow-through by the Day-2 close end worse, and would
exiting it there beat holding? Every definition, threshold and decision rule is fixed in
the pre-registration; this file only implements it.

Until there are >= MIN_FAIL FT-FAIL trades (tiers 1 + 2) with R20 elapsed it prints COUNTS
ONLY - the real analysis runs once, at the threshold. --placebo shuffles the FT-FAIL label
across all trades so the code can be exercised without spending the run.

    python followthrough_d2.py            counts (or the one real run, once the sample is there)
    python followthrough_d2.py --placebo  debug run on shuffled labels (numbers are noise by construction)
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SHADOW = os.path.join(HERE, "logs", "entry_shadow.csv")
SINCE = "2026-10-03"
MIN_FAIL = 40
THIN = 15
H1_GAP, H2_GAP = 0.30, 0.15
_bars: dict = {}


def _daily(sym):
    if sym not in _bars:
        try:
            import data_provider as dp
            d = dp.fetch_ohlcv(sym, period="1y", interval="1d", use_cache=True)
            if getattr(d.index, "tz", None) is not None:
                d.index = d.index.tz_localize(None)
            _bars[sym] = d[["Open", "High", "Low", "Close"]].dropna()
        except Exception:
            _bars[sym] = None
    return _bars[sym]


def score(r) -> dict | None:
    d = _daily(str(r["symbol"]))
    if d is None or d.empty:
        return None
    fill_day = pd.Timestamp(str(r["fill_ts"])).normalize()
    after = d[d.index.normalize() > fill_day]
    if len(after) < 2:
        return None
    e, s = float(r["entry_px"]), float(r["stop_used"])
    risk = e - s
    if risk <= 0:
        return None
    out = {"ft_fail": float(after["Close"].iloc[1]) <= e,
           "ft_fail_b": not any(after["Close"].iloc[:2] > after["Open"].iloc[:2])}
    stopped_r = None
    for i, (_, b) in enumerate(after.iterrows()):
        if stopped_r is None and b["Low"] <= s:
            stopped_r = (min(b["Open"], s) - e) / risk
        n = i + 1
        cur = stopped_r if stopped_r is not None else (b["Close"] - e) / risk
        if n == 2:
            out["R_exitD2"] = cur
        if n == 20:
            out["R20"] = cur
        out["R_last"] = cur
        if n == 40:
            out["R40"] = cur
            break
    return out


def _boot(df, col, n=10000, seed=7):
    syms = df["symbol"].unique()
    rng = np.random.default_rng(seed)
    g = {k: v[col].values for k, v in df.groupby("symbol")}
    m = []
    for _ in range(n):
        pick = rng.choice(syms, len(syms))
        m.append(np.mean(np.concatenate([g[k] for k in pick])))
    return np.percentile(m, [2.5, 97.5])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--placebo", action="store_true")
    ap.add_argument("--since", help="PLACEBO ONLY: widen the window to exercise the code on older rows")
    a = ap.parse_args()
    since = SINCE
    if a.since:
        if not a.placebo:
            print("--since is allowed only with --placebo (the real run's window is pre-registered)"); return 2
        since = a.since
    if not os.path.exists(SHADOW):
        print("no entry_shadow.csv yet"); return 0
    sh = pd.read_csv(SHADOW)
    need = {"variant", "status", "plan_type", "fill_ts", "stop_used", "entry_px", "ts", "tier"}
    if not need.issubset(sh.columns):
        print("entry_shadow.csv lacks %s - rerun entry_shadow.py" % sorted(need - set(sh.columns))); return 0
    sh = sh[(sh["variant"] == "S_4atrD") & (sh["status"] == "scored") & (sh["plan_type"] == "positional")
            & (pd.to_datetime(sh["ts"], errors="coerce") >= pd.Timestamp(since)) & sh["tier"].isin([1, 2])]
    rows = []
    for _, r in sh.iterrows():
        o = score(r)
        if o:
            rows.append(dict(symbol=r["symbol"], tier=int(r["tier"]), ts=r["ts"], **o))
    df = pd.DataFrame(rows)
    n_all = len(df)
    n_fail = int(df["ft_fail"].sum()) if n_all else 0
    n_fail20 = int(df.loc[df["ft_fail"], "R20"].notna().sum()) if n_all and "R20" in df else 0
    print("DAY-2 FOLLOW-THROUGH (pre-registered %s+): %d positional trades with Day 2 elapsed, "
          "%d FT-FAIL, %d of them with R20 elapsed (run needs %d)" % (since, n_all, n_fail, n_fail20, MIN_FAIL))
    if not a.placebo and n_fail20 < MIN_FAIL:
        print("counts only - the analysis runs once, at the threshold.")
        return 0
    if a.placebo:
        print("PLACEBO - labels shuffled within symbol; every number below is noise by construction.")
        rng = np.random.default_rng(1)
        # Shuffle ACROSS all trades. Within-symbol shuffling (the first version) leaves a
        # one-trade symbol's real label in place - on 2-Oct it leaked the real labels.
        df["ft_fail"] = rng.permutation(df["ft_fail"].values)
    hz = "R20"
    if "R20" not in df.columns:
        df["R20"] = np.nan
    if a.placebo and df["R20"].notna().sum() == 0:
        hz = "R_last"
        print("(no trade has 20 sessions yet - the placebo uses the latest available R)")
    d = df[df[hz].notna()].copy()
    d["R20"] = d[hz]
    for name, sub in [("tier 1 · S4 alert", d[d.tier == 1]), ("tier 2 · board", d[d.tier == 2]), ("tiers 1+2", d)]:
        f, p = sub[sub.ft_fail], sub[~sub.ft_fail]
        print("\n== %s: FT-FAIL n=%d  FT-PASS n=%d%s" % (name, len(f), len(p), "  (THIN)" if len(f) < THIN else ""))
        if len(f) and len(p):
            gap = p["R20"].mean() - f["R20"].mean()
            print("  H1  mean R20 pass %+.3f  fail %+.3f  gap %+.3fR  (needs >= %.2f)" % (p["R20"].mean(), f["R20"].mean(), gap, H1_GAP))
        if len(f) and len(p):
            # H2' (Amendment 2): the Day-2 exit benefit must be larger for FT-FAIL than for
            # FT-PASS. An early exit beats holding in ANY falling tape, so the plain benefit
            # (the original H2) measured the tape - a shuffled-label placebo passed it.
            sub = sub.assign(diff=sub["R_exitD2"] - sub["R20"])
            did = sub.loc[sub.ft_fail, "diff"].mean() - sub.loc[~sub.ft_fail, "diff"].mean()
            syms = sub["symbol"].unique()
            rng = np.random.default_rng(7)
            g = {k: v for k, v in sub.groupby("symbol")}
            boots = []
            for _ in range(10000):
                x = pd.concat([g[k] for k in rng.choice(syms, len(syms))])
                fa, pa = x.loc[x.ft_fail, "diff"], x.loc[~x.ft_fail, "diff"]
                if len(fa) and len(pa):
                    boots.append(fa.mean() - pa.mean())
            ci = np.percentile(boots, [2.5, 97.5]) if boots else (np.nan, np.nan)
            print("  H2' D2-exit benefit FAIL %+.3fR vs PASS %+.3fR -> difference %+.3fR  CI95 [%+.3f, %+.3f]"
                  "  FAIL median %+.3fR  (needs diff >= %.2f, CI > 0, median >= 0)" % (
                      sub.loc[sub.ft_fail, "diff"].mean(), sub.loc[~sub.ft_fail, "diff"].mean(), did,
                      ci[0], ci[1], sub.loc[sub.ft_fail, "diff"].median(), H2_GAP))
    print("\nDecision rule: docs/PREREG_followthrough_D2.md - H1 and H2' both, same H2' sign in tiers 1 and 2.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
