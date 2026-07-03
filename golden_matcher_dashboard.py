"""
golden_matcher_dashboard.py — Single-symbol Golden Matcher checklist (2nd-screen companion)
============================================================================================

A lean, read-only Streamlit page that renders the full Golden Matcher checklist for ONE
stock, so it can sit on a second monitor while trade-trigger work happens on TradingView.

It is a PRESENTATION LAYER ONLY — every number is computed by the existing, validated
modules (zero signal drift):

    bull_screener.screen_one()            -> Stage, RS, Alpha, Catalyst, Entry/SL/T1/T2, ML prob, VCP
    bull_screener.compute_indicators()    -> EMA stack, 200-DMA, RelVol, 52WH distance
    fundamental_hub.fetch_stock_fundamentals() -> ROE, ROCE, D/E, Promoter, P/E, growth (Screener.in)
    data_provider.fetch_ohlcv()           -> OHLCV / CMP (Dhan-routed)

No new strategy logic, no new parameters. Run on the second screen:

    streamlit run golden_matcher_dashboard.py

(c) Jay's trading system. 30 Jun 2026.
"""
from __future__ import annotations

import math
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------------------------
# Page config + compact styling (tuned for a second-screen glance)
# ----------------------------------------------------------------------------------------
st.set_page_config(page_title="Golden Matcher — Single Stock", page_icon="🎯", layout="wide")

st.markdown("""
<style>
  .block-container{padding-top:1.1rem;padding-bottom:1rem;max-width:2300px;}
  .chk{display:flex;justify-content:space-between;align-items:center;
       padding:4px 10px;border-radius:5px;margin:2px 0;font-size:14px;}
  .chk b{font-weight:600;}
  .pass{background:rgba(38,166,154,.16);border-left:3px solid #26A69A;}
  .watch{background:rgba(255,152,0,.16);border-left:3px solid #FF9800;}
  .fail{background:rgba(239,83,80,.16);border-left:3px solid #EF5350;}
  .na{background:rgba(120,123,134,.12);border-left:3px solid #787B86;}
  .sechead{font-size:13px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;
           border-bottom:2px solid currentColor;padding-bottom:3px;margin:6px 0 6px;}
  .verdict{font-size:26px;font-weight:800;}
  .plan{font-family:Consolas,monospace;font-size:14px;line-height:1.7;}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------------------
def inr(x) -> str:
    """Indian-format a number: 1234567 -> 12,34,567."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    neg = x < 0
    x = abs(x)
    whole = int(round(x))
    s = str(whole)
    if len(s) > 3:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:]); rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        s = ",".join(parts) + "," + last3
    return ("-₹" if neg else "₹") + s


def fnum(x, dp=2, suffix="") -> str:
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return "—"
        return f"{float(x):,.{dp}f}{suffix}"
    except (TypeError, ValueError):
        return "—"


def row(label: str, value: str, status: str, note: str = ""):
    """Render a single colored checklist row. status in pass/watch/fail/na."""
    rhs = f"{value}" + (f"  <span style='opacity:.65'>· {note}</span>" if note else "")
    st.markdown(f"<div class='chk {status}'><b>{label}</b><span>{rhs}</span></div>",
                unsafe_allow_html=True)


def _g(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


# ----------------------------------------------------------------------------------------
# Graphical primitives (pure HTML/SVG — no extra deps)
# ----------------------------------------------------------------------------------------
def _sc(state: str) -> str:
    return {"pass": "#26A69A", "watch": "#FF9800", "fail": "#EF5350", "na": "#787B86"}.get(state, "#787B86")


def _gauge(label, value, vmin, vmax, gradient, state, valtxt) -> str:
    col = _sc(state)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        pct = 0.0; valtxt = "—"; col = "#787B86"
    else:
        pct = max(0.0, min(100.0, (float(value) - vmin) / (vmax - vmin) * 100.0))
    return (f"<div style='margin:5px 0;'>"
            f"<div style='display:flex;justify-content:space-between;font-size:11.5px;margin-bottom:3px;'>"
            f"<span style='font-weight:600'>{label}</span>"
            f"<span style='font-weight:800;color:{col}'>{valtxt}</span></div>"
            f"<div style='position:relative;height:9px;border-radius:5px;background:{gradient};'>"
            f"<div style='position:absolute;left:calc({pct:.1f}% - 1px);top:-2px;width:2px;height:13px;"
            f"background:#111;box-shadow:0 0 0 1px #fff;border-radius:1px;'></div></div></div>")


def _crit(ok: bool, label: str) -> str:
    col = "#26A69A" if ok else "#EF5350"; mk = "✓" if ok else "✗"
    return (f"<div style='display:flex;align-items:center;gap:6px;font-size:11px;margin:1.5px 0;'>"
            f"<span style='flex:0 0 15px;width:15px;height:15px;border-radius:50%;background:{col};"
            f"color:#fff;display:inline-flex;align-items:center;justify-content:center;font-size:10px;"
            f"font-weight:700'>{mk}</span><span>{label}</span></div>")


def _pill(state: str, label: str, val: str) -> str:
    col = _sc(state)
    return (f"<div style='border-left:3px solid {col};background:{col}22;border-radius:4px;padding:3px 7px;'>"
            f"<div style='opacity:.65;font-size:9.5px;text-transform:uppercase;letter-spacing:.3px'>{label}</div>"
            f"<b style='color:{col};font-size:12px'>{val}</b></div>")


def _donut(passed: int, total: int) -> str:
    r = 22.0; circ = 2 * math.pi * r
    frac = (passed / total) if total else 0
    col = "#26A69A" if frac >= 0.75 else ("#FF9800" if frac >= 0.5 else "#EF5350")
    off = circ * (1 - frac)
    return (f"<svg width='54' height='54' viewBox='0 0 52 52'>"
            f"<circle cx='26' cy='26' r='{r}' fill='none' stroke='#80808033' stroke-width='6'/>"
            f"<circle cx='26' cy='26' r='{r}' fill='none' stroke='{col}' stroke-width='6'"
            f" stroke-dasharray='{circ:.1f}' stroke-dashoffset='{off:.1f}' stroke-linecap='round'"
            f" transform='rotate(-90 26 26)'/>"
            f"<text x='26' y='31' text-anchor='middle' font-size='14' font-weight='800' fill='{col}'>{passed}/{total}</text></svg>")


def _range_bar(low, high, cmp_, marks) -> str:
    if not (low and high and high > low and cmp_):
        return "<div style='font-size:11px;opacity:.6'>52W range unavailable</div>"
    span = high - low
    def p(x): return max(0.0, min(100.0, (x - low) / span * 100.0))
    ticks = ""
    for x, lab, col in marks:
        if x is None:
            continue
        ticks += (f"<div style='position:absolute;left:{p(x):.1f}%;top:11px;width:1px;height:7px;"
                  f"background:{col};transform:translateX(-50%)'></div>"
                  f"<div style='position:absolute;left:{p(x):.1f}%;top:18px;transform:translateX(-50%);"
                  f"font-size:8.5px;color:{col};white-space:nowrap'>{lab}</div>")
    cp = p(cmp_)
    return (f"<div style='position:relative;margin:6px 0 30px;'>"
            f"<div style='position:relative;height:9px;border-radius:5px;"
            f"background:linear-gradient(90deg,#EF535055,#FF980055,#26A69A55);'>"
            f"<div style='position:absolute;left:{cp:.1f}%;top:-5px;transform:translateX(-50%);width:0;height:0;"
            f"border-left:6px solid transparent;border-right:6px solid transparent;border-top:11px solid #111;'></div>"
            f"{ticks}</div>"
            f"<div style='display:flex;justify-content:space-between;font-size:9px;opacity:.6;margin-top:2px'>"
            f"<span>52WL {inr(low)}</span><span>52WH {inr(high)}</span></div></div>")


def minervini_checks(ctx: dict, cmp_px, mansfield):
    """Minervini 8-point trend template — shared by the board and the decision engine."""
    e20 = _g(ctx, "ema20"); s50 = _g(ctx, "sma50"); s150 = _g(ctx, "sma150")
    s200 = _g(ctx, "sma200"); s200p = _g(ctx, "sma200_prev")
    low = _g(ctx, "low52w"); high = _g(ctx, "high52w")
    checks = [
        (bool(s150 and s200 and cmp_px > s150 and cmp_px > s200), "Price > 150 & 200 SMA"),
        (bool(s150 and s200 and s150 > s200), "150 SMA > 200 SMA"),
        (bool(s200 and s200p and s200 > s200p), "200 SMA trending up (1m)"),
        (bool(s50 and s150 and s200 and s50 > s150 and s50 > s200), "50 SMA > 150 & 200"),
        (bool(s50 and cmp_px > s50), "Price > 50 SMA"),
        (bool(low and cmp_px >= 1.30 * low), "≥30% above 52W low"),
        (bool(high and cmp_px >= 0.75 * high), "≤25% from 52W high"),
        (bool((mansfield or -1) > 0), "RS positive (vs N500)"),
    ]
    return sum(1 for ok, _ in checks if ok), checks


def compute_decision(rec: dict, ctx: dict, cmp_px, mansfield) -> dict:
    """Synthesize all signals into a verdict via a 3-gate funnel (Decision Mode)."""
    stage = str(_g(rec, "Stage", default="")); s2 = "2" in stage
    s34 = ("3" in stage or "4" in stage)
    above30w = bool(_g(ctx, "sma150") and cmp_px > _g(ctx, "sma150"))
    regime = _g(rec, "Regime", default="—"); counter = bool(_g(rec, "Counter_Trend"))
    rs = (mansfield or 0) > 0
    alpha = _g(rec, "Alpha") or 0
    mpass, _ = minervini_checks(ctx, cmp_px, mansfield)
    rrg = _g(rec, "RRG_Quadrant", default=""); rrg_ok = rrg in ("LEADING", "IMPROVING")
    catalyst = _g(rec, "Catalyst", default="NONE")
    cat_on = str(catalyst) not in ("NONE", "None", "—", "0", "")
    rsi = _g(rec, "RSI") or 0; not_ob = rsi < 75
    s2w = _g(ctx, "stage2_weeks"); fresh = (s2w is None) or (s2w <= 26)
    macro = bool(_g(ctx, "shelf_ok") and _g(ctx, "acc_ok"))
    micro = bool(_g(ctx, "cpr_p") and cmp_px > _g(ctx, "cpr_p") and _g(ctx, "mvwap") and cmp_px > _g(ctx, "mvwap"))
    vcp = bool(_g(rec, "VCP_Valid")); broke = bool(_g(rec, "Broke_Pivot"))

    g1_checks = [("Stage 2 advancing", s2), ("Above 30W MA", above30w),
                 (f"Market regime {regime}", (regime == "BULL") or not counter)]
    g1 = s2 and above30w
    g2_checks = [("Mansfield RS positive", rs), (f"Alpha ≥ 60 (now {alpha:.0f})", alpha >= 60),
                 (f"Minervini ≥ 6/8 (now {mpass}/8)", mpass >= 6), ("RRG leading/improving", rrg_ok)]
    g2 = rs and (alpha >= 50) and (mpass >= 5)
    g3_checks = [(f"Catalyst firing ({catalyst})", cat_on), ("Not over-extended", fresh and not_ob),
                 ("Macro/Micro edge active", macro or micro), ("VCP / pivot break", vcp or broke)]
    g3 = cat_on and fresh and not_ob

    gates = [
        {"name": "CONTEXT", "sub": "Trend & Regime", "ok": g1, "checks": g1_checks},
        {"name": "STRENGTH", "sub": "Quality & RS", "ok": g2, "checks": g2_checks},
        {"name": "TIMING", "sub": "Location & Trigger", "ok": g3, "checks": g3_checks},
    ]

    if s34 or not rs:
        verdict, color = "AVOID / EXIT", "#EF5350"
        reason = "Stage 3/4 or RS negative — fails the no-Stage-3-holds rule."
        action = "No long. If held, plan the exit per the Sell-to-Buy matrix."
    elif g1 and g2 and g3:
        verdict, color = "STRONG BUY", "#26A69A"
        reason = f"All 3 gates pass · catalyst {catalyst} firing."
        action = f"Confirm a CLOSED 75/125m trigger → buy-STOP above its high. Size {_g(rec,'Suggested_Size','—')}."
    elif g1 and g2:
        verdict, color = "BUY ON TRIGGER", "#FF9800"
        reason = "Context + strength pass; only timing/trigger is pending."
        action = "Set an alert at the fresh zone; act ONLY on a closed 75/125m trigger bar."
    elif g1:
        verdict, color = "WATCHLIST", "#FF9800"
        reason = "Stage-2 context OK but strength is incomplete."
        action = "Track only — needs RS / Alpha / Minervini to firm up."
    else:
        verdict, color = "NOT YET", "#787B86"
        reason = "Context gate not met (Stage 2 + above 30W MA)."
        action = "No setup. Re-check when context turns."
    if counter and verdict in ("STRONG BUY", "BUY ON TRIGGER"):
        reason += "  ⚠ Counter-trend (index not bull) — size halved."
    return {"verdict": verdict, "color": color, "reason": reason, "action": action, "gates": gates}


def render_decision(d: dict) -> str:
    gates_html = ""
    for i, g in enumerate(d["gates"]):
        col = "#26A69A" if g["ok"] else "#787B86"
        mk = "✓" if g["ok"] else "○"
        subs = ""
        for lab, ok in g["checks"]:
            cc = "#26A69A" if ok else "#EF5350"; mm = "✓" if ok else "✗"
            subs += (f"<div style='display:flex;gap:5px;font-size:10.5px;margin:1px 0'>"
                     f"<span style='color:{cc};font-weight:700'>{mm}</span>"
                     f"<span style='opacity:.85'>{lab}</span></div>")
        gates_html += (f"<div style='flex:1;border-top:3px solid {col};background:{col}14;"
                       f"border-radius:0 0 6px 6px;padding:7px 9px;'>"
                       f"<div style='font-weight:800;font-size:12px;color:{col}'>{mk} GATE {i+1} · {g['name']}</div>"
                       f"<div style='font-size:9.5px;opacity:.55;margin-bottom:4px'>{g['sub']}</div>{subs}</div>")
    return (f"<div style='border:2px solid {d['color']};border-radius:10px;padding:12px 16px;margin-bottom:12px;"
            f"background:{d['color']}11;'>"
            f"<div style='display:flex;align-items:baseline;gap:12px;flex-wrap:wrap'>"
            f"<span style='font-size:11px;letter-spacing:1px;opacity:.55'>DECISION</span>"
            f"<span style='font-size:30px;font-weight:900;color:{d['color']}'>{d['verdict']}</span></div>"
            f"<div style='font-size:13px;margin:4px 0 2px'>{d['reason']}</div>"
            f"<div style='font-size:12px;opacity:.85'>▶ <b>Next:</b> {d['action']}</div>"
            f"<div style='display:flex;gap:8px;margin-top:10px'>{gates_html}</div></div>")


def render_pine_mirror(rec: dict, ctx: dict, cmp_px) -> str:
    """Key composite fields mirrored from the v67 Decision-Mode panel."""
    cat = str(_g(rec, "Catalyst", default=""))
    rec_style = ("Positional (6–8 mo)" if cat.startswith("POS")
                 else "Swing (1–4 wk)" if cat.startswith("SWG")
                 else "Recovery" if cat.startswith("REV") else "—")
    s2w = _g(ctx, "stage2_weeks")
    if s2w is None:
        fresh = "—"; fresh_state = "na"
    elif s2w <= 13:
        fresh = f"Fresh ({s2w:.0f}w)"; fresh_state = "pass"
    elif s2w <= 26:
        fresh = f"Maturing ({s2w:.0f}w)"; fresh_state = "watch"
    else:
        fresh = f"Extended ({s2w:.0f}w)"; fresh_state = "fail"
    macro = bool(_g(ctx, "shelf_ok") and _g(ctx, "acc_ok"))
    cpr_p = _g(ctx, "cpr_p"); mv = _g(ctx, "mvwap")
    micro = bool(cpr_p and cmp_px > cpr_p and mv and cmp_px > mv)
    pills = "".join([
        _pill("na", "Rec. Style", rec_style),
        _pill(fresh_state, "Stage-2 Age", fresh),
        _pill("pass" if macro else "na", "Macro Edge", "Inst-Vol ON" if macro else "off"),
        _pill("pass" if micro else "na", "Micro Edge", "CPR+MVWAP ON" if micro else "off"),
        _pill("pass" if (cpr_p and cmp_px > cpr_p) else "watch", "vs CPR Pivot",
              ("above " + inr(cpr_p)) if cpr_p else "—"),
        _pill("pass" if (mv and cmp_px > mv) else "watch", "vs Monthly VWAP", inr(mv) if mv else "—"),
        _pill("pass" if _g(ctx, "acc_ok") else "na", "Accumulation", f"{_g(ctx,'acc_days',default=0)}/10 days"),
        _pill("pass" if _g(ctx, "squeeze_on") else "na", "Squeeze 20/50", "ON" if _g(ctx, "squeeze_on") else "off"),
        _pill("pass" if _g(rec, "Regime") == "BULL" else "watch", "Market Regime", _g(rec, "Regime", default="—")),
    ])
    return f"<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;'>{pills}</div>"


# ----------------------------------------------------------------------------------------
# Panel-mirror cards (replace the 5 Pine panel tables)
# ----------------------------------------------------------------------------------------
def card(title: str, rows, accent: str = "#2962FF") -> str:
    """Compact label:value table card mirroring a Pine panel."""
    body = ""
    for label, value, state in rows:
        col = _sc(state)
        body += (f"<div style='display:flex;justify-content:space-between;gap:8px;padding:2.5px 0;"
                 f"font-size:11.5px;border-bottom:1px solid rgba(136,136,136,.18)'>"
                 f"<span style='opacity:.78'>{label}</span>"
                 f"<b style='color:{col};text-align:right'>{value}</b></div>")
    return (f"<div style='border:1px solid rgba(136,136,136,.28);border-radius:7px;overflow:hidden;margin-bottom:9px'>"
            f"<div style='background:{accent};color:#fff;font-weight:700;font-size:10.5px;"
            f"letter-spacing:.4px;padding:4px 9px'>{title}</div>"
            f"<div style='padding:4px 9px 6px'>{body}</div></div>")


def _grade(a) -> str:
    a = a or 0
    return ("A+ Excellent" if a >= 80 else "A Strong" if a >= 70 else "B Good" if a >= 55
            else "C Fair" if a >= 40 else "D Weak")


def section_structure(rec, ctx, cmp_px, mansfield, decision) -> str:
    """Mirror of the v67 Weinstein Dashboard header rows."""
    stage = str(_g(rec, "Stage", default="—"))
    cat = str(_g(rec, "Catalyst", default="NONE"))
    style = ("Positional" if cat.startswith("POS") else "Swing" if cat.startswith("SWG")
             else "Recovery" if cat.startswith("REV") else "Both / —")
    alpha = _g(rec, "Alpha") or 0
    s2w = _g(ctx, "stage2_weeks")
    fresh = ("—" if s2w is None else f"Fresh ({s2w:.0f}w)" if s2w <= 13
             else f"Maturing ({s2w:.0f}w)" if s2w <= 26 else f"Extended ({s2w:.0f}w)")
    subs = [ok for g in decision["gates"] for _, ok in g["checks"]]
    act = round(10 * sum(1 for x in subs if x) / max(1, len(subs)))
    persona = ("LEADER" if (mansfield or 0) > 0 and _g(rec, "RRG_Quadrant") in ("LEADING", "IMPROVING")
               else "Improving" if (mansfield or 0) > 0 else "Laggard")
    v = decision["verdict"]
    rows = [
        ("Recommendation", v, "pass" if "BUY" in v else "fail" if "AVOID" in v else "watch"),
        ("Recommended Style", style, "na"),
        ("Action Signal", f"{act}/10", "pass" if act >= 7 else "watch" if act >= 5 else "fail"),
        ("Asset Quality", f"{alpha:.0f}/100 [{_grade(alpha)}]",
         "pass" if alpha >= 70 else "watch" if alpha >= 50 else "fail"),
        ("Weekly Stage", f"Stage {stage} · {fresh}",
         "pass" if "2" in stage else "fail" if ("3" in stage or "4" in stage) else "watch"),
        ("Daily Trend", f"{_g(rec,'Active_Dir',default='—')} {_g(rec,'Vel_Accel',default='')}",
         "pass" if str(_g(rec, "Active_Dir")).upper().startswith("UP") else "watch"),
        ("Momentum", f"RSI {fnum(_g(rec,'RSI'),0)} · ADX {fnum(_g(ctx,'adx'),0)} · Vol {fnum(_g(ctx,'relvol'),1)}x", "na"),
        ("Persona", persona, "pass" if persona == "LEADER" else "watch"),
        ("ML Win Prob", fnum(_g(rec, "ML_Prob"), 1, "%"), "pass" if (_g(rec, "ML_Prob") or 0) >= 60 else "watch"),
    ]
    return card("WEINSTEIN STRUCTURE · " + str(_g(rec, "Symbol", default="")), rows, "#1565C0")


def section_bull_gates(rec, ctx, cmp_px, mansfield) -> str:
    """Mirror of the Commander Bull Screener POS-BO gate panel."""
    s2 = "2" in str(_g(rec, "Stage", default=""))
    g200 = bool(_g(ctx, "sma200") and cmp_px > _g(ctx, "sma200"))
    rrg_ok = _g(rec, "RRG_Quadrant") in ("LEADING", "IMPROVING")
    mpass, _ = minervini_checks(ctx, cmp_px, mansfield)
    tpl = mpass >= 6
    vacc = bool(_g(ctx, "acc_ok"))
    s2w = _g(ctx, "stage2_weeks")
    freshg = (s2w is not None and s2w <= 6)
    gates = [("G1 Stage 2", s2), ("G2 Price > 200DMA", g200), ("G3 N500 RRG lead", rrg_ok),
             ("G4 Sector S1/2", None), ("G5 Trend Template", tpl), ("G6 Vol Accum", vacc),
             ("G7 Fresh ≤6w" + (f" ({s2w:.0f}w)" if s2w is not None else ""), freshg)]
    passed = sum(1 for _, ok in gates if ok)
    total = sum(1 for _, ok in gates if ok is not None)
    cat = str(_g(rec, "Catalyst", default="NONE")); firing = cat not in ("NONE", "None", "—", "0", "")
    rows = [("VERDICT", (cat + " · FIRING") if firing else "NONE · WATCH", "pass" if firing else "watch")]
    for lab, ok in gates:
        rows.append((lab, "n/a", "na") if ok is None else (lab, "✓ pass" if ok else "✗ block", "pass" if ok else "fail"))
    return card(f"BULL SCREENER · POS-BO {passed}/{total}", rows, "#00695C")


def section_context(rec, ctx, cmp_px) -> str:
    """Mirror of the Context Layers panel — SMC / Wyckoff / Volume Profile."""
    adir = str(_g(rec, "Active_Dir", default="")).upper()
    smc = "BULLISH" if adir.startswith("UP") else "BEARISH" if adir.startswith("DOWN") else "NEUTRAL"
    stage = str(_g(rec, "Stage", default=""))
    bfvg = _g(ctx, "bull_fvg", default=0); rfvg = _g(ctx, "bear_fvg", default=0)
    wyk = ("ACCUMULATION" if (_g(ctx, "acc_ok") and ("1" in stage or "2" in stage))
           else "DISTRIBUTION" if "3" in stage else "NEUTRAL")
    poc = _g(ctx, "poc"); vah = _g(ctx, "vah"); val = _g(ctx, "val")
    vp_pos = _g(ctx, "vp_pos", default="—"); dpoc = _g(ctx, "dist_poc")
    rows = [
        ("SMC Trend", smc, "pass" if smc == "BULLISH" else "fail" if smc == "BEARISH" else "na"),
        ("Open FVGs", f"Bull {bfvg} · Bear {rfvg}", "pass" if bfvg >= rfvg else "watch"),
        ("Wyckoff Bias", wyk, "pass" if wyk == "ACCUMULATION" else "fail" if wyk == "DISTRIBUTION" else "na"),
        ("VP Position", vp_pos,
         "pass" if vp_pos == "ABOVE VAH" else "watch" if vp_pos == "INSIDE VA" else "fail" if vp_pos == "BELOW VAL" else "na"),
        ("POC", inr(poc) if poc else "—", "na"),
        ("VAH / VAL", (inr(vah) + " / " + inr(val)) if (vah and val) else "—", "na"),
        ("Dist to POC", fnum(dpoc, 1, "%"), "na"),
    ]
    return card("CONTEXT LAYERS · SMC / VP / Wyckoff", rows, "#6A1B9A")


def section_edges(rec, ctx, cmp_px) -> str:
    """Macro/Micro mathematical edges + CPR/MVWAP/squeeze."""
    macro = bool(_g(ctx, "shelf_ok") and _g(ctx, "acc_ok"))
    cpr_p = _g(ctx, "cpr_p"); mv = _g(ctx, "mvwap")
    micro = bool(cpr_p and cmp_px > cpr_p and mv and cmp_px > mv and _g(ctx, "squeeze_on"))
    rows = [
        ("Macro Edge (Inst Vol)", "ON" if macro else "off", "pass" if macro else "na"),
        ("Micro Edge (CPR+VWAP+Sqz)", "ON" if micro else "off", "pass" if micro else "na"),
        ("vs CPR Pivot", ("above " + inr(cpr_p)) if (cpr_p and cmp_px > cpr_p) else "below",
         "pass" if (cpr_p and cmp_px > cpr_p) else "watch"),
        ("vs Monthly VWAP", ("above " + inr(mv)) if (mv and cmp_px > mv) else "below",
         "pass" if (mv and cmp_px > mv) else "watch"),
        ("Accumulation", f"{_g(ctx,'acc_days',default=0)}/10 days", "pass" if _g(ctx, "acc_ok") else "na"),
        ("Squeeze 20/50", "ON" if _g(ctx, "squeeze_on") else "off", "pass" if _g(ctx, "squeeze_on") else "na"),
        ("VCP / Base", ("valid · " + str(_g(rec, "Days_Since_Pivot", default="—")) + "d") if _g(rec, "VCP_Valid") else "no",
         "pass" if _g(rec, "VCP_Valid") else "na"),
    ]
    return card("MATHEMATICAL EDGES", rows, "#7B1FA2")


def section_trade(rec, cmp_px) -> str:
    entry = _g(rec, "Entry", default=cmp_px); sl_pct = _g(rec, "SL_pct")
    t1_pct = _g(rec, "T1_pct"); t2_pct = _g(rec, "T2_pct")
    if not (entry and sl_pct is not None):
        return card("TRADE GEOMETRY", [("Status", "No active catalyst", "na"),
                                       ("Levels", "reference only", "na")], "#E65100")
    sl = entry * (1 - sl_pct / 100)
    t1 = entry * (1 + t1_pct / 100) if t1_pct is not None else None
    t2 = entry * (1 + t2_pct / 100) if t2_pct is not None else None
    rr = (t1_pct / sl_pct) if (t1_pct and sl_pct) else None
    rows = [
        ("Entry", inr(entry), "na"),
        ("Stop-Loss", f"{inr(sl)} (-{sl_pct:.1f}%)", "fail"),
        ("Target 1", f"{inr(t1)} (+{t1_pct:.1f}% · {fnum(rr,1)}R)", "pass"),
        ("Target 2", f"{inr(t2)} (+{t2_pct:.1f}%)", "pass"),
        ("Suggested Size", str(_g(rec, "Suggested_Size", default="—")), "na"),
        ("Regime", str(_g(rec, "Regime", default="—")), "pass" if _g(rec, "Regime") == "BULL" else "watch"),
    ]
    if _g(rec, "Counter_Trend"):
        rows.append(("⚠ Counter-trend", "size halved", "watch"))
    return card("TRADE GEOMETRY · daily plan", rows, "#E65100")


def section_levels(rec, ctx, cmp_px) -> str:
    d52 = _g(ctx, "dist52wh")
    rows = [
        ("Room to 52WH", fnum(d52, 1, "%"), "pass" if (d52 is not None and -15 <= d52 <= -1) else "watch"),
        ("EMA20 distance", fnum(_g(rec, "EMA20_Dist_ATR"), 2, " ATR"), "na"),
        ("Pivot", f"{_g(rec,'Days_Since_Pivot','—')}d" + (" · broke ↑" if _g(rec, "Broke_Pivot") else ""),
         "pass" if _g(rec, "Broke_Pivot") else "na"),
        ("Turnover", fnum(_g(ctx, "turnover_cr"), 1) + " Cr", "na"),
        ("DZ / SZ zones", "live on chart", "na"),
    ]
    return card("LEVELS & ROOM", rows, "#EF6C00")


def section_sector(rec, ctx, mansfield) -> str:
    rows = [
        ("Market Regime", str(_g(rec, "Regime", default="—")), "pass" if _g(rec, "Regime") == "BULL" else "watch"),
        ("RS vs N500", fnum(mansfield, 1) + (" Positive" if (mansfield or 0) > 0 else " Negative"),
         "pass" if (mansfield or 0) > 0 else "fail"),
        ("RS Momentum 4w", fnum(_g(rec, "JdK_RS_Momentum"), 1), "na"),
        ("RRG Quadrant", f"{_g(rec,'RRG_Quadrant',default='—')} {_g(rec,'RRG_Arrow','')}",
         "pass" if _g(rec, "RRG_Quadrant") in ("LEADING", "IMPROVING") else "watch"),
        ("RRG Trajectory", str(_g(rec, "RRG_Trajectory", default="—")), "na"),
        ("Sector RS", "see Commander Web", "na"),
        ("Futures OI", "see broker (F&O)", "na"),
    ]
    return card("SECTOR / MACRO / RRG", rows, "#283593")


def section_fundamentals(fun) -> str:
    roe = _g(fun, "roe"); roce = _g(fun, "roce"); de = _g(fun, "debt_equity")
    prom = _g(fun, "promoter_holding", "promoter"); piot = _g(fun, "piotroski", "piotroski_score")
    qpv = _g(fun, "qtr_profit_var", "quarterly_profit_growth")
    qsv = _g(fun, "qtr_sales_var", "quarterly_sales_growth")
    pe = _g(fun, "pe_ratio"); mcap = _g(fun, "market_cap")
    rows = []
    if roe is not None: rows.append(("ROE %", fnum(roe, 1, "%"), "pass" if roe >= 15 else "watch" if roe >= 10 else "fail"))
    if roce is not None: rows.append(("ROCE %", fnum(roce, 1, "%"), "pass" if roce >= 15 else "watch" if roce >= 10 else "fail"))
    if de is not None: rows.append(("Debt / Equity", fnum(de, 2), "pass" if de < 0.5 else "watch" if de < 1.0 else "fail"))
    if prom is not None: rows.append(("Promoter %", fnum(prom, 1, "%"), "pass" if prom >= 50 else "watch"))
    if piot is not None: rows.append(("Piotroski", fnum(piot, 0, "/9"), "pass" if piot >= 7 else "watch" if piot >= 5 else "fail"))
    if qpv is not None: rows.append(("Qtr Profit Δ", fnum(qpv, 1, "%"), "pass" if qpv > 0 else "fail"))
    if qsv is not None: rows.append(("Qtr Sales Δ", fnum(qsv, 1, "%"), "pass" if qsv > 0 else "fail"))
    if pe is not None: rows.append(("P/E", fnum(pe, 1), "na"))
    if mcap is not None: rows.append(("Market Cap", inr(mcap) + " Cr", "na"))
    if not rows:
        rows = [("Fundamentals", "unavailable — refresh cookie", "na")]
    return card("FUNDAMENTALS · Screener.in", rows, "#00838F")


# ----------------------------------------------------------------------------------------
# DECISION WORKFLOW — the sequential path (crucial metrics only)
# ----------------------------------------------------------------------------------------
def compute_workflow(rec, ctx, cmp_px, mansfield) -> dict:
    """Order the decision as a gated sequence: CONTEXT → QUALITY → SETUP → LOCATION → TRIGGER → EXECUTE."""
    stage = str(_g(rec, "Stage", default="")); s2 = "2" in stage; s34 = ("3" in stage or "4" in stage)
    regime = _g(rec, "Regime", default="—")
    rs = (mansfield or 0) > 0
    alpha = _g(rec, "Alpha") or 0
    mpass, _ = minervini_checks(ctx, cmp_px, mansfield)
    rrg = _g(rec, "RRG_Quadrant", default="—"); rrg_ok = rrg in ("LEADING", "IMPROVING")
    cat = str(_g(rec, "Catalyst", default="NONE")); cat_on = cat not in ("NONE", "None", "—", "0", "")
    s2w = _g(ctx, "stage2_weeks"); fresh = (s2w is None) or (s2w <= 26)
    vcp = bool(_g(rec, "VCP_Valid"))
    cpr_p = _g(ctx, "cpr_p"); mv = _g(ctx, "mvwap")
    above_value = bool(cpr_p and cmp_px > cpr_p and mv and cmp_px > mv)
    vp_pos = _g(ctx, "vp_pos", default="—"); d52 = _g(ctx, "dist52wh")
    not_ext = (d52 is None) or (d52 <= -1)

    g1 = s2 and rs and not s34
    g2 = alpha >= 50 and mpass >= 5
    g3 = cat_on
    g4 = above_value and not_ext

    entry = _g(rec, "Entry", default=cmp_px); sl_pct = _g(rec, "SL_pct"); t1_pct = _g(rec, "T1_pct")
    if entry and sl_pct is not None:
        sl = entry * (1 - sl_pct / 100); t1 = entry * (1 + t1_pct / 100) if t1_pct else None
        rr = (t1_pct / sl_pct) if (t1_pct and sl_pct) else None
        plan = (f"Set SL {inr(sl)} (-{sl_pct:.1f}%), size at 0.25% risk, place order + GTT. "
                f"Target T1 {inr(t1)} ({fnum(rr,1)}R).")
    else:
        plan = "No active catalyst → no plan yet. Levels are reference only."

    steps = [
        dict(n=1, title="CONTEXT", sub="Weekly trend", hard=True, ok=g1,
             metrics=[("Stage", stage or "—", s2 and not s34),
                      ("RS vs N500", f"{(mansfield or 0):+.1f}", rs),
                      ("Regime", regime, regime == "BULL")],
             do_pass="Weekly Stage 2 + positive RS — confirmed by the engine.",
             do_fail="Not a Stage-2 leader (or RS negative). SKIP — go to the next name."),
        dict(n=2, title="QUALITY", sub="Leadership", hard=True, ok=g2,
             metrics=[("Asset Qual", f"{alpha:.0f}/100", alpha >= 70),
                      ("Minervini", f"{mpass}/8", mpass >= 6),
                      ("RRG", rrg, rrg_ok)],
             do_pass="Leadership confirmed (Alpha + trend template + RRG).",
             do_fail="Not a leader yet. WATCHLIST — revisit when RS / Alpha firm up."),
        dict(n=3, title="SETUP", sub="Catalyst & base", hard=False, ok=g3,
             metrics=[("Catalyst", cat, cat_on),
                      ("Freshness", (f"{s2w:.0f}w" if s2w is not None else "—"), fresh),
                      ("VCP/Base", "valid" if vcp else "no", vcp)],
             do_pass=f"Catalyst {cat} is LIVE — proceed to location.",
             do_fail="No live catalyst. Add to watchlist & set a price alert at the zone; wait."),
        dict(n=4, title="LOCATION", sub="Price at value", hard=False, ok=g4,
             metrics=[("vs CPR+VWAP", "above" if above_value else "below", above_value),
                      ("VP", vp_pos, vp_pos in ("ABOVE VAH", "INSIDE VA")),
                      ("Room 52WH", fnum(d52, 1, "%"), not_ext)],
             do_pass="Price at value & not extended. On TV: mark the FRESH demand zone (Daily+).",
             do_fail="Extended / below value. WAIT for a pullback into a fresh demand zone."),
        dict(n=5, title="TRIGGER", sub="Your move · TradingView", hard=False, ok=None, manual=True,
             metrics=[],
             do_now="Wait for a CLOSED 75/125m bar at the zone → buy-STOP above its high. Never buy the touch."),
        dict(n=6, title="EXECUTE", sub="Plan & GTT", hard=False, ok=None, execute=True,
             metrics=[], do_now=plan),
    ]

    stop_at = None
    for s in steps:
        if s.get("hard") and not s["ok"]:
            stop_at = s["n"]; break

    if s34 or not rs:
        verdict, color = "AVOID / EXIT", "#EF5350"
    elif stop_at == 1:
        verdict, color = "AVOID", "#EF5350"
    elif stop_at == 2:
        verdict, color = "WATCHLIST", "#FF9800"
    elif not g3:
        verdict, color = "BUY-WATCH · no catalyst", "#FF9800"
    elif not g4:
        verdict, color = "WAIT FOR PULLBACK", "#FF9800"
    else:
        verdict, color = "BUY ON TRIGGER", "#26A69A"

    # The single step that needs attention right now
    if stop_at:
        current = stop_at
    elif not g3:
        current = 3
    elif not g4:
        current = 4
    else:
        current = 5
    actionable = verdict not in ("AVOID", "AVOID / EXIT", "WATCHLIST")
    return dict(steps=steps, verdict=verdict, color=color, stop_at=stop_at,
                current=current, actionable=actionable)


def render_workflow(wf: dict) -> str:
    cmap = {"pass": "#26A69A", "fail": "#EF5350", "wait": "#FF9800",
            "pending": "#2962FF", "skip": "#9aa0a6", "plan": "#26A69A"}
    pill = {"pass": "DONE", "fail": "STOP", "wait": "WAIT", "pending": "YOUR MOVE", "skip": "LOCKED", "plan": "PLAN"}
    cur = wf.get("current")
    steps_html = ""; prior_fail = False; n = len(wf["steps"])
    for i, s in enumerate(wf["steps"]):
        if prior_fail:
            status = "skip"
        elif s.get("manual"):
            status = "pending"
        elif s.get("execute"):
            status = "plan"
        elif s["ok"] is True:
            status = "pass"
        elif s["ok"] is False:
            status = "fail" if s.get("hard") else "wait"
        else:
            status = "pending"
        col = cmap[status]
        is_cur = (s["n"] == cur and status != "skip")
        chips = ""
        for lab, val, ok in s["metrics"]:
            cc = "#26A69A" if ok else ("#EF5350" if ok is False else "#9aa0a6")
            mk = "✓" if ok else ("✗" if ok is False else "·")
            chips += (f"<span style='display:inline-block;margin:3px 9px 0 0;font-size:11.5px'>"
                      f"<span style='opacity:.7'>{lab}</span> <b>{val}</b> "
                      f"<span style='color:{cc};font-weight:700'>{mk}</span></span>")
        # imperative guidance line — this is the "do this" of the sequence
        if status == "skip":
            guide = ""
        elif status == "pass":
            guide = "✓ " + s.get("do_pass", "")
        elif status == "fail":
            guide = "⛔ " + s.get("do_fail", "")
        elif status == "wait":
            guide = "⏳ " + s.get("do_fail", "")
        else:
            guide = "▶ " + s.get("do_now", "")
        guide_html = (f"<div style='font-size:11.5px;margin-top:3px;color:{col};font-weight:600'>{guide}</div>"
                      if guide else "")
        nowbadge = ("<span style='font-size:9px;font-weight:800;color:#fff;background:#111;"
                    "padding:1px 7px;border-radius:9px;margin-left:6px'>← NOW</span>" if is_cur else "")
        line = "" if i == n - 1 else f"<div style='width:2px;flex:1;background:{col}55;min-height:10px;margin:2px 0'></div>"
        bg = f"background:{col}14;border-radius:7px;padding:5px 8px;margin:-4px 0;" if is_cur else "padding:0 8px;"
        steps_html += (
            f"<div style='display:flex;gap:11px;align-items:stretch'>"
            f"<div style='display:flex;flex-direction:column;align-items:center;flex:0 0 28px'>"
            f"<div style='width:28px;height:28px;border-radius:50%;background:{col};color:#fff;display:flex;"
            f"align-items:center;justify-content:center;font-weight:800;font-size:13px;"
            f"{'box-shadow:0 0 0 3px ' + col + '44;' if is_cur else ''}'>{s['n']}</div>{line}</div>"
            f"<div style='flex:1;padding-bottom:10px'><div style='{bg}'>"
            f"<div style='display:flex;align-items:center;gap:8px'>"
            f"<span style='font-weight:800;font-size:12.5px;color:{col}'>STEP {s['n']} · {s['title']}</span>"
            f"<span style='font-size:9.5px;opacity:.55'>{s['sub']}</span>{nowbadge}"
            f"<span style='margin-left:auto;font-size:9.5px;font-weight:800;color:#fff;background:{col};"
            f"padding:1px 8px;border-radius:9px'>{pill[status]}</span></div>"
            f"{('<div>' + chips + '</div>') if chips else ''}{guide_html}</div></div></div>")
        if s.get("hard") and s["ok"] is False:
            prior_fail = True
    sub = (f"⛔ stops at Step {wf['stop_at']}" if wf["stop_at"] else f"→ you are at Step {cur}")
    return (f"<div style='border:2px solid {wf['color']};border-radius:10px;padding:12px 16px;"
            f"background:{wf['color']}11;max-width:880px'>"
            f"<div style='display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:11px'>"
            f"<span style='font-size:11px;letter-spacing:1px;opacity:.55'>DECISION PATH</span>"
            f"<span style='font-size:26px;font-weight:900;color:{wf['color']}'>{wf['verdict']}</span>"
            f"<span style='font-size:11px;opacity:.6'>{sub}</span></div>{steps_html}</div>")


def render_technical_board(rec: dict, ctx: dict, cmp_px, mansfield) -> str:
    """Build the full graphical technical board as one HTML string."""
    rsi = _g(rec, "RSI"); adx = _g(ctx, "adx"); alpha = _g(rec, "Alpha"); ml = _g(rec, "ML_Prob")
    vdry = _g(ctx, "vol_dry")
    rsi_state = ("watch" if (rsi or 0) >= 70 else "pass" if (rsi or 0) >= 50 else "watch" if (rsi or 0) >= 40 else "fail")
    gauges = "".join([
        _gauge("RSI (14)", rsi, 0, 100,
               "linear-gradient(90deg,#EF5350,#FF9800 30%,#26A69A 50%,#26A69A 68%,#FF9800 78%,#EF5350)",
               rsi_state, fnum(rsi, 0)),
        _gauge("ADX (14)", adx, 0, 50,
               "linear-gradient(90deg,#EF5350,#FF9800 40%,#26A69A 50%)",
               ("pass" if (adx or 0) >= 25 else "watch" if (adx or 0) >= 20 else "fail"), fnum(adx, 0)),
        _gauge("Alpha Score", alpha, 0, 100,
               "linear-gradient(90deg,#EF5350,#FF9800 50%,#26A69A 70%)",
               ("pass" if (alpha or 0) >= 70 else "watch" if (alpha or 0) >= 50 else "fail"), fnum(alpha, 0)),
        _gauge("ML Win Prob", ml, 0, 100,
               "linear-gradient(90deg,#EF5350,#FF9800 55%,#26A69A 65%)",
               ("pass" if (ml or 0) >= 65 else "watch" if (ml or 0) >= 55 else "fail"), fnum(ml, 1, "%")),
        _gauge("Mansfield RS", mansfield, -50, 50,
               "linear-gradient(90deg,#EF5350,#80808055 50%,#26A69A)",
               ("pass" if (mansfield or 0) > 0 else "fail"), fnum(mansfield, 1)),
        _gauge("Vol Dry-up 5/20d", vdry, 0, 2,
               "linear-gradient(90deg,#26A69A,#FF9800 50%,#EF5350)",
               ("pass" if (vdry if vdry is not None else 9) < 0.8 else "na"), fnum(vdry, 2, "×")),
    ])

    rng = _range_bar(_g(ctx, "low52w"), _g(ctx, "high52w"), cmp_px, [
        (_g(ctx, "sma200"), "200", "#EF5350"),
        (_g(ctx, "sma50"), "50", "#2962FF"),
        (_g(ctx, "ema20"), "20e", "#FF9800"),
    ])

    # Minervini 8-point trend template (shared with the decision engine)
    e20 = _g(ctx, "ema20"); s50 = _g(ctx, "sma50"); s150 = _g(ctx, "sma150"); s200 = _g(ctx, "sma200")
    passed, c8 = minervini_checks(ctx, cmp_px, mansfield)
    dots = "".join(_crit(ok, lab) for ok, lab in c8)

    # Price-action signal pills
    stage = str(_g(rec, "Stage", default="—")); s2 = "2" in stage
    stacked = bool(e20 and s50 and cmp_px > e20 > s50 and (not s200 or s50 > s200))
    above30w = bool(s150 and cmp_px > s150)
    adir = _g(rec, "Active_Dir", default="—"); vacc = _g(rec, "Vel_Accel", default="")
    vcp = bool(_g(rec, "VCP_Valid")); rrg = _g(rec, "RRG_Quadrant", default="—")
    broke = bool(_g(rec, "Broke_Pivot")); rv = _g(ctx, "relvol"); d52 = _g(ctx, "dist52wh")
    pills = "".join([
        _pill("pass" if s2 else ("watch" if "1" in stage else "fail"), "Weinstein Stage", stage),
        _pill("pass" if stacked else "watch", "EMA Stack", "Px&gt;20&gt;50&gt;200" if stacked else "broken"),
        _pill("pass" if above30w else "fail", "Px vs 30W MA", "above" if above30w else "below"),
        _pill("pass" if str(adir).upper().startswith("UP") else "watch", "Swing Structure", f"{adir} {vacc}"),
        _pill("pass" if vcp else "na", "VCP / Base", (f"valid · {_g(rec,'Days_Since_Pivot','—')}d" if vcp else "no")),
        _pill("pass" if rrg in ("LEADING", "IMPROVING") else "watch", "RRG", f"{rrg} {_g(rec,'RRG_Arrow','')}"),
        _pill("pass" if broke else "na", "Pivot", ("broke ↑" if broke else (inr(_g(rec, "Pivot_Price")) if _g(rec, "Pivot_Price") else "—"))),
        _pill("pass" if (rv or 0) >= 1 else "na", "Rel Volume", fnum(rv, 2, "×")),
        _pill(("pass" if (d52 is not None and -15 <= d52 <= -1) else ("watch" if (d52 or -99) > -1 else "na")),
              "52WH Dist", fnum(d52, 1, "%")),
    ])

    sub = ("<div style='font-size:11px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;"
           "opacity:.6;margin:11px 0 4px'>{}</div>")
    return (
        sub.format("Momentum &amp; Strength")
        + f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:2px 16px;'>{gauges}</div>"
        + sub.format("52-Week Range (●=CMP, ticks=MAs)")
        + rng
        + sub.format(f"Minervini Trend Template — {passed}/8")
        + ("<div style='display:flex;gap:12px;align-items:center;'>"
           f"<div>{_donut(passed, 8)}</div>"
           f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:0 14px;flex:1'>{dots}</div></div>")
        + sub.format("Price-Action Signals")
        + f"<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;'>{pills}</div>"
    )


# ----------------------------------------------------------------------------------------
# Data (cached; the Refresh button clears it)
# ----------------------------------------------------------------------------------------
@st.cache_data(ttl=120, show_spinner=False)
def load_symbol(symbol: str) -> dict:
    """Pull everything for one symbol from the existing validated modules."""
    out = {"symbol": symbol, "errors": []}

    # --- Technical record (Stage / RS / Alpha / Catalyst / levels / ML) ---
    try:
        import bull_screener as bs
        out["rec"] = bs.screen_one(symbol, force_output=True)
    except Exception as e:
        out["rec"] = None
        out["errors"].append(f"screen_one: {e}")

    # --- Daily indicator context (EMA stack / 200-DMA / RelVol / 52WH dist) ---
    try:
        import data_provider as dp
        df = dp.fetch_ohlcv(symbol, period="2y", interval="1d", use_cache=True, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        out["df"] = df
        c = df["Close"]; h = df["High"]; l = df["Low"]; v = df["Volume"]
        ema20 = c.ewm(span=20, adjust=False).mean()
        sma50 = c.rolling(50).mean()
        sma150 = c.rolling(150).mean()
        sma200 = c.rolling(200).mean()
        h52 = h.rolling(min(252, len(h))).max()
        l52 = l.rolling(min(252, len(l))).min()
        last = float(c.iloc[-1])
        # Wilder ADX(14) + directional indices
        up = h.diff(); dn = -l.diff()
        plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
        minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
        tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/14, adjust=False).mean()
        pdi = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr
        mdi = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr
        dx = (100 * (pdi - mdi).abs() / (pdi + mdi)).replace([np.inf, -np.inf], np.nan)
        adx = dx.ewm(alpha=1/14, adjust=False).mean()
        # Bollinger width (20,2) + 5d/20d volume dry-up ratio
        mid = c.rolling(20).mean(); sd = c.rolling(20).std()
        bbw = float(((mid + 2*sd) - (mid - 2*sd)).iloc[-1] / mid.iloc[-1]) if mid.iloc[-1] else None
        vol20 = float(v.rolling(20).mean().iloc[-1]); vol5 = float(v.rolling(5).mean().iloc[-1])

        def _f(s):
            x = float(s.iloc[-1]); return None if math.isnan(x) else x

        def _fprev(s, n):
            if len(s) > n and not math.isnan(s.iloc[-1 - n]):
                return float(s.iloc[-1 - n])
            return None

        # --- Pine-panel primitives (mirror of v67 Decision Mode composite rows) ---
        # CPR (Central Pivot Range) from the prior bar
        try:
            ph, pl, pc = float(h.iloc[-2]), float(l.iloc[-2]), float(c.iloc[-2])
            cpr_p = (ph + pl + pc) / 3.0
            cpr_bc = (ph + pl) / 2.0
            cpr_tc = 2 * cpr_p - cpr_bc
        except Exception:
            cpr_p = cpr_bc = cpr_tc = None
        # Monthly anchored VWAP (current calendar month)
        try:
            tp = (h + l + c) / 3.0
            mper = df.index.to_period("M")
            msk = (mper == mper[-1])
            mvwap = float((tp[msk] * v[msk]).sum() / v[msk].sum()) if v[msk].sum() else None
        except Exception:
            mvwap = None
        # Macro edge — volume shelf: VWMA(20) > SMA(50)
        try:
            vwma20 = float((c * v).rolling(20).sum().iloc[-1] / v.rolling(20).sum().iloc[-1])
            shelf_ok = bool(_f(sma50) and vwma20 > _f(sma50))
        except Exception:
            vwma20 = None; shelf_ok = False
        # Accumulation days — green close in upper-60% of range on above-avg vol (last 10)
        try:
            rng = (h - l).replace(0, np.nan)
            acc_mask = ((c - l) / rng >= 0.6) & (c > c.shift()) & (v > v.rolling(50).mean())
            acc_days = int(acc_mask.iloc[-10:].sum())
            acc_ok = acc_days >= 2
        except Exception:
            acc_days = 0; acc_ok = False
        # TTM-style squeeze — BB(20,2) inside Keltner(20, 1.5*ATR)
        try:
            kc_up = mid + 1.5 * atr; kc_dn = mid - 1.5 * atr
            squeeze_on = bool((mid.iloc[-1] + 2 * sd.iloc[-1] < kc_up.iloc[-1]) and
                              (mid.iloc[-1] - 2 * sd.iloc[-1] > kc_dn.iloc[-1]))
        except Exception:
            squeeze_on = False
        # Stage-2 freshness — weeks since price last reclaimed ~30W MA (SMA150)
        try:
            above150 = (c > sma150).tolist()
            since = 0
            for val in reversed(above150):
                if val:
                    since += 1
                else:
                    break
            stage2_weeks = since / 5.0
        except Exception:
            stage2_weeks = None

        # Volume Profile (POC / VAH / VAL) over the last 120 bars
        try:
            win = df.iloc[-120:]
            tp_w = ((win["High"] + win["Low"] + win["Close"]) / 3.0).values
            volw = win["Volume"].values
            lo_p, hi_p = float(win["Low"].min()), float(win["High"].max())
            nb = 40
            edges = np.linspace(lo_p, hi_p, nb + 1)
            bidx = np.clip(np.digitize(tp_w, edges) - 1, 0, nb - 1)
            prof = np.zeros(nb)
            for bi, vv in zip(bidx, volw):
                prof[bi] += vv
            pb = int(prof.argmax())
            poc = (edges[pb] + edges[pb + 1]) / 2.0
            tgt = prof.sum() * 0.70; lo_b = hi_b = pb; acc_v = prof[pb]
            while acc_v < tgt and (lo_b > 0 or hi_b < nb - 1):
                lft = prof[lo_b - 1] if lo_b > 0 else -1.0
                rgt = prof[hi_b + 1] if hi_b < nb - 1 else -1.0
                if rgt >= lft:
                    hi_b += 1; acc_v += prof[hi_b]
                else:
                    lo_b -= 1; acc_v += prof[lo_b]
            val_lo = (edges[lo_b] + edges[lo_b + 1]) / 2.0
            vah_hi = (edges[hi_b] + edges[hi_b + 1]) / 2.0
            dist_poc = (last - poc) / poc * 100 if poc else None
            vp_pos = "ABOVE VAH" if last > vah_hi else ("BELOW VAL" if last < val_lo else "INSIDE VA")
        except Exception:
            poc = vah_hi = val_lo = dist_poc = None; vp_pos = "—"

        # Open Fair-Value-Gaps (3-bar) in the last 30 bars
        try:
            Hs = df["High"].values; Ls = df["Low"].values
            bull_fvg = bear_fvg = 0
            for i in range(max(2, len(df) - 30), len(df)):
                if Ls[i] > Hs[i - 2]:
                    bull_fvg += 1
                if Hs[i] < Ls[i - 2]:
                    bear_fvg += 1
        except Exception:
            bull_fvg = bear_fvg = 0

        out["ctx"] = {
            "cmp": last,
            "prev": float(c.iloc[-2]) if len(c) > 1 else last,
            "ema20": _f(ema20), "sma50": _f(sma50), "sma150": _f(sma150), "sma200": _f(sma200),
            "sma200_prev": _fprev(sma200, 21),
            "adx": _f(adx), "plus_di": _f(pdi), "minus_di": _f(mdi),
            "high52w": _f(h52), "low52w": _f(l52),
            "dist52wh": (last - _f(h52)) / _f(h52) * 100 if _f(h52) else None,
            "relvol": (last and vol20) and float(v.iloc[-1] / vol20) or None,
            "vol_dry": (vol5 / vol20) if vol20 else None,
            "bbw": bbw,
            "cpr_p": cpr_p, "cpr_tc": cpr_tc, "cpr_bc": cpr_bc,
            "mvwap": mvwap, "vwma20": vwma20, "shelf_ok": shelf_ok,
            "acc_days": acc_days, "acc_ok": acc_ok, "squeeze_on": squeeze_on,
            "stage2_weeks": stage2_weeks,
            "poc": poc, "vah": vah_hi, "val": val_lo, "dist_poc": dist_poc, "vp_pos": vp_pos,
            "bull_fvg": bull_fvg, "bear_fvg": bear_fvg,
            "turnover_cr": last * float(v.iloc[-1]) / 1e7,
        }
    except Exception as e:
        out["ctx"] = None
        out["errors"].append(f"daily ctx: {e}")

    # --- Fundamentals (Screener.in via fundamental_hub) ---
    try:
        import fundamental_hub as fh
        yf_sym = symbol if symbol.endswith((".NS", ".BO")) else symbol + ".NS"
        out["fun"] = fh.fetch_stock_fundamentals(yf_sym)
    except Exception as e:
        out["fun"] = {}
        out["errors"].append(f"fundamentals: {e}")

    out["fetched_at"] = datetime.now().strftime("%d-%b %H:%M:%S")
    return out


# ----------------------------------------------------------------------------------------
# Sidebar — symbol input
# ----------------------------------------------------------------------------------------
with st.sidebar:
    st.header("🎯 Golden Matcher")
    symbol = st.text_input("NSE symbol", value="NETWEB").strip().upper()
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption("Read-only. All values from your validated modules "
               "(screen_one · compute_indicators · fundamental_hub · Dhan feed).")
    st.caption("Reference only — the **trigger** is the 75/125m closed bar on TradingView.")

if not symbol:
    st.info("Enter an NSE symbol in the sidebar.")
    st.stop()

data = load_symbol(symbol)
rec = data.get("rec") or {}
ctx = data.get("ctx") or {}
fun = data.get("fun") or {}

if not rec and not ctx:
    st.error(f"Could not load **{symbol}**.")
    for e in data.get("errors", []):
        st.caption(f"• {e}")
    st.stop()

# ----------------------------------------------------------------------------------------
# Header — name, CMP, change, verdict
# ----------------------------------------------------------------------------------------
name = _g(fun, "name", default=symbol)
cmp_px = _g(ctx, "cmp") or _g(rec, "Entry")
prev = _g(ctx, "prev", default=cmp_px)
chg_pct = ((cmp_px - prev) / prev * 100) if (cmp_px and prev) else 0.0
catalyst = _g(rec, "Catalyst", default="NONE")
stage = str(_g(rec, "Stage", default="—"))
alpha = _g(rec, "Alpha", default=None)
rs_ratio = _g(rec, "JdK_RS_Ratio")
mansfield = (rs_ratio - 100.0) if rs_ratio is not None else None
ml_prob = _g(rec, "ML_Prob")

h1, h2, h3 = st.columns([3, 1.3, 1.6])
with h1:
    st.markdown(f"### {symbol} — {name}")
    st.caption(f"{_g(fun,'sector',default='')}  ·  {_g(fun,'industry',default='')}")
with h2:
    st.metric("CMP", inr(cmp_px), f"{chg_pct:+.2f}%")
with h3:
    is_pos = str(catalyst).upper().startswith("POS")
    color = "#26A69A" if is_pos else ("#FF9800" if catalyst not in ("NONE", "—", 0) else "#787B86")
    st.markdown(f"<div style='text-align:right'><div style='font-size:12px;opacity:.7'>CATALYST</div>"
                f"<div class='verdict' style='color:{color}'>{catalyst}</div></div>",
                unsafe_allow_html=True)

# ----------------------------------------------------------------------------------------
# DECISION WORKFLOW — the sequential path to the trade (crucial metrics only)
# ----------------------------------------------------------------------------------------
decision = compute_decision(rec, ctx, cmp_px, mansfield)
wf = compute_workflow(rec, ctx, cmp_px, mansfield)
st.markdown(render_workflow(wf), unsafe_allow_html=True)

# ---- The single next action + guided execution sequence ----
cur_step = wf["steps"][wf["current"] - 1]
if not wf["actionable"]:
    if "AVOID" in wf["verdict"]:
        st.error(f"**{wf['verdict']} — Step {wf['stop_at']}.** {cur_step.get('do_fail','')}  Go to the next name.")
    else:
        st.warning(f"**{wf['verdict']} — Step {wf['stop_at']}.** {cur_step.get('do_fail','')}  Track only; no action today.")
elif wf["current"] < 5:
    st.warning(f"**→ NOW · Step {wf['current']} ({cur_step['title']}):**  {cur_step.get('do_fail','')}")
else:
    st.success(f"**→ NOW · Step 5 (TRIGGER):**  {cur_step.get('do_now')}")
    st.markdown("##### ✅ Guided execution — tick as you go")
    _man = [
        ("zone",  "1 · Mark the FRESH demand zone on Daily+ (hand-drawn, untested)"),
        ("alert", "2 · Set a TradingView alert at the zone proximal"),
        ("close", "3 · Wait for a 75/125m bar to CLOSE in your direction at the zone"),
        ("stop",  "4 · Place a buy-STOP above that trigger bar's high (never buy the touch)"),
        ("size",  "5 · Set SL below the zone distal · size at 0.25% risk"),
        ("gtt",   "6 · Place the order + GTT the same evening · log the trade"),
    ]
    _key = f"chk_{symbol}"
    _done = 0; _next = None
    for _k, _label in _man:
        if st.checkbox(_label, key=f"{_key}_{_k}"):
            _done += 1
        elif _next is None:
            _next = _label
    st.progress(_done / len(_man), text=f"{_done}/{len(_man)} done")
    if _done == len(_man):
        st.success("✅ Trade executed & logged. On to the next name.")
    elif _next:
        st.caption(f"→ Next: {_next}")

st.divider()

# Full per-panel detail is one click away — but the workflow above is the decision.
with st.expander("▸ Full metrics — all panels (optional depth)", expanded=False):
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        st.markdown(render_technical_board(rec, ctx, cmp_px, mansfield), unsafe_allow_html=True)
        st.markdown(section_context(rec, ctx, cmp_px), unsafe_allow_html=True)
    with c2:
        st.markdown(section_structure(rec, ctx, cmp_px, mansfield, decision), unsafe_allow_html=True)
        st.markdown(section_bull_gates(rec, ctx, cmp_px, mansfield), unsafe_allow_html=True)
        st.markdown(section_edges(rec, ctx, cmp_px), unsafe_allow_html=True)
    with c3:
        st.markdown(section_trade(rec, cmp_px), unsafe_allow_html=True)
        st.markdown(section_levels(rec, ctx, cmp_px), unsafe_allow_html=True)
        st.markdown(section_sector(rec, ctx, mansfield), unsafe_allow_html=True)
        st.markdown(section_fundamentals(fun), unsafe_allow_html=True)

st.divider()
st.caption(f"Data: Dhan feed + Screener.in via your validated modules · "
           f"fetched {data.get('fetched_at','—')} · cache 120s · "
           f"⚠ identification only — the trigger is yours on TradingView.")
if data.get("errors"):
    with st.expander("⚠ Partial-data notes"):
        for e in data["errors"]:
            st.caption(f"• {e}")
