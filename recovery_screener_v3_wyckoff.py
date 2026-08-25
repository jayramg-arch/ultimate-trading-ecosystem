#!/usr/bin/env python3
"""
recovery_screener.py :  Wyckoff Recovery Screener v3.0  (2026-05-20)

CLEAN-SHEET REWRITE #2 — Price-action first, zero lagging oscillators.

═══════════════════════════════════════════════════════════════════════════
WHY v3.0 EXISTS
═══════════════════════════════════════════════════════════════════════════
v1.x (catalyst-based REV-* edges) was retired: -5.25% cumulative alpha.
v2.0 (RSI-oversold + first reversal) tested even WORSE: -25.52% cumulative.
Both indicator-based approaches failed because catching falling knives with
oscillators is a documented losing strategy.

v3.0 abandons indicators entirely and implements the Wyckoff Method's
accumulation-phase setup: the same framework used by smart-money tape readers
since the 1930s and still taught at top prop firms.

═══════════════════════════════════════════════════════════════════════════
WYCKOFF ACCUMULATION (Phases A-E)
═══════════════════════════════════════════════════════════════════════════

  Phase A : Selling climax exhausts. Stage 4 decline ends. Range forms.
  Phase B : Cause-building. Sideways consolidation. Smart money accumulates.
            Multiple tests of range low (Secondary Tests).
  Phase C : The Spring — price breaks below range support on weak volume,
            then rapidly rejects back inside. False breakdown traps shorts.
            Often followed by a Test (lower-volume retest of the spring low).
  Phase D : Sign of Strength (SOS) — wide-range up bar on heavy volume back
            through the range. Backup to Edge of Creek (BUEC) = first pullback.
            Jump Across the Creek (JAC) = close above range high on volume.
  Phase E : Stock leaves accumulation, enters Stage 2 markup.

═══════════════════════════════════════════════════════════════════════════
WHAT THIS SCREENER DETECTS
═══════════════════════════════════════════════════════════════════════════

  1. ACCUMULATION BASE  — sideways range (max 25% high-low) for >= 8 weeks
                          following a prior Stage 4 / decline phase
  2. SPRING             — recent close below base low with WEAK volume,
                          then close back above base low within 1-3 bars
  3. SOS  (Sign of Strength) — wide-range up bar (spread >= 1.5× avg) closing
                               in upper third with volume >= 1.5× 50-bar avg
  4. JAC  (Jump Across Creek) — close above accumulation high on volume >= 2×

  Catalysts (any one triggers entry):
    WYC-SPRING   : Spring detected, entered after rejection back into range
    WYC-SOS      : SOS bar confirmed, entered on first pullback (BUEC)
    WYC-JAC      : Close above range high on heavy volume (late but safer)

═══════════════════════════════════════════════════════════════════════════
INDICATORS USED
═══════════════════════════════════════════════════════════════════════════
  - PRICE: OHLC bars only
  - VOLUME: raw + 50-bar SMA (for ratio comparison, not as signal)
  - ATR(14): for STOP placement only, not as entry signal
  - That's it. No RSI, MACD, oscillators, momentum indicators.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

import bull_screener as _bs   # Reused for to_yf, _flatten_cols, data fetch

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────
CONFIG = {
    "min_turnover_cr":          50.0,   # liquidity floor
    "base_lookback_bars":       60,     # 60 daily bars ~= 12 weeks
    "base_max_pct_range":       25.0,   # high-low range max % of range_low
    "base_min_decline_pct":     20.0,   # must have been in decline before base
    "base_decline_lookback":    120,    # look this far back for prior decline
    "spring_max_lookback":      10,     # spring must be within last N bars
    "spring_max_below_pct":     3.0,    # spring low max N% below base low
    "spring_max_vol_ratio":     1.0,    # spring volume must be ≤ N× avg
    "spring_recovery_bars":     3,      # must close back above base low within N bars
    "sos_lookback":             5,      # SOS must be within last N bars
    "sos_min_spread_mult":      1.5,    # SOS spread ≥ N× 20-bar avg spread
    "sos_close_upper_third":    0.66,   # SOS close must be in upper N of bar
    "sos_min_vol_mult":         1.5,    # SOS volume ≥ N× 50-bar avg
    "jac_min_vol_mult":         2.0,    # JAC needs ≥ N× avg volume
    "atr_sl_mult":              1.5,    # stop = entry - 1.5× ATR
    "atr_t1_mult":              5.0,    # v3.1: T1 = 5R (was 3R) — matches Pine Ecosystem v3.4 + Pine Recovery v2.0
    "atr_t2_mult":              10.0,   # v3.1: T2 = 10R — Wyckoff base breakouts run far
    "min_avg_vol":              50000,  # min 50-bar avg vol (sanity)
}


# ── Daily feature extraction (price + volume only) ─────────────────────────
def _compute_features(df_d: pd.DataFrame) -> dict:
    """Extract OHLCV-derived features. No oscillators."""
    if df_d is None or df_d.empty or len(df_d) < CONFIG["base_decline_lookback"]:
        return {}
    c = df_d["Close"].astype(float)
    h = df_d["High"].astype(float)
    l = df_d["Low"].astype(float)
    v = df_d["Volume"].astype(float)
    spread = h - l
    # ATR(14) — for STOP placement only
    tr = pd.concat([h - l,
                    (h - c.shift()).abs(),
                    (l - c.shift()).abs()], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean()
    return {
        "close": c, "high": h, "low": l, "volume": v,
        "spread": spread,
        "vol_avg50": v.rolling(50).mean(),
        "spread_avg20": spread.rolling(20).mean(),
        "atr14": atr14,
    }


# ── Phase detection ────────────────────────────────────────────────────────
def _detect_accumulation_base(f: dict) -> dict:
    """Detect Phase B accumulation range.

    Returns dict with: in_base, base_high, base_low, base_pct_range,
    decline_pct (prior). Empty if no base.
    """
    n = len(f["close"])
    if n < CONFIG["base_decline_lookback"]:
        return {}

    # Current sideways window
    lk = CONFIG["base_lookback_bars"]
    h_window = f["high"].iloc[-lk:].max()
    l_window = f["low"].iloc[-lk:].min()
    if l_window <= 0:
        return {}
    pct_range = (h_window - l_window) / l_window * 100
    if pct_range > CONFIG["base_max_pct_range"]:
        return {}

    # Prior decline: from N bars before base to start of base, did price drop ≥X%?
    prior_lk = CONFIG["base_decline_lookback"]
    prior_high = f["high"].iloc[-prior_lk:-lk].max() if prior_lk > lk else f["high"].iloc[0]
    if prior_high <= 0:
        return {}
    decline_pct = (prior_high - l_window) / prior_high * 100
    if decline_pct < CONFIG["base_min_decline_pct"]:
        return {}

    return {
        "in_base":       True,
        "base_high":     float(h_window),
        "base_low":      float(l_window),
        "base_pct_range":round(pct_range, 1),
        "decline_pct":   round(decline_pct, 1),
    }


def _detect_spring(f: dict, base_low: float) -> dict:
    """Phase C — Spring: false breakdown below base low on weak volume + recovery."""
    lk = CONFIG["spring_max_lookback"]
    closes  = f["close"].iloc[-lk:].values
    lows    = f["low"].iloc[-lk:].values
    vols    = f["volume"].iloc[-lk:].values
    vol_avg = f["vol_avg50"].iloc[-lk:].values

    spring_threshold = base_low * (1 - CONFIG["spring_max_below_pct"] / 100)

    # Find the most recent bar where LOW pierced below base_low
    spring_idx = None
    for i in range(lk - 1, -1, -1):
        if not np.isnan(lows[i]) and lows[i] < base_low and lows[i] >= spring_threshold:
            # Check volume was weak (Wyckoff: no demand / no supply on spring)
            if not np.isnan(vols[i]) and not np.isnan(vol_avg[i]):
                if vols[i] <= vol_avg[i] * CONFIG["spring_max_vol_ratio"]:
                    spring_idx = i
                    break

    if spring_idx is None:
        return {}

    # Check recovery — within `spring_recovery_bars` of the spring, did price close back above base_low?
    # v3.1: include the spring bar itself — a same-bar rejection (close > base_low on the spring) is valid Wyckoff
    rec_window = closes[spring_idx : spring_idx + 1 + CONFIG["spring_recovery_bars"]]
    recovered = any(c > base_low for c in rec_window if not np.isnan(c))
    if not recovered:
        return {}

    return {
        "has_spring":    True,
        "spring_low":    float(lows[spring_idx]),
        "spring_vol_ratio": round(float(vols[spring_idx] / vol_avg[spring_idx]), 2),
        "bars_since_spring": lk - 1 - spring_idx,
    }


def _detect_sos(f: dict, base_high: float, base_low: float) -> dict:
    """Phase D — Sign of Strength: wide-range up bar on heavy volume."""
    lk = CONFIG["sos_lookback"]
    closes   = f["close"].iloc[-lk:].values
    opens    = f.get("open", f["close"]).iloc[-lk:].values if "open" in f else closes
    highs    = f["high"].iloc[-lk:].values
    lows     = f["low"].iloc[-lk:].values
    spreads  = f["spread"].iloc[-lk:].values
    vols     = f["volume"].iloc[-lk:].values
    spread_avg = f["spread_avg20"].iloc[-lk:].values
    vol_avg    = f["vol_avg50"].iloc[-lk:].values

    base_mid = (base_high + base_low) / 2

    for i in range(lk - 1, -1, -1):
        if any(np.isnan(x) for x in [closes[i], highs[i], lows[i], spreads[i],
                                       vols[i], spread_avg[i], vol_avg[i]]):
            continue
        # Wide range
        if spreads[i] < spread_avg[i] * CONFIG["sos_min_spread_mult"]:
            continue
        # Closed in upper third
        bar_range = highs[i] - lows[i]
        if bar_range <= 0:
            continue
        close_pos = (closes[i] - lows[i]) / bar_range
        if close_pos < CONFIG["sos_close_upper_third"]:
            continue
        # Heavy volume
        if vols[i] < vol_avg[i] * CONFIG["sos_min_vol_mult"]:
            continue
        # Closed above mid of accumulation
        if closes[i] < base_mid:
            continue
        return {
            "has_sos":       True,
            "sos_close":     float(closes[i]),
            "sos_spread_ratio": round(float(spreads[i] / spread_avg[i]), 2),
            "sos_vol_ratio": round(float(vols[i] / vol_avg[i]), 2),
            "bars_since_sos": lk - 1 - i,
        }
    return {}


def _detect_jac(f: dict, base_high: float) -> dict:
    """Phase D — Jump Across the Creek: close above base high on heavy volume."""
    if len(f["close"]) < 2:
        return {}
    c_now    = float(f["close"].iloc[-1])
    c_prev   = float(f["close"].iloc[-2])
    v_now    = float(f["volume"].iloc[-1])
    v_avg    = float(f["vol_avg50"].iloc[-1])
    if any(np.isnan(x) for x in [c_now, c_prev, v_now, v_avg]):
        return {}
    if c_now <= base_high or c_prev > base_high:
        return {}    # need a fresh close above base high
    if v_now < v_avg * CONFIG["jac_min_vol_mult"]:
        return {}
    return {
        "has_jac":       True,
        "jac_close":     c_now,
        "jac_vol_ratio": round(v_now / v_avg, 2),
    }


# ── Catalyst selection (priority: SPRING > SOS > JAC) ──────────────────────
def _select_catalyst(base: dict, spring: dict, sos: dict, jac: dict) -> tuple[str, str]:
    """Return (label, reason). Priority: most-recent + most-conviction signal first."""
    if spring and sos:
        # Spring + SOS = highest conviction (Phase C → D confirmed)
        return ("WYC-SPRING+SOS",
                 f"Spring @ {spring['spring_low']:.2f} (vol {spring['spring_vol_ratio']}× avg) + "
                 f"SOS bar (spread {sos['sos_spread_ratio']}×, vol {sos['sos_vol_ratio']}× avg)")
    if jac:
        # Jump across creek — late but confirmed
        return ("WYC-JAC",
                 f"JAC: close {jac['jac_close']:.2f} > base high {base['base_high']:.2f} on "
                 f"vol {jac['jac_vol_ratio']}× avg")
    if sos:
        return ("WYC-SOS",
                 f"SOS bar (spread {sos['sos_spread_ratio']}×, vol {sos['sos_vol_ratio']}× avg, "
                 f"closed in upper third of range)")
    if spring:
        return ("WYC-SPRING",
                 f"Spring @ {spring['spring_low']:.2f} below base low {base['base_low']:.2f}, "
                 f"weak vol {spring['spring_vol_ratio']}× avg, recovered in "
                 f"{spring['bars_since_spring']} bars")
    return ("", "no Wyckoff catalyst firing")


# ── Universe scan: the WYC family's own way into the candidate list ────────
def scan_universe_for_catalysts(symbols=None, verbose: bool = False) -> list:
    """[(symbol, catalyst)] for every name with a live Wyckoff catalyst.

    WHY THIS EXISTS (25-Aug-2026). WYC-* had produced ZERO signals for as long
    as anyone had looked, and the assumption was that the gates (rff_ok +
    regime_ok) or the market were to blame. Neither was true. MEASURED on the
    day this was written:

        recovery_screener candidates (Chartink)   64
          of which regime_ok                      59
          RFF_Total median                         6   (gate is >= 4)
          WYC catalysts found                      0

        the SAME detector run over nifty500      500
          base range > 25%                       223   rejected
          prior decline < 20%                    186   rejected
          valid accumulation base                 91
          LIVE CATALYST                            5   COHANCE MUTHOOTFIN
                                                       NCC SBICARD VMM  (all SOS)

    All five are ABSENT from the 64. The cause is plumbing, not markets and not
    thresholds: `recovery_screener.load_candidates()` sources ONLY the three
    Chartink recovery scans (REV-RS / REV-CB / REV-EARLY), so `detect_wyckoff()`
    is only ever offered names that already passed a scan built for a DIFFERENT
    catalyst. A Wyckoff accumulation base is a different structural signature
    from an RS survivor, a climax bounce or an early turn — there is no Chartink
    scan for one, so a WYC name could only arrive by coincidence. It never did.

    Wyckoff detection is pure price/volume, so it needs no pre-filter to be
    affordable: this scans the universe directly and hands the survivors to the
    recovery screener, which then applies the SAME rff_ok + regime_ok gates as
    every other REV-* edge. The gates are unchanged — only the supply is.

    COST: one daily-bar fetch per symbol, cache-warm in the pipeline (the bull
    screener has already pulled nifty500 by the time this runs). ~2-3 min cold
    on 500. Failures are skipped silently per-symbol; a symbol that cannot be
    fetched is absent, never a false negative dressed as a rejection.
    """
    import json
    import os
    if symbols is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "nifty500_symbols.json")
        try:
            with open(path) as fh:
                symbols = [str(s).replace(".NS", "") for s in json.load(fh)]
        except Exception as e:
            logger.warning("Wyckoff scan: no universe (%s)", e)
            return []

    out = []
    for sym in symbols:
        s = str(sym).strip().upper().replace("NSE:", "").replace(".NS", "")
        if not s:
            continue
        try:
            df_d = _bs._flatten_cols(_bs._dp.fetch_ohlcv(f"{s}.NS", period="2y",
                                                         interval="1d"))
        except Exception:
            continue
        if df_d is None or df_d.empty or len(df_d) < CONFIG["base_decline_lookback"]:
            continue
        try:
            f = _compute_features(df_d)
            if not f:
                continue
            f["open"] = df_d["Open"].astype(float)
            base = _detect_accumulation_base(f)
            if not base:
                continue
            cat, _ = _select_catalyst(base,
                                      _detect_spring(f, base["base_low"]),
                                      _detect_sos(f, base["base_high"], base["base_low"]),
                                      _detect_jac(f, base["base_high"]))
        except Exception:
            continue
        if cat:
            out.append((s, cat))
            if verbose:
                print(f"    WYC candidate: {s}  {cat}")
    logger.info("Wyckoff universe scan: %d candidates from %d symbols",
                len(out), len(symbols))
    return out


# ── Public driver (compat with old API + replay.py) ────────────────────────
def _screen_one(symbol: str, force_output: bool = False) -> Optional[dict]:
    """Run the Wyckoff v3 pipeline on a single symbol."""
    try:
        df_d = _bs._flatten_cols(_bs._dp.fetch_ohlcv(symbol, period="2y", interval="1d"))
    except Exception:
        return None
    if df_d.empty or len(df_d) < CONFIG["base_decline_lookback"]:
        return None

    f = _compute_features(df_d)
    if not f:
        return None
    # add 'open' for SOS
    f["open"] = df_d["Open"].astype(float)

    # Liquidity
    c_now = float(f["close"].iloc[-1])
    v_avg = float(f["vol_avg50"].iloc[-1])
    if np.isnan(v_avg) or v_avg < CONFIG["min_avg_vol"]:
        if not force_output: return None
    turnover_cr = c_now * v_avg / 1e7
    if turnover_cr < CONFIG["min_turnover_cr"] and not force_output:
        return None

    # Phase B: accumulation base?
    base = _detect_accumulation_base(f)
    if not base and not force_output:
        return None

    if base:
        spring = _detect_spring(f, base["base_low"])
        sos    = _detect_sos(f, base["base_high"], base["base_low"])
        jac    = _detect_jac(f, base["base_high"])
    else:
        spring = sos = jac = {}

    catalyst, reason = _select_catalyst(base, spring, sos, jac)
    if not catalyst and not force_output:
        return None

    # Risk sizing
    atr = float(f["atr14"].iloc[-1])
    sl  = c_now - atr * CONFIG["atr_sl_mult"]
    risk = c_now - sl
    t1  = c_now + risk * CONFIG["atr_t1_mult"]
    t2  = c_now + risk * CONFIG["atr_t2_mult"]

    # Score: SPRING+SOS confluence = 20, JAC = 18, SOS-alone = 15, SPRING-alone = 12
    score = {"WYC-SPRING+SOS": 20, "WYC-JAC": 18,
              "WYC-SOS": 15, "WYC-SPRING": 12}.get(catalyst, 0)

    return {
        "Symbol":           symbol,
        "Catalyst":         catalyst or "None",
        "Signal_Label":     catalyst or "None",
        "Score":            score,
        "Stage":            1,  # all Wyckoff accumulation candidates are Stage 1 by definition
        "Base_High":        round(base.get("base_high", 0), 2),
        "Base_Low":         round(base.get("base_low", 0), 2),
        "Base_Range_Pct":   base.get("base_pct_range", 0),
        "Prior_Decline_Pct":base.get("decline_pct", 0),
        "Has_Spring":       bool(spring),
        "Has_SOS":          bool(sos),
        "Has_JAC":          bool(jac),
        "Spring_Vol_Ratio": spring.get("spring_vol_ratio"),
        "SOS_Vol_Ratio":    sos.get("sos_vol_ratio"),
        "JAC_Vol_Ratio":    jac.get("jac_vol_ratio"),
        "Entry":            round(c_now, 2),
        "SL":               round(sl, 2),
        "SL_pct":           round((c_now - sl) / c_now * 100, 2),
        "T1":               round(t1, 2),
        "T1_pct":           round((t1 - c_now) / c_now * 100, 2),
        "T2":               round(t2, 2),
        "T2_pct":           round((t2 - c_now) / c_now * 100, 2),
        "T1_R":             CONFIG["atr_t1_mult"],
        "T2_R":             CONFIG["atr_t2_mult"],
        "R_Multiple":       CONFIG["atr_t1_mult"],   # legacy alias
        "Catalyst_Reason":  reason,
    }


def run_recovery_screener(progress_callback=None,
                            symbols: Optional[list] = None,
                            out_file: str = "Recovery_Wyckoff_Results.csv",
                            strict: bool = False) -> pd.DataFrame:
    """Wyckoff Recovery Screener v3.0. Same public API as v1/v2 for compat."""
    print(f"\n  WYCKOFF RECOVERY SCREENER v3.0  {pd.Timestamp.now():%d %b %Y %H:%M}")
    print(f"    Phase B: accumulation base, range <={CONFIG['base_max_pct_range']}% over "
          f"{CONFIG['base_lookback_bars']} bars, prior decline >={CONFIG['base_min_decline_pct']}%")
    print(f"    Phase C: Spring (weak-vol breakdown + recovery <={CONFIG['spring_recovery_bars']} bars)")
    print(f"    Phase D: SOS (spread {CONFIG['sos_min_spread_mult']}x, vol {CONFIG['sos_min_vol_mult']}x, "
          f"close upper third) OR JAC (close > base high, vol {CONFIG['jac_min_vol_mult']}x)")

    if symbols is None:
        try:
            import validation as _v
            symbols = _v.default_universe("nifty100")
        except Exception:
            return pd.DataFrame()

    rows = []
    n = len(symbols)
    for i, sym in enumerate(symbols):
        if progress_callback:
            try: progress_callback(i, n, sym)
            except Exception: pass
        yf_sym = _bs.to_yf(sym)
        rec = _screen_one(yf_sym, force_output=(not strict))
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
    print(f"    --> {len(df)} picks {'(strict mode)' if strict else '(live mode)'} --> {out_file}")
    return df


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", default=None)
    p.add_argument("--strict", action="store_true")
    args = p.parse_args()
    syms = [s.strip() for s in args.symbols.split(",")] if args.symbols else None
    df = run_recovery_screener(symbols=syms, strict=args.strict)
    if not df.empty:
        cols = ["Symbol","Catalyst","Score","Base_Range_Pct","Prior_Decline_Pct",
                "Has_Spring","Has_SOS","Has_JAC","Entry","SL","T1"]
        print(df[cols].to_string(index=False))
