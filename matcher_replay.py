"""
matcher_replay.py — Filter chartink-replay candidates through historical
conviction scoring. Phase 2.2 of the validation rebuild.

Mirrors brute_force_match_pro's bull-side flow:
  1. Chartink scan output  (already produced by chartink_replay)
  2. Inner-join with Screener.in fundamentals  (we replace this with the
     yfinance-derived `fundamental_replay.conviction_score_as_of`)
  3. Filter by minimum conviction score
  4. Pass survivors to the bull screener

Public API:
  filter_by_conviction(symbols, anchor, min_conviction)  -> list[str]
  conviction_table(symbols, anchor)                       -> pd.DataFrame

The conviction filter has a subtle behavior the production matcher exhibits:
stocks with NO fundamental data are EXCLUDED (in production they fail the
inner-join; here they fail because conviction_score_as_of returns 0.0 with
ok=False). This is the right default — the matcher's gate is essentially
"is this stock in our fundamental quality list?"
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

import fundamental_replay as _fr


logger = logging.getLogger(__name__)


def filter_by_conviction(symbols: list[str], anchor: str,
                            min_conviction: float = 6.0,
                            require_fundamentals: bool = True) -> list[str]:
    """Return only symbols whose conviction score at `anchor` ≥ min_conviction.

    Parameters
    ----------
    symbols              : Chartink-replay output for the anchor
    anchor               : ISO YYYY-MM-DD
    min_conviction       : threshold (matcher production default = 6.0
                            yields ~top-30% of fundamental quality)
    require_fundamentals : when True, stocks with NO fundamental data are
                            dropped (production matcher behavior). When False,
                            they're kept (technical-only signal).
    """
    out: list[str] = []
    for sym in symbols:
        try:
            score, breakdown = _fr.conviction_score_as_of(sym, anchor)
        except Exception as e:
            logger.debug("conviction lookup failed for %s @ %s: %s", sym, anchor, e)
            continue
        if not breakdown.get("ok"):
            if require_fundamentals:
                continue
            # If we don't require fundamentals, fall back to the base 5.0 score
            score = 5.0
        if score >= min_conviction:
            out.append(sym)
    return out


def conviction_table(symbols: list[str], anchor: str) -> pd.DataFrame:
    """Diagnostic table — every symbol's conviction breakdown at this anchor.
    Useful for debugging which stocks are being filtered out and why.
    """
    rows = []
    for sym in symbols:
        try:
            score, br = _fr.conviction_score_as_of(sym, anchor)
        except Exception:
            score, br = 0.0, {"ok": False}
        rows.append({
            "Symbol":       sym,
            "Score":        score,
            "Quarter_end":  br.get("quarter_end"),
            "ProfitG_pct":  br.get("profit_growth_qtr_pct"),
            "SalesG_pct":   br.get("sales_growth_qtr_pct"),
            "ROE_pct":      br.get("roe_pct"),
            "DE":           br.get("debt_to_equity"),
            "MarCap_Cr":    br.get("mar_cap_cr"),
            "Promoter_pct": br.get("promoter_pct"),
            "ok":           br.get("ok"),
        })
    return pd.DataFrame(rows).sort_values("Score", ascending=False).reset_index(drop=True)


__all__ = ["filter_by_conviction", "conviction_table"]
