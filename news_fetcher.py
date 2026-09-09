# news_fetcher.py
# Financial news aggregator — RSS feeds + NSE corporate announcements
# No extra dependencies beyond stdlib + requests (already used project-wide)
# Cache: reports/news_cache.json with 30-minute TTL

import os, re, time, json, logging
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)
_DIR        = os.path.dirname(os.path.abspath(__file__))
_CACHE_FILE = os.path.join(_DIR, "reports", "news_cache.json")
_CACHE_TTL  = 1800   # 30 minutes

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

RSS_FEEDS = {
    "ET Markets":        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Moneycontrol":      "https://www.moneycontrol.com/rss/business.xml",
    "Business Standard": "https://www.business-standard.com/rss/markets-106.rss",
    "LiveMint":          "https://www.livemint.com/rss/markets",
}

BULLISH_WORDS = {
    "surge", "rally", "gain", "rise", "jump", "soar", "breakout", "bull",
    "strong", "record high", "positive", "growth", "upgrade", "inflow",
    "recovery", "rebound", "outperform", "accumulate", "high", "boost",
}
BEARISH_WORDS = {
    "fall", "drop", "crash", "decline", "plunge", "bear", "weak",
    "loss", "sell", "downgrade", "low", "negative", "slump", "tumble",
    "outflow", "concern", "risk", "caution", "cut", "below", "fear",
}


# ── helpers ────────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _score(title: str, summary: str) -> str:
    combined = (title + " " + summary).lower()
    bull = sum(1 for w in BULLISH_WORDS if w in combined)
    bear = sum(1 for w in BEARISH_WORDS if w in combined)
    if bull > bear: return "bullish"
    if bear > bull: return "bearish"
    return "neutral"


def _parse_pubdate(raw: str):
    """Try common RSS/Atom date formats; return naive IST datetime or None."""
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",   # RFC 2822
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",         # ISO 8601
        "%Y-%m-%dT%H:%M:%SZ",
        "%d %b %Y %H:%M:%S %z",
    ):
        try:
            dt = datetime.strptime(raw, fmt)
            # Convert to naive IST (UTC+5:30)
            if dt.tzinfo is not None:
                dt = dt.utctimetuple()
                dt = datetime(*dt[:6]) + timedelta(hours=5, minutes=30)
            return dt
        except ValueError:
            continue
    return None


def _parse_rss(xml_text: str, source: str, hours_back: int) -> list:
    cutoff   = datetime.now() - timedelta(hours=hours_back)
    articles = []
    ns_atom  = {"atom": "http://www.w3.org/2005/Atom"}

    try:
        root  = ET.fromstring(xml_text)
        items = root.findall(".//item") or root.findall(".//atom:entry", ns_atom)

        for item in items[:20]:
            title   = _strip_html(
                item.findtext("title", "") or
                item.findtext("atom:title", "", ns_atom)
            )
            summary = _strip_html(
                item.findtext("description", "") or
                item.findtext("atom:summary", "", ns_atom)
            )[:280]
            link_el = item.find("atom:link", ns_atom)
            link    = (
                item.findtext("link", "") or
                (link_el.get("href", "") if link_el is not None else "")
            )
            pub_raw = (
                item.findtext("pubDate", "") or
                item.findtext("atom:published", "", ns_atom)
            )
            pub_dt  = _parse_pubdate(pub_raw)

            if pub_dt and pub_dt < cutoff:
                continue
            if not title:
                continue

            articles.append({
                "source":    source,
                "title":     title,
                "summary":   summary,
                "link":      link,
                "published": pub_dt.strftime("%d %b %H:%M") if pub_dt else "",
                "pub_dt":    pub_dt.isoformat() if pub_dt else "",
                "sentiment": _score(title, summary),
            })

    except ET.ParseError as e:
        logger.warning("RSS parse error [%s]: %s", source, e)

    return articles


# ── public API ─────────────────────────────────────────────────────────────

def fetch_rss_news(hours_back: int = 18) -> list:
    """Fetch & merge RSS news from all configured feeds."""
    all_articles: list = []

    for source, url in RSS_FEEDS.items():
        try:
            req = Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml"})
            with urlopen(req, timeout=12) as resp:
                xml_text = resp.read().decode("utf-8", errors="replace")
            arts = _parse_rss(xml_text, source, hours_back)
            all_articles.extend(arts)
            logger.info("RSS [%s]: %d articles", source, len(arts))
        except (URLError, Exception) as e:
            logger.warning("RSS fetch failed [%s]: %s", source, e)

    all_articles.sort(key=lambda a: a.get("pub_dt", ""), reverse=True)
    return all_articles


def fetch_nse_announcements(count: int = 25) -> list:
    """Fetch latest NSE corporate announcements (equities)."""
    try:
        import requests
        sess = requests.Session()
        sess.headers.update({"User-Agent": UA, "Referer": "https://www.nseindia.com"})
        sess.get("https://www.nseindia.com", timeout=8)
        r = sess.get(
            "https://www.nseindia.com/api/corporate-announcements?index=equities",
            timeout=12,
        )
        if r.status_code == 200:
            raw = r.json()
            return [
                {
                    "symbol":   item.get("symbol", ""),
                    "subject":  item.get("subject", item.get("desc", ""))[:120],
                    "date":     item.get("exchdisstime", item.get("bm_timestamp", "")),
                    "category": item.get("bm_corp_ann_category", "General"),
                }
                for item in raw[:count]
            ]
    except Exception as e:
        logger.warning("NSE announcements failed: %s", e)
    return []


def get_news(hours_back: int = 18, force_refresh: bool = False) -> dict:
    """
    Main entry point.
    Returns {"articles": [...], "announcements": [...], "fetched_at": "...", "_ts": float}.
    Results are cached for 30 minutes in reports/news_cache.json.
    """
    os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)

    if not force_refresh and os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, encoding="utf-8") as f:
                cached = json.load(f)
            if time.time() - cached.get("_ts", 0) < _CACHE_TTL:
                return cached
        except Exception:
            pass

    articles      = fetch_rss_news(hours_back=hours_back)
    announcements = fetch_nse_announcements()

    result = {
        "articles":      articles,
        "announcements": announcements,
        "fetched_at":    datetime.now().strftime("%Y-%m-%d %H:%M IST"),
        "_ts":           time.time(),
    }
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
    except Exception as e:
        logger.warning("News cache save failed: %s", e)

    return result
