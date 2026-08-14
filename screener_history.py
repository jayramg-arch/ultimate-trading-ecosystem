"""Point-in-time fundamentals from screener.in's own history tables.

WHY (14 Aug 2026)
-----------------
`bff_as_of()` was built to score a historical anchor with the fundamentals that
were actually REPORTED then - scoring a 2024 anchor with today's screener.in
page leaks look-ahead into every row and makes the partition measure nothing.

The first attempt sourced it from yfinance and could not work: yfinance returns
only FIVE quarters (oldest 2025-03-31, with a gap), while the bull anchors run
2024-06 to 2025-11. Most anchors had neither the quarter nor its year-ago pair,
so every row came back INSUFFICIENT.

screener.in carries the history on the company page itself:
    #quarters  -> ~13 quarters: Sales, Net Profit, OPM %
    #ratios    -> ~12 annual years: ROCE %
That is ~3.25 years of quarterly data - enough for every anchor - and it
includes the OPM row, so the reconstruction is the FULL 5-check BFF rather
than the degraded 4-check version yfinance allowed.

It is also the right source by the project's own hierarchy: screener.in is
PRIMARY for Indian fundamentals.

HONESTY
-------
Returns None when the page cannot be read; never fabricates a quarter. A caller
that gets fewer than the periods it needs must report INSUFFICIENT rather than
scoring what it has - a missing fundamental must never look like a failing one.
"""
from __future__ import annotations

import logging
import os
import re
import sys
import time
from datetime import date

logger = logging.getLogger(__name__)

try:
    if (sys.stdout.encoding or "").lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_CACHE: dict = {}
CACHE_TTL_S = 24 * 3600          # quarterly data; a day is generous

_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


def _period_to_date(label: str):
    """'Jun 2026' -> date(2026, 6, 30). None if unparseable."""
    m = re.match(r"([A-Za-z]{3})\s+(\d{4})", (label or "").strip())
    if not m:
        return None
    mo = _MONTHS.get(m.group(1).title())
    if not mo:
        return None
    yr = int(m.group(2))
    # last day of that month is close enough — quarters are period-END labels
    nxt = date(yr + (mo == 12), 1 if mo == 12 else mo + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)


def _num(txt):
    """'57%' -> 57.0 · '1,234' -> 1234.0 · '' -> None · '-51' -> -51.0"""
    if txt is None:
        return None
    t = str(txt).strip().replace(",", "").replace("%", "").replace("₹", "")
    if t in ("", "-", "—"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _cookie() -> str:
    ck = os.getenv("SCREENER_COOKIE", "").strip("'\"")
    if not ck:
        try:
            from dotenv import load_dotenv
            load_dotenv(override=False)
            ck = os.getenv("SCREENER_COOKIE", "").strip("'\"")
        except Exception:
            pass
    return ck


def _section_rows(soup, section_id: str):
    """(periods, {row_label_lower: [values]}) for a company-page table section."""
    sec = soup.find("section", id=section_id)
    if not sec:
        return [], {}
    tbl = sec.find("table")
    if not tbl:
        return [], {}
    heads = [" ".join(th.text.split()) for th in tbl.select("thead th")]
    periods = [p for p in heads[1:]]          # first header cell is the row label
    out = {}
    for tr in tbl.select("tbody tr"):
        tds = [" ".join(td.text.split()) for td in tr.select("td")]
        if len(tds) < 2:
            continue
        label = tds[0].replace("+", "").strip().lower()
        out[label] = tds[1:]
    return periods, out


def fetch_history(symbol: str, ttl: int = CACHE_TTL_S):
    """Quarterly + annual history for one symbol, or None if unreadable.

    {
      "quarters": [ {"end": date, "sales": float|None,
                     "net_profit": float|None, "opm": float|None}, ... ]  # oldest→newest
      "roce_by_year": { 2026: 40.0, 2025: 47.0, ... }
    }
    """
    import requests
    from bs4 import BeautifulSoup

    key = symbol.strip().upper()
    hit = _CACHE.get(key)
    if hit and time.time() < hit["expires"]:
        return hit["data"]

    clean = key
    for suf in (".NS", ".BO", ".NSE", "-EQ"):
        if clean.endswith(suf):
            clean = clean[: -len(suf)]
            break

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    ck = _cookie()
    if ck:
        headers["Cookie"] = ck
    try:
        r = requests.get(f"https://www.screener.in/company/{clean}/",
                         headers=headers, timeout=20)
        if r.status_code != 200:
            return None
    except Exception as e:
        logger.warning("screener history %s: %s", symbol, e)
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    qp, qrows = _section_rows(soup, "quarters")
    if not qp:
        return None

    def _row(rows, *names):
        for n in names:
            for k in rows:
                if k.startswith(n):
                    return rows[k]
        return None

    sales = _row(qrows, "sales", "revenue")
    npf = _row(qrows, "net profit")
    opm = _row(qrows, "opm")

    quarters = []
    for i, label in enumerate(qp):
        d = _period_to_date(label)
        if not d:
            continue
        def _at(row):
            return _num(row[i]) if row and i < len(row) else None
        quarters.append({"end": d, "sales": _at(sales),
                         "net_profit": _at(npf), "opm": _at(opm)})
    quarters.sort(key=lambda q: q["end"])

    rp, rrows = _section_rows(soup, "ratios")
    roce_row = _row(rrows, "roce")
    roce_by_year = {}
    for i, label in enumerate(rp):
        d = _period_to_date(label)
        v = _num(roce_row[i]) if roce_row and i < len(roce_row) else None
        if d and v is not None:
            roce_by_year[d.year] = v

    data = {"quarters": quarters, "roce_by_year": roce_by_year}
    _CACHE[key] = {"data": data, "expires": time.time() + ttl}
    return data


def as_of(symbol: str, anchor):
    """The reported picture as of `anchor` (date or 'YYYY-MM-DD'), or None.

    Uses the latest quarter ENDING ON OR BEFORE the anchor, and compares it to
    the quarter four back (YoY) and one back (sequential margin). Returns None
    when the history does not reach far enough — the caller reports INSUFFICIENT
    rather than scoring a partial picture.
    """
    if isinstance(anchor, str):
        try:
            y, m, d = (int(x) for x in anchor[:10].split("-"))
            anchor = date(y, m, d)
        except Exception:
            return None

    h = fetch_history(symbol)
    if not h or not h.get("quarters"):
        return None

    qs = [q for q in h["quarters"] if q["end"] <= anchor]
    if not qs:
        return None
    i = len(qs) - 1
    cur = qs[i]
    prev = qs[i - 1] if i >= 1 else None
    yoy = qs[i - 4] if i >= 4 else None

    def _growth(now, before):
        if now is None or before is None or before == 0:
            return None
        return (now - before) / abs(before) * 100.0

    # ROCE for the financial year in force at the anchor. screener labels Indian
    # FYs by their March end, so an anchor in Aug-2025 sits in FY Mar-2026, which
    # was NOT yet reported — use the latest year ENDING on or before the anchor.
    roce = None
    for yr in sorted(h["roce_by_year"], reverse=True):
        if date(yr, 3, 31) <= anchor:
            roce = h["roce_by_year"][yr]
            break

    return {
        "quarter_end": cur["end"].isoformat(),
        "profit_growth_pct": _growth(cur["net_profit"], yoy["net_profit"] if yoy else None),
        "sales_growth_pct": _growth(cur["sales"], yoy["sales"] if yoy else None),
        "opm_now": cur["opm"],
        "opm_prev": prev["opm"] if prev else None,
        "net_profit": cur["net_profit"],
        "roce_pct": roce,
        "n_quarters": len(qs),
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol")
    ap.add_argument("--anchor", default=None)
    a = ap.parse_args()
    if a.anchor:
        print(as_of(a.symbol, a.anchor))
    else:
        h = fetch_history(a.symbol) or {}
        qs = h.get("quarters", [])
        print(f"  {len(qs)} quarters {qs[0]['end'] if qs else '-'} → {qs[-1]['end'] if qs else '-'}")
        for q in qs[-4:]:
            print("   ", q)
        print("  ROCE by year:", h.get("roce_by_year"))
