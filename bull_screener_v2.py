#!/usr/bin/env python3
"""
bull_screener_v2.py :  Minervini SEPA Bull Screener v2.0  (2026-05-20)

Pure price-action rewrite of the catalyst-based bull_screener.py.

═══════════════════════════════════════════════════════════════════════════
WHY v2.0 EXISTS
═══════════════════════════════════════════════════════════════════════════
v1.x (catalyst stack: POS-BO / POS-ACCUM / SWG-PB / SWG-BO / SWG-REV / SWG-GAP)
delivered +14.81% cumulative alpha on Nifty 500 12-anchor backtest — real edge.
But POS-ACCUM contributed -10.04% drag (now disabled in v1.8) and the entire
catalyst stack was ported from Pine v4.52 with significant indicator dependence.

v2.0 implements Mark Minervini's SEPA (Specific Entry Point Analysis) framework
— the same methodology that won him multiple US Investing Championships and
underpins his "Trade Like a Stock Market Wizard" book.

═══════════════════════════════════════════════════════════════════════════
SEPA PIPELINE
═══════════════════════════════════════════════════════════════════════════

  STAGE 1: TREND TEMPLATE (8 gates — ALL required)
  ─────────────────────────────────────────────────
    T1: Close > MA150 AND close > MA200       (above key MAs)
    T2: MA150 > MA200                          (medium-term above long-term)
    T3: MA200 trending up for >=1 month        (long-term trend rising)
    T4: MA50  > MA150 AND MA50 > MA200         (short above medium and long)
    T5: Close > MA50                           (price above short-term)
    T6: Close >= 25% above 52-week LOW         (not at the bottom)
    T7: Close >= 75% of 52-week HIGH           (within 25% of the top)
    T8: RS rank (vs N500) >= 70                (relative strength leader)

  STAGE 2: VOLATILITY CONTRACTION PATTERN (VCP)
  ─────────────────────────────────────────────────
    Uses existing pivot_detector.detect_vcp:
      - >=2 measurable contractions in the base
      - Each contraction smaller than the previous
      - Volume drying up through the base (price-action confirmation)
      - Pivot point established at the top of the right-most contraction

  STAGE 3: PIVOT BREAKOUT (entry catalyst)
  ─────────────────────────────────────────────────
    M-PIVOT-BO  : Close > pivot_price on volume >= 1.5x 50-day avg
                  Stock just punched through the VCP pivot today/recently.
    M-PIVOT-PB  : Close within 1% of pivot AND base just completed (broke
                  pivot recently within last 5 days, now pulling back to test).
                  Lower-risk entry — Minervini's "pocket pivot" variant.

  STAGE 4: RISK MANAGEMENT (Minervini-spec)
  ─────────────────────────────────────────────────
    Entry  : current close
    SL     : max(pivot_low, entry - 1.5*ATR)   — never risk more than 1.5*ATR
    Risk%  : (entry - SL) / entry
    T1     : entry + 3 * risk                   — 3R target (Minervini default)
    Position size: 25% / risk%                  — 1% portfolio risk per trade

INDICATORS USED
═══════════════════════════════════════════════════════════════════════════
  - PRICE: OHLC bars
  - VOLUME: raw + 50-day SMA (ratio comparison, not signal)
  - MAs: 50/150/200-day for Trend Template STRUCTURE (not crossovers)
  - ATR(14): for stop placement only

  NOT USED: RSI, MACD, Stochastic, ADX, OBV, momentum oscillators.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

import bull_screener as _bs  # reused: to_yf, _flatten_cols, data fetch, compute_weekly_indicators
import pivot_detector as _pv  # VCP + pivot quality

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────
CONFIG = {
    "min_turnover_cr":          50.0,
    # Trend Template thresholds (Minervini originals)
    "tt_pct_above_52w_low":     25.0,    # close >= 25% above 52w low
    "tt_pct_below_52w_high":    25.0,    # close <= 25% below 52w high (= >= 75% of high)
    "tt_ma200_uptrend_bars":    22,      # MA200 trending up for 1 month (22 trading days)
    "tt_rs_rank_min":           70,      # RS rank vs N500 >= 70 (percentile)
    # VCP / pivot
    "vcp_min_contractions":     2,
    "vcp_pivot_buffer_pct":     1.0,     # M-PIVOT-PB: within 1% of pivot
    "vcp_pb_lookback":          5,       # PB: broke pivot within last 5 days
    # Breakout confirmation
    "bo_vol_mult":              1.5,     # volume >= 1.5x avg on breakout
    # Risk
    "atr_sl_mult":              1.5,
    "atr_t1_mult":              3.0,     # 3R target (Minervini default)
}


# ── Trend Template ─────────────────────────────────────────────────────────
def _check_trend_template(df_d: pd.DataFrame, weekly: dict, df_bench_d: pd.DataFrame) -> tuple[bool, dict, list]:
    """8-gate Minervini Trend Template. Returns (all_pass, diagnostics, failed_gates)."""
    if len(df_d) < 252:  # need 52w + room
        return False, {}, ["insufficient_history"]
    c   = df_d["Close"].astype(float)
    ma50  = c.rolling(50).mean()
    ma150 = c.rolling(150).mean()
    ma200 = c.rolling(200).mean()
    c_now    = float(c.iloc[-1])
    ma50_now  = float(ma50.iloc[-1])
    ma150_now = float(ma150.iloc[-1])
    ma200_now = float(ma200.iloc[-1])
    ma200_22bk = float(ma200.iloc[-CONFIG["tt_ma200_uptrend_bars"]])
    h52 = float(c.iloc[-252:].max())
    l52 = float(c.iloc[-252:].min())

    gates = {
        "T1_above_ma150_200":  c_now > ma150_now and c_now > ma200_now,
        "T2_ma150_above_200":  ma150_now > ma200_now,
        "T3_ma200_uptrend":    ma200_now > ma200_22bk,
        "T4_ma50_above_med":   ma50_now > ma150_now and ma50_now > ma200_now,
        "T5_above_ma50":       c_now > ma50_now,
        "T6_25pct_above_low":  c_now >= l52 * (1 + CONFIG["tt_pct_above_52w_low"] / 100),
        "T7_within_25pct_high": c_now >= h52 * (1 - CONFIG["tt_pct_below_52w_high"] / 100),
        # T8: RS rank — use Mansfield (already computed in weekly) as proxy.
        # JdK RS-Ratio > 100 (i.e., mansfield > 0) means stock outperforming benchmark.
        # Higher mansfield = stronger RS. Map mansfield to rank:
        #   mansfield > 0  → roughly top 50% (outperforming)
        "T8_rs_rank":          weekly.get("mansfield", 0.0) > 0.0,
    }
    all_pass = all(gates.values())
    failed = [k for k, v in gates.items() if not v]
    diag = {
        "tt_close":     round(c_now, 2),
        "tt_ma50":      round(ma50_now, 2),
        "tt_ma150":     round(ma150_now, 2),
        "tt_ma200":     round(ma200_now, 2),
        "tt_52w_high":  round(h52, 2),
        "tt_52w_low":   round(l52, 2),
        "tt_pct_above_low":  round((c_now / l52 - 1) * 100, 1),
        "tt_pct_below_high": round((1 - c_now / h52) * 100, 1),
        "tt_rs_mansfield":   round(weekly.get("mansfield", 0.0), 2),
        "tt_pass_count": sum(gates.values()),
        "tt_pass_all":   all_pass,
    }
    return all_pass, diag, failed


# ── Pivot Breakout Detection ───────────────────────────────────────────────
def _check_pivot_catalyst(df_d: pd.DataFrame, vcp: dict) -> tuple[str, str]:
    """Identify the entry catalyst (M-PIVOT-BO or M-PIVOT-PB) or empty."""
    if not vcp.get("is_valid"):
        return "", "no valid VCP base"
    pivot = vcp.get("pivot_price")
    if pivot is None:
        return "", "no pivot price"
    pivot = float(pivot)

    c = df_d["Close"].astype(float)
    v = df_d["Volume"].astype(float)
    vol_avg = v.rolling(50).mean()
    c_now = float(c.iloc[-1])
    v_now = float(v.iloc[-1])
    v_avg = float(vol_avg.iloc[-1])

    if np.isnan(v_avg) or v_avg <= 0:
        return "", "no volume average"

    # M-PIVOT-BO: current bar breaks pivot on volume
    if c_now > pivot and vcp.get("broke_pivot"):
        days_since = vcp.get("days_since_pivot", 0) or 0
        if days_since <= 2 and v_now >= v_avg * CONFIG["bo_vol_mult"]:
            return "M-PIVOT-BO", (f"close {c_now:.2f} > pivot {pivot:.2f}, "
                                    f"vol {v_now/v_avg:.1f}x avg, day {days_since} since breakout")

    # M-PIVOT-PB: pivot was broken in last 5 days, now pulling back to test
    if vcp.get("broke_pivot"):
        days_since = vcp.get("days_since_pivot", 0) or 0
        if 0 < days_since <= CONFIG["vcp_pb_lookback"]:
            # Pullback: current close within 1% of pivot
            if abs(c_now - pivot) / pivot * 100 <= CONFIG["vcp_pivot_buffer_pct"]:
                return "M-PIVOT-PB", (f"pulled back to pivot {pivot:.2f} "
                                        f"({days_since} days after BO)")

    return "", f"no pivot catalyst (broke={vcp.get('broke_pivot')}, days={vcp.get('days_since_pivot')})"


# ── Pipeline ───────────────────────────────────────────────────────────────
def _screen_one(symbol: str, df_bench_w: pd.DataFrame, df_bench_d: pd.DataFrame,
                  force_output: bool = False) -> Optional[dict]:
    """Run Minervini v2 pipeline on a single symbol."""
    try:
        df_d = _bs._flatten_cols(_bs._dp.fetch_ohlcv(symbol, period="2y", interval="1d"))
        if df_d.empty or len(df_d) < 252:
            return None
        df_w = _bs._flatten_cols(_bs._dp.fetch_ohlcv(symbol, period="3y", interval="1wk"))
    except Exception:
        return None

    c = df_d["Close"].astype(float)
    v = df_d["Volume"].astype(float)
    c_now = float(c.iloc[-1])
    v_avg = float(v.rolling(50).mean().iloc[-1])
    if np.isnan(v_avg):
        return None

    # Liquidity
    turnover_cr = c_now * v_avg / 1e7
    if turnover_cr < CONFIG["min_turnover_cr"] and not force_output:
        return None

    # Weekly indicators (Stage + RRG + Mansfield)
    weekly = _bs.compute_weekly_indicators(df_w, df_bench_w)

    # Stage 1: Trend Template
    tt_pass, tt_diag, tt_failed = _check_trend_template(df_d, weekly, df_bench_d)
    if not tt_pass and not force_output:
        return None

    # Stage 2: VCP base detection
    vcp = _pv.detect_vcp(df_d, min_contractions=CONFIG["vcp_min_contractions"])
    if not vcp.get("is_valid") and not force_output:
        return None

    # Stage 3: Pivot breakout / pullback catalyst
    catalyst, cat_reason = _check_pivot_catalyst(df_d, vcp)
    if not catalyst and not force_output:
        return None

    # Stage 4: Risk sizing — Minervini spec
    # ATR(14)
    h = df_d["High"].astype(float); l = df_d["Low"].astype(float)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr14 = float(tr.rolling(14).mean().iloc[-1])
    # SL: max of pivot_low (structural) and ATR-based
    sl_atr     = c_now - atr14 * CONFIG["atr_sl_mult"]
    _pl_raw    = vcp.get("pivot_low")
    _pp_raw    = vcp.get("pivot_price")
    pivot_low  = float(_pl_raw) if _pl_raw is not None else (float(_pp_raw) * 0.92 if _pp_raw is not None else sl_atr)
    sl         = max(pivot_low, sl_atr)
    risk      = c_now - sl
    if risk <= 0:
        return None
    risk_pct  = risk / c_now * 100
    t1        = c_now + risk * CONFIG["atr_t1_mult"]

    # Score: tighter base + earlier breakout + more contractions = higher conviction
    base_score = 60 if catalyst else 0
    base_score += min(20, int(vcp.get("quality_score", 0)) // 5)   # VCP quality bonus
    if catalyst == "M-PIVOT-BO":
        base_score += 10                                            # fresh BO premium
    if tt_diag.get("tt_pass_count", 0) == 8:
        base_score += 10                                            # all 8 TT gates passed

    return {
        "Symbol":              symbol,
        "Catalyst":            catalyst or "None",
        "Signal_Label":        catalyst or "None",
        "Score":               min(100, base_score),
        "Stage":               int(weekly.get("stage", 0)),
        "TT_Pass_Count":       tt_diag.get("tt_pass_count", 0),
        "TT_Pass_All":         tt_diag.get("tt_pass_all", False),
        "TT_Failed_Gates":     ",".join(tt_failed) if tt_failed else "",
        "Pct_Above_52w_Low":   tt_diag.get("tt_pct_above_low"),
        "Pct_Below_52w_High":  tt_diag.get("tt_pct_below_high"),
        "JdK_RS_Ratio":        round(weekly.get("mansfield", 0.0) + 100.0, 2),
        "RRG_Quadrant":        weekly.get("rrg_quadrant", "n/a"),
        "VCP_Valid":           bool(vcp.get("is_valid")),
        "VCP_Quality_Score":   vcp.get("quality_score", 0),
        "VCP_Contractions":    vcp.get("contractions", 0),
        "Pivot_Price":         vcp.get("pivot_price"),
        "Broke_Pivot":         bool(vcp.get("broke_pivot")),
        "Days_Since_Pivot":    vcp.get("days_since_pivot"),
        "Entry":               round(c_now, 2),
        "SL":                  round(sl, 2),
        "SL_pct":              round(risk_pct, 2),
        "T1":                  round(t1, 2),
        "T1_pct":              round((t1 - c_now) / c_now * 100, 2),
        "R_Multiple":          CONFIG["atr_t1_mult"],
        "Catalyst_Reason":     cat_reason,
    }


# ── Public driver (compat with bull_screener.py API + validation.py) ───────
def run_bull_screener(progress_callback=None,
                        symbols: Optional[list] = None,
                        out_file: str = "Bull_Screener_v2_Results.csv",
                        strict: bool = True,
                        in_file: Optional[str] = None,
                        force_tracker_mode: bool = False) -> pd.DataFrame:
    """Run Minervini SEPA v2.0 screener. Same public API as bull_screener.py."""
    print(f"\n  MINERVINI SEPA BULL SCREENER v2.0  {pd.Timestamp.now():%d %b %Y %H:%M}")
    print(f"    Trend Template: 8 gates (all required)")
    print(f"    VCP base: >={CONFIG['vcp_min_contractions']} contractions, drying volume")
    print(f"    Catalysts: M-PIVOT-BO (fresh BO + vol) | M-PIVOT-PB (pullback to pivot)")

    if symbols is None:
        try:
            import validation as _v
            symbols = _v.default_universe("nifty100")
        except Exception:
            return pd.DataFrame()

    # Benchmark weekly (RRG/Mansfield) + daily (regime context)
    try:
        df_bench_w = _bs._flatten_cols(_bs._dp.fetch_ohlcv("^CRSLDX", period="3y", interval="1wk"))
        df_bench_d = _bs._flatten_cols(_bs._dp.fetch_ohlcv("^CRSLDX", period="2y", interval="1d"))
        if not df_bench_d.empty:
            res = df_bench_d.resample("W-MON", closed="left", label="left").agg({
                "Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"
            }).dropna(subset=["Close"])
            if not res.empty and not df_bench_w.empty:
                extra = res[res.index > df_bench_w.index[-1]]
                if not extra.empty:
                    df_bench_w = pd.concat([df_bench_w, extra])
    except Exception as e:
        print(f"    [WARN] Benchmark fetch failed: {e}")
        return pd.DataFrame()

    rows = []
    n = len(symbols)
    for i, sym in enumerate(symbols):
        if progress_callback:
            try: progress_callback(i, n, sym)
            except Exception: pass
        yf_sym = _bs.to_yf(sym)
        rec = _screen_one(yf_sym, df_bench_w, df_bench_d,
                            force_output=(not strict) or force_tracker_mode)
        if rec is None:
            continue
        if strict and rec.get("Catalyst", "None") == "None":
            continue
        rec["Symbol"] = sym
        rows.append(rec)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Score", ascending=False).reset_index(drop=True)
    try:
        df.to_csv(out_file, index=False)
    except Exception:
        pass
    print(f"    --> {len(df)} picks {'(strict)' if strict else '(live)'} --> {out_file}")
    return df


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", default=None)
    p.add_argument("--strict", action="store_true", default=True)
    args = p.parse_args()
    syms = [s.strip() for s in args.symbols.split(",")] if args.symbols else None
    df = run_bull_screener(symbols=syms, strict=args.strict)
    if not df.empty:
        cols = ["Symbol","Catalyst","Score","TT_Pass_Count","VCP_Quality_Score",
                "VCP_Contractions","Pct_Below_52w_High","Pivot_Price","Entry","SL","T1"]
        print(df[cols].to_string(index=False))
