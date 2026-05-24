"""
verify_bull_engulf_tightening.py — multi-variant BULL_ENGULF tightening test.

Tests several filter additions:
  B1: meaningful prior decline (close[1] < 0.93 * high(10)[1])  [REJECTED]
  B2: stronger volume (relvol > 2.0 instead of 1.2)
  B3: deeper trend weakness (ema10 < ema20 < ema50)
  B4: oversold (RSI(14) < 40 at prior bar)
  B5: B2+B3 combined
"""
from __future__ import annotations
import warnings, json, time
import numpy as np, pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
import data_provider as dp
from pa_field_validator import compute_pa_detectors


def _rsi_fn(close: pd.Series, length: int = 14) -> pd.Series:
    """Wilder RSI."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1.0 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

BENCHMARK = "^CRSLDX"
HORIZON = 20


def process(symbol, period, bench, bench_sma200):
    raw = dp.fetch_ohlcv(symbol, period=period, interval="1d")
    if raw is None or raw.empty or len(raw) < 252:
        return []
    df = compute_pa_detectors(raw)
    if "pa_bull_engulf" not in df.columns:
        return []
    close = df["Close"] if "Close" in df.columns else df["close"]

    # Pre-compute all variant gates
    high_10_prev = close.rolling(10).max().shift(1)
    high_pullback = close.shift(1) < (high_10_prev * 0.93)  # B1

    # Need to re-derive vol since cur_rel_vol may not be in df
    vol = raw["Volume"]
    vavg = vol.rolling(50).mean()
    relvol = vol / vavg
    high_vol = relvol > 2.0  # B2

    ema10 = close.ewm(span=10, adjust=False).mean()
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    deeper_trend = (close < ema10) & (ema10 < ema20) & (ema20 < ema50)  # B3

    rsi14 = _rsi_fn(close, 14)
    oversold = rsi14.shift(1) < 40  # B4 — yesterday was oversold

    bench_close = bench["Close"]
    fired = df[df["pa_bull_engulf"].fillna(False).astype(bool)]
    records = []
    for entry_date in fired.index:
        try:
            ei = df.index.get_loc(entry_date)
            if ei + HORIZON >= len(df):
                continue
            ep = float(close.iloc[ei])
            xp = float(close.iloc[ei + HORIZON])
            if ep <= 0 or pd.isna(ep) or pd.isna(xp):
                continue
            be = bench_close.asof(entry_date)
            bx = bench_close.asof(df.index[ei + HORIZON])
            if pd.isna(be) or pd.isna(bx) or be <= 0:
                continue
            stock_ret = (xp - ep) / ep * 100
            bench_ret = (bx - be) / be * 100
            alpha = stock_ret - bench_ret
            bsma = bench_sma200.asof(entry_date)
            regime = "bull" if (not pd.isna(bsma) and be > bsma) else (
                "bear" if not pd.isna(bsma) else "unknown")
            records.append({
                "alpha": alpha,
                "regime": regime,
                "b1_pullback": bool(high_pullback.iloc[ei]),
                "b2_vol2x": bool(high_vol.iloc[ei]),
                "b3_deeper_trend": bool(deeper_trend.iloc[ei]),
                "b4_oversold": bool(oversold.iloc[ei]) if not pd.isna(oversold.iloc[ei]) else False,
            })
        except Exception:
            continue
    return records


def summarize(label, df_subset):
    if len(df_subset) < 5:
        print(f"  {label:25s}: n={len(df_subset):4d} (too few)")
        return
    for regime in ["bull", "bear"]:
        g = df_subset[df_subset["regime"] == regime]
        if len(g) < 5:
            print(f"  {label:25s} | {regime:4s}: n={len(g):4d} (too few)")
            continue
        a = g["alpha"].values
        rng = np.random.default_rng(42)
        means = np.array([rng.choice(a, size=len(a), replace=True).mean() for _ in range(1500)])
        lo, hi = np.percentile(means, [2.5, 97.5])
        prob_pos = (means > 0).mean() * 100
        wr = (a > 0).mean() * 100
        print(f"  {label:25s} | {regime:4s}: n={len(g):4d}  α={a.mean():+.2f}%  "
              f"CI95=({lo:+.2f}, {hi:+.2f})  P(α>0)={prob_pos:3.0f}%  WR={wr:.1f}%")


def main():
    syms = [s.replace(".NS", "") for s in json.load(open("nifty500_symbols.json"))]
    period = "5y"
    print(f"[verify] Fetching benchmark {BENCHMARK} ({period})...")
    bench = dp.fetch_ohlcv(BENCHMARK, period=period, interval="1d")
    bench_sma200 = bench["Close"].rolling(200).mean()

    all_recs = []
    t0 = time.time()
    for i, s in enumerate(syms, 1):
        all_recs.extend(process(s, period, bench, bench_sma200))
        if i % 125 == 0 or i == len(syms):
            print(f"[verify] {i}/{len(syms)}, {len(all_recs):,} firings, {(time.time()-t0)/60:.1f}m")

    df = pd.DataFrame(all_recs)
    print(f"\nTotal: {len(df):,} BULL_ENGULF firings\n")

    print("=== BASELINE (all firings) ===")
    summarize("BASELINE", df)
    print()
    print("=== B1: meaningful prior decline (REJECTED) ===")
    summarize("B1 pullback", df[df["b1_pullback"]])
    print()
    print("=== B2: relvol > 2.0 (institutional vol) ===")
    summarize("B2 vol2x", df[df["b2_vol2x"]])
    print()
    print("=== B3: deeper trend weakness (close<ema10<ema20<ema50) ===")
    summarize("B3 deeper_trend", df[df["b3_deeper_trend"]])
    print()
    print("=== B4: oversold at prior bar (RSI(14)<40) ===")
    summarize("B4 oversold", df[df["b4_oversold"]])
    print()
    print("=== B5: B2 AND B3 combined ===")
    summarize("B5 vol2x+deeper", df[df["b2_vol2x"] & df["b3_deeper_trend"]])
    print()
    print("=== B6: B2 AND B4 combined ===")
    summarize("B6 vol2x+oversold", df[df["b2_vol2x"] & df["b4_oversold"]])


if __name__ == "__main__":
    main()
