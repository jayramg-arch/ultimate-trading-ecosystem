"""entry_rebaseline.py - Step B of the entry-optimizer work (2-Oct-2026, Jay).

The Golden Rules line "the GO gate is a trade CLASSIFIER, not an entry optimizer" rests on
the 23-Jul A/B, which compared GO-timed entries with a buy@close baseline that had two
defects since fixed or recognised: (1) the baseline's benchmark ran the full 120-180d
design window against trades that exited in weeks (fixed 26-Jul; +2.56% -> ~+0.5-0.8%);
(2) everything was scored in % per trade, which hides what an entry changes most - R.
The baseline also used the screener's ATR stop while GO used a structural stop, so the
two differed in stop as well as entry.

This re-runs the comparison like-for-like:
  E0_close   buy at the anchor-day close (the naive entry), STRUCTURAL stop at that bar
  E3_buystop GO, then buy-stop above the GO bar's high   (the 23-Jul control)
  E2_retest  GO, then buy-limit at the GO bar's close    (the live S4 default)
Same candidates (the cached 23-Jul catalyst qualification), same stop function, same
2R/3R targets and 33/33 partials, same 4.5x trail, same costs, benchmark over each
trade's ACTUAL hold. Scored in R = realised % / initial risk %.

Reported: all-name means; the PAIRED comparison on names a GO variant filled (GO R vs
E0 R on the very same names - the entry effect alone); and the E0 R of names the GO
variant skipped (what the gate gave up). Per family, early vs late anchors (60/40),
symbol-block bootstrap on the paired difference. DAILY bars only - the intraday replay
(step A) is separate. Run once; nothing here changes the live system.

    python entry_rebaseline.py            (venv; ~20-40 min, cached data)
"""
import json
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "validation_runs")
CACHE = os.path.join(RUNS, "_ab_qual_cache")
OUT = os.path.join(RUNS, "entry_rebaseline")
CATALYST_RUN = "20260723_063652"

import data_provider as _dp          # noqa: E402
import replay as _rp                  # noqa: E402


def fam(fw) -> str:
    try:
        fw = int(float(fw))
    except Exception:
        return "NA"
    return "POS" if fw >= 120 else ("REV" if fw >= 90 else "SWG")


def _bench() -> pd.DataFrame:
    b = _dp.fetch_ohlcv(_rp.BENCHMARK_YF, period="3y", interval="1d")
    if b is None or b.empty:
        return pd.DataFrame()
    b = b.copy()
    if getattr(b.index, "tz", None) is not None:
        b.index = b.index.tz_localize(None)
    return b


def _bench_matched(bench, entry_iso, days_held):
    try:
        eb = bench.index.searchsorted(pd.Timestamp(entry_iso), side="right") - 1
        xb = min(eb + days_held, len(bench) - 1)
        if eb >= 0 and xb > eb:
            b0, b1 = float(bench["Close"].iloc[eb]), float(bench["Close"].iloc[xb])
            return round(100.0 * (b1 - b0) / b0, 2) if b0 > 0 else None
    except Exception:
        pass
    return None


def e0_trade(sym, as_of, cand, bench) -> dict:
    """Buy at the anchor close, with the same structural stop / targets / exits as GO."""
    base = {"Symbol": sym, "Status": "no data"}
    df = _dp.fetch_ohlcv(sym, period="3y", interval="1d")
    if df is None or df.empty or len(df) < 220:
        return base
    df = df.copy()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    pos = df.index.searchsorted(pd.Timestamp(as_of), side="right") - 1
    if pos < 0 or pos >= len(df) - 2:
        base["Status"] = "no entry bar"
        return base
    det = _rp._pafv.compute_pa_detectors(df)
    px = float(df["Close"].iloc[pos])
    loc = _rp._location_at(df.iloc[:pos + 1], px)
    fwd = _rp._go_forward_days(cand, det, pos)
    sl = _rp._structural_sl(df, pos, px, loc)
    r = px - sl
    res = _rp._simulate_one_trade(df, pos, px, sl, px + 2 * r, px + 3 * r, t1_qty_pct=33, t2_qty_pct=33,
                                  max_bars=fwd, trail_atr_mult=4.5, cost_pct=_rp.COST_PER_LEG_DEFAULT)
    entry_iso = df.index[pos].strftime("%Y-%m-%d")
    bm = _bench_matched(bench, entry_iso, res["days_held"])
    return {"Symbol": sym, "Entry_Date": entry_iso, "forward_days_used": fwd, "Entry_Price": round(px, 2),
            "SL_price": round(sl, 2), "SL_pct": round((px - sl) / px * 100, 2),
            "Return_pct": res["realized_pct"], "Benchmark_Matched_pct": bm,
            "Alpha_Matched_pct": (round(res["realized_pct"] - bm, 2) if res["realized_pct"] is not None and bm is not None else None),
            "Exit_Reason": res["exit_reason"], "Days_Held": res["days_held"],
            "Hit_Initial_SL": res.get("hit_initial_sl", False),
            "Status": "OK" if res["realized_pct"] is not None else "no result"}


def run_variant(name, anchors, per_anchor, bench) -> pd.DataFrame:
    rows = []
    t0 = time.time()
    for a in anchors:
        c = per_anchor.get(a)
        if c is None or c.empty:
            continue
        for meta in c.to_dict("records"):
            sym = str(meta.get("Symbol"))
            try:
                if name == "E0_close":
                    row = e0_trade(sym, a, meta, bench)
                else:
                    mode = "retest" if name == "E2_retest" else "buystop"
                    row = _rp.s4go_forward_trade(sym, a, candidate=meta, mode="bull", entry_window=40,
                                                 rv_floor=1.0, entry_mode=mode, df_bench=bench)
            except Exception as e:
                row = {"Symbol": sym, "Status": "err: %s" % str(e)[:80]}
            row["as_of"] = a
            row["Catalyst"] = meta.get("Catalyst")
            rows.append(row)
    df = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    df.to_csv(os.path.join(OUT, "%s.csv" % name), index=False)
    print("  %-11s %4d rows, %d OK, %.0fs" % (name, len(df), (df["Status"] == "OK").sum(), time.time() - t0), flush=True)
    return df


def add_r(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    ok = df["Status"].astype(str) == "OK"
    ret = pd.to_numeric(df["Return_pct"], errors="coerce")
    risk = pd.to_numeric(df["SL_pct"], errors="coerce")
    df["R"] = np.where(ok & (risk > 0), ret / risk, np.nan)
    df["fam"] = df["forward_days_used"].map(fam) if "forward_days_used" in df else "NA"
    return df


def boot_paired(d: pd.DataFrame, n=5000, seed=7):
    """Symbol-block bootstrap of mean(GO R - E0 R) on paired rows."""
    if d.empty:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    syms = d["Symbol"].unique()
    g = {s: d.loc[d["Symbol"] == s, "diff"].values for s in syms}
    means = []
    for _ in range(n):
        pick = rng.choice(syms, size=len(syms), replace=True)
        v = np.concatenate([g[s] for s in pick])
        means.append(v.mean())
    lo, hi = np.percentile(means, [2.5, 97.5])
    return (lo, hi, float((np.array(means) > 0).mean()))


def report(res: dict, anchors: list) -> str:
    L = []
    cut = anchors[int(len(anchors) * 0.6)]
    e0 = add_r(res["E0_close"])
    L.append("ENTRY RE-BASELINE (daily bars, catalyst set of %s, %d anchors, OOS from %s)" % (CATALYST_RUN, len(anchors), cut))
    L.append("R = realised %% / initial risk %%; benchmark over each trade's actual hold\n")
    L.append("%-11s %5s %6s %7s %7s %6s %7s %6s" % ("variant", "fills", "fill%", "meanR", "medR", "win%", "stop%", "meanA%"))
    nall = len(e0)
    for name in ("E0_close", "E3_buystop", "E2_retest"):
        d = add_r(res[name]); ok = d[d["R"].notna()]
        a = pd.to_numeric(ok["Alpha_Matched_pct"], errors="coerce")
        L.append("%-11s %5d %5.0f%% %+7.3f %+7.3f %5.1f%% %6.1f%% %+6.2f" % (
            name, len(ok), 100 * len(ok) / max(nall, 1), ok["R"].mean(), ok["R"].median(),
            100 * (ok["R"] > 0).mean(), 100 * ok["Hit_Initial_SL"].astype(bool).mean(), a.mean()))
    for name in ("E3_buystop", "E2_retest"):
        g = add_r(res[name])
        key = ["as_of", "Symbol"]
        m = g[g["R"].notna()][key + ["R", "fam"]].merge(e0[e0["R"].notna()][key + ["R"]], on=key, suffixes=("_go", "_e0"))
        m["diff"] = m["R_go"] - m["R_e0"]
        L.append("\n=== %s vs E0 on the SAME names (entry effect) ===" % name)
        for lab, sub in (("ALL", m), ("IS", m[m["as_of"] < cut]), ("OOS", m[m["as_of"] >= cut])):
            lo, hi, pp = boot_paired(sub)
            L.append("  %-4s n=%4d  GO %+.3fR  E0 %+.3fR  diff %+.3fR  med diff %+.3fR  CI95 [%+.3f, %+.3f]  P(>0) %.0f%%" % (
                lab, len(sub), sub["R_go"].mean(), sub["R_e0"].mean(), sub["diff"].mean(), sub["diff"].median(), lo, hi, 100 * pp))
        for f, sub in m.groupby("fam"):
            L.append("     %-4s n=%4d  GO %+.3fR  E0 %+.3fR  diff %+.3fR" % (f, len(sub), sub["R_go"].mean(), sub["R_e0"].mean(), sub["diff"].mean()))
        skipped = e0[e0["R"].notna()].merge(g[g["R"].notna()][key], on=key, how="left", indicator=True)
        skipped = skipped[skipped["_merge"] == "left_only"]
        L.append("  names %s did NOT fill: n=%d, their E0 R mean %+.3f / median %+.3f  (what the gate gave up)" % (
            name, len(skipped), skipped["R"].mean(), skipped["R"].median()))
    return "\n".join(L)


def main() -> int:
    meta = json.load(open(os.path.join(RUNS, "validation_%s_meta.json" % CATALYST_RUN)))
    anchors = sorted(meta["anchors"])
    per_anchor = {}
    for a in anchors:
        p = os.path.join(CACHE, "qual_%s.pkl" % a)
        per_anchor[a] = pickle.load(open(p, "rb")) if os.path.exists(p) else pd.DataFrame()
    print("entry re-baseline: %d anchors, %d qualified rows" % (len(anchors), sum(len(c) for c in per_anchor.values())), flush=True)
    bench = _bench()
    res = {n: run_variant(n, anchors, per_anchor, bench) for n in ("E0_close", "E3_buystop", "E2_retest")}
    txt = report(res, anchors)
    open(os.path.join(OUT, "report.txt"), "w", encoding="utf-8").write(txt)
    print("\n" + txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
