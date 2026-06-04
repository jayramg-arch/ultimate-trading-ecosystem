#!/usr/bin/env python3
"""
recovery_screener.py :  Commander Recovery Screener (Python Edition) v1.5
Aligned with: Weinstein Recovery Strategy v1.4 / Commander Capitulation Screener v1.3 /
              Chartink Recovery Scanners v2.0 / Unified Ecosystem v2.3

v1.5 (2026-05-21) — RE-INSTATED. The v1.4 "RETIRED" verdict was based on a
30-day forward-window backtest, which is the wrong horizon for recovery /
mean-reversion catalysts (designed for multi-month base-building per the
Weinstein Stage 1->2 transition). Roll-back pending re-validation with a
catalyst-aware forward window.

The Wyckoff variant (recovery_screener v3.0) lives alongside in
`recovery_screener_v3_wyckoff.py` for use when explicit Wyckoff
Spring/SOS/JAC detection is desired. Both are valid; choose by trade thesis.


CHANGELOG v1.4 (May-2026) — Align with Pine Unified Ecosystem v2.3 (3 fixes)
  Resolves: "Recovery picks show no catalyst signals on Unified Ecosystem chart"
    1. REV-CB regime gate: Pine v2.3 line 1196 requires regime_ok for ALL 3
       recovery edges. Python v1.3 only gated REV-RS/REV-EARLY. REV-CB now
       gated on regime_ok at the dispatch level (signal priority selector).
    2. REV-RS stock_corrected: Pine line 1205 requires stock_corrected as a
       STANDALONE gate (correction 10-40% from 52W high) in addition to
       regime_ok. Python v1.3 only checked regime_ok which could pass via
       market path (CNX500 corrected) without the stock itself being corrected.
    3. REV-EARLY strict trend: Pine line 1219 requires rs_recovery_state =
       higher_low_ok AND trend_up (dTrend==1 from strict zigzag). Python v1.3
       only checked higher_low_ok. Now ports compute_strict_trend() into
       check_rev_early() matching the existing pattern in check_rev_rs().

CHANGELOG v1.3 (Apr-2026) — Sync with Pine Recovery Strategy v1.4 (7 fixes)
  Brings the Python screener back into 1:1 alignment with the canonical Pine
  source-of-truth and adds RRG (Relative Rotation Graph) compatibility.
    1. REV-CB Pillar 1: cb_drawdown_pct default 15% → 25%. Aligns with the
       Capitulation Screener's calibrated threshold for high-conviction climaxes.
    2. REV-CB Pillar 3: relaxed `vol AND (bearish OR widest)` tightened to
       `vol AND bearish AND widest` — all three must fire (Pine v1.3 line 265 +
       strategy v1.4 line 720). Eliminates "fake" climax bars that have only
       volume + one of bearish/wide.
    3. Regime gate: restored 3-way OR gate (CNX500 corrected ≥7% OR CNX500
       SMA50-reclaim within 30 bars OR stock corrected). Stock_corrected
       previously gated alone, which was stricter than Pine. Quality cap
       (40% upper bracket on stock correction) retained as a Python-only filter.
    4. cb_washout_window: 7 → 10, cb_range_lookback: 20 → 10. Aligned with
       Pine's single 10-bar window for both red-bar count and widest-range.
    5. REV-RS / REV-EARLY: added strict-trend pivot zigzag gate (HH+HL pivot
       confirmation, `piv_d_right=2` so confirms 2 bars late). Ports Pine's
       f_getStrictTrend → compute_strict_trend(). dtrend == 1 ANDed onto the
       existing higher-low gate.
    6. RS gating metric: `rs_slope_w` (4-week ROC) → `mansfield_x100` (26-week
       Mansfield > 0). Matches Pine's textbook Mansfield gate. rs_slope_w kept
       as a secondary score column for tiebreaking. New `rs_momentum_4w` column
       (4-bar diff of Mansfield) exposes the RRG second axis.
    7. Mansfield scale: ×10 → ×100 (textbook, RRG-compatible). Score thresholds
       updated (rs_val >= 1.0 → rs_val >= 10.0). CSV column renamed
       Mansfield_RS → Mansfield_RS_x100 for self-documenting scale.
  Also adds an RRG_Quadrant column (LEADING / WEAKENING / LAGGING / IMPROVING)
  classifying each stock by Mansfield (price RS) and 4-bar Momentum.

CHANGELOG v1.2 (Apr-2026) — Price-action over lagging indicators
  The original v1.1 leaned heavily on SMA/RSI/ATR — lagging tools that fire
  3–6 bars after the real turn. This update replaces the worst offenders with
  pure price-structure checks. Lagging MAs are still computed for display
  (score/table) but no longer GATE entries.
  Six changes, aligned 1:1 with the Pine strategy v1.3:
    1. REV-CB Pillar 1: stretch vs SMA200  →  drawdown ≥ 25% from 60-bar high.
       Captures real selloffs without waiting for SMA200 to bend.
    2. REV-CB Pillar 2: RSI14<30 AND RSI3<15  →  ≥5 of last 7 bars red AND
       today closes in bottom 25% of 10-day range. Bar-1 reactive, no smoothing.
    3. REV-CB Pillar 3: range > ATR×1.5  →  range ≥ widest of last 20 ranges.
       No ATR smoothing. Relative volume kept (vol data is inherently reactive).
    4. REV-RS: drop "close > SMA50 today" gate  →  higher-low confirmation:
       lowest low of last 5 bars > lowest low of prior 10 bars. Pure structure.
       Mansfield RS (26wk SMA of ratio) demoted to display; 4-week RS-line slope
       gates the signal (same concept, 6× more responsive).
    5. REV-EARLY: "SMA50 within 5% of SMA200" near-GC  →  trendline reclaim:
       close > highest high of bars 20-10 ago (break of prior swing-high shelf).
       ATR-based VCP  →  NR7 (narrowest range in 7) OR ≥3 inside bars in last 10.
    6. Regime gate: CNX500 SMA50 < SMA200 (death cross)  →  correction depth
       AND/OR price-structure reclaim (recent 10-bar low > prior 10-bar low).
       Death cross retained as DISPLAY ONLY in the regime summary.

CHANGELOG v1.1 (Apr-2026)
  cb_stretch_pct: 15.0 → 8.0  (deprecated in v1.2 — Pillar 1 no longer uses SMA200)
  cb_vol_mult:     2.5 → 2.0  (retained — still used in Pillar 3 volume check)
Aligned with: Weinstein Recovery Strategy v1.0

Replaces the Pine Screener for swing/positional traders.  Run daily post-market
or over the weekend: signals stay visible for signal_hold_days after they fire.

WHAT IT DOES
  Reads the three Chartink recovery watchlists (already on disk from your
  "Complete Workflow" run), downloads EOD OHLCV from Yahoo Finance, and applies
  all three recovery edges with no Pine Screener constraints.

IMPROVEMENTS OVER PINE SCREENER
   No 5-call limit: full indicator suite + all 6 RFF fundamental checks
   Signal hold window via date arithmetic (not var-int hacks)
   Proper Mansfield RS from OHLCV ratio: no fragile ticker strings
   Regime gate includes CNX500 52W-high correction depth
   Can be run daily post-market or any time over the weekend

INPUTS  (from DATA_DIR: same folder as chartink_scanner_pro.py)
  Recovery_RS_Survivors.csv           : Chartink REV-RS candidates
  Recovery_Climax_Bounce.csv          : Chartink REV-CB candidates
  Recovery_Early_Birds.csv            : Chartink REV-EARLY candidates
  SCREENER_Recovery_RSLeaders.csv     : Screener.in fundamentals (optional)
  SCREENER_Recovery_ClimaxBounce.csv  : Screener.in fundamentals (optional)
  SCREENER_Recovery_EarlyBirds.csv    : Screener.in fundamentals (optional)

OUTPUT
  Recovery_Screener_Results.csv : sorted: Signal 40, then Score highlow
"""

import os
import time
import logging
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

# Suppress yfinance's own HTTP-error and peewee logging — the screener already
# handles failed downloads gracefully; the noise just clutters the console.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("peewee").setLevel(logging.CRITICAL)

# C1: route OHLCV through the unified data_provider when available.
try:
    import data_provider as _dp
    USE_DATA_PROVIDER = True
except Exception:
    _dp = None
    USE_DATA_PROVIDER = False

warnings.filterwarnings("ignore")

# -----------------------------------------------------------------------------
# CONFIGURATION :  mirror the Pine Screener inputs here
# -----------------------------------------------------------------------------
CONFIG = {
    # -- Timing --------------------------------------------------------------
    "signal_hold_days"         : 5,     # signal stays active for N trading days after trigger
    "cb_climax_window"         : 10,    # look back this many days for a valid climax bar

    # -- Liquidity ------------------------------------------------------------
    "min_daily_turnover_cr"    : 5.0,   # INR Crores (5 Cr = 50M)

    # -- REV-CB (v1.2: pure price action) -------------------------------------
    "cb_vol_mult"              : 2.0,   # Pillar 3: climax volume >= 2.0× 50D average
    "cb_lookback_high_days"    : 60,    # Pillar 1: drawdown lookback window (bars)
    "cb_drawdown_pct"          : 15.0,  # Pillar 1: ≥N% drawdown from 60D high. RESTORED 25→15 (2026-06-04): 25% caught only 2% of stocks (extreme crashes only); 15% = ~20% (realistic beaten-down universe for catching quality on sale). Climax still gated by P2 washout + P3 panic-vol.
    "cb_washout_window"        : 10,    # Pillar 2: red-bar count window (v1.3: 7 → 10, aligns with Pine cb_range_lookback unification)
    "cb_washout_red_count"     : 5,     # Pillar 2: ≥N of last cb_washout_window bars red (was RSI14<30)
    "cb_range_lookback"        : 10,    # Pillar 3: "widest range in N bars" (v1.3: 20 → 10, aligns with Capitulation Screener v1.3)
    "cb_stretch_pct"           : 8.0,   # DEPRECATED v1.2 — retained only for display in older CSVs

    # -- REV-RS ---------------------------------------------------------------
    "rs_bo_len"                : 20,    # breakout: close > highest high of last N days
    "vol_confirm_mult"         : 1.5,   # breakout volume >= 1.5 50D average
    "rs_hl_recent"             : 5,     # v1.2: higher-low check — recent low window (bars)
    "rs_hl_prior"              : 10,    # v1.2: higher-low check — prior low window (bars before recent)
    "rs_slope_weeks"           : 4,     # v1.2: RS-line slope weeks — DEMOTED v1.3 to secondary score column (gate now on Mansfield)
    "piv_d_left"               : 2,     # v1.3: strict-trend pivot left bars (matches Pine f_getStrictTrend)
    "piv_d_right"              : 2,     # v1.3: strict-trend pivot right bars (signal confirms 2 bars late)
    "rs_momentum_weeks"        : 4,     # v1.3: RS-Momentum = Mansfield.diff(N) for RRG second axis

    # -- REV-EARLY (v1.2: trendline reclaim + NR7) ----------------------------
    "early_pivot_len"          : 15,    # pivot: close > highest high of last N days
    "early_trendline_recent"   : 10,    # v1.2: skip last N bars when finding prior swing high
    "early_trendline_window"   : 10,    # v1.2: width of prior swing-high window (bars 20→10 ago)
    "early_nr7_len"            : 7,     # v1.2: NR7 length for base compression
    "early_inside_lookback"    : 10,    # v1.2: inside-bar count lookback
    "early_inside_count_min"   : 3,     # v1.2: ≥N inside bars in last 10 (alternative to NR7)
    "near_gc_pct"              : 5.0,   # DEPRECATED v1.2 — near-GC check removed from gating
    "vcp_atr_mult"             : 1.5,   # DEPRECATED v1.2 — ATR-based VCP replaced by NR7/inside

    # -- Regime Gate ----------------------------------------------------------
    "mkt_correction_pct"       : 7.0,   # CNX500 down >=7% from 52W high  gate opens
    "mkt_reclaim_max_bars"     : 30,    # v1.3: CNX500 reclaimed SMA50 within last N bars (replaces v1.2 higher-low lookback)
    "mkt_reclaim_lookback"     : 10,    # DEPRECATED v1.3 — kept for back-compat; not used
    "min_stock_correction_pct" : 10.0,  # individual stock >=10% off 52W high → regime bypass
    "max_stock_correction_pct" : 40.0,  # individual stock <=40% off 52W high → quality cap (>40% = distressed, not discounted)
    "use_regime_gate"          : True,  # MASTER TOGGLE: If true, stock MUST be corrected within 10-40% band

    # -- Fundamentals (RFF) ---------------------------------------------------
    "rff_min_score"            : 4,     # min RFF base (4/6) — Jay: only fundamentally strong stocks (was 1 = ~any non-bankrupt)

    # -- Data -----------------------------------------------------------------
    "data_lookback_days"       : 400,   # daily history to download (covers 200D SMA warmup)
    "download_delay_sec"       : 0.4,   # polite pause between yfinance calls
}

DATA_DIR    = os.path.dirname(os.path.abspath(__file__))   # always same folder as this script
OUTPUT_FILE = "Recovery_Screener_Results.csv"
CNX500_YF   = "^CRSLDX"          # Nifty 500 on Yahoo Finance (^CNX500 is not valid)

CHARTINK_FILES = {
    "REV-RS"   : "Recovery_RS_Survivors.csv",
    "REV-CB"   : "Recovery_Climax_Bounce.csv",
    "REV-EARLY": "Recovery_Early_Birds.csv",
}

SCREENER_FILES = {
    "REV-RS"   : "SCREENER_Recovery_RSLeaders.csv",
    "REV-CB"   : "SCREENER_Recovery_ClimaxBounce.csv",
    "REV-EARLY": "SCREENER_Recovery_EarlyBirds.csv",
}

SIGNAL_LABELS = {4: "REV-EARLY", 3: "REV-RS", 2: "REV-CB", 1: "CB-Watch", 0: "None"}


# -----------------------------------------------------------------------------
# SYMBOL HELPER
# -----------------------------------------------------------------------------
def to_yf(symbol: str) -> str:
    """Chartink NSE code (BAJAJ-AUTO)  yfinance format (BAJAJ-AUTO.NS)."""
    s = str(symbol).strip().upper()
    return s if s.startswith("^") else f"{s}.NS"


def _flatten_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns produced by yfinance 0.2+."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


# -----------------------------------------------------------------------------
# INDICATOR ENGINE
# -----------------------------------------------------------------------------
def compute_indicators(df: pd.DataFrame) -> dict:
    """
    Compute all daily indicators needed for edge detection.
    Returns a dict of aligned Series (indexed by date).
    """
    c, h, l, v, o = df["Close"], df["High"], df["Low"], df["Volume"], df["Open"]

    # Moving averages
    sma50  = c.rolling(50).mean()
    sma150 = c.rolling(150).mean()
    sma200 = c.rolling(200).mean()
    ema20  = c.ewm(span=20, adjust=False).mean()
    vol_ma = v.rolling(50).mean()

    # ATR (Wilder's RMA parity with TradingView ta.atr)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr14    = tr.ewm(alpha=1.0/14, min_periods=14, adjust=False).mean()
    atr10    = tr.ewm(alpha=1.0/10, min_periods=10, adjust=False).mean()
    atr10_avg = atr10.rolling(50).mean()

    # RSI
    def _rsi(series, n):
        d = series.diff()
        g = d.clip(lower=0).rolling(n).mean()
        ls = (-d.clip(upper=0)).rolling(n).mean()
        return 100 - 100 / (1 + g / ls.replace(0, np.nan))

    rsi14 = _rsi(c, 14)
    rsi3  = _rsi(c, 3)

    # Rolling highs/lows
    high52w = h.rolling(250).max()
    rel_vol = v / vol_ma.replace(0, np.nan)

    return dict(
        close=c, high=h, low=l, open=o, volume=v,
        sma50=sma50, sma150=sma150, sma200=sma200, ema20=ema20,
        vol_ma=vol_ma, atr14=atr14, atr10=atr10, atr10_avg=atr10_avg,
        rsi14=rsi14, rsi3=rsi3, high52w=high52w, rel_vol=rel_vol,
    )


def compute_mansfield_rs(df_stock_w: pd.DataFrame, df_cnx500_w: pd.DataFrame) -> float:
    """
    Mansfield RS (weekly) = (RS_Line / SMA26_of_RS_Line - 1) × 100   (v1.3: ×100, RRG-compatible)
    RS_Line = stock_close / cnx500_close
    Positive = outperforming; Negative = lagging.
    Returns the latest value, or NaN if insufficient data.

    v1.3 note: now the PRIMARY gate metric for REV-RS / REV-EARLY (matches Pine
    v1.4). rs_slope_w (4-week ROC) demoted to a secondary score column for
    tiebreaking. Scaled ×100 so the value is in textbook RRG units (LEADING
    quadrant = Mansfield > 0 + Momentum > 0).
    """
    sc = df_stock_w["Close"].rename("s")
    mc = df_cnx500_w["Close"].rename("m")
    merged = pd.merge(sc, mc, left_index=True, right_index=True, how="inner")
    # B6 fix: warm-up requires 52 weekly bars (was 27). 26-week SMA needs 26
    # bars to compute; trusting Mansfield with one SMA sample is noisy.
    # 52 = 26 SMA + 26 trail history → stable, matches bull_screener.
    if len(merged) < 52:
        return np.nan
    rs_line  = merged["s"] / merged["m"]
    sma26    = rs_line.rolling(26).mean()
    mansfield = (rs_line / sma26.replace(0, np.nan) - 1) * 100
    return float(mansfield.iloc[-1]) if not mansfield.empty else np.nan


def compute_mansfield_series(df_stock_w: pd.DataFrame, df_cnx500_w: pd.DataFrame) -> pd.Series:
    """
    v1.3: full Mansfield ×100 SERIES (not just last value).
    Used to compute RS-momentum (4-bar diff) and RRG quadrant.
    Returns an empty Series if insufficient data.
    """
    sc = df_stock_w["Close"].rename("s")
    mc = df_cnx500_w["Close"].rename("m")
    merged = pd.merge(sc, mc, left_index=True, right_index=True, how="inner")
    # B6 fix: 52-week warm-up (was 27) — see compute_mansfield_rs.
    if len(merged) < 52:
        return pd.Series(dtype=float)
    rs_line  = merged["s"] / merged["m"]
    sma26    = rs_line.rolling(26).mean()
    return (rs_line / sma26.replace(0, np.nan) - 1) * 100


def compute_rs_slope_w(df_stock_w: pd.DataFrame, df_cnx500_w: pd.DataFrame,
                       weeks: int = 4) -> float:
    """
    v1.2: RS-line slope over N weeks (pure-price relative-strength gate).

    Replaces Mansfield RS for signal gating. Same idea — is the stock beating
    the benchmark — but without the 26-week SMA that buries recent recoveries.
    Formula: (RS_line[-1] / RS_line[-weeks-1] - 1) * 100
    Positive = outperforming over the window; Negative = lagging.
    """
    sc = df_stock_w["Close"].rename("s")
    mc = df_cnx500_w["Close"].rename("m")
    merged = pd.merge(sc, mc, left_index=True, right_index=True, how="inner")
    if len(merged) < weeks + 1:
        return np.nan
    rs_line = merged["s"] / merged["m"]
    ref     = rs_line.iloc[-(weeks + 1)]
    if ref == 0 or np.isnan(ref):
        return np.nan
    return float((rs_line.iloc[-1] / ref - 1) * 100)


def compute_strict_trend(high: pd.Series, low: pd.Series,
                         piv_left: int = 2, piv_right: int = 2) -> pd.Series:
    """
    v1.3: pivot-zigzag strict trend (port of Pine f_getStrictTrend).

    A pivot high at bar i is a high greater than the previous `piv_left` highs
    AND the next `piv_right` highs. A pivot low is the mirror.

    Trend states (ported from Pine — all returned aligned to the input index):
       1 = uptrend (current PH > prior PH AND current PL > prior PL → HH+HL)
      -1 = downtrend (LH+LL)
       0 = neither / unconfirmed

    NOTE: Because pivot confirmation requires `piv_right` future bars, the trend
    state at any bar i is only known after `piv_right` more bars have closed.
    This is the intended 2-bar confirmation lag of the canonical Pine version.
    """
    n = len(high)
    out = pd.Series(0, index=high.index, dtype=int)
    if n < (piv_left + piv_right + 1):
        return out

    h_arr = high.to_numpy()
    l_arr = low.to_numpy()

    # Detect pivots (placed at the pivot bar — i.e. piv_right bars BEFORE confirmation).
    # We track confirmed pivots and their bar index, then carry trend state forward.
    last_ph = np.nan
    prev_ph = np.nan
    last_pl = np.nan
    prev_pl = np.nan
    state = 0

    # Walk bars; a pivot at bar (i - piv_right) is confirmable at bar i.
    for i in range(piv_left + piv_right, n):
        piv_idx = i - piv_right                  # candidate pivot bar
        # Pivot high check
        win_h = h_arr[piv_idx - piv_left : piv_idx + piv_right + 1]
        if h_arr[piv_idx] == win_h.max() and (win_h == h_arr[piv_idx]).sum() == 1:
            prev_ph, last_ph = last_ph, h_arr[piv_idx]
        # Pivot low check
        win_l = l_arr[piv_idx - piv_left : piv_idx + piv_right + 1]
        if l_arr[piv_idx] == win_l.min() and (win_l == l_arr[piv_idx]).sum() == 1:
            prev_pl, last_pl = last_pl, l_arr[piv_idx]

        # Classify HH/HL = uptrend, LH/LL = downtrend
        if not (np.isnan(last_ph) or np.isnan(prev_ph) or
                np.isnan(last_pl) or np.isnan(prev_pl)):
            if last_ph > prev_ph and last_pl > prev_pl:
                state = 1
            elif last_ph < prev_ph and last_pl < prev_pl:
                state = -1
            # else: leave state unchanged (mixed signal preserves prior trend)
        out.iloc[i] = state

    return out


def compute_weinstein_stage(df_w: pd.DataFrame) -> int:
    """
    Weinstein stage from the CURRENT week's 30W SMA slope and price position.
    Avoids state-machine convergence issues by classifying from current indicators.
    Stage 2 = rising SMA30, price above SMA30.
    Stage 4 = falling SMA30, price below SMA30.
    Stage 1 = flattening/rising SMA30, price above SMA30.
    Stage 3 = flattening/falling SMA30, price above SMA30 (topping).
    """
    if len(df_w) < 35:
        return 0
    c    = df_w["Close"]
    sma  = c.rolling(30).mean()
    slope = sma - sma.shift(4)
    thresh = sma * 0.0005
    above = bool(c.iloc[-1] > sma.iloc[-1])
    sl    = float(slope.iloc[-1])
    th    = float(thresh.iloc[-1])
    up = sl > th
    dn = sl < -th
    if up and above:       return 2
    if dn and not above:   return 4
    if not dn and above:   return 1   # SMA flattening/rising, price above = Stage 1 base
    return 3                           # SMA weakening, price above = Stage 3 top


# -----------------------------------------------------------------------------
# REGIME GATE
# -----------------------------------------------------------------------------
def check_regime(df_cnx500_d: pd.DataFrame) -> dict:
    """
    v1.3: 3-way regime gate (Pine v1.4 alignment). Any one opens the gate:
      A) mkt_idx_corrected: CNX500 ≥7% off 52W high   (pure price: drawdown)
      B) mkt_reclaim:       CNX500 close > SMA50 today AND barssince(close <
                            SMA50) ≤ 30 — i.e. index has reclaimed its SMA50
                            within the last 30 bars (recent price/MA cross).
      C) stock_corrected:   per-symbol, ≥10% off own 52W high (caller-side)

    Quality cap (Python-only, retained as a useful filter):
      stock_correction must also be ≤ 40% (>40% = distressed, not discounted).

    The old "SMA50 < SMA200" death-cross is informational only (mkt_death_cross).
    """
    c   = df_cnx500_d["Close"]
    h   = df_cnx500_d["High"]
    l   = df_cnx500_d["Low"]

    # Pure-price metrics
    h52w = h.rolling(250).max().iloc[-1]
    last = c.iloc[-1]
    corr_depth    = float((h52w - last) / h52w) if h52w > 0 else 0.0
    mkt_corrected = corr_depth >= CONFIG["mkt_correction_pct"] / 100

    # v1.3: SMA50-reclaim — CNX500 close > SMA50 today AND was below within last 30 bars
    # (Pine v1.4 / Capitulation Screener v1.3 line 130. Replaces v1.2 higher-low check.)
    s50_series  = c.rolling(50).mean()
    s200_series = c.rolling(200).mean()
    s50  = s50_series.iloc[-1]
    s200 = s200_series.iloc[-1]
    max_bars_below = CONFIG.get("mkt_reclaim_max_bars", 30)
    if not (np.isnan(s50) or np.isnan(c.iloc[-1])):
        if c.iloc[-1] > s50:
            below_mask = (c < s50_series).values
            if below_mask.any():
                last_below_pos = int(np.where(below_mask)[0][-1])
                bars_since = len(c) - 1 - last_below_pos
                mkt_reclaim = bool(bars_since <= max_bars_below)
            else:
                mkt_reclaim = False  # always above → no reclaim event
        else:
            mkt_reclaim = False  # currently below SMA50
    else:
        mkt_reclaim = False

    # v1.3: 3-way OR gate — any of the three opens the regime
    # (was: corrected AND reclaiming. Pine v1.4 uses OR for proper coverage.)
    mkt_in_recovery = mkt_corrected or mkt_reclaim

    # Display-only: SMA cross state (no longer a gating input)
    death_cross = bool(not np.isnan(s50 + s200) and s50 < s200)

    return {
        "mkt_in_recovery": mkt_in_recovery,       # v1.3: corrected OR reclaiming (was AND)
        "mkt_corrected"  : mkt_corrected,          # ≥7% off 52W high
        "mkt_reclaim"    : mkt_reclaim,            # v1.2: higher-low structure
        "mkt_death_cross": death_cross,            # v1.2: display only, no longer gates
        "mkt_corr_pct"   : round(corr_depth * 100, 2),
        "mkt_close"      : round(last, 2),
        "mkt_sma50"      : round(s50, 2),
        "mkt_sma200"     : round(s200, 2),
    }


# -----------------------------------------------------------------------------
# RFF: FULL 6-CHECK RECOVERY FUNDAMENTAL FILTER
# -----------------------------------------------------------------------------
def _num(row: dict, *keys) -> float:
    """Extract first matching key from a Screener.in row dict, as float."""
    for k in keys:
        v = row.get(k, None)
        if v is not None and str(v).strip() not in ("", "-", "NA", "N/A"):
            try:
                return float(str(v).replace(",", "").replace("%", "").strip())
            except ValueError:
                pass
    return np.nan


def fetch_yf_fundamentals(yf_sym: str) -> dict:
    """
    Fetch RFF metrics for the strengthened scoring (v2.0 — 11 May 2026).

    This now goes well beyond Pine v2.2's `request.financial(... "FY")` calls,
    which suffer poor NSE coverage. We pull:

      • Pine-parity fields (NI, OCF, **CapEx** for FCF, EBITDA, Interest, D/E,
        CR, ROA) so compute_rff() can match the Pine 6-check set exactly.
      • TTM cashflow via the cashflow DataFrame (sum of last 4 quarters) when
        available — beats yfinance's point-in-time `info` snapshots which can
        be stale by a quarter or two.
      • Recovery-specific extras (quarterly sales/profit growth, OPM trend,
        prior-year D/E for trajectory) that Pine literally cannot compute due
        to the FY-only `request.financial()` constraint.

    Returns {} on any failure so the caller can detect 'no data'.

    Field notes (yfinance quirks for NSE stocks):
      debtToEquity   : returned as a percentage (e.g. 45 = 0.45× ratio) → /100
      returnOnAssets : returned as a decimal  (e.g. 0.08 = 8%)          → ×100
      interestExpense: often negative in yfinance → use abs()
      capitalExpenditures: typically negative on cashflow stmt          → abs()
    """
    try:
        tk = yf.Ticker(yf_sym)
        info = tk.info or {}
        if info.get("quoteType") in (None, "NONE", ""):
            return {}

        result = {}

        # ── Pine-parity fields ────────────────────────────────────────────────
        ni  = info.get("netIncomeToCommon")
        if ni  is not None:
            result["Net profit"] = float(ni)

        ocf = info.get("operatingCashflow")
        if ocf is not None:
            result["Cash from operating activity"] = float(ocf)

        # CapEx — required for FCF computation (Pine parity check #2).
        # Try info first, then walk the cashflow DataFrame.
        capex = info.get("capitalExpenditures")
        try:
            if capex is None:
                cf = getattr(tk, "cashflow", None)
                if cf is not None and not cf.empty:
                    for k in ("Capital Expenditure", "Capital Expenditures",
                              "CapitalExpenditure", "Capex"):
                        if k in cf.index:
                            capex = float(cf.loc[k].dropna().iloc[0])
                            break
        except Exception:
            pass
        if capex is not None:
            result["CapEx"] = abs(float(capex))   # always store as positive magnitude

        # TTM cashflow override (more accurate than point-in-time info)
        try:
            qcf = getattr(tk, "quarterly_cashflow", None)
            if qcf is not None and not qcf.empty:
                for k in ("Operating Cash Flow", "Total Cash From Operating Activities",
                          "OperatingCashFlow"):
                    if k in qcf.index:
                        ttm = qcf.loc[k].dropna().iloc[:4].sum()
                        if ttm and abs(ttm) > 0:
                            result["Cash from operating activity"] = float(ttm)
                        break
                for k in ("Capital Expenditure", "Capital Expenditures"):
                    if k in qcf.index:
                        ttm = qcf.loc[k].dropna().iloc[:4].sum()
                        if ttm and abs(ttm) > 0:
                            result["CapEx"] = abs(float(ttm))
                        break
        except Exception:
            pass

        de  = info.get("debtToEquity")
        if de is not None:
            de = float(de)
            result["Debt to equity"] = de / 100 if de > 10 else de

        cr  = info.get("currentRatio")
        if cr is not None:
            result["Current ratio"] = float(cr)

        roa = info.get("returnOnAssets")
        if roa is not None:
            result["Return on assets"] = float(roa) * 100

        # ICR: ebitda / |interestExpense|
        ebitda   = info.get("ebitda")
        interest = info.get("interestExpense")
        if ebitda and interest and interest != 0:
            result["Interest Coverage Ratio"] = abs(float(ebitda) / float(interest))

        # ── Recovery-specific extras (Tier-B bonus checks) ────────────────────
        # Quarterly profit growth (YoY) — recovery: bottom-line turning
        try:
            qf = getattr(tk, "quarterly_financials", None)
            if qf is not None and not qf.empty:
                if "Net Income" in qf.index:
                    s = qf.loc["Net Income"].dropna()
                    if len(s) >= 5:
                        prev_yoy = float(s.iloc[4]); curr = float(s.iloc[0])
                        if prev_yoy and abs(prev_yoy) > 0:
                            result["Qtr Profit Var %"] = (curr - prev_yoy) / abs(prev_yoy) * 100
                if "Total Revenue" in qf.index:
                    s = qf.loc["Total Revenue"].dropna()
                    if len(s) >= 5:
                        prev_yoy = float(s.iloc[4]); curr = float(s.iloc[0])
                        if prev_yoy and prev_yoy > 0:
                            result["Qtr Sales Var %"] = (curr - prev_yoy) / prev_yoy * 100
                # Operating margin trend (latest 2 quarters)
                if "Operating Income" in qf.index and "Total Revenue" in qf.index:
                    op = qf.loc["Operating Income"].dropna()
                    rv = qf.loc["Total Revenue"].dropna()
                    if len(op) >= 2 and len(rv) >= 2:
                        opm_now  = float(op.iloc[0]) / float(rv.iloc[0]) * 100 if rv.iloc[0] else None
                        opm_prev = float(op.iloc[1]) / float(rv.iloc[1]) * 100 if rv.iloc[1] else None
                        if opm_now is not None and opm_prev is not None:
                            result["OPM_Now"]   = opm_now
                            result["OPM_Prev"]  = opm_prev
        except Exception:
            pass

        # Prior-year D/E for trajectory check
        try:
            bs = getattr(tk, "balance_sheet", None)
            if bs is not None and not bs.empty and bs.shape[1] >= 2:
                td_keys = ("Total Debt", "TotalDebt")
                eq_keys = ("Stockholders Equity", "Total Stockholder Equity",
                           "StockholdersEquity")
                td_prev = eq_prev = None
                for k in td_keys:
                    if k in bs.index:
                        td_prev = float(bs.loc[k].iloc[1])
                        break
                for k in eq_keys:
                    if k in bs.index:
                        eq_prev = float(bs.loc[k].iloc[1])
                        break
                if td_prev is not None and eq_prev and eq_prev > 0:
                    result["DE_Prev"] = td_prev / eq_prev
        except Exception:
            pass

        return result

    except Exception:
        return {}


# Minimum number of populated base-tier fields required to attempt scoring.
# Below this we report INSUFFICIENT and don't pretend we measured fundamentals.
# Mirrors Pine v2.2 line 1006-1007 (`rff_data_fields >= 3`).
RFF_MIN_BASE_FIELDS = 3


def compute_rff(row: dict) -> tuple:
    """
    Strengthened RFF scoring (v2.0 — 11 May 2026).

    Two-tier score that brings the Python Recovery Screener to **parity with
    Pine Weinstein_Unified_Ecosystem v2.2** on the 6 fundamental checks, then
    extends with 4 recovery-specific checks Pine cannot compute (its
    `request.financial(... "FY")` calls have poor NSE coverage and no
    quarterly trend access).

    Returns
    -------
    tuple : (base_score, bonus_score, total_score, quality, checks)
        base_score   : 0-6   Pine-parity fundamental gate
        bonus_score  : 0-4   recovery-specific top-up (Python-only)
        total_score  : 0-10  base + bonus (used for ranking)
        quality      : "FULL" | "PARTIAL" | "INSUFFICIENT"
                       FULL        = ≥5 base fields populated
                       PARTIAL     = 3-4 base fields populated
                       INSUFFICIENT= <3 — score returned as 0 with quality flag
        checks       : dict of every check with bool/None values

    Tier-A (Pine parity, 0-6)
    -------------------------
        NI>0            net income positive
        FCF>0           OCF − |CapEx| positive  ← upgraded from OCF>0
        ICR>3.5         EBITDA / interest      ← tightened from 2 (matches Pine)
        D/E<2           debt-to-equity below 2
        CR>1            current ratio above 1
        ROA>5%          return on assets above 5%

    Tier-B (Recovery-specific bonus, 0-4)
    -------------------------------------
        Sales reflex    Qtr Sales Var % > 0       (top-line turning)
        Profit reflex   Qtr Profit Var % > 0      (bottom-line turning)
        Op leverage     ProfitGrowth > SalesGrowth (margins expanding)
        Deleveraging    D/E now < D/E prior year   (balance-sheet repair)
    """
    # ── Field extraction ─────────────────────────────────────────────────────
    ni    = _num(row, "Net profit", "Net Profit", "Net profit TTM", "PAT",
                      "NP 12M Rs.Cr.", "NP 12M",
                      "NP Qtr Rs.Cr.", "NP Qtr")
    ocf   = _num(row, "Cash from operating activity", "Operating cash flow",
                      "Cash from Operations", "Cash from operations last year", "CFO",
                      "CF Operations Rs.Cr.", "CF Operations")
    capex = _num(row, "CapEx", "Capital expenditure", "Capital Expenditure",
                      "CapEx Rs.Cr.")
    icr   = _num(row, "Interest Coverage Ratio", "Interest coverage", "ICR",
                      "Interest Coverage", "Int. Coverage")
    de    = _num(row, "Debt to equity", "Debt / Equity", "D/E",
                      "Debt / Equity Ratio", "Debt to Equity",
                      "Debt / Eq.", "Debt/Eq.")
    cr    = _num(row, "Current ratio", "Current Ratio")
    roa   = _num(row, "Return on assets", "ROA", "Return on Assets",
                      "ROA 12M %", "ROA 12M")
    roce  = _num(row, "ROCE", "Return on capital employed",
                      "Return on capital employed %", "ROCE %")
    if np.isnan(roa) and not np.isnan(roce):
        roa = roce * 0.6  # ROA ≈ 0.6 × ROCE (conservative)

    # Tier-B fields
    qsv     = _num(row, "Qtr Sales Var %", "Sales Var Qtr %", "QoQ Sales %",
                        "YoY Sales Var %")
    qpv     = _num(row, "Qtr Profit Var %", "Profit Var Qtr %", "QoQ Profit %",
                        "YoY Profit Var %")
    opm_now  = _num(row, "OPM_Now", "OPM %", "OPM")
    opm_prev = _num(row, "OPM_Prev", "OPM Prev %")
    de_prev  = _num(row, "DE_Prev", "Debt to equity prev", "D/E Prev")

    # ── FCF computation (Pine parity #2) ─────────────────────────────────────
    fcf = np.nan
    if not np.isnan(ocf):
        fcf = ocf - (abs(capex) if not np.isnan(capex) else 0.0)
        # If CapEx is unavailable, FCF degrades to OCF. Mark this in checks so
        # the caller knows the FCF check ran in degraded mode.

    # ── Data-sufficiency gate (mirrors Pine line 1006-1007) ──────────────────
    # Six base fields: NI, OCF, ICR, D/E, CR, ROA — must have ≥3 populated
    # before we attempt a real score (otherwise NaN→0 silently biases ranking).
    base_fields_present = sum(1 for v in (ni, ocf, icr, de, cr, roa)
                               if not np.isnan(v))
    if base_fields_present < RFF_MIN_BASE_FIELDS:
        return 0, 0, 0, "INSUFFICIENT", {
            "_quality": "INSUFFICIENT",
            "_fields_present": base_fields_present,
        }
    quality = "FULL" if base_fields_present >= 5 else "PARTIAL"

    # ── Tier A — Pine parity (0-6) ───────────────────────────────────────────
    base_checks = {
        "NI>0"     : (not np.isnan(ni)  and ni  > 0),
        "FCF>0"    : (not np.isnan(fcf) and fcf > 0),
        "ICR>3.5"  : (not np.isnan(icr) and icr > 3.5),
        "D/E<2"    : (not np.isnan(de)  and de  < 2),
        "CR>1"     : (not np.isnan(cr)  and cr  > 1),
        "ROA>5%"   : (not np.isnan(roa) and roa > 5),
    }
    base_score = sum(1 for v in base_checks.values() if v)

    # ── Tier B — Recovery-specific bonus (0-4) ───────────────────────────────
    op_lev_ok = (not np.isnan(qsv) and not np.isnan(qpv) and qpv > qsv)
    if not op_lev_ok and not np.isnan(opm_now) and not np.isnan(opm_prev):
        # Fallback: explicit OPM expansion when growth rates aren't available
        op_lev_ok = opm_now > opm_prev
    deleverage_ok = (not np.isnan(de) and not np.isnan(de_prev)
                      and de_prev > 0 and de < de_prev)

    bonus_checks = {
        "Sales↑"     : (not np.isnan(qsv) and qsv > 0),
        "Profit↑"    : (not np.isnan(qpv) and qpv > 0),
        "OpLev↑"     : op_lev_ok,
        "Deleverage" : deleverage_ok,
    }
    bonus_score = sum(1 for v in bonus_checks.values() if v)

    # ── Merge & return ───────────────────────────────────────────────────────
    checks = {**base_checks, **bonus_checks,
              "_quality": quality,
              "_fields_present": base_fields_present}
    total_score = base_score + bonus_score
    return base_score, bonus_score, total_score, quality, checks


# -----------------------------------------------------------------------------
# EDGE DETECTION: all three edges, DataFrame-based, signal hold window
# -----------------------------------------------------------------------------
# REV-CB pillar funnel diagnostic (reset per run via reset_cb_funnel()).
_CB_FUNNEL = {"eligible": 0, "p1": 0, "p1_p2": 0, "p1_p3": 0, "p1_p2_p3": 0, "p3_alone": 0}

def reset_cb_funnel():
    for k in _CB_FUNNEL: _CB_FUNNEL[k] = 0


def check_rev_cb(ind: dict) -> dict:
    """
    REV-CB: Four-Pillar Climax Bottom Bounce (v1.2 — price-action pillars).

    Pillar 1: Drawdown    : close ≥ cb_drawdown_pct below rolling 60-bar high
                            (was: close ≤ SMA200 × (1 − stretch). SMA200 lags the
                             actual selloff; a 60-bar drawdown captures the shock
                             as it happens.)
    Pillar 2: Washout     : ≥ cb_washout_red_count of last cb_washout_window bars
                            closed red (c<o) AND today closes in bottom 25% of
                            10-day range. (was: RSI14<30 AND RSI3<15. RSI is
                            smoothed; bar-color count and range position fire on
                            the climax bar itself.)
    Pillar 3: Climax Vol  : volume ≥ cb_vol_mult × 50D avg AND close < open AND
                            range ≥ widest range in cb_range_lookback bars.
                            (v1.3: tightened from OR → AND. Pine v1.4 line 720
                             requires all three to fire — eliminates "fake"
                             climax bars that have volume + only one of
                             bearish/wide.)
    Pillar 4: Turn        : green bar, closes top 40% of range, breaks prior day
                            high. Unchanged — already pure price action.

    Signal = 2 (Buy)   if climax detected + turn fired within signal_hold_days
    Signal = 1 (Watch) if climax detected but no turn yet
    Signal = 0         if no climax in the window, or both expired
    """
    hold  = CONFIG["signal_hold_days"]
    cwin  = CONFIG["cb_climax_window"]
    vm    = CONFIG["cb_vol_mult"]
    dd    = CONFIG["cb_drawdown_pct"] / 100
    lb_h  = CONFIG["cb_lookback_high_days"]
    w_win = CONFIG["cb_washout_window"]
    w_red = CONFIG["cb_washout_red_count"]
    r_lb  = CONFIG["cb_range_lookback"]
    n     = cwin + hold + 5          # total detection-window slice

    # Compute pillar flags on the FULL series so rolling windows have enough data,
    # then slice the last n bars for climax detection.
    c_full = ind["close"]; h_full = ind["high"]; l_full = ind["low"]
    o_full = ind["open"];  v_full = ind["volume"]; vm_full = ind["vol_ma"]

    # Pillar 1: drawdown from rolling 60-bar high
    lookback_high = h_full.rolling(lb_h).max()
    drawdown      = (lookback_high - c_full) / lookback_high.replace(0, np.nan)
    p1_full       = drawdown >= dd

    # Pillar 2: red-bar count + range position (pure price)
    red           = (c_full < o_full).astype(int)
    red_count     = red.rolling(w_win).sum()
    range10_h     = h_full.rolling(10).max()
    range10_l     = l_full.rolling(10).min()
    range10       = (range10_h - range10_l).replace(0, np.nan)
    pos_in_range  = (c_full - range10_l) / range10
    p2_full       = (red_count >= w_red) & (pos_in_range <= 0.25)

    # Pillar 3 (v1.3): relative volume AND bearish AND widest bar in N
    # (was: vol AND (bearish OR widest) — too loose. Pine v1.4 line 720 requires
    #  all three: panic volume + close<open + range = max-of-N. Eliminates "fake"
    #  climaxes that fire on volume + only one of bearish/wide.)
    bar_range     = h_full - l_full
    # v2.4 sync (B2): shift(1) excludes current bar from the rolling max so the
    # comparison isn't tautological (was: range_max includes current bar -> always
    # bar_range >= range_max for the bar that IS the max; tightens with strict >)
    range_max_n   = bar_range.rolling(r_lb).max().shift(1)
    p3_full       = (v_full >= vm * vm_full) & (c_full < o_full) & (bar_range > range_max_n)

    df = pd.DataFrame({
        "c": c_full, "h": h_full, "l": l_full, "o": o_full,
        "p1": p1_full, "p2": p2_full, "p3": p3_full,
    }).iloc[-n:]
    df["climax"] = df["p1"] & df["p2"] & df["p3"]

    # Diagnostic funnel — where does the climax detection collapse across the
    # universe? (counts per-symbol: did ANY bar in the slice fire each combo)
    try:
        _CB_FUNNEL["eligible"]    += 1
        _CB_FUNNEL["p1"]          += 1 if df["p1"].any() else 0
        _CB_FUNNEL["p1_p2"]       += 1 if (df["p1"] & df["p2"]).any() else 0
        _CB_FUNNEL["p1_p3"]       += 1 if (df["p1"] & df["p3"]).any() else 0
        _CB_FUNNEL["p1_p2_p3"]    += 1 if df["climax"].any() else 0
        _CB_FUNNEL["p3_alone"]    += 1 if df["p3"].any() else 0
    except Exception:
        pass

    climax_rows = df[df["climax"]]
    if climax_rows.empty:
        return {"signal": 0, "signal_date": None, "climax_date": None,
                "climax_low": np.nan, "details": "No climax bar detected"}

    climax_date = climax_rows.index[-1]    # most recent climax bar
    loc_climax  = df.index.get_loc(climax_date)
    bars_since_climax = len(df) - 1 - loc_climax

    if bars_since_climax > cwin:
        return {"signal": 0, "signal_date": None, "climax_date": climax_date,
                "climax_low": np.nan,
                "details": f"Climax expired ({bars_since_climax}d ago > {cwin}d window)"}

    # Climax zone low (for SL anchor)
    climax_low = df["l"].iloc[max(0, loc_climax - 4): loc_climax + 1].min()

    # Look for turn candle in bars AFTER the climax (up to today)
    post = df.iloc[loc_climax + 1:].copy()
    if post.empty:
        return {"signal": 1, "signal_date": None, "climax_date": climax_date,
                "climax_low": climax_low,
                "details": f"Climax active ({bars_since_climax}d ago): waiting for turn"}

    post["prev_h"] = df["h"].shift(1).reindex(post.index)
    post["range"]  = post["h"] - post["l"]
    turn_mask = (
        (post["c"] > post["o"]) &
        (post["range"] > 0) &
        ((post["c"] - post["l"]) / post["range"] >= 0.60) &
        (post["c"] > post["prev_h"])
    )
    turn_rows = post[turn_mask]

    if turn_rows.empty:
        return {"signal": 1, "signal_date": None, "climax_date": climax_date,
                "climax_low": climax_low,
                "details": f"Climax active ({bars_since_climax}d ago): no turn yet"}

    turn_date = turn_rows.index[-1]
    loc_turn  = df.index.get_loc(turn_date)
    bars_since_turn = len(df) - 1 - loc_turn

    if bars_since_turn > hold:
        return {"signal": 0, "signal_date": turn_date, "climax_date": climax_date,
                "climax_low": climax_low,
                "details": f"Turn expired ({bars_since_turn}d ago > {hold}d hold window)"}

    return {"signal": 2, "signal_date": turn_date, "climax_date": climax_date,
            "climax_low": climax_low,
            "details": f"CB buy: climax {bars_since_climax}d ago, turn {bars_since_turn}d ago"}


def check_rev_rs(ind: dict, rs_positive: bool, regime_ok: bool,
                 stock_corrected: bool = True) -> dict:
    """
    REV-RS: RS Survivor Structural Breakout (v1.2 — price-action today-check).

    Conditions (any of the last signal_hold_days bars):
       close > highest high of prior rs_bo_len days  (20D structural breakout — pure price)
       volume >= vol_confirm_mult × 50D avg           (relative volume)
    AND today's higher-low structure is intact:
       lowest low of last rs_hl_recent bars  >
       lowest low of bars rs_hl_recent+rs_hl_prior → rs_hl_recent ago
       (pure price structure — replaces "close > SMA50 today" lagging filter).

    v1.4: stock_corrected gate added (Pine v2.3 line 1205). Requires the stock
          itself to be in the 10-40% correction band from its 52W high — not
          just the market. This prevents REV-RS from firing on non-corrected
          stocks that pass regime_ok via the market path.
    """
    if not rs_positive:
        return {"signal": 0, "signal_date": None, "details": "RS slope negative"}
    if not regime_ok:
        return {"signal": 0, "signal_date": None, "details": "Regime gate failed"}
    # v1.4 Fix #2: stock_corrected standalone gate (Pine v2.3 line 1205)
    if not stock_corrected:
        return {"signal": 0, "signal_date": None, "details": "Stock not in 10-40% correction band"}

    hold   = CONFIG["signal_hold_days"]
    bo_len = CONFIG["rs_bo_len"]
    vm     = CONFIG["vol_confirm_mult"]
    hl_r   = CONFIG["rs_hl_recent"]
    hl_p   = CONFIG["rs_hl_prior"]

    c_s    = ind["close"]
    h_s    = ind["high"]
    l_s    = ind["low"]
    vol_s  = ind["volume"]
    vm_s   = ind["vol_ma"]
    n      = len(c_s)

    # Higher-low structure today (price-action trend filter)
    if n < hl_r + hl_p + 1:
        return {"signal": 0, "signal_date": None, "details": "Insufficient history for HL check"}
    recent_low = float(l_s.iloc[-hl_r:].min())
    prior_low  = float(l_s.iloc[-(hl_r + hl_p) : -hl_r].min())
    if not (recent_low > prior_low):
        return {"signal": 0, "signal_date": None,
                "details": f"No higher-low structure (recent {recent_low:.2f} <= prior {prior_low:.2f})"}

    # v1.3: Strict-trend pivot gate (Pine v1.4 alignment — f_getStrictTrend port)
    # HH+HL pivot zigzag with piv_d_right=2 → confirms 2 bars after the pivot.
    # Requires the most recent confirmed trend to be UP (dtrend == 1).
    dtrend = compute_strict_trend(h_s, l_s,
                                   piv_left=CONFIG.get("piv_d_left", 2),
                                   piv_right=CONFIG.get("piv_d_right", 2))
    dtrend_now = int(dtrend.iloc[-1]) if not dtrend.empty and not pd.isna(dtrend.iloc[-1]) else 0
    if dtrend_now != 1:
        return {"signal": 0, "signal_date": None,
                "details": f"Strict-trend not confirmed UP (dtrend={dtrend_now})"}

    found_date = None
    days_ago   = None
    for i in range(hold, 0, -1):         # oldest → newest within hold window
        pos = n - i                       # absolute 0-indexed position
        if pos < bo_len + 1:
            continue
        c_i   = c_s.iloc[pos]
        vol_i = vol_s.iloc[pos]
        vm_i  = vm_s.iloc[pos]
        if any(pd.isna([c_i, vm_i])) or vm_i == 0:
            continue
        bo_high = h_s.iloc[pos - bo_len: pos].max()   # highest high of PRIOR bo_len bars
        # v1.2: dropped `c_i > s50_i` — replaced by today's higher-low gate above.
        if c_i > bo_high and (vol_i / vm_i) >= vm:
            found_date = c_s.index[pos]
            days_ago   = i - 1                         # 0 = today, 1 = yesterday, ...

    if found_date is None:
        return {"signal": 0, "signal_date": None,
                "details": f"No RS breakout in last {hold} trading days"}

    return {"signal": 3, "signal_date": found_date,
            "details": f"RS breakout {days_ago}d ago, higher-low intact"}


def check_rev_early(ind: dict, rs_positive: bool, regime_ok: bool) -> dict:
    """
    REV-EARLY: Early Bird Trendline Reclaim + Base Compression (v1.2).

    Conditions (any of the last signal_hold_days bars):
       close > highest high of prior early_pivot_len days          (15D pivot breakout — pure price)
       close > highest high of bars [trendline_recent+window, trendline_recent] ago
                                                                    (trendline reclaim — break of prior swing-high shelf,
                                                                     replaces "SMA50 within 5% of SMA200" near-GC lagging check)
       base compression: NR7 (narrowest range in 7 bars)
                         OR ≥ early_inside_count_min inside bars in last early_inside_lookback
                                                                    (replaces ATR-based VCP — pure price structure)
       5D vol avg BEFORE the bar < 50D vol avg                      (VCP dry-up, kept)
       volume >= vol_confirm_mult × 50D avg                         (breakout volume)
    AND today's higher-low structure is intact (pure price):
       lowest low of last rs_hl_recent bars > lowest low of prior rs_hl_prior bars.

    Rationale: near-GC fires WELL after recovery has begun (SMA50/SMA200 are
    the two most lagging indicators in retail TA). A trendline reclaim fires
    the bar the stock breaks its multi-week downtrend — which IS early-bird
    timing. NR7 and inside-bar counts react to the same tightness ATR picks
    up, but without the 10/50-bar smoothing lag.
    """
    if not rs_positive:
        return {"signal": 0, "signal_date": None, "details": "RS slope negative"}
    if not regime_ok:
        return {"signal": 0, "signal_date": None, "details": "Regime gate failed"}

    hold     = CONFIG["signal_hold_days"]
    piv_len  = CONFIG["early_pivot_len"]
    vm       = CONFIG["vol_confirm_mult"]
    tl_rec   = CONFIG["early_trendline_recent"]
    tl_win   = CONFIG["early_trendline_window"]
    nr7_len  = CONFIG["early_nr7_len"]
    in_lb    = CONFIG["early_inside_lookback"]
    in_min   = CONFIG["early_inside_count_min"]
    hl_r     = CONFIG["rs_hl_recent"]
    hl_p     = CONFIG["rs_hl_prior"]

    c_s    = ind["close"]
    h_s    = ind["high"]
    l_s    = ind["low"]
    vol_s  = ind["volume"]
    vm_s   = ind["vol_ma"]
    n      = len(c_s)

    # Today's higher-low structure (price-action replacement for near-GC + MA stack)
    if n < hl_r + hl_p + 1:
        return {"signal": 0, "signal_date": None, "details": "Insufficient history for HL check"}
    recent_low = float(l_s.iloc[-hl_r:].min())
    prior_low  = float(l_s.iloc[-(hl_r + hl_p) : -hl_r].min())
    if not (recent_low > prior_low):
        return {"signal": 0, "signal_date": None,
                "details": f"No higher-low structure (recent {recent_low:.2f} <= prior {prior_low:.2f})"}

    # v1.4 Fix #3: Strict-trend pivot gate for REV-EARLY (Pine v2.3 line 1219).
    # Pine requires rs_recovery_state = higher_low_ok AND trend_up for BOTH
    # REV-RS and REV-EARLY. v1.3 only applied this to REV-RS.
    dtrend = compute_strict_trend(h_s, l_s,
                                   piv_left=CONFIG.get("piv_d_left", 2),
                                   piv_right=CONFIG.get("piv_d_right", 2))
    dtrend_now = int(dtrend.iloc[-1]) if not dtrend.empty and not pd.isna(dtrend.iloc[-1]) else 0
    if dtrend_now != 1:
        return {"signal": 0, "signal_date": None,
                "details": f"Strict-trend not confirmed UP (dtrend={dtrend_now})"}

    # Pre-compute inside-bar flags (needed per-bar inside the loop)
    inside_full = (h_s < h_s.shift(1)) & (l_s > l_s.shift(1))

    found_date = None
    days_ago   = None
    for i in range(hold, 0, -1):
        pos = n - i
        if pos < max(piv_len, tl_rec + tl_win, in_lb, nr7_len) + 6:
            continue

        c_i   = c_s.iloc[pos]
        vol_i = vol_s.iloc[pos]
        vm_i  = vm_s.iloc[pos]

        if any(pd.isna([c_i, vm_i])) or vm_i == 0:
            continue

        # Trendline reclaim: close > highest high of bars [tl_rec+tl_win, tl_rec] ago.
        # This is the "prior swing-high shelf" — by breaking it we reclaim the
        # downtrend line connecting the last cluster of lower highs.
        tl_slice = h_s.iloc[pos - (tl_rec + tl_win) : pos - tl_rec]
        if tl_slice.empty:
            continue
        tl_high = tl_slice.max()
        if not (c_i > tl_high):
            continue

        # Pivot breakout (15-day high)
        piv_high = h_s.iloc[pos - piv_len: pos].max()
        if not (c_i > piv_high):
            continue

        # Base compression: NR7 OR ≥N inside bars in last 10
        bar_range_i = h_s.iloc[pos] - l_s.iloc[pos]
        ranges_n    = (h_s.iloc[pos - nr7_len + 1 : pos + 1] -
                       l_s.iloc[pos - nr7_len + 1 : pos + 1])
        is_nr7      = bar_range_i <= ranges_n.min()
        inside_count = int(inside_full.iloc[pos - in_lb : pos].sum())
        if not (is_nr7 or inside_count >= in_min):
            continue

        # VCP dry-up: 5D vol average BEFORE this bar (kept — structural & correct)
        vol5_pre = vol_s.iloc[pos - 5: pos].mean()
        if not (vol5_pre < vm_i):
            continue

        # Volume expansion on breakout
        if not ((vol_i / vm_i) >= vm):
            continue

        found_date = c_s.index[pos]
        days_ago   = i - 1

    if found_date is None:
        return {"signal": 0, "signal_date": None,
                "details": f"No EARLY breakout in last {hold} trading days"}

    return {"signal": 4, "signal_date": found_date,
            "details": f"EARLY trendline reclaim {days_ago}d ago, base compressed"}


# -----------------------------------------------------------------------------
# COMPOSITE SCORE  (0-22)
#
# v2.0 (11 May 2026): expanded fundamentals slot from 0-6 to 0-8 to absorb the
# new RFF Tier-B bonus (capped at +2 of the 4 possible bonus points so a
# fundamentally weak but momentum-strong stock can't dominate purely on
# bonus). The legacy `rff` argument now accepts the **total** (base 0-6 +
# bonus 0-4) — old callers passing only base still produce identical scores
# because bonus would be 0.
# -----------------------------------------------------------------------------
def compute_score(signal: int, rff: int, rs_val: float,
                  corr_pct: float, mkt_recovery: bool,
                  mkt_corrected: bool, stage: int, rel_vol: float,
                  chartink_confirmed: bool = False) -> int:
    s = 0
    s += min(rff, 8)                             # fundamentals  0-8 (was 0-6)
    if rs_val > 0:     s += 1                    # positive RS   0-1
    if rs_val >= 10.0: s += 1                    # strong RS     0-1 (v1.3: ×100 scale, 10.0 = 10% outperformance vs benchmark)
    if corr_pct >= 30: s += 3                    # deep discount 0-3
    elif corr_pct >= 20: s += 2
    elif corr_pct >= 10: s += 1
    if mkt_recovery:   s += 2                    # regime        0-2
    elif mkt_corrected: s += 1
    if stage in (1, 2): s += 1                   # Weinstein     0-1
    if signal >= 2:    s += 3                    # edge fired    0-3
    elif signal == 1:  s += 1
    if signal >= 2 and rel_vol >= 3.0: s += 2   # vol strength  0-2
    elif signal >= 2 and rel_vol >= 2.0: s += 1
    if chartink_confirmed: s += 1               # intersection: in both Chartink + Screener.in  0-1
    return s


# -----------------------------------------------------------------------------
# EXIT LEVELS
# -----------------------------------------------------------------------------
def compute_exit_levels(ind: dict, signal: int, climax_low: float = np.nan) -> dict:
    """
    REV-CB  : SL = climax zone low - 0.5ATR  |  T1 = EMA20  |  T2 = SMA200
    REV-RS/E: SL = 10D low - 0.2ATR          |  T1 = 2.5R   |  T2 = 52W High
    """
    c     = ind["close"].iloc[-1]
    atr   = ind["atr14"].iloc[-1]
    ema20 = ind["ema20"].iloc[-1]
    s200  = ind["sma200"].iloc[-1]
    h52w  = ind["high52w"].iloc[-1]
    low10 = ind["low"].iloc[-10:].min()

    if signal == 2 and not np.isnan(climax_low):
        sl = climax_low - atr * 0.5
    else:
        sl = low10 - atr * 0.2

    if sl >= c:                             # safety floor: SL must be below close
        # v1.6 (2026-05-21): widened fallback from 1.5x to 2.5x daily ATR.
        # REV-* trades are 90-day holds; a 1.5x daily-ATR floor gets knocked
        # out within days on routine volatility.
        sl = c - atr * 2.5

    risk = max(c - sl, c * 0.005)
    t1   = ema20 if signal == 2 else c + risk * 2.5
    t2   = s200  if signal == 2 else h52w

    return {
        "Entry"  : round(c, 2),
        "SL"     : round(sl, 2),
        "T1"     : round(t1, 2),
        "T2"     : round(t2, 2),
        "RR_T1"  : round((t1 - c) / risk, 2)   if risk > 0 else None,
        "T1_pct" : round((t1 - c) / c * 100, 2) if c > 0 else None,
        "SL_pct" : round((c - sl) / c * 100, 2) if c > 0 else None,
    }


# -----------------------------------------------------------------------------
# SINGLE-SYMBOL SCREENER
# -----------------------------------------------------------------------------
def screen_symbol(symbol: str, edge_hint: str, regime: dict,
                  df_cnx500_w: pd.DataFrame, screener_row: dict | None,
                  chartink_confirmed: bool = False) -> dict:
    """Download OHLCV, compute all indicators, run all 3 edges, score, exit levels."""

    blank = dict(
        Symbol=symbol, Edge_Hint=edge_hint,
        Signal=0, Signal_Label="None", Signal_Date=None,
        Score=0, RFF_Score=0, RFF_Base=0, RFF_Bonus=0, RFF_Total=0,
        RFF_Quality="INSUFFICIENT", Chartink_Confirmed=chartink_confirmed,
        Weinstein_Stage=0, Mansfield_RS_x100=None, RS_Momentum_4W=None, RRG_Quadrant="n/a", RS_Slope_4W=None, RS_Positive=False,
        Stretch_SMA200_pct=None, Correction_52W_pct=None,
        Rel_Vol=None, RSI14=None, RSI3=None,
        Regime_OK=False,
        Mkt_Recovery=regime["mkt_in_recovery"],
        Mkt_Corrected=regime["mkt_corrected"],
        Mkt_Reclaim=regime.get("mkt_reclaim", False),
        Mkt_Corr_Depth_pct=regime["mkt_corr_pct"],
        Entry=None, SL=None, T1=None, T2=None,
        RR_T1=None, T1_pct=None, SL_pct=None,
        Signal_Date_CB=None, Details="",
    )

    yf_sym = to_yf(symbol)

    # -- 1. Download daily OHLCV (C1: cached via data_provider when available)
    try:
        if USE_DATA_PROVIDER and _dp is not None:
            df_d = _flatten_cols(
                _dp.fetch_ohlcv(symbol,
                                  period=f"{CONFIG['data_lookback_days']}d",
                                  interval="1d")
            )
        else:
            df_d = _flatten_cols(
                yf.download(yf_sym, period=f"{CONFIG['data_lookback_days']}d",
                            interval="1d", auto_adjust=True, progress=False)
            )
        if df_d.empty or len(df_d) < 60:
            blank["Details"] = "Insufficient daily data"
            return blank
    except Exception as e:
        blank["Details"] = f"Download error: {e}"
        return blank

    # -- 2. Download weekly OHLCV (covers both Mansfield RS and Weinstein Stage)
    try:
        if USE_DATA_PROVIDER and _dp is not None:
            df_w = _flatten_cols(_dp.fetch_ohlcv(symbol, period="3y", interval="1wk"))
        else:
            df_w = _flatten_cols(
                yf.download(yf_sym, period="3y", interval="1wk",
                            auto_adjust=True, progress=False)
            )
    except Exception:
        df_w = pd.DataFrame()

    # -- 3. Indicators --------------------------------------------------------
    ind = compute_indicators(df_d)

    # -- 4. Liquidity gate ----------------------------------------------------
    turnover_cr = float(ind["close"].iloc[-1] * ind["volume"].iloc[-1]) / 1e7
    if turnover_cr < CONFIG["min_daily_turnover_cr"]:
        blank["Details"] = f"Below liquidity gate ({turnover_cr:.1f} Cr today)"
        return blank

    # -- 5. Current-bar metrics -----------------------------------------------
    c_now    = float(ind["close"].iloc[-1])
    s200_now = float(ind["sma200"].iloc[-1])
    h52w_now = float(ind["high52w"].iloc[-1])
    r14_now  = float(ind["rsi14"].iloc[-1])
    r3_now   = float(ind["rsi3"].iloc[-1])
    rv_now   = float(ind["rel_vol"].iloc[-1]) if not np.isnan(ind["rel_vol"].iloc[-1]) else 0.0

    stretch200  = (c_now - s200_now) / s200_now * 100 if s200_now > 0 else np.nan
    corr_52w    = (h52w_now - c_now) / h52w_now * 100 if h52w_now > 0 else np.nan

    # v1.3: 3-way regime gate (Pine v1.4 alignment).
    #   Path A: market index corrected ≥7% off 52W high  → trade any non-distressed quality stock
    #   Path B: market index reclaimed SMA50 in last 30 bars  → trade any non-distressed quality stock
    #   Path C: stock itself in 10-40% correction band  → idiosyncratic recovery setup
    # Universal quality cap: stock_correction ≤ 40% (>40% = distressed, not discounted)
    not_distressed     = (not np.isnan(corr_52w)) and corr_52w <= CONFIG["max_stock_correction_pct"]
    stock_corr_in_band = (not np.isnan(corr_52w)) and corr_52w >= CONFIG["min_stock_correction_pct"] and corr_52w <= CONFIG["max_stock_correction_pct"]
    mkt_path_open      = bool(regime.get("mkt_corrected", False) or regime.get("mkt_reclaim", False))
    if not CONFIG.get("use_regime_gate", True):
        regime_ok = True
    elif mkt_path_open:
        # Market in recovery/reclaim — gate opens for any non-distressed stock
        regime_ok = not_distressed
    else:
        # Market not in recovery — only fire on stock-specific correction in 10-40% band
        regime_ok = stock_corr_in_band
    stock_corr = stock_corr_in_band  # legacy name kept for downstream readability

    # -- 6. Relative Strength -------------------------------------------------
    # v1.3: gating metric = 26wk Mansfield ×100 (Pine v1.4 alignment, RRG-compatible).
    #       rs_slope_w (4w ROC) demoted to a SECONDARY score column for tiebreaking.
    #       New: rs_momentum_4w (4-bar diff of Mansfield) for RRG second axis.
    rs_val          = compute_mansfield_rs(df_w, df_cnx500_w) if not df_w.empty else np.nan
    rs_slope        = compute_rs_slope_w(df_w, df_cnx500_w, CONFIG["rs_slope_weeks"]) if not df_w.empty else np.nan
    # Compute rs_momentum_4w by reading the FULL Mansfield series (not just the last value)
    rs_mansfield_series = compute_mansfield_series(df_w, df_cnx500_w) if not df_w.empty else pd.Series(dtype=float)
    if len(rs_mansfield_series) > CONFIG["rs_momentum_weeks"]:
        rs_momentum_4w = float(rs_mansfield_series.iloc[-1] - rs_mansfield_series.iloc[-1 - CONFIG["rs_momentum_weeks"]])
    else:
        rs_momentum_4w = np.nan
    rs_pos          = (not np.isnan(rs_val)) and rs_val > 0       # v1.3: gate on Mansfield > 0 (was: rs_slope > 0)

    # RRG quadrant classifier (Pine v1.4 alignment)
    rs_quadrant = (
        "n/a"        if (np.isnan(rs_val) or np.isnan(rs_momentum_4w)) else
        "LEADING"    if rs_val > 0 and rs_momentum_4w > 0 else
        "WEAKENING"  if rs_val > 0 and rs_momentum_4w <= 0 else
        "LAGGING"    if rs_val <= 0 and rs_momentum_4w <= 0 else
        "IMPROVING"
    )

    # -- 7. Weinstein Stage (weekly) ------------------------------------------
    stage = compute_weinstein_stage(df_w) if not df_w.empty else 0

    # -- 8. RFF (full 6-check) ------------------------------------------------
    fund_source = "Screener.in"
    if screener_row is None:
        # Screener.in has no row for this stock — fall back to yfinance .info
        yf_fund = fetch_yf_fundamentals(yf_sym)
        if yf_fund:
            screener_row = yf_fund
            fund_source  = "yfinance"
        else:
            fund_source  = "unavailable"

    # v2.0 RFF: returns (base 0-6, bonus 0-4, total 0-10, quality, checks)
    if screener_row:
        rff_base, rff_bonus, rff_total, rff_quality, rff_checks = compute_rff(screener_row)
    else:
        rff_base, rff_bonus, rff_total, rff_quality, rff_checks = (0, 0, 0, "INSUFFICIENT", {})
    # Back-compat: legacy callers/columns expect a single rff_score (0-6, base only).
    rff_score = rff_base
    # Gate uses the BASE score (Pine parity) so behaviour matches Pine v2.2.
    rff_ok = (CONFIG["rff_min_score"] == 0
              or (rff_quality != "INSUFFICIENT" and rff_base >= CONFIG["rff_min_score"]))

    # -- 9. Edge detection ----------------------------------------------------
    # Pass regime_ok only: rff_ok is applied below at the priority selection level.
    # This way the edge functions correctly report "no breakout" vs "regime failed"
    # even when no Screener.in fundamental data is available.
    cb_res    = check_rev_cb(ind)
    rs_res    = check_rev_rs(ind, rs_pos, regime_ok, stock_corrected=stock_corr)
    early_res = check_rev_early(ind, rs_pos, regime_ok)

    # Priority: EARLY 4 > RS 3 > CB-Buy 2 > CB-Watch 1 > None 0
    # v1.4 Fix #1: REV-CB now gated on regime_ok (Pine v2.3 line 1196).
    sig = 0; sig_date = None; sig_label = "None"; details = ""; climax_low = np.nan

    if early_res["signal"] == 4 and rff_ok:
        sig, sig_date, sig_label = 4, early_res["signal_date"], "REV-EARLY"
        details = early_res["details"]
    elif rs_res["signal"] == 3 and rff_ok:
        sig, sig_date, sig_label = 3, rs_res["signal_date"], "REV-RS"
        details = rs_res["details"]
    elif cb_res["signal"] == 2 and rff_ok and regime_ok:  # v1.4: + regime_ok
        sig, sig_date, sig_label = 2, cb_res["signal_date"], "REV-CB"
        details   = cb_res["details"]
        climax_low = cb_res["climax_low"]
    elif cb_res["signal"] == 1:
        sig, sig_label = 1, "CB-Watch"
        details = cb_res["details"]
    else:
        parts = [r["details"] for r in [early_res, rs_res, cb_res] if r["details"]]
        details = " | ".join(parts)

    if sig >= 2 and fund_source == "unavailable":
        details += " [RFF not verified: no fundamental data from Screener.in or yfinance]"
    elif sig >= 2 and rff_quality == "INSUFFICIENT":
        details += " [RFF INSUFFICIENT: <3 base fields populated]"
    elif sig >= 2 and fund_source == "yfinance":
        details += (f" [RFF via yfinance — base {rff_base}/6, bonus {rff_bonus}/4, "
                    f"total {rff_total}/10, quality {rff_quality}]")
    elif sig >= 2:
        details += (f" [RFF base {rff_base}/6, bonus {rff_bonus}/4, "
                    f"total {rff_total}/10, quality {rff_quality}]")
    if chartink_confirmed:
        details += " [Also in Screener.in screens — intersection]"

    # -- 10. Score ------------------------------------------------------------
    score = compute_score(
        sig, rff_total, rs_val if not np.isnan(rs_val) else 0.0,
        corr_52w if not np.isnan(corr_52w) else 0.0,
        regime["mkt_in_recovery"], regime["mkt_corrected"],
        stage, rv_now, chartink_confirmed,
    )

    # -- 11. Exit levels ------------------------------------------------------
    exits = compute_exit_levels(ind, sig, climax_low)

    return dict(
        Symbol       = symbol,
        Edge_Hint    = edge_hint,
        Signal       = sig,
        Signal_Label = sig_label,
        Signal_Date  = str(sig_date.date()) if sig_date is not None else None,
        Score        = score,
        RFF_Score    = rff_score,             # = RFF_Base (back-compat)
        RFF_Base     = rff_base,              # 0-6, Pine-parity gate
        RFF_Bonus    = rff_bonus,             # 0-4, recovery-specific top-up
        RFF_Total    = rff_total,             # 0-10, used for ranking
        RFF_Quality  = rff_quality,           # FULL / PARTIAL / INSUFFICIENT
        Chartink_Confirmed = chartink_confirmed,
        RFF_Detail   = str({k: v for k, v in rff_checks.items()
                             if not str(k).startswith("_") and v}) if rff_checks else "",
        Weinstein_Stage       = stage,
        Mansfield_RS_x100     = round(rs_val, 3)   if not np.isnan(rs_val)   else None,   # v1.3: ×100 textbook scale (was Mansfield_RS ×10)
        RS_Momentum_4W        = round(rs_momentum_4w, 3) if not np.isnan(rs_momentum_4w) else None,  # v1.3: RRG second axis
        RRG_Quadrant          = rs_quadrant,                                                          # v1.3: LEADING/WEAKENING/LAGGING/IMPROVING
        RS_Slope_4W           = round(rs_slope, 2) if not np.isnan(rs_slope) else None,   # v1.3: demoted to secondary score column
        RS_Positive           = rs_pos,
        Stretch_SMA200_pct    = round(stretch200, 2) if not np.isnan(stretch200) else None,
        Correction_52W_pct    = round(corr_52w, 2)   if not np.isnan(corr_52w)   else None,
        Rel_Vol               = round(rv_now, 2),
        RSI14                 = round(r14_now, 1),
        RSI3                  = round(r3_now, 1),
        Regime_OK             = regime_ok,
        Mkt_Recovery          = regime["mkt_in_recovery"],
        Mkt_Corrected         = regime["mkt_corrected"],
        Mkt_Reclaim           = regime.get("mkt_reclaim", False),
        Mkt_Corr_Depth_pct    = regime["mkt_corr_pct"],
        CB_Climax_Date = str(cb_res["climax_date"].date()) if cb_res.get("climax_date") is not None else None,
        **exits,
        Details = details,
    )


# -----------------------------------------------------------------------------
# INPUT LOADERS
# -----------------------------------------------------------------------------
def load_candidates() -> list:
    """Return (symbol, edge_hint) candidates from Chartink recovery CSVs. De-duplicated.

    Architecture:
      Chartink scans 5-7 are the TECHNICAL PRE-FILTER — they produce a tight list of
      NSE stocks that passed real-time technical criteria. The Python screener then
      applies strict signal-hold-window logic on top.

      Screener.in recovery CSVs (SCREENER_FILES) are used ONLY as a fundamentals
      lookup table (via load_fundamentals). A Chartink stock that also appears in
      the Screener.in screen gets a full RFF score; one that doesn't gets RFF=0.
      The intersection (both sources) = highest conviction → gets a score bonus.

    Run chartink_scanner_pro.py scans 5-7 before this script.
    Run screener_fetcher + screener_processor to populate the RFF lookup.
    """
    candidates, seen = [], set()
    skipped = []

    def _valid_sym(s: str) -> bool:
        """Reject non-NSE symbols: numeric BSE codes, ISINs, long garbage strings."""
        if not s:
            return False
        if s.isdigit():                              # unmapped BSE scrip codes (513119…)
            return False
        if all(c.isdigit() or c == "-" for c in s): # digit-hyphen BSE patterns
            return False
        if s.startswith("INE") and len(s) == 12:    # ISIN codes
            return False
        if len(s) > 20:                              # HTML parse artefacts
            return False
        return True

    _EDGE_SCAN = {"REV-RS": "5", "REV-CB": "6", "REV-EARLY": "7"}
    for edge, fname in CHARTINK_FILES.items():
        fpath = os.path.join(DATA_DIR, fname)
        if not os.path.exists(fpath):
            print(f"  WARN  {fname} not found — run chartink_scanner_pro.py scan {_EDGE_SCAN.get(edge, '5-7')}")
            continue
        try:
            df = pd.read_csv(fpath)
            if "Symbol" not in df.columns:
                print(f"  WARN  {fname} has no Symbol column: skipping")
                continue
            syms = df["Symbol"].dropna().astype(str).str.strip().str.upper().unique()
            added = 0
            for s in syms:
                if not _valid_sym(s):
                    skipped.append(s)
                    continue
                if s not in seen:
                    candidates.append((s, edge))
                    seen.add(s)
                    added += 1
            print(f"    {edge}: {added} stocks from {fname}")
        except Exception as e:
            print(f"  WARN  Error reading {fname}: {e}")

    if skipped:
        print(f"  Skipped {len(set(skipped))} invalid symbols (numeric/BSE): "
              f"{', '.join(sorted(set(skipped))[:10])}" + (" ..." if len(set(skipped)) > 10 else ""))
    if not candidates:
        print("  WARN  No Screener.in recovery CSVs found — RFF will be 0 for all stocks.")
    print(f"  Total candidates: {len(candidates)}")
    return candidates


def load_screener_symbols() -> set:
    """Return set of all symbols present in the Screener.in recovery CSVs.
    Used by main() to identify Chartink candidates that are ALSO in Screener.in
    screens — these are the intersection stocks (highest conviction, full RFF)."""
    si_syms = set()
    for _, fname in SCREENER_FILES.items():
        fpath = os.path.join(DATA_DIR, fname)
        if not os.path.exists(fpath):
            continue
        try:
            df = pd.read_csv(fpath)
            sym_col = next((c for c in df.columns if c.lower() in ("symbol", "nsecode", "ticker")), None)
            if sym_col:
                si_syms.update(df[sym_col].dropna().astype(str).str.strip().str.upper())
        except Exception:
            pass
    return si_syms


def load_fundamentals() -> dict:
    """Load Screener.in fundamental CSVs  {symbol: row_dict}."""
    fund = {}
    for edge, fname in SCREENER_FILES.items():
        fpath = os.path.join(DATA_DIR, fname)
        if not os.path.exists(fpath):
            continue
        try:
            df = pd.read_csv(fpath)
            # Screener.in exports column headers with embedded \n + spaces
            # e.g. "ROCE\n                    %" → normalise to "ROCE %"
            df.columns = [" ".join(str(c).replace("\n", " ").split()) for c in df.columns]
            if "Symbol" not in df.columns:
                continue
            for _, row in df.iterrows():
                sym = str(row["Symbol"]).strip().upper()
                if sym and sym not in fund:
                    fund[sym] = row.to_dict()
        except Exception as e:
            print(f"  WARN  Error reading {fname}: {e}")
    print(f"    Fundamentals loaded for {len(fund)} symbols "
          f"({'RFF will be 0-6' if fund else 'no Screener.in CSVs found: RFF skipped'})")
    return fund


# -----------------------------------------------------------------------------
# PROGRAMMATIC ENTRY POINT (called from weinstein_commander_web)
# -----------------------------------------------------------------------------
def run_recovery_screener(progress_callback=None, symbols=None,
                          out_file: str = OUTPUT_FILE,
                          strict: bool = False) -> pd.DataFrame:
    """Run the recovery screener and return results as a DataFrame.

    Parameters
    ----------
    progress_callback : callable(idx, total, sym), optional
        Called after each symbol is processed.
    symbols : list[str] | list[tuple[str,str]], optional
        Pre-loaded symbol list.  Each item may be a plain string (edge_hint
        defaults to "CUSTOM") or a (symbol, edge_hint) tuple.
        When *None* the function reads from the standard Chartink CSVs.
    out_file : str, optional
        CSV filename to save results (relative to DATA_DIR).
    """
    from datetime import datetime
    print(f"\n  RECOVERY SCREENER (programmatic)  {datetime.now().strftime('%d %b %Y %H:%M')}")

    # -- Build candidate list --------------------------------------------------
    if symbols is None:
        candidates = load_candidates()
    else:
        def _valid(s: str) -> bool:
            if not s or s.isdigit(): return False
            if s.startswith("INE") and len(s) == 12: return False
            return len(s) <= 20
        candidates = []
        seen: set = set()
        for item in symbols:
            if isinstance(item, (list, tuple)):
                sym, edge = str(item[0]).strip().upper(), str(item[1])
            else:
                sym, edge = str(item).strip().upper(), "CUSTOM"
            sym = sym.replace("NSE:", "").replace("BSE:", "").replace(".NS", "")
            if _valid(sym) and sym not in seen:
                candidates.append((sym, edge))
                seen.add(sym)

    if not candidates:
        print("  No candidates.")
        # 10 May 2026 fix: write a header-only CSV so the file timestamp
        # updates even when the input was empty. Lets the dashboard
        # distinguish "ran today, found nothing" from "never ran".
        _empty_cols = [
            "Symbol", "Signal", "Signal_Label", "Score",
            "RFF_Score", "RFF_Base", "RFF_Bonus", "RFF_Total", "RFF_Quality",
            "Mansfield_RS", "Entry", "SL", "T1", "RR_T1", "Details",
        ]
        try:
            pd.DataFrame(columns=_empty_cols).to_csv(
                os.path.join(DATA_DIR, out_file), index=False
            )
        except Exception:
            pass
        return pd.DataFrame(columns=_empty_cols)

    screener_syms = load_screener_symbols()
    fund_map      = load_fundamentals()

    print("  Downloading CNX500...")
    if USE_DATA_PROVIDER and _dp is not None:
        df_cnx_d = _flatten_cols(_dp.fetch_ohlcv(CNX500_YF, period="2y", interval="1d"))
        df_cnx_w = _flatten_cols(_dp.fetch_ohlcv(CNX500_YF, period="3y", interval="1wk"))
    else:
        df_cnx_d = _flatten_cols(yf.download(CNX500_YF, period="2y", interval="1d",
                                              auto_adjust=True, progress=False))
        df_cnx_w = _flatten_cols(yf.download(CNX500_YF, period="3y", interval="1wk",
                                              auto_adjust=True, progress=False))
    regime   = check_regime(df_cnx_d)

    total, results = len(candidates), []
    for idx, (symbol, edge_hint) in enumerate(candidates, 1):
        if progress_callback:
            progress_callback(idx, total, symbol)
        try:
            r = screen_symbol(symbol, edge_hint, regime, df_cnx_w,
                              fund_map.get(symbol),
                              chartink_confirmed=(symbol in screener_syms))
            results.append(r)
        except Exception as e:
            results.append({"Symbol": symbol, "Edge_Hint": edge_hint,
                            "Signal": 0, "Score": 0, "Details": str(e)})
        time.sleep(CONFIG["download_delay_sec"])

    df_out = pd.DataFrame(results)
    # strict=True (Nifty 500 / F&O / backtest-aligned scan) drops Signal=0 rows
    # so the output CSV contains only actionable (CB-Watch and above) candidates.
    # Default (strict=False) preserves all rows for tracker-style watchlist scans.
    if strict and not df_out.empty and "Signal" in df_out.columns:
        df_out = df_out[df_out["Signal"] >= 1].copy()
    if not df_out.empty:
        df_out.sort_values(["Signal", "Score"], ascending=[False, False], inplace=True)
        df_out.reset_index(drop=True, inplace=True)

        # 10 May 2026 — Conviction passthrough: look up each symbol's
        # Recovery-mode conviction (rewards balance sheet + value, same logic
        # the Golden Matcher uses for recovery targets) and compute a unified
        # Combined_Score so Recovery Screener's ranking is consistent with
        # FINAL_COMBINED_RECOVERY_PICKS.csv.
        try:
            import conviction_passthrough as _cp
            df_out = _cp.add_conviction_and_combined_score(
                df_out, mode="recovery", score_col="Score"
            )
            # Re-rank: Combined_Score primary, then Signal as tiebreak (so
            # actively-firing signals still float above WATCH/HOLD ties)
            if "Combined_Score" in df_out.columns:
                df_out = df_out.sort_values(
                    ["Combined_Score", "Signal"], ascending=[False, False]
                ).reset_index(drop=True)
        except Exception as _cpe:
            logger.debug("Conviction passthrough skipped: %s", _cpe)

    df_out.to_csv(os.path.join(DATA_DIR, out_file), index=False)
    # Auto-log live picks to pick_log.db (replay-safe).
    try:
        import pick_log as _pl
        _pl.log_picks("recovery", df_out)
    except Exception:
        pass
    return df_out


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    # E10: optional --as-of YYYY-MM-DD flag for replay mode.
    import argparse as _ap
    from datetime import datetime
    parser = _ap.ArgumentParser(description="Commander Recovery Screener")
    parser.add_argument("--as-of", dest="as_of", default=None,
                         help="Replay mode: run as of this date (YYYY-MM-DD).")
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
    print(f"  COMMANDER RECOVERY SCREENER :  Python Edition v1.1{pin_label}")
    print(f"    {datetime.now().strftime('%A %d %b %Y  %H:%M')}")
    print("=" * 68)

    # 1 -- Candidates (Screener.in primary, Chartink secondary)
    print("\n  Loading candidates...")
    candidates = load_candidates()
    if not candidates:
        print("ERROR  No candidates found.")
        print("       Run screener_fetcher + screener_processor (for Screener.in pool)")
        print("       and/or chartink_scanner_pro.py scans 5-7 (for Chartink pool).")
        return

    # 1b -- Screener.in symbol set: candidates also in Screener.in = intersection
    screener_syms = load_screener_symbols()
    overlap = sum(1 for s, _ in candidates if s in screener_syms)
    print(f"  Screener.in overlap (intersection): {overlap} of {len(candidates)} stocks have RFF data")

    # 2 -- Fundamentals
    print("\n  Loading Screener.in fundamentals...")
    fund_map = load_fundamentals()

    # 3 -- CNX500 market data (regime gate + Mansfield RS denominator)
    print("\n  Downloading CNX500 market data...")
    try:
        if USE_DATA_PROVIDER and _dp is not None:
            df_cnx_d = _flatten_cols(_dp.fetch_ohlcv(CNX500_YF, period="2y", interval="1d"))
            df_cnx_w = _flatten_cols(_dp.fetch_ohlcv(CNX500_YF, period="3y", interval="1wk"))
        else:
            df_cnx_d = _flatten_cols(
                yf.download(CNX500_YF, period="2y", interval="1d",
                            auto_adjust=True, progress=False)
            )
            df_cnx_w = _flatten_cols(
                yf.download(CNX500_YF, period="3y", interval="1wk",
                            auto_adjust=True, progress=False)
            )
        regime = check_regime(df_cnx_d)
        print(f"    CNX500 close : {regime['mkt_close']}")
        print(f"    SMA50/SMA200 : {regime['mkt_sma50']} / {regime['mkt_sma200']}  "
              f"(death-cross: {regime['mkt_death_cross']} — info only in v1.2)")
        print(f"    Corrected≥7% : {regime['mkt_corrected']}  "
              f"({regime['mkt_corr_pct']:.1f}% off 52W high)")
        print(f"    SMA50 Reclaim: {regime['mkt_reclaim']}  (v1.3: CNX500 close > SMA50 AND was below within last 30 bars)")
        print(f"    Recovery     : {regime['mkt_in_recovery']}  (v1.3: corrected OR reclaiming)")
    except Exception as e:
        print(f"ERROR  CNX500 download failed: {e}")
        return

    # 4 -- Screen each symbol
    total   = len(candidates)
    results = []
    print(f"\n   Screening {total} symbols  (signal_hold_days={CONFIG['signal_hold_days']})...\n")

    for idx, (symbol, edge_hint) in enumerate(candidates, 1):
        si_confirmed = symbol in screener_syms   # also in Screener.in = intersection
        si_tag = " [SI]" if si_confirmed else ""  # SI = Screener.in intersection
        print(f"  [{idx:3d}/{total}]  {symbol:<16} ({edge_hint:<10}){si_tag} ... ", end="", flush=True)
        try:
            r = screen_symbol(symbol, edge_hint, regime, df_cnx_w,
                              fund_map.get(symbol), chartink_confirmed=si_confirmed)
            tag = f"Signal={r['Signal']} ({r['Signal_Label']:<10})  Score={r['Score']:2d}"
            if r["Signal"] >= 3:
                tag += "  ***"
            elif r["Signal"] == 2:
                tag += "  "
            elif r["Signal"] == 1:
                tag += "  *"
            print(tag)
            results.append(r)
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({"Symbol": symbol, "Edge_Hint": edge_hint,
                            "Signal": 0, "Score": 0, "Details": str(e)})
        time.sleep(CONFIG["download_delay_sec"])

    # 5 -- Sort and save
    df_out = pd.DataFrame(results)
    if not df_out.empty:
        df_out.sort_values(["Signal", "Score"], ascending=[False, False], inplace=True)
        df_out.reset_index(drop=True, inplace=True)
    out_path = os.path.join(DATA_DIR, OUTPUT_FILE)
    df_out.to_csv(out_path, index=False)

    # 6 -- Summary
    print("\n" + "=" * 68)
    print("  RESULTS SUMMARY")
    print("=" * 68)
    counts = df_out["Signal"].value_counts().sort_index(ascending=False)
    for s, n in counts.items():
        lbl = SIGNAL_LABELS.get(s, "?")
        bar = "#" * n
        print(f"  Signal {s}  {lbl:<12}  {n:3d}  {bar}")

    actionable = df_out[df_out["Signal"] >= 2]
    if not actionable.empty:
        print(f"\n  ACTIONABLE SETUPS  (Signal >= 2, top {min(15, len(actionable))})")
        hdr = f"  {'Symbol':<16} {'Edge':<12} {'Scr':>3} {'RFF':>4} {'RS':>6}  {'SL%':>5}  {'T1%':>5}  {'RR':>4}  Signal Date"
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))
        for _, row in actionable.head(15).iterrows():
            rs_s  = f"{row.get('Mansfield_RS_x100', ''):.2f}" if row.get("Mansfield_RS_x100") is not None else "  n/a"
            sl_s  = f"{row.get('SL_pct', ''):.1f}" if row.get("SL_pct") is not None else "  n/a"
            t1_s  = f"{row.get('T1_pct', ''):.1f}" if row.get("T1_pct") is not None else "  n/a"
            rr_s  = f"{row.get('RR_T1', ''):.1f}" if row.get("RR_T1") is not None else " n/a"
            sd    = row.get("Signal_Date") or ""
            print(f"  {row['Symbol']:<16} {row['Signal_Label']:<12} "
                  f"{row.get('Score', 0):>3} {row.get('RFF_Score', 0):>4} {rs_s:>6}  "
                  f"{sl_s:>5}  {t1_s:>5}  {rr_s:>4}  {sd}")
    else:
        print("\n  No actionable setups (Signal >= 2) in current watchlists.")
        print("  Check Signal=1 (CB-Watch) for upcoming CB setups.")

    print(f"\nDONE  Full results  {OUTPUT_FILE}")
    print("=" * 68)


if __name__ == "__main__":
    main()
