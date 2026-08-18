"""CORE UNIVERSE — the one size/governance floor every scanner must clear.

WHY THIS EXISTS (Jay, 13 Aug 2026)
----------------------------------
    "Today I noticed that a Microcap has slipped into my portfolio, due to these
     sporadic set of fundamental filters."

He is right, and docs/25 measured it. The Bull and Recovery books enforce
market cap > Rs 5,000 Cr, pledged % < 5 and a promoter/institutional holding
floor - because those conditions live inside his saved screener.in screens. The
Catalyst and Pullback books enforce none of them: they were built later, on
Python engines (RFF, BFF) that check growth and solvency but never size,
governance or ownership. A Rs 600 Cr promoter-pledged name is invisible to
those engines and passes.

THE DESIGN
----------
Rather than fetch three more fields per company (and pledged % is NOT on the
company page - it is a screener QUERY field only), submit ONE ad-hoc query to
screener.in and keep the resulting symbol set. Every category then asks the
same question: "is this name in the core universe?"

  * one network call per run instead of N
  * one definition of the floor, in one place, editable here
  * identical semantics across Bull / Recovery / Catalyst / Pullback, which is
    exactly what "sporadic" was describing

Ad-hoc queries need no saved screen: /screen/raw/?query=... accepts the same
syntax as the saved screens and the row hrefs carry NSE codes directly.

THE HONESTY RULE (the one that matters most here)
-------------------------------------------------
`eligible_symbols()` returns **None** on any failure - never an empty set. An
empty set passed to a membership gate blocks EVERY name in every book, which
would read as "the market has nothing to offer today" when the truth is an
expired cookie. Callers must treat None as "gate unavailable, do not gate" and
say so out loud. This is the same distinction bull_fundamental_filter draws
between WEAK (a judgement about the company) and INSUFFICIENT (a judgement
about our data).

Usage:
    import core_universe as cu
    ok = cu.eligible_symbols()          # set[str] | None
    if ok is not None and sym not in ok: ...   # reject
"""
from __future__ import annotations

import logging
import os
import sys
import time

logger = logging.getLogger(__name__)

try:
    if (sys.stdout.encoding or "").lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(_DIR, "data", "core_universe.txt")
CACHE_TTL_S = 20 * 3600          # a trading day; the underlying data is quarterly

# ── The floor. These are the Bull screens' OWN thresholds (docs/25 section 4),
#    applied everywhere rather than only where a saved screen happens to run. ──
CONFIG = {
    "mcap_min_cr":     5000,     # Bull + Recovery screens all use > 5000
    # PRICE. Added 13 Aug 2026 after an audit found it enforced in only two of
    # five producers: pullback_finder and the catalyst had Rs 100, while the GM
    # workflow, the matcher and this query had NO floor at all. The Chartink bull
    # scans use Rs 20 and the Early Birds screener.in screen only Rs 50, so a
    # sub-100 name could reach the board through that pair. Putting it HERE fixes
    # every surface at once, which is the whole reason this module exists.
    "price_min":        100,     # Recovery screens' floor, now applied everywhere
    "pledge_max_pct":     5,     # Bull screens use < 5 (Leaders < 2)
    "promoter_min_pct":  40,     # promoter > 40 OR institutional conviction below
    "fii_min_pct":       15,
    "dii_min_pct":       15,
}


def build_query(cfg=None) -> str:
    c = dict(CONFIG, **(cfg or {}))
    return (f"Market Capitalization > {c['mcap_min_cr']} AND "
            f"Current Price > {c['price_min']} AND "
            f"Pledged percentage < {c['pledge_max_pct']} AND "
            f"(Promoter holding > {c['promoter_min_pct']} OR "
            f"FII holding > {c['fii_min_pct']} OR "
            f"DII holding > {c['dii_min_pct']})")


def _load_cookie() -> str:
    """Read SCREENER_COOKIE, loading .env if nobody has yet.

    Modules run standalone (`python pullback_finder.py`) do NOT load .env, so
    the paid session was silently absent and screener.in was being scraped
    anonymously - which is the likeliest cause of the INSUFFICIENT bursts the
    BFF retry wrapper was built to absorb.
    """
    ck = os.getenv("SCREENER_COOKIE", "").strip("'\"")
    if not ck:
        try:
            from dotenv import load_dotenv
            load_dotenv(override=False)
            ck = os.getenv("SCREENER_COOKIE", "").strip("'\"")
        except Exception:
            pass
    return ck


def _read_cache():
    try:
        if not os.path.exists(CACHE_FILE):
            return None
        if time.time() - os.path.getmtime(CACHE_FILE) > CACHE_TTL_S:
            return None
        with open(CACHE_FILE, encoding="utf-8") as fh:
            syms = {ln.strip().upper() for ln in fh if ln.strip()}
        return syms or None
    except Exception:
        return None


def _write_cache(syms) -> None:
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        from io_utils import atomic_write_text
        atomic_write_text(CACHE_FILE, "\n".join(sorted(syms)))
    except Exception as e:
        logger.warning("core universe cache write failed: %s", e)


def fetch(cfg=None, max_pages: int = 30):
    """Every symbol passing the core floor, or None if screener.in cannot answer."""
    import requests
    from bs4 import BeautifulSoup

    q = build_query(cfg)
    h = {"User-Agent": "Mozilla/5.0"}
    ck = _load_cookie()
    if ck:
        h["Cookie"] = ck

    import screener_breaker as _brk
    if not _brk.allow():
        logger.warning("core universe: screener.in breaker %s - UNAVAILABLE (no gate)",
                       _brk.state())
        return None

    out, page = set(), 1
    while page <= max_pages:
        try:
            with _brk.gate():
                r = requests.get("https://www.screener.in/screen/raw/", headers=h,
                                 params={"query": q, "page": page}, timeout=30)
            _brk.record_ok()
            if r.status_code != 200:
                logger.warning("core universe: HTTP %s on page %s", r.status_code, page)
                break
            s = BeautifulSoup(r.text, "html.parser")
            codes = [a["href"].split("/")[2].upper()
                     for a in s.select('table.data-table tbody tr a[href^="/company/"]')]
        except Exception as e:
            _brk.record_fail(e)
            logger.warning("core universe: page %s failed (%s)", page, e)
            break
        if not codes:
            break
        before = len(out)
        out.update(codes)
        if len(out) == before:          # a repeated page = pagination ended
            break
        page += 1
        time.sleep(0.4)

    # A partial fetch is worse than none: it would reject real names as
    # ineligible. Demand a plausible floor before trusting the answer.
    if len(out) < 100:
        logger.warning("core universe: only %d symbols — treating as UNAVAILABLE", len(out))
        return None
    # ONLY the default thresholds may write the shared cache. A parameter sweep
    # (fetch({"mcap_min_cr": 20000}) while sizing the floor) previously wrote its
    # 200-name result to the same file, and the next auto-pilot read that as the
    # production universe - the pullback phase gated against a Rs 20,000 Cr floor
    # and rejected 32 names including BAJFINANCE and CCL. A cache keyed to
    # nothing is a cache that lies about what it holds.
    if not cfg:
        _write_cache(out)
    return out


def eligible_symbols(cfg=None, force: bool = False):
    """set[str] of eligible NSE codes, or None if the gate cannot be evaluated.

    None means DO NOT GATE. Never substitute an empty set."""
    if not force:
        c = _read_cache()
        if c:
            return c
    return fetch(cfg)


def gate(symbol: str, eligible) -> bool:
    """True = keep. An unavailable gate (None) keeps everything, loudly upstream."""
    if eligible is None:
        return True
    return str(symbol).replace(".NS", "").strip().upper() in eligible


def describe(cfg=None) -> str:
    c = dict(CONFIG, **(cfg or {}))
    return (f"mcap > Rs {c['mcap_min_cr']:,} Cr · price > Rs {c['price_min']} · "
            f"pledge < {c['pledge_max_pct']}% · "
            f"promoter > {c['promoter_min_pct']}% or FII > {c['fii_min_pct']}% "
            f"or DII > {c['dii_min_pct']}%")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--check", nargs="*", help="symbols to test against the gate")
    a = ap.parse_args()
    print("  CORE UNIVERSE —", describe())
    e = eligible_symbols(force=a.force)
    if e is None:
        print("  ⛔ UNAVAILABLE — screener.in did not answer. Gate would be SKIPPED.")
        raise SystemExit(1)
    print(f"  {len(e)} eligible symbols  →  {CACHE_FILE}")
    for s in (a.check or []):
        print(f"    {s:<14}{'PASS' if gate(s, e) else 'REJECT — below the core floor'}")
