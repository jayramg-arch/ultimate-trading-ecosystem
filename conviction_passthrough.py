"""
conviction_passthrough.py — Add Screener.in Conviction + Combined_Score
to the output of bull_screener.py / recovery_screener.py.

Bull and Recovery Screeners produce technically-rich output (Score, Stage,
RSI, ADX, Mansfield, etc.) but lack the fundamentals overlay (Conviction)
that Golden Matcher applies. This helper fills that gap so all three
screeners' outputs carry a consistent `Combined_Score` — the same blend
used in `FINAL_WATCHLIST.csv` (Conviction × 0.5 + Tech × 0.5, both
normalized to 0-100).

Public API
----------
    add_conviction_and_combined_score(
        df, mode='bull', score_col='Score', symbol_col='Symbol'
    ) -> pd.DataFrame
        Mutates `df` in-place AND returns it. Adds:
          'Conviction'      : 0-10 from Screener.in fundamentals
          'Combined_Score'  : 0-100, (Conviction*10)*0.5 + (Score normalized)*0.5

        mode='bull'     → uses Stage 2 conviction logic
        mode='recovery' → uses Recovery conviction logic (rewards balance sheet)

    The function silently degrades if MASTER_scan_results.csv isn't readable —
    Conviction stays None and Combined_Score collapses to Tech only.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
MASTER_FILE = os.path.join(_HERE, "MASTER_scan_results.csv")

# Cache the master fundamentals file in-process so multiple screener calls
# in one Python session don't re-read the disk.
_master_cache: Optional[pd.DataFrame] = None


def _load_master() -> Optional[pd.DataFrame]:
    """Read MASTER_scan_results.csv as dtype=str. Cached. Returns None on failure."""
    global _master_cache
    if _master_cache is not None:
        return _master_cache
    if not os.path.exists(MASTER_FILE):
        logger.warning("MASTER_scan_results.csv not found at %s — Conviction "
                       "passthrough disabled.", MASTER_FILE)
        return None
    try:
        df = pd.read_csv(MASTER_FILE, dtype=str)
        # Normalize Symbol column for matching
        sym_col = next((c for c in df.columns
                        if c.lower() in ("symbol", "nsecode", "name", "ticker")), None)
        if sym_col is None:
            logger.warning("No Symbol column in MASTER — passthrough disabled.")
            return None
        if sym_col != "Symbol":
            df.rename(columns={sym_col: "Symbol"}, inplace=True)
        # B5 FIX (19 Jun 2026): MASTER carries RAW Screener.in column names
        # ('Return on equity', 'Return on capital employed', ...), but the
        # conviction scorers expect the GOLDEN names ('ROE %', 'ROCE %', ...) —
        # the same rename brute_force_match_pro applies to `merged`. Without
        # this, only 'Debt to equity' (identically named) ever matched, so every
        # conviction collapsed to a degenerate base+D/E (~5.0/7.0). Apply the
        # same rename here so passthrough conviction is computed on real fields.
        _GOLDEN_RENAME = {
            "Return on capital employed": "ROCE %",
            "Return on equity":           "ROE %",
            "Market Capitalization":      "Mar Cap Rs.Cr.",
            "YOY Quarterly sales growth": "Qtr Sales Var %",
            "YOY Quarterly profit growth":"Qtr Profit Var %",
            "Current Price":              "CMP Rs.",
        }
        for _raw, _gold in _GOLDEN_RENAME.items():
            _actual = next((c for c in df.columns if c.strip().lower() == _raw.lower()), None)
            if _actual and _gold not in df.columns:
                df.rename(columns={_actual: _gold}, inplace=True)
        df["MATCH_KEY"] = df["Symbol"].astype(str).str.upper().str.strip()
        _master_cache = df
        return df
    except Exception as e:
        logger.warning("Failed to load MASTER: %s — passthrough disabled.", e)
        return None


def _get_conviction_fn(mode: str):
    """Lazy-import the matcher's conviction function so we share its logic
    rather than re-implementing it (single source of truth).
    """
    try:
        if mode == "recovery":
            from brute_force_match_pro import calculate_recovery_conviction_score as _fn
        else:
            from brute_force_match_pro import calculate_conviction_score as _fn
        return _fn
    except ImportError as e:
        logger.warning("Could not import conviction fn from matcher: %s — "
                       "passthrough disabled.", e)
        return None


def _calc_combined_score(conviction, tech_score) -> float:
    """0-100 blend of Conviction (0-10 → ×10) and Tech_Score (0-100), 50/50.
    Falls back to whichever is available."""
    try:
        conv_n = float(conviction) * 10 if conviction not in (None, "", "N/A") else None
    except (TypeError, ValueError):
        conv_n = None
    try:
        tech_n = float(tech_score) if tech_score not in (None, "", "N/A") else None
    except (TypeError, ValueError):
        tech_n = None

    if conv_n is not None and tech_n is not None:
        return round(conv_n * 0.5 + tech_n * 0.5, 1)
    if conv_n is not None:
        return round(conv_n, 1)
    if tech_n is not None:
        return round(tech_n, 1)
    return 0.0


def _extend_recovery_conviction(df, symbol_col, sym_to_conv, conv_fn) -> int:
    """Q1 FIX (19 Jun 2026): the Stage-2 MASTER only carries value-style
    fundamentals (ROE/ROCE/mcap/promoter/div/growth) for the ~16/78 recovery
    names that overlap it; the recovery Screener.in source has RFF fields
    instead. For the rest, fetch per-symbol via fundamental_hub (Screener.in
    primary, yfinance fallback) and compute the SAME recovery conviction, so the
    full recovery set gets a conviction value rather than tech-only.

    Cached by fundamental_hub (ttl); failures degrade to no-entry (tech-only) —
    never raises, no regression. Returns count of names newly resolved.
    """
    try:
        import fundamental_hub as _fh
    except Exception as e:
        logger.warning("fundamental_hub unavailable (%s) — recovery conviction stays partial", e)
        return 0

    missing, seen = [], set()
    for raw in df[symbol_col].dropna().astype(str):
        key = raw.upper().strip().replace("NSE:", "").replace("BSE:", "").replace(".NS", "")
        if key and key not in sym_to_conv and key not in seen:
            seen.add(key); missing.append(key)
    if not missing:
        return 0

    logger.info("Recovery conviction: fetching fundamentals for %d names not in "
                "Stage-2 master (Q1 coverage extension)", len(missing))
    resolved = 0
    for key in missing:
        try:
            fh = _fh.fetch_stock_fundamentals(f"{key}.NS") or {}
            if not fh:
                continue
            # Map fundamental_hub keys/units -> the golden column names the
            # recovery conviction scorer expects (roe/roce/div/growth = %,
            # debt_equity = ratio, market_cap = Cr — all already aligned).
            row = {
                "Debt to equity":     fh.get("debt_equity"),
                "ROCE %":             fh.get("roce"),
                "ROE %":              fh.get("roe"),
                "Promoter holding %": fh.get("promoter_holding"),
                "Div Yld %":          fh.get("dividend_yield"),
                "Qtr Profit Var %":   fh.get("earnings_growth"),
                "Mar Cap Rs.Cr.":     fh.get("market_cap"),
            }
            if any(v is not None for v in row.values()):
                sym_to_conv[key] = conv_fn(row)
                resolved += 1
        except Exception as e:
            logger.debug("recovery conviction fetch failed for %s: %s", key, e)
    logger.info("Recovery conviction: resolved %d/%d additional names", resolved, len(missing))
    return resolved


def add_conviction_and_combined_score(
    df: pd.DataFrame,
    mode: str = "bull",
    score_col: str = "Score",
    symbol_col: str = "Symbol",
) -> pd.DataFrame:
    """Add Conviction + Combined_Score columns to a screener output DataFrame.

    The screener's existing Score column (whatever it represents — bull_screener
    uses 0-100 catalyst quality, recovery_screener uses 0-22) is normalized to
    0-100 before blending. For bull (already 0-100) the normalization is a no-op.

    RANKING-INTEGRITY FIX (19 Jun 2026): the recovery factor was 100/12, but
    recovery_screener.compute_score actually maxes at 22 (rff 8 + rs 2 + corr 3
    + regime 2 + stage 1 + signal 3 + vol 2 + chartink 1). With /12, every
    recovery pick scoring >=12 saturated to tech_norm=100 — washing out the
    recovery signal's discriminating power above 12 (the actionable picks score
    14-18). Corrected to 100/22 so the full range maps without saturation.
    """
    if df is None or df.empty or symbol_col not in df.columns:
        return df

    master = _load_master()
    conv_fn = _get_conviction_fn(mode)

    if master is None or conv_fn is None:
        # Graceful: don't add Conviction, just compute Combined from Tech alone
        df["Conviction"] = None
        df["Combined_Score"] = df.apply(
            lambda r: _calc_combined_score(None, r.get(score_col)), axis=1
        )
        return df

    # Build Symbol → Conviction map
    sym_to_conv: Dict[str, float] = {}
    for _, master_row in master.iterrows():
        key = master_row.get("MATCH_KEY", "")
        if key:
            sym_to_conv[key] = conv_fn(master_row)

    # Q1 coverage extension: for recovery names absent from the Stage-2 master,
    # fetch value-style fundamentals per-symbol so the whole set gets conviction.
    if mode == "recovery":
        _extend_recovery_conviction(df, symbol_col, sym_to_conv, conv_fn)

    # Normalize Score: bull = already 0-100; recovery = 0-22 (compute_score max)
    # → ×4.545. (Was 100/12 which saturated every pick scoring >=12 to 100.)
    score_norm_factor = 100.0 / 22.0 if mode == "recovery" else 1.0

    def _row_eval(row):
        sym_key = str(row.get(symbol_col, "")).upper().strip() \
                    .replace("NSE:", "").replace("BSE:", "").replace(".NS", "")
        conv = sym_to_conv.get(sym_key)
        try:
            tech_raw = float(row.get(score_col, 0) or 0)
            tech_norm = min(100.0, tech_raw * score_norm_factor)
        except (TypeError, ValueError):
            tech_norm = None
        return pd.Series({
            "Conviction":     conv,
            "Combined_Score": _calc_combined_score(conv, tech_norm),
        })

    enriched = df.apply(_row_eval, axis=1)
    df["Conviction"]     = enriched["Conviction"]
    df["Combined_Score"] = enriched["Combined_Score"]
    return df


__all__ = ["add_conviction_and_combined_score"]
