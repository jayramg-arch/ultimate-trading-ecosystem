"""
v2_fixes.py — Candidate fixes for the Top-N ranking failure observed in
the Jan-15-26 anchor (the only losing anchor in the v1 LOCKED backtest).

v2.3 ENHANCEMENTS (2026-05-10)
------------------------------
Flags 6-9 implement cross-module intelligence enhancements that make
the system regime-aware, risk-capped, and streak-guarded. They add NO
new screens or UI options — they surgically improve existing decision
logic inside bull_screener, exit_signal_engine, and sniper_trigger.

Background
----------
v1 FINAL (Run ID 20260508_105114) delivered alpha 4.45% / hit-rate 91.7%.
The lone miss (Jan-15-26, -3.23 alpha) was diagnosed as a *ranking* failure
rather than a *signal* failure: the 45-candidate universe contained the
eventual winners (MAHABANK +15.17, BANKINDIA +15.16, GESHIP +20.16,
APLAPOLLO +15.50) at ranks 11+, while Top-N=10 took COALINDIA, MANAPPURAM,
HCLTECH instead.

Five root-cause failure modes were identified (BACKTEST_RESULTS_v1.docx §6.2).
This module implements them as **togglable feature flags** so each can be
ablated against the v1 FINAL baseline. None of the flags are active by
default — turning them on requires explicit opt-in via V2_FLAGS or per-call.

Usage (single fix)
------------------
    import v2_fixes as v2
    v2.V2_FLAGS["vcp_score_multiplier"] = True
    # then run validation.run_validation(...) — bull_screener and validation
    # will pick up the flag automatically through the registered hooks.

Usage (full ablation)
---------------------
    See run_v2_ablation.py — wraps a single flag at a time, runs validation,
    and writes a row to validation_runs/v2_ablation_results.csv.

Fixes
-----
1. vcp_score_multiplier      — Score *= 0.5 when VCP_Valid is False
2. days_since_pivot_penalty  — Score -= 10 when Days_Since_Pivot > 30
3. sector_cap_top_n          — at most 3 picks per sector in Top-N
4. pos_accum_rsi_nullout     — POS-ACCUM catalyst score → 0 when RSI > 50
5. tiebreak_rs_momentum      — break Score ties by RS_Momentum_4W desc
6. regime_score_penalty      — E-1: penalize screener picks in weak regimes
7. regime_exit_accelerator   — E-2: tighten exit thresholds in bear regimes
8. portfolio_heat_ceiling    — E-3: block new entries when total risk > 6%
9. consecutive_loss_breaker  — E-4: block entries after 3 consecutive losses

References
----------
- Forensic table: BACKTEST_RESULTS_v1.docx, Section 6
- Hooks integrated in: bull_screener.screen_symbol() and validation.run_validation()
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─── Feature flags ───────────────────────────────────────────────────────────
# All default OFF — set True (or use enable() / enable_all()) to activate.
# Each flag corresponds to one ablation cell.
V2_FLAGS: dict[str, bool] = {
    "vcp_score_multiplier":      False,  # Fix #1 — REJECTED v2 ablation (drops α both universes)
    "days_since_pivot_penalty":  False,  # Fix #2 — defensive-mode toggle, not default (universe-dependent)
    "sector_cap_top_n":          False,  # Fix #3 — REJECTED v2 ablation (drops α both universes)
    "pos_accum_rsi_nullout":     True,   # Fix #4 — v2 LOCKED 2026-05-10 (raw +0.14pp, filtered +0.26pp, hit held)
    "tiebreak_rs_momentum":      False,  # Fix #5 — REJECTED v2 ablation (drops hit-rate both universes)
    # ── v2.3 Enhancements (E-1 through E-4) ──────────────────────────────
    "regime_score_penalty":      True,   # E-1: penalize screener picks in weak market regimes
    "regime_exit_accelerator":   True,   # E-2: tighten exit thresholds when regime is bearish
    "portfolio_heat_ceiling":    True,   # E-3: block new entries when total portfolio risk > ceiling
    "consecutive_loss_breaker":  True,   # E-4: block entries after N consecutive losses
}

# Parameters (tunable per fix)
V2_PARAMS = {
    "vcp_invalid_multiplier":   0.5,    # Fix #1: multiplier when VCP_Valid is False
    "days_since_pivot_max":     30,     # Fix #2: threshold above which penalty kicks in
    "days_since_pivot_penalty": 10,     # Fix #2: points to subtract from Score
    "sector_cap":               3,      # Fix #3: max picks per sector in Top-N
    "pos_accum_rsi_threshold":  50,     # Fix #4: RSI above which POS-ACCUM is nullified
    # ── v2.3 Enhancement parameters ──────────────────────────────────────
    "regime_penalty_bear":      20,     # E-1: score penalty when regime ≤ 2 (Bear/Cash)
    "regime_penalty_defensive": 10,     # E-1: score penalty when regime 3-4 (Defensive)
    "regime_bonus_bull":         5,     # E-1: score bonus when regime ≥ 8 (Bull Healthy)
    "regime_exit_r_shift":      0.5,    # E-2: R-multiple triggers fire 0.5R earlier in bear regime
    "regime_exit_stage3_trim":  50,     # E-2: Stage 3 trim % in bear regime (vs 25% normal)
    "portfolio_heat_block_pct": 6.0,    # E-3: total portfolio risk % → hard block
    "portfolio_heat_warn_pct":  4.0,    # E-3: total portfolio risk % → warning
    "consecutive_loss_block":    3,     # E-4: N consecutive losses → hard block
    "consecutive_loss_warn":     2,     # E-4: N consecutive losses → warning
}


def enable(flag: str) -> None:
    """Turn ON a single v2 fix (raises KeyError if unknown)."""
    if flag not in V2_FLAGS:
        raise KeyError(f"Unknown v2 flag: {flag!r}. Valid: {list(V2_FLAGS)}")
    V2_FLAGS[flag] = True


def disable(flag: str) -> None:
    if flag not in V2_FLAGS:
        raise KeyError(f"Unknown v2 flag: {flag!r}. Valid: {list(V2_FLAGS)}")
    V2_FLAGS[flag] = False


def enable_all() -> None:
    for k in V2_FLAGS:
        V2_FLAGS[k] = True


def reset() -> None:
    for k in V2_FLAGS:
        V2_FLAGS[k] = False


def active_flags() -> list[str]:
    return [k for k, v in V2_FLAGS.items() if v]


# ─── Fix #4: POS-ACCUM nullout — applied at catalyst-score time ──────────────
def adjust_catalyst_score(cat_label: str, base_score: int, daily_rsi: float) -> int:
    """Hook called from bull_screener.calculate_score() before catalyst tier is added.

    Returns the (possibly adjusted) catalyst contribution. By default returns base_score.
    """
    if not V2_FLAGS["pos_accum_rsi_nullout"]:
        return base_score
    if cat_label == "POS-ACCUM" and daily_rsi is not None and daily_rsi > V2_PARAMS["pos_accum_rsi_threshold"]:
        return 0  # nullify late-stage catalyst trap
    return base_score


# ─── Fix #1 + #2: VCP multiplier and Days_Since_Pivot penalty ────────────────
def adjust_record_score(record: dict) -> dict:
    """Hook called from bull_screener.screen_symbol() AFTER the record dict is built.

    Mutates and returns `record` with adjusted Score. The original Score is
    preserved as `Score_pre_v2` for diff inspection.

    Applied fixes:
      - vcp_score_multiplier:     Score *= V2_PARAMS["vcp_invalid_multiplier"]
                                  when record["VCP_Valid"] is False
      - days_since_pivot_penalty: Score -= V2_PARAMS["days_since_pivot_penalty"]
                                  when record["Days_Since_Pivot"] > V2_PARAMS["days_since_pivot_max"]
    """
    if not V2_FLAGS["vcp_score_multiplier"] and not V2_FLAGS["days_since_pivot_penalty"]:
        return record

    score = float(record.get("Score", 0))
    record["Score_pre_v2"] = score

    if V2_FLAGS["vcp_score_multiplier"]:
        if not record.get("VCP_Valid", False):
            score *= V2_PARAMS["vcp_invalid_multiplier"]

    if V2_FLAGS["days_since_pivot_penalty"]:
        dsp = record.get("Days_Since_Pivot")
        if dsp is not None and dsp > V2_PARAMS["days_since_pivot_max"]:
            score -= V2_PARAMS["days_since_pivot_penalty"]

    record["Score"] = max(0, int(round(score)))
    return record


# ─── Fix #3 + #5: sector cap and RS_Momentum tiebreak — applied at Top-N time ─
def select_top_n(picks: pd.DataFrame,
                 top_n: int,
                 sector_lookup_fn: Optional[callable] = None) -> pd.DataFrame:
    """Hook called from validation.run_validation() AFTER Score sort, BEFORE head(top_n).

    Behaviour:
      1. If `tiebreak_rs_momentum` flag is set, secondary sort key is RS_Momentum_4W desc.
      2. If `sector_cap_top_n` flag is set, no more than V2_PARAMS["sector_cap"] picks
         per sector in the final Top-N. Requires `sector_lookup_fn(symbol) -> str` or
         a `Sector` column already present on `picks`.

    Returns a new DataFrame of <= top_n rows.
    """
    if picks.empty or top_n is None:
        return picks

    # FAST PATH — no-op when both relevant flags are off. Must be byte-identical
    # to validation.py's fallback (`picks.sort_values("Score", ascending=False).head(top_n)`)
    # so a "v2 hook present, all flags off" run reproduces the v1 FINAL baseline
    # exactly. (See BACKTEST_RESULTS_v2.docx §8.1 for the drift incident.)
    if not V2_FLAGS["tiebreak_rs_momentum"] and not V2_FLAGS["sector_cap_top_n"]:
        return picks.sort_values("Score", ascending=False).head(top_n)

    # Step A: stable sort with optional tiebreak
    sort_cols = ["Score"]
    sort_asc = [False]
    if V2_FLAGS["tiebreak_rs_momentum"] and "RS_Momentum_4W" in picks.columns:
        sort_cols.append("RS_Momentum_4W")
        sort_asc.append(False)

    df = picks.sort_values(by=sort_cols, ascending=sort_asc, kind="mergesort").reset_index(drop=True)

    # Step B: optional sector cap
    if V2_FLAGS["sector_cap_top_n"]:
        cap = V2_PARAMS["sector_cap"]
        # Resolve sector column
        if "Sector" not in df.columns:
            if sector_lookup_fn is None:
                # Try to import the project-standard helper
                try:
                    from sector_lookup import get_sector_index as _gsi
                    sector_lookup_fn = _gsi
                except Exception:
                    logger.warning("sector_cap_top_n: no sector lookup available; cap disabled")
                    return df.head(top_n)
            df = df.copy()
            df["Sector"] = df["Symbol"].astype(str).map(lambda s: sector_lookup_fn(s) or "UNKNOWN")

        # Greedy selection respecting the cap
        kept_idx, sector_counts = [], {}
        for idx, row in df.iterrows():
            sec = row["Sector"]
            if sector_counts.get(sec, 0) >= cap:
                continue
            kept_idx.append(idx)
            sector_counts[sec] = sector_counts.get(sec, 0) + 1
            if len(kept_idx) >= top_n:
                break

        # If the cap was binding hard and we didn't fill Top-N, allow overflow from
        # remaining symbols (preserve sort order). This protects against thin universes.
        if len(kept_idx) < top_n:
            remaining = [i for i in df.index if i not in kept_idx]
            kept_idx.extend(remaining[: top_n - len(kept_idx)])

        return df.loc[kept_idx].head(top_n).reset_index(drop=True)

    return df.head(top_n)


# ─── E-1: Regime-aware score adjustment (bull_screener hook) ─────────────────
def _read_regime_score() -> Optional[int]:
    """Read the cached regime score from regime_state.json.

    Returns the score (0-10) or None if the file is missing / stale (>60 min).
    Shared by E-1, E-2, E-3, and E-4 hooks.
    """
    import os as _os, json as _json
    from datetime import datetime as _dt, timedelta as _td
    state_path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)), "regime_state.json"
    )
    if not _os.path.exists(state_path):
        return None
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = _json.load(f)
        last = state.get("last", {})
        ts = last.get("computed_at", "")
        if ts:
            age = _dt.now() - _dt.fromisoformat(ts)
            if age > _td(minutes=60):
                logger.debug("regime_state.json is >60 min old; returning stale score")
        return last.get("score")
    except Exception as e:
        logger.debug(f"_read_regime_score failed: {e}")
        return None


def regime_score_adjust(base_score: int) -> int:
    """E-1 hook: called from bull_screener.compute_score() to adjust the
    final score based on the current market regime.

    Regime ≤ 2 (Bear/Cash):     -20 pts
    Regime 3-4 (Defensive):     -10 pts
    Regime 5-7 (Neutral/Cautious): no change
    Regime ≥ 8 (Bull Healthy):   +5 pts
    Regime unknown:              no change

    Returns the adjusted score (clamped to [0, 100]).
    """
    if not V2_FLAGS["regime_score_penalty"]:
        return base_score
    regime = _read_regime_score()
    if regime is None:
        return base_score
    if regime <= 2:
        base_score -= V2_PARAMS["regime_penalty_bear"]
    elif regime <= 4:
        base_score -= V2_PARAMS["regime_penalty_defensive"]
    elif regime >= 8:
        base_score += V2_PARAMS["regime_bonus_bull"]
    return max(0, min(base_score, 100))


# ─── E-2: Regime-accelerated exit parameters ─────────────────────────────────
def get_exit_regime_overrides() -> dict:
    """E-2 hook: called from exit_signal_engine.recommend_actions() to
    retrieve regime-adjusted exit parameters.

    Returns a dict with:
      - 'active': bool — whether the accelerator is active
      - 'regime_score': int | None
      - 'r_shift': float — how much to lower R-multiple thresholds (0 if inactive)
      - 'stage3_trim_pct': int — trim % for Stage 3 topping
      - 'exit_below_entry_in_bear': bool — full exit if below entry in regime ≤ 2
    """
    defaults = {
        "active": False, "regime_score": None, "r_shift": 0.0,
        "stage3_trim_pct": 25, "exit_below_entry_in_bear": False,
    }
    if not V2_FLAGS["regime_exit_accelerator"]:
        return defaults
    regime = _read_regime_score()
    if regime is None:
        return defaults
    result = {"active": True, "regime_score": regime}
    if regime <= 2:
        result["r_shift"] = V2_PARAMS["regime_exit_r_shift"]
        result["stage3_trim_pct"] = V2_PARAMS["regime_exit_stage3_trim"]
        result["exit_below_entry_in_bear"] = True
    elif regime <= 3:
        result["r_shift"] = V2_PARAMS["regime_exit_r_shift"]
        result["stage3_trim_pct"] = V2_PARAMS["regime_exit_stage3_trim"]
        result["exit_below_entry_in_bear"] = False
    else:
        result["r_shift"] = 0.0
        result["stage3_trim_pct"] = 25
        result["exit_below_entry_in_bear"] = False
    return result


# ─── E-3 / E-4: Pre-flight gates (sniper_trigger hooks) ─────────────────────
def portfolio_heat_check(open_positions: list[dict],
                         new_risk_rupees: float,
                         total_capital: float) -> dict:
    """E-3 hook: compute total portfolio heat and return block/warn/ok.

    Parameters
    ----------
    open_positions : list of dicts with keys 'buy_price', 'stoploss', 'quantity'
    new_risk_rupees : risk of the proposed new trade in ₹
    total_capital : total account equity in ₹

    Returns {"status": "block"|"warn"|"ok", "current_heat_pct": float,
             "projected_heat_pct": float, "message": str}
    """
    if not V2_FLAGS["portfolio_heat_ceiling"]:
        return {"status": "ok", "current_heat_pct": 0.0,
                "projected_heat_pct": 0.0, "message": ""}
    current_risk = 0.0
    for pos in open_positions:
        bp = float(pos.get("buy_price", 0) or 0)
        sl = float(pos.get("stoploss", 0) or 0)
        qty = float(pos.get("quantity", 0) or 0)
        if bp > 0 and sl > 0 and qty > 0 and bp > sl:
            current_risk += (bp - sl) * qty
    if total_capital <= 0:
        return {"status": "ok", "current_heat_pct": 0.0,
                "projected_heat_pct": 0.0, "message": "capital unknown"}
    current_pct = current_risk / total_capital * 100
    projected_pct = (current_risk + max(0, new_risk_rupees)) / total_capital * 100
    block_at = V2_PARAMS["portfolio_heat_block_pct"]
    warn_at = V2_PARAMS["portfolio_heat_warn_pct"]
    if projected_pct >= block_at:
        return {
            "status": "block",
            "current_heat_pct": round(current_pct, 2),
            "projected_heat_pct": round(projected_pct, 2),
            "message": (f"PORTFOLIO HEAT: projected total risk {projected_pct:.1f}% "
                        f"exceeds {block_at:.0f}% ceiling. Current: {current_pct:.1f}%. "
                        "Reduce existing positions or skip this entry."),
        }
    if projected_pct >= warn_at:
        return {
            "status": "warn",
            "current_heat_pct": round(current_pct, 2),
            "projected_heat_pct": round(projected_pct, 2),
            "message": (f"PORTFOLIO HEAT: projected total risk {projected_pct:.1f}% "
                        f"approaching {block_at:.0f}% ceiling. Consider half-sizing."),
        }
    return {"status": "ok", "current_heat_pct": round(current_pct, 2),
            "projected_heat_pct": round(projected_pct, 2), "message": ""}


def consecutive_loss_check(recent_closed: list[dict]) -> dict:
    """E-4 hook: count consecutive losses from the most recent closed trade.

    Parameters
    ----------
    recent_closed : list of dicts with keys 'exit_price', 'buy_price',
                    ordered from most recent to oldest (max 10 trades).

    Returns {"status": "block"|"warn"|"ok", "streak": int, "message": str}
    """
    if not V2_FLAGS["consecutive_loss_breaker"]:
        return {"status": "ok", "streak": 0, "message": ""}
    streak = 0
    for trade in recent_closed:
        ep = float(trade.get("exit_price", 0) or 0)
        bp = float(trade.get("buy_price", 0) or 0)
        if ep <= 0 or bp <= 0:
            break  # incomplete data — stop counting
        if ep < bp:
            streak += 1
        else:
            break  # win breaks the streak
    block_at = V2_PARAMS["consecutive_loss_block"]
    warn_at = V2_PARAMS["consecutive_loss_warn"]
    if streak >= block_at:
        return {
            "status": "block", "streak": streak,
            "message": (f"LOSS STREAK: {streak} consecutive losses detected. "
                        f"System paused (threshold: {block_at}). "
                        "Wait for regime improvement or review trade journal."),
        }
    if streak >= warn_at:
        return {
            "status": "warn", "streak": streak,
            "message": (f"LOSS CAUTION: {streak} consecutive losses. "
                        "Consider half-sizing the next entry."),
        }
    return {"status": "ok", "streak": streak, "message": ""}


# ─── Convenience: print active config ────────────────────────────────────────
def describe() -> str:
    """Human-readable summary of which v2 fixes are currently active."""
    active = active_flags()
    if not active:
        return "v2_fixes: ALL OFF (v1 FINAL behavior)"
    lines = ["v2_fixes ACTIVE:"]
    for f in active:
        lines.append(f"  • {f}")
    return "\n".join(lines)


__all__ = [
    "V2_FLAGS", "V2_PARAMS",
    "enable", "disable", "enable_all", "reset", "active_flags", "describe",
    "adjust_catalyst_score", "adjust_record_score", "select_top_n",
    "regime_score_adjust", "get_exit_regime_overrides",
    "portfolio_heat_check", "consecutive_loss_check",
    "_read_regime_score",
]
