# -*- coding: utf-8 -*-
"""rv_band_intraday_study.py — does the RV inverted U survive on 75m bars, where S4
actually applies the gate?

PRE-REGISTERED in docs/PREREG_rv_band.md, ADDENDUM (A1-A6), written before this file.
The corrected criterion E' (deployment must beat BOTH the floor and the no-gate arm) and
the falsifier are fixed there and are not renegotiated here.

WHY THIS IS A SEPARATE TEST, NOT A FORMALITY
--------------------------------------------
The daily study found a clean inverted U (0.8-1.5 = +4.6% vs both tails negative) that
passed four of five criteria and STRENGTHENED out of sample. But it was measured on DAILY
bars from the validation harness, and S4 applies rv_floor on 75m/125m. Two reasons that
may not transfer:

  1. Different distribution entirely.
  2. Intraday RV is TIME-OF-DAY BIASED. chart_rv = volume / sma(volume,50)[1] uses a
     rolling mean that MIXES every bar of the session, and NSE volume is U-shaped. Measured
     18-Aug over 14,466 bar-observations: the V gate passes 48.2% at 10:30 and ~18% midday
     - a 2.8x swing from clock position alone.

So this measures the band under BOTH RV definitions: S4's current session-mixing baseline,
and a PER-SLOT baseline (each bar against the mean volume of the same bar-of-day). If the
time-of-day bias is noise, debiasing should sharpen the effect. If the bias carries
information, it will not.

DESIGN
------
RV on 75m bars over the ~90 days Dhan serves intraday; OUTCOME on DAILY bars - forward
return over FWD_DAYS from the intraday bar's date, minus the benchmark over the same
window. Intraday history is capped at 90 days, so spending it on the horizon would leave
nothing; daily has the depth.

THE OVERLAP PROBLEM (PREREG A5), because it would otherwise flatter everything
------------------------------------------------------------------------------
~5.5 bars per session share almost the same forward window. Bar counts therefore MASSIVELY
overstate independent evidence. Significance is symbol-block bootstrapped, and bar counts
are reported as BARS, never as sample size. "n=40,000 bars" is not comparable to the daily
study's "n=464 trades" and no such comparison is drawn.

Usage:
    python rv_band_intraday_study.py [--symbols 60] [--days 90] [--minutes 75] [--fwd 20]
Read-only. Touches no gate, no live file.
"""
from __future__ import annotations
import argparse
import os
import sys
import warnings
from datetime import date, timedelta

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dhan_ohlcv as _dh          # noqa: E402
import pa_patterns as pap         # noqa: E402
import data_provider as dp        # noqa: E402
from rv_time_of_day_study import universe, RV_LEN   # noqa: E402
import pa_field_validator as _pafv                  # noqa: E402
from replay import GO_BULL_TRIGGERS                 # noqa: E402

BAND_LO, BAND_HI = 0.8, 1.5      # PREREG section 2 - fixed from the 13-Aug sample
FLOOR = 1.0
BENCH = "^CRSLDX"


def _slot_rv(df: pd.DataFrame, minutes: int) -> pd.Series:
    """PER-SLOT baseline: each bar against the mean volume of the SAME bar-of-day over
    prior sessions. This is the debiased alternative to S4's session-mixing mean.
    Expanding + shifted, so a bar is never part of its own baseline."""
    v = df["Volume"].astype(float)
    slot = (df.index + pd.Timedelta(minutes=minutes)).strftime("%H:%M")
    out = pd.Series(index=df.index, dtype=float)
    for s in pd.unique(slot):
        m = slot == s
        vv = v[m]
        base = vv.expanding().mean().shift(1)
        out[m] = vv / base
    return out.replace([np.inf, -np.inf], np.nan)


def _bars(sym: str, minutes: int, days: int):
    try:
        base = _dh.fetch_intraday(sym,
                                  from_date=(date.today() - timedelta(days=days)).isoformat(),
                                  to_date=date.today().isoformat(), interval=25)
        if base is None or base.empty:
            return None
        if isinstance(base.columns, pd.MultiIndex):
            base.columns = base.columns.get_level_values(0)
        df = pap.resample_intraday(base, minutes, base_minutes=25)
        if df is None or len(df) < RV_LEN + 5:
            return None
        v = df["Volume"].astype(float)
        cur = (v / v.rolling(RV_LEN).mean().shift(1)).replace([np.inf, -np.inf], np.nan)
        out = pd.DataFrame({"rv_cur": cur, "rv_slot": _slot_rv(df, minutes), "vol": v})
        # resample_intraday labels a bar by its OPEN; the gate fires at the CLOSE.
        # Getting this backwards inverted a finding on 18-Aug.
        out["close_ts"] = df.index + pd.Timedelta(minutes=minutes)
        out["day"] = out["close_ts"].dt.normalize()
        out["symbol"] = sym
        # V2 (PREREG addendum): mark bars where a BULL PA trigger fired. Vectorised via
        # compute_pa_detectors - the same per-bar path replay._go_pa_series uses - because
        # detect_bull_patterns evaluates the LAST bar only and would need one call per bar.
        try:
            det = _pafv.compute_pa_detectors(df)
            cols = [c for c in GO_BULL_TRIGGERS if c in det.columns]
            pa = det[cols[0]].astype(bool)
            for c in cols[1:]:
                pa = pa | det[c].astype(bool)
            out["pa"] = pa.reindex(df.index).fillna(False).values
        except Exception:
            out["pa"] = False
        out = out[out["vol"] > 0]            # Dhan's phantom 15:30 stub
        return out.dropna(subset=["rv_cur"])
    except Exception:
        return None


def _fwd_map(sym: str, fwd: int):
    """day -> forward % return over `fwd` trading days, from DAILY bars."""
    try:
        d = dp.fetch_ohlcv(sym, period="1y", interval="1d")
        if d is None or len(d) < fwd + 10:
            return None
        c = d["Close"].astype(float)
        idx = c.index.tz_localize(None) if getattr(c.index, "tz", None) is not None else c.index
        f = (c.shift(-fwd) / c - 1.0) * 100.0
        f.index = idx.normalize()
        return f.dropna()
    except Exception:
        return None


def _blk_ci(d, m_a, m_b, col, n_boot=4000, seed=7):
    w = d[["symbol", col]].copy()
    w["a"], w["b"] = m_a.values, m_b.values
    w = w.dropna(subset=[col])
    syms = w["symbol"].unique()
    groups = {s: g for s, g in w.groupby("symbol")}
    k = len(syms)
    if k < 5:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    out = np.full(n_boot, np.nan)
    for i in range(n_boot):
        blk = pd.concat([groups[syms[j]] for j in rng.integers(0, k, k)], copy=False)
        x, y = blk.loc[blk["a"], col], blk.loc[blk["b"], col]
        if len(x) >= 20 and len(y) >= 20:
            out[i] = x.mean() - y.mean()
    out = out[~np.isnan(out)]
    if out.size < 100:
        return (np.nan, np.nan, np.nan)
    return (float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5)),
            float((out > 0).mean() * 100.0))


def _shape(d, rvcol, acol, label):
    print("   %s" % label)
    edges = [0, 0.5, 0.8, 1.0, 1.5, 2.5, 999]
    names = ["<0.5", "0.5-0.8", "0.8-1.0", "1.0-1.5", "1.5-2.5", "2.5+"]
    d = d.copy()
    d["b"] = pd.cut(d[rvcol], edges, labels=names)
    for b, g in d.groupby("b", observed=True):
        print("      %-9s bars=%6d  mean alpha %+6.2f%%  win %4.1f%%"
              % (b, len(g), g[acol].mean(), (g[acol] > 0).mean() * 100))


def _arms(d, rvcol, acol, tag):
    tot = len(d)
    rows = []
    for lab, m in (("no gate", pd.Series(True, index=d.index)),
                   ("floor RV>=%.1f" % FLOOR, d[rvcol] >= FLOOR),
                   ("band %.1f-%.1f" % (BAND_LO, BAND_HI), (d[rvcol] >= BAND_LO) & (d[rvcol] <= BAND_HI))):
        s = d[m]
        if len(s) == 0:
            continue
        keep = len(s) / tot
        rows.append((lab, len(s), keep * 100, s[acol].mean(), (s[acol] > 0).mean() * 100, s[acol].mean() * keep))
    print("   %s" % tag)
    for lab, n, keep, mean, win, dep in rows:
        print("      %-18s bars=%6d  keep %5.1f%%  mean %+6.2f%%  win %4.1f%%  deployment %+6.2f%%"
              % (lab, n, keep, mean, win, dep))
    return {r[0]: r for r in rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=60)
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--minutes", type=int, default=75)
    ap.add_argument("--fwd", type=int, default=20)
    ap.add_argument("--pa-only", action="store_true",
                    help="V2: restrict to bars where a BULL PA TRIGGER fired - the actual "
                         "decision point where S4 consults the V gate. Without this the "
                         "population is every bar of every board name, on which 'no gate' "
                         "is not a strategy and E' cannot be validly evaluated.")
    a = ap.parse_args()

    syms = universe(a.symbols)
    print("POPULATION: %s" % ("PA-TRIGGER BARS ONLY (v2)" if a.pa_only else "ALL BARS (v1 - E' not valid here)"))
    print("universe: %d board names · %dm bars · %d days intraday · outcome = %dd forward vs %s"
          % (len(syms), a.minutes, a.days, a.fwd, BENCH))

    bench = _fwd_map(BENCH, a.fwd)
    if bench is None:
        print("benchmark unavailable — cannot compute alpha"); return 1

    frames, miss = [], 0
    for i, s in enumerate(syms, 1):
        b = _bars(s, a.minutes, a.days)
        f = _fwd_map(s, a.fwd) if b is not None else None
        if b is None or f is None:
            miss += 1
            continue
        b["fwd"] = b["day"].map(f)
        b["bmk"] = b["day"].map(bench)
        b = b.dropna(subset=["fwd", "bmk"])
        if len(b):
            b["alpha"] = b["fwd"] - b["bmk"]
            frames.append(b)
        if i % 15 == 0:
            print("   ...%d/%d" % (i, len(syms)), file=sys.stderr)
    if not frames:
        print("no data resolved — nothing to measure"); return 1
    d = pd.concat(frames, ignore_index=True)
    if a.pa_only:
        before = len(d)
        d = d[d.get("pa", False) == True].copy()
        print("PA-trigger bars: %d of %d (%.1f%%)" % (len(d), before, len(d) / max(before, 1) * 100))
        if len(d) < 200:
            print("too few PA-trigger bars to measure — stopping rather than reporting noise")
            return 1
    print("resolved %d/%d symbols (%d skipped) · %d bar-observations"
          % (len(syms) - miss, len(syms), miss, len(d)))
    print("bars are NOT independent — ~%.1f per session share one forward window (PREREG A5)"
          % (len(d) / max(d["day"].nunique() * d["symbol"].nunique(), 1)))
    print()

    print("=== H2 · SHAPE ===")
    _shape(d, "rv_cur", "alpha", "CURRENT RV (S4 today, session-mixing baseline)")
    print()
    _shape(d, "rv_slot", "alpha", "PER-SLOT RV (debiased)")
    print()

    print("=== ARMS ===")
    cur = _arms(d, "rv_cur", "alpha", "CURRENT RV")
    print()
    slot = _arms(d, "rv_slot", "alpha", "PER-SLOT RV")
    print()

    for tag, rvcol, res in (("CURRENT", "rv_cur", cur), ("PER-SLOT", "rv_slot", slot)):
        bm = (d[rvcol] >= BAND_LO) & (d[rvcol] <= BAND_HI)
        fm = d[rvcol] >= FLOOR
        edge = d.loc[bm, "alpha"].mean() - d.loc[fm, "alpha"].mean()
        lo, hi, pp = _blk_ci(d, bm, fm, "alpha")
        halves = []
        mid = d["day"].median()
        for sub in (d[d["day"] < mid], d[d["day"] >= mid]):
            b2 = (sub[rvcol] >= BAND_LO) & (sub[rvcol] <= BAND_HI)
            f2 = sub[rvcol] >= FLOOR
            halves.append(sub.loc[b2, "alpha"].mean() - sub.loc[f2, "alpha"].mean()
                          if b2.sum() > 20 and f2.sum() > 20 else np.nan)
        keys = list(res.keys())
        dep_band = res[keys[-1]][5] if len(keys) >= 3 else np.nan
        dep_floor = res[keys[1]][5] if len(keys) >= 2 else np.nan
        dep_none = res[keys[0]][5] if keys else np.nan
        A = d["symbol"].nunique() >= 40
        B = edge >= 1.0
        C = (not np.isnan(lo)) and (lo > 0 or hi < 0)
        D = all((not np.isnan(h)) and h > 0 for h in halves)
        E = (not np.isnan(dep_band)) and dep_band > dep_floor and dep_band > dep_none
        print("--- ADOPTION RULE · %s RV (PREREG addendum A6) ---" % tag)
        print("   A symbols>=40 .............. %4d           %s" % (d["symbol"].nunique(), "PASS" if A else "FAIL"))
        print("   B band-floor >= +1.0pp ..... %+.2fpp        %s" % (edge, "PASS" if B else "FAIL"))
        print("   C CI excludes zero ......... [%+.2f,%+.2f]  %s" % (lo, hi, "PASS" if C else "FAIL"))
        print("   D both halves same sign .... %-15s %s" % (["%+.2f" % h for h in halves], "PASS" if D else "FAIL"))
        print("   E' deployment beats both ... band %+.2f vs floor %+.2f / none %+.2f  %s"
              % (dep_band, dep_floor, dep_none, "PASS" if E else "FAIL"))
        print("   VERDICT: %s" % ("ADOPT" if all((A, B, C, D, E)) else "DO NOT ADOPT"))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
