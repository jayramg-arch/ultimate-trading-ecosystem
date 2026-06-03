#!/usr/bin/env python3
"""
bull_screener.py : Commander Bull Market Screener  v1.1
Implements 6 catalysts from Pine Strategy v4.52 (canonical) /
Commander_Screener_Beta_Edition_v2.5.pine
Input: FINAL_COMBINED_BULL_PICKS.csv
Output: Bull_Screener_Results.csv
Benchmark: ^CRSLDX (weekly + daily)

CHANGELOG v1.1 (May-2026) — Align with Pine Unified Ecosystem v2.3 (5 fixes)
    Resolves: "Auto-Pilot watchlist stocks show no catalyst signals on chart"
    1. mkt_bull gate: SWG-* catalysts now require CNX500 close > SMA200 AND
       SMA50 > SMA200 (Pine v2.3 line 1022). Without this, ALL swing catalysts
       were passing in Python while being suppressed in Pine.
    2. vol_acc_ok: aligned with Pine's 20-bar institutional accumulation density
       (green close + above-avg volume + close in upper 60% of range). Was a
       simpler 10-bar volume-only check that passed non-institutional bars.
    3. bb_sqz_ok: BB width SMA lookback 120 -> 30 bars (Pine v2.3 line 1088).
    4. stage1_base: weinstein_setup now accepts stage 1 OR 2 (was stage 2 only).
       Pine v2.3 line 1096: (stage2_uptrend or stage1_base).
    5. Daily benchmark fetch: run_bull_screener() now fetches CNX500 daily data
       alongside weekly for the mkt_bull regime gate. Cached once per run.

CHANGELOG v1.0 (Apr-2026) — Sync with Pine Strategy v4.52 (9 fixes)
    1. Catalyst priority cascade INVERTED to match Pine v4.52 order:
       POS-BO -> POS-ACCUM -> SWG-GAP -> SWG-BO -> SWG-PB -> SWG-REV
       (Pine evaluates positional first, swing second; we mirror that.)
    2. VCP definition replaced with canonical Pine v4.52 (line 672-677) /
       Beta v2.4 (line 238): ATR(10) < ATR-SMA50 * 1.5 AND VWMA(vol,5) <
       SMA(vol,50). Replaces the loose "range5 < range10 * 0.8" proxy.
    3. weinstein_setup rebuilt from 2 gates -> 9 gates per Pine v4.52 line 937:
       stage2 + trend_aligned + rs_ok + sector_stage_ok + vol_acc_ok +
       stage2_fresh_ok + ma_sqz_ok + bb_sqz_ok + trend_template_ok.
       sector_stage_ok defaults True (no sector data in Python pipeline).
    4. minervini_trend stripped to canonical trend stack only (Pine v4.52
       line 969). 52H/52L checks moved into trend_template_ok.
    5. Trend-template floor 25% -> 30% (Pine min_dist_52L = 0.30).
    6. POS-ACCUM OBV gate upgraded from "obv > obv_ema(20)" to 13-bar
       linreg slope-rising test (Pine v4.52 lines 947-949).
    7. POS-BO `intraday_pos > 0.75` extra constraint dropped — not in Pine.
    8. Score scale 0-20 -> 0-100. Components rebalanced (see compute_score
       docstring for the full breakdown summing to 100).
    9. CSV schema aligned with recovery_screener v1.3 conventions:
         - Mansfield -> Mansfield_RS_x100 (textbook RRG scale)
         - Added RS_Momentum_4W (4-week diff of Mansfield)
         - Added RRG_Quadrant (LEADING / WEAKENING / LAGGING / IMPROVING)
   10. Mansfield warm-up strengthened: requires >= 52 weekly bars before
       trusting the value (was 27). 27 weeks gives only 1 SMA26 sample —
       gives an unreliable Mansfield. 52 = 26 SMA + 26 trail = stable.
"""

import os
import time
import logging
import warnings
from collections import Counter
from typing import Optional
import numpy as np
import pandas as pd
import yfinance as yf

# v2.4 sync diagnostic — funnel counter per gate per catalyst.
# Reset at start of each run; printed after the screening loop completes.
# Tells you exactly where the catalyst funnel collapses.
FUNNEL = Counter()

logging.getLogger("yfinance").setLevel(logging.CRITICAL)
warnings.filterwarnings("ignore")

# C1: route OHLCV through the unified data_provider when available.
# Set USE_DATA_PROVIDER=False (or remove the import) to fall back to direct
# yfinance calls if the parquet cache is misbehaving.
try:
    import data_provider as _dp
    USE_DATA_PROVIDER = True
except Exception:
    _dp = None
    USE_DATA_PROVIDER = False

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = "FINAL_COMBINED_BULL_PICKS.csv"
OUTPUT_FILE = "Bull_Screener_Results.csv"
BENCHMARK_YF = "^CRSLDX"

CONFIG = {
    "min_turnover_cr": 5.0,
    "alpha_gate": 60,
    "data_lookback_days": 400,
    "download_delay_sec": 0.0
}

def to_yf(symbol: str) -> str:
    s = str(symbol).strip().upper()
    return s if s.startswith("^") else f"{s}.NS"

def _flatten_cols(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def compute_atr(h: pd.Series, l: pd.Series, c: pd.Series, n: int) -> pd.Series:
    """True-range ATR(n) using Wilder's RMA (EMA with alpha=1/n) for TradingView parity."""
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0/n, min_periods=n, adjust=False).mean()


def compute_swing_momentum(df: pd.DataFrame, pivot_len: int = 2, atr_n: int = 14) -> dict:
    """B11 back-port — Python parity for the Wesinstein Swing Zigzag [Strict v6.2] panel.

    Mirrors the Pine engine's swing accounting on daily OHLCV so the same momentum
    reads (I:C ratio, leg velocity, EMA20 distance in ATR units) are available in
    the screener output as CSV columns. Zero signal drift goal: pivot semantics
    match Pine `ta.pivothigh(left, right)` / `ta.pivotlow(low, left, right)` with
    `left = right = pivot_len` (default 2 = the user's Daily setting).

    A bar B is a pivot high if `high[B]` is strictly the max of
    `high[B-pivot_len .. B+pivot_len]`. Confirmation therefore lags by
    `pivot_len` bars — same as Pine.

    Returns:
        dict with keys:
            swing_pct_current : % range of the currently developing leg
            swing_pct_prev    : % range of the most-recently-completed leg
            ic_ratio          : swing_pct_current / swing_pct_prev
            leg_vel_pct       : %/bar on the current developing leg
            prev_leg_vel_pct  : %/bar on the previous completed leg
            vel_accel         : "UP" / "FLAT" / "DOWN" vs prev_leg_vel (±10% bands)
            ema20_dist_atr    : (close - EMA20) / ATR(atr_n), signed
            active_dir        : "UP" or "DOWN" — direction of the developing leg
        All numerics return np.nan when insufficient history.
    """
    out = {"swing_pct_current": np.nan, "swing_pct_prev": np.nan,
           "ic_ratio": np.nan, "leg_vel_pct": np.nan, "prev_leg_vel_pct": np.nan,
           "vel_accel": "n/a", "ema20_dist_atr": np.nan, "active_dir": "n/a"}
    if df is None or len(df) < max(50, pivot_len * 6):
        return out

    h = df["High"].values
    l = df["Low"].values
    c = df["Close"].values
    n = len(df)
    L = pivot_len

    # Detect pivots — strict max/min over [B-L .. B+L]. Pivot is "confirmed" only
    # once L bars on the right have printed, so on the live (last) bar the most
    # recent confirmable pivot is at index n-1-L.
    piv_h_idx, piv_h_px = [], []
    piv_l_idx, piv_l_px = [], []
    for b in range(L, n - L):
        win_h = h[b - L:b + L + 1]
        win_l = l[b - L:b + L + 1]
        if h[b] == win_h.max() and (win_h == h[b]).sum() == 1:
            piv_h_idx.append(b); piv_h_px.append(h[b])
        if l[b] == win_l.min() and (win_l == l[b]).sum() == 1:
            piv_l_idx.append(b); piv_l_px.append(l[b])

    if not piv_h_idx or not piv_l_idx:
        # Still compute EMA20/ATR distance if we have enough bars
        pass
    else:
        # Build a zigzag — alternating H/L by chronological order, keeping the most
        # extreme pivot in any run of same-type pivots between opposite-type ones.
        merged = sorted(
            [(i, p, "H") for i, p in zip(piv_h_idx, piv_h_px)] +
            [(i, p, "L") for i, p in zip(piv_l_idx, piv_l_px)],
            key=lambda x: x[0]
        )
        zz = []  # list of (idx, price, type)
        for idx, px, typ in merged:
            if not zz:
                zz.append((idx, px, typ)); continue
            if zz[-1][2] == typ:
                # Same type — keep the more extreme one (max for H, min for L)
                if (typ == "H" and px > zz[-1][1]) or (typ == "L" and px < zz[-1][1]):
                    zz[-1] = (idx, px, typ)
            else:
                zz.append((idx, px, typ))

        if len(zz) >= 2:
            last_idx, last_px, last_typ = zz[-1]
            # Current developing leg: from the last locked pivot to NOW.
            cur_close = float(c[-1])
            if last_typ == "L":
                # Last pivot is a low → developing UP leg
                cur_pct  = (cur_close - last_px) / last_px * 100 if last_px > 0 else np.nan
                cur_dir  = "UP"
            else:
                # Last pivot is a high → developing DOWN leg
                cur_pct  = (last_px - cur_close) / cur_close * 100 if cur_close > 0 else np.nan
                cur_dir  = "DOWN"
            cur_bars = max(1, (n - 1) - last_idx)
            out["swing_pct_current"] = float(cur_pct) if not np.isnan(cur_pct) else np.nan
            out["leg_vel_pct"]       = float(cur_pct / cur_bars) if not np.isnan(cur_pct) else np.nan
            out["active_dir"]        = cur_dir

            # Previous completed leg: between zz[-2] and zz[-1] (both locked pivots).
            prev_idx, prev_px, prev_typ = zz[-2]
            if prev_typ == "L" and last_typ == "H":
                prev_pct = (last_px - prev_px) / prev_px * 100 if prev_px > 0 else np.nan
            elif prev_typ == "H" and last_typ == "L":
                prev_pct = (prev_px - last_px) / last_px * 100 if last_px > 0 else np.nan
            else:
                prev_pct = np.nan
            prev_bars = max(1, last_idx - prev_idx)
            out["swing_pct_prev"]    = float(prev_pct) if not np.isnan(prev_pct) else np.nan
            out["prev_leg_vel_pct"]  = float(prev_pct / prev_bars) if not np.isnan(prev_pct) else np.nan

            # I:C ratio + accel arrow vs prev velocity (±10% bands match Pine)
            if not np.isnan(out["swing_pct_current"]) and not np.isnan(out["swing_pct_prev"]) and out["swing_pct_prev"] > 0:
                out["ic_ratio"] = round(out["swing_pct_current"] / out["swing_pct_prev"], 2)
            if not np.isnan(out["leg_vel_pct"]) and not np.isnan(out["prev_leg_vel_pct"]) and out["prev_leg_vel_pct"] > 0:
                ratio = out["leg_vel_pct"] / out["prev_leg_vel_pct"]
                out["vel_accel"] = "UP" if ratio > 1.10 else "DOWN" if ratio < 0.90 else "FLAT"

    # EMA20 distance in ATR units — same formula as Pine TREND row.
    if len(df) >= max(20, atr_n + 1):
        close_s = df["Close"]
        high_s, low_s = df["High"], df["Low"]
        ema20 = close_s.ewm(span=20, adjust=False).mean().iloc[-1]
        atr   = compute_atr(high_s, low_s, close_s, atr_n).iloc[-1]
        if not np.isnan(ema20) and not np.isnan(atr) and atr > 0:
            out["ema20_dist_atr"] = round(float((close_s.iloc[-1] - ema20) / atr), 2)

    # Round leg/swing fields for CSV readability
    for k in ("swing_pct_current", "swing_pct_prev", "leg_vel_pct", "prev_leg_vel_pct"):
        if isinstance(out[k], float) and not np.isnan(out[k]):
            out[k] = round(out[k], 2)
    return out


def linreg_slope(series: pd.Series, length: int, offset: int = 0) -> float:
    """Endpoint of the linear regression line, mirroring Pine ta.linreg(src, length, offset).
    Returns the linreg ENDPOINT value (not the slope coefficient itself).
    Used to compare two endpoints (now vs offset bars back) to detect a rising trend.
    """
    end = len(series) - offset
    start = end - length
    if start < 0 or len(series) < length + offset:
        return float("nan")
    y = series.iloc[start:end].values
    if len(y) < length or np.any(np.isnan(y)):
        return float("nan")
    x = np.arange(length, dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    return float(slope * (length - 1) + intercept)  # value at last x


def compute_indicators(df: pd.DataFrame) -> dict:
    c, h, l, v, o = df["Close"], df["High"], df["Low"], df["Volume"], df["Open"]

    sma20 = c.rolling(20).mean()
    sma50 = c.rolling(50).mean()
    sma150 = c.rolling(150).mean()
    sma200 = c.rolling(200).mean()
    ema20 = c.ewm(span=20, adjust=False).mean()
    vol_ma = v.rolling(50).mean()

    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = compute_atr(h, l, c, 14)

    # VCP / squeeze inputs (Pine v4.52 lines 672-685)
    atr10        = compute_atr(h, l, c, 10)
    atr10_sma50  = atr10.rolling(50).mean()
    # VWMA(volume, 5) per Pine: Σ(v*c)/Σ(v)
    vol_vwma5    = (v * c).rolling(5).sum() / v.rolling(5).sum().replace(0, np.nan)

    # Bollinger Bands for bb_sqz_ok (window 20, 2σ)
    bb_std       = c.rolling(20).std()
    bb_upper     = sma20 + 2.0 * bb_std
    bb_lower     = sma20 - 2.0 * bb_std
    bb_width     = (bb_upper - bb_lower) / sma20.replace(0, np.nan)
    
    def _rsi(series, n):
        d = series.diff()
        g = d.clip(lower=0).rolling(n).mean()
        ls = (-d.clip(upper=0)).rolling(n).mean()
        return 100 - 100 / (1 + g / ls.replace(0, np.nan))
        
    rsi14 = _rsi(c, 14)
    rsi3 = _rsi(c, 3)
    
    # ADX/DI
    up = h - h.shift(1)
    dn = l.shift(1) - l
    pos_dm = np.where((up > dn) & (up > 0), up, 0)
    neg_dm = np.where((dn > up) & (dn > 0), dn, 0)
    tr_smooth = tr.rolling(14).sum()
    plus_di = 100 * pd.Series(pos_dm, index=c.index).rolling(14).sum() / tr_smooth
    minus_di = 100 * pd.Series(neg_dm, index=c.index).rolling(14).sum() / tr_smooth
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.rolling(14).mean()
    
    # OBV
    obv = np.where(c > c.shift(1), v, np.where(c < c.shift(1), -v, 0))
    obv = pd.Series(obv, index=c.index).cumsum()
    obv_ema = obv.ewm(span=20, adjust=False).mean()
    
    rel_vol = v / vol_ma.replace(0, np.nan)
    high52w = h.rolling(250).max()
    low52w = l.rolling(250).min()
    
    return dict(
        close=c, high=h, low=l, open=o, volume=v,
        sma20=sma20, sma50=sma50, sma150=sma150, sma200=sma200, ema20=ema20,
        vol_ma=vol_ma, atr=atr, rsi14=rsi14, rsi3=rsi3,
        plus_di=plus_di, minus_di=minus_di, adx=adx,
        obv=obv, obv_ema=obv_ema,
        rel_vol=rel_vol, high52w=high52w, low52w=low52w,
        # v1.0: VCP/squeeze inputs
        atr10=atr10, atr10_sma50=atr10_sma50, vol_vwma5=vol_vwma5,
        bb_width=bb_width
    )

def compute_weekly_indicators(df: pd.DataFrame, df_bench: pd.DataFrame) -> dict:
    """Weekly Weinstein stage + JdK RS-Ratio / RS-Momentum (Strike.Money parity).

    v1.5 (2026-05): replaced Mansfield (RS/SMA26 - 1) with the StockCharts-default
    JdK formula (2-pass normalization, length=10, no extra smoothing). Matches
    Strike.Money / StockCharts RRG conventions (100-centered).
    Field names `mansfield` and `mansfield_4w` are retained for downstream
    compatibility but now hold **JdK_RS_Ratio - 100** and **JdK_RS_Momentum - 100**
    so existing tier thresholds (>0, >=10, >0 at lines 351/556-565) keep their
    semantic meaning. Quadrant labels now match Strike.Money's RRG view.
    """
    if len(df) < 35:
        return {"stage": 0, "mansfield": 0.0, "wrsi": 0.0,
                "mansfield_4w": 0.0, "rrg_quadrant": "n/a",
                "rrg_trajectory": "n/a", "rrg_next": "n/a",
                "rrg_score": 0, "rrg_arrow": "•", "rrg_tradeable": False,
                "w_mom": False}
    c = df["Close"]
    sma30 = c.rolling(30).mean()
    slope = sma30 - sma30.shift(4)
    thresh = sma30 * 0.0005
    above = c.iloc[-1] > sma30.iloc[-1]
    sl = slope.iloc[-1]
    th = thresh.iloc[-1]
    up = sl > th
    dn = sl < -th

    stage = 0
    if up and above: stage = 2
    elif dn and not above: stage = 4
    elif not dn and above: stage = 1
    else: stage = 3

    # WRSI
    def _rsi(series, n):
        d = series.diff()
        g = d.clip(lower=0).rolling(n).mean()
        ls = (-d.clip(upper=0)).rolling(n).mean()
        return 100 - 100 / (1 + g / ls.replace(0, np.nan))
    wrsi = float(_rsi(c, 14).iloc[-1])

    # JdK RS-Ratio / RS-Momentum (textbook formula, 100-centered, double-smoothed)
    # Matches Strike.Money / StockCharts RRG. length=14 weekly bars.
    merged = pd.merge(c.rename("s"), df_bench["Close"].rename("m"),
                      left_index=True, right_index=True, how="inner")
    # Warm-up: 1-pass formula needs length(12)*3 + smooth(5) ≈ 41 bars for stable
    # values without look-ahead bias. Pine Dashboard uses math.max(jdkLen*3+10, 60).
    # Raised from 40 → 52 to match Pine warmup and prevent unreliable early values.
    if len(merged) < 52:
        mansfield = 0.0
        mansfield_4w = 0.0
        rrg = "n/a"
        rrg_traj = "n/a"
        rrg_next = "n/a"
        rrg_score = 0
        rrg_arrow = "•"
        rrg_tradeable = False
    else:
        # v1.7 (2026-05-19): Strike.Money-matched JdK formula.
        # Replaces the 2-pass "StockCharts default" — calibration against 15
        # symbols vs Strike's published values showed:
        #   2-pass (old): ratio error 8.86, quadrant agreement 66.7%
        #   1-pass + 5-bar smooth (new): ratio error 5.26, quadrant agreement 93.3%
        # Strike evidently uses single-pass normalization with longer SMA and
        # final 5-bar smoothing — NOT the textbook double-pass.
        # Parameters: length=12, single normalization, 5-bar final smooth.
        length = 12
        smooth = 5      # final smoothing on the ratio — key Strike-match parameter
        trail_len = 4   # standard RRG tail length (weeks)
        rs_raw = merged["s"] / merged["m"].replace(0, np.nan)
        # Single normalization pass (no double-pass)
        rs_raw_sma = rs_raw.rolling(length).mean()
        rs_ratio_raw = 100.0 + ((rs_raw - rs_raw_sma) / rs_raw_sma.replace(0, np.nan)) * 100.0
        # Apply 5-bar SMA on the ratio — primary Strike-match adjustment
        rs_ratio = rs_ratio_raw.rolling(smooth).mean()
        # RS-Momentum = SMA(length) of ROC of smoothed RS-Ratio
        rm1 = 100.0 * (rs_ratio / rs_ratio.shift(1).replace(0, np.nan))
        rs_mom = rm1.rolling(length).mean()

        rsr_val = float(rs_ratio.iloc[-1]) if not np.isnan(rs_ratio.iloc[-1]) else np.nan
        rsm_val = float(rs_mom.iloc[-1])   if not np.isnan(rs_mom.iloc[-1])   else np.nan

        # Store as deviation from 100 so downstream thresholds (>0, >=10) keep meaning
        mansfield    = 0.0 if np.isnan(rsr_val) else (rsr_val - 100.0)
        mansfield_4w = 0.0 if np.isnan(rsm_val) else (rsm_val - 100.0)

        # RRG quadrant — JdK convention: 100 is the centerline
        if np.isnan(rsr_val) or np.isnan(rsm_val):
            rrg = "n/a"
        elif rsr_val >= 100 and rsm_val >= 100:
            rrg = "LEADING"
        elif rsr_val >= 100 and rsm_val < 100:
            rrg = "WEAKENING"
        elif rsr_val < 100 and rsm_val < 100:
            rrg = "LAGGING"
        else:
            rrg = "IMPROVING"

        # --- Trajectory: velocity vector vs trail_len weeks ago ---
        rrg_traj, rrg_next, rrg_score, rrg_arrow, rrg_tradeable = _rrg_trajectory(
            rs_ratio, rs_mom, rrg, trail_len
        )

    # PRICE-ACTION weekly momentum (replaces weekly-RSI gate in POS-BO):
    # weekly close above its 5-week-ago close = positive 5-week momentum.
    w_mom = bool(float(c.iloc[-1]) > float(c.iloc[-6])) if len(c) > 6 else False
    return {"stage": stage, "mansfield": mansfield, "wrsi": wrsi,
            "mansfield_4w": mansfield_4w, "rrg_quadrant": rrg,
            "rrg_trajectory": rrg_traj, "rrg_next": rrg_next,
            "rrg_score": rrg_score, "rrg_arrow": rrg_arrow,
            "rrg_tradeable": rrg_tradeable, "w_mom": w_mom}


# v1.7 (2026-05-20): Re-calibrated after switch to Strike-matched 1-pass formula.
# New backtest n=5,020 (Nifty 500 × 12 anchors). Edge collapsed vs old 2-pass:
#   RS-Ratio side spread: 2.71pp → 0.93pp (5-bar smoothing damped predictive signal)
# Per-quadrant data:
#   LEADING:   +1.24% (n=1,807)   ← only quadrant with material alpha
#   IMPROVING: +0.07% (n=808)     ← flat
#   WEAKENING: +0.07% (n=491)     ← flat
#   LAGGING:   +0.06% (n=1,914)   ← flat
# Conclusion: only LEADING earns a score bonus. Old +5/-5 was over-stated.
def _rrg_score(rs_ratio_centered: float, quadrant: str = "") -> int:
    """+2 if LEADING (RS-Ratio >= 100 AND momentum >= 100), else 0.

    Data-backed (n=5,020): LEADING is the only quadrant with material edge
    (+1.24% mean alpha). WEAKENING (+0.07%) is RS-Ratio >= 100 but momentum
    falling — backtest shows it's barely positive, doesn't deserve a bonus.
    """
    return 2 if quadrant == "LEADING" else 0


# v1.7 (2026-05-20): RRG_Tradeable recalibrated on new 1-pass formula.
# Backtest n=5,020 cell-level data (lower is better; > +0.5% = green light):
#   POSITIVE cells (tradeable):
#     LEADING -> IMPROVING:  +2.92% (n=195)  ← surprise — ratio holding, momentum easing
#     LEADING (stable):      +1.50% (n=1,264) ← bread and butter
#     IMPROVING -> LEADING:  +1.17% (n=384)  ← textbook breakout — now actually works
#     LAGGING -> IMPROVING:  +0.99% (n=365)  ← turning bullish
#     WEAKENING -> LEADING:  +0.58% (n=89)   ← partial recovery (marginal)
#   NEGATIVE cells (not tradeable):
#     IMPROVING -> LAGGING:  -2.34% (n=137)  ← failed bounce
#     LEADING -> WEAKENING:  -0.63% (n=348)  ← exhausted leader (no cushion exception)
#     IMPROVING (stable):    -0.24% (n=287)  ← stagnant under 100
#     WEAKENING (stable):    -0.23% (n=154)  ← drifting
# The 5-bar smoothing destroyed the "deeper LEADING cushion = safer" gradient.
# Now: LEADING heading to WEAKENING is FALSE regardless of cushion depth.
def _rrg_tradeable(current: str, nxt: str, rs_ratio_centered: float) -> bool:
    """Boolean entry-timing gate based on cell-level backtest alpha.
    Positive-alpha cells return True; negative or near-zero return False."""
    # Trajectory-based — most reliable signal
    if current == "LEADING":
        return nxt in ("LEADING", "IMPROVING")    # stable or fading slowly = OK
    if current == "IMPROVING":
        return nxt == "LEADING"                   # only the breakout cell is +alpha
    if current == "LAGGING":
        return nxt == "IMPROVING"                 # only the turn-up cell is +alpha
    if current == "WEAKENING":
        return nxt == "LEADING"                   # only recovery cell is +alpha
    return False

def _rrg_trajectory(rs_ratio_series, rs_mom_series, current, trail_len):
    """Return (trajectory_str, next_quadrant, score, arrow, tradeable).

    - score    : binary RS-Ratio side (+5 / -5), backed by n=5,460 backtest
    - tradeable: boolean entry gate combining quadrant + trajectory + distance
                 from RS-Ratio centerline
    """
    thresh = 0.30  # noise floor (units = JdK centered scale)
    try:
        v_now = float(rs_ratio_series.iloc[-1])
        m_now = float(rs_mom_series.iloc[-1])
        v_prev = float(rs_ratio_series.iloc[-1 - trail_len])
        m_prev = float(rs_mom_series.iloc[-1 - trail_len])
    except (IndexError, ValueError):
        return ("n/a", "n/a", 0, "•", False)
    if any(np.isnan(x) for x in (v_now, m_now, v_prev, m_prev)):
        return ("n/a", "n/a", 0, "•", False)

    dv = v_now - v_prev
    dm = m_now - m_prev
    dv_pos, dv_neg = dv > thresh, dv < -thresh
    dm_pos, dm_neg = dm > thresh, dm < -thresh

    arrow = ("↗" if dv_pos and dm_pos else
             "↘" if dv_pos and dm_neg else
             "↖" if dv_neg and dm_pos else
             "↙" if dv_neg and dm_neg else
             "→" if dv_pos else "←" if dv_neg else
             "↑" if dm_pos else "↓" if dm_neg else "•")

    nxt = current
    if current == "LEADING":
        nxt = "WEAKENING" if dm_neg else ("IMPROVING" if dv_neg and not dm_pos else current)
    elif current == "WEAKENING":
        nxt = "LAGGING"   if dv_neg else ("LEADING"   if dm_pos and not dv_neg else current)
    elif current == "LAGGING":
        nxt = "IMPROVING" if dm_pos else ("WEAKENING" if dv_pos and not dm_neg else current)
    elif current == "IMPROVING":
        nxt = "LEADING"   if dv_pos else ("LAGGING"   if dm_neg and not dv_pos else current)

    # Translate v_now (already centered, range typically ±20) for the helpers
    rs_ratio_centered = v_now - 100.0
    traj = f"{current} (stable)" if nxt == current else f"{current} -> {nxt}"
    score = _rrg_score(rs_ratio_centered, current)
    tradeable = _rrg_tradeable(current, nxt, rs_ratio_centered)
    return (traj, nxt, score, arrow, tradeable)

def calculate_alpha_score(ind: dict) -> int:
    score = 0
    c = float(ind["close"].iloc[-1])
    ema20 = float(ind["ema20"].iloc[-1])
    sma50 = float(ind["sma50"].iloc[-1])
    rsi14 = float(ind["rsi14"].iloc[-1])
    adx = float(ind["adx"].iloc[-1])
    pdi = float(ind["plus_di"].iloc[-1])
    mdi = float(ind["minus_di"].iloc[-1])
    o = float(ind["open"].iloc[-1])
    rv = float(ind["rel_vol"].iloc[-1])
    
    if c > ema20: score += 15
    if c > sma50: score += 15
    
    # R1: N-bar momentum replaces RSI(14) > 60/50
    pa_mom_10 = c > float(ind["close"].iloc[-11]) if len(ind["close"]) > 10 else False
    pa_mom_5  = c > float(ind["close"].iloc[-6])  if len(ind["close"]) > 5 else False
    if pa_mom_10 and pa_mom_5: score += 20
    elif pa_mom_10: score += 10
    
    # R4: Directional bar count replaces ADX
    if len(ind["close"]) > 14:
        dir_bars = sum(1 for i in range(1, 15) if float(ind["close"].iloc[-i]) > float(ind["open"].iloc[-i]) and float(ind["high"].iloc[-i]) > float(ind["high"].iloc[-(i+1)]))
        if dir_bars >= 7: score += 10
    
    if c > o and rv >= 1.5: score += 20
    elif c > o and rv >= 1.0: score += 10
    
    dist_ema20 = abs(c - ema20) / ema20 * 100
    if dist_ema20 < 5: score += 20
    elif dist_ema20 < 10: score += 10

    # Macro edge (parity with Pine use_macro_edge, default on). Volume regime,
    # PA-compatible: above-average participation (+10) vs thin/distribution (-20).
    if rv > 1.0: score += 10
    else: score -= 20

    return score

def check_conditions(ind: dict, weekly: dict, alpha: int,
                       symbol: Optional[str] = None,
                       mkt_bull: bool = True) -> dict:
    alpha_ok = alpha >= CONFIG["alpha_gate"]
    
    c = ind["close"]
    h = ind["high"]
    l = ind["low"]
    o = ind["open"]
    v = ind["volume"]
    rv = ind["rel_vol"]
    rsi14 = ind["rsi14"]
    rsi3 = ind["rsi3"]
    ema20 = ind["ema20"]
    sma50 = ind["sma50"]
    sma150 = ind["sma150"]
    sma200 = ind["sma200"]
    obv = ind["obv"]
    obv_ema = ind["obv_ema"]
    h52w = ind["high52w"]
    l52w = ind["low52w"]
    
    sma20 = ind["sma20"]
    atr10 = ind["atr10"]
    atr10_sma50 = ind["atr10_sma50"]
    vol_vwma5 = ind["vol_vwma5"]
    bb_width = ind["bb_width"]

    c_now = float(c.iloc[-1])
    o_now = float(o.iloc[-1])
    h_now = float(h.iloc[-1])
    l_now = float(l.iloc[-1])
    rv_now = float(rv.iloc[-1])
    ema20_now = float(ema20.iloc[-1])
    rsi14_now = float(rsi14.iloc[-1])
    rsi3_now = float(rsi3.iloc[-1])

    # ----- Pine v4.52 line 969: minervini_trend = pure trend stack only -----
    # 52H/52L now live in trend_template_ok (Fix #4).
    minervini = (
        c_now > sma50.iloc[-1] and
        sma50.iloc[-1] > sma150.iloc[-1] and
        sma150.iloc[-1] > sma200.iloc[-1]
    )

    # ----- Pine v4.52 line 888: trend_template_ok -----
    # min_dist_52L = 0.30 (was 0.25 in old Python — Fix #5)
    # max_dist_52H = 0.25 (close within 25% of 52W high)
    trend_template_ok = (
        c_now > l52w.iloc[-1] * 1.30 and
        c_now >= h52w.iloc[-1] * 0.75
    )

    # ----- 9-gate weinstein_setup (Pine v4.52 line 937) — Fix #3 -----
    # Gates enforced (in Pine order):
    #   stage_ok         : weekly stage == 1 or 2 (basing or uptrend — v1.1 Fix #4)
    #   trend_aligned    : full Minervini trend stack (close>50>150>200)
    #   rs_ok            : Mansfield > 0 (×100 scale → outperforming benchmark)
    #   sector_stage_ok  : SKIPPED — no sector data in Python pipeline (default True). TODO.
    #   vol_acc_ok       : >= 3 of last 20 bars: green close in upper-60% + above-avg vol (v1.1 Fix #2; v2.4 sync: comment matches code threshold of 3)
    #   stage2_fresh_ok  : SMA50>SMA150 not true for ALL last 130 bars (recent transition)
    #   ma_sqz_ok        : abs(SMA20-SMA50)/SMA50 < 0.05 (MAs squeezed within 5%)
    #   bb_sqz_ok        : current BB width < 30-bar SMA of BB width (v1.1 Fix #3)
    #   trend_template_ok: Minervini 52W proximity gate (above)
    stage_ok = weekly["stage"] in (1, 2)  # v1.1: accept Stage 1 (base) + Stage 2 (uptrend)
    trend_aligned = minervini  # close>50>150>200 — same as Pine d_close>d_50>d_150>d_200
    rs_ok = weekly["mansfield"] > 0
    sector_stage_ok = True  # TODO: wire up sector data when available
    # vol_acc_ok: institutional accumulation density (v1.1 Fix #2 — Pine v2.3 lines 1076-1080)
    # Green close + above-avg volume + close in upper 60% of bar range, counted over 20 bars.
    _dr = h - l
    _cr = (c - l) / _dr.replace(0, np.nan)
    _v_one = (c > c.shift(1)) & (v > ind["vol_ma"]) & (_cr > 0.6)
    vol_acc_ok = bool(_v_one.iloc[-20:].sum() >= 3)
    # stage2_fresh_ok: stock didn't have SMA50>SMA150 for ALL last 130 bars
    # → means it has freshly transitioned within the last ~26 weeks
    if len(sma50) >= 130 and len(sma150) >= 130:
        _stack = (sma50.iloc[-130:] > sma150.iloc[-130:])
        stage2_fresh_ok = bool(_stack.sum() < 130)
    else:
        stage2_fresh_ok = True  # not enough history → don't gate it out
    # R6: Price coil (20-bar range < 10% of close) replaces ma_sqz_ok
    if len(h) >= 20:
        coil_range = float(h.iloc[-20:].max()) - float(l.iloc[-20:].min())
        ma_sqz_ok = (coil_range / c_now) <= 0.10
    else:
        ma_sqz_ok = False
        
    # R5: NR7 range contraction replaces bb_sqz_ok
    if len(h) >= 7:
        cur_range = h_now - l_now
        min_range_7 = float((h.iloc[-7:] - l.iloc[-7:]).min())
        bb_sqz_ok = float(cur_range) <= min_range_7 * 1.1
    else:
        bb_sqz_ok = False

    # ZERO-DRIFT FIX (2026-06-02): align to canonical Pine weinstein_setup
    # (Weinstein_Unified_Ecosystem_v3.4.pine line 1622), which is:
    #   (stage2_uptrend or stage1_base) and close>d_sma200 and rs_quadrant!="LAGGING"
    #   and vol_acc_ok and stage2_fresh_ok and trend_template_ok
    # ma_sqz_ok / bb_sqz_ok are computed in Pine but used only as display/VCP
    # flags — they are NOT in the positional gate. Python had wrongly AND-ed
    # them in (a tight-coil/NR7 squeeze), which is mutually exclusive with the
    # POS-BO breakout requirement and nullified the ENTIRE positional book
    # (0 POS picks across 24 months; 25/440 qualify once the squeeze is removed).
    weinstein_setup = (
        stage_ok and trend_aligned and rs_ok and sector_stage_ok and
        vol_acc_ok and stage2_fresh_ok and
        trend_template_ok
    )

    intraday_pos = (c_now - l_now) / (h_now - l_now) if h_now > l_now else 0
    # VDU gate — Pine v3.1 line 1275: single-bar vol < 70% avg AND declining close
    vol_drying = (
        float(v.iloc[-1]) < float(ind["vol_ma"].iloc[-1]) * 0.7 and
        c_now < float(c.iloc[-2])
    )
    dist_ema20 = abs(c_now - ema20_now) / ema20_now * 100

    # ----- VCP per Pine v4.52 line 672-677 / Beta v2.4 line 238 — Fix #2 -----
    if (not np.isnan(atr10.iloc[-1]) and not np.isnan(atr10_sma50.iloc[-1])
            and not np.isnan(vol_vwma5.iloc[-1]) and not np.isnan(ind["vol_ma"].iloc[-1])):
        vcp_tight_bo = (
            atr10.iloc[-1] < atr10_sma50.iloc[-1] * 1.875 and
            vol_vwma5.iloc[-1] < ind["vol_ma"].iloc[-1]
        )
        vcp_tight_swg = (
            atr10.iloc[-1] < atr10_sma50.iloc[-1] * 1.50 and
            vol_vwma5.iloc[-1] < ind["vol_ma"].iloc[-1]
        )
    else:
        vcp_tight_bo = False
        vcp_tight_swg = False

    # Decouple alpha gate for breakouts
    alpha_ok_for_bo = True

    # Daily CPR (Central Pivot Range) math:
    d_pivot = (h_now + l_now + c_now) / 3.0
    d_bc = (h_now + l_now) / 2.0
    d_tc = d_pivot + abs(d_pivot - d_bc)
    cpr_ok = c_now > d_tc

    # Monthly VWAP math:
    last_date = c.index[-1]
    same_month_mask = (c.index.year == last_date.year) & (c.index.month == last_date.month)
    monthly_pv = (c[same_month_mask] * v[same_month_mask]).sum()
    monthly_v = v[same_month_mask].sum()
    mvwap = monthly_pv / monthly_v if monthly_v > 0 else c_now
    mvwap_ok = c_now > mvwap

    # ----- H2: Volume-price accumulation bars replace OBV trending-up filter -----
    if len(c) >= 20:
        acc_bars = sum(1 for i in range(1, 21) if float(c.iloc[-i]) > float(ind["open"].iloc[-i]) and float(v.iloc[-i]) > float(v.iloc[-(i+1)]))
        obv_trending_up = acc_bars >= 8
    else:
        obv_trending_up = False
        
    # ----- R2: Pullback depth replaces RSI(14) pocket for SWG-PB -----
    if len(h) >= 20:
        sw_hi_20 = float(h.iloc[-20:].max())
        sw_lo_20 = float(l.iloc[-20:].min())
        sw_range = sw_hi_20 - sw_lo_20
        retrace_pct = (sw_hi_20 - c_now) / sw_range if sw_range > 0 else 0.0
        rsi_pb_pocket = 0.38 <= retrace_pct <= 0.62
    else:
        rsi_pb_pocket = False
        
    # ----- R3: PRIOR down-structure replaces RSI(3) for SWG-REV -----
    # FIX 2026-06-03: measure weakness in the bars ENDING YESTERDAY (not today),
    # so it is compatible with the reversal-bar confirm (today close>open AND
    # close>high[1]). Earlier version included today's down close, which
    # contradicted close>high[1] → the gate could never fire (0 picks).
    # Price fell over the 3 days ending yesterday: close[1]<close[2]<close[3]
    # (Python: c[-2]<c[-3]<c[-4]).
    if len(c) >= 4:
        pa_oversold = (float(c.iloc[-2]) < float(c.iloc[-3]) and
                       float(c.iloc[-3]) < float(c.iloc[-4]))
    else:
        pa_oversold = False

    # ----- Catalysts — Pine v4.52 priority cascade — Fix #1 -----
    # Pine evaluates positional engine first, then swing engine.
    # Order: POS-BO -> POS-ACCUM -> SWG-GAP -> SWG-BO -> SWG-PB -> SWG-REV
    # v1.1 Fix #1: SWG-* catalysts gated on mkt_bull (Pine v2.3 line 1022).
    # (cat_id values kept compatible with previous output ordering for downstream tools)
    cat_id = 0
    cat_label = "None"

    # v2.4 funnel diagnostic — count per-gate eligibility for each catalyst INDEPENDENTLY
    # so we see where each funnel collapses, regardless of priority cascade outcome.
    adx_now = float(ind["adx"].iloc[-1]) if not np.isnan(ind["adx"].iloc[-1]) else 0.0

    # POS-BO funnel (E5: uses weinstein_setup for the base gate)
    _pb_break = c_now > float(h.iloc[-22:-1].max())
    _pb_vol   = rv_now > 1.25

    # ── Pine-parity catalyst helpers (Weinstein_Unified_Ecosystem_v3.4) ──────
    # Zero-drift restoration: the undocumented "R-series" rewrite diverged the
    # Python catalyst gates from the canonical Pine triggers. These mirror them.
    _sma50_now  = float(sma50.iloc[-1])  if not np.isnan(sma50.iloc[-1])  else c_now
    _sma150_now = float(sma150.iloc[-1]) if not np.isnan(sma150.iloc[-1]) else c_now
    _sma200_now = float(sma200.iloc[-1]) if not np.isnan(sma200.iloc[-1]) else c_now
    _vol_ma_now = float(ind["vol_ma"].iloc[-1])
    # is_vcp_tight = f_is_vcp(1.0): atr10 < sma(atr10,50)*1.0 AND vwma(vol,5) < sma(vol,50)
    if (not np.isnan(atr10.iloc[-1]) and not np.isnan(atr10_sma50.iloc[-1])
            and not np.isnan(vol_vwma5.iloc[-1]) and not np.isnan(_vol_ma_now)):
        is_vcp_tight = (atr10.iloc[-1] < atr10_sma50.iloc[-1] * 1.0 and
                        vol_vwma5.iloc[-1] < _vol_ma_now)
        # POS-ACCUM gets a looser VCP (1.5x) so accumulation isn't starved (was 2 fires).
        is_vcp_accum = (atr10.iloc[-1] < atr10_sma50.iloc[-1] * 1.5 and
                        vol_vwma5.iloc[-1] < _vol_ma_now)
    else:
        is_vcp_tight = False
        is_vcp_accum = False
    # PART (a): PRICE-ACTION anti-chase (replaces POS-ACCUM daily RSI<=50).
    # Accumulation entry should not chase a sharp run-up: close not more than 5%
    # above its 5-day-ago close (momentum hasn't already extended).
    pa_not_extended = (c_now <= float(c.iloc[-6]) * 1.05) if len(c) >= 6 else True
    # base_confirmed (Pine 1633) = (weinstein_setup or mature_trend_ok) and mpa_pass.
    # mature_trend_ok needs weeks-in-stage (wStageWks) the Python weekly pipeline
    # doesn't track — approximated by stage-2 + LEADING RRG + above EMA20/SMA200.
    mpa_pass = c_now > _sma150_now and _sma150_now > _sma200_now
    mature_trend_ok = (weekly["stage"] == 2 and
                       str(weekly.get("rrg_quadrant", "")).upper() == "LEADING" and
                       c_now > ema20_now and c_now > _sma200_now)
    base_confirmed = (weinstein_setup or mature_trend_ok) and mpa_pass
    # PRICE-ACTION directional strength (Jay's preference: replaces ADX). >=7 of
    # last 14 bars are up-closes making higher highs — a clean uptrend structure.
    _pb_dir_ok = (sum(1 for i in range(1, 15)
                      if float(c.iloc[-i]) > float(ind["open"].iloc[-i]) and
                         float(h.iloc[-i]) > float(h.iloc[-(i + 1)])) >= 7) if len(c) > 14 else False
    _bo20 = float(h.iloc[-21:-1].max()) if len(h) >= 21 else float(h.max())  # 20-bar breakout: highest(high,20)[1]
    # SWG-PB — bull_pullback (price action: tag EMA20 low, close above, up day)
    bull_pullback = (c_now > _sma50_now and l_now <= ema20_now and
                     c_now > ema20_now and c_now > o_now)
    pb_ma_stack   = _sma150_now > _sma200_now
    # PRICE-ACTION pullback pocket (replaces RSI 30-70): retrace 38-62% of the
    # 20-bar range off the swing high — a measured pullback, not extreme.
    pb_pocket_pa  = rsi_pb_pocket
    pb_vol_dry    = (float(v.iloc[-4:-1].mean()) < _vol_ma_now) if len(v) >= 4 else False
    # SWG-GAP: gap_intra_pos = (close-open)/(high-open)
    gap_up        = o_now > float(h.iloc[-2]) and c_now > o_now
    gap_pct       = (o_now - float(h.iloc[-2])) / float(h.iloc[-2]) if float(h.iloc[-2]) > 0 else 0.0
    gap_intra_pos = (c_now - o_now) / (h_now - o_now) if h_now > o_now else 0.0
    # SWG-REV: rev_struct + PRICE-ACTION oversold (pa_oversold, replaces RSI<35)
    #          + bullish reversal confirm (close>open and close>prior high)
    rev_struct    = c_now > _sma200_now and c_now < ema20_now
    not_stage4    = weekly["stage"] != 4

    FUNNEL["POSBO_eligible"]       += 1
    FUNNEL["POSBO_pass_mkt_bull"]  += 1 if mkt_bull else 0
    FUNNEL["POSBO_pass_alpha"]     += 1 if (mkt_bull and alpha_ok_for_bo) else 0
    FUNNEL["POSBO_pass_weinstein"]      += 1 if (mkt_bull and alpha_ok and base_confirmed) else 0
    FUNNEL["POSBO_pass_breakout"]  += 1 if (mkt_bull and alpha_ok and base_confirmed and c_now > _bo20) else 0
    FUNNEL["POSBO_pass_vol"]       += 1 if (mkt_bull and alpha_ok and base_confirmed and c_now > _bo20 and _pb_vol) else 0
    FUNNEL["POSBO_pass_wrsi60"]    += 1 if (mkt_bull and alpha_ok and base_confirmed and c_now > _bo20 and _pb_vol and weekly.get("w_mom", False)) else 0
    FUNNEL["POSBO_pass_adx25"]     += 1 if (mkt_bull and alpha_ok and base_confirmed and c_now > _bo20 and _pb_vol and weekly.get("w_mom", False) and _pb_dir_ok) else 0

    # POS-ACCUM funnel
    _pa_break = c_now > float(h.iloc[-31:-1].max()) * 0.9
    FUNNEL["POSAC_eligible"]       += 1
    FUNNEL["POSAC_pass_mkt_bull"]  += 1 if mkt_bull else 0
    FUNNEL["POSAC_pass_alpha"]     += 1 if (mkt_bull and alpha_ok_for_bo) else 0
    FUNNEL["POSAC_pass_obv"]       += 1 if (mkt_bull and alpha_ok and obv_trending_up) else 0
    FUNNEL["POSAC_pass_weinstein"]      += 1 if (mkt_bull and alpha_ok and obv_trending_up and base_confirmed) else 0
    FUNNEL["POSAC_pass_vcp"]       += 1 if (mkt_bull and alpha_ok and obv_trending_up and base_confirmed and is_vcp_accum) else 0
    FUNNEL["POSAC_pass_breakout"]  += 1 if (mkt_bull and alpha_ok and obv_trending_up and base_confirmed and is_vcp_accum and _pa_break) else 0
    FUNNEL["POSAC_pass_rsi50"]     += 1 if (mkt_bull and alpha_ok and obv_trending_up and base_confirmed and is_vcp_accum and _pa_break and pa_not_extended) else 0

    # SWG-PB funnel (Pine-parity gate chain)
    FUNNEL["SWGPB_eligible"]    += 1
    FUNNEL["SWGPB_pass_mkt"]    += 1 if mkt_bull else 0
    FUNNEL["SWGPB_pass_pullback"]  += 1 if (mkt_bull and bull_pullback) else 0
    FUNNEL["SWGPB_pass_vcp"]    += 1 if (mkt_bull and bull_pullback and is_vcp_tight) else 0
    FUNNEL["SWGPB_pass_mastack"] += 1 if (mkt_bull and alpha_ok and minervini and bull_pullback and is_vcp_tight) else 0
    FUNNEL["SWGPB_pass_rsipocket"] += 1 if (mkt_bull and alpha_ok and minervini and bull_pullback and is_vcp_tight and pb_pocket_pa) else 0
    FUNNEL["SWGPB_pass_voldry"] += 1 if (mkt_bull and bull_pullback and is_vcp_tight and pb_ma_stack and pb_pocket_pa and pb_vol_dry) else 0

    # Sub-funnel: weinstein_setup composition
    FUNNEL["WEIN_stage_ok"]        += 1 if stage_ok else 0
    FUNNEL["WEIN_trend_aligned"]   += 1 if trend_aligned else 0
    FUNNEL["WEIN_rs_ok"]           += 1 if rs_ok else 0
    FUNNEL["WEIN_vol_acc_ok"]      += 1 if vol_acc_ok else 0
    FUNNEL["WEIN_stage2_fresh"]    += 1 if stage2_fresh_ok else 0
    FUNNEL["WEIN_ma_sqz_ok"]       += 1 if ma_sqz_ok else 0
    FUNNEL["WEIN_bb_sqz_ok"]       += 1 if bb_sqz_ok else 0
    FUNNEL["WEIN_trend_template"]  += 1 if trend_template_ok else 0
    # Diagnostic: weinstein without the two squeeze gates (suspected POS killer)
    FUNNEL["WEIN_all_no_squeeze"]  += 1 if (stage_ok and trend_aligned and rs_ok and
                                            sector_stage_ok and vol_acc_ok and
                                            stage2_fresh_ok and trend_template_ok) else 0
    FUNNEL["WEIN_all_pass"]        += 1 if weinstein_setup else 0

    # ── Catalyst priority cascade — structure/firing mirrors Pine
    #    (Weinstein_Unified_Ecosystem_v3.4), but lagging indicators are replaced
    #    with PRICE ACTION per Jay's design (ADX→dir-bars, RSI-pocket→retrace,
    #    RSI<35→pa_oversold). Pine to be synced to these PA gates (see AUDIT_FINDINGS).
    # POS-BO: base_confirmed + alpha + 20-bar breakout + vol>1.25x
    #   + PA weekly momentum (w_mom, replaces weekly RSI>=60 — part a)
    #   + PA directional strength (_pb_dir_ok, replaces ADX>=25)
    if (mkt_bull and base_confirmed and alpha_ok and c_now > _bo20 and _pb_vol and
            weekly.get("w_mom", False) and _pb_dir_ok):
        cat_id = 2; cat_label = "POS-BO"
    # POS-ACCUM: base_confirmed + alpha + obv + looser VCP (is_vcp_accum) +
    #   30-bar breakout + PA anti-chase (pa_not_extended, replaces RSI<=50 — part a)
    elif (mkt_bull and base_confirmed and alpha_ok and obv_trending_up and is_vcp_accum and
            _pa_break and pa_not_extended):
        cat_id = 1; cat_label = "POS-ACCUM"
    # SWG-GAP: gap_up + gap>=4% + close in top 40% of gap bar + vol>3x (pure PA)
    elif (mkt_bull and gap_up and gap_pct >= 0.04 and gap_intra_pos >= 0.60 and
            rv_now >= 3.0):
        cat_id = 6; cat_label = "SWG-GAP"
    # SWG-BO: is_vcp_tight + 20-bar breakout + vol>1.5x (price/volume structure)
    elif (mkt_bull and is_vcp_tight and c_now > _bo20 and rv_now > 1.5):
        cat_id = 4; cat_label = "SWG-BO"
    # SWG-PB: QUALITY pullback in a strong leader. Restored the quality gates the
    #   Pine-sync had stripped (alpha_ok leadership + full minervini stack
    #   close>50>150>200, vs the looser sma150>200) — without them SWG-PB fired on
    #   weak/rolling-over stocks that bounce then fail (-5% alpha, 88% SL-hit).
    #   PA throughout: bull_pullback (tag EMA20, close above, up day) + is_vcp_tight
    #   + price-action pocket (retrace) + volume dry-up.
    elif (mkt_bull and alpha_ok and minervini and bull_pullback and is_vcp_tight and
            pb_pocket_pa and pb_vol_dry):
        cat_id = 3; cat_label = "SWG-PB"
    # SWG-REV: not stage4 + rev_struct + PRICE-ACTION oversold (pa_oversold,
    #   replaces RSI<35) + bullish reversal confirm (close>open and close>prior high)
    elif (not_stage4 and rev_struct and pa_oversold and c_now > o_now and
            c_now > float(h.iloc[-2])):
        cat_id = 5; cat_label = "SWG-REV"

    score = compute_score(cat_label, weekly, alpha, rv_now, trend_template_ok,
                          c_now, h52w.iloc[-1], symbol=symbol,
                          daily_rsi=rsi14_now)

    return {"id": cat_id, "label": cat_label, "score": score,
            "minervini": minervini, "trend_template": trend_template_ok}


def compute_score(cat_label: str, weekly: dict, alpha: int, rv_now: float,
                  trend_template_ok: bool, c_now: float, h52w_now: float,
                  symbol: Optional[str] = None,
                  daily_rsi: Optional[float] = None) -> int:
    """v1.1 100-pt score. Tuned from validation findings (12 monthly anchors,
    Apr-2025 → Mar-2026, Nifty 100 universe, top-10 picks per anchor):

      Original v1.0 top-10 alpha was +0.55% / median +1.24%.
      The April-2025 anchor missed by 6.5pp — root causes:
         • 4 of 10 picks in WEAKENING RRG quadrant — averaged -1.30% there
         • 0 of 10 picks had a fired catalyst → score was Mansfield+trend only
         • VCP_Valid stocks underperformed in this period (small sample)

      v1.1 changes:
         • NEW: RRG quadrant scoring  (+5 LEADING / -10 WEAKENING / -5 LAGGING)
         • Mansfield_4w bonus  (+5 if positive momentum)
         • Reduced VCP boost in screen_symbol from +20% to +10% (keep broke_pivot
           bonus since pivot break is the actionable confirmation)
         • Catalyst weights unchanged (signal was flat in this sample but kept
           since the catalyst gates are interpretable; a noisy fix risks worse).

    Components (max sums to ~110, capped at 100):
      Catalyst tier ........... up to 30 pts (unchanged)
      Stage 2 confirmation ....   10 pts
      Mansfield RS .............  up to 20 pts (>0: +10, >=10: +10 more)
      Mansfield 4w momentum ...   5 pts  (NEW: positive momentum)
      RRG quadrant ............  -10 to +5 pts (NEW: LEADING+5, WEAKENING-10, LAGGING-5)
      Volume confirmation .....  up to 15 pts
      Sector strength placeholder . 5 pts
      Trend template pass .....   10 pts
      Distance off 52W high ... up to 10 pts
    """
    score = 0

    # Catalyst tier — v1.3 (REVERTED from v1.4 after N500 validation regression).
    # The v1.4 sweep changed 5 things at once and lost -1.02pp avg alpha and
    # -25pp hit rate. We're back at v1.3 (production); future tuning must
    # change ONE component at a time and re-validate before composing.
    #
    #   POS-BO / SWG-GAP : 30 (theoretical — never/rarely fires on N500)
    #   SWG-BO           : 30 (N500 n=44, +3.79% alpha)
    #   SWG-REV          : 20 (N500 n=20, +2.56% alpha)
    #   SWG-PB           : 10 (v1.3 cut from 20 — kept after v1.4 revert; see
    #                      validation note: SWG-PB restoration was bundled with
    #                      4 other changes in v1.4 so we can't isolate its
    #                      contribution. Run it alone in v1.5 to settle.)
    #   POS-ACCUM        : 15
    # v2 hook: catalyst score adjustment (e.g. POS-ACCUM nullout when RSI > 50).
    # Hook is a no-op when v2 flags are all OFF (the v1 FINAL default).
    try:
        import v2_fixes as _v2
    except Exception:
        _v2 = None

    if cat_label in ("POS-BO", "SWG-BO", "SWG-GAP"):
        score += 30
    elif cat_label == "SWG-REV":
        score += 20
    elif cat_label == "SWG-PB":
        score += 10
    elif cat_label == "POS-ACCUM":
        _base = 15
        if _v2 is not None:
            _base = _v2.adjust_catalyst_score(cat_label, _base, daily_rsi)
        score += _base

    # Stage 2 confirmation
    if weekly.get("stage") == 2:
        score += 10

    # Mansfield (cumulative tiers)
    m = weekly.get("mansfield", 0.0)
    if m > 0:
        score += 10
    if m >= 10:
        score += 10

    # v1.1: Mansfield 4w momentum bonus — second axis of RRG, rewards rising RS
    m4w = weekly.get("mansfield_4w", 0.0) or 0.0
    if m4w > 0:
        score += 5

    # v1.6 RRG scoring — replaced n=33 Nifty-100 calibration with universe-wide
    # validation (n=5,460 Nifty 500 × 12 anchors, no screener filters).
    # The only signal that survived: which side of RS-Ratio=100 the stock sits.
    #   RS-Ratio >= 100 (LEADING + WEAKENING): n=2,776, mean alpha +2.07%
    #   RS-Ratio <  100 (IMPROVING + LAGGING): n=2,684, mean alpha -0.64%
    # 2.71 pp spread. Single binary signal, +5 / -5.
    # (12-cell trajectory matrix didn't survive — r=0.086 only, with cells
    # inverted: IMPROVING->LEADING n=154 was -0.96%, not +10 as Nifty 100 implied.
    # Trajectory is now an advisory `RRG_Tradeable` column, not a score input.)
    score += weekly.get("rrg_score", 0)

    # Volume confirmation (REVERTED from v1.4 flatten — see validation note).
    if rv_now >= 2.0:
        score += 15
    elif rv_now >= 1.5:
        score += 10
    elif rv_now >= 1.0:
        score += 5

    # v1.2 (E3-overlay): real sector-strength bonus.
    # Replaces the flat +5 placeholder with -5..+5 from sector_strength.py
    # which classifies the symbol's sector as Stage 2/4/Transitional and
    # measures monthly momentum. Stage 4 sectors get -5; Stage 2 with
    # positive monthly momentum gets +5; n/a / unknown sectors get 0.
    try:
        if symbol:
            from sector_lookup import get_sector_index
            from sector_strength import get_sector_score
            sec_idx = get_sector_index(symbol)
            if sec_idx:
                score += get_sector_score(sec_idx)
            else:
                score += 0  # unknown sector — neutral
        else:
            score += 0
    except Exception:
        # Fall back to the old flat bonus if sector_strength is unavailable.
        score += 5

    # Trend template pass
    if trend_template_ok:
        score += 10

    # Distance off 52W high (sliding)
    if h52w_now and h52w_now > 0 and not np.isnan(h52w_now):
        dist_high_pct = (h52w_now - c_now) / h52w_now * 100
        if dist_high_pct <= 5:
            score += 10
        elif dist_high_pct <= 10:
            score += 7
        elif dist_high_pct <= 15:
            score += 5
        elif dist_high_pct <= 25:
            score += 3

    # v2.3 E-1: regime-aware score adjustment — penalizes picks in bear markets,
    # bonuses picks in strong bull markets. Gated by V2_FLAGS["regime_score_penalty"].
    # When flag is OFF, regime_score_adjust() returns base_score unchanged.
    if _v2 is not None:
        score = _v2.regime_score_adjust(score)

    # v1.1: clamp to [0, 100] (the new RRG penalty can push below 0)
    return max(0, min(score, 100))

def screen_symbol(symbol: str, df_bench: pd.DataFrame,
                  force_output: bool = False,
                  mkt_bull: bool = True) -> dict:
    yf_sym = to_yf(symbol)
    try:
        if USE_DATA_PROVIDER and _dp is not None:
            df_d = _flatten_cols(_dp.fetch_ohlcv(symbol, period="2y", interval="1d"))
            if df_d.empty or len(df_d) < 60: return None
            df_w = _flatten_cols(_dp.fetch_ohlcv(symbol, period="3y", interval="1wk"))
        else:
            df_d = _flatten_cols(yf.download(yf_sym, period="2y", interval="1d", auto_adjust=True, progress=False))
            if df_d.empty or len(df_d) < 60: return None
            df_w = _flatten_cols(yf.download(yf_sym, period="3y", interval="1wk", auto_adjust=True, progress=False))
    except Exception:
        return None

    ind = compute_indicators(df_d)
    
    turnover_cr = float(ind["close"].iloc[-1] * ind["volume"].iloc[-1]) / 1e7
    if turnover_cr < CONFIG["min_turnover_cr"] and not force_output: return None
    
    weekly = compute_weekly_indicators(df_w, df_bench)
    alpha = calculate_alpha_score(ind)
    cond = check_conditions(ind, weekly, alpha, symbol=symbol, mkt_bull=mkt_bull)
    
    if cond["id"] == 0 and not force_output: return None
    
    c = float(ind["close"].iloc[-1])
    atr = float(ind["atr"].iloc[-1])
    _label = cond.get("label", "")
    # v1.11 (2026-05-21): Catalyst-aware SL multiplier — a 1.5x daily-ATR stop
    # on a 120-180d positional trade gets knocked out by routine pullbacks
    # within the first 2 weeks (per-catalyst audit: POS-BO showed 100% SL hit
    # at avg 5d held). Wider SL = lower position size per the 1% risk rule,
    # but the trade survives to its design horizon.
    if _label.startswith("POS"):
        atr_mult = 4.0   # positional: 4x daily ATR ~ 1 weekly ATR worth of room
    elif _label.startswith("WYC"):
        atr_mult = 3.5   # Wyckoff base: between positional and swing
    elif _label.startswith("REV"):
        atr_mult = 2.5   # recovery / mean-reversion: 90d holds
    else:
        atr_mult = 1.5   # swing (SWG-*)
    sl = c - atr * atr_mult
    risk = c - sl
    # v1.9 (2026-05-21): Catalyst-differentiated T1/T2 — respect trade timeframe.
    # POS (positional, 2-12mo holds): 5R/10R — let winners run
    # SWG-BO/PB (swing, 1-4wk): 3R/5R — partial fast, ride remainder
    # SWG-GAP (gap-and-go, days):  2R/4R — gaps fade fast
    # SWG-REV (mean rev, days):    2R/2R — quick exit
    if _label.startswith("POS"):
        t1_r, t2_r = 5.0, 10.0
    elif _label == "SWG-REV":
        t1_r, t2_r = 2.0, 2.0
    elif _label == "SWG-GAP":
        t1_r, t2_r = 2.0, 4.0
    elif _label.startswith("SWG"):           # SWG-BO, SWG-PB
        t1_r, t2_r = 3.0, 5.0
    else:                                     # fallback / NONE
        t1_r, t2_r = 3.0, 5.0
    t1 = c + risk * t1_r
    t2 = c + risk * t2_r
    
    # E3: VCP / pivot detection — adds base-quality context to the catalyst Score.
    # Uses the same daily frame already fetched, so no extra network cost.
    try:
        from pivot_detector import detect_vcp
        _vcp = detect_vcp(df_d)
    except Exception:
        _vcp = {"is_valid": False, "quality_score": 0, "pivot_price": None,
                 "broke_pivot": False, "days_since_pivot": None}

    # B11: Pine-parity swing-momentum back-port — I:C ratio, leg velocity, accel
    # arrow, EMA20 ATR distance. Pivot semantics match Wesinstein Swing Zigzag
    # [Strict v6.2] with default Daily pivot_len=2 (the user's setting).
    try:
        _swm = compute_swing_momentum(df_d, pivot_len=2, atr_n=14)
    except Exception:
        _swm = {"swing_pct_current": np.nan, "swing_pct_prev": np.nan,
                "ic_ratio": np.nan, "leg_vel_pct": np.nan, "prev_leg_vel_pct": np.nan,
                "vel_accel": "n/a", "ema20_dist_atr": np.nan, "active_dir": "n/a"}

    # VCP boost (REVERTED to v1.3 logic — removing the score multiplier in
    # v1.4 cost ~1pp alpha; the universe-level inversion of VCP_score was
    # misleading because VCP_score correlates with hidden discriminators
    # that the screener relies on for selection).
    _final_score = int(cond["score"])
    if _vcp.get("is_valid"):
        _final_score = min(100, _final_score + int(_vcp["quality_score"]) // 10)
        if _vcp.get("broke_pivot"):
            _final_score = min(100, _final_score + 5)

    # ML Probability Scoring (from 10y Nifty 500 Backtest)
    rsi_val = float(ind["rsi14"].iloc[-1])
    atr_pct = (float(ind["atr"].iloc[-1]) / float(ind["close"].iloc[-1])) * 100 if float(ind["close"].iloc[-1]) > 0 else 3.0
    bbw_val = float(ind["bb_width"].iloc[-1])
    mrs_val = float(weekly["mansfield"])
    alpha_val = float(alpha)
    pb_depth = (float(ind["high52w"].iloc[-1]) - float(ind["close"].iloc[-1])) / float(ind["high52w"].iloc[-1]) if float(ind["high52w"].iloc[-1]) > 0 else 0
    vcp_val = 1.0 if _vcp.get("is_valid") else 0.0
    ma_sqz_val = abs(float(ind["ema20"].iloc[-1]) - float(ind["sma50"].iloc[-1])) / float(ind["sma50"].iloc[-1]) if float(ind["sma50"].iloc[-1]) > 0 else 0

    ml_score = (-0.510474
         + (0.023048 * rsi_val)
         + (0.113267 * atr_pct)
         + (-0.848810 * bbw_val)
         + (0.002488 * mrs_val)
         + (-0.013312 * alpha_val)
         + (-1.137420 * pb_depth)
         + (0.072967 * vcp_val)
         + (-1.658263 * ma_sqz_val))
    import math
    ml_win_prob = round((1.0 / (1.0 + math.exp(-ml_score))) * 100, 1)

    record = {
        "Symbol": symbol,
        "Catalyst": cond["label"],
        "Score": _final_score,                                 # E3: includes VCP boost
        "Catalyst_Score": cond["score"],                       # E3: original catalyst-only score
        "Alpha": alpha,
        "Stage": weekly["stage"],
        "JdK_RS_Ratio":      round(weekly["mansfield"] + 100.0, 2),
        "JdK_RS_Momentum":   round(weekly["mansfield_4w"] + 100.0, 2),
        "RRG_Quadrant":      weekly["rrg_quadrant"],
        "RRG_Trajectory":    weekly.get("rrg_trajectory", "n/a"),
        "RRG_Next":          weekly.get("rrg_next", "n/a"),
        "RRG_Arrow":         weekly.get("rrg_arrow", "•"),
        "RRG_Score":         weekly.get("rrg_score", 0),
        "RRG_Tradeable":     bool(weekly.get("rrg_tradeable", False)),
        "ML_Prob":           ml_win_prob,
        "Rel_Vol": round(float(ind["rel_vol"].iloc[-1]), 2),
        "RSI": round(float(ind["rsi14"].iloc[-1]), 1),
        # E3: VCP / pivot columns
        "VCP_Valid":          bool(_vcp.get("is_valid")),
        "VCP_Score":          int(_vcp.get("quality_score", 0)),
        "Pivot_Price":        _vcp.get("pivot_price"),
        "Broke_Pivot":        bool(_vcp.get("broke_pivot")),
        "Days_Since_Pivot":   _vcp.get("days_since_pivot"),
        "Entry": round(c, 2),
        "SL_pct": round((c - sl) / c * 100, 2),
        "T1_pct": round((t1 - c) / c * 100, 2),
        "T2_pct": round((t2 - c) / c * 100, 2),
        "T1_R": t1_r,
        "T2_R": t2_r,
        "Suggested_Size": "15%" if alpha >= 70 else "5%",
        # B11: Pine-parity swing momentum (mirrors Wesinstein Swing Zigzag v6.2 panel)
        "Swing_Pct_Current":  _swm.get("swing_pct_current"),
        "Swing_Pct_Prev":     _swm.get("swing_pct_prev"),
        "IC_Ratio":           _swm.get("ic_ratio"),
        "Leg_Vel_Pct":        _swm.get("leg_vel_pct"),
        "Prev_Leg_Vel_Pct":   _swm.get("prev_leg_vel_pct"),
        "Vel_Accel":          _swm.get("vel_accel"),
        "EMA20_Dist_ATR":     _swm.get("ema20_dist_atr"),
        "Active_Dir":         _swm.get("active_dir"),
    }

    # v2 hook: record-level Score adjustments (VCP multiplier, Days_Since_Pivot
    # penalty). No-op when v2 flags are all OFF (the v1 FINAL default).
    try:
        import v2_fixes as _v2
        record = _v2.adjust_record_score(record)
    except Exception:
        pass
    return record

def run_bull_screener(progress_callback=None, symbols=None,
                      out_file: str = OUTPUT_FILE,
                      strict: bool = False) -> pd.DataFrame:
    """Screen a list of NSE symbols for bull market catalysts.

    Parameters
    ----------
    progress_callback : callable(idx, total, sym), optional
        Called after each symbol is processed.
    symbols : list[str], optional
        Pre-loaded symbol list.  When *None* the function reads from
        ``FINAL_COMBINED_BULL_PICKS.csv`` (default behaviour).
    out_file : str, optional
        CSV filename to save results (relative to DATA_DIR).
    """
    # D6: the original `force_tracker_mode = (symbols is not None)` test was
    # always True after the default-path branch overwrote `symbols`. Capture
    # whether the caller supplied a list BEFORE that branch reassigns.
    caller_supplied_symbols = symbols is not None

    if symbols is None:
        in_path = os.path.join(DATA_DIR, INPUT_FILE)
        if not os.path.exists(in_path):
            raise FileNotFoundError(f"Missing input {INPUT_FILE}")
        df_in   = pd.read_csv(in_path)
        # Accept common column-name variants
        col = next(
            (c for c in df_in.columns
             if c.strip().lower() in ("symbol", "nsecode", "ticker", "scrip")),
            None,
        )
        if col is None:
            raise ValueError(
                f"No 'Symbol' column found in {INPUT_FILE}. "
                f"Columns present: {list(df_in.columns)}"
            )
        symbols = df_in[col].dropna().astype(str).str.strip().str.upper().unique().tolist()
        symbols = [s for s in symbols if s and not s.isdigit()]

    # C1: shared cache for the benchmark too — a single screener run reuses
    # the same ^CRSLDX weekly slice across hundreds of symbols.
    if USE_DATA_PROVIDER and _dp is not None:
        df_bench = _flatten_cols(_dp.fetch_ohlcv(BENCHMARK_YF, period="3y", interval="1wk"))
        df_bench_d = _flatten_cols(_dp.fetch_ohlcv(BENCHMARK_YF, period="2y", interval="1d"))
    else:
        df_bench = _flatten_cols(
            yf.download(BENCHMARK_YF, period="3y", interval="1wk",
                        auto_adjust=True, progress=False)
        )
        df_bench_d = _flatten_cols(
            yf.download(BENCHMARK_YF, period="2y", interval="1d",
                        auto_adjust=True, progress=False)
        )

    # v1.5: yfinance's weekly bars for ^CRSLDX often lag the current week,
    # while individual stocks include it. Inner-merge then drops the live week
    # → RRG/Mansfield run on stale data. Fix: resample daily→weekly (W-MON,
    # closed=left, label=left to match yfinance's Monday-start convention) and
    # APPEND any newer weeks the weekly fetch missed onto df_bench. Preserves
    # the full 3-year history while ensuring the latest week is always present.
    if not df_bench_d.empty and len(df_bench_d) >= 20:
        try:
            df_bench_resampled = df_bench_d.resample(
                "W-MON", closed="left", label="left"
            ).agg({
                "Open":  "first",
                "High":  "max",
                "Low":   "min",
                "Close": "last",
                "Volume": "sum",
            }).dropna(subset=["Close"])
            if not df_bench_resampled.empty:
                if df_bench.empty:
                    df_bench = df_bench_resampled
                else:
                    # Append only NEW weeks not already present in weekly fetch
                    new_weeks = df_bench_resampled[
                        df_bench_resampled.index > df_bench.index[-1]
                    ]
                    if not new_weeks.empty:
                        df_bench = pd.concat([df_bench, new_weeks])
        except Exception:
            pass

    # v1.1 Fix #1: mkt_bull regime gate (Pine v2.3 line 1022).
    # CNX500 close > SMA200 AND SMA50 > SMA200 → bull market confirmed.
    # Computed ONCE per run (same for all symbols). SWG-* catalysts suppressed
    # when the broader market is not in a confirmed uptrend.
    mkt_bull = False
    _b_close = _b_sma50 = _b_sma200 = float("nan")
    _bench_rows = 0
    _bench_last_date = "n/a"
    if not df_bench_d.empty:
        _bench_rows = len(df_bench_d)
        try:
            _bench_last_date = str(df_bench_d.index[-1].date())
        except Exception:
            _bench_last_date = str(df_bench_d.index[-1])
        if _bench_rows >= 200:
            _bc = df_bench_d["Close"]
            _b_sma50  = float(_bc.rolling(50).mean().iloc[-1])
            _b_sma200 = float(_bc.rolling(200).mean().iloc[-1])
            _b_close  = float(_bc.iloc[-1])
            mkt_bull = bool(
                not np.isnan(_b_sma50) and not np.isnan(_b_sma200) and
                _b_close > _b_sma200 and _b_sma50 > _b_sma200
            )

    # Override via env var when Commander Web regime disagrees with yfinance ^CRSLDX
    _override = os.environ.get("MKT_BULL_OVERRIDE", "").strip().upper()
    if _override in ("1", "TRUE", "BULL"):
        print(f"  >>> MKT_BULL_OVERRIDE=BULL — forcing mkt_bull=True (was {mkt_bull})")
        mkt_bull = True
    elif _override in ("0", "FALSE", "NOT"):
        print(f"  >>> MKT_BULL_OVERRIDE=NOT — forcing mkt_bull=False (was {mkt_bull})")
        mkt_bull = False

    print(f"  Market regime: {'BULL' if mkt_bull else 'NOT BULL'} "
          f"(CNX500 close>SMA200 AND SMA50>SMA200)")
    print(f"    Benchmark fetch: {_bench_rows} bars, last={_bench_last_date}")
    print(f"    CNX500 close = {_b_close:.2f}")
    print(f"    CNX500 SMA50 = {_b_sma50:.2f}")
    print(f"    CNX500 SMA200= {_b_sma200:.2f}")
    print(f"    close>SMA200: {_b_close > _b_sma200 if not np.isnan(_b_sma200) else 'na'}")
    print(f"    SMA50>SMA200: {_b_sma50 > _b_sma200 if not np.isnan(_b_sma200) else 'na'}")

    # v2.4 sync diagnostic: reset funnel counters at start of run
    FUNNEL.clear()

    results = []
    total   = len(symbols)
    # Tracker mode: only when the caller explicitly handed us a watchlist
    # (e.g. the dashboard's custom-upload path). Default-watchlist runs keep
    # the strict catalyst gate.
    # v2.5 patch (18 May 2026 — user intent clarification):
    # Tracker mode is the DEFAULT for curated watchlists (FINAL_COMBINED_BULL_PICKS
    # and upload-CSV) because those lists have already gone through rigorous
    # filtering before reaching the screener — user wants visibility into ALL
    # tracked stocks with their catalyst state (including "None").
    # Only explicit strict=True (Nifty 500 / F&O broad-universe screens) applies
    # the catalyst gate that drops non-firing rows.
    force_tracker_mode = not strict
    
    for idx, sym in enumerate(symbols, 1):
        if progress_callback:
            progress_callback(idx, total, sym)
        try:
            res = screen_symbol(sym, df_bench, force_output=force_tracker_mode,
                                mkt_bull=mkt_bull)
            if res:
                results.append(res)
        except Exception:
            pass
        time.sleep(CONFIG["download_delay_sec"])

    # v2.4 sync diagnostic — print per-gate funnel for POS-BO and POS-ACCUM
    # AND mirror it to a file (Bull_Screener_Funnel.log in DATA_DIR) so you can
    # read it after the run without needing to capture stdout from Streamlit.
    funnel_lines = []
    def _flog(msg=""):
        funnel_lines.append(msg)
        print(msg)
    _flog()
    _flog(f"  Market regime computed: {'BULL' if mkt_bull else 'NOT BULL'}")
    _flog("  ---- CATALYST FUNNEL DIAGNOSTIC (v2.4 sync) ----")
    pb_e = FUNNEL.get("POSBO_eligible", 0)
    if pb_e:
        _flog(f"  POS-BO ({pb_e} eligible)")
        for k in ["POSBO_pass_mkt_bull", "POSBO_pass_alpha", "POSBO_pass_weinstein",
                  "POSBO_pass_breakout", "POSBO_pass_vol", "POSBO_pass_wrsi60", "POSBO_pass_adx25"]:
            n = FUNNEL.get(k, 0)
            pct = (n / pb_e * 100) if pb_e else 0
            label = "[" + k.replace("POSBO_pass_", "+ ") + "]"
            _flog(f"    {label:<26} {n:>5} / {pb_e}  ({pct:5.1f}%)")
    pa_e = FUNNEL.get("POSAC_eligible", 0)
    if pa_e:
        _flog(f"  POS-ACCUM ({pa_e} eligible)")
        for k in ["POSAC_pass_mkt_bull", "POSAC_pass_alpha", "POSAC_pass_obv",
                  "POSAC_pass_weinstein", "POSAC_pass_vcp", "POSAC_pass_breakout", "POSAC_pass_rsi50"]:
            n = FUNNEL.get(k, 0)
            pct = (n / pa_e * 100) if pa_e else 0
            label = "[" + k.replace("POSAC_pass_", "+ ") + "]"
            _flog(f"    {label:<26} {n:>5} / {pa_e}  ({pct:5.1f}%)")
    sp_e = FUNNEL.get("SWGPB_eligible", 0)
    if sp_e:
        _flog(f"  SWG-PB ({sp_e} eligible)")
        for k in ["SWGPB_pass_mkt", "SWGPB_pass_pullback", "SWGPB_pass_vcp",
                  "SWGPB_pass_mastack", "SWGPB_pass_rsipocket", "SWGPB_pass_voldry"]:
            n = FUNNEL.get(k, 0)
            pct = (n / sp_e * 100) if sp_e else 0
            label = "[" + k.replace("SWGPB_pass_", "+ ") + "]"
            _flog(f"    {label:<26} {n:>5} / {sp_e}  ({pct:5.1f}%)")
    we = pb_e
    if we:
        _flog(f"  WEINSTEIN_SETUP composition ({we} eligible)")
        for k in ["WEIN_stage_ok", "WEIN_trend_aligned", "WEIN_rs_ok", "WEIN_vol_acc_ok",
                  "WEIN_stage2_fresh", "WEIN_ma_sqz_ok", "WEIN_bb_sqz_ok",
                  "WEIN_trend_template", "WEIN_all_no_squeeze", "WEIN_all_pass"]:
            n = FUNNEL.get(k, 0)
            pct = (n / we * 100) if we else 0
            label = "[" + k.replace("WEIN_", "+ ") + "]"
            _flog(f"    {label:<26} {n:>5} / {we}  ({pct:5.1f}%)")
    _flog()

    # Persist funnel diagnostic to file so you can read it without stdout capture
    try:
        _funnel_path = os.path.join(DATA_DIR, "Bull_Screener_Funnel.log")
        with open(_funnel_path, "w", encoding="utf-8") as _fh:
            _fh.write("\n".join(funnel_lines))
        print(f"  Funnel diagnostic written to: {_funnel_path}")
    except Exception as _e:
        print(f"  Could not write funnel log: {_e}")
    print()

    if results:
        df_out = pd.DataFrame(results).sort_values("Score", ascending=False)

        # 10 May 2026 — Conviction passthrough: look up each symbol's Screener.in
        # conviction (same logic the Golden Matcher uses) and compute a unified
        # Combined_Score so Bull Screener's ranking is consistent with the
        # matcher's FINAL_WATCHLIST.csv. Single source of truth for "best picks".
        try:
            import conviction_passthrough as _cp
            df_out = _cp.add_conviction_and_combined_score(
                df_out, mode="bull", score_col="Score"
            )
            # Re-rank by Combined_Score (was previously Score-only)
            if "Combined_Score" in df_out.columns:
                df_out = df_out.sort_values("Combined_Score", ascending=False)
        except Exception as _cpe:
            logger.debug("Conviction passthrough skipped: %s", _cpe)

        df_out.to_csv(os.path.join(DATA_DIR, out_file), index=False)
        # Auto-log live picks to pick_log.db (replay-safe — pick_log.log_picks
        # silently skips when data_provider is pinned).
        try:
            import pick_log as _pl
            _pl.log_picks("bull", df_out)
        except Exception:
            pass
        return df_out

    # Zero-signals case (10 May 2026 fix): still write a header-only CSV so
    # the file timestamp updates. Without this, a successful run that found
    # no actionable catalysts looked identical to "never ran" — the freshness
    # check stayed stuck on the previous run's date. Now: file exists, mtime
    # = today, row count = 0, downstream code reads it as empty df and shows
    # "No signals found" cleanly.
    _empty_cols = [
        "Symbol", "Score", "Catalyst", "Stage", "Mansfield_RS",
        "Daily_RSI", "Daily_ADX", "Vol_Shelf", "OBV_Trending_Up",
        "VCP_Tight", "Recommended_SL", "T1", "T2",
    ]
    pd.DataFrame(columns=_empty_cols).to_csv(
        os.path.join(DATA_DIR, out_file), index=False
    )
    return pd.DataFrame(columns=_empty_cols)

def main():
    # E10: optional --as-of YYYY-MM-DD flag for replay mode.
    import argparse as _ap
    parser = _ap.ArgumentParser(description="Commander Bull Screener")
    parser.add_argument("--as-of", dest="as_of", default=None,
                         help="Replay mode: run as of this date (YYYY-MM-DD). "
                              "data_provider slices all OHLCV to bars on/before it.")
    parser.add_argument("--out", dest="out_file", default=OUTPUT_FILE,
                         help="Output CSV filename (default: Bull_Screener_Results.csv)")
    args, _ = parser.parse_known_args()

    pin_label = ""
    if args.as_of and USE_DATA_PROVIDER and _dp is not None:
        try:
            _dp.set_pinned_date(args.as_of)
            pin_label = f"  [REPLAY @ {args.as_of}]"
        except Exception as e:
            print(f"❌ invalid --as-of value: {e}")
            return

    print("=" * 68)
    print(f"  COMMANDER BULL SCREENER v1.0{pin_label}")
    print("=" * 68)

    def on_progress(idx, total, sym):
        print(f"[{idx:3d}/{total}] {sym:<15} ... ", end="", flush=True)

    try:
        df = run_bull_screener(on_progress, out_file=args.out_file)
        if not df.empty:
            print(f"\nSaved {len(df)} results to {args.out_file}")
        else:
            print("\nNo signals found.")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        # Always restore live mode at the end of a CLI run.
        if args.as_of and USE_DATA_PROVIDER and _dp is not None:
            try: _dp.set_pinned_date(None)
            except Exception: pass

if __name__ == "__main__":
    main()
