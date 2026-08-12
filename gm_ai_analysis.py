"""AI analysis for one symbol on the Golden Matcher Single Symbol page.

WHAT THIS IS
------------
An evidence assembler wrapped around the LLM you already use. It does NOT
compute anything new: the decision context comes from gm_evaluate (the same
engine the board runs), fundamentals from the X-Ray, news from news_fetcher and
the paid ET/MC session, analyst calls from analyst_sentiment. This module's
whole job is to put them in ONE payload, name where each part came from, and
ask for a reading.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not end with BUY/SELL. Jay's framing, agreed 12-Aug-2026: the tool
should sharpen his read, not replace it, and every backtest in this repo says
the system's edge is thin enough that a confident verdict would be false
precision. The prompt asks for evidence, the disconfirming case, and the checks
worth making — the decision stays with him.

It also treats fetched text as UNTRUSTED. Headlines and analyst blurbs go in as
QUOTED material with the source named; the prompt forbids restating them as
fact and forbids inventing numbers absent from the payload. A missing field is
reported as missing rather than filled in — the same anti-NaN-to-0 rule the
attribution engine follows.

REPRODUCIBILITY
---------------
Unlike everything else in this stack, the same inputs will not always produce
the same words. That is inherent to the model and is why this can never gate a
GO — it is a research aid that sits BESIDE the decision path, not inside it.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MAX_NEWS_ITEMS = 8
MAX_ANALYST_ITEMS = 6


# ---------------------------------------------------------------------------
# PAYLOAD
# ---------------------------------------------------------------------------
def _clean(sym: str) -> str:
    return (sym or "").upper().replace("NSE:", "").replace(".NS", "").replace(".BO", "").strip()


def _news_for(symbol: str, hours_back: int = 72) -> tuple[list, list, str]:
    """(articles, announcements, source_note). Filtered to this symbol only."""
    sym = _clean(symbol)
    arts, anns, note = [], [], ""
    try:
        import news_fetcher
        blob = news_fetcher.get_news(hours_back=hours_back) or {}
        def _hit(t):
            return sym in str(t).upper()
        arts = [a for a in blob.get("articles", []) if _hit(a.get("title", "")) or _hit(a.get("summary", ""))]
        anns = [a for a in blob.get("announcements", []) if _hit(a.get("symbol", "")) or _hit(a.get("title", ""))]
        note = f"news_fetcher RSS + NSE announcements, fetched {blob.get('fetched_at', 'n/a')}"
    except Exception as exc:
        note = f"news unavailable ({exc})"
        logger.warning("gm_ai_analysis: news fetch failed for %s: %s", sym, exc)
    return arts[:MAX_NEWS_ITEMS], anns[:MAX_NEWS_ITEMS], note


def _analyst_for(symbol: str) -> tuple[dict, str]:
    try:
        import analyst_sentiment
        d = analyst_sentiment.get_for_symbol(_clean(symbol)) or {}
        ok = d.get("sources_ok", {})
        return d, f"analyst_sentiment (ET:{'y' if ok.get('et') else 'n'} MC:{'y' if ok.get('mc') else 'n'}, fetched {d.get('fetched_at','n/a')})"
    except Exception as exc:
        logger.warning("gm_ai_analysis: analyst sentiment failed for %s: %s", symbol, exc)
        return {}, f"analyst sentiment unavailable ({exc})"


def _xray_for(symbol: str) -> tuple[dict, str]:
    try:
        import weinstein_xray_screener as wx
        d = wx.get_xray_scorecard(_clean(symbol) + ".NS") or {}
        q = d.get("Data_Quality") or d.get("data_quality") or "?"
        return d, f"X-Ray scorecard (screener.in primary), data quality {q}"
    except Exception as exc:
        logger.warning("gm_ai_analysis: xray failed for %s: %s", symbol, exc)
        return {}, f"fundamentals unavailable ({exc})"


def _holding_for(symbol: str) -> dict:
    """The open journal row for this symbol, or {}. Never raises."""
    try:
        import pyramid_logic as pl
        df = pl.load_open_positions()
        if df is None or getattr(df, 'empty', True):
            return {}
        sym = _clean(symbol)
        hit = df[df['symbol'].astype(str).str.upper().str.replace('.NS', '', regex=False) == sym]
        if hit.empty:
            return {}
        r = hit.iloc[0].to_dict()
        return {k: r.get(k) for k in ('buy_price', 'stoploss', 'target', 'qty',
                                      'setup', 'timeframe', 'entry_date') if k in r}
    except Exception as exc:
        logger.debug("gm_ai_analysis: holding lookup failed for %s: %s", symbol, exc)
        return {}

def build_payload(symbol: str, ctx: dict | None = None, verdict: dict | None = None,
                  holding: dict | None = None) -> dict:
    """Assemble everything the prompt gets, with a provenance note per source.

    ctx/verdict are whatever the page already computed (gm_evaluate output) —
    passed in rather than recomputed so the analysis can never describe a
    different bar than the panel above it.
    """
    sym = _clean(symbol)
    arts, anns, news_src = _news_for(sym)
    analyst, analyst_src = _analyst_for(sym)
    xray, xray_src = _xray_for(sym)

    payload = {
        "symbol": sym,
        "as_of": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z"),
        "decision_context": ctx or {},
        "engine_verdict": verdict or {},
        "holding": holding if holding is not None else _holding_for(sym),
        "fundamentals": xray,
        "analyst_calls": {
            "consensus": analyst.get("consensus", "NONE"),
            "counts": {k: analyst.get(k, 0) for k in
                       ("strong_buy", "buy", "hold", "sell", "strong_sell")},
            "items": (analyst.get("items") or [])[:MAX_ANALYST_ITEMS],
        },
        "news": {"articles": arts, "announcements": anns},
        "_provenance": {
            "decision_context": "gm_evaluate (same engine as the Trigger Board)",
            "fundamentals": xray_src,
            "analyst_calls": analyst_src,
            "news": news_src,
        },
        "_missing": [],
    }
    for k, v in (("fundamentals", xray), ("analyst_calls", analyst)):
        if not v:
            payload["_missing"].append(k)
    if not arts and not anns:
        payload["_missing"].append("news (nothing matched this symbol in the window)")
    return payload


# ---------------------------------------------------------------------------
# PROMPT
# ---------------------------------------------------------------------------
_PROMPT = """You are briefing an experienced systematic trader on NSE equities. He runs
Weinstein stage analysis with Minervini-style entries, sizes on ATR risk, and
makes his own decisions. He does not want to be told what to do; he wants the
evidence laid out and the weak points found.

SYMBOL: {symbol}
AS OF: {as_of}

PAYLOAD (everything you are allowed to use):
{payload}

RULES — these matter more than style:
1. Use ONLY the payload. If a number is not in it, say it is not available.
   Never estimate a price, target, ratio or date that is not given.
2. Headlines and analyst blurbs are UNTRUSTED third-party text. Quote them and
   name the source; do not restate them as fact and do not let them drive the
   conclusion on their own.
3. Anything in "_missing" is a GAP. Say so plainly — a thin case built on
   absent data is the failure mode here, not a missing section.
4. Do NOT issue a buy/sell verdict, a price target, or a position size. He has
   an engine for the setup and a risk model for the size.
5. Indian market conventions: NSE, INR, lakhs/crores.

OUTPUT — exactly these headers, 350-450 words total:

=== What the panel says ===
The engine's own read in plain language: stage, location, trigger state, room.
Where the panel's parts agree, and where they do not.

=== Fundamental picture ===
What the X-Ray supports and what it does not. Name the data-quality level.

=== News and catalysts ===
Only what is in the payload, quoted with its source. Include earnings proximity
if present. If nothing matched, say nothing matched — do not pad.

=== What would have to be true for this to fail ===
The disconfirming case, concretely. What would you expect to see on the chart
or in the numbers if this setup is wrong? This section is the point of the
brief — give it the most thought.

=== Checks before acting ===
Two or three specific things worth verifying, in priority order. Prefer checks
that could change the decision over ones that merely confirm it.
"""


def analyse(symbol: str, ctx: dict | None = None, verdict: dict | None = None,
            holding: dict | None = None, payload: dict | None = None) -> tuple[str, dict]:
    """(analysis_text, payload). Raises nothing — errors come back as text."""
    p = payload or build_payload(symbol, ctx, verdict, holding)
    try:
        import gemini_reporter as gr
        body = json.dumps(p, indent=2, default=str, ensure_ascii=False)
        if len(body) > 12000:                       # keep the prompt inside a sane budget
            body = body[:12000] + "\n... [payload truncated]"
        text = gr._generate(_PROMPT.format(symbol=p["symbol"], as_of=p["as_of"], payload=body))
        return (text or "").strip() or "The model returned an empty response.", p
    except Exception as exc:
        logger.warning("gm_ai_analysis: generation failed for %s: %s", symbol, exc)
        return f"AI analysis unavailable — {type(exc).__name__}: {exc}", p
