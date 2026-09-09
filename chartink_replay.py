"""
chartink_replay.py — Python port of the 4 bull Chartink scans.

Why: today's `FINAL_*.csv` watchlists are matcher output anchored to today's
Chartink + Screener.in run. For honest historical validation we need
versions of those watchlists *as they would have stood* on each anchor date.
Chartink doesn't archive its CSVs, so we reproduce the scan logic in Python
against a pinned `data_provider`.

Each scan is a predicate function that returns True if a symbol qualifies as
of `data_provider`'s currently-pinned date. The predicates use the same TA
primitives the bull_screener already computes (SMA/EMA/RSI/ADX/MACD/Volume).

Public API:
  qualifies_hunter(symbol)          -> bool
  qualifies_pullback(symbol)        -> bool
  qualifies_early_birds(symbol)     -> bool
  qualifies_strong_leaders(symbol)  -> bool

  run_scan(scan_name, universe)     -> list[str]
  run_all_bull_scans(universe)      -> dict[str, list[str]]
  combined_bull_universe(universe)  -> list[str]

Reference: chartink_scanner_pro.SCAN_CATALOG  (scans 1-4 ported here).
"""

from __future__ import annotations

import logging
import warnings
from typing import Optional

import numpy as np
import pandas as pd

import data_provider as _dp


warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)


# ─── Tunable parameters per scan (overrideable for sweeps) ────────────────────
# To sweep: chartink_replay.SCAN_PARAMS["hunter"]["weekly_rsi_min"] = 50
# Each predicate reads from this dict at call-time, so changes take effect
# immediately on the next scan call.
#
# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║ v2 FINAL CONFIG — LOCKED 2026-05-10                                       ║
# ║                                                                           ║
# ║ Backtest path: chartink_replay → matcher conviction (>=6.0) → bull_screen ║
# ║ Universe:      Nifty 500 base, ~23 names per anchor after both filters    ║
# ║ Anchors:       12 monthly (2025-04-15 → 2026-03-16), 30-day fwd window    ║
# ║                                                                           ║
# ║ Aggregate (filtered, Run ID 20260508_224037):                             ║
# ║   alpha 4.63%, hit-rate 83.3% (10/12), winrate 60.0%, median α 5.00       ║
# ║ Baseline (v1 FINAL filtered, Run ID 20260508_214659):                     ║
# ║   alpha 4.37%, hit-rate 83.3%, winrate 59.2%, median α 4.68               ║
# ║                                                                           ║
# ║ Hunter / EarlyBirds parameters: UNCHANGED from v1 FINAL (already locked). ║
# ║ The v2 lock is a single behavioral change in the Score pipeline:          ║
# ║   v2_fixes.V2_FLAGS["pos_accum_rsi_nullout"] = True                       ║
# ║     (POS-ACCUM catalyst score → 0 when daily RSI > 50)                    ║
# ║                                                                           ║
# ║ v1 FINAL CONFIG (PRESERVED — locked 2026-05-08, Run ID 20260508_105114):  ║
# ║   alpha 4.45%, hit-rate 91.7%, winrate 61.7%                              ║
# ║   hunter.weekly_rsi_min:   55 → 60                                        ║
# ║   hunter.daily_adx_min:    20 → 25                                        ║
# ║   early_birds.disable_rsi: False → True                                   ║
# ║                                                                           ║
# ║ v2 promotion verdict: only fix that lifted alpha while holding hit-rate   ║
# ║ on BOTH the raw and filtered universes (cross-universe verification).     ║
# ║ Other 4 candidates rejected; days_since_pivot_penalty kept as runtime     ║
# ║ defensive-mode flag.                                                      ║
# ║                                                                           ║
# ║ Source: BACKTEST_RESULTS_v2.docx; validation_runs/v2_ablation_results.csv ║
# ║         + v2_ablation_filtered_results.csv                                ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
SCAN_PARAMS: dict[str, dict[str, float]] = {
    "hunter": {
        "weekly_rsi_min":     60,    # v1 LOCKED (was 55) — weekly RSI threshold
        "daily_adx_min":      25,    # v1 LOCKED (was 20) — daily ADX threshold
        "price_floor":        20,    # weekly close floor
        "high52_proximity":   0.85,  # within 1-x of 52W high
        "structural_only":    False, # bulk: skip RSI + ADX gates
        "disable_rsi":        False, # fine: skip only RSI gate
        "disable_adx":        False, # fine: skip only ADX gate
    },
    "pullback": {
        "weekly_rsi_min":     55,    # production (ablation: no incremental alpha)
        "ema20_proximity":    1.015, # daily low within (x-1) of EMA20
        "price_floor":        20,
        "structural_only":    False,
        "disable_rsi":        False,
    },
    "early_birds": {
        "weekly_rsi_min":     50,    # lagging
        "sma50_max_extension": 1.15, # close < 50D SMA × x
        "min_volume":          100_000,
        "price_floor":        20,
        "structural_only":    False,
        "disable_rsi":        True,  # v1 LOCKED (was False) — RSI gate redundant w/ Stage 2 + breakout logic
        "disable_macd":       False, # fine: skip only MACD gate
    },
    "strong_leaders": {
        "daily_rsi_min":      60,    # lagging
        "daily_adx_min":      25,    # lagging
        "price_floor":        20,
        "structural_only":    False,
        "disable_rsi":        False,
        "disable_adx":        False,
    },
}

# Version metadata — bump on every locked-config change.
SCAN_PARAMS_VERSION = "v2_FINAL_20260510"


def get_param(scan: str, key: str) -> float:
    """Read the current tunable parameter (with fallback to default)."""
    return SCAN_PARAMS.get(scan, {}).get(key, 0)


# ─── Common helpers ──────────────────────────────────────────────────────────
def _fetch(symbol: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (daily, weekly) frames pinned to the current data_provider state.
    Both are flat-columned with OHLCV columns. Empty frames on failure."""
    df_d = _dp.fetch_ohlcv(symbol, period="2y", interval="1d")
    df_w = _dp.fetch_ohlcv(symbol, period="3y", interval="1wk")
    return df_d, df_w


def _last_value(s: pd.Series) -> float:
    """Last non-NaN value or NaN."""
    if s is None or len(s) == 0:
        return float("nan")
    val = s.iloc[-1]
    if pd.isna(val):
        return float("nan")
    return float(val)


def _rsi(series: pd.Series, n: int = 14) -> pd.Series:
    """Wilder's RSI — uses RMA (Wilder's smoothing) which is what Chartink
    and TradingView use by default. RMA = ewm(alpha=1/n, adjust=False)."""
    d = series.diff()
    g = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + g / l.replace(0, np.nan))


def _adx(h: pd.Series, l: pd.Series, c: pd.Series, n: int = 14) -> pd.Series:
    up = h - h.shift(1)
    dn = l.shift(1) - l
    pos_dm = np.where((up > dn) & (up > 0), up, 0.0)
    neg_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    tr_smooth = tr.rolling(n).sum().replace(0, np.nan)
    plus_di  = 100 * pd.Series(pos_dm, index=c.index).rolling(n).sum() / tr_smooth
    minus_di = 100 * pd.Series(neg_dm, index=c.index).rolling(n).sum() / tr_smooth
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.rolling(n).mean()


def _macd(close: pd.Series, slow: int = 26, fast: int = 12, signal: int = 9
           ) -> tuple[pd.Series, pd.Series]:
    """Returns (macd_line, signal_line). Chartink notation
    `macd line(26, 12, 9)` means slow=26, fast=12, signal=9."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


# ─── Pure price-action equivalents for lagging-oscillator gates ──────────────
def _position_in_range(close: pd.Series, high: pd.Series, low: pd.Series,
                          n: int = 14) -> float:
    """Replacement for RSI(N) ≥ X. Returns last close's position within the
    N-bar range as 0..1. Pure price action — no smoothing.

    A stock with RSI > 55 (bullish momentum) typically has its close in the
    upper half of its recent range; PIR ≥ 0.55 captures the same intent
    without Wilder smoothing or lookback drift.
    """
    if len(close) < n + 1:
        return float("nan")
    h_n = float(high.iloc[-n:].max())
    l_n = float(low.iloc[-n:].min())
    c   = float(close.iloc[-1])
    if h_n <= l_n:
        return float("nan")
    return (c - l_n) / (h_n - l_n)


def _efficiency_ratio(close: pd.Series, n: int = 14) -> float:
    """Replacement for ADX(N) ≥ X. Kaufman's Efficiency Ratio: net price
    movement divided by total path. Returns 0..1. Pure price action.

    ADX > 20 ≈ moderately trending; ER ≈ 0.30. ADX > 25 ≈ strongly trending;
    ER ≈ 0.40. Cannot be gamed by oscillator smoothing artifacts.
    """
    if len(close) < n + 1:
        return float("nan")
    c    = close.iloc[-(n + 1):]
    net  = abs(float(c.iloc[-1]) - float(c.iloc[0]))
    path = float(c.diff().abs().sum())
    if path == 0:
        return float("nan")
    return net / path


def _regime_flip_up(close: pd.Series, ma: pd.Series, lookback: int = 5) -> bool:
    """Replacement for `macd_line > signal AND prev_signal < 0`. Detects a
    fresh re-cross above a moving average after spending part of the recent
    window below it. Pure price action with MA structure.

    Returns True iff: close > MA today AND close < MA on at least one of the
    prior `lookback` bars. Captures the same "regime flip" intent as MACD
    crossing its signal after a bearish stretch.
    """
    if len(close) < lookback + 2 or len(ma) < lookback + 2:
        return False
    if pd.isna(ma.iloc[-1]) or close.iloc[-1] <= ma.iloc[-1]:
        return False
    window_close = close.iloc[-(lookback + 1):-1]
    window_ma    = ma.iloc[-(lookback + 1):-1]
    return bool((window_close < window_ma).any())


# ─── Scan 1: Stage 2 Hunter (Positional) ─────────────────────────────────────
def qualifies_hunter(symbol: str) -> bool:
    """Stage 2 Hunter: 30W-MA rising + full trend template + within 15% of
    52W high + EMA20 + weekly RSI > 55 + ADX > 20 + price > ₹20 + above 200D
    SMA + weekly volume above 20W avg.

    All conditions evaluated as-of the currently-pinned date.
    """
    df_d, df_w = _fetch(symbol)
    if df_d.empty or len(df_d) < 200 or df_w.empty or len(df_w) < 35:
        return False

    c_d = df_d["Close"].astype(float)
    h_d = df_d["High"].astype(float)
    l_d = df_d["Low"].astype(float)
    v_d = df_d["Volume"].astype(float)

    c_w = df_w["Close"].astype(float)
    h_w = df_w["High"].astype(float)
    v_w = df_w["Volume"].astype(float)

    # Daily SMAs
    sma50_d   = c_d.rolling(50).mean()
    sma150_d  = c_d.rolling(150).mean()
    sma200_d  = c_d.rolling(200).mean()
    ema20_d   = c_d.ewm(span=20, adjust=False).mean()

    # Weekly indicators
    sma30_w   = c_w.rolling(30).mean()
    rsi14_w   = _rsi(c_w, 14)
    vol_sma20_w = v_w.rolling(20).mean()
    high52_w  = h_w.rolling(52).max()

    # Latest values
    c_d_last  = _last_value(c_d)
    sma50_last  = _last_value(sma50_d)
    sma150_last = _last_value(sma150_d)
    sma200_last = _last_value(sma200_d)
    ema20_last  = _last_value(ema20_d)

    c_w_last  = _last_value(c_w)
    sma30_w_last     = _last_value(sma30_w)
    sma30_w_4wk_ago  = (float(sma30_w.iloc[-5]) if len(sma30_w.dropna()) >= 5 else float("nan"))
    rsi14_w_last     = _last_value(rsi14_w)
    high52_w_last    = _last_value(high52_w)
    v_w_last         = _last_value(v_w)
    vol_sma20_w_last = _last_value(vol_sma20_w)

    # Daily ADX
    adx_d = _adx(h_d, l_d, c_d, 14)
    adx_d_last = _last_value(adx_d)

    # Conditions (all must be true) — thresholds read from SCAN_PARAMS["hunter"]
    p = SCAN_PARAMS.get("hunter", {})
    structural_only = bool(p.get("structural_only", False))
    disable_rsi     = structural_only or bool(p.get("disable_rsi", False))
    disable_adx     = structural_only or bool(p.get("disable_adx", False))
    try:
        # Structural / price-action gates
        structural = (
            sma30_w_last > sma30_w_4wk_ago and                                 # 30W MA rising
            sma50_last > sma150_last and                                        # Trend template: 50D > 150D
            sma150_last > sma200_last and                                       # Trend template: 150D > 200D
            c_w_last > sma30_w_last and                                          # Price > 30W MA
            c_w_last > high52_w_last * get_param("hunter", "high52_proximity") and
            c_d_last > ema20_last and                                            # Price > EMA20
            c_w_last > get_param("hunter", "price_floor") and
            c_d_last > sma200_last and                                           # Above 200D SMA
            v_w_last > vol_sma20_w_last                                          # Volume floor
        )
        # Lagging-indicator gates (each individually skippable)
        rsi_ok = disable_rsi or (rsi14_w_last > get_param("hunter", "weekly_rsi_min"))
        adx_ok = disable_adx or (adx_d_last    > get_param("hunter", "daily_adx_min"))
        cond = structural and rsi_ok and adx_ok
    except Exception:
        return False
    return bool(cond)


# ─── Scan 2: Stage 2 Pullback (Swing) ────────────────────────────────────────
def qualifies_pullback(symbol: str) -> bool:
    """Stage 2 Pullback: weekly close > 30W MA + weekly RSI > 55 + daily low
    within 1.5% of EMA20 + close > EMA20 + volume below 10D avg + close >
    200D SMA + inside-bar today vs yesterday + price > ₹20.
    """
    df_d, df_w = _fetch(symbol)
    if df_d.empty or len(df_d) < 200 or df_w.empty or len(df_w) < 30:
        return False

    c_d = df_d["Close"].astype(float)
    h_d = df_d["High"].astype(float)
    l_d = df_d["Low"].astype(float)
    v_d = df_d["Volume"].astype(float)
    c_w = df_w["Close"].astype(float)

    # Indicators
    ema20_d   = c_d.ewm(span=20, adjust=False).mean()
    sma200_d  = c_d.rolling(200).mean()
    vol_sma10_d = v_d.rolling(10).mean()
    sma30_w   = c_w.rolling(30).mean()
    rsi14_w   = _rsi(c_w, 14)

    # Latest values
    c_d_last   = _last_value(c_d)
    h_d_last   = _last_value(h_d)
    l_d_last   = _last_value(l_d)
    v_d_last   = _last_value(v_d)
    ema20_last = _last_value(ema20_d)
    sma200_last = _last_value(sma200_d)
    vol_sma10_last = _last_value(vol_sma10_d)
    rsi14_w_last = _last_value(rsi14_w)
    c_w_last   = _last_value(c_w)
    sma30_w_last = _last_value(sma30_w)

    # 1-day-ago values
    if len(df_d) < 2:
        return False
    h_d_prev = float(h_d.iloc[-2])
    l_d_prev = float(l_d.iloc[-2])

    p = SCAN_PARAMS.get("pullback", {})
    structural_only = bool(p.get("structural_only", False))
    disable_rsi     = structural_only or bool(p.get("disable_rsi", False))
    try:
        # Structural / price-action gates
        structural = (
            c_w_last > sma30_w_last and                                          # weekly close > 30W MA
            l_d_last < ema20_last * get_param("pullback", "ema20_proximity") and # daily low near EMA20
            c_d_last > ema20_last and                                             # close > EMA20
            v_d_last < vol_sma10_last and                                         # volume drying up
            c_d_last > sma200_last and                                            # above 200D SMA
            (h_d_last - l_d_last) < (h_d_prev - l_d_prev) and                     # inside bar
            c_d_last > get_param("pullback", "price_floor")                       # anti-penny
        )
        rsi_ok = disable_rsi or (rsi14_w_last > get_param("pullback", "weekly_rsi_min"))
        cond = structural and rsi_ok
    except Exception:
        return False
    return bool(cond)


# ─── Scan 3: Early Birds (Accumulation) ──────────────────────────────────────
def qualifies_early_birds(symbol: str) -> bool:
    """Early Birds: weekly RSI > 50 + close > 50D SMA but < SMA*1.15 + daily
    volume > 100k + weekly MACD bullish (line > signal AND prior week's
    signal was negative) + close above 20D high + price > ₹20.
    """
    df_d, df_w = _fetch(symbol)
    if df_d.empty or len(df_d) < 60 or df_w.empty or len(df_w) < 30:
        return False

    c_d = df_d["Close"].astype(float)
    h_d = df_d["High"].astype(float)
    v_d = df_d["Volume"].astype(float)
    c_w = df_w["Close"].astype(float)

    sma50_d  = c_d.rolling(50).mean()
    rsi14_w  = _rsi(c_w, 14)
    macd_w, sig_w = _macd(c_w, slow=26, fast=12, signal=9)

    c_d_last  = _last_value(c_d)
    sma50_last = _last_value(sma50_d)
    v_d_last  = _last_value(v_d)
    rsi14_w_last = _last_value(rsi14_w)
    macd_w_last  = _last_value(macd_w)
    sig_w_last   = _last_value(sig_w)
    sig_w_prev   = (float(sig_w.iloc[-2]) if len(sig_w.dropna()) >= 2 else float("nan"))

    # 1-day-ago: highest high of last 20 days BEFORE today
    if len(df_d) < 21:
        return False
    high20_yesterday = float(h_d.iloc[-21:-1].max())

    p = SCAN_PARAMS.get("early_birds", {})
    structural_only = bool(p.get("structural_only", False))
    disable_rsi     = structural_only or bool(p.get("disable_rsi", False))
    disable_macd    = structural_only or bool(p.get("disable_macd", False))
    try:
        # Structural / price-action gates
        structural = (
            c_d_last > sma50_last and                                              # above 50D SMA
            c_d_last < sma50_last * get_param("early_birds", "sma50_max_extension") and
            v_d_last > get_param("early_birds", "min_volume") and                  # liquidity floor
            c_d_last > high20_yesterday and                                         # breakout above 20D high
            c_d_last > get_param("early_birds", "price_floor")                      # anti-penny
        )
        rsi_ok  = disable_rsi  or (rsi14_w_last > get_param("early_birds", "weekly_rsi_min"))
        macd_ok = disable_macd or (macd_w_last > sig_w_last and sig_w_prev < 0)
        cond = structural and rsi_ok and macd_ok
    except Exception:
        return False
    return bool(cond)


# ─── Scan 4: Strong Leaders (Momentum) ───────────────────────────────────────
def qualifies_strong_leaders(symbol: str) -> bool:
    """Strong Leaders: daily RSI > 60 + close > 20D SMA + ADX > 25 + volume
    above 20D avg + close > 200D SMA + price > ₹20.
    """
    df_d, _ = _fetch(symbol)
    if df_d.empty or len(df_d) < 200:
        return False

    c_d = df_d["Close"].astype(float)
    h_d = df_d["High"].astype(float)
    l_d = df_d["Low"].astype(float)
    v_d = df_d["Volume"].astype(float)

    sma20_d   = c_d.rolling(20).mean()
    sma200_d  = c_d.rolling(200).mean()
    rsi14_d   = _rsi(c_d, 14)
    adx_d     = _adx(h_d, l_d, c_d, 14)
    vol_sma20_d = v_d.rolling(20).mean()

    c_d_last      = _last_value(c_d)
    sma20_last    = _last_value(sma20_d)
    sma200_last   = _last_value(sma200_d)
    rsi14_d_last  = _last_value(rsi14_d)
    adx_d_last    = _last_value(adx_d)
    v_d_last      = _last_value(v_d)
    vol_sma20_last = _last_value(vol_sma20_d)

    p = SCAN_PARAMS.get("strong_leaders", {})
    structural_only = bool(p.get("structural_only", False))
    disable_rsi     = structural_only or bool(p.get("disable_rsi", False))
    disable_adx     = structural_only or bool(p.get("disable_adx", False))
    try:
        # Structural / price-action gates
        structural = (
            c_d_last > sma20_last and                                              # above 20D SMA
            v_d_last > vol_sma20_last and                                           # volume confirmation
            c_d_last > sma200_last and                                              # above 200D SMA
            c_d_last > get_param("strong_leaders", "price_floor")                   # anti-penny
        )
        rsi_ok = disable_rsi or (rsi14_d_last > get_param("strong_leaders", "daily_rsi_min"))
        adx_ok = disable_adx or (adx_d_last   > get_param("strong_leaders", "daily_adx_min"))
        cond = structural and rsi_ok and adx_ok
    except Exception:
        return False
    return bool(cond)


# ─── Orchestrators ───────────────────────────────────────────────────────────
SCAN_REGISTRY = {
    "hunter":          qualifies_hunter,
    "pullback":        qualifies_pullback,
    "early_birds":     qualifies_early_birds,
    "strong_leaders":  qualifies_strong_leaders,
}


def run_scan(scan_name: str, universe: list[str]) -> list[str]:
    """Apply a scan predicate to every symbol; return qualifiers."""
    if scan_name not in SCAN_REGISTRY:
        raise ValueError(f"unknown scan {scan_name!r}; "
                          f"valid: {list(SCAN_REGISTRY)}")
    pred = SCAN_REGISTRY[scan_name]
    out = []
    for sym in universe:
        try:
            if pred(sym):
                out.append(sym)
        except Exception as e:
            logger.debug("scan %s failed for %s: %s", scan_name, sym, e)
            continue
    return out


def run_all_bull_scans(universe: list[str]) -> dict[str, list[str]]:
    """Run all 4 bull scans. Returns {scan_name: [qualifiers]}."""
    return {name: run_scan(name, universe) for name in SCAN_REGISTRY}


def combined_bull_universe(universe: list[str]) -> list[str]:
    """Union of all 4 bull scans (deduplicated, stable order)."""
    all_results = run_all_bull_scans(universe)
    seen, out = set(), []
    for syms in all_results.values():
        for s in syms:
            if s not in seen:
                seen.add(s); out.append(s)
    return out


__all__ = [
    "qualifies_hunter", "qualifies_pullback",
    "qualifies_early_birds", "qualifies_strong_leaders",
    "run_scan", "run_all_bull_scans", "combined_bull_universe",
    "SCAN_REGISTRY",
]


if __name__ == "__main__":
    # Smoke test: run today's universe, count qualifiers per scan.
    import sys, time
    if hasattr(sys.stdout, "encoding") and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try: sys.stdout.reconfigure(encoding="utf-8")
        except Exception: pass

    import validation as _v
    universe = _v.default_universe("nifty500")
    print(f"Universe: {len(universe)} symbols")

    for scan_name in SCAN_REGISTRY:
        t0 = time.time()
        results = run_scan(scan_name, universe[:50])  # first 50 for smoke
        print(f"  {scan_name:<16} on first 50: {len(results)} qualifiers  "
              f"({time.time()-t0:.1f}s)  sample: {results[:5]}")
