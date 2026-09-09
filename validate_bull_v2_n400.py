"""Backtest Bull v2 Minervini on Nifty 400 (mid + small caps).
Runs both BULL window (Dec 2023 - Nov 2024) and CHOP window (May 2025 - Apr 2026)
to see if Minervini SEPA fits the smaller-cap segment where it was designed for."""
from __future__ import annotations
import os, sys, time, json
from datetime import datetime
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validation as _v
import replay as _r
import data_provider as _dp
import bull_screener_v2 as _bv2

FORWARD_DAYS = 30
BULL_ANCHORS = [f"{y}-{m:02d}-15" for y, m in [
    (2023,12),(2024,1),(2024,2),(2024,3),(2024,4),(2024,5),
    (2024,6),(2024,7),(2024,8),(2024,9),(2024,10),(2024,11)]]
CHOP_ANCHORS = [f"{y}-{m:02d}-15" for y, m in [
    (2025,5),(2025,6),(2025,7),(2025,8),(2025,9),(2025,10),
    (2025,11),(2025,12),(2026,1),(2026,2),(2026,3),(2026,4)]]


def run_window(label, anchors, universe):
    print(f"\n{'='*60}\n  {label}\n{'='*60}")
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary, details = [], []
    t0 = time.time()
    for i, anchor in enumerate(anchors, 1):
        print(f"[{i:2d}/{len(anchors)}] {anchor}", flush=True)
        _dp.set_pinned_date(anchor)
        try:
            picks = _bv2.run_bull_screener(symbols=universe,
                                              out_file=f"validation_runs/bv2_n400_{label}_{anchor}.csv",
                                              strict=True)
        finally:
            _dp.set_pinned_date(None)
        bench = _r._benchmark_forward_pct(anchor, FORWARD_DAYS)
        if picks is None or picks.empty:
            summary.append({"as_of": anchor, "picks": 0, "benchmark_pct": bench})
            continue
        perf = _r.forward_returns(picks["Symbol"].astype(str).tolist(),
                                     as_of=anchor, forward_days=FORWARD_DAYS)
        s = _r._summarize(perf, bench)
        summary.append({
            "as_of": anchor, "picks": int(len(picks)),
            "win_rate_pct": s.get("win_rate_pct"),
            "avg_return_pct": s.get("avg_return_pct"),
            "benchmark_pct": bench,
            "alpha_pct": s.get("alpha_vs_bench"),
        })
        if not perf.empty:
            c = picks.merge(perf, on="Symbol", how="left")
            c.insert(0, "as_of", anchor)
            details.append(c)
    sm = pd.DataFrame(summary)
    sm.to_csv(f"validation_runs/n400_{label}_summary_{run_id}.csv", index=False)
    if details:
        pd.concat(details, ignore_index=True).to_csv(
            f"validation_runs/n400_{label}_details_{run_id}.csv", index=False)
    valid = sm[sm.get("alpha_pct", pd.Series()).notna()] if "alpha_pct" in sm.columns else pd.DataFrame()
    n_picks = sum(r.get("picks", 0) for r in summary)
    if not valid.empty:
        cum_s = (1 + valid["avg_return_pct"]/100).prod() - 1
        cum_b = (1 + valid["benchmark_pct"]/100).prod() - 1
        cum_a = (1+cum_s)/(1+cum_b) - 1
        print(f"  Picks: {n_picks}")
        print(f"  Anchors with picks: {(sm['picks']>0).sum()}/{len(sm)}")
        print(f"  Avg anchor alpha: {valid['alpha_pct'].mean():.2f}%")
        print(f"  Cumulative strategy: {cum_s*100:+.2f}%  bench: {cum_b*100:+.2f}%  ALPHA: {cum_a*100:+.2f}%")
    else:
        print(f"  Picks: {n_picks}, no alpha data")
    return {"label": label, "picks": n_picks,
              "cum_alpha": (1+cum_s)/(1+cum_b)-1 if not valid.empty else 0,
              "duration_s": time.time()-t0}


def main():
    n400 = json.load(open("nifty400_symbols.json"))
    print(f"Nifty 400 universe: {len(n400)} symbols")
    res_bull = run_window("BULL_WINDOW", BULL_ANCHORS, n400)
    res_chop = run_window("CHOP_WINDOW", CHOP_ANCHORS, n400)
    print(f"\n{'='*60}\nMINERVINI v2 on NIFTY 400 — SUMMARY\n{'='*60}")
    for r in (res_bull, res_chop):
        print(f"  {r['label']:14s}  picks={r['picks']:4d}  cum_alpha={r['cum_alpha']*100:+7.2f}%  ({r['duration_s']:.0f}s)")


if __name__ == "__main__":
    main()
