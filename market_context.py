"""market_context.py - one line of market backdrop, shared by the reviewer and S4.

2-Oct-2026 (Jay). The regime verdict plus Nifty 500 breadth (A/D, % above 50/200-DMA,
52-week highs/lows, Stage-2 share) and the McClellan oscillator. Sources:
regime_state.json and reports/latest_breadth.json, both written by the 16:45 jobs.

Information only: it sets expectations and size, it never vetoes a setup. Each source
carries its own date so a stale file reads as stale; a missing source is omitted,
never filled. One builder, so the reviewer's prompt and the S4 panel cannot disagree.
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def parts() -> list[str]:
    out = []
    try:
        with open(os.path.join(HERE, "regime_state.json"), encoding="utf-8") as f:
            rg = (json.load(f) or {}).get("last") or {}
        if rg.get("verdict"):
            out.append("regime %s (score %s · %s)" % (rg.get("verdict"), rg.get("score"),
                                                    str(rg.get("computed_at") or "")[:10]))
    except Exception:
        pass
    try:
        with open(os.path.join(HERE, "reports", "latest_breadth.json"), encoding="utf-8") as f:
            bj = json.load(f) or {}
        b = bj.get("breadth") or {}
        if b.get("advance_count") is not None:
            out.append("Nifty 500 breadth %s: A/D %s/%s · above 50/200-DMA %s%%/%s%% · 52w highs/lows %s/%s · Stage 2 %s%%"
                       % (bj.get("date"), b.get("advance_count"), b.get("decline_count"),
                          b.get("above_sma50_pct"), b.get("above_sma200_pct"),
                          b.get("new_52w_high_count"), b.get("new_52w_low_count"), b.get("stage2_pct")))
        m = bj.get("mcclellan") or {}
        if m.get("oscillator") is not None:
            out.append("McClellan osc %s / summation %s (%s)" % (m.get("oscillator"), m.get("summation"), m.get("last_date")))
    except Exception:
        pass
    return out


def exposure() -> str:
    """The exposure rule's line (house_policy.exposure_status, Option A, 6-Oct-2026), or ''."""
    try:
        import house_policy as hp
        return hp.exposure_status().get("text", "")
    except Exception:
        return ""


def for_review() -> str:
    """The reviewer's prompt block, or '' when nothing is known. The market context is
    information; the EXPOSURE RULE line under it is binding (6-Oct-2026)."""
    p = parts()
    ex = exposure()
    if not p and not ex:
        return ""
    out = ""
    if p:
        out = ("MARKET CONTEXT (information, not a gate - it sets expectations and size, never vetoes a setup)\n"
               + " · ".join(p))
    if ex:
        out += ("\n\n" if out else "") + "EXPOSURE RULE (house rule, BINDING - unlike the context above): " + ex
    return out


def for_s4() -> str:
    """The S4 bundle's MKT section: one line, safe inside the pipe-separated bundle
    (no '|'). Empty when nothing is known, which leaves S4's default text in place."""
    ex = exposure()
    return " · ".join(parts() + ([ex] if ex else [])).replace("|", "/")
