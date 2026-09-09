# -*- coding: utf-8 -*-
"""Bulk RFF fundamentals from screener.in's SCREEN endpoint (29-Aug-2026).

WHY THIS EXISTS
---------------
RFF needs six Tier-A fields. Screener.in's COMPANY PAGE can supply five of them
(NI and OCF directly; ICR from Operating Profit / Interest; ROA from Net profit /
Total Assets; D/E from the balance sheet) but NOT `Current ratio` -- its balance
sheet reports Equity Capital / Reserves / Borrowings / Other Liabilities / Total
Liabilities / Fixed Assets / CWIP / Investments / Other Assets / Total Assets, with
no current-vs-non-current split, so CA/CL cannot be formed.

That single missing field capped a live-path name at 5 of 6. Combined with
`rff_min_score` going 4 -> 5 on 13-Aug-2026 (commit d43764f) it capped them at 4 of 6
against a floor of 5, which is arithmetically unreachable: firing recovery names went
from 7-10 per run to 1-2 within two days and stayed there. Neither change was wrong
on its own, which is why it took a fortnight to notice.

THE FIX is not to fall back to yfinance -- Jay's standing rule is screener.in PRIMARY,
yfinance fallback only, and yfinance is where this class of failure came from
(info['currentRatio'] and info['interestExpense'] return None for EVERY symbol on
1.1.0, including RELIANCE, while the payload still looks healthy at ~160 keys).

Screener.in DOES publish Current ratio -- on the SCREEN endpoint rather than the
company page. Verified live: the account's DEFAULT COLUMN SET returns all six Tier-A
inputs for any query, so this does not depend on query phrasing:

    NP 12M Rs.Cr. | CF Operations Rs.Cr. | Int Coverage | Debt / Eq |
    Current ratio | ROA 12M %

One paginated sweep therefore replaces N per-symbol company-page fetches AND closes
the CR gap, from the primary source. This is the same endpoint core_universe already
uses, so it is a proven path, not a new dependency.

HONESTY
-------
A partial sweep is worse than none: it would silently mark real names as unscored and
push them back onto the thinner company-page path. Below MIN_ROWS the whole result is
discarded and None is returned, which callers must read as "pool unavailable, use the
existing path" -- never as "these names have no fundamentals".
"""
from __future__ import annotations

import json
import logging
import os
import time

logger = logging.getLogger(__name__)

_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(_DIR, "data", "screener_rff_pool.json")
CACHE_TTL_S = 24 * 3600

# Permissive by design: the pool is a LOOKUP TABLE, not a filter. Every eligibility
# decision belongs to core_universe / the screeners, so anything that narrowed this
# query would silently narrow their input too.
QUERY = "Market Capitalization > 500"
MAX_PAGES = 40          # 50 rows/page -> ~2,000 names, comfortably past nifty500
MIN_ROWS = 300          # below this the sweep is treated as failed, not as data

# Screen header -> the canonical keys compute_rff._num already looks for. Mapping to
# the canonical name (rather than adding header aliases) keeps every RFF consumer on
# one vocabulary regardless of which screener.in surface the row came from.
COLMAP = {
    "NP 12M Rs.Cr.":        "Net profit",
    "CF Operations Rs.Cr.": "Cash from operating activity",
    "Int Coverage":         "Interest Coverage Ratio",
    "Debt / Eq":            "Debt to equity",
    "Current ratio":        "Current ratio",
    "ROA 12M %":            "Return on assets",
}


def _num(txt):
    try:
        t = str(txt).replace(",", "").replace("%", "").strip()
        return float(t) if t not in ("", "-", "nan") else None
    except Exception:
        return None


def _read_cache():
    try:
        if not os.path.exists(CACHE_FILE):
            return None
        if time.time() - os.path.getmtime(CACHE_FILE) > CACHE_TTL_S:
            return None
        with open(CACHE_FILE, encoding="utf-8") as fh:
            d = json.load(fh)
        return d or None
    except Exception:
        return None


def _write_cache(pool) -> None:
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        from io_utils import atomic_write_text
        atomic_write_text(CACHE_FILE, json.dumps(pool, indent=0, sort_keys=True))
    except Exception as e:
        logger.warning("screener_rff_pool: cache write failed: %s", e)


def fetch(max_pages: int = MAX_PAGES):
    """{SYMBOL: {canonical_key: float}} for the whole universe, or None if unusable."""
    import requests
    from bs4 import BeautifulSoup

    try:
        import core_universe as _cu
        cookie = _cu._load_cookie()
    except Exception:
        cookie = os.getenv("SCREENER_COOKIE", "").strip("'\"")
    headers = {"User-Agent": "Mozilla/5.0"}
    if cookie:
        headers["Cookie"] = cookie

    import screener_breaker as _brk
    if not _brk.allow():
        logger.warning("screener_rff_pool: breaker %s - pool UNAVAILABLE", _brk.state())
        return None

    pool: dict = {}
    page = 1
    while page <= max_pages:
        try:
            with _brk.gate():
                r = requests.get("https://www.screener.in/screen/raw/", headers=headers,
                                 params={"query": QUERY, "page": page}, timeout=30)
            if r.status_code != 200:
                logger.warning("screener_rff_pool: HTTP %s on page %s", r.status_code, page)
                break
            _brk.record_ok()
            soup = BeautifulSoup(r.text, "html.parser")
            table = soup.select_one("table.data-table")
            if table is None:
                break
            head_row = table.find("tr")
            heads = [c.get_text(" ", strip=True)
                     for c in head_row.find_all(["th", "td"])] if head_row else []
            # Index by HEADER NAME, never by position: the account's default column
            # set is what supplies these, and a column added in the screener.in UI
            # would shift every position silently.
            idx = {h: i for i, h in enumerate(heads)}
            wanted = {h: i for h, i in idx.items() if h in COLMAP}
            if not wanted:
                logger.warning("screener_rff_pool: none of the RFF columns present "
                               "(headers=%s) - default column set may have changed", heads)
                return None
            before = len(pool)
            for tr in table.select("tbody tr"):
                a = tr.select_one('a[href^="/company/"]')
                if not a:
                    continue
                sym = a["href"].split("/")[2].upper()
                cells = [td.get_text(" ", strip=True) for td in tr.select("td")]
                row = {}
                for h, i in wanted.items():
                    if i < len(cells):
                        v = _num(cells[i])
                        if v is not None:
                            row[COLMAP[h]] = v
                if row:
                    pool.setdefault(sym, row)
            if len(pool) == before:      # repeated/empty page = pagination ended
                break
        except Exception as e:
            _brk.record_fail(e)
            logger.warning("screener_rff_pool: page %s failed (%s)", page, e)
            break
        page += 1
        time.sleep(0.4)

    if len(pool) < MIN_ROWS:
        logger.warning("screener_rff_pool: only %d rows - treating as UNAVAILABLE "
                       "(a partial pool would mark real names unscored)", len(pool))
        return None
    _write_cache(pool)
    logger.info("screener_rff_pool: %d symbols cached", len(pool))
    return pool


def get_pool(force: bool = False):
    """Cached accessor. None means POOL UNAVAILABLE -> use the per-symbol path."""
    if not force:
        c = _read_cache()
        if c:
            return c
    return fetch()


def row_for(symbol: str):
    """The six Tier-A fields for one symbol, or None. Never raises."""
    try:
        pool = get_pool()
        if not pool:
            return None
        sym = str(symbol).replace(".NS", "").replace(".BO", "").strip().upper()
        r = pool.get(sym)
        return dict(r) if r else None
    except Exception as e:
        logger.warning("screener_rff_pool.row_for(%s) failed: %s", symbol, e)
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = fetch()
    print("pool:", len(p) if p else "UNAVAILABLE")
    if p:
        for s in ("RELIANCE", "ECLERX", "AEGISLOG", "TECHM", "HDFCBANK"):
            print("  %-10s %s" % (s, p.get(s)))
