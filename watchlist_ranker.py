# watchlist_ranker.py
# Weinstein Stage 2 setup scorer for watchlist stocks.
# Scores each symbol 0-100 and labels the stage/setup quality.
# No extra dependencies — yfinance + pandas + numpy only.

import os, logging, time
import numpy as np
import pandas as pd
import yfinance as yf

# C1: route OHLCV through the unified data_provider when available.
try:
    import data_provider as _dp
    USE_DATA_PROVIDER = True
except Exception:
    _dp = None
    USE_DATA_PROVIDER = False

logger = logging.getLogger(__name__)
_DIR = os.path.dirname(os.path.abspath(__file__))

BENCHMARK = "^CRSLDX"   # RS denominator (Nifty 500 — ^CNX500 is invalid on yfinance)

# Score weights (must sum to 100)
W = {
    "stage2":       25,   # price > SMA50 > SMA200, SMA200 rising
    "above_sma50":   8,   # above 50-day MA
    "above_sma200": 10,   # above 200-day MA
    "rs_vs_bench":  20,   # 3-month return vs CNX500
    "week52_pos":   12,   # proximity to 52-week high
    "volume_surge": 10,   # recent volume vs 50-day avg
    "sma200_slope": 15,   # SMA200 trending upward
}


def _yf_sym(sym: str) -> str:
    s = sym.strip().upper().replace(" ", "")
    if not s.endswith(".NS") and not s.startswith("^"):
        s += ".NS"
    return s


def rank_watchlist(symbols: list, period: str = "6mo") -> pd.DataFrame:
    """
    Score and rank a list of NSE symbols by Weinstein setup quality.

    Args:
        symbols: List of NSE symbols (e.g. ["RELIANCE", "INFY.NS"]).
        period:  yfinance download period string.

    Returns:
        DataFrame sorted best-setup-first with columns:
        Symbol, Score, Stage, SMA50, SMA200, RS_3M, 52W_Pos%, Vol_Surge, Grade
    """
    if not symbols:
        return pd.DataFrame()

    yf_syms = [_yf_sym(s) for s in symbols if s.strip()]

    # ── Fetch benchmark (C1: parquet-cached) ─────────────────────────────────
    bench_ret = 0.0
    try:
        import data_provider as dp
        braw = dp.fetch_ohlcv(BENCHMARK, period=period, interval="1d", use_cache=True, auto_adjust=True)
        bclose = braw["Close"].squeeze().dropna() if not braw.empty else pd.Series(dtype=float)
        if len(bclose) >= 65:
            bench_ret = float((bclose.iloc[-1] - bclose.iloc[-65]) / bclose.iloc[-65])
    except Exception as e:
        logger.warning("Benchmark fetch failed: %s", e)

    # ── Fetch universe in batches (C1: data_provider, then yf fallback) ──────
    all_close  = pd.DataFrame()
    all_volume = pd.DataFrame()
    batch_size = 30

    for i in range(0, len(yf_syms), batch_size):
        batch = yf_syms[i: i + batch_size]
        c_batch = v_batch = None
        try:
            import data_provider as dp
            bd = dp.fetch_batch_ohlcv(batch, period=period, interval="1d", use_cache=True, auto_adjust=True)
            if bd:
                # Restore .NS suffix so the join key set matches the input
                c_batch = pd.DataFrame({
                    (k if k.startswith("^") else f"{k}.NS"): df["Close"]
                    for k, df in bd.items() if "Close" in df.columns
                })
                v_batch = pd.DataFrame({
                    (k if k.startswith("^") else f"{k}.NS"): df["Volume"]
                    for k, df in bd.items() if "Volume" in df.columns
                })
        except Exception as e:
            logger.warning("data_provider batch %d failed: %s", i // batch_size, e)
            c_batch = v_batch = pd.DataFrame()
        
        if c_batch.empty:
            continue

        all_close  = c_batch if all_close.empty  else all_close.join(c_batch, how="outer")
        all_volume = v_batch if all_volume.empty else all_volume.join(v_batch, how="outer")

    if all_close.empty:
        return pd.DataFrame()

    rows = []
    for sym_yf, sym_orig in zip(yf_syms, symbols):
        try:
            if sym_yf not in all_close.columns:
                continue
            close = all_close[sym_yf].dropna()
            vol   = all_volume[sym_yf].dropna() if sym_yf in all_volume.columns else pd.Series(dtype=float)

            if len(close) < 50:
                continue

            ltp      = float(close.iloc[-1])
            high_52w = float(close.tail(252).max())
            low_52w  = float(close.tail(252).min())

            sma50  = float(close.rolling(50).mean().iloc[-1])
            sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else float("nan")
            sma200_20d = float(close.rolling(200).mean().iloc[-21]) if len(close) >= 221 else float("nan")

            above50  = ltp > sma50
            above200 = ltp > sma200 if not np.isnan(sma200) else False
            sma50_above_sma200 = sma50 > sma200 if not np.isnan(sma200) else False
            sma200_rising = (sma200 > sma200_20d) if not (np.isnan(sma200) or np.isnan(sma200_20d)) else False

            stage2 = above50 and above200 and sma50_above_sma200 and sma200_rising

            # RS vs benchmark (3-month / 65 days)
            ret_3m = float((close.iloc[-1] - close.iloc[-65]) / close.iloc[-65]) if len(close) >= 65 else 0.0
            rs_diff = ret_3m - bench_ret   # positive = outperforming

            # 52W position (how close to 52W high, 0–100)
            rng = high_52w - low_52w
            week52_pos = ((ltp - low_52w) / rng * 100) if rng > 0 else 50.0

            # Volume surge (recent 5-day avg vs 50-day avg)
            vol_surge = 1.0
            if len(vol) >= 50:
                vol50  = float(vol.rolling(50).mean().iloc[-1])
                vol5   = float(vol.tail(5).mean())
                vol_surge = vol5 / vol50 if vol50 > 0 else 1.0

            # SMA200 slope score (% change over 20 days)
            sma200_slope_pct = ((sma200 - sma200_20d) / sma200_20d * 100
                                if not (np.isnan(sma200) or np.isnan(sma200_20d)) else 0.0)

            # ── Scoring ────────────────────────────────────────────────────
            score = 0.0
            score += W["stage2"]       * (1.0 if stage2 else 0.0)
            score += W["above_sma50"]  * (1.0 if above50 else 0.0)
            score += W["above_sma200"] * (1.0 if above200 else 0.0)
            score += W["rs_vs_bench"]  * max(0.0, min(1.0, (rs_diff + 0.20) / 0.40))  # normalise ±20% → 0-1
            score += W["week52_pos"]   * (week52_pos / 100.0)
            score += W["volume_surge"] * max(0.0, min(1.0, (vol_surge - 0.5) / 2.0))  # 0.5x→0, 2.5x→1
            score += W["sma200_slope"] * max(0.0, min(1.0, (sma200_slope_pct + 1.0) / 3.0))  # -1%→0, +2%→1

            score = round(score, 1)

            # Stage label — Weinstein canonical:
            #   Stage 2: above SMA200 + SMA200 rising         (confirmed uptrend)
            #   Stage 3: above SMA200 + SMA200 flat/declining (topping)
            #   Stage 4: below SMA200 + SMA200 declining      (downtrend)
            #   Stage 1: below SMA200 + SMA200 flat/rising    (basing)
            #
            # 10 May 2026 fix:
            #   (a) The previous "Stage 1" and "Stage 3" branches were SWAPPED
            #       — `above200 and not sma200_rising` is Stage 3 (Top), not
            #       Stage 1; and `not above200 and sma200_rising` is Stage 1
            #       (Base), not Stage 3.
            #   (b) NaN SMA200 (stocks with <200 trading days of data) silently
            #       fell into the Stage 4 "else" branch. Now flagged explicitly
            #       so the user knows the classification is data-limited, not a
            #       genuine downtrend signal.
            if np.isnan(sma200) or np.isnan(sma200_20d):
                stage_label = "⚪ Stage ? (insufficient history)"
            elif stage2:
                stage_label = "🟢 Stage 2"
            elif above200 and not sma200_rising:
                stage_label = "🟡 Stage 3 (Top)"
            elif not above200 and sma200_rising:
                stage_label = "🟡 Stage 1 (Base)"
            elif not above200 and not sma200_rising:
                stage_label = "🔴 Stage 4"
            else:
                # above 200 + rising but somehow not stage2 (e.g. SMA50 below SMA200)
                stage_label = "🟡 Stage 2 (Transitioning)"

            # Grade
            if score >= 80:   grade = "⭐⭐⭐ A+"
            elif score >= 65: grade = "⭐⭐ A"
            elif score >= 50: grade = "⭐ B"
            elif score >= 35: grade = "C"
            else:             grade = "D"

            rows.append({
                "Symbol":     sym_orig.strip().upper().replace(".NS", ""),
                "Score":      score,
                "Grade":      grade,
                "Stage":      stage_label,
                "LTP":        round(ltp, 2),
                "SMA50":      round(sma50, 2),
                "SMA200":     round(sma200, 2) if not np.isnan(sma200) else None,
                "RS_3M%":     round(ret_3m * 100, 1),
                "Bench_3M%":  round(bench_ret * 100, 1),
                "RS_Edge%":   round(rs_diff * 100, 1),
                "52W_Pos%":   round(week52_pos, 1),
                "Vol_Surge":  round(vol_surge, 2),
                "SMA200_Slope%": round(sma200_slope_pct, 2),
            })

        except Exception as e:
            logger.debug("Score failed for %s: %s", sym_yf, e)
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).sort_values("Score", ascending=False).reset_index(drop=True)
    logger.info("Ranked %d stocks | top: %s (%.1f)", len(df),
                df.iloc[0]["Symbol"] if len(df) else "–",
                df.iloc[0]["Score"] if len(df) else 0)
    return df


def load_watchlist_symbols() -> list:
    """
    Auto-load symbols from any CSV files in the project folder
    that look like watchlists (contain a 'Symbol' or 'Ticker' column).
    Falls back to empty list.
    """
    syms = set()
    for fname in os.listdir(_DIR):
        if not fname.endswith(".csv"):
            continue
        if any(kw in fname.lower() for kw in ("watchlist", "stage2", "golden", "match")):
            try:
                df = pd.read_csv(os.path.join(_DIR, fname))
                col = next((c for c in df.columns if c.strip().lower() in
                            ("symbol","ticker","nse","scrip")), None)
                if col:
                    for s in df[col].dropna().tolist():
                        if isinstance(s, str) and 2 <= len(s.strip()) <= 20:
                            syms.add(s.strip().upper())
            except Exception:
                continue
    return sorted(syms)
