"""
market_regime.py — Distribution-day, follow-through, Zweig breadth-thrust,
and a composite regime classifier shared by the dashboard, screeners, and
(in time) the Sniper entry guard.

Implements three classic timing tools that the Commander stack was missing:

  • Distribution Day Tracker (O'Neil)
        A "distribution day" = benchmark closes ≥ 0.2% lower on volume above
        the prior day. ≥5 in any rolling 25-session window = institutions
        unloading → cap or pause new positional entries.

  • Follow-Through Day Detector (O'Neil / IBD)
        After a correction low (benchmark prints ≥3% off prior 50-day high):
        on bar 4–25 of the rally attempt, a session that closes up ≥1.7% on
        higher volume than the prior day = green light to begin re-entry.
        Not perfect (~30% false positives) but the canonical re-entry signal.

  • Zweig Breadth Thrust (transition variant — B8)
        EMA10 of A/(A+D) must cross *up* through 0.40 then up through 0.615
        within 10 trading days. Rare, but extremely bullish when it fires
        — different from "is current EMA ≥ 0.615" which the prior breadth
        engine implementation was effectively reporting.

Regime score 0–10 combines:
  +3  benchmark above SMA200 with rising 5-day SMA200 slope
  +2  breadth (% above SMA200) ≥ 50%
  +2  distribution-day count ≤ 3 in last 25 sessions
  +1  no death cross (SMA50 > SMA200)
  +1  follow-through day inside the last 10 sessions
  +1  Zweig breadth thrust active (EMA10 of A/A+D ≥ 0.615 with valid transition)

Verdict mapping:
  8–10  RISK-ON / Bull Healthy
  6–7   Cautious Bull
  4–5   Neutral / Choppy
  2–3   Defensive
  0–1   Bear / Cash

Persistent state is stored in ``regime_state.json`` so distribution-day decay,
breadth-thrust transitions, and follow-through windows survive process
restarts and dashboard reruns.
"""

from __future__ import annotations

import json
import os
import time
import logging

logger = logging.getLogger(__name__)
from datetime import datetime, timedelta
from typing import Optional

import threading
import numpy as np
import pandas as pd
import yfinance as yf
from net_utils import is_internet_available

# Process-wide lock for the dashboard's background regime refresh. Created ONCE
# at import (race-free) so at most one silent regime-update thread runs at a time.
# PC-HANG FIX (20 Jun 2026): the previous code created this lock lazily INSIDE the
# spawned thread (a check-then-act race -> two threads could each make their own
# Lock, both acquire, and run compute_regime concurrently) AND spawned a new
# thread on every Streamlit rerun. Under rapid reruns that produced a thread /
# yfinance-socket storm -> ephemeral-port exhaustion -> Windows kernel freeze.
_regime_update_lock = threading.Lock()


# C1: route OHLCV through the unified data_provider when available.
try:
    import data_provider as _dp
    USE_DATA_PROVIDER = True
except Exception:
    _dp = None
    USE_DATA_PROVIDER = False

# ─── Paths & defaults ─────────────────────────────────────────────────────────
HERE          = os.path.dirname(os.path.abspath(__file__))
STATE_PATH    = os.path.join(HERE, "regime_state.json")
BENCHMARK_YF  = "^CRSLDX"   # Nifty 500 — same as bull/recovery screeners

# Tunables — keep close to the canonical rules for transparency
DD_DROP_PCT          = 0.20    # day-bar drop ≥ 0.20% counts
DD_WINDOW            = 25      # rolling distribution count window
DD_HARD_LIMIT        = 5       # ≥5 distribution days in window = stress

CORRECTION_DRAWDOWN  = 3.00    # ≥3% off recent 50-day high triggers correction state
CORRECTION_LOOKBACK  = 50

FT_MIN_BAR           = 4       # earliest bar (after low) where FT can count
FT_MAX_BAR           = 25      # latest bar
FT_GAIN_PCT          = 1.70    # day must close up ≥ 1.70%
FT_VOL_HIGHER        = True    # volume must exceed prior day

ZWEIG_LOWER          = 0.40
ZWEIG_UPPER          = 0.615
ZWEIG_WINDOW         = 10      # bars to complete the cross sequence


# ─── State persistence ────────────────────────────────────────────────────────
def _load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, default=str)
    except Exception:
        pass


# ─── Benchmark fetch ──────────────────────────────────────────────────────────
def _fetch_benchmark(period: str = "1y") -> pd.DataFrame:
    """Daily OHLCV for ^CRSLDX. Returned df is flat-columned, NaN-dropped.
    C1: cached via data_provider so the regime score computation reuses the
    same benchmark slice as bull_screener / recovery_screener / exit_engine.
    """
    if USE_DATA_PROVIDER and _dp is not None:
        raw = _dp.fetch_ohlcv(BENCHMARK_YF, period=period, interval="1d")
    else:
        raw = yf.download(BENCHMARK_YF, period=period, interval="1d",
                           auto_adjust=True, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    return raw.dropna(how="all")


# ─── Distribution day count ───────────────────────────────────────────────────
def compute_distribution_days(df: pd.DataFrame,
                                 drop_pct: float = DD_DROP_PCT,
                                 window: int = DD_WINDOW) -> dict:
    """Count distribution days (close down ≥drop_pct% on higher volume vs prior day)
    inside the most recent `window` sessions. Returns dict with count, dates,
    and `stress` flag (count ≥ DD_HARD_LIMIT).
    """
    if df.empty or len(df) < window + 2:
        return {"count": 0, "dates": [], "stress": False, "details": "insufficient data"}
    work = df.tail(window + 1).copy()
    work["pct"]    = work["Close"].pct_change() * 100
    work["volup"]  = work["Volume"] > work["Volume"].shift(1)
    work["dd"]     = (work["pct"] <= -drop_pct) & work["volup"]
    recent = work.iloc[-window:]
    dd_dates = recent.index[recent["dd"]].strftime("%Y-%m-%d").tolist()
    count = len(dd_dates)
    return {
        "count":   count,
        "dates":   dd_dates,
        "window":  window,
        "stress":  count >= DD_HARD_LIMIT,
        "details": f"{count} distribution day(s) in last {window} sessions",
    }


# ─── Follow-through detector ──────────────────────────────────────────────────
def detect_follow_through(df: pd.DataFrame,
                            min_bar: int = FT_MIN_BAR,
                            max_bar: int = FT_MAX_BAR,
                            gain_pct: float = FT_GAIN_PCT,
                            require_volume_higher: bool = FT_VOL_HIGHER) -> dict:
    """Identify the most recent valid follow-through day if present.

    Algorithm:
      1. Find the most recent "correction low" — a bar where price was ≥
         CORRECTION_DRAWDOWN% below its prior 50-day high.
      2. Walk forward from that low; on bars [min_bar, max_bar] check whether
         any session closed up ≥ gain_pct% with volume > prior day.
      3. Return the first qualifying session (date, gain, days-since-low).
    """
    if df.empty or len(df) < CORRECTION_LOOKBACK + max_bar + 5:
        return {"active": False, "details": "insufficient data"}

    work = df.copy()
    work["high50"]     = work["High"].rolling(CORRECTION_LOOKBACK).max()
    work["drawdown"]   = (work["high50"] - work["Close"]) / work["high50"] * 100
    work["pct"]        = work["Close"].pct_change() * 100
    work["volup"]      = work["Volume"] > work["Volume"].shift(1)

    # Find the most recent correction low — the lowest Close in the last
    # 60 sessions where drawdown breached threshold.
    recent_window = work.tail(60)
    correction = recent_window[recent_window["drawdown"] >= CORRECTION_DRAWDOWN]
    if correction.empty:
        return {"active": False, "details": "no correction in last 60 sessions"}

    low_idx_pos = recent_window["Close"].idxmin()
    if low_idx_pos not in work.index:
        return {"active": False, "details": "low index not found"}

    pos_of_low = work.index.get_loc(low_idx_pos)
    bars_since_low = len(work) - 1 - pos_of_low
    if bars_since_low < min_bar:
        return {"active": False,
                 "details": f"only {bars_since_low}d since low (need ≥{min_bar})",
                 "low_date": str(low_idx_pos.date())}

    # Walk forward and score
    candidate_dates = []
    end = min(pos_of_low + max_bar + 1, len(work))
    for i in range(pos_of_low + min_bar, end):
        row = work.iloc[i]
        if pd.isna(row["pct"]):
            continue
        if row["pct"] >= gain_pct and (not require_volume_higher or bool(row["volup"])):
            candidate_dates.append((work.index[i], float(row["pct"])))

    if not candidate_dates:
        return {"active": False,
                 "details": f"no FT day on bars {min_bar}–{max_bar} since low",
                 "low_date": str(low_idx_pos.date()),
                 "bars_since_low": bars_since_low}

    ft_date, ft_gain = candidate_dates[-1]   # most recent in the window
    days_ago = len(work) - 1 - work.index.get_loc(ft_date)
    return {
        "active":          days_ago <= 10,    # treat as fresh signal for 10 bars
        "ft_date":         str(ft_date.date()),
        "ft_gain_pct":     round(ft_gain, 2),
        "low_date":        str(low_idx_pos.date()),
        "bars_since_low":  bars_since_low,
        "days_since_ft":   days_ago,
        "details":         f"FT on {ft_date.date()}: +{ft_gain:.2f}% ({days_ago}d ago)",
    }


# ─── Zweig Breadth Thrust (transition) ────────────────────────────────────────
def detect_breadth_thrust(ad_history: pd.DataFrame,
                            lower: float = ZWEIG_LOWER,
                            upper: float = ZWEIG_UPPER,
                            window: int = ZWEIG_WINDOW) -> dict:
    """Detect the canonical Zweig Breadth Thrust transition.

    EMA10 of A/(A+D) must travel from ≤lower to ≥upper within `window` bars.
    `ad_history` must have advance_count and decline_count columns ordered
    oldest → newest with at least window + 5 rows.
    """
    if ad_history is None or ad_history.empty or len(ad_history) < window + 5:
        return {"active": False, "details": "insufficient breadth history"}
    df = ad_history.copy()
    df["ratio"] = df["advance_count"] / (df["advance_count"] + df["decline_count"]).replace(0, np.nan)
    df["ema10"] = df["ratio"].ewm(span=10, adjust=False).mean()

    series = df["ema10"].dropna()
    if len(series) < window + 2:
        return {"active": False,
                 "current_ema10": float(series.iloc[-1]) if not series.empty else None,
                 "details": "EMA10 not warmed up"}

    cur = float(series.iloc[-1])
    # Walk back: find the most recent bar where EMA10 was ≤ lower, and the
    # most recent bar where EMA10 ≥ upper. If the upper crossing is at or
    # after a lower crossing within `window` bars, the thrust is fresh.
    above_upper_idx = series[series >= upper].index
    below_lower_idx = series[series <= lower].index
    active = False
    transition_bars = None
    if len(above_upper_idx) and len(below_lower_idx):
        last_upper_pos = series.index.get_loc(above_upper_idx[-1])
        # latest lower-touch *before* that upper
        prior_lower_positions = [
            series.index.get_loc(d) for d in below_lower_idx
            if series.index.get_loc(d) <= last_upper_pos
        ]
        if prior_lower_positions:
            last_lower_pos = max(prior_lower_positions)
            transition_bars = last_upper_pos - last_lower_pos
            # Active if the thrust completed within `window` bars AND the
            # crossing happened in the last 20 sessions (still fresh).
            recent = (len(series) - 1 - last_upper_pos) <= 20
            active = transition_bars <= window and recent

    return {
        "active":          active,
        "current_ema10":   round(cur, 4),
        "lower":           lower,
        "upper":           upper,
        "transition_bars": transition_bars,
        "details": (f"Thrust active: ratio crossed {lower:.2f}→{upper:.2f} in "
                    f"{transition_bars}d" if active
                    else f"No fresh thrust (current EMA10={cur:.3f})"),
    }


# ─── Composite regime score & verdict ─────────────────────────────────────────
def _verdict(score: int) -> str:
    if score >= 8:  return "RISK-ON / Bull Healthy"
    if score >= 6:  return "Cautious Bull"
    if score >= 4:  return "Neutral / Choppy"
    if score >= 2:  return "Defensive"
    return "Bear / Cash"


def compute_regime(breadth_metrics: Optional[dict] = None,
                     ad_history: Optional[pd.DataFrame] = None,
                     persist: bool = True) -> dict:
    """Compute the composite market regime.

    Parameters
    ----------
    breadth_metrics : dict
        Output of breadth_engine.calculate_breadth_metrics().
        If None, the regime is computed without breadth (caps at 8 points).
    ad_history : DataFrame
        Output of breadth_engine.bootstrap_ad_history(). Required for the
        breadth-thrust check; if None the thrust check is skipped.
    persist : bool
        Whether to write the result to regime_state.json.
    """
    if not is_internet_available():
        logger.warning("[market_regime] Internet offline: returning last computed regime from state.")
        state = _load_state()
        if "last" in state:
            return state["last"]
        return {"score": 0, "verdict": "UNAVAILABLE", "details": "Internet offline and no persisted state"}

    df_bench = _fetch_benchmark(period="1y")
    if df_bench.empty:
        return {"score": 0, "verdict": "UNAVAILABLE",
                 "details": "benchmark download failed"}

    close = df_bench["Close"]
    sma50  = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    last      = float(close.iloc[-1])
    s50_now   = float(sma50.iloc[-1])  if len(close) >= 50  else float("nan")
    s200_now  = float(sma200.iloc[-1]) if len(close) >= 200 else float("nan")
    s200_5d   = float(sma200.iloc[-6]) if len(close) >= 206 else float("nan")
    above_s200 = bool(last > s200_now) if not np.isnan(s200_now) else False
    s200_rising = bool(s200_now > s200_5d) if not (np.isnan(s200_now) or np.isnan(s200_5d)) else False
    death_cross = bool(s50_now < s200_now) if not (np.isnan(s50_now) or np.isnan(s200_now)) else False

    dd  = compute_distribution_days(df_bench)
    ft  = detect_follow_through(df_bench)
    bt  = (detect_breadth_thrust(ad_history) if ad_history is not None
            and not ad_history.empty else {"active": False, "details": "ad_history not provided"})

    # Build score
    score = 0
    components = {}
    components["above_sma200_rising"] = above_s200 and s200_rising
    if components["above_sma200_rising"]:
        score += 3

    breadth_above_50 = False
    if breadth_metrics:
        breadth_above_50 = (breadth_metrics.get("above_sma200_pct", 0) >= 50)
        if breadth_above_50:
            score += 2
    components["breadth_above_50"] = breadth_above_50

    components["dd_low"] = (not dd["stress"]) and dd["count"] <= 3
    if components["dd_low"]:
        score += 2

    components["no_death_cross"] = not death_cross
    if components["no_death_cross"]:
        score += 1

    components["follow_through"] = bool(ft.get("active"))
    if components["follow_through"]:
        score += 1

    components["breadth_thrust"] = bool(bt.get("active"))
    if components["breadth_thrust"]:
        score += 1

    score = min(score, 10)
    verdict = _verdict(score)

    out = {
        "score":        score,
        "verdict":       verdict,
        "computed_at":   datetime.now().isoformat(timespec="seconds"),
        "benchmark":     BENCHMARK_YF,
        "close":         round(last, 2),
        "sma50":         round(s50_now, 2)  if not np.isnan(s50_now)  else None,
        "sma200":        round(s200_now, 2) if not np.isnan(s200_now) else None,
        "above_sma200":  above_s200,
        "sma200_rising": s200_rising,
        "death_cross":   death_cross,
        "distribution":  dd,
        "follow_through": ft,
        "breadth_thrust": bt,
        "breadth_above_sma200_pct": (breadth_metrics or {}).get("above_sma200_pct"),
        "components":    components,
    }
    if persist:
        state = _load_state()
        state["last"] = out
        history = state.get("history", [])
        # Keep last 60 daily snapshots keyed by date
        today = datetime.now().date().isoformat()
        history = [h for h in history if h.get("date") != today]
        history.append({"date": today, "score": score, "verdict": verdict})
        state["history"] = history[-60:]
        _save_state(state)
    return out


# ─── Convenience entrypoint ───────────────────────────────────────────────────
def main() -> int:
    print("=" * 60)
    print("  COMMANDER MARKET REGIME ENGINE  v1.0")
    print("=" * 60)
    try:
        # Optional breadth integration if breadth_engine is importable
        try:
            import breadth_engine as be
            metrics = be.calculate_breadth_metrics()
            ad_hist = be.load_or_bootstrap_ad_history()
        except Exception as e:
            print(f"  [warn] breadth_engine unavailable: {e}")
            metrics, ad_hist = None, None

        result = compute_regime(metrics, ad_hist)
        print(f"\n  SCORE: {result['score']}/10  -  {result['verdict']}")
        print(f"  Benchmark: {BENCHMARK_YF}  Close: {result['close']}  "
              f"SMA200: {result['sma200']}  rising={result['sma200_rising']}")
        print(f"  Distribution Days: {result['distribution']['count']} of "
              f"{result['distribution']['window']}  "
              f"(stress={result['distribution']['stress']})")
        print(f"  Follow-Through: {result['follow_through']['details']}")
        print(f"  Breadth Thrust: {result['breadth_thrust']['details']}")
        print(f"\n  State persisted to {STATE_PATH}")
    except Exception as e:
        print(f"  ERROR: {e}")
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
