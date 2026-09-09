"""
mc_scraper.py — Moneycontrol scraper for analyst recos + per-stock news.

Mirrors et_scraper.py shape so analyst_sentiment.py can call them uniformly.

Public API
----------
    fetch_news_listing(limit=50, force=False) -> list[dict]
        Pulls the Stocks news listing page, returns headline list.

    fetch_news_for_stock(symbol, limit=20) -> list[dict]
        Filters the news listing + tries the per-stock URL.

    fetch_article(url, force=False) -> dict
        Fetches a single MC article body.

    health_check() -> dict
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

MC_BASE = "https://www.moneycontrol.com"
NEWS_LISTING_URL = f"{MC_BASE}/news/business/stocks/"

# Same action mapping as et_scraper for consistency. STRONG_BUY/STRONG_SELL
# are checked FIRST so "strong buy" doesn't get bucketed as plain BUY.
ACTION_BUCKETS = {
    "STRONG_BUY":  ["strong buy", "high conviction buy", "top pick", "best idea",
                     "best ideas", "aggressive buy", "screaming buy",
                     "outperform with high conviction", "high-conviction buy",
                     "conviction buy", "strong outperform"],
    "STRONG_SELL": ["strong sell", "strong underweight", "high conviction sell",
                     "strong underperform"],
    "BUY":         ["buy", "outperform", "overweight", "accumulate", "add",
                     "raise target", "raises target", "hike target", "hikes target",
                     "upgrades to buy", "remains bullish", "stays bullish",
                     "bullish", "initiates with buy", "target raised"],
    "HOLD":        ["hold", "neutral", "equal weight", "equal-weight",
                     "market perform", "remains neutral"],
    "SELL":        ["sell", "underweight", "underperform", "reduce", "exit",
                     "downgrade to sell", "cuts target", "cut target", "target cut"],
}

# Reuse known-brokerage list (same set covers ET + MC)
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
        logger.debug("cache write failed: %s", e)


def _extract_brokerage(text: str) -> Optional[str]:
    for b in KNOWN_BROKERAGES:
        if re.search(r"\b" + re.escape(b) + r"\b", text, re.I):
            return b
    return None


def _extract_action(text: str) -> str:
    t = text.lower()
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
    """Pull capitalized stock names from a headline (same heuristic as ET)."""
    candidates = set()
    for m in re.finditer(
        r"\b(?:on|for|in|to)\s+([A-Z][A-Za-z0-9& ]{2,40}?)(?:[,;.\)]|\s+(?:and|maintains|raises|cuts|hikes|recommends|upgrades|downgrades|target|after|while|with|but)|\Z)",
        text
    ):
        s = m.group(1).strip()
        if s and not re.match(r"^(?:the|its|their|after|while|despite)$", s, re.I):
            candidates.add(s)
    return sorted(candidates)


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

def fetch_news_listing(limit: int = 50, force: bool = False) -> List[Dict]:
    """Fetch the MC stocks news listing page."""
    cache_key = "mc_news_listing.json"
    if not force:
        cached = _read_cache(cache_key, ttl_seconds=60 * 60)  # 1h
        if cached and "items" in cached:
            return cached["items"][:limit]

    try:
        sess = get_session("mc")
        resp = sess.get(NEWS_LISTING_URL, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("MC fetch_news_listing failed: %s", e)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    items: List[Dict] = []
    seen: Set[str] = set()

    # MC news anchors typically live in <li class="clearfix"> blocks under news listing.
    # Defensive: any anchor whose href looks like a news article URL.
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # MC article URLs look like: /news/business/stocks/{slug}-{id}.html
        if not re.search(r"/news/.+\d+\.html$", href):
            continue
        full_url = href if href.startswith("http") else MC_BASE + href
        if full_url in seen:
            continue
        seen.add(full_url)

        title = re.sub(r"\s+", " ", a.get_text()).strip()
        if not title or len(title) < 15:
            continue

        items.append({
            "title":             title,
            "url":               full_url,
            "brokerage":         _extract_brokerage(title),
            "action":            _extract_action(title),
            "stocks_mentioned":  _extract_stocks(title),
            "snippet":           "",
            "source":            "Moneycontrol",
            "fetched_at":        time.strftime("%Y-%m-%d %H:%M IST"),
        })

    _write_cache(cache_key, {"items": items, "fetched_at": time.time()})
    return items[:limit]


def fetch_news_for_stock(symbol: str, limit: int = 20) -> List[Dict]:
    """Per-stock news from MC. Filters the news listing for stock mentions."""
    sym_clean = symbol.upper().replace(".NS", "").replace(".BO", "").strip()
    if not sym_clean:
        return []

    out: List[Dict] = []
    items = fetch_news_listing(limit=200)
    for r in items:
        title_blob = (r.get("title") or "") + " " + " ".join(r.get("stocks_mentioned") or [])
        if (re.search(r"\b" + re.escape(sym_clean) + r"\b", title_blob.upper())
            or any(sym_clean in s.upper() for s in r.get("stocks_mentioned", []))):
            out.append({
                "title":     r["title"],
                "url":       r["url"],
                "source":    "Moneycontrol",
                "published": r.get("fetched_at", ""),
                "snippet":   (f"{r.get('brokerage')} → {r.get('action')}"
                              if r.get("brokerage") else ""),
                "kind":      "news",
            })

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
    """Fetch single MC article. Returns {title, body, url, fetched_at, paywalled}."""
    safe_name = re.sub(r"[^A-Za-z0-9]+", "_", url)[:120]
    cache_key = f"mc_article_{safe_name}.json"
    if not force:
        cached = _read_cache(cache_key, ttl_seconds=24 * 60 * 60)
        if cached:
            return cached

    out = {"url": url, "title": "", "body": "", "fetched_at": "",
           "paywalled": False, "error": None}
    try:
        sess = get_session("mc")
        resp = sess.get(url, timeout=20)
        out["fetched_at"] = time.strftime("%Y-%m-%d %H:%M IST")
        body_html = resp.text
        out["paywalled"] = SITES["mc"]["paywall_signal"].lower() in body_html.lower()
        soup = BeautifulSoup(body_html, "lxml")
        title_tag = soup.find("h1") or soup.find("title")
        if title_tag:
            out["title"] = re.sub(r"\s+", " ", title_tag.get_text()).strip()
        body_node = (
            soup.select_one("div.content_wrapper")
            or soup.select_one("div.article_wrapper")
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
    try:
        sess = get_session("mc")
        resp = sess.get(NEWS_LISTING_URL, timeout=15)
        return {
            "ok":              resp.status_code == 200,
            "status":          resp.status_code,
            "html_size":       len(resp.text or ""),
            "error":           None,
        }
    except FileNotFoundError:
        return {"ok": False, "status": None, "html_size": 0,
                "error": "Cookie file missing — run setup_paid_news_cookies.py"}
    except Exception as e:
        return {"ok": False, "status": None, "html_size": 0,
                "error": f"{type(e).__name__}: {e}"}


__all__ = ["fetch_news_listing", "fetch_news_for_stock", "fetch_article", "health_check"]
