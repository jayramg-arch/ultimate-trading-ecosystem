"""screener_history.py — point-in-time fundamentals from screener.in's history tables.

WHY (24-Sep-2026, audit AUD-EVD-01, docs/PREREG_rff_pit.md). The recovery backtest scored
every historical anchor with TODAY's fundamentals. yfinance cannot fix that: its quarterly
statements hold ~5 quarters and roll forward. A screener.in company page, though, carries
~12 quarterly results and 10+ years of annual P&L / balance sheet / cash flow — enough to
rebuild five of RFF's six checks AS OF any past date.

POINT-IN-TIME RULE: a period counts at date t only once it was PUBLISHED by t —
quarterly results at period end + 45 days, annual statements at period end + 60 days
(SEBI LODR deadlines; the March quarter rides with the annual at 60).

Same URL and the same row names the live fetcher (fundamental_hub.fetch_screener_rff_row)
uses, so the two read the same fields. Pages are cached to data/screener_pages/ so a run is
reproducible and the site is hit once per name. Known residual: screener shows figures as
last reported, so a later RESTATEMENT of an old period is visible here — minor, and stated.

CURRENT RATIO is not rebuildable: the page's balance sheet has no current/non-current split.
"""
from __future__ import annotations

import os
import re
from datetime import timedelta

import pandas as pd

_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(_DIR, "data", "screener_pages")
Q_LAG_DAYS = 45
A_LAG_DAYS = 60
ICR_MIN, DE_MAX, ROA_MIN = 3.5, 2.0, 5.0      # compute_rff Tier-A thresholds
MIN_CHECKS = 4

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _clean(sym: str) -> str:
    s = str(sym).strip().upper()
    for suf in (".NS", ".BO", ".NSE", "-EQ"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s


def fetch_page(symbol: str, refresh: bool = False) -> str | None:
    os.makedirs(CACHE, exist_ok=True)
    sym = _clean(symbol)
    path = os.path.join(CACHE, sym.replace("&", "_AND_") + ".html")
    if os.path.exists(path) and not refresh:
        return open(path, encoding="utf-8").read()
    import screener_breaker as brk
    # The PAID session (Jay: screener.in is the fundamentals source, subscription). A bare
    # shell does not load .env, and a logged-out page is a different, thinner page — so
    # load it here rather than trusting the caller's environment.
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(_DIR, ".env"))
    except Exception:
        pass
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    ck = os.getenv("SCREENER_COOKIE", "")
    if not ck:
        raise RuntimeError("SCREENER_COOKIE not set — refusing a logged-out fetch")
    if ck:
        headers["Cookie"] = ck
    html = brk.fetch_html(f"https://www.screener.in/company/{sym}/", headers, timeout=15, tag=sym)
    if html:
        open(path, "w", encoding="utf-8").write(html)
    return html


def _period_end(label: str):
    m = re.match(r"\s*([A-Za-z]{3})\w*\s+(\d{4})", label or "")
    if not m or m.group(1).lower() not in _MONTHS:
        return None
    return (pd.Timestamp(int(m.group(2)), _MONTHS[m.group(1).lower()], 1)
            + pd.offsets.MonthEnd(0))


def _num(txt: str):
    t = (txt or "").strip().replace(",", "").replace("%", "")
    try:
        return float(t)
    except ValueError:
        return None


def parse_tables(html: str) -> dict:
    """{section_id: DataFrame(index=row label lower, columns=period-end Timestamp)}."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for sid in ("quarters", "profit-loss", "balance-sheet", "cash-flow"):
        sec = soup.find("section", id=sid)
        table = sec.find("table") if sec else None
        if table is None:
            continue
        heads = [th.text.strip() for th in table.find_all("th")]
        cols = [_period_end(h) for h in heads[1:]]
        rows = {}
        for tr in table.find_all("tr"):
            td = tr.find_all("td")
            if not td:
                continue
            label = re.sub(r"\s*\+\s*$", "", td[0].text.strip()).lower()
            vals = [_num(c.text) for c in td[1:]]
            rows.setdefault(label, vals)
        keep = [i for i, c in enumerate(cols) if c is not None]
        df = pd.DataFrame({lab: [v[i] if i < len(v) else None for i in keep]
                           for lab, v in rows.items()}, index=[cols[i] for i in keep]).T
        out[sid] = df
    return out


def _row(df: pd.DataFrame, contains: str):
    if df is None or df.empty:
        return None
    for lab in df.index:
        if contains in lab:
            return df.loc[lab]
    return None


def _published(cols, t: pd.Timestamp, lag: int):
    return [c for c in cols if c + timedelta(days=lag) <= t]


def rff_pit(tables: dict, as_of) -> dict:
    """The five rebuildable Tier-A checks as of `as_of`. None = not computable."""
    t = pd.Timestamp(as_of)
    chk = {"NI": None, "FCF": None, "ICR": None, "DE": None, "ROA": None}
    q = tables.get("quarters")
    ni_ttm = None
    if q is not None and not q.empty:
        pub = sorted(_published(q.columns, t, Q_LAG_DAYS))[-4:]
        if len(pub) == 4:
            ni = _row(q, "net profit")
            op = _row(q, "operating profit")
            it = _row(q, "interest")
            if ni is not None and all(pd.notna(ni[c]) for c in pub):
                ni_ttm = float(sum(ni[c] for c in pub))
                chk["NI"] = ni_ttm > 0
            if op is not None and it is not None and all(pd.notna(op[c]) and pd.notna(it[c]) for c in pub):
                o, i = float(sum(op[c] for c in pub)), float(sum(it[c] for c in pub))
                chk["ICR"] = True if i <= 0 else (o / i) > ICR_MIN
    bs = tables.get("balance-sheet")
    if bs is not None and not bs.empty:
        pub = sorted(_published(bs.columns, t, A_LAG_DAYS))
        if pub:
            c = pub[-1]
            borr, res, eq = _row(bs, "borrowing"), _row(bs, "reserve"), _row(bs, "equity capital")
            if eq is None:
                eq = _row(bs, "share capital")
            if borr is not None and res is not None and eq is not None:
                b, r_, e = borr[c], res[c], eq[c]
                if pd.notna(b) and pd.notna(r_) and pd.notna(e) and (e + r_) > 0:
                    chk["DE"] = (b / (e + r_)) < DE_MAX
            ta = _row(bs, "total assets")
            if ta is not None and pd.notna(ta[c]) and ta[c] > 0 and ni_ttm is not None:
                chk["ROA"] = (ni_ttm / ta[c] * 100.0) > ROA_MIN
    cf = tables.get("cash-flow")
    if cf is not None and not cf.empty:
        pub = sorted(_published(cf.columns, t, A_LAG_DAYS))
        if pub:
            c = pub[-1]
            fcf = _row(cf, "free cash flow")
            if fcf is not None and pd.notna(fcf[c]):
                chk["FCF"] = fcf[c] > 0
    known = [v for v in chk.values() if v is not None]
    return {"checks": chk, "n_known": len(known), "passed": int(sum(bool(v) for v in known)),
            "quality": "OK" if len(known) >= MIN_CHECKS else "INSUFFICIENT"}


def rff_pit_symbol(symbol: str, as_of) -> dict:
    html = fetch_page(symbol)
    if not html:
        return {"checks": {}, "n_known": 0, "passed": 0, "quality": "NO_PAGE"}
    return rff_pit(parse_tables(html), as_of)


if __name__ == "__main__":
    import sys
    import validation as V
    syms = V.default_universe("nifty500") if len(sys.argv) < 2 else sys.argv[1].split(",")
    ok = miss = 0
    for i, s in enumerate(syms, 1):
        html = fetch_page(s)
        ok, miss = (ok + 1, miss) if html else (ok, miss + 1)
        if i % 50 == 0:
            print(f"  {i}/{len(syms)}  cached {ok}  missing {miss}", flush=True)
    print(f"done: {ok} pages cached, {miss} missing -> {CACHE}")
