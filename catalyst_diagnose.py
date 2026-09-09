"""
catalyst_diagnose.py — Per-gate pass-rate breakdown for bull_screener catalysts.

Why: in our N500 12-anchor validation POS-BO and SWG-GAP fired 0 / 5,737
times. The catalysts both require `weinstein_setup` — a 9-condition mega-gate
that includes `ma_sqz_ok` (SMA20 within 5% of SMA50) and `bb_sqz_ok` (BB width
compressed) — which structurally contradict the simultaneous breakout / gap
triggers (a stock breaking a 21-bar high usually has SMA20 well above SMA50,
and a 4% gap means BBs are widening, not compressed).

This diagnostic re-evaluates each gate independently across a candidate
universe and reports:
  - per-gate pass rate
  - "weinstein_setup pass rate" (all 9 ANDed)
  - bottleneck gates: which ones fail most often
  - hypothetical fire rate if specific gates are dropped

Public API:
  diagnose_catalysts(symbols, anchor=None) -> pd.DataFrame   (per-symbol)
  summarize_gates(df)                       -> dict           (aggregate)
  run_diagnostic(anchor, base_universe)     -> dict           (orchestrator)
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

import bull_screener as _bs
import data_provider as _dp


logger = logging.getLogger(__name__)


def _eval_one(symbol: str) -> Optional[dict]:
    """Re-compute every catalyst gate for one symbol at the pinned date.
    Returns a dict of bool flags per gate, or None on data failure.
    """
    df = _dp.fetch_ohlcv(symbol, period="2y", interval="1d")
    if df is None or df.empty or len(df) < 200:
        return None
    df = _bs._flatten_cols(df)
    bench = _dp.fetch_ohlcv("^CRSLDX", period="2y", interval="1d")
    if bench is None or bench.empty:
        return None
    bench = _bs._flatten_cols(bench)

    try:
        ind     = _bs.compute_indicators(df)
        weekly  = _bs.compute_weekly_indicators(df, bench)
        alpha   = _bs.calculate_alpha_score(ind)
    except Exception as e:
        logger.debug("indicator failure for %s: %s", symbol, e)
        return None

    # ----- Replicate check_conditions's gate computations -----
    c = ind["close"]; h = ind["high"]; l = ind["low"]; o = ind["open"]
    v = ind["volume"]; rv = ind["rel_vol"]
    rsi14 = ind["rsi14"]; rsi3 = ind["rsi3"]
    sma20 = ind["sma20"]; sma50 = ind["sma50"]
    sma150 = ind["sma150"]; sma200 = ind["sma200"]
    h52w = ind["high52w"]; l52w = ind["low52w"]
    atr10 = ind["atr10"]; atr10_sma50 = ind["atr10_sma50"]
    vol_vwma5 = ind["vol_vwma5"]; bb_width = ind["bb_width"]
    obv = ind["obv"]
    ema20 = ind["ema20"]

    c_now = float(c.iloc[-1]); o_now = float(o.iloc[-1])
    h_now = float(h.iloc[-1]); l_now = float(l.iloc[-1])
    rv_now = float(rv.iloc[-1])
    ema20_now = float(ema20.iloc[-1])

    alpha_ok = alpha >= _bs.CONFIG["alpha_gate"]

    minervini = (c_now > sma50.iloc[-1] > sma150.iloc[-1] > sma200.iloc[-1])
    trend_template_ok = (c_now > l52w.iloc[-1] * 1.30 and
                            c_now >= h52w.iloc[-1] * 0.75)

    # 9-gate weinstein_setup
    stage2_uptrend = weekly["stage"] == 2
    trend_aligned  = bool(minervini)
    rs_ok          = weekly["mansfield"] > 0
    sector_stage_ok = True   # not wired in Python
    vol_acc_ok = bool((v.iloc[-10:] > ind["vol_ma"].iloc[-10:]).sum() >= 6)
    if len(sma50) >= 130 and len(sma150) >= 130:
        _stack = (sma50.iloc[-130:] > sma150.iloc[-130:])
        stage2_fresh_ok = bool(_stack.sum() < 130)
    else:
        stage2_fresh_ok = True
    s20 = sma20.iloc[-1]; s50 = sma50.iloc[-1]
    ma_sqz_ok = (not np.isnan(s20)) and (not np.isnan(s50)) and abs(s20-s50)/s50 < 0.05
    bbw_now = bb_width.iloc[-1]
    bbw_avg = bb_width.rolling(120).mean().iloc[-1]
    bb_sqz_ok = (not np.isnan(bbw_now)) and (not np.isnan(bbw_avg)) and bbw_now < bbw_avg

    weinstein_setup = (stage2_uptrend and trend_aligned and rs_ok and
                          sector_stage_ok and vol_acc_ok and stage2_fresh_ok and
                          ma_sqz_ok and bb_sqz_ok and trend_template_ok)

    # Catalyst-specific triggers
    intraday_pos = (c_now - l_now) / (h_now - l_now) if h_now > l_now else 0.0
    h21 = float(h.iloc[-22:-1].max())
    pos_bo_trig = (c_now > h21) and (rv_now > 1.25)

    h_prev = float(h.iloc[-2])
    swg_gap_trig = ((o_now - h_prev) / h_prev > 0.04 and rv_now >= 3.0
                       and c_now > o_now and intraday_pos > 0.60)

    # VCP / SWG-BO
    vcp_tight = bool(
        not np.isnan(atr10.iloc[-1]) and not np.isnan(atr10_sma50.iloc[-1])
        and not np.isnan(vol_vwma5.iloc[-1]) and not np.isnan(ind["vol_ma"].iloc[-1])
        and atr10.iloc[-1] < atr10_sma50.iloc[-1] * 1.5
        and vol_vwma5.iloc[-1] < ind["vol_ma"].iloc[-1]
    )
    h16 = float(h.iloc[-16:-1].max())
    swg_bo_trig = (minervini and vcp_tight and c_now > h16
                      and rv_now > 1.25 and intraday_pos > 0.60)

    return {
        "Symbol":            symbol,
        # individual weinstein gates
        "alpha_ok":          alpha_ok,
        "stage2_uptrend":    stage2_uptrend,
        "trend_aligned":     trend_aligned,
        "rs_ok":             rs_ok,
        "vol_acc_ok":        vol_acc_ok,
        "stage2_fresh_ok":   stage2_fresh_ok,
        "ma_sqz_ok":         ma_sqz_ok,
        "bb_sqz_ok":         bb_sqz_ok,
        "trend_template_ok": trend_template_ok,
        # composite
        "weinstein_setup":   weinstein_setup,
        # catalyst triggers (independent of weinstein_setup)
        "pos_bo_trig":       bool(pos_bo_trig),
        "swg_gap_trig":      bool(swg_gap_trig),
        "swg_bo_trig":       bool(swg_bo_trig),
        # combined: would each catalyst fire?
        "POS-BO":            bool(alpha_ok and weinstein_setup and pos_bo_trig),
        "SWG-GAP":           bool(weinstein_setup and swg_gap_trig),
        "SWG-BO":            bool(alpha_ok and swg_bo_trig),
    }


def diagnose_catalysts(symbols: list[str], anchor: Optional[str] = None
                          ) -> pd.DataFrame:
    """Diagnose every symbol; pin data_provider if anchor given."""
    if anchor:
        _dp.set_pinned_date(anchor)
    try:
        rows = []
        for i, s in enumerate(symbols, 1):
            try:
                d = _eval_one(s)
                if d is not None:
                    rows.append(d)
            except Exception as e:
                logger.debug("eval %s failed: %s", s, e)
            if i % 50 == 0:
                print(f"  diagnosed {i}/{len(symbols)} ...", flush=True)
        return pd.DataFrame(rows)
    finally:
        if anchor:
            _dp.set_pinned_date(None)


def summarize_gates(df: pd.DataFrame) -> dict:
    """Aggregate pass-rates and bottleneck identification."""
    if df.empty:
        return {"n": 0}

    weinstein_gates = ["stage2_uptrend", "trend_aligned", "rs_ok",
                          "vol_acc_ok", "stage2_fresh_ok", "ma_sqz_ok",
                          "bb_sqz_ok", "trend_template_ok"]
    triggers = ["pos_bo_trig", "swg_gap_trig", "swg_bo_trig"]
    catalysts = ["POS-BO", "SWG-GAP", "SWG-BO"]

    out: dict = {"n_symbols": int(len(df))}
    out["gate_pass_pct"] = {
        g: round(float(df[g].mean()) * 100, 1) for g in weinstein_gates
    }
    out["trigger_pass_pct"] = {
        t: round(float(df[t].mean()) * 100, 1) for t in triggers
    }
    out["weinstein_setup_pct"] = round(float(df["weinstein_setup"].mean()) * 100, 1)
    out["catalyst_fire_pct"] = {
        c: round(float(df[c].mean()) * 100, 2) for c in catalysts
    }
    out["catalyst_fire_n"] = {
        c: int(df[c].sum()) for c in catalysts
    }

    # Hypothetical: if we drop ma_sqz_ok + bb_sqz_ok from weinstein_setup,
    # how many POS-BO / SWG-GAP would fire?
    relaxed = (df["stage2_uptrend"] & df["trend_aligned"] & df["rs_ok"] &
                  df["vol_acc_ok"] & df["stage2_fresh_ok"] &
                  df["trend_template_ok"])
    out["relaxed_setup_pct"] = round(float(relaxed.mean()) * 100, 1)
    out["if_drop_squeeze_pos_bo_n"] = int((df["alpha_ok"] & relaxed
                                              & df["pos_bo_trig"]).sum())
    out["if_drop_squeeze_swg_gap_n"] = int((relaxed & df["swg_gap_trig"]).sum())

    # Bottleneck identification: among rows that pass alpha_ok + stage2 +
    # trend_aligned (i.e. legitimate uptrenders), which gates fail most?
    base = df[df["alpha_ok"] & df["stage2_uptrend"] & df["trend_aligned"]]
    if not base.empty:
        out["bottleneck_in_uptrenders"] = {
            g: round(float((~base[g]).mean()) * 100, 1)
                for g in weinstein_gates
        }
    return out


def run_diagnostic(anchor: str, base_universe: str = "nifty500",
                     use_chartink: bool = True) -> dict:
    """Orchestrator: pull universe, optionally filter via chartink_replay,
    diagnose, summarize. Returns {df, summary, anchor, n_in, n_diagnosed}.
    """
    import validation as _v
    universe = _v.default_universe(base_universe)

    if use_chartink:
        import chartink_replay as _cr
        _dp.set_pinned_date(anchor)
        try:
            scanned = _cr.combined_bull_universe(universe)
        finally:
            _dp.set_pinned_date(None)
    else:
        scanned = universe

    print(f"\nDiagnosing {len(scanned)} symbols @ {anchor} "
          f"(use_chartink={use_chartink})...", flush=True)
    df = diagnose_catalysts(scanned, anchor)
    summary = summarize_gates(df)
    summary["anchor"] = anchor
    summary["base_universe"] = base_universe
    summary["use_chartink"] = use_chartink
    summary["n_in"] = len(scanned)
    summary["n_diagnosed"] = len(df)
    return {"df": df, "summary": summary}


__all__ = ["diagnose_catalysts", "summarize_gates", "run_diagnostic"]


if __name__ == "__main__":
    import sys, json
    if hasattr(sys.stdout, "encoding") and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try: sys.stdout.reconfigure(encoding="utf-8")
        except Exception: pass

    anchor = sys.argv[1] if len(sys.argv) > 1 else "2025-09-15"
    res = run_diagnostic(anchor, base_universe="nifty500", use_chartink=True)
    print("\n" + "=" * 68)
    print(f"  CATALYST GATE DIAGNOSTIC  @ {anchor}")
    print("=" * 68)
    print(json.dumps(res["summary"], indent=2, default=str))
