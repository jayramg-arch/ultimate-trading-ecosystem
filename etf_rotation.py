"""
etf_rotation.py — Phase-2 ETF Rotation Engine for NSE ETFs.

Built 11 May 2026 as Phase 2 of the ETF Trading System.

Why a rotation engine
---------------------
Phase 1 (`etf_screener.py`) scores each ETF on its own merits. But the *real*
ETF alpha is **timing the rotation between exposures** — when do you tilt
from IT to PSU Bank? When does Gold deserve 25% of the book vs 5%? Single-
ETF screening can't answer those.

This module produces three rotation views:

    1. SECTOR ROTATION TABLE
       Ranks all 20 NSE sector ETFs by composite RS:
           composite_RS = 0.6 × 12-week return rank + 0.4 × 4-week momentum rank
       The 60/40 weighting favours the established trend (12W) but lets the
       4W catch the early turn (RRG IMPROVING quadrant). Output: ranked
       sector list with quartile tier — top quartile = OVERWEIGHT.

    2. ASSET-CLASS REGIME DETECTOR
       Compares flagship ETFs across asset classes (NIFTYBEES, GOLDBEES,
       MON100, BBETF, JUNIORBEES) on 4W + 12W return + Stage. Outputs:
           • Regime label: RISK_ON / RISK_OFF / GOLD_LED / INTL_LED / MIXED
           • Suggested allocation tilt (%) per asset class
           • Capital rotation signal vs prior week

    3. RRG COORDINATES (for plotting)
       Per-ETF (RS-Ratio, RS-Momentum) coordinates over the last 8 weeks.
       Drives the RRG quadrant plot in the Pine dashboard (Phase 3) and the
       Commander Web ETF page (Phase 4).

All three are written as CSVs that downstream UIs can render without re-
computing anything.

Public API
----------
    sector_rotation_table()     -> pd.DataFrame
    asset_class_regime()        -> dict
    rrg_coordinates(syms, weeks=8) -> pd.DataFrame
    top_picks_by_regime()       -> pd.DataFrame
    main()                      -> CLI entry: scan + write all CSVs
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
    ETF_UNIVERSE, get_meta, sector_etfs, list_by_asset_class,
)

logger = logging.getLogger(__name__)
_DIR = os.path.dirname(os.path.abspath(__file__))

BENCHMARK_YF = "^CRSLDX"   # Nifty 500 — the rotation denominator

# Output files
SECTOR_CSV    = "ETF_Sector_Rotation.csv"
REGIME_CSV    = "ETF_AssetClass_Regime.csv"
RRG_CSV       = "ETF_RRG_Coordinates.csv"
PICKS_CSV     = "ETF_Top_Picks.csv"

# Asset-class flagships — most liquid representative per class
FLAGSHIPS = {
    "EQUITY_LARGE":  "NIFTYBEES",
    "EQUITY_MID":    "JUNIORBEES",
    "EQUITY_SMALL":  "MID150BEES",
    "GOLD":          "GOLDBEES",
    "SILVER":        "SILVERBEES",
    "INTL_NASDAQ":   "MON100",
    "INTL_FANG":     "MAFANG",
    "DEBT_LIQUID":   "LIQUIDBEES",
    "DEBT_BHARAT":   "BBETF",
}

# Composite RS weights (sector rotation): 60% long-term, 40% short-term
W_LONG  = 0.60   # 12-week return weight
W_SHORT = 0.40   # 4-week momentum weight

# RRG window
RRG_WEEKS_DEFAULT = 8

# Optional JSON config override (etf_config.json) -- shared with etf_screener.py
try:
    import json as _json
    _cfg_path = os.path.join(_DIR, "etf_config.json")
    if os.path.exists(_cfg_path):
        with open(_cfg_path) as _f:
            _CFG = _json.load(_f)
        BENCHMARK_YF = _CFG.get("benchmark_yf", BENCHMARK_YF)
        if "rotation_engine" in _CFG:
            W_LONG  = _CFG["rotation_engine"].get("composite_long_weight",  W_LONG)
            W_SHORT = _CFG["rotation_engine"].get("composite_short_weight", W_SHORT)
except Exception:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Data fetch (re-uses data_provider parquet cache)
# ─────────────────────────────────────────────────────────────────────────────
def _fetch_close(syms: List[str], period: str = "1y") -> pd.DataFrame:
    """Fetch close prices for syms. Returns wide DataFrame indexed by date."""
    out = pd.DataFrame()
    yf_syms = [f"{s}.NS" if not s.startswith("^") and not s.endswith(".NS") else s
               for s in syms]

    if _USE_DP:
        try:
            bd = _dp.fetch_batch_ohlcv(yf_syms, period=period, interval="1d")
            if bd:
                out = pd.DataFrame({
                    k: df["Close"] for k, df in bd.items() if "Close" in df.columns
                })
        except Exception as e:
            logger.warning("data_provider failed: %s — yf fallback", e)

    if out.empty:
        logger.info("ETF rotation: prices served by yfinance FALLBACK "
                    "(data_provider/Dhan returned nothing for this batch)")
        raw = yf.download(yf_syms, period=period, interval="1d",
                          auto_adjust=True, progress=False, threads=True)
        if isinstance(raw.columns, pd.MultiIndex):
            out = raw["Close"]
        else:
            out = raw[["Close"]].rename(columns={"Close": yf_syms[0]})

    # Strip .NS for cleaner column names (keep ^ prefixed)
    out.columns = [c.replace(".NS", "") if not c.startswith("^") else c
                   for c in out.columns]
    return out


def _period_return_pct(close: pd.Series, days: int) -> float:
    """Return % over `days` trading sessions. NaN if insufficient history."""
    s = close.dropna()
    if len(s) < days + 1:
        return np.nan
    return float((s.iloc[-1] - s.iloc[-days - 1]) / s.iloc[-days - 1] * 100)


def _excess_return_pct(close: pd.Series, bench: pd.Series, days: int) -> float:
    """Excess return vs benchmark over `days` sessions. Anchors on intersection
    so prices align even if the ETF / bench have different non-trading dates."""
    aligned = pd.concat([close, bench], axis=1, join="inner").dropna()
    if len(aligned) < days + 1:
        return np.nan
    aligned.columns = ["px", "bx"]
    px_ret = (aligned["px"].iloc[-1] - aligned["px"].iloc[-days - 1]) / aligned["px"].iloc[-days - 1] * 100
    bx_ret = (aligned["bx"].iloc[-1] - aligned["bx"].iloc[-days - 1]) / aligned["bx"].iloc[-days - 1] * 100
    return float(px_ret - bx_ret)


# ─────────────────────────────────────────────────────────────────────────────
# 1. SECTOR ROTATION TABLE
# ─────────────────────────────────────────────────────────────────────────────
def sector_rotation_table() -> pd.DataFrame:
    """Rank all sector ETFs by composite RS (60% 12W + 40% 4W).

    Output columns:
        Symbol, Sub_Category, Underlying, LTP,
        Ret_4W_pct, Ret_12W_pct, Excess_4W_pct, Excess_12W_pct,
        Rank_4W, Rank_12W, Composite_Score, Rank_Composite,
        Quartile, Tilt
        (Quartile: TOP / 2 / 3 / BOTTOM. Tilt: OVERWEIGHT / NEUTRAL+ /
         NEUTRAL- / UNDERWEIGHT)
    """
    syms = sector_etfs()
    close_df = _fetch_close(syms + [BENCHMARK_YF], period="1y")
    if BENCHMARK_YF not in close_df.columns:
        logger.error("Benchmark missing — cannot compute excess returns")
        return pd.DataFrame()
    bench = close_df[BENCHMARK_YF].dropna()

    rows = []
    for sym in syms:
        if sym not in close_df.columns:
            continue
        close = close_df[sym].dropna()
        if len(close) < 65:
            continue
        meta = get_meta(sym) or {}
        r4   = _period_return_pct(close, 20)
        r12  = _period_return_pct(close, 60)
        ex4  = _excess_return_pct(close, bench, 20)
        ex12 = _excess_return_pct(close, bench, 60)
        rows.append({
            "Symbol":       sym,
            "Sub_Category": meta.get("sub_category", ""),
            "Underlying":   meta.get("underlying", ""),
            "LTP":          round(float(close.iloc[-1]), 2),
            "Ret_4W_pct":   round(r4, 2)  if not np.isnan(r4)  else None,
            "Ret_12W_pct":  round(r12, 2) if not np.isnan(r12) else None,
            "Excess_4W_pct":  round(ex4, 2)  if not np.isnan(ex4)  else None,
            "Excess_12W_pct": round(ex12, 2) if not np.isnan(ex12) else None,
        })

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)

    # Rank (1 = best). Use excess returns so we're measuring true rotation,
    # not absolute beta exposure.
    df["Rank_4W"]  = df["Excess_4W_pct"].rank(ascending=False, method="min").astype("Int64")
    df["Rank_12W"] = df["Excess_12W_pct"].rank(ascending=False, method="min").astype("Int64")

    # Composite — invert so higher is better, then weight
    n = len(df)
    df["Composite_Score"] = (
        W_LONG  * (n - df["Rank_12W"].fillna(n) + 1) +
        W_SHORT * (n - df["Rank_4W"].fillna(n)  + 1)
    ).round(2)
    df["Rank_Composite"] = df["Composite_Score"].rank(ascending=False, method="min").astype("Int64")

    # Quartile + tilt
    q = df["Rank_Composite"]
    df["Quartile"] = pd.cut(q, bins=[0, n / 4, n / 2, 3 * n / 4, n + 1],
                             labels=["TOP", "2", "3", "BOTTOM"]).astype(str)
    tilt_map = {"TOP": "🟢 OVERWEIGHT", "2": "🟡 NEUTRAL+",
                "3": "🟠 NEUTRAL−",   "BOTTOM": "🔴 UNDERWEIGHT"}
    df["Tilt"] = df["Quartile"].map(tilt_map).fillna("⚪ —")

    return df.sort_values("Rank_Composite").reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# 2. ASSET-CLASS REGIME DETECTOR
# ─────────────────────────────────────────────────────────────────────────────
def asset_class_regime() -> Dict:
    """Decide capital allocation across asset classes.

    Methodology
    -----------
    For each flagship ETF we measure 4W + 12W return + above-200DMA flag.
    Score = 0.5 × Ret_12W + 0.5 × Ret_4W (favours recent acceleration but
    anchored to trend). Above-200DMA acts as a binary trend gate: if the
    flagship is below its 200DMA, the asset class is RISK-OFF regardless of
    short-term return.

    Output
    ------
        {
          "regime_label": "RISK_ON" | "RISK_OFF" | "GOLD_LED" |
                          "INTL_LED" | "MIXED",
          "fetched_at":   ISO timestamp,
          "rows": [{class, flagship, ret_4w, ret_12w, score, above_200dma,
                    suggested_tilt_pct, status}, ...]
        }

    Suggested tilt
    --------------
    Capital is split among asset classes whose flagship is above its 200DMA
    AND has positive 12W excess return. Top scorer gets 40%, then 25%, 20%,
    15%, 0%, 0%... Gold gets a minimum 10% floor in RISK_OFF regimes (the
    diversifier sleeve). Debt absorbs anything not allocated.
    """
    import datetime as _dt

    syms = list(FLAGSHIPS.values())
    close_df = _fetch_close(syms + [BENCHMARK_YF], period="1y")
    if BENCHMARK_YF not in close_df.columns:
        return {"regime_label": "UNKNOWN", "rows": [],
                "fetched_at": _dt.datetime.now().isoformat()}
    bench = close_df[BENCHMARK_YF].dropna()

    rows = []
    for cls, sym in FLAGSHIPS.items():
        if sym not in close_df.columns:
            continue
        close = close_df[sym].dropna()
        if len(close) < 65:
            continue
        r4    = _period_return_pct(close, 20)
        r12   = _period_return_pct(close, 60)
        ex12  = _excess_return_pct(close, bench, 60)
        ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else np.nan
        last  = float(close.iloc[-1])
        above_200 = (not np.isnan(ma200)) and last > ma200

        score = (0.5 * (r12 if not np.isnan(r12) else 0) +
                 0.5 * (r4  if not np.isnan(r4)  else 0))

        # Status flag drives tilt eligibility
        if above_200 and not np.isnan(r12) and r12 > 0:
            status = "RISK_ON"
        elif above_200:
            status = "NEUTRAL"
        else:
            status = "RISK_OFF"

        rows.append({
            "asset_class":     cls,
            "flagship":        sym,
            "ret_4w_pct":      round(r4, 2)  if not np.isnan(r4)  else None,
            "ret_12w_pct":     round(r12, 2) if not np.isnan(r12) else None,
            "excess_12w_pct":  round(ex12, 2) if not np.isnan(ex12) else None,
            "above_200dma":    bool(above_200),
            "score":           round(score, 2),
            "status":          status,
        })

    # ── Allocation logic ────────────────────────────────────────────────────
    eligible = [r for r in rows if r["status"] == "RISK_ON"]
    eligible.sort(key=lambda r: r["score"], reverse=True)

    # Tilt template by rank position
    TILTS = [40, 25, 20, 15, 0, 0, 0, 0, 0]
    for r in rows:
        r["suggested_tilt_pct"] = 0
    for i, r in enumerate(eligible):
        r["suggested_tilt_pct"] = TILTS[min(i, len(TILTS) - 1)]

    # Gold floor in RISK_OFF
    gold_row = next((r for r in rows if r["asset_class"] == "GOLD"), None)
    risk_off_count = sum(1 for r in rows if r["status"] == "RISK_OFF" and
                          r["asset_class"].startswith("EQUITY"))
    if gold_row and risk_off_count >= 2 and gold_row["suggested_tilt_pct"] < 10:
        gold_row["suggested_tilt_pct"] = 10

    # Debt absorbs the unallocated
    total_alloc = sum(r["suggested_tilt_pct"] for r in rows)
    debt_row = next((r for r in rows if r["asset_class"] == "DEBT_LIQUID"), None)
    if debt_row:
        debt_row["suggested_tilt_pct"] = max(0, 100 - total_alloc)

    # ── Regime label ────────────────────────────────────────────────────────
    label = "MIXED"
    eq_on   = sum(1 for r in eligible if r["asset_class"].startswith("EQUITY"))
    intl_on = sum(1 for r in eligible if r["asset_class"].startswith("INTL"))
    gold_on = gold_row and gold_row["status"] == "RISK_ON"

    if eq_on >= 2 and (gold_row is None or gold_row["score"] < 5):
        label = "RISK_ON"
    elif gold_on and gold_row["score"] > max((r["score"] for r in eligible
                                               if r["asset_class"].startswith("EQUITY")),
                                              default=0):
        label = "GOLD_LED"
    elif intl_on >= 1 and eq_on == 0:
        label = "INTL_LED"
    elif eq_on == 0 and intl_on == 0 and not gold_on:
        # FIXED Bug #6: widened condition. Previously required only "eq_on == 0
        # and not gold_on" which missed debt-led / fully-defensive regimes.
        label = "RISK_OFF"

    return {
        "regime_label": label,
        "fetched_at":   _dt.datetime.now().isoformat(timespec="seconds"),
        "rows":         rows,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. RRG COORDINATES
# ─────────────────────────────────────────────────────────────────────────────
def rrg_coordinates(syms: Optional[List[str]] = None,
                    weeks: int = RRG_WEEKS_DEFAULT) -> pd.DataFrame:
    """RS-Ratio + RS-Momentum coordinates over the last `weeks` weeks.

    RS-Ratio    = (RS / 200d-SMA(RS) - 1) × 100   (Mansfield, ×100 scale)
    RS-Momentum = ROC(RS-Ratio, 4 weeks)          (1-month change)

    Returns long-format DataFrame:
        Symbol, week_offset, rs_ratio, rs_momentum, quadrant
        week_offset: 0 = current, -1 = 1 week ago, ..., -(weeks-1) = oldest

    The weekly tail powers the "rotation tail" trail in the RRG plot.
    """
    if syms is None:
        # Default: sector ETFs + flagships (the rotation universe)
        syms = sorted(set(sector_etfs() + list(FLAGSHIPS.values())))

    close_df = _fetch_close(syms + [BENCHMARK_YF], period="2y")
    if BENCHMARK_YF not in close_df.columns:
        return pd.DataFrame()
    bench = close_df[BENCHMARK_YF].dropna()

    rows = []
    for sym in syms:
        if sym not in close_df.columns:
            continue
        close = close_df[sym].dropna()
        aligned = pd.concat([close, bench], axis=1, join="inner").dropna()
        if len(aligned) < 220:
            continue
        aligned.columns = ["px", "bx"]
        rs        = aligned["px"] / aligned["bx"]
        rs_sma    = rs.rolling(200).mean()
        rs_ratio  = (rs / rs_sma - 1) * 100             # %
        rs_mom    = rs_ratio.diff(20)                    # 4-week change

        # Sample at weekly cadence (every ~5 sessions) for the last `weeks` points
        for w in range(weeks):
            offset = -1 - (w * 5)                        # 0,-5,-10... in trading days
            if abs(offset) >= len(rs_ratio):
                break
            rr = rs_ratio.iloc[offset]
            rm = rs_mom.iloc[offset]
            if np.isnan(rr) or np.isnan(rm):
                continue
            if   rr >= 0 and rm >= 0: quad = "LEADING"
            elif rr >= 0 and rm <  0: quad = "WEAKENING"
            elif rr <  0 and rm <  0: quad = "LAGGING"
            else:                     quad = "IMPROVING"
            rows.append({
                "Symbol":      sym,
                "week_offset": -w,                       # 0 = now, -1 = last week...
                "rs_ratio":    round(float(rr), 2),
                "rs_momentum": round(float(rm), 2),
                "quadrant":    quad,
            })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["Symbol", "week_offset"],
                                           ascending=[True, False]).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Correlation gate -- block top picks that are too highly correlated.
# Enhancement #2 from the validation audit. Prevents the rotation engine from
# outputting 5 highly-correlated equity sector ETFs in a commodity-led cycle.
# ─────────────────────────────────────────────────────────────────────────────
CORR_THRESHOLD = 0.75   # symbols with 60d corr above this are considered redundant
CORR_LOOKBACK  = 60     # trading days for the correlation window


def _correlation_matrix(syms: List[str], lookback: int = CORR_LOOKBACK) -> pd.DataFrame:
    """Pairwise correlation of daily returns over `lookback` sessions.
    Returns an empty DataFrame if data is missing -- caller should handle."""
    if not syms:
        return pd.DataFrame()
    px = _fetch_close(syms, period="6mo")
    if px.empty:
        return pd.DataFrame()
    ret = px.pct_change().tail(lookback).dropna(how="all")
    if len(ret) < lookback // 2:
        return pd.DataFrame()
    return ret.corr()


def _filter_correlated(candidates: List[str], corr_mat: pd.DataFrame,
                        threshold: float = CORR_THRESHOLD) -> List[str]:
    """Drop candidates whose correlation with an earlier-accepted candidate
    exceeds `threshold`. Preserves the input order (= conviction order)."""
    if corr_mat.empty:
        return candidates
    accepted: List[str] = []
    for c in candidates:
        if c not in corr_mat.columns:
            accepted.append(c)
            continue
        redundant = False
        for a in accepted:
            if a in corr_mat.columns:
                r = corr_mat.loc[c, a]
                if not np.isnan(r) and abs(r) >= threshold:
                    redundant = True
                    break
        if not redundant:
            accepted.append(c)
    return accepted


# ─────────────────────────────────────────────────────────────────────────────
# Liquidity warning helper -- Enhancement #3 from audit.
# Flags top picks whose current 60-day median turnover is below threshold.
# ─────────────────────────────────────────────────────────────────────────────
def _liquidity_status(sym: str, close_df: pd.DataFrame,
                       vol_df: pd.DataFrame, min_cr: float = 2.0) -> str:
    if sym not in close_df.columns or sym not in vol_df.columns:
        return "?"
    close = close_df[sym].dropna().tail(60)
    vol   = vol_df[sym].dropna().tail(60)
    if close.empty or vol.empty:
        return "?"
    turnover_cr = ((close * vol) / 1e7).median()
    if turnover_cr >= min_cr * 2:    return "OK"
    if turnover_cr >= min_cr:         return "OK"
    if turnover_cr >= min_cr * 0.5:   return "WATCH"
    return "ILLIQUID"


# ─────────────────────────────────────────────────────────────────────────────
# 4. UNIFIED TOP PICKS BY REGIME
# ─────────────────────────────────────────────────────────────────────────────
def top_picks_by_regime(sector_df: pd.DataFrame,
                         regime: Dict,
                         max_picks: int = 8,
                         apply_correlation_gate: bool = True,
                         apply_liquidity_warning: bool = True) -> pd.DataFrame:
    """Combine sector rotation + asset-class regime into a single picks list.

    Logic:
        • In RISK_ON: top 5 sector ETFs (composite quartile = TOP)
                      + JUNIORBEES + MID150BEES + MAFANG (broad/intl)
        • In GOLD_LED: top 2 sector ETFs + GOLDBEES + SILVERBEES + MAFANG
        • In INTL_LED: MAFANG + MON100 + top 2 sector ETFs
        • In RISK_OFF: GOLDBEES + LIQUIDBEES + BBETF (defensive)
        • In MIXED:   top 4 sector ETFs + GOLDBEES + MAFANG

    Output: DataFrame with Symbol, Reason, Suggested_Weight_pct, Source.
    """
    label = regime.get("regime_label", "MIXED")

    # Sector candidates: top quartile only
    top_sectors = (sector_df[sector_df["Quartile"] == "TOP"]
                   ["Symbol"].tolist() if not sector_df.empty else [])

    # Build picks per regime
    picks: List[Dict] = []

    def add(sym, reason, weight, source):
        picks.append({"Symbol": sym, "Reason": reason,
                      "Suggested_Weight_pct": weight, "Source": source})

    if label == "RISK_ON":
        for i, s in enumerate(top_sectors[:5]):
            add(s, f"Sector rotation #{i+1}", 12, "Sector")
        add("JUNIORBEES", "Mid-cap broad equity tilt", 15, "Broad")
        add("MID150BEES", "Mid-cap broad equity tilt", 15, "Broad")
        add("MAFANG",     "International diversifier", 10, "Intl")
    elif label == "GOLD_LED":
        for i, s in enumerate(top_sectors[:2]):
            add(s, f"Defensive sector #{i+1}", 10, "Sector")
        add("GOLDBEES",   "Gold leadership regime", 30, "Commodity")
        add("SILVERBEES", "Precious-metal sleeve",  10, "Commodity")
        add("MAFANG",     "Intl hedge",             10, "Intl")
        add("LIQUIDBEES", "Cash sleeve",            30, "Debt")
    elif label == "INTL_LED":
        add("MAFANG",     "International leadership", 25, "Intl")
        add("MON100",     "Nasdaq exposure",          25, "Intl")
        for i, s in enumerate(top_sectors[:2]):
            add(s, f"Best Indian sector #{i+1}", 15, "Sector")
        add("GOLDBEES",   "Diversifier", 10, "Commodity")
        add("LIQUIDBEES", "Cash sleeve", 10, "Debt")
    elif label == "RISK_OFF":
        add("GOLDBEES",   "Risk-off flight",   25, "Commodity")
        add("LIQUIDBEES", "Cash preservation", 50, "Debt")
        add("BBETF",      "Bond ladder",       15, "Debt")
        add("SILVERBEES", "Diversifier",       10, "Commodity")
    else:  # MIXED
        for i, s in enumerate(top_sectors[:4]):
            add(s, f"Sector rotation #{i+1}", 12, "Sector")
        add("GOLDBEES",   "Diversifier",       15, "Commodity")
        add("MAFANG",     "International",     10, "Intl")
        add("LIQUIDBEES", "Cash sleeve",       17, "Debt")

    df = pd.DataFrame(picks).head(max_picks)
    df["Regime"] = label

    # ── Correlation gate (Enhancement #2) ──────────────────────────────────
    # Re-rank sector-source picks by removing redundant correlated names.
    # Non-sector picks (broad/intl/commodity/debt) are preserved as-is.
    if apply_correlation_gate and not df.empty:
        try:
            all_syms = df["Symbol"].tolist()
            corr_mat = _correlation_matrix(all_syms)
            if not corr_mat.empty:
                kept = _filter_correlated(all_syms, corr_mat)
                df = df[df["Symbol"].isin(kept)].reset_index(drop=True)
        except Exception as e:
            logger.warning("Correlation gate skipped: %s", e)

    # ── Liquidity warning (Enhancement #3) ─────────────────────────────────
    # Adds a Liquidity_Status column to the picks output. Currently best-effort
    # -- a fuller liquidity check would require re-fetching ETF volume data.
    if apply_liquidity_warning and not df.empty:
        try:
            syms = df["Symbol"].tolist()
            yf_syms = [f"{s}.NS" for s in syms]
            close_df = _fetch_close(syms, period="6mo")
            # _fetch_close strips .NS and returns only Close; need Volume too.
            # Prefer data_provider (Dhan-first, full OHLCV); yfinance is a loud fallback.
            vol_df = pd.DataFrame()
            if _USE_DP and _dp is not None:
                try:
                    bd = _dp.fetch_batch_ohlcv(yf_syms, period="6mo", interval="1d")
                    if bd:
                        vol_df = pd.DataFrame({
                            k.replace(".NS", ""): v["Volume"]
                            for k, v in bd.items() if "Volume" in v.columns
                        })
                except Exception as e:
                    logger.warning("Liquidity volume via data_provider failed: %s — yf fallback", e)
            if vol_df.empty:
                import yfinance as _yf
                logger.info("ETF liquidity volume served by yfinance FALLBACK (data_provider empty)")
                vol_raw = _yf.download(yf_syms, period="6mo", interval="1d",
                                        progress=False, auto_adjust=True, threads=True)
                vol_df = vol_raw["Volume"] if isinstance(vol_raw.columns, pd.MultiIndex) else pd.DataFrame()
                vol_df.columns = [c.replace(".NS", "") for c in vol_df.columns]
            df["Liquidity_Status"] = df["Symbol"].apply(
                lambda s: _liquidity_status(s, close_df, vol_df, min_cr=2.0)
            )
        except Exception as e:
            logger.warning("Liquidity warning skipped: %s", e)
            df["Liquidity_Status"] = "?"

    return df


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    print("ETF Rotation Engine — Phase 2")
    print("─" * 60)

    # Always write header-only stubs first so timestamps update even on failure
    for fname, cols in [
        (SECTOR_CSV, ["Symbol", "Composite_Score", "Quartile", "Tilt"]),
        (REGIME_CSV, ["asset_class", "score", "suggested_tilt_pct", "status"]),
        (RRG_CSV,    ["Symbol", "week_offset", "rs_ratio", "rs_momentum"]),
        (PICKS_CSV,  ["Symbol", "Reason", "Suggested_Weight_pct", "Regime"]),
    ]:
        try:
            pd.DataFrame(columns=cols).to_csv(os.path.join(_DIR, fname), index=False)
        except Exception:
            pass

    # 1. Sector rotation
    print("→ Computing sector rotation table...")
    sector_df = sector_rotation_table()
    if sector_df.empty:
        print("  ⚠ Sector rotation table empty (data fetch failed?)")
    else:
        sector_df.to_csv(os.path.join(_DIR, SECTOR_CSV), index=False)
        print(f"  ✓ {len(sector_df)} sectors ranked → {SECTOR_CSV}")
        print()
        print("  TOP-quartile sectors (OVERWEIGHT):")
        top = sector_df[sector_df["Quartile"] == "TOP"]
        for _, r in top.iterrows():
            print(f"    #{r['Rank_Composite']} {r['Symbol']:<14} "
                  f"{r['Sub_Category']:<22} "
                  f"4W={r['Excess_4W_pct']:>+6.2f}%  "
                  f"12W={r['Excess_12W_pct']:>+6.2f}%  "
                  f"score={r['Composite_Score']}")

    # 2. Asset-class regime
    print()
    print("→ Detecting asset-class regime...")
    regime = asset_class_regime()
    if regime["rows"]:
        df_reg = pd.DataFrame(regime["rows"])
        df_reg["regime_label"] = regime["regime_label"]
        df_reg["fetched_at"]   = regime["fetched_at"]
        df_reg.to_csv(os.path.join(_DIR, REGIME_CSV), index=False)
        print(f"  ✓ Regime: **{regime['regime_label']}** → {REGIME_CSV}")
        print()
        print("  Allocation tilts:")
        for r in regime["rows"]:
            if r["suggested_tilt_pct"] > 0:
                print(f"    {r['asset_class']:<14} ({r['flagship']:<11}) "
                      f"score={r['score']:>+6.2f}  "
                      f"tilt={r['suggested_tilt_pct']:>3}%  "
                      f"status={r['status']}")
    else:
        print("  ⚠ Regime detection failed (data fetch issue)")

    # 3. RRG coordinates
    print()
    print("→ Generating RRG coordinates (8-week tail)...")
    rrg = rrg_coordinates(weeks=RRG_WEEKS_DEFAULT)
    if rrg.empty:
        print("  ⚠ RRG empty")
    else:
        rrg.to_csv(os.path.join(_DIR, RRG_CSV), index=False)
        n_syms = rrg["Symbol"].nunique()
        print(f"  ✓ {len(rrg)} coordinates for {n_syms} ETFs → {RRG_CSV}")
        cur = rrg[rrg["week_offset"] == 0]
        if not cur.empty:
            print()
            print("  Current quadrant distribution:")
            for q, n in cur["quadrant"].value_counts().items():
                print(f"    {q:<12} {n}")

    # 4. Unified top picks
    print()
    print("→ Building regime-aware top picks...")
    picks = top_picks_by_regime(sector_df if not sector_df.empty else pd.DataFrame(),
                                 regime)
    if picks.empty:
        print("  ⚠ No picks produced")
    else:
        picks.to_csv(os.path.join(_DIR, PICKS_CSV), index=False)
        print(f"  ✓ {len(picks)} picks → {PICKS_CSV}")
        print()
        print("  Regime-aware picks:")
        for _, p in picks.iterrows():
            print(f"    {p['Symbol']:<12} {p['Suggested_Weight_pct']:>3}%  "
                  f"[{p['Source']:<10}] {p['Reason']}")

    print()
    print("Phase 2 complete. Run again any session — outputs are date-stamped.")


__all__ = [
    "sector_rotation_table", "asset_class_regime",
    "rrg_coordinates", "top_picks_by_regime",
    "FLAGSHIPS", "BENCHMARK_YF",
]


if __name__ == "__main__":
    main()
