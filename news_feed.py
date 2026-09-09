# news_feed.py
# Public-facing news API for Commander Web v4.0 NEWS page.
# Returns DataFrames with columns expected by the UI:
#   source, title, summary, link, published_ts, sentiment, sentiment_color
# No extra pip installs — stdlib urllib + xml.etree + pandas only.

import os, re, time, logging
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError
import xml.etree.ElementTree as ET

import pandas as pd

logger = logging.getLogger(__name__)
_DIR = os.path.dirname(os.path.abspath(__file__))
# Browser-grade UA — Cloudflare in front of Moneycontrol / ET / BS routinely
# 503s requests with a bare "AppleWebKit/537.36" footprint. Use a current
# Chrome-on-Windows token plus the matching Accept-Language / Sec-Fetch hints
# that CF expects to see together.
UA   = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
_BROWSER_HEADERS = {
    "User-Agent":       UA,
    "Accept":           "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
    "Accept-Language":  "en-IN,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding":  "identity",
    "Connection":       "keep-alive",
    "Sec-Fetch-Dest":   "document",
    "Sec-Fetch-Mode":   "navigate",
    "Sec-Fetch-Site":   "none",
    "Cache-Control":    "no-cache",
}

# Module-level health tracker so the UI can surface "3 of 7 feeds failing"
# without us having to inject fake rows into the news DataFrame.
_LAST_FEED_HEALTH: dict = {}

# ── Feed definitions ────────────────────────────────────────────────────────
# Moneycontrol's public RSS endpoints (markets.xml + business.xml) were dropped
# from the feed list on 18 May 2026 — both confirmed dead. markets.xml returns
# HTTP 503 unconditionally; business.xml returns 200 but the newest item is
# from April 2024, so every entry gets filtered out by the hours_back cutoff.
# MC has effectively abandoned their free RSS infrastructure. Paid MC content
# is still available via the ET Prime + MC Pro tab (cookie-authenticated).
# Replaced with three fresh sources verified live on 18 May 2026.
RSS_FEEDS = {
    "Economic Times Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Economic Times Stocks":  "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    "CNBCTV18 Markets":       "https://www.cnbctv18.com/commonfeeds/v1/cne/rss/market.xml",
    "Business Standard":      "https://www.business-standard.com/rss/markets-106.rss",
    "Business Standard Co.":  "https://www.business-standard.com/rss/companies-101.rss",
    "LiveMint Markets":       "https://www.livemint.com/rss/markets",
    "LiveMint Companies":     "https://www.livemint.com/rss/companies",
    "NDTV Profit":            "https://feeds.feedburner.com/ndtvprofit-latest",
}

BULLISH_WORDS = {
    "surge", "rally", "gain", "rise", "jump", "soar", "breakout", "bull",
    "strong", "record high", "positive", "growth", "upgrade", "inflow",
    "recovery", "rebound", "outperform", "accumulate", "high", "boost",
    "buy", "long", "bullish",
}
BEARISH_WORDS = {
    "fall", "drop", "crash", "decline", "plunge", "bear", "weak",
    "loss", "sell", "downgrade", "low", "negative", "slump", "tumble",
    "outflow", "concern", "risk", "caution", "cut", "below", "fear",
    "short", "bearish",
}

# Simple in-process TTL cache
_cache: dict = {}
_CACHE_TTL   = 1800  # 30 min


# ── Internal helpers ─────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _parse_pubdate(raw: str):
    raw = (raw or "").strip()
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None) - dt.utcoffset() + timedelta(hours=5, minutes=30)
            return dt
        except (ValueError, TypeError):
            continue
    return None


def _fetch_with_retry(url: str, attempts: int = 3) -> bytes:
    """Fetch with exponential backoff. Re-raises the last exception on failure.

    Cloudflare-fronted endpoints (Moneycontrol, ET, BS) frequently return a
    transient 503 on the first hit and succeed on the second. A short retry
    loop turns most "Service Unavailable" cases into successful reads.
    """
    last_exc = None
    for i in range(attempts):
        try:
            req = Request(url, headers=_BROWSER_HEADERS)
            with urlopen(req, timeout=12) as resp:
                return resp.read()
        except Exception as e:
            last_exc = e
            # Only retry on transient 5xx / timeout / reset — give up on 4xx.
            msg = str(e)
            if any(t in msg for t in ("503", "502", "504", "timed out", "reset")):
                time.sleep(0.6 * (i + 1))
                continue
            raise
    raise last_exc if last_exc else RuntimeError("fetch failed")


def _fetch_feed(source: str, url: str, max_items: int, hours_back: int) -> list:
    cutoff  = datetime.now() - timedelta(hours=hours_back)
    ns_atom = {"atom": "http://www.w3.org/2005/Atom"}
    rows: list = []
    try:
        xml_bytes = _fetch_with_retry(url)
        root  = ET.fromstring(xml_bytes.decode("utf-8", errors="replace"))
        items = root.findall(".//item") or root.findall(".//atom:entry", ns_atom)

        for item in items[:max_items]:
            title   = _strip_html(item.findtext("title","") or item.findtext("atom:title","",ns_atom))
            summary = _strip_html(item.findtext("description","") or item.findtext("atom:summary","",ns_atom))[:300]
            link_el = item.find("atom:link", ns_atom)
            link    = item.findtext("link","") or (link_el.get("href","") if link_el is not None else "")
            pub_raw = item.findtext("pubDate","") or item.findtext("atom:published","",ns_atom)
            pub_dt  = _parse_pubdate(pub_raw)

            if pub_dt and pub_dt < cutoff:
                continue
            if not title:
                continue

            rows.append({
                "source":       source,
                "title":        title,
                "summary":      summary,
                "link":         link,
                "published_ts": pub_dt.strftime("%d %b %H:%M") if pub_dt else "",
                "_sort_key":    pub_dt.isoformat() if pub_dt else "",
            })

        _LAST_FEED_HEALTH[source] = "ok"
    except ET.ParseError as e:
        logger.warning("Parse error [%s]: %s", source, e)
        _LAST_FEED_HEALTH[source] = f"parse error: {str(e)[:60]}"
    except (URLError, Exception) as e:
        logger.warning("Fetch error [%s]: %s", source, e)
        _LAST_FEED_HEALTH[source] = f"unavailable: {str(e)[:60]}"
    return rows


# ── Public API ───────────────────────────────────────────────────────────────

def fetch_all_news(max_per_feed: int = 12, hours_back: int = 18) -> pd.DataFrame:
    """
    Fetch news from all configured RSS feeds.
    Returns DataFrame with columns: source, title, summary, link, published_ts.
    Call add_sentiment() to enrich with sentiment labels.
    """
    cache_key = f"all_{max_per_feed}_{hours_back}"
    entry = _cache.get(cache_key)
    if entry and time.time() < entry["exp"]:
        return entry["df"].copy()

    all_rows: list = []
    for source, url in RSS_FEEDS.items():
        all_rows.extend(_fetch_feed(source, url, max_per_feed, hours_back))

    if all_rows:
        df = pd.DataFrame(all_rows)
        df = df.sort_values("_sort_key", ascending=False).reset_index(drop=True)
    else:
        df = pd.DataFrame(columns=["source","title","summary","link","published_ts","_sort_key"])

    _cache[cache_key] = {"df": df.copy(), "exp": time.time() + _CACHE_TTL}
    return df


def add_sentiment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich DataFrame with sentiment label and colour.
    Adds: sentiment ("🟢 Bullish" | "🔴 Bearish" | "🟡 Neutral"), sentiment_color (hex).
    """
    if df.empty:
        return df

    def _score_row(row):
        combined = (str(row.get("title","")) + " " + str(row.get("summary",""))).lower()
        bull = sum(1 for w in BULLISH_WORDS if w in combined)
        bear = sum(1 for w in BEARISH_WORDS if w in combined)
        if bull > bear: return "🟢 Bullish", "#00f260"
        if bear > bull: return "🔴 Bearish", "#ff4b4b"
        return "🟡 Neutral", "#e3b341"

    scored = df.apply(_score_row, axis=1, result_type="expand")
    df = df.copy()
    df["sentiment"]       = scored[0]
    df["sentiment_color"] = scored[1]
    return df


def filter_by_symbol(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Return rows mentioning the given symbol or company name (case-insensitive)."""
    if df.empty or not symbol:
        return pd.DataFrame()
    sym = symbol.strip().upper().replace(".NS", "")
    mask = (
        df["title"].str.upper().str.contains(sym, na=False) |
        df["summary"].str.upper().str.contains(sym, na=False)
    )
    return df[mask].reset_index(drop=True)


def get_market_news_summary(df: pd.DataFrame) -> dict:
    """Return aggregate sentiment stats dict from a news DataFrame."""
    if df.empty or "sentiment" not in df.columns:
        return {"total": 0, "bullish": 0, "bearish": 0, "neutral": 0, "score": 0.0}
    total   = len(df)
    bullish = int(df["sentiment"].str.contains("Bullish", na=False).sum())
    bearish = int(df["sentiment"].str.contains("Bearish", na=False).sum())
    neutral = total - bullish - bearish
    score   = round((bullish - bearish) / max(total, 1) * 100, 1)
    return {"total": total, "bullish": bullish, "bearish": bearish,
            "neutral": neutral, "score": score}


def get_feed_health() -> dict:
    """Probe all feeds; returns {source: 'ok' | 'error: ...'} dict."""
    health = {}
    for source, url in RSS_FEEDS.items():
        try:
            req = Request(url, headers=_BROWSER_HEADERS)
            with urlopen(req, timeout=8) as resp:
                health[source] = "ok" if resp.status == 200 else f"HTTP {resp.status}"
        except Exception as e:
            health[source] = f"error: {str(e)[:40]}"
    return health


def get_last_feed_health() -> dict:
    """Return the per-source status recorded during the most recent
    fetch_all_news() call. Empty until fetch_all_news() has run.

    Used by the NEWS page to render a one-line health pill instead of
    inserting "Feed unavailable" placeholder rows into the news list."""
    return dict(_LAST_FEED_HEALTH)
