"""house_policy.py — the ONE place the house rules live.

WHY (25-Sep-2026 integration audit). The same rule was held in several places and
they had drifted apart:
  * risk %  — GM sizer 0.5 / Capital Queue 0.5 / AI-LAB sniper 1.0 / Risk Shield heat
    budget 0.25 ("execution freeze", session-only) / six guidance strings "0.25%";
  * capital — GM sizer used the declared ₹ figure, AI-LAB used Dhan cash + deployed and
    fell back to a silent ₹50,00,000 when Dhan was down;
  * regime  — the header read Nifty 500 vs its 200-DMA while Risk Shield, the pyramid
    ladder and the GTT trailer read the composite score ≤ 5.

Every surface now imports from here. A number that is a house RULE is a constant in
this file; a number that is a USER SETTING (the declared capital, the per-trade ₹ cap)
lives in gm_settings.json and is read through the functions below, never re-read ad hoc.

Nothing in here computes a signal. It is policy, not analysis.
"""
from __future__ import annotations

import json
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_GM_SETTINGS = os.path.join(_HERE, "gm_settings.json")
_REGIME_STATE = os.path.join(_HERE, "regime_state.json")

# ── Risk per trade, % of sizing capital (Jay, 24-Sep-2026 — CLAUDE.md DNA) ────────────
RISK_NEW_STOCK_PCT = 0.5
ETF_RISK_MULT = 1.5                                  # S4 sizes an ETF at 1.5× its base
RISK_NEW_ETF_PCT = RISK_NEW_STOCK_PCT * ETF_RISK_MULT  # 0.75
RISK_ADD_PCT = 1.0                                   # a pyramid add

# ── Per-trade allocation cap (₹) — S4's `size_max_alloc` default. gm_settings
#    `max_alloc` overrides it; 0 / missing means "use this", never "uncapped".
MAX_ALLOC_DEFAULT = 100_000.0

# ── Book caps — the ORDER GATE's numbers. pre_trade_gate reads its defaults from
#    here (env overrides still win there), so the gate and every display agree.
MAX_OPEN_POSITIONS = 25        # Jay, 24-Sep-2026 (was 15 while the book held 22)
SECTOR_CAP_PCT = 25.0          # at cost, ai_risk_manager.analyze_sector_concentration
MAX_RISK_PCT = 1.5             # hard ceiling on any single order, % of equity

# ── Regime — the composite from market_regime.compute_regime (0..10, persisted
#    daily to regime_state.json). Bear = score ≤ 5, the rule the GTT trailer, the
#    pyramid ladder and Risk Shield already used; now one constant.
BEAR_SCORE_MAX = 5


def _settings() -> dict:
    try:
        with open(_GM_SETTINGS, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _num(x, default=float("nan")) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def is_etf(symbol: str) -> bool:
    try:
        import etf_universe as eu
        return bool(eu.is_etf(symbol))
    except Exception:
        return False


def risk_pct_for(symbol: str = "", add: bool = False) -> float:
    """House risk % for one order: add 1% · ETF 0.75% · stock 0.5%."""
    if add:
        return RISK_ADD_PCT
    return RISK_NEW_ETF_PCT if (symbol and is_etf(symbol)) else RISK_NEW_STOCK_PCT


def risk_label() -> str:
    """For guidance text, so no string hard-codes a percentage again."""
    return (f"{RISK_NEW_STOCK_PCT:g}% (ETF {RISK_NEW_ETF_PCT:g}%, add {RISK_ADD_PCT:g}%)")


def sizing_capital() -> tuple[float, str]:
    """(capital, source) that every SIZER uses.

    The declared capital in gm_settings is the sizing base: a deliberate number, stable
    through a drawdown, and the one the GM sizer and Capital Queue already used. Live
    equity (Dhan cash + holdings) is for measuring exposure, not for sizing. When the
    declaration is missing the answer is NaN with source "unset" — never an invented
    figure (the old ₹50,00,000 fallback sized real orders off a number nobody chose).
    """
    v = _num(_settings().get("capital"), 0.0)
    return (v, "gm_settings") if v > 0 else (float("nan"), "unset")


def max_alloc() -> float:
    """Per-trade ₹ cap: gm_settings max_alloc when set, else S4's default."""
    v = _num(_settings().get("max_alloc"), 0.0)
    return v if v > 0 else MAX_ALLOC_DEFAULT


def size_qty(symbol: str, entry: float, stop: float, add: bool = False,
             capital: float | None = None) -> tuple[int, str]:
    """Shares for one order at house risk and the ₹ cap. Returns (qty, note)."""
    entry, stop = _num(entry), _num(stop)
    if not (entry > 0 and stop > 0 and stop < entry):
        return 0, "no valid entry/stop"
    cap = capital if capital is not None else sizing_capital()[0]
    if not (cap and cap > 0):
        return 0, "capital unset in GM settings"
    rk = risk_pct_for(symbol, add)
    q = math.floor(cap * rk / 100.0 / (entry - stop))
    lim = math.floor(max_alloc() / entry)
    if q > lim:
        return lim, f"alloc-capped at ₹{max_alloc():,.0f}"
    return q, f"{rk:g}% risk"


def regime() -> dict:
    """Last persisted composite regime: {score, verdict, bear, computed_at}.

    Reads regime_state.json (written by the daily scheduler and by any live
    compute_regime(persist=True)). Missing/unreadable → score None, bear None —
    unknown is never reported as bull or bear.
    """
    try:
        with open(_REGIME_STATE, encoding="utf-8") as f:
            last = (json.load(f) or {}).get("last") or {}
    except Exception:
        last = {}
    sc = _num(last.get("score"))
    return {"score": None if math.isnan(sc) else sc,
            "verdict": last.get("verdict"),
            "bear": None if math.isnan(sc) else sc <= BEAR_SCORE_MAX,
            "computed_at": last.get("computed_at")}


def is_bear(score) -> bool:
    """The one bear rule, for callers that computed the score themselves."""
    v = _num(score)
    return (not math.isnan(v)) and v <= BEAR_SCORE_MAX
