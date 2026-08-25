#!/usr/bin/env python3
"""The ETF answer to the QUALITY step — ported from the ETF Dashboard/Strategy.

WHY THIS EXISTS. The GM decision path asks the same six questions of every name:
context, QUALITY, setup, location, trigger, execute. For a stock, QUALITY is BFF /
RFF / X-Ray. For an ETF there is nothing to ask -- no promoter, no margin, no
growth table -- so those gates are correctly short-circuited, and the step goes
BLANK. A blank quality step reads as "nothing to check here", which for an ETF is
the opposite of true.

An ETF has its own quality question, and it is arguably sharper than a stock's
because it is about the WRAPPER rather than the business:

    LIQUIDITY   roughly a third of the NSE ETF universe trades under Rs 1 Cr/day.
                On those, the spread you pay is the trade.
    PREMIUM     an ETF's price can drift from what it holds. Buying a 2% premium
                is a 2% loss on day one, and NO amount of stage / RS / RRG / zone
                analysis will reveal it -- every one of those reads the PRICE, and
                the price is the thing that is wrong.
    TRACKING    two funds on the same index are the same trade; what separates
                them is cost, and that shows up as a return gap over a year.

WHAT WAS DELIBERATELY *NOT* PORTED, and this is the important part.

`Commander_ETF_Strategy_v1.1` gates entries on

    BUY-LEADER = Stage 2  AND  RRG LEADING  AND  liquidity >= 6

Measured 25-Aug-2026 on 39-45 monthly anchors, point-in-time, bootstrapped by
anchor, restricted to names that clear the live liquidity gate:

    Trend / Stage   -1.37pp @60d   P(>0) 12.3%     noise-to-negative
    Rotation / RRG  -0.04pp @60d   P(>0) 48.5%     flat
    Liquidity       -1.04pp @60d                   INVERTS inside the tradeable set
    RS (Mansfield)  +2.81pp @60d, +8.21pp @120d    the only leg that measures

So that ladder is built from the three legs that did not separate winners, and
omits the one that did. Porting it as a GATE would have imported a rule the
evidence contradicts. Liquidity and premium are carried here as **status**, which
is what they are: reasons a trade is expensive, not reasons it will work.

Everything here is DISPLAY. Nothing gates.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)
_DIR = os.path.dirname(os.path.abspath(__file__))
_RESULTS = os.path.join(_DIR, "ETF_Screener_Results.csv")

# Below this the spread starts to matter more than the signal. Same threshold the
# screener gates on, imported rather than repeated so the two cannot drift.
try:
    from etf_screener import LIQ_MIN_CR as THIN_CR
except Exception:                                   # pragma: no cover
    THIN_CR = 1.0

_cache: dict = {"mtime": None, "rows": {}}


def _load() -> dict:
    """{SYMBOL: row} from the screener's own output, re-read when the file moves."""
    try:
        mt = os.path.getmtime(_RESULTS)
    except OSError:
        return {}
    if _cache["mtime"] == mt:
        return _cache["rows"]
    try:
        df = pd.read_csv(_RESULTS)
    except Exception as e:
        logger.warning("ETF quality: %s unreadable (%s)", _RESULTS, e)
        return {}
    rows = {}
    for _, r in df.iterrows():
        s = str(r.get("Symbol") or "").strip().upper()
        if s:
            rows[s] = r.to_dict()
    _cache.update({"mtime": mt, "rows": rows})
    return rows


def quality(symbol: str) -> Optional[dict]:
    """ETF quality facts, or None when the symbol is not an ETF we have scored.

    None means UNKNOWN and callers must render it as such. Returning a neutral
    dict would make an unscored ETF indistinguishable from a clean one -- the same
    rule the premium gate follows, for the same reason.
    """
    if not symbol:
        return None
    row = _load().get(str(symbol).strip().upper())
    if row is None:
        return None

    def _f(k):
        try:
            v = float(row.get(k))
            return None if v != v else v
        except (TypeError, ValueError):
            return None

    turn = _f("Turnover_60D_Cr")
    prem = None
    try:
        import etf_inav
        prem = etf_inav.premium_for(symbol)
    except Exception as e:
        logger.debug("premium unavailable for %s: %s", symbol, e)

    return {
        "turnover_cr": turn,
        "liquidity_score": _f("Liquidity_Score"),
        "premium_pct": prem,
        "asset_class": str(row.get("Asset_Class") or "") or None,
        "underlying": str(row.get("Underlying") or "") or None,
        "grade": str(row.get("Grade") or "") or None,
        "total_score": _f("Total_Score"),
        "thin": (turn is not None and turn < THIN_CR),
    }


def badge(symbol: str) -> str:
    """One compact line for the QUALITY slot, e.g.

        ETF · ₹12.4Cr · NAV +0.3%
        ETF · ₹0.4Cr THIN · NAV +19.6% ⚠

    Empty string when the symbol is not a scored ETF, so a stock row is unaffected.
    An UNKNOWN premium prints as an em-dash rather than being omitted: silence
    would read as "trades at NAV", which is the most dangerous possible default
    for this particular measurement.
    """
    q = quality(symbol)
    if q is None:
        return ""
    parts = ["ETF"]
    t = q["turnover_cr"]
    parts.append("—Cr" if t is None else
                 (f"₹{t:.1f}Cr" + (" THIN" if q["thin"] else "")))
    p = q["premium_pct"]
    if p is None:
        parts.append("NAV —")
    else:
        # 3% is where the premium gate rejects. Flag at 1% so a widening one is
        # visible before it becomes a rejection.
        flag = " ⚠" if abs(p) >= 3.0 else ("" if abs(p) < 1.0 else " ·")
        parts.append(f"NAV {p:+.1f}%{flag}")
    return "  ·  ".join(parts)


def is_scored_etf(symbol: str) -> bool:
    return quality(symbol) is not None


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    syms = sys.argv[1:] or ["GOLDBEES", "MON100", "AUTOBEES", "CPSEETF", "RELIANCE"]
    for s in syms:
        print(f"  {s:<12} {badge(s) or '(not a scored ETF)'}")
