"""
pivot_detector.py — Volatility Contraction Pattern (VCP) + pivot detector.

Implements Minervini's VCP rules in code so the screener can score each
candidate's base structure rather than just its trend stack:

  1. The stock is leading (≥30% rise in the last 3–12 months).
  2. A consolidation base has formed (5–65 weeks long).
  3. Within the base, ≥2 contractions of decreasing depth.
  4. The most recent contraction is tight (≤ ~10% pullback) and ideally
     accompanied by drying-up volume.
  5. Pivot price = high of the last contraction (the lid the stock must clear).

Public API:
    detect_vcp(df_d, ...) -> dict
    pivot_quality_score(detection) -> int  (0–100)

`df_d` is a daily OHLCV DataFrame indexed by date (yfinance shape).
Detection output dict (keys present even when is_valid=False):

    {
      "is_valid":              bool,
      "base_start":            "YYYY-MM-DD" | None,
      "base_length_days":      int,
      "contractions":          [{"high_date","high","low_date","low","pullback_pct"}],
      "pivot_price":           float | None,    # high of last contraction
      "current_close":         float | None,
      "days_since_pivot":      int | None,      # days since last contraction high
      "broke_pivot":           bool,            # close > pivot_price * (1 + buffer)
      "vol_dry_up":            bool,            # 5d-avg volume < 50d-avg
      "leading":               bool,            # ≥30% gain in last 3-12mo
      "quality_score":         int,             # 0–100
      "reason":                str,             # human-readable detail
    }
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


# ─── Tunables ────────────────────────────────────────────────────────────────
ZIGZAG_PCT          = 0.04   # 4% reversal threshold defines a swing
MIN_BASE_DAYS       = 25     # ~5 weeks
MAX_BASE_DAYS       = 325    # ~65 weeks
MIN_CONTRACTIONS    = 3      # a 2-swing base passes a 'last 3' rule on ONE comparison
VCP_CONTRACTIONS    = 3      # the base IS the last N contractions (Minervini: 2-4)
PIVOT_BREAK_BUFFER  = 0.001  # close > pivot × 1.001 counts as broken
LEADING_LOOKBACK    = 130    # ~6 months (CAN-SLIM "C" approximation)
LEADING_MIN_GAIN    = 0.30   # 30% rise required to be a "leader"


# ─── Zigzag / swing detection ────────────────────────────────────────────────
def _zigzag_pivots(close: pd.Series, threshold: float = ZIGZAG_PCT) -> list[dict]:
    """Standard zigzag: alternate HIGH/LOW pivots after `threshold` reversals.

    Returns a chronological list of {date, price, kind} where kind ∈ {"H","L"}.
    """
    if close is None or close.empty:
        return []
    pivots: list[dict] = []
    last_pivot_price = float(close.iloc[0])
    last_pivot_date  = close.index[0]
    last_pivot_kind  = None        # "H" or "L"
    extreme_price    = last_pivot_price
    extreme_date     = last_pivot_date
    direction        = 0           # +1 = looking for high; -1 = looking for low

    for date, price in close.items():
        price = float(price)
        if direction >= 0:
            if price > extreme_price:
                extreme_price, extreme_date = price, date
            elif price < extreme_price * (1 - threshold):
                # Confirmed a HIGH at extreme, now hunting for low
                if last_pivot_kind != "H":
                    pivots.append({"date": extreme_date, "price": extreme_price, "kind": "H"})
                    last_pivot_kind = "H"
                last_pivot_price, last_pivot_date = extreme_price, extreme_date
                extreme_price, extreme_date = price, date
                direction = -1
        if direction <= 0:
            if price < extreme_price:
                extreme_price, extreme_date = price, date
            elif price > extreme_price * (1 + threshold):
                if last_pivot_kind != "L":
                    pivots.append({"date": extreme_date, "price": extreme_price, "kind": "L"})
                    last_pivot_kind = "L"
                last_pivot_price, last_pivot_date = extreme_price, extreme_date
                extreme_price, extreme_date = price, date
                direction = +1

    # Append the trailing extreme so the last leg is visible to the caller.
    if last_pivot_kind != ("H" if direction >= 0 else "L"):
        pivots.append({"date": extreme_date, "price": extreme_price,
                        "kind": ("H" if direction >= 0 else "L")})
    return pivots


def _build_contractions(pivots: list[dict]) -> list[dict]:
    """Pair consecutive (HIGH, LOW) pivots into contraction records."""
    out = []
    for i in range(len(pivots) - 1):
        p, q = pivots[i], pivots[i + 1]
        if p["kind"] == "H" and q["kind"] == "L" and p["price"] > 0:
            depth = (p["price"] - q["price"]) / p["price"] * 100
            if depth > 0:
                out.append({
                    "high_date":    str(p["date"].date() if hasattr(p["date"], "date") else p["date"]),
                    "high":         round(p["price"], 2),
                    "low_date":     str(q["date"].date() if hasattr(q["date"], "date") else q["date"]),
                    "low":          round(q["price"], 2),
                    "pullback_pct": round(depth, 2),
                })
    return out


# ─── Main detector ───────────────────────────────────────────────────────────
def detect_vcp(df_d: pd.DataFrame,
                 zigzag_pct: float = ZIGZAG_PCT,
                 min_base_days: int = MIN_BASE_DAYS,
                 max_base_days: int = MAX_BASE_DAYS,
                 min_contractions: int = MIN_CONTRACTIONS,
                 vcp_contractions: int = VCP_CONTRACTIONS) -> dict:
    """Detect a VCP base in the trailing data, score it, and return a dict.

    Returns a fully-populated dict (see module docstring) — never raises.
    """
    blank = {
        "is_valid":           False,
        "base_start":         None,
        "base_length_days":   0,
        "contractions":       [],
        "contractions_all":   [],
        "pivot_price":        None,
        "current_close":      None,
        "days_since_pivot":   None,
        "broke_pivot":        False,
        "vol_dry_up":         False,
        "leading":            False,
        "quality_score":      0,
        "reason":             "insufficient data",
    }
    if df_d is None or df_d.empty or len(df_d) < min_base_days + 10:
        return blank
    if "Close" not in df_d.columns or "Volume" not in df_d.columns:
        blank["reason"] = "missing OHLCV columns"
        return blank

    work = df_d.tail(max_base_days + 30).copy()
    close = work["Close"].astype(float).dropna()
    vol   = work["Volume"].astype(float).fillna(0)
    if close.empty:
        return blank

    # 1) Leading-stock check (CAN-SLIM "C" approximation)
    leading = False
    if len(close) >= LEADING_LOOKBACK:
        ref = float(close.iloc[-LEADING_LOOKBACK])
        if ref > 0:
            leading = (float(close.iloc[-1]) - ref) / ref >= LEADING_MIN_GAIN

    # 2) Find swing pivots and pair into contractions
    pivots = _zigzag_pivots(close, threshold=zigzag_pct)
    contractions = _build_contractions(pivots)

    # 3) Take only contractions inside the trailing max_base_days window.
    last_date = close.index[-1]
    window_start = last_date - pd.Timedelta(days=max_base_days)
    in_window = []
    for c in contractions:
        try:
            cd = pd.Timestamp(c["high_date"])
            if cd >= window_start:
                in_window.append(c)
        except Exception:
            continue
    contractions = in_window

    if not contractions or len(contractions) < min_contractions:
        return {**blank,
                "current_close": round(float(close.iloc[-1]), 2),
                "leading":       leading,
                "contractions":  contractions,
                "reason":        f"only {len(contractions)} contraction(s) — need ≥{min_contractions}"}

    # 3b) THE BASE IS THE LAST N CONTRACTIONS, not every swing in the window.
    # Treating all of them as one base is what killed this gate: with 4-16 contractions
    # inside 325 days, `decreasing` was asking whether ten months of price action
    # tightened monotonically. A VCP is the final few contractions coiling into a pivot,
    # so that is what gets measured. The wider set is kept for context only.
    contractions_all = contractions
    contractions = contractions_all[-vcp_contractions:]

    # 4) Decreasing-depth check (each contraction tighter than the last)
    depths = [c["pullback_pct"] for c in contractions]
    decreasing = all(depths[i] > depths[i + 1] for i in range(len(depths) - 1))

    # 5) Tight-final-contraction check
    last_depth   = depths[-1]
    tight_final  = last_depth <= 12.0   # Minervini textbook ≤10%; allow 12% slack

    # 6) Base length
    try:
        base_start = pd.Timestamp(contractions[0]["high_date"])
    except Exception:
        base_start = None
    base_len_days = ((last_date - base_start).days
                       if base_start is not None else 0)

    base_len_ok = (min_base_days <= base_len_days <= max_base_days)

    # 7) Pivot price = high of the last contraction
    pivot_price = float(contractions[-1]["high"])
    cur_close   = float(close.iloc[-1])
    broke = cur_close > pivot_price * (1 + PIVOT_BREAK_BUFFER)

    # Days since pivot
    try:
        pivot_date = pd.Timestamp(contractions[-1]["high_date"])
        days_since_pivot = (last_date - pivot_date).days
    except Exception:
        days_since_pivot = None

    # 8) Volume dry-up: 5d avg < 50d avg
    vol_dry = False
    if len(vol) >= 50:
        vol5_avg  = float(vol.iloc[-5:].mean())
        vol50_avg = float(vol.iloc[-50:].mean())
        if vol50_avg > 0:
            vol_dry = vol5_avg < vol50_avg * 0.85   # 15%+ dry-up vs 50d

    # 9) Validity gate
    is_valid = (len(contractions) >= min_contractions
                  and decreasing and tight_final and base_len_ok)

    # 10) Quality score (0–100)
    score = 0
    if is_valid:                        score += 25
    if decreasing:                      score += 15
    if tight_final:                     score += 15
    if last_depth <= 8.0:               score += 10   # extra-tight bonus
    if base_len_ok:                     score += 10
    if vol_dry:                         score += 10
    if leading:                         score += 10
    if len(contractions) >= 3:          score += 5
    score = min(score, 100)

    reason_parts = [
        f"{len(contractions)} of {len(contractions_all)} contractions",
        f"depths {' > '.join(f'{d:.1f}%' for d in depths)}",
        f"base {base_len_days}d",
        "decreasing" if decreasing else "NOT decreasing",
        "tight final" if tight_final else "loose final",
    ]
    if leading:    reason_parts.append("leader")
    if vol_dry:    reason_parts.append("vol dry-up")
    if broke:      reason_parts.append(f"BROKE PIVOT @ {pivot_price:.2f}")

    return {
        "is_valid":           bool(is_valid),
        "base_start":         (str(base_start.date())
                                 if base_start is not None and hasattr(base_start, "date")
                                 else None),
        "base_length_days":   int(base_len_days),
        "contractions":       contractions,
        "contractions_all":   contractions_all,
        "pivot_price":        round(pivot_price, 2),
        "current_close":      round(cur_close, 2),
        "days_since_pivot":   int(days_since_pivot) if days_since_pivot is not None else None,
        "broke_pivot":        bool(broke),
        "vol_dry_up":         bool(vol_dry),
        "leading":            bool(leading),
        "quality_score":      int(score),
        "reason":             " · ".join(reason_parts),
    }


def pivot_quality_score(detection: dict) -> int:
    """Convenience accessor: score from a detect_vcp result, or 0."""
    if not detection:
        return 0
    return int(detection.get("quality_score", 0))


__all__ = ["detect_vcp", "pivot_quality_score",
           "ZIGZAG_PCT", "MIN_BASE_DAYS", "MAX_BASE_DAYS"]


if __name__ == "__main__":
    # Smoke-test against a known leading stock via data_provider.
    import sys
    if hasattr(sys.stdout, "encoding") and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try: sys.stdout.reconfigure(encoding="utf-8")
        except Exception: pass
    try:
        import data_provider as _dp
        for sym in ("HDFCBANK", "RELIANCE", "TCS", "INFY", "TRENT"):
            df = _dp.fetch_ohlcv(sym, period="1y", interval="1d")
            r = detect_vcp(df)
            print(f"{sym:<10}  valid={r['is_valid']:1}  "
                  f"score={r['quality_score']:3d}  "
                  f"contractions={len(r['contractions'])}  "
                  f"pivot={r['pivot_price']}  "
                  f"broke={r['broke_pivot']}  "
                  f"reason: {r['reason'][:80]}")
    except Exception as e:
        print(f"smoke test failed: {e}")
