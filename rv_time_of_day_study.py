"""Is S4's relative-volume gate biased by TIME OF DAY?

THE CLAIM UNDER TEST (mine, asserted on 20-Aug and never measured):

    S4 computes `chart_rv = volume / sma(volume, 50)[1]` — a rolling 50-bar mean that
    MIXES every bar of the day. NSE intraday volume is U-shaped, heaviest at the open and
    thinnest late morning. If so, the same baseline is too LOW for the opening bar and too
    HIGH for the midday bars, so the V gate is structurally easy at 10:30 and structurally
    hard at 11:45 — regardless of whether anything real is happening.

WHAT THIS MEASURES: the shape of that bias, and the V-gate PASS RATE by bar-of-day, which
is the number that actually matters for how alerts distribute across the session.

WHAT IT DOES NOT MEASURE: whether 10:30 triggers make or lose money. That needs an
intraday backtest, which does not exist — the s4go replay is daily-bar
(`interval="1d"`, GO_Date carries no time). Do not read a pass-rate skew as an edge claim.

Read-only. Fetches nothing it does not already cache.

    python rv_time_of_day_study.py [--symbols 60] [--days 90]
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dhan_ohlcv as _dh            # noqa: E402
import pa_patterns as pap           # noqa: E402

RV_LEN = 50                          # S4: vol_sma_50
GATE = 1.0                           # S4: rv_floor
PB_GATE = 0.5                        # S4: pb_rv_floor (pullback context)


def universe(n: int) -> list:
    """The board's own names first — this is about HIS alerts, not a generic sample."""
    syms = []
    for f in ("FINAL_GOLDEN_MATCHER.csv", "FINAL_CATALYST_WATCHLIST.csv"):
        if os.path.exists(f):
            try:
                s = pd.read_csv(f)["Symbol"].dropna().astype(str)
                syms += [x.replace(".NS", "").strip().upper() for x in s]
            except Exception:
                pass
    seen, out = set(), []
    for s in syms:
        if s not in seen:
            seen.add(s); out.append(s)
    return out[:n]


def rv_by_bar(sym: str, minutes: int, days: int):
    """RV per bar, exactly S4's formula, tagged with the bar's CLOSE time."""
    try:
        # SAME PATH AS THE BOARD: gm_load_intraday goes straight to dhan_ohlcv, not
        # through data_provider — `fetch_ohlcv(period="90d", interval="25m")` returns
        # nothing, which is why the first run of this study found no data at all.
        from datetime import date, timedelta
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
        # S4 uses the PRIOR bar's mean so a 5x bar cannot inflate its own baseline
        base_mean = v.rolling(RV_LEN).mean().shift(1)
        rv = (v / base_mean).replace([np.inf, -np.inf], np.nan)
        out = pd.DataFrame({"rv": rv, "vol": v})
        # resample_intraday labels a bar by its OPEN. The alert fires at the CLOSE, so
        # label by close or the whole table reads one slot early — the 09:15 label IS the
        # bar that closes 10:30. Getting this backwards would have inverted the finding.
        out["slot"] = (df.index + pd.Timedelta(minutes=minutes)).strftime("%H:%M")
        out["symbol"] = sym
        # Dhan publishes a phantom 15:30 stub (O=H=L=C, volume 0) that resamples into a
        # 6th bar; it is not a session bar and its RV is 0 by construction.
        out = out[out["vol"] > 0]
        return out.dropna(subset=["rv"])
    except Exception:
        return None


def report(rows: pd.DataFrame, minutes: int):
    if rows.empty:
        print(f"  no data for {minutes}m"); return
    n_sym = rows.symbol.nunique()
    print(f"\n{'='*78}\n{minutes}-MINUTE BARS — {n_sym} symbols, {len(rows):,} bar-observations\n{'='*78}")
    # share of each session's volume, and the RV the S4 formula actually produces
    g = rows.groupby("slot")
    tot_by_slot = g["vol"].median()
    share = tot_by_slot / tot_by_slot.sum() * 100
    print(f"{'close':>7}{'med RV':>9}{'mean RV':>9}{'vol share':>11}"
          f"{'V pass ≥1.0':>13}{'pass ≥0.5':>11}{'n':>8}")
    print("-" * 78)
    for slot in sorted(g.groups):
        s = rows[rows.slot == slot]
        print(f"{slot:>7}{s.rv.median():>9.2f}{s.rv.mean():>9.2f}{share[slot]:>10.1f}%"
              f"{(s.rv >= GATE).mean()*100:>12.1f}%{(s.rv >= PB_GATE).mean()*100:>10.1f}%"
              f"{len(s):>8,}")
    med = rows.groupby("slot").rv.median()
    print("-" * 78)
    print(f"  If the baseline were unbiased every median would sit near 1.00.")
    print(f"  Spread across the session: {med.min():.2f} (at {med.idxmin()}) "
          f"to {med.max():.2f} (at {med.idxmax()})  =  {med.max()/max(med.min(),1e-9):.2f}x")
    return med


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=60)
    ap.add_argument("--days", type=int, default=90)
    a = ap.parse_args()

    syms = universe(a.symbols)
    print(f"universe: {len(syms)} board names · {a.days} days · RV = volume / sma(volume,{RV_LEN})[1]")

    for minutes in (75, 125):
        frames, ok = [], 0
        for s in syms:
            r = rv_by_bar(s, minutes, a.days)
            if r is not None and not r.empty:
                frames.append(r); ok += 1
        if not frames:
            print(f"\n{minutes}m: no usable data"); continue
        rows = pd.concat(frames, ignore_index=True)
        med = report(rows, minutes)
        if med is not None:
            rows.to_csv(f"validation_runs/rv_time_of_day_{minutes}m.csv", index=False)

    print("\nNOTE: this measures the GATE's behaviour, not trade outcomes. Whether a 10:30")
    print("trigger performs worse than an 11:45 one is a different question and needs an")
    print("intraday backtest, which does not exist — the s4go replay is daily-bar.")


if __name__ == "__main__":
    main()
