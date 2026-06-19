"""
etf_screener.py — Phase-1 ETF Screener for NSE ETFs.

Built 11 May 2026 as Phase 1 of the ETF Trading System.

Why a separate screener (not just bull_screener with ETF symbols)
-----------------------------------------------------------------
Stock screeners filter on fundamentals (RFF, conviction, EPS growth). ETFs
have *no* fundamentals. The alpha sources are different:

    • Liquidity (turnover, AUM proxied via ADV × price, spread)
    • Trend quality (Stage 2 + 30W MA + EMA stack — same Weinstein logic)
    • Relative strength (Mansfield RS vs Nifty 500, with momentum overlay)
    • Rotation position (RRG quadrant — leading vs lagging the benchmark)

This module computes all four axes per ETF, ranks the universe, and writes
the result to ETF_Screener_Results.csv (matching the bull/recovery output
shape so downstream consumers — pipeline health, TV sync, AI brief — can
treat it identically).

Public API
----------
    score_etf(symbol)              -> dict (single ETF)
    rank_universe(syms=None)       -> pd.DataFrame ranked best-first
    main()                         -> CLI entry: scan + write CSV

CSV output schema (v1.1 -- 12 May 2026)
---------------------------------------
    Symbol, Name, Asset_Class, Sub_Category, Underlying, Issuer,
    Liquidity_Tier, Liquidity_Score, Trend_Score, RS_Score, Rotation_Score,
    Total_Score, Grade, Stage, RRG_Quadrant, Rotation_Vector,
    LTP, SMA50, SMA200, MA200_Slope_pct, Above_SMA200,
    Mansfield_RS, RS_Momentum_4W,
    Vol_60D_Lakhs, Turnover_60D_Cr, Dist_52WH_pct,
    Signal

Changelog
---------
12 May 2026 (v1.1):
    - Reordered signal ladder (ILLIQUID first, then AVOID-DOWNTREND, etc.)
      to match Pine dashboard. Fixes 'ACCUMULATE' overriding 'ILLIQUID'.
    - Locked RS benchmark to ^CRSLDX universally (was per-ETF -- broke
      cross-ETF ranking).
    - Renamed MA30W_Slope_pct -> MA200_Slope_pct, Above_30WMA -> Above_SMA200
      (misnomer; was always 200-DMA slope).
    - Added Rotation_Vector column (current quadrant vs 4-week-prior).
    - Removed dead W_LIQ/W_TREND/W_RS/W_ROTATION constants (never applied).
    - ILLIQUID threshold = LIQ_MIN_CR = Rs 2 Cr/day (matches Pine default).
    - JSON config override via etf_config.json (shared with Pine).
"""

from __future__ import annotations

import os
import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

try:
    import data_provider as _dp
    _USE_DP = True
except Exception:
    _dp = None
    _USE_DP = False

import yfinance as yf

from etf_universe import (
    ETF_UNIVERSE, all_symbols, get_meta, universe_summary,
)

logger = logging.getLogger(__name__)
_DIR = os.path.dirname(os.path.abspath(__file__))

# Benchmark for RS calculation. Nifty 500 is the right denominator for an
# ETF *picker* -- it's broad enough that sector/asset-class rotation shows up.
# Locked to ^CRSLDX universally (NOT per-ETF underlying) so the RS_Score
# column is comparable across ETFs and aligned with the Pine dashboard.
BENCHMARK_YF = "^CRSLDX"

OUTPUT_CSV = "ETF_Screener_Results.csv"

# Liquidity threshold for ILLIQUID signal. Matches Pine dashboard's
# `liq_min_cr` input default (2.0 Rs Cr/day median turnover).
# Single source of truth; etf_config.json loader (below) can override.
LIQ_MIN_CR = 2.0

# Liquidity thresholds (Rs Cr daily turnover, 60-day median)
LIQ_BANDS = [
    (10.0, 10),   # >= 10 Cr/day -> 10/10
    (5.0,   8),
    (2.0,   6),
    (1.0,   4),
    (0.5,   2),
    (0.0,   0),   # below 50L/day -> unscored / illiquid warning
]

# Optional JSON config override (etf_config.json) -- shared with Pine
# via manual sync. If present, overrides defaults above.
try:
    import json as _json
    _cfg_path = os.path.join(_DIR, "etf_config.json")
    if os.path.exists(_cfg_path):
        with open(_cfg_path) as _f:
            _CFG = _json.load(_f)
        BENCHMARK_YF = _CFG.get("benchmark_yf", BENCHMARK_YF)
        LIQ_MIN_CR   = _CFG.get("liq_min_cr",   LIQ_MIN_CR)
        if "liq_bands" in _CFG:
            LIQ_BANDS = [(b["threshold"], b["score"]) for b in _CFG["liq_bands"]]
except Exception:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Data fetch
# ─────────────────────────────────────────────────────────────────────────────
def _fetch_history(syms: List[str], period: str = "2y") -> pd.DataFrame:
    """Fetch close + volume for all symbols. Returns DataFrame with
    MultiIndex columns (Symbol, Field). Uses parquet cache via data_provider
    when available, else yf.download."""
    out_close = pd.DataFrame()
    out_vol   = pd.DataFrame()

    if _USE_DP:
        try:
            bd = _dp.fetch_batch_ohlcv(syms, period=period, interval="1d")
            if bd:
                out_close = pd.DataFrame({
                    (k if k.startswith("^") else f"{k}"): df["Close"]
                    for k, df in bd.items() if "Close" in df.columns
                })
                out_vol = pd.DataFrame({
                    (k if k.startswith("^") else f"{k}"): df["Volume"]
                    for k, df in bd.items() if "Volume" in df.columns
                })
        except Exception as e:
            logger.warning("data_provider batch failed: %s — yf fallback", e)

    if out_close.empty:
        logger.info("ETF screener: prices served by yfinance FALLBACK "
                    "(data_provider/Dhan returned nothing for this batch)")
        raw = yf.download(syms, period=period, interval="1d",
                          auto_adjust=True, progress=False, threads=True)
        if isinstance(raw.columns, pd.MultiIndex):
            out_close = raw["Close"]
            out_vol   = raw["Volume"]
        else:
            out_close = raw[["Close"]].rename(columns={"Close": syms[0]})
            out_vol   = raw[["Volume"]].rename(columns={"Volume": syms[0]})

    return out_close, out_vol


# ─────────────────────────────────────────────────────────────────────────────
# Per-axis scoring
# ─────────────────────────────────────────────────────────────────────────────
def score_liquidity(close: pd.Series, vol: pd.Series) -> tuple:
    """Returns (score 0-10, turnover_cr_60d, vol_lakhs_60d)."""
    if close.empty or vol.empty or len(close) < 60:
        return 0, 0.0, 0.0
    last_60_close = close.tail(60).dropna()
    last_60_vol   = vol.tail(60).dropna()
    if last_60_close.empty or last_60_vol.empty:
        return 0, 0.0, 0.0
    # Daily turnover in ₹ Cr  (price × volume / 1e7)
    turnover_series = (last_60_close * last_60_vol) / 1e7
    median_turnover_cr = float(turnover_series.median())
    median_vol_lakhs   = float(last_60_vol.median() / 1e5)
    score = 0
    for thr, pts in LIQ_BANDS:
        if median_turnover_cr >= thr:
            score = pts
            break
    return score, round(median_turnover_cr, 2), round(median_vol_lakhs, 2)


def _compute_stage(close: pd.Series) -> tuple:
    """Weinstein stage on the daily series (we don't need weekly resample
    here — for ETFs the daily 200-DMA proxies 30-WMA closely enough, and
    rotation logic cares about *position relative to MA*, not the bar
    interval). Returns (stage_int, ma200, ma200_slope)."""
    if len(close) < 210:
        return 0, np.nan, 0.0
    ma200 = close.rolling(200).mean()
    ma200_now  = float(ma200.iloc[-1])
    ma200_prev = float(ma200.iloc[-21])  # ~1mo ago
    slope_pct  = (ma200_now - ma200_prev) / ma200_prev * 100 if ma200_prev else 0.0
    last = float(close.iloc[-1])
    above = last > ma200_now
    rising = slope_pct > 0.1
    if above and rising:    stage = 2
    elif above and not rising: stage = 3
    elif not above and rising: stage = 1
    else:                   stage = 4
    return stage, ma200_now, slope_pct


def score_trend(close: pd.Series) -> tuple:
    """Returns (score 0-10, stage, ma30w_proxy, ma30w_slope_pct,
    above_30wma_bool, dist_52wh_pct)."""
    if close.empty or len(close) < 50:
        return 0, 0, np.nan, 0.0, False, np.nan
    last = float(close.iloc[-1])
    sma50 = float(close.rolling(50).mean().iloc[-1])
    stage, ma200, slope = _compute_stage(close)

    # 52W high proximity
    high_52w = float(close.tail(252).max()) if len(close) >= 252 else float(close.max())
    dist_52wh = (last - high_52w) / high_52w * 100 if high_52w else np.nan

    score = 0
    if stage == 2:                   score += 5
    elif stage == 1:                 score += 2     # basing — partial credit
    if not np.isnan(ma200) and last > ma200:  score += 2
    if last > sma50:                 score += 1
    if slope > 0.5:                  score += 1     # 30W MA rising sharply
    if not np.isnan(dist_52wh) and dist_52wh > -5:  # within 5% of 52W high
        score += 1

    return min(score, 10), stage, ma200, slope, (last > ma200 if not np.isnan(ma200) else False), dist_52wh


def score_rs(close: pd.Series, bench_close: pd.Series) -> tuple:
    """Returns (score 0-10, mansfield_rs_x100, rs_momentum_4w, rrg_quadrant).
    Mansfield RS = (RS / 200-day SMA(RS) - 1) × 100, where RS = price / bench."""
    if (close.empty or bench_close.empty
        or len(close) < 250 or len(bench_close) < 250):
        return 0, np.nan, np.nan, "n/a"

    aligned = pd.concat([close, bench_close], axis=1, join="inner").dropna()
    if len(aligned) < 250:
        return 0, np.nan, np.nan, "n/a"
    aligned.columns = ["px", "bx"]

    rs       = aligned["px"] / aligned["bx"]
    rs_sma   = rs.rolling(200).mean()
    mansfield = (rs / rs_sma - 1) * 100
    mans_now = float(mansfield.iloc[-1])
    mans_4w  = float(mansfield.iloc[-21]) if len(mansfield) >= 21 else mans_now
    momentum_4w = mans_now - mans_4w   # change over ~1 month

    # RRG quadrant on (RS-Ratio, RS-Momentum)
    if   mans_now >= 0 and momentum_4w >= 0: quad = "LEADING"
    elif mans_now >= 0 and momentum_4w <  0: quad = "WEAKENING"
    elif mans_now <  0 and momentum_4w <  0: quad = "LAGGING"
    else:                                    quad = "IMPROVING"

    score = 0
    if mans_now > 0:        score += 3
    if mans_now > 5:        score += 2
    if mans_now > 15:       score += 1
    if momentum_4w > 0:     score += 2
    if momentum_4w > 3:     score += 1
    if quad == "LEADING":   score += 1
    return min(score, 10), round(mans_now, 2), round(momentum_4w, 2), quad


def score_rotation(quad: str, mansfield: float, momentum_4w: float) -> int:
    """Standalone rotation score using the RRG quadrant + magnitude."""
    if quad == "n/a":
        return 0
    base = {"LEADING": 7, "IMPROVING": 5, "WEAKENING": 3, "LAGGING": 1}.get(quad, 0)
    bonus = 0
    if not np.isnan(momentum_4w):
        if momentum_4w > 5:   bonus += 2
        elif momentum_4w > 0: bonus += 1
    if not np.isnan(mansfield) and mansfield > 10:
        bonus += 1
    return min(base + bonus, 10)


def _rotation_vector(close: pd.Series, bench_close: pd.Series) -> str:
    """Compute the rotation direction: current quadrant vs 4-week-prior quadrant.
    Returns one of:
        IGNITE   : LAGGING -> IMPROVING (early turn)
        BREAKOUT : IMPROVING -> LEADING (full rotation in)
        STABLE   : LEADING -> LEADING   (continuation)
        DECAY    : LEADING -> WEAKENING (loss of momentum)
        ROLLOVER : WEAKENING -> LAGGING (full rotation out)
        FALLING  : LAGGING -> LAGGING   (continuation)
        n/a      : insufficient data
    """
    if close.empty or bench_close.empty or len(close) < 250:
        return "n/a"
    aligned = pd.concat([close, bench_close], axis=1, join="inner").dropna()
    if len(aligned) < 250:
        return "n/a"
    aligned.columns = ["px", "bx"]
    rs       = aligned["px"] / aligned["bx"]
    rs_sma   = rs.rolling(200).mean()
    mans     = (rs / rs_sma - 1) * 100
    mom      = mans.diff(20)

    def _q(m, mo):
        if np.isnan(m) or np.isnan(mo): return "n/a"
        if m >= 0 and mo >= 0: return "LEADING"
        if m >= 0 and mo <  0: return "WEAKENING"
        if m <  0 and mo <  0: return "LAGGING"
        return "IMPROVING"

    now  = _q(mans.iloc[-1], mom.iloc[-1])
    prev = _q(mans.iloc[-21] if len(mans) >= 21 else np.nan,
              mom.iloc[-21]  if len(mom)  >= 21 else np.nan)
    if now == "n/a" or prev == "n/a":
        return "n/a"

    transitions = {
        ("LAGGING",   "IMPROVING"): "IGNITE",
        ("IMPROVING", "LEADING"):   "BREAKOUT",
        ("LEADING",   "LEADING"):   "STABLE",
        ("LEADING",   "WEAKENING"): "DECAY",
        ("WEAKENING", "LAGGING"):   "ROLLOVER",
        ("LAGGING",   "LAGGING"):   "FALLING",
        ("IMPROVING", "IMPROVING"): "CHURNING",
        ("WEAKENING", "WEAKENING"): "FADING",
        ("LAGGING",   "LEADING"):   "BREAKOUT",   # quick double-jump
        ("IMPROVING", "WEAKENING"): "REJECTED",   # failed breakout
        ("WEAKENING", "IMPROVING"): "RECOVERED",  # bounce
        ("LEADING",   "LAGGING"):   "COLLAPSED",  # rare big drop
    }
    return transitions.get((prev, now), now)


def grade_for(total: int) -> str:
    if total >= 32:  return "⭐⭐⭐ A+"
    if total >= 26:  return "⭐⭐ A"
    if total >= 20:  return "⭐ B"
    if total >= 14:  return "C"
    return "D"


# ─────────────────────────────────────────────────────────────────────────────
# Main scorer
# ─────────────────────────────────────────────────────────────────────────────
def rank_universe(syms: Optional[List[str]] = None,
                   min_liq_score: int = 2) -> pd.DataFrame:
    """Score and rank the ETF universe. Default = full universe.

    Args
    ----
        syms          : list of symbols (without .NS) or None for full universe
        min_liq_score : drop rows with liquidity_score below this (default 2 =
                        ≥ ₹50L median daily turnover)
    """
    if syms is None:
        syms = list(ETF_UNIVERSE.keys())

    yf_syms = [f"{s}.NS" for s in syms]

    logger.info("Fetching history for %d ETFs + benchmark...", len(yf_syms))
    close_df, vol_df = _fetch_history(yf_syms + [BENCHMARK_YF], period="2y")

    if BENCHMARK_YF not in close_df.columns:
        logger.error("Benchmark %s not fetched — RS scores will be 0", BENCHMARK_YF)
        bench_close = pd.Series(dtype=float)
    else:
        bench_close = close_df[BENCHMARK_YF].dropna()

    rows = []
    for sym in syms:
        ysym = f"{sym}.NS"
        meta = get_meta(sym) or {}
        if ysym not in close_df.columns:
            logger.debug("No data for %s — skipped", sym)
            continue
        close = close_df[ysym].dropna()
        vol   = vol_df[ysym].dropna() if ysym in vol_df.columns else pd.Series(dtype=float)
        if len(close) < 50:
            continue

        liq_score, turnover_cr, vol_lakhs = score_liquidity(close, vol)
        if liq_score < min_liq_score:
            # Still emit the row but flagged — the dashboard can show
            # them in a separate "illiquid" pane.
            pass

        trend_score, stage, ma200, slope_pct, above_30wma, dist_52wh = score_trend(close)

        # RS benchmark LOCKED to Nifty 500 for all ETFs -- ensures cross-ETF
        # rankings are comparable AND matches Pine dashboard's fixed bench.
        # The per-ETF meta["benchmark_yf"] is kept for documentation only.
        rs_score, mansfield, momentum_4w, quad = score_rs(close, bench_close)
        rot_score = score_rotation(quad, mansfield, momentum_4w)

        # RRG Rotation Vector (Enhancement #4): direction of travel.
        # Compares current quadrant to 4-week-prior quadrant.
        rotation_vector = _rotation_vector(close, bench_close)

        # Total uses calibrated weights (here all = 1.0 since each axis is
        # already 0-10; phase 3 will introduce regime-conditional weights)
        total = liq_score + trend_score + rs_score + rot_score
        grade = grade_for(total)

        # Signal label -- ORDER MUST MATCH Pine dashboard (CLAUDE.md zero-drift rule):
        #   1. ILLIQUID first (using LIQ_MIN_CR threshold, matches Pine default 2.0 Cr/day)
        #   2. AVOID-DOWNTREND (Stage 4)
        #   3. BUY-LEADER, ACCUMULATE, HOLD-WATCH, EARLY-BASE
        #   4. NEUTRAL fallback
        if turnover_cr < LIQ_MIN_CR:
            signal = "⚠ ILLIQUID"
        elif stage == 4:
            signal = "🔴 AVOID-DOWNTREND"
        elif stage == 2 and quad == "LEADING" and liq_score >= 6:
            signal = "🟢 BUY-LEADER"
        elif stage == 2 and quad == "IMPROVING":
            signal = "🟡 ACCUMULATE"
        elif stage == 2 and quad == "WEAKENING":
            signal = "🟠 HOLD-WATCH"
        elif stage == 1 and quad == "IMPROVING":
            signal = "🟡 EARLY-BASE"
        else:
            signal = "⚪ NEUTRAL"

        rows.append({
            "Symbol":          sym,
            "Name":            meta.get("name", ""),
            "Asset_Class":     meta.get("asset_class", ""),
            "Sub_Category":    meta.get("sub_category", ""),
            "Underlying":      meta.get("underlying", ""),
            "Issuer":          meta.get("issuer", ""),
            "Liquidity_Tier":  meta.get("liquidity_tier", "?"),

            "Liquidity_Score": liq_score,
            "Trend_Score":     trend_score,
            "RS_Score":        rs_score,
            "Rotation_Score":  rot_score,
            "Total_Score":     total,
            "Grade":           grade,

            "Stage":           stage,
            "RRG_Quadrant":    quad,
            "Rotation_Vector": rotation_vector,    # NEW: current-vs-4w-prior direction

            "LTP":             round(float(close.iloc[-1]), 2),
            "SMA50":           round(float(close.rolling(50).mean().iloc[-1]), 2),
            "SMA200":          round(ma200, 2) if not np.isnan(ma200) else None,
            "MA200_Slope_pct": round(slope_pct, 2),    # FIXED: was MA30W_Slope_pct (misnomer)
            "Above_SMA200":    bool(above_30wma),       # FIXED: was Above_30WMA
            "Mansfield_RS":    mansfield,
            "RS_Momentum_4W":  momentum_4w,
            "Vol_60D_Lakhs":   vol_lakhs,
            "Turnover_60D_Cr": turnover_cr,
            "Dist_52WH_pct":   round(dist_52wh, 2) if not np.isnan(dist_52wh) else None,

            "Signal":          signal,
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).sort_values("Total_Score", ascending=False).reset_index(drop=True)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry
# ─────────────────────────────────────────────────────────────────────────────
def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    print("ETF Screener — Phase 1")
    print("─" * 60)
    summary = universe_summary()
    print(f"Universe: {summary['TOTAL']} ETFs across "
          f"{sum(1 for k,v in summary.items() if k!='TOTAL' and v>0)} asset classes")
    print()

    # Always write a header-only stub first so the file timestamp updates
    # even if the scan finds nothing — same pattern as bull_screener.
    out_path = os.path.join(_DIR, OUTPUT_CSV)
    _empty_cols = ["Symbol", "Name", "Asset_Class", "Total_Score", "Grade",
                   "Stage", "RRG_Quadrant", "Signal"]
    try:
        pd.DataFrame(columns=_empty_cols).to_csv(out_path, index=False)
    except Exception:
        pass

    df = rank_universe()
    if df.empty:
        print("⚠ No ETFs scored. Check data_provider / yfinance connectivity.")
        return

    df.to_csv(out_path, index=False)
    print(f"✅ Wrote {len(df)} ranked ETFs → {OUTPUT_CSV}")
    print()
    print("Top 10:")
    cols = ["Symbol", "Asset_Class", "Total_Score", "Grade", "Stage",
            "RRG_Quadrant", "Mansfield_RS", "Turnover_60D_Cr", "Signal"]
    avail = [c for c in cols if c in df.columns]
    print(df.head(10)[avail].to_string(index=False))
    print()
    print("By asset class (top of each):")
    for cls in df["Asset_Class"].unique():
        top = df[df["Asset_Class"] == cls].head(1)
        if not top.empty:
            r = top.iloc[0]
            print(f"  {cls:<16} → {r['Symbol']:<14} "
                  f"score={r['Total_Score']:>2}/40  "
                  f"stage={r['Stage']}  {r['Signal']}")


if __name__ == "__main__":
    main()
