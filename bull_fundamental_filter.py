# bull_fundamental_filter.py — Bull Fundamental Filter (BFF)  v1.0  (10 Jul 2026)
#
# The Minervini fundamental leg for the BULL path of the Golden Matcher.
#
# WHY THIS EXISTS
# ---------------
# The Recovery path has RFF (a HARD fundamental gate) because it buys names whose
# TAPE looks bad — you can't trust price there, so fundamentals separate "quality
# on sale" from a falling knife. The Bull path buys confirmed Stage-2 / high-RS
# leaders where the market has ALREADY voted, so RS/Stage-2 is an implicit
# fundamental proxy and no hard gate is needed. BUT RS can lead a name whose
# earnings are rotting (a momentum pump / sympathy move), and Minervini's own
# method (SEPA) pairs the breakout with EARNINGS + SALES acceleration. BFF surfaces
# that leg so a leader with weak fundamentals shows WEAK — as STATUS Jay eyeballs,
# NOT a blocker (per the catalyst-gate philosophy: structure fires, quality is
# status). See CLAUDE.md "path symmetry doctrine": symmetric in FORM (both paths
# now show a fundamental badge at QUALITY), asymmetric in SUBSTANCE (bull soft,
# recovery hard).
#
# DATA SOURCE
# -----------
# screener.in (PRIMARY for Indian fundamentals — cleaner than yfinance) via the
# existing fundamental_hub.fetch_screener_rff_row(). ONE cached (24h) call gives
# every field BFF needs; no new fetcher, no new cookie handling. Pine cannot
# compute this (5-call request.financial ceiling) → BFF is Python-only, like RFF.
#
# HONESTY LAYER
# -------------
# No NaN->0. If fewer than MIN_FIELDS of the checks have data, quality =
# INSUFFICIENT and score is reported as None (not 0) — a missing fundamental must
# never masquerade as a failing one (the critique's "silent fallbacks bias every
# signal upward" rule).
#
# Usage:
#   from bull_fundamental_filter import compute_bff
#   bff = compute_bff("SUMICHEM")   # NSE symbol, with or without .NS
#   -> {"score": 4, "max": 5, "quality": "STRONG", "checks": {...},
#       "drivers": ["Profit +32%", ...], "as_of": "...", "source": "screener.in"}

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ==========================================================================
# CONFIG — growth/quality thresholds (Minervini-tilted). Tunable in one place.
# ==========================================================================
CONFIG = {
    "profit_growth_min_pct": 20.0,   # YoY quarterly profit growth (EPS proxy)
    "sales_growth_min_pct":  15.0,   # YoY quarterly sales growth (top-line backing)
    "roce_min_pct":          15.0,   # return quality (ROCE from screener top-ratios)
    # margin_expansion: OPM_Now > OPM_Prev  (operating leverage) — no numeric knob
    # profitable:       Net profit > 0
    # --- financials (banks/NBFCs): OPM doesn't exist & ROCE>=15 is the wrong bar
    #     (lenders run low ROCE/ROA). Mirrors recovery_screener.get_rff's fin-adj:
    #     drop margin_expansion, use a lender-appropriate return threshold. ---
    "fin_roce_min_pct":      10.0,   # lender ROCE bar (RFF uses ROCE>10)
    "fin_roe_min_pct":       12.0,   # lender ROE bar (screener shows ROE for banks)
    "min_fields":            3,       # data-sufficiency floor (else INSUFFICIENT)
    "strong_min":            4,       # score >= -> STRONG
    "ok_min":                2,       # score >= -> OK   (else WEAK)
}


def _num(v) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


# module-level 24h cache so a symbol's screener.in page is fetched once
_bff_cache: dict = {}


def _fetch_screener_bff_row(symbol: str, ttl: int = 86400) -> Optional[dict]:
    """Self-contained screener.in company-page parse for the BFF growth leg.

    Pulls the fields BFF needs in ONE cached page fetch (independent of the RFF
    row so recovery is untouched):
        Profit growth TTM   <- 'Compounded Profit Growth' ranges table, TTM row
        Sales growth TTM    <- 'Compounded Sales Growth'  ranges table, TTM row
        OPM_Now / OPM_Prev  <- P&L 'OPM %' row, last two annual columns
        Net profit          <- P&L 'Net Profit' row, last column
        ROCE / ROE          <- top-ratios card
    Same cookie/session convention as fundamental_hub. Returns None when the page
    yields nothing (honesty: caller reports INSUFFICIENT, never zero-fills).
    """
    import time
    key = symbol.upper()
    now = time.time()
    hit = _bff_cache.get(key)
    if hit and now < hit["expires"]:
        return hit["data"]

    import os
    import requests
    from bs4 import BeautifulSoup

    clean = symbol.strip().upper()
    for suf in (".NS", ".BO", ".NSE", "-EQ"):
        if clean.endswith(suf):
            clean = clean[:-len(suf)]
            break
    url = f"https://www.screener.in/company/{clean}/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    cookie = os.getenv("SCREENER_COOKIE", "")
    if cookie:
        headers["Cookie"] = cookie
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
    except Exception:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    out: dict = {}

    def _f(txt):
        try:
            return float(txt.strip().replace(",", "").replace("%", ""))
        except Exception:
            return None

    # --- Compounded Sales/Profit Growth ranges tables (TTM row = latest momentum)
    def _ranges_ttm(label: str):
        for tbl in soup.find_all("table", class_="ranges-table"):
            head = tbl.find("th")
            if head and label in head.text.strip().lower():
                for tr in tbl.find_all("tr"):
                    tds = tr.find_all("td")
                    if len(tds) >= 2 and "ttm" in tds[0].text.strip().lower():
                        return _f(tds[-1].text)
                # no TTM row -> fall back to the shortest available (3 Years)
                rows = [tr.find_all("td") for tr in tbl.find_all("tr")]
                for want in ("1 year", "3 year", "5 year"):
                    for tds in rows:
                        if len(tds) >= 2 and want in tds[0].text.strip().lower():
                            return _f(tds[-1].text)
        return None

    pg = _ranges_ttm("compounded profit growth")
    if pg is not None:
        out["profit_growth"] = pg
    sg = _ranges_ttm("compounded sales growth")
    if sg is not None:
        out["sales_growth"] = sg

    # --- P&L section: OPM (last two annual cols) + Net Profit (last col) ---
    def _row_vals(section_id: str, contains: str):
        sec = soup.find("section", id=section_id)
        if not sec:
            return None, None
        table = sec.find("table")
        if not table:
            return None, None
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if cells and contains in cells[0].text.strip().lower():
                last = _f(cells[-1].text) if len(cells) >= 2 else None
                prev = _f(cells[-2].text) if len(cells) >= 3 else None
                return last, prev
        return None, None

    opm_now, opm_prev = _row_vals("profit-loss", "opm")
    if opm_now is not None:
        out["OPM_Now"] = opm_now
    if opm_prev is not None:
        out["OPM_Prev"] = opm_prev
    ni, _ = _row_vals("profit-loss", "net profit")
    if ni is not None:
        out["Net profit"] = ni

    # --- top-ratios card: ROCE / ROE ---
    top = soup.find(id="top-ratios")
    if top:
        for li in top.find_all("li"):
            nm = li.find("span", class_="name")
            val = li.find("span", class_="number")
            if nm and val:
                k = nm.text.strip().replace(":", "")
                if k == "ROCE":
                    out["ROCE"] = _f(val.text)
                elif k == "ROE":
                    out["ROE"] = _f(val.text)

    data = out or None
    _bff_cache[key] = {"data": data, "expires": now + ttl}
    return data


def compute_bff(symbol: str, ttl: int = 86400) -> dict:
    """Bull Fundamental Filter for one NSE symbol.

    Returns a dict:
        score    : int 0-5, or None if INSUFFICIENT data (honesty layer)
        max      : 5
        quality  : "STRONG" | "OK" | "WEAK" | "INSUFFICIENT"
        checks   : {name: True|False|None}  (None = no data for that check)
        drivers  : list[str] short human labels of what fired / dragged
        n_data   : how many of the 5 checks had data
        source   : "screener.in" | "none"
        as_of    : IST timestamp of the underlying fetch, if available
    """
    sym = (symbol or "").strip().upper()
    result = {
        "symbol": sym, "score": None, "max": 5, "quality": "INSUFFICIENT",
        "checks": {}, "drivers": [], "n_data": 0, "source": "none", "as_of": None,
    }
    if not sym:
        return result

    # Data-provider rule: fundamentals = screener.in PRIMARY, yfinance FALLBACK.
    # Primary: the compounded-growth-table page parse.
    try:
        row = _fetch_screener_bff_row(sym, ttl=ttl)
    except Exception as exc:                       # network / cookie
        logger.warning("BFF: screener fetch failed for %s: %s", sym, exc)
        row = None

    # Fallback: when the primary parse yields nothing (or no growth fields — the
    # cause of the blank bull rows), fetch_stock_fundamentals gives screener.in-
    # first / yfinance-merged growth + return fields so BFF still reads.
    fb = None
    if (not row) or (row.get("profit_growth") is None and row.get("sales_growth") is None):
        try:
            from fundamental_hub import fetch_stock_fundamentals
            fb = fetch_stock_fundamentals(sym)
        except Exception as exc:
            logger.warning("BFF: fundamentals fallback failed for %s: %s", sym, exc)
            fb = None

    if not row and not fb:
        return result
    row = dict(row or {})
    result["source"] = "screener.in" if row.get("profit_growth") is not None else "screener/yf"
    if fb:
        # merge fallback ONLY where the primary row lacks the field (screener wins)
        if row.get("profit_growth") is None and fb.get("earnings_growth") is not None:
            row["profit_growth"] = fb["earnings_growth"]
        if row.get("sales_growth") is None and fb.get("revenue_growth") is not None:
            row["sales_growth"] = fb["revenue_growth"]
        if row.get("ROCE") is None and fb.get("roce") is not None:
            row["ROCE"] = fb["roce"]
        if row.get("ROE") is None and fb.get("roe") is not None:
            row["ROE"] = fb["roe"]
        if row.get("Net profit") is None and fb.get("net_income_ttm") is not None:
            row["Net profit"] = fb["net_income_ttm"]
        # OPM expansion needs two periods → not derivable from the info snapshot;
        # margin_expansion stays None in the fallback path (honestly blank).

    profit_g = _num(row.get("profit_growth"))
    sales_g  = _num(row.get("sales_growth"))
    opm_now  = _num(row.get("OPM_Now"))
    opm_prev = _num(row.get("OPM_Prev"))
    roce     = _num(row.get("ROCE"))
    roe      = _num(row.get("ROE"))
    ni       = _num(row.get("Net profit"))

    # Sector-aware branch — mirrors recovery_screener.get_rff's financials
    # re-score (SAME sector detection → zero drift). Banks/NBFCs: OPM doesn't
    # exist and the industrial ROCE>=15 bar is wrong, so drop margin_expansion
    # and use a lender-appropriate return check (ROCE>10 OR ROE>12).
    is_fin = False
    try:
        import sector_lookup as _sl
        _sidx = (_sl.get_sector_index(sym) or "").upper()
        is_fin = ("BANKNIFTY" in _sidx) or ("FINANCE" in _sidx) or ("FINSERV" in _sidx)
    except Exception:
        is_fin = False
    result["is_financial"] = is_fin

    checks: dict = {}
    drivers: list = []

    # 1. Profit growth (both sectors) — EPS acceleration proxy
    if profit_g is None:
        checks["profit_growth"] = None
    else:
        checks["profit_growth"] = profit_g >= CONFIG["profit_growth_min_pct"]
        drivers.append(f"Profit {profit_g:+.0f}%")

    # 2. Sales growth (both sectors) — top-line backing the move
    if sales_g is None:
        checks["sales_growth"] = None
    else:
        checks["sales_growth"] = sales_g >= CONFIG["sales_growth_min_pct"]
        drivers.append(f"Sales {sales_g:+.0f}%")

    if is_fin:
        # 3f. Lender-appropriate return: ROCE>10 OR ROE>12 (margin_expansion is
        #     NOT scored for lenders — no OPM line on a bank/NBFC P&L).
        if roce is None and roe is None:
            checks["return_quality"] = None
        else:
            checks["return_quality"] = (
                (roce is not None and roce > CONFIG["fin_roce_min_pct"]) or
                (roe is not None and roe > CONFIG["fin_roe_min_pct"]))
            drivers.append(f"ROCE {roce:.0f}%" if roce is not None else f"ROE {roe:.0f}%")
        # 4f. Profitable
        if ni is None:
            checks["profitable"] = None
        else:
            checks["profitable"] = ni > 0
            drivers.append("NP+" if ni > 0 else "NP<0")
        _defined = 4                         # profit, sales, return, profitable
    else:
        # 3. Margin expansion (industrial operating leverage) — needs both OPM cols
        if opm_now is None or opm_prev is None:
            checks["margin_expansion"] = None
        else:
            checks["margin_expansion"] = opm_now > opm_prev
            drivers.append(f"OPM {opm_prev:.0f}->{opm_now:.0f}%")
        # 4. Return quality (ROCE>=15; ROE fallback)
        rq = roce if roce is not None else roe
        if rq is None:
            checks["return_quality"] = None
        else:
            checks["return_quality"] = rq >= CONFIG["roce_min_pct"]
            drivers.append(f"ROCE {rq:.0f}%" if roce is not None else f"ROE {rq:.0f}%")
        # 5. Profitable (a real leader should be earning)
        if ni is None:
            checks["profitable"] = None
        else:
            checks["profitable"] = ni > 0
            drivers.append("NP+" if ni > 0 else "NP<0")
        _defined = 5                         # + margin_expansion

    result["checks"] = checks

    n_data = sum(1 for v in checks.values() if v is not None)
    result["n_data"] = n_data
    if n_data < CONFIG["min_fields"]:
        # Honesty layer: too little data to judge — do NOT score 0.
        result["quality"] = "INSUFFICIENT"
        result["score"] = None
        result["drivers"] = drivers
        return result

    passed = sum(1 for v in checks.values() if v is True)
    # scale to the 0-5 display range (financials have 4 defined checks, not 5).
    score = int(round(5 * passed / _defined))
    result["score"] = score
    result["drivers"] = drivers
    if score >= CONFIG["strong_min"]:
        result["quality"] = "STRONG"
    elif score >= CONFIG["ok_min"]:
        result["quality"] = "OK"
    else:
        result["quality"] = "WEAK"

    result["as_of"] = row.get("as_of") or row.get("As_Of")
    return result


def bff_badge(bff: dict) -> str:
    """Compact one-line badge for the GM QUALITY step, e.g.
    'BFF STRONG 4/5 · Profit +32% · Sales +18% · OPM 19->22% · ROCE 21%'."""
    if not bff or bff.get("source") == "none":
        return "BFF —  (no screener data)"
    q = bff.get("quality", "INSUFFICIENT")
    if q == "INSUFFICIENT":
        return f"BFF INSUFFICIENT ({bff.get('n_data', 0)}/5 fields)"
    sc = bff.get("score")
    drv = " · ".join(bff.get("drivers", [])[:4])
    return f"BFF {q} {sc}/{bff.get('max', 5)}" + (f" · {drv}" if drv else "")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s — %(message)s")
    syms = sys.argv[1:] or ["SUMICHEM", "RELIANCE", "GRANULES"]
    for s in syms:
        b = compute_bff(s)
        print(f"\n{s}")
        print("  " + bff_badge(b))
        print(f"  checks: {b['checks']}")
