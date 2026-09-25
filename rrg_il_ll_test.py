"""rrg_il_ll_test.py — IMPROVING->LEADING vs LEADING->LEADING on GO-timed Stage-2 trades.

Implements docs/PREREG_rrg_IL_vs_LL.md EXACTLY (written 25-Sep-2026 before any label).
Trades: validation_20260909_190451 (GO-timed bull, filled). Outcomes AS RECORDED.
Label: the RRG cell at the last CONFIRMED week on or before GO_Date — daily data truncated
at GO_Date, confirmed W-FRI weeks (forming week dropped), strike_cal vs NIFTY 500, and the
verbatim quadrant/next_quadrant of rrg_cell_remeasure.py. Stage 2 = weekly 30-SMA rising
(4-week raw change > 0.0012 x MA), the shared stateless 2x2 (above OR below a rising MA).

  --coverage   labels + counts only (no outcomes)
  --check      label check vs bull_screener._rrg_trajectory on 20 random trades
  --placebo    labels shuffled within GO month — any pass is a bug
  --run        the single real run (marker-guarded)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import data_provider as dp                         # noqa: E402
import pa_patterns as pap                          # noqa: E402
from rrg_engine import calculate_jdk_rrg           # noqa: E402
from rrg_cell_remeasure import quadrant, next_quadrant, TRAIL          # noqa: E402
BENCH = "^CRSLDX"     # Amendment 1: Dhan's "NIFTY 500" returns nothing today; same index


RUNS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validation_runs")
RUN_ID = "20260909_190451"
MARKER = os.path.join(RUNS, "_rrg_IL_LL_REAL_RUN_DONE.json")
LABELS = os.path.join(RUNS, "_rrg_IL_LL_labels.csv")
IS_FRAC, EMBARGO_DAYS = 0.6, 45
BAR_R, MIN_N, N_BOOT = 0.10, 40, 5000
LL, IL, WL = "LEADING -> LEADING", "IMPROVING -> LEADING", "WEAKENING -> LEADING"


def _daily(sym):
    try:
        d = dp.fetch_ohlcv(sym, period="10y", interval="1d", use_cache=True, auto_adjust=True)
    except Exception:
        return None
    if d is None or d.empty:
        return None
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.copy()
    d.index = pd.to_datetime(d.index).tz_localize(None) if getattr(d.index, "tz", None) else pd.to_datetime(d.index)
    return d.sort_index()


_YF = {}


def _yf(sym):
    """Amendment 1 fallback: the yfinance 10-year series for the WHOLE symbol (never spliced)."""
    if sym in _YF:
        return _YF[sym]
    import threading
    import yfinance as yf
    out = {}
    def go():
        try:
            t = sym if sym.startswith("^") else sym + ".NS"
            h = yf.Ticker(t).history(period="10y", auto_adjust=True)
            if h is not None and not h.empty:
                h.index = pd.to_datetime(h.index).tz_localize(None)
                out["d"] = h[["Open", "High", "Low", "Close", "Volume"]].sort_index()
        except Exception:
            pass
    th = threading.Thread(target=go, daemon=True); th.start(); th.join(60)
    _YF[sym] = out.get("d")
    return _YF[sym]


def label_at(d_stock, d_bench, go_date):
    """(cell, stage2, rrg_frame_trunc) as of the last confirmed week <= go_date, or None."""
    s = d_stock[d_stock.index <= go_date]
    b = d_bench[d_bench.index <= go_date]
    if len(s) < 250 or len(b) < 250:
        return None
    ws = pap._confirmed_weekly_ohlcv(s)["Close"].dropna()
    wb = pap._confirmed_weekly_ohlcv(b)["Close"].dropna()
    if len(ws) < 60:
        return None
    rrg = calculate_jdk_rrg(ws, wb, mode="strike_cal")
    if rrg is None or len(rrg) < TRAIL + 1:
        return None
    rrg = rrg.dropna()
    if len(rrg) < TRAIL + 1:
        return None
    r, m = rrg["RS_Ratio"].to_numpy(), rrg["RS_Momentum"].to_numpy()
    cur = quadrant(r[-1], m[-1])
    nxt = next_quadrant(cur, r[-1] - r[-1 - TRAIL], m[-1] - m[-1 - TRAIL])
    ma = ws.rolling(30).mean()
    if len(ma.dropna()) < 5:
        return None
    stage2 = bool(ma.iloc[-1] - ma.iloc[-5] > 0.0012 * ma.iloc[-1])
    return f"{cur} -> {nxt}", stage2, rrg


def build_labels():
    d = pd.read_csv(os.path.join(RUNS, f"validation_{RUN_ID}_details.csv"))
    d = d[d["Alpha_Matched_pct"].notna() & d["GO_Date"].notna()].copy()
    d["go"] = pd.to_datetime(d["GO_Date"])
    d["R"] = d["Return_pct"] / d["SL_pct"].where(d["SL_pct"] > 0)
    bench = _daily(BENCH)
    if bench is None:
        sys.exit("benchmark data unavailable")
    bench_yf = _yf(BENCH)
    cells, st2, srcs, cache = [], [], [], {}
    for i, r in enumerate(d.itertuples(index=False), 1):
        sym = r.Symbol
        if sym not in cache:
            cache[sym] = _daily(sym)
        out = label_at(cache[sym], bench, r.go) if cache[sym] is not None else None
        src = "dhan" if out else None
        if out is None and bench_yf is not None:          # Amendment 1: depth fallback, both legs yf
            ys = _yf(sym)
            out = label_at(ys, bench_yf, r.go) if ys is not None else None
            src = "yfinance" if out else None
        cells.append(out[0] if out else None)
        st2.append(out[1] if out else None)
        srcs.append(src)
        if i % 100 == 0:
            print(f"  labelled {i}/{len(d)}", flush=True)
    d["cell"], d["stage2"], d["src"] = cells, st2, srcs
    d.to_csv(LABELS, index=False)
    return d, cache, bench


def load_labels():
    d = pd.read_csv(LABELS)
    d["go"] = pd.to_datetime(d["go"])
    return d


def split(d):
    dates = sorted(d["go"].unique())
    cut = dates[int(round(len(dates) * IS_FRAC))]
    IS = d[d["go"] <= cut - pd.Timedelta(days=EMBARGO_DAYS)]
    OOS = d[d["go"] > cut]
    return IS, OOS, cut


def boot_diff(a, b, rng):
    """Symbol-block bootstrap of mean R(a) - mean R(b)."""
    both = pd.concat([a.assign(_g=1), b.assign(_g=0)])
    syms = both["Symbol"].unique()
    grp = {s: g for s, g in both.groupby("Symbol")}
    out = []
    for _ in range(N_BOOT):
        pick = rng.choice(syms, size=len(syms), replace=True)
        bb = pd.concat([grp[s] for s in pick])
        x, y = bb.loc[bb["_g"] == 1, "R"], bb.loc[bb["_g"] == 0, "R"]
        if len(x) and len(y):
            out.append(x.mean() - y.mean())
    return np.percentile(out, [2.5, 97.5])


def report(d, label, rng):
    s = d[(d["stage2"] == True) & d["cell"].notna() & d["R"].notna()].copy()   # noqa: E712
    IS, OOS, cut = split(s)
    print(f"\n==== {label} ====  Stage-2 labelled trades {len(s)} · IS {len(IS)} · OOS {len(OOS)} (cut {str(cut)[:10]}, purge {EMBARGO_DAYS}d)")
    print(f"  {'cell':24}{'n IS':>6}{'n OOS':>7}{'R IS':>8}{'R OOS':>8}{'med R':>8}{'α% all':>8}{'stop%':>7}{'T1%':>6}")
    for c in (LL, WL, IL):
        a, i, o = s[s["cell"] == c], IS[IS["cell"] == c], OOS[OOS["cell"] == c]
        stop = a["Hit_Initial_SL"].mean() * 100 if "Hit_Initial_SL" in a and len(a) else float("nan")
        t1 = a["Hit_T1"].mean() * 100 if "Hit_T1" in a and len(a) else float("nan")
        print(f"  {c:24}{len(i):6d}{len(o):7d}{i['R'].mean():+8.3f}{o['R'].mean():+8.3f}"
              f"{a['R'].median():+8.3f}{a['Alpha_Matched_pct'].mean():+8.2f}{stop:7.1f}{t1:6.1f}")
    rest = s[~s["cell"].isin([LL, WL, IL])]
    print(f"  {'all other cells':24}{len(IS[~IS['cell'].isin([LL,WL,IL])]):6d}{len(OOS[~OOS['cell'].isin([LL,WL,IL])]):7d}"
          f"{IS[~IS['cell'].isin([LL,WL,IL])]['R'].mean():+8.3f}{OOS[~OOS['cell'].isin([LL,WL,IL])]['R'].mean():+8.3f}"
          f"{rest['R'].median():+8.3f}{rest['Alpha_Matched_pct'].mean():+8.2f}")
    nLL = (len(IS[IS["cell"] == LL]), len(OOS[OOS["cell"] == LL]))
    nIL = (len(IS[IS["cell"] == IL]), len(OOS[OOS["cell"] == IL]))
    dIS = IS.loc[IS["cell"] == LL, "R"].mean() - IS.loc[IS["cell"] == IL, "R"].mean()
    dOOS = OOS.loc[OOS["cell"] == LL, "R"].mean() - OOS.loc[OOS["cell"] == IL, "R"].mean()
    dmed = s.loc[s["cell"] == LL, "R"].median() - s.loc[s["cell"] == IL, "R"].median()
    ci = boot_diff(s[s["cell"] == LL], s[s["cell"] == IL], rng) if min(nLL[0]+nLL[1], nIL[0]+nIL[1]) else (np.nan, np.nan)
    thin = min(*nLL, *nIL) < MIN_N
    passed = (not thin and dIS >= BAR_R and dOOS >= BAR_R and dmed >= 0 and ci[0] > 0)
    backwards = (not thin and dIS <= -BAR_R and dOOS <= -BAR_R and ci[1] < 0)
    verdict = "THIN" if thin else ("PASS" if passed else ("BACKWARDS" if backwards else "FAIL"))
    print(f"\n  L->L minus I->L:  IS {dIS:+.3f}R  OOS {dOOS:+.3f}R  median {dmed:+.3f}R  CI95 [{ci[0]:+.3f}, {ci[1]:+.3f}]"
          f"  n L->L {nLL}  n I->L {nIL}\n  → {verdict}")
    return verdict, dict(dIS=dIS, dOOS=dOOS, dmed=dmed, ci=list(map(float, ci)), nLL=nLL, nIL=nIL)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    for f in ("coverage", "check", "placebo", "run"):
        g.add_argument("--" + f, action="store_true")
    a = ap.parse_args()
    rng = np.random.default_rng(41)
    if a.coverage:
        d, _, _ = build_labels()
        n = len(d)
        print(d["src"].value_counts(dropna=False).to_string())
        print(f"filled trades {n} · labelled {d['cell'].notna().sum()} ({d['cell'].notna().mean()*100:.1f}%) · "
              f"Stage 2 {int((d['stage2'] == True).sum())}")                       # noqa: E712
        s = d[d["stage2"] == True]                                                    # noqa: E712
        print(s["cell"].value_counts().to_string())
        return
    d = load_labels()
    if a.check:
        import bull_screener as bs
        bench, bench_yf = _daily(BENCH), _yf(BENCH)
        smp = d[d["cell"].notna()].sample(20, random_state=3)
        bad = 0
        for r in smp.itertuples(index=False):
            out = (label_at(_daily(r.Symbol), bench, pd.Timestamp(r.go)) if r.src == "dhan"
                   else label_at(_yf(r.Symbol), bench_yf, pd.Timestamp(r.go)))
            rrg = out[2]
            cur = r.cell.split(" -> ")[0]
            _traj, nxt, *_ = bs._rrg_trajectory(rrg["RS_Ratio"], rrg["RS_Momentum"], cur, TRAIL)
            live = f"{cur} -> {nxt}"
            if live != r.cell:
                bad += 1
                print("  MISMATCH", r.Symbol, str(r.go)[:10], r.cell, "vs live", live)
        print(f"label check: {20 - bad}/20 match bull_screener._rrg_trajectory")
        return
    if a.placebo:
        p = d.copy()
        p["mo"] = p["go"].dt.to_period("M")
        p["cell"] = p.groupby("mo")["cell"].transform(lambda x: x.sample(frac=1, random_state=5).values)
        report(p, "PLACEBO (cells shuffled within GO month)", rng)
        return
    if os.path.exists(MARKER):
        sys.exit(f"REFUSED: already run ({MARKER}).")
    v, res = report(d, "REAL RUN", rng)
    report(d[d["src"] == "dhan"], "REAL RUN · Dhan-labelled subset (reported only)", rng)
    json.dump({"at": datetime.now().isoformat(), "run": RUN_ID, "verdict": v, **res}, open(MARKER, "w"))
    print("\nmarker written.")


if __name__ == "__main__":
    main()
