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
MAX_SECTOR_ITEMS = 6


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


def _sector_for(symbol: str) -> tuple[str, str, list]:
    """(sector_name, sector_index, peer_symbols). ("", "", []) when unknown."""
    try:
        import sector_lookup as sl
        rec = sl.get_sector(_clean(symbol)) or {}
        name = rec.get("display_name") or rec.get("sector_name") or ""
        idx = rec.get("sector_index") or ""
        peers = []
        if idx:
            import sqlite3, os
            db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sectors.db")
            with sqlite3.connect(db) as c:
                peers = [r[0].upper() for r in c.execute(
                    "select symbol from stock_sector where sector_index=?", (idx,))]
            peers = [p for p in peers if p != _clean(symbol)]
        return name, idx, peers
    except Exception as exc:
        logger.debug("gm_ai_analysis: sector lookup failed for %s: %s", symbol, exc)
        return "", "", []


def _peer_names(peers: list) -> dict:
    """{TICKER: COMPANY NAME} from the Dhan scrip master, for the peers only.

    Headlines say "HDFC Bank" and "UltraTech Cement", not HDFCBANK and
    ULTRACEMCO, so ticker-only matching finds almost nothing on the names that
    are covered most. Measured on a 60-article corpus: ticker-only matched 0 of
    27 Bank peers. Names are the half that works.
    """
    out = {}
    try:
        import dhan_ohlcv as d
        df = d._load_scrip_master()
        df = df[(df["SEM_EXM_EXCH_ID"] == "NSE") & (df["SEM_INSTRUMENT_NAME"] == "EQUITY")]
        want = set(peers)
        for t, nm in zip(df["SEM_TRADING_SYMBOL"], df["SEM_CUSTOM_SYMBOL"]):
            t = str(t).upper()
            if t in want and isinstance(nm, str) and len(nm) > 4:
                out[t] = nm.upper()
    except Exception as exc:
        logger.debug("gm_ai_analysis: peer-name map failed: %s", exc)
    return out


def _sector_news(symbol: str, sector_name: str, peers: list, own_titles: set,
                 hours_back: int = 72) -> tuple[list, str]:
    """Sector-level items, each tagged with WHY it matched.

    MATCHING IS PEER-BASED, by ticker OR company name. It is deliberately NOT
    matched on a bare sector word: the first cut of this function accepted
    "ENERGY" and handed RELIANCE three headlines about UltraTech Cement and a
    solar JV - noise dressed as sector context, which is exactly what this was
    supposed to avoid. The only phrase accepted now is the full index name
    ("NIFTY IT", "BANK NIFTY"), which is unambiguous.

    Items already collected for the symbol itself are excluded so the two
    buckets never double-count, and the match reason travels WITH each item so
    a peer-earnings headline can be weighed differently from an index one.
    """
    if not sector_name and not peers:
        return [], "sector unknown - no sector news"
    out = []
    try:
        import news_fetcher
        blob = news_fetcher.get_news(hours_back=hours_back) or {}
        names = _peer_names(peers)
        # PHRASE ONLY. "Nifty IT" and "Bank Nifty" are unambiguous; a bare
        # sector word is not - "Energy" pulled in Solaris Horizon Energy and
        # Insolation Energy for RELIANCE, neither of them sector news. If the
        # index name is a single word, peers carry the whole job.
        idx_phrase = sector_name.upper() if " " in sector_name.strip() else None
        for a in (blob.get("articles") or []):
            title = str(a.get("title", ""))
            if title in own_titles:
                continue
            hay = (title + " " + str(a.get("summary", ""))).upper()
            hits = [p for p in peers if len(p) > 4 and p in hay]
            hits += [t for t, nm in names.items() if t not in hits and nm in hay]
            why = None
            if hits:
                why = "peer: " + ", ".join(sorted(set(hits))[:3])
            elif idx_phrase and idx_phrase in hay:
                why = f"sector index named: {sector_name}"
            if not why:
                continue
            out.append({"title": title, "source": a.get("source"),
                        "published": a.get("published"), "matched_because": why})
            if len(out) >= MAX_SECTOR_ITEMS:
                break
        note = (f"news_fetcher, matched on {len(peers)} {sector_name or 'sector'} peers "
                f"(ticker or company name) or the index name; fetched "
                f"{blob.get('fetched_at', 'n/a')}")
    except Exception as exc:
        logger.warning("gm_ai_analysis: sector news failed for %s: %s", symbol, exc)
        return [], f"sector news unavailable ({exc})"
    return out, note

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
    sec_name, sec_idx, peers = _sector_for(sym)
    sec_items, sec_src = _sector_news(sym, sec_name, peers, {str(a.get("title", "")) for a in arts})
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
        "sector": {"name": sec_name, "index": sec_idx, "peer_count": len(peers)},
        "news": {"articles": arts, "announcements": anns, "sector_items": sec_items},
        "_provenance": {
            "decision_context": "gm_evaluate (same engine as the Trigger Board)",
            "fundamentals": xray_src,
            "analyst_calls": analyst_src,
            "news": news_src,
            "sector_news": sec_src,
        },
        "_missing": [],
    }
    for k, v in (("fundamentals", xray), ("analyst_calls", analyst)):
        if not v:
            payload["_missing"].append(k)
    if not arts and not anns:
        payload["_missing"].append("news (nothing matched this symbol in the window)")
    if not sec_items:
        payload["_missing"].append("sector news (no peer or sector-name match in the window)")
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
Cover the SECTOR separately from the stock: news.sector_items are peer or
sector-level, each carrying "matched_because". A peer result is context for
the sector, NOT evidence about this company — say which is which, and say
plainly when the only news here is about somebody else.

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
