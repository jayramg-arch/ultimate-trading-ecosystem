"""Standalone universe-wide RRG bucketing test.

Bypasses bull_screener entirely. For each of 12 monthly anchors, computes
JdK RS-Ratio / RS-Momentum / RRG_Quadrant / RRG_Score for EVERY symbol in
the Nifty 500 universe, then looks up the 30-day forward return.

Goal: definitively test whether RRG_Score predicts forward alpha in isolation
from the bull_screener's catalyst / stage / score filters.

Output: validation_runs/rrg_universe_bucketing_<ts>.csv with all
(anchor, symbol, RRG_Quadrant, RRG_Score, forward_return, bench_return, alpha) rows.
"""
from __future__ import annotations
import os, sys, time
from datetime import datetime
import numpy as np
import pandas as pd

# Reuse the screener's compute path so we test the EXACT formula in production
import data_provider as _dp
import bull_screener as bs
import validation as v
import replay

BENCH = "^CRSLDX"
FORWARD_DAYS = 30


def compute_rrg(df_w: pd.DataFrame, df_bench_w: pd.DataFrame) -> dict | None:
    """Call screener's compute_weekly_indicators on weekly slices."""
    if df_w is None or df_w.empty or df_bench_w is None or df_bench_w.empty:
        return None
    if len(df_w) < 35:
        return None
    try:
        return bs.compute_weekly_indicators(df_w, df_bench_w)
    except Exception as e:
        print(f"  compute err: {e}", flush=True)
        return None


def main():
    anchors = v.monthly_anchors(months_back=12,
                                  end_offset_days=max(FORWARD_DAYS + 5, 35))
    print(f"Anchors: {anchors}")
    universe = v.default_universe("nifty500")
    print(f"Universe: {len(universe)} symbols")

    # Pre-fetch full benchmark weekly + daily once
    df_bench_w_full = bs._flatten_cols(_dp.fetch_ohlcv(BENCH, period="3y", interval="1wk"))
    df_bench_d_full = bs._flatten_cols(_dp.fetch_ohlcv(BENCH, period="3y", interval="1d"))
    # Tail-extend bench weekly (same fix as bull_screener v1.5)
    if not df_bench_d_full.empty:
        res = df_bench_d_full.resample("W-MON", closed="left", label="left").agg(
            {"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}
        ).dropna(subset=["Close"])
        if not res.empty and not df_bench_w_full.empty:
            extra = res[res.index > df_bench_w_full.index[-1]]
            if not extra.empty:
                df_bench_w_full = pd.concat([df_bench_w_full, extra])

    print(f"Bench weekly bars: {len(df_bench_w_full)}, last={df_bench_w_full.index[-1].date()}")
    print(f"Bench daily bars:  {len(df_bench_d_full)}, last={df_bench_d_full.index[-1].date()}")

    rows = []
    t0 = time.time()
    for ai, anchor in enumerate(anchors, 1):
        print(f"\n[{ai:2d}/{len(anchors)}] anchor={anchor}", flush=True)
        anchor_ts = pd.Timestamp(anchor)

        # Slice benchmark up to anchor for RRG calc
        df_bench_w_anchor = df_bench_w_full.loc[:anchor_ts]
        if len(df_bench_w_anchor) < 52:
            print(f"  bench too short ({len(df_bench_w_anchor)}) — skip", flush=True)
            continue

        # Compute benchmark forward return
        try:
            entry_b = df_bench_d_full.loc[:anchor_ts]["Close"].iloc[-1]
            fwd_iso = replay._add_trading_days(anchor, FORWARD_DAYS, df_bench_d_full)
            exit_b = df_bench_d_full.loc[:pd.Timestamp(fwd_iso)]["Close"].iloc[-1] if fwd_iso else None
        except Exception:
            entry_b = exit_b = None
        if entry_b is None or exit_b is None:
            print(f"  no bench fwd return — skip", flush=True)
            continue
        bench_ret_pct = (exit_b - entry_b) / entry_b * 100

        sym_count = 0
        rrg_count = 0
        for si, sym in enumerate(universe):
            yf_sym = bs.to_yf(sym)
            try:
                df_w = bs._flatten_cols(_dp.fetch_ohlcv(yf_sym, period="3y", interval="1wk"))
                df_d = bs._flatten_cols(_dp.fetch_ohlcv(yf_sym, period="2y", interval="1d"))
            except Exception:
                continue
            if df_w is None or df_w.empty or df_d is None or df_d.empty:
                continue
            sym_count += 1
            df_w_anchor = df_w.loc[:anchor_ts]
            if len(df_w_anchor) < 52:
                continue
            rrg = compute_rrg(df_w_anchor, df_bench_w_anchor)
            if rrg is None or rrg.get("rrg_quadrant") == "n/a":
                continue
            try:
                entry = df_d.loc[:anchor_ts]["Close"].iloc[-1]
                exit_ = df_d.loc[:pd.Timestamp(fwd_iso)]["Close"].iloc[-1] if fwd_iso else None
            except Exception:
                continue
            if entry is None or exit_ is None:
                continue
            ret_pct = (exit_ - entry) / entry * 100
            rows.append({
                "as_of": anchor,
                "Symbol": sym,
                "Entry_Close": round(entry, 2),
                "Forward_Close": round(exit_, 2),
                "Return_pct": round(ret_pct, 2),
                "Benchmark_pct": round(bench_ret_pct, 2),
                "Alpha_pct": round(ret_pct - bench_ret_pct, 2),
                "RRG_Quadrant": rrg["rrg_quadrant"],
                "RRG_Next": rrg.get("rrg_next", "n/a"),
                "RRG_Trajectory": rrg.get("rrg_trajectory", "n/a"),
                "RRG_Score": rrg.get("rrg_score", 0),
                "RS_Ratio": round(rrg.get("mansfield", 0) + 100, 2),
                "RS_Momentum": round(rrg.get("mansfield_4w", 0) + 100, 2),
                "Stage": rrg.get("stage", 0),
            })
            rrg_count += 1
        dt = time.time() - t0
        print(f"  done: {sym_count} symbols with data, {rrg_count} with valid RRG; cumulative {dt:.0f}s", flush=True)

    df = pd.DataFrame(rows)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = f"validation_runs/rrg_universe_bucketing_{ts}.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved {len(df)} rows to {out}")

    if not df.empty:
        print()
        print("=== Per-Quadrant ===")
        print(df.groupby("RRG_Quadrant").agg(
            n=("Alpha_pct","size"),
            mean_alpha=("Alpha_pct","mean"),
            median_alpha=("Alpha_pct","median"),
            win_rate=("Return_pct", lambda s: (s>0).mean()*100),
        ).round(2).sort_values("mean_alpha", ascending=False))
        print()
        print("=== Per RRG_Score ===")
        print(df.groupby("RRG_Score").agg(
            n=("Alpha_pct","size"),
            mean_alpha=("Alpha_pct","mean"),
            median_alpha=("Alpha_pct","median"),
            win_rate=("Return_pct", lambda s: (s>0).mean()*100),
        ).round(2).sort_index(ascending=False))
        print()
        print("=== Per (Current -> Next) ===")
        print(df.groupby(["RRG_Quadrant", "RRG_Next"]).agg(
            n=("Alpha_pct","size"),
            score=("RRG_Score","first"),
            mean_alpha=("Alpha_pct","mean"),
            win_rate=("Return_pct", lambda s: (s>0).mean()*100),
        ).round(2).sort_values("mean_alpha", ascending=False))
        print()
        corr = df[["RRG_Score","Alpha_pct"]].corr().iloc[0,1]
        print(f"Correlation(RRG_Score, Alpha_pct) = {corr:.4f}  (n={len(df)})")


if __name__ == "__main__":
    sys.exit(main() or 0)
