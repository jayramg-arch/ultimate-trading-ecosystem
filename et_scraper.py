"""
et_scraper.py — Economic Times scraper for analyst recos + per-stock news.

Uses the authenticated session from paid_news_cookies.get_session('et').
Cookies must have been exported via setup_paid_news_cookies.py first.

Public API
----------
    fetch_recos(limit=50, force=False) -> list[dict]
        Pulls the Recos list page, parses each headline into structured fields:
            {title, url, brokerage, action, stocks_mentioned[], snippet, fetched_at}
        Cached 1h to data/cache/et_recos.json. Pass force=True to bypass cache.

    fetch_news_for_stock(symbol, limit=20) -> list[dict]
        Pulls the topic page for the stock + filters Recos for stock mentions.
        Returns dicts: {title, url, source, published, snippet}

    fetch_article(url, force=False) -> dict
        Fetches a single ET article body. Cached.

    health_check() -> dict
        Quick session-state probe for the UI.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Dict, List, Optional, Set

from bs4 import BeautifulSoup

from paid_news_cookies import get_session, SITES

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ET_BASE = "https://economictimes.indiatimes.com"
RECOS_URL = f"{ET_BASE}/markets/stocks/recos"

# Lower-cased keywords that map to consensus buckets.
# STRONG_BUY / STRONG_SELL are checked FIRST so "strong buy" isn't accidentally
# captured by the plain "buy" rule. Order matters in _extract_action.
ACTION_BUCKETS = {
    "STRONG_BUY":  ["strong buy", "high conviction buy", "top pick", "best idea",
                     "best ideas", "aggressive buy", "screaming buy",
                     "outperform with high conviction", "high-conviction buy",
                     "conviction buy", "strong outperform"],
    "STRONG_SELL": ["strong sell", "strong underweight", "high conviction sell",
                     "strong underperform"],
    "BUY":         ["buy", "outperform", "overweight", "accumulate", "add",
                     "raise target", "raises target", "hike target", "hikes target",
                     "upgrades to buy", "upgrades to overweight",
                     "remains bullish", "stays bullish", "bullish",
                     "initiates with buy", "initiated with buy",
                     "target raised"],
    "HOLD":        ["hold", "neutral", "equal weight", "equal-weight",
                     "market perform", "maintains neutral", "maintains hold",
                     "remains neutral", "stays neutral"],
    "SELL":        ["sell", "underweight", "underperform", "reduce", "exit",
                     "downgrade to sell", "cuts target", "cut target",
                     "target cut", "downgrades to sell"],
}

# Common Indian brokerage names — used to extract the "who" from a headline
KNOWN_BROKERAGES = [
    "Morgan Stanley", "Goldman Sachs", "Citi", "JP Morgan", "JPMorgan",
    "Jefferies", "Macquarie", "UBS", "Bernstein", "Nomura", "HSBC", "BofA",
    "Bank of America", "CLSA", "Credit Suisse", "Deutsche Bank",
    "Motilal Oswal", "Nuvama", "Elara", "Kotak", "ICICI Securities", "IIFL",
    "Anand Rathi", "Axis Securities", "HDFC Securities", "JM Financial",
    "Edelweiss", "Antique", "Sharekhan", "Emkay", "Centrum", "Prabhudas Lilladher",
    "Prabhudas", "Equirus", "Investec", "Phillip Capital", "Phillip",
    "DAM Capital", "InCred", "Yes Securities", "BNP Paribas", "DBS",
    "Choice", "ICICI Direct", "Religare", "SMC", "Geojit",
]


def _cache_path(name: str) -> str:
    return os.path.join(CACHE_DIR, name)


def _read_cache(name: str, ttl_seconds: int) -> Optional[Dict]:
    p = _cache_path(name)
    if not os.path.exists(p):
        return None
    if time.time() - os.path.getmtime(p) > ttl_seconds:
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(name: str, data) -> None:
    try:
        with open(_cache_path(name), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.debug("cache write failed for %s: %s", name, e)


def _extract_brokerage(text: str) -> Optional[str]:
    """Find the first known brokerage name mentioned in the headline."""
    for b in KNOWN_BROKERAGES:
        if re.search(r"\b" + re.escape(b) + r"\b", text, re.I):
            return b
    return None


def _extract_action(text: str) -> str:
    """Map text to BUY / HOLD / SELL bucket (best effort). Returns 'OTHER' if none match.

    Strips the standard "Buy, Sell or Hold:" framing prefix before scanning so
    we extract the ACTUAL recommendation (in the body), not the framing word.
    """
    t = text.lower()
    # Strip standard ET headline framings that contain all three words but say nothing
    for prefix_pat in [
        r"^buy,?\s+sell\s+or\s+hold:\s*",
        r"^buy/sell/hold:\s*",
        r"^stock(s)?\s+(to\s+)?buy(\s+today)?:\s*",
    ]:
        t = re.sub(prefix_pat, "", t)
    for bucket, kws in ACTION_BUCKETS.items():
        for kw in kws:
            if re.search(r"\b" + re.escape(kw) + r"\b", t):
                return bucket
    return "OTHER"


def _extract_stocks(text: str) -> List[str]:
    """Pull capitalized stock names from a recos headline.

    Heuristic: looks for `on <Stock Name>` or `<Stock Name> recommendations`
    patterns. Returns list of likely stock names (caller filters against
    real ticker list).
    """
    candidates = set()
    # Pattern 1: "on Stock Name" / "for Stock Name"
    for m in re.finditer(
        r"\b(?:on|for|in|to)\s+([A-Z][A-Za-z0-9& ]{2,40}?)(?:[,;.\)]|\s+(?:and|maintains|raises|cuts|hikes|recommends|upgrades|downgrades|target|after|while|while|with|but)|\Z)",
        text
    ):
        s = m.group(1).strip()
        # Filter out common non-stock words
        if s and not re.match(r"^(?:the|its|their|after|while|despite)$", s, re.I):
            candidates.add(s)
    # Pattern 2: "Stock Name; Brokerage on" — symbol followed by semicolon
    for m in re.finditer(r"on\s+([A-Z][A-Za-z0-9& ]{2,40}?);", text):
        candidates.add(m.group(1).strip())
    return sorted(candidates)


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

def fetch_recos(limit: int = 50, force: bool = False) -> List[Dict]:
    """Fetch ET Recos list page. Returns parsed list of recommendation dicts."""
    cache_key = "et_recos.json"
    if not force:
        cached = _read_cache(cache_key, ttl_seconds=60 * 60)  # 1h
        if cached and "recos" in cached:
            return cached["recos"][:limit]

    try:
        sess = get_session("et")
        resp = sess.get(RECOS_URL, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("ET fetch_recos failed: %s", e)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    recos: List[Dict] = []

    # Strategy: any anchor whose href contains "/recos/" — the article URL slug
    seen_urls: Set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/recos/" not in href:
            continue
        full_url = href if href.startswith("http") else ET_BASE + href
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        title = re.sub(r"\s+", " ", a.get_text()).strip()
        if not title or len(title) < 15:
            continue

        recos.append({
            "title":             title,
            "url":               full_url,
            "brokerage":         _extract_brokerage(title),
            "action":            _extract_action(title),
            "stocks_mentioned":  _extract_stocks(title),
            "snippet":           "",  # filled by fetch_article on demand
            "source":            "Economic Times",
            "fetched_at":        time.strftime("%Y-%m-%d %H:%M IST"),
        })

    _write_cache(cache_key, {"recos": recos, "fetched_at": time.time()})
    return recos[:limit]


def fetch_news_for_stock(symbol: str, limit: int = 20) -> List[Dict]:
    """Per-stock news from ET. Combines:
       (a) Recos that mention the symbol or its company name
       (b) Topic page articles for the symbol
    """
    sym_clean = symbol.upper().replace(".NS", "").replace(".BO", "").strip()
    if not sym_clean:
        return []

    out: List[Dict] = []

    # (a) Filter Recos
    all_recos = fetch_recos(limit=200)
    for r in all_recos:
        title_blob = (r.get("title") or "") + " " + " ".join(r.get("stocks_mentioned") or [])
        # match by uppercase ticker mention OR by clean stock-name fragment
        if (re.search(r"\b" + re.escape(sym_clean) + r"\b", title_blob.upper())
            or any(sym_clean in s.upper() for s in r.get("stocks_mentioned", []))):
            out.append({
                "title":     r["title"],
                "url":       r["url"],
                "source":    "ET Recos",
                "published": r.get("fetched_at", ""),
                "snippet":   f"{r.get('brokerage') or 'Brokerage'} → {r.get('action')}",
                "kind":      "reco",
            })

    # (b) Topic page (heuristic URL — may 404 for some symbols)
    topic_url = f"{ET_BASE}/topic/{sym_clean.lower()}"
    try:
        sess = get_session("et")
        resp = sess.get(topic_url, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.select("a[href]"):
                href = a["href"]
                # ET article URLs contain "/articleshow/" or end in ".cms"
                if not ("/articleshow/" in href or href.endswith(".cms")):
                    continue
                full_url = href if href.startswith("http") else ET_BASE + href
                title = re.sub(r"\s+", " ", a.get_text()).strip()
                if not title or len(title) < 20:
                    continue
                out.append({
                    "title":     title,
                    "url":       full_url,
                    "source":    "ET",
                    "published": "",
                    "snippet":   "",
                    "kind":      "news",
                })
                if len(out) >= limit + 10:
                    break
    except Exception as e:
        logger.debug("ET topic fetch failed for %s: %s", sym_clean, e)

    # Dedupe by URL, return up to `limit`
    seen: Set[str] = set()
    deduped = []
    for r in out:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        deduped.append(r)
    return deduped[:limit]


def fetch_article(url: str, force: bool = False) -> Dict:
    """Fetch single ET article. Returns {title, body, url, fetched_at, paywalled}."""
    safe_name = re.sub(r"[^A-Za-z0-9]+", "_", url)[:120]
    cache_key = f"et_article_{safe_name}.json"
    if not force:
        cached = _read_cache(cache_key, ttl_seconds=24 * 60 * 60)  # 24h
        if cached:
            return cached

    out = {"url": url, "title": "", "body": "", "fetched_at": "",
           "paywalled": False, "error": None}

    try:
        sess = get_session("et")
        resp = sess.get(url, timeout=20)
        out["fetched_at"] = time.strftime("%Y-%m-%d %H:%M IST")
        body_html = resp.text
        out["paywalled"] = (
            SITES["et"]["paywall_signal"].lower() in body_html.lower()
            and "subscribe to et prime" in body_html.lower()
        )
        soup = BeautifulSoup(body_html, "lxml")
        title_tag = soup.find("h1") or soup.find("title")
        if title_tag:
            out["title"] = re.sub(r"\s+", " ", title_tag.get_text()).strip()
        # Article body — try multiple selector candidates
        body_node = (
            soup.select_one("div.artText")
            or soup.select_one("div.article-text")
            or soup.select_one("div[itemprop='articleBody']")
            or soup.select_one("article")
        )
        if body_node:
            out["body"] = re.sub(r"\s+", " ", body_node.get_text(" ", strip=True)).strip()
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"

    _write_cache(cache_key, out)
    return out


def health_check() -> Dict:
    """Quick session probe for UI rendering."""
    try:
        sess = get_session("et")
        resp = sess.get(RECOS_URL, timeout=15)
        return {
            "ok":       resp.status_code == 200,
            "status":   resp.status_code,
            "recos_html_size": len(resp.text or ""),
            "error":    None,
        }
    except FileNotFoundError as e:
        return {"ok": False, "status": None, "recos_html_size": 0,
                "error": f"Cookie file missing — run setup_paid_news_cookies.py"}
    except Exception as e:
        return {"ok": False, "status": None, "recos_html_size": 0,
                "error": f"{type(e).__name__}: {e}"}


__all__ = ["fetch_recos", "fetch_news_for_stock", "fetch_article", "health_check"]
