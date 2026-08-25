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
import sys
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
# The BOARD list. ETF_Screener_Results.csv stays the full analytical dump;
# this is the qualified subset, the same split the stock side uses between a
# screener output and its FINAL_* watchlist.
FINAL_ETF_PICKS = "FINAL_ETF_Picks.csv"

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
    MultiIndex columns (Symbol, Field). Uses data_provider."""
    out_close = pd.DataFrame()
    out_vol   = pd.DataFrame()

    try:
        import data_provider as dp
        bd = dp.fetch_batch_ohlcv(syms, period=period, interval="1d", use_cache=True, auto_adjust=True)
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
        logger.warning("data_provider batch failed: %s", e)

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


# Canonical 30-week flat band, imported in spirit from S4's wmaSlopeThresh input
# (Section4:1481, default 0.0012 x MA over a 4-week change). Same number, so the
# two surfaces call the same chart flat.
WMA_FLAT_PCT = 0.0012


def _compute_stage(close: pd.Series) -> tuple:
    """Weinstein stage, on the SAME stateless 2x2 the rest of the ecosystem uses.

    REWRITTEN 24-Aug-2026. The shape was already right -- above/below the anchor x
    anchor rising/falling -- but all three inputs differed from S4 / v67 / the GM
    board, so an ETF's stage here did not mean what "Stage 2" means anywhere else:

      * ANCHOR was the DAILY 200-SMA as a proxy for the weekly 30-SMA. 200 daily
        bars is ~40 weeks against 30 -- a third longer, and slower to turn. The old
        docstring called it "closely enough"; the 19-Aug parity pass found 19 of 56
        names mis-staged on a smaller discrepancy than this.
      * SLOPE was a PERCENT RATE over 21 daily bars. The canonical form is the RAW
        change over 4 weekly bars. That exact pair of errors (rate-vs-change, wrong
        lookback) is what made the Unified Ecosystem's flat band 6x too wide.
      * FLAT BAND was a hardcoded 0.1%, unrelated to the 0.0012 x MA the rest use.

    Returns (stage_int, ma_now, slope_pct) -- signature unchanged, and slope_pct is
    still a percent so the caller's `slope > 0.5` scoring test keeps its meaning.
    """
    from rrg_engine import weekly_from_daily
    if len(close) < 210:
        return 0, np.nan, 0.0
    w = weekly_from_daily(close)
    if len(w) < 35:                      # 30-period SMA + the 4-bar slope lookback
        return 0, np.nan, 0.0
    ma = w.rolling(30).mean()
    ma_now = float(ma.iloc[-1])
    if not np.isfinite(ma_now) or ma_now == 0:
        return 0, np.nan, 0.0
    raw_slope = ma_now - float(ma.iloc[-5])      # 4-week change, canonical
    band = ma_now * WMA_FLAT_PCT
    last = float(w.iloc[-1])
    above = last >= ma_now
    falling = raw_slope < -band
    if above and not falling:      stage = 2
    elif not above and not falling: stage = 1
    elif above and falling:        stage = 3
    else:                          stage = 4
    slope_pct = raw_slope / ma_now * 100.0
    return stage, ma_now, slope_pct


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

    # QUADRANT FROM THE CANONICAL ENGINE (24-Aug-2026). This used to derive the
    # quadrant from (Mansfield, 4-week Mansfield change) -- which is not JdK RRG at
    # all, just a sign test on two Mansfield readings. It was a THIRD RRG in this
    # stack, and it is why the screener printed GOLDBEES LEADING on the same day the
    # rotation engine printed LAGGING. Mansfield itself is kept: it is a legitimate
    # magnitude Jay reads directly, and it feeds the score below unchanged. Only the
    # QUADRANT moves, because a quadrant is an RRG object and the ecosystem has one
    # definition of that.
    quad = "n/a"
    try:
        from rrg_engine import calculate_jdk_rrg, weekly_from_daily
        _pw = weekly_from_daily(aligned["px"])
        _bw = weekly_from_daily(aligned["bx"])
        _aw = pd.concat([_pw, _bw], axis=1, join="inner").dropna()
        if len(_aw) >= 45:              # strike_cal needs 25 + 10 + 7 + 2 weekly bars
            _aw.columns = ["px", "bx"]
            _res = calculate_jdk_rrg(_aw["px"], _aw["bx"], mode="strike_cal")
            if _res is not None and not _res.empty:
                quad = str(_res["Quadrant"].iloc[-1]).upper()
    except Exception as _e:
        logger.warning("canonical RRG failed, quadrant unavailable: %s", _e)
    # Deliberately NO fallback to the old sign test. A wrong quadrant that looks
    # right is worse than "n/a" -- score_rotation already returns 0 on "n/a", so an
    # engine failure costs the rotation points rather than inventing them.

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
        meta = get_meta(sym) or {}
        # COLUMN KEY (24-Aug-2026). _fetch_history returns BARE symbols -- the ".NS"
        # is stripped on the way through data_provider -- while this loop looked up
        # "SYM.NS", so EVERY symbol missed and rank_universe returned an empty frame.
        # The miss was logged at DEBUG and the only visible symptom was the summary
        # line "No ETFs scored. Check data_provider / yfinance connectivity", which
        # pointed at the network. Connectivity was fine: 56 ETFs fetched, 1241 bars.
        # Resolve the key instead of assuming a suffix, so this survives either
        # convention rather than trading one hardcoded guess for another.
        ysym = sym if sym in close_df.columns else f"{sym}.NS"
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
    # Windows consoles default to cp1252 and this file prints box-drawing rules,
    # so main() died on its FIRST print with UnicodeEncodeError -- which is why the
    # outputs on disk were 98 days old. Reconfigure rather than de-Unicode the
    # output: every other tool here prints the same characters.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
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


def write_board_picks(df=None, path: str = None) -> int:
    """Qualified ETFs for the GM Trigger Board -> FINAL_ETF_Picks.csv.

    THE BOARD IS A BUY BOARD, so this is not the whole universe. Two hard filters,
    and both are ETF-specific risks the stock side has no equivalent for:

      * LIQUIDITY. Roughly a third of the NSE ETF universe reads ILLIQUID -- 17 of
        48 on the run this was written against. An armed ETF you cannot exit is
        worse than no signal at all, and nothing downstream in the board or S4 has
        any concept of turnover. This is the gate that has to live here.
      * DOWNTREND. AVOID-DOWNTREND names are Stage 3/4; the board's break-down
        guard would invalidate them anyway, so admitting them only adds noise.

    Deliberately NOT filtered on signal strength. The board's job is timing, and a
    NEUTRAL or HOLD-WATCH ETF that arrives at a level is exactly what it exists to
    catch. Filtering to BUY-LEADER here would re-qualify on the board's behalf --
    the mistake the inherited-qualification model was built to stop.
    """
    import pandas as pd
    if df is None:
        try:
            df = pd.read_csv(os.path.join(_DIR, OUTPUT_CSV))
        except Exception:
            return 0
    if df is None or df.empty:
        return 0
    out = df.copy()
    sig = out["Signal"].astype(str) if "Signal" in out.columns else pd.Series([""] * len(out))
    keep = ~sig.str.contains("ILLIQUID", na=False) & ~sig.str.contains("AVOID", na=False)
    out = out[keep]

    # OUT OF TRADING SCOPE (25-Aug-2026). Debt and liquid ETFs are still SCORED and
    # still appear in ETF_Screener_Results -- the regime engine reads LIQUIDBEES to
    # detect risk-off and that measurement stays. They are simply never offered as a
    # trade: Jay parks cash in a sweep-in FD, so a board row saying LIQUIDBEES is
    # "Buy Trigger Live" is noise on a surface whose whole job is deciding what to buy.
    try:
        from etf_universe import is_tradeable as _tradeable
        before = len(out)
        out = out[out["Symbol"].map(_tradeable)]
        if before != len(out):
            logger.info("board picks: dropped %d out-of-scope (debt/liquid) ETFs",
                        before - len(out))
    except Exception as e:
        logger.warning("trading-scope filter unavailable (%s) - keeping all rows", e)

    # PREMIUM / DISCOUNT vs NAV -- the third gate, and the only one that measures
    # something no chart can show. See etf_inav for the numbers; the short version
    # is that three international ETFs trade ~19.5% over NAV because SEBI's overseas
    # cap suspended unit creation, so there is no arbitrage to close the gap. Two of
    # them were on the board when this was written, ranked partly on a price series
    # the premium itself inflates.
    # The column is attached to EVERY surviving row, not just the rejected ones --
    # a 1.3% premium on GOLDBEES passes the gate and is still worth seeing before
    # committing 30% of a sleeve to it.
    try:
        import etf_inav as _inav
        _pm = _inav.premium_map()
        if _pm:
            out["Premium_Pct"] = out["Symbol"].astype(str).str.upper().map(_pm)
            _cap = _inav.MAX_PREMIUM_PCT
            _bad = out["Premium_Pct"].abs() > _cap          # NaN compares False = kept
            if _bad.any():
                logger.warning("ETF premium gate blocked %d: %s", int(_bad.sum()),
                               ", ".join(f"{r.Symbol} {r.Premium_Pct:+.1f}%"
                                         for r in out[_bad].itertuples()))
            out = out[~_bad]
        else:
            logger.warning("ETF NAV unavailable - premium gate NOT applied this run")
    except Exception as _e:
        # Never fail the board list over this. A missing premium is a missing
        # WARNING, not a reason to ship no ETFs at all.
        logger.warning("ETF premium gate skipped: %s", _e)
    # Columns the board reads by name; everything else rides along for display.
    if "Symbol" not in out.columns:
        return 0
    path = path or os.path.join(_DIR, FINAL_ETF_PICKS)
    out.to_csv(path, index=False)
    return len(out)
