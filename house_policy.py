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

# ── Sizing capital (₹) — Jay, 25-Sep-2026: ₹30,00,000. gm_settings `capital` overrides
#    it (the GM settings panel writes there); this is the house figure when the file is
#    missing or unreadable, so sizing never depends on a settings file surviving.
CAPITAL_DEFAULT = 3_000_000.0

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

# ── STOP RULES (AUD-OCT-02, 4-Oct-2026). Before this, the positional floor lived in
#    commander_core, the Chandelier table in risk_common, the pyramid at-SL test in
#    pyramid_logic, and the "noise" warning twice in the Journal (1.5x) and once in
#    ai_risk_manager (2.0x) - so one stop could read green on the banner and red in the
#    sidebar. Every surface reads these. S4 Pine mirrors them as inputs (pos_floor_atrD).
POS_STOP_FLOOR_ATR_D = 4.0     # positional initial stop >= 4x DAILY ATR (2-Oct-2026)
CHANDELIER_MULT = {"POS": 4.5, "WYC": 3.5, "REV": 2.5, "SWG": 1.5}   # by setup family
CHANDELIER_BEAR_ADD = 0.5      # wider in a Bear/Cash tape
CHANDELIER_WINDOW_SWING = 14   # bars for the highest-close anchor + ATR
CHANDELIER_WINDOW_POS = 22
NOISE_ATR_RED = 1.5            # stop within this many ATR of LTP = inside the noise: warn
NOISE_ATR_AMBER = 2.0          # display tint only, never an alert
AT_SL_ATR = 1.5                # pyramid ladder: losing position this close to its stop = EXIT


def noise_band(dist_atr: float | None) -> str:
    """'red' / 'amber' / 'green' for a stop-to-LTP distance in ATR; '' when unknown.
    One rule for the Journal banner, its ledger column and the AI Risk Guard."""
    if dist_atr is None or not math.isfinite(dist_atr):
        return ""
    return "red" if dist_atr < NOISE_ATR_RED else "amber" if dist_atr < NOISE_ATR_AMBER else "green"


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
    settings file has no capital the answer is the HOUSE figure Jay set (CAPITAL_DEFAULT,
    ₹30,00,000) with source "house default" - a number he chose, unlike the old ₹50,00,000
    fallback that sized real orders off a number nobody chose.
    """
    v = _num(_settings().get("capital"), 0.0)
    return (v, "gm_settings") if v > 0 else (CAPITAL_DEFAULT, "house default")


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


# ── EXPOSURE RULE - Option A (Jay, 6-Oct-2026) ────────────────────────────────────────────
# When to trade at all: the one checklist question the system measured (the regime score)
# but never enforced - the book sat 78% deployed at score 1, and four stop-outs cost ₹70K
# in a week before the pause was taken by instinct. Tiers on the composite regime score
# (market_regime.compute_regime, 0-10):
#   0-2 BEAR    no new entries, no pyramid adds, total exposure cap 40%
#   3-5 NEUTRAL half risk, at most 3 new entries a week, cap 70%
#   6+  OPEN    full house rules
# RECOVERY SIGNAL: a follow-through day or a breadth thrust (both regime components)
# unlocks 2 PILOT entries at half risk even in the BEAR tier.
# CIRCUIT BREAKER: 3 losing exits in the last 7 sessions, or realised losses >= 2% of
# capital over them, pause new entries for 5 sessions from the last loss.
# Exits are never touched by this rule. Not backtested - the thresholds are a policy choice;
# logs/board_counts_history.csv and the trade log will show whether they help.
EXPOSURE_TIERS = (  # (min_score, name, new_ok, risk_mult, max_new_week, adds_ok, cap_pct)
    (6, "OPEN", True, 1.0, None, True, None),
    (3, "NEUTRAL", True, 0.5, 3, True, 70.0),
    (0, "BEAR", False, 0.0, 0, False, 40.0),
)
PILOT_ENTRIES = 2
PILOT_RISK_MULT = 0.5
BREAKER_LOSSES = 3
BREAKER_SESSIONS = 7
BREAKER_LOSS_PCT = 2.0
BREAKER_PAUSE_SESSIONS = 5


def _journal_frame():
    import sqlite3
    import pandas as pd
    import journal_path as _jp
    con = sqlite3.connect(_jp.JOURNAL_DB)
    try:
        return pd.read_sql_query(
            "SELECT symbol, status, quantity, buy_price, exit_price, entry_date, exit_date FROM journal", con)
    finally:
        con.close()


def _sessions_back(n: int):
    """The date n NSE sessions before the last completed one (inclusive window start)."""
    import datetime as _dt
    try:
        import nse_calendar as nc
        d = nc.last_completed_session()
        for _ in range(n - 1):
            d = nc.prev_trading_day(d)
        return d
    except Exception:
        return _dt.date.today() - _dt.timedelta(days=int(n * 1.5))


def exposure_status() -> dict:
    """The exposure rule as it stands now. Never raises: on missing data it says so and
    errs to the stricter reading (unknown regime -> BEAR tier)."""
    import datetime as _dt
    import json as _json
    out = {"ok": True, "notes": []}
    try:
        with open(_REGIME_STATE, encoding="utf-8") as f:
            last = (_json.load(f) or {}).get("last") or {}
    except Exception:
        last = {}
    sc = _num(last.get("score"))
    score = None if math.isnan(sc) else int(sc)
    comps = last.get("components") or {}
    signal = bool(comps.get("follow_through") or comps.get("breadth_thrust"))
    sig_name = "follow-through day" if comps.get("follow_through") else "breadth thrust" if comps.get("breadth_thrust") else ""
    eff = score if score is not None else 0
    if score is None:
        out["notes"].append("regime unknown - BEAR tier applied")
    tier = next(t for t in EXPOSURE_TIERS if eff >= t[0])
    _, name, new_ok, rmult, max_week, adds_ok, cap = tier
    cap_rs, _src = sizing_capital()
    deployed = losses_n = 0
    loss_rs = 0.0
    new_week = 0
    pause_until = None
    last_loss = None
    try:
        df = _journal_frame()
        for c in ("quantity", "buy_price", "exit_price"):
            df[c] = __import__("pandas").to_numeric(df[c], errors="coerce")
        op = df[df["status"].astype(str).str.upper() == "OPEN"]
        deployed = float((op["quantity"] * op["buy_price"]).sum())
        _pd = __import__("pandas")
        # dates parsed, not compared as text: a missing date reads "None", which sorts after
        # every ISO date and counted 28 entries "this week" on the first run
        df["_ed"] = _pd.to_datetime(df["entry_date"], errors="coerce")
        df["_xd"] = _pd.to_datetime(df["exit_date"], errors="coerce")
        start7 = _pd.Timestamp(_sessions_back(BREAKER_SESSIONS))
        cl = df[(df["status"].astype(str).str.upper() == "CLOSED") & (df["_xd"] >= start7)].copy()
        cl["pnl"] = (cl["exit_price"] - cl["buy_price"]) * cl["quantity"]
        lost = cl[cl["pnl"] < 0]
        losses_n = int(len(lost))
        loss_rs = float(-lost["pnl"].sum())
        if len(lost):
            last_loss = lost["_xd"].max().date().isoformat()
        today = _dt.date.today()
        monday = _pd.Timestamp(today - _dt.timedelta(days=today.weekday()))
        new_week = int((df["_ed"] >= monday).sum())
    except Exception as e:
        out["notes"].append("journal unreadable (%s)" % str(e)[:60])
    tripped = losses_n >= BREAKER_LOSSES or (cap_rs and loss_rs >= cap_rs * BREAKER_LOSS_PCT / 100.0)
    if tripped and last_loss:
        try:
            import nse_calendar as nc
            d = _dt.date.fromisoformat(last_loss)
            for _ in range(BREAKER_PAUSE_SESSIONS):
                d = d + _dt.timedelta(days=1)
                while not nc.is_trading_day(d):
                    d = d + _dt.timedelta(days=1)
            pause_until = d.isoformat()
        except Exception:
            pause_until = (_dt.date.fromisoformat(last_loss) + _dt.timedelta(days=7)).isoformat()
        if pause_until < _dt.date.today().isoformat():
            pause_until = None
    dep_pct = (deployed / cap_rs * 100.0) if cap_rs else None
    pilot = (not new_ok) and signal
    out.update({
        "score": score, "verdict": last.get("verdict"), "tier": name,
        "new_ok": bool(new_ok or pilot) and not pause_until,
        "pilot": bool(pilot), "pilots_left": max(0, PILOT_ENTRIES - new_week) if pilot else 0,
        "risk_mult": (PILOT_RISK_MULT if pilot else rmult),
        "max_new_week": PILOT_ENTRIES if pilot else max_week, "new_this_week": new_week,
        "adds_ok": bool(adds_ok) and not pause_until, "cap_pct": cap,
        "deployed_pct": None if dep_pct is None else round(dep_pct, 1),
        "signal": sig_name, "losses_7s": losses_n, "loss_rs_7s": round(loss_rs, 0),
        "pause_until": pause_until,
    })
    out["text"] = exposure_text(out)
    return out


def exposure_text(e: dict) -> str:
    """One line for the S4 MKT header, the SUMMARY and the reviewer."""
    if e.get("pause_until"):
        head = "CIRCUIT BREAKER until %s (%d losing exits / ₹%s in 7 sessions) - no new entries · no adds" % (
            e["pause_until"], e.get("losses_7s", 0), "{:,.0f}".format(e.get("loss_rs_7s", 0)))
    elif e.get("tier") == "BEAR" and e.get("pilot"):
        head = "BEAR tier, %s seen - %d PILOT entr%s left at half risk · no adds" % (
            e.get("signal"), e.get("pilots_left", 0), "y" if e.get("pilots_left") == 1 else "ies")
    elif e.get("tier") == "BEAR":
        head = "BEAR tier - no new entries · no adds"
    elif e.get("tier") == "NEUTRAL":
        head = "NEUTRAL tier - half risk, %d of %d new entries left this week" % (
            max(0, (e.get("max_new_week") or 0) - e.get("new_this_week", 0)), e.get("max_new_week") or 0)
    else:
        head = "OPEN tier - full house rules"
    cap = e.get("cap_pct")
    dep = e.get("deployed_pct")
    capt = "" if cap is None else " · exposure cap %g%%%s" % (cap, "" if dep is None else " (deployed %.0f%%%s)" % (dep, " - OVER" if dep > cap else ""))
    unlock = ""
    if e.get("tier") == "BEAR" and not e.get("pilot"):
        unlock = " · unlocks: a follow-through day or breadth thrust (2 pilots) or regime score 3+"
    elif e.get("tier") == "NEUTRAL":
        unlock = " · full rules at score 6+"
    return "EXPOSURE (Option A · score %s): %s%s%s" % (e.get("score"), head, capt, unlock)
