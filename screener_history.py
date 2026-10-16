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


def _sales_row(df):
    """Industrials label the top line 'sales', lenders 'revenue'."""
    r = _row(df, "sales")
    return r if r is not None else _row(df, "revenue")


def bff_fields(tables: dict, as_of, basis: str = "auto") -> dict | None:
    """The five BFF inputs AS OF a date (16-Oct-2026 - fundamental_replay.bff_as_of called an
    `as_of` here that a later commit had removed, so the point-in-time BFF had been dead).

    basis "ttm"    - growth = last 4 published quarters vs the 4 before (needs 8 quarters; the
                     page holds ~13, so this only works from about May 2025). Net profit = TTM.
    basis "annual" - growth = latest published financial year vs the one before; works back
                     ~10 years, which is what a 2018-2026 backtest needs.
    basis "auto"   - ttm when 8 quarters are published, else annual (closest to the live BFF,
                     which reads screener's TTM growth row).
    OPM now/prev = the last two published annual OPMs (as the live BFF). ROCE = (profit before
    tax + interest) / average capital employed (equity + reserves + borrowings) over the last
    two published year-ends. Publication lags: quarters +45 days, annuals +60 days."""
    t = pd.Timestamp(as_of)
    out = {"basis": None, "profit_growth_pct": None, "sales_growth_pct": None, "opm_now": None,
           "opm_prev": None, "roce_pct": None, "net_profit": None, "quarter_end": None}
    q, pl, bs = tables.get("quarters"), tables.get("profit-loss"), tables.get("balance-sheet")

    def _g(a, b):
        return None if (a is None or b is None or b <= 0) else (a / b - 1.0) * 100.0

    used_ttm = False
    if basis in ("ttm", "auto") and q is not None and not q.empty:
        pub = sorted(_published(q.columns, t, Q_LAG_DAYS))
        if len(pub) >= 8:
            cur, prv = pub[-4:], pub[-8:-4]
            ni, sl = _row(q, "net profit"), _sales_row(q)
            if ni is not None and all(pd.notna(ni[c]) for c in cur + prv):
                out["net_profit"] = float(sum(ni[c] for c in cur))
                out["profit_growth_pct"] = _g(out["net_profit"], float(sum(ni[c] for c in prv)))
            if sl is not None and all(pd.notna(sl[c]) for c in cur + prv):
                out["sales_growth_pct"] = _g(float(sum(sl[c] for c in cur)), float(sum(sl[c] for c in prv)))
            out["quarter_end"] = str(cur[-1].date())
            used_ttm = True
    if basis == "ttm" and not used_ttm:
        return None
    if pl is not None and not pl.empty:
        apub = sorted(_published(pl.columns, t, A_LAG_DAYS))
        if len(apub) >= 2:
            c1, c0 = apub[-1], apub[-2]
            if not used_ttm:
                ni, sl = _row(pl, "net profit"), _sales_row(pl)
                if ni is not None and pd.notna(ni[c1]):
                    out["net_profit"] = float(ni[c1])
                    if pd.notna(ni[c0]):
                        out["profit_growth_pct"] = _g(float(ni[c1]), float(ni[c0]))
                if sl is not None and pd.notna(sl[c1]) and pd.notna(sl[c0]):
                    out["sales_growth_pct"] = _g(float(sl[c1]), float(sl[c0]))
            opm = _row(pl, "opm")
            if opm is not None and pd.notna(opm[c1]) and pd.notna(opm[c0]):
                out["opm_now"], out["opm_prev"] = float(opm[c1]), float(opm[c0])
            pbt, it = _row(pl, "profit before tax"), _row(pl, "interest")
            if bs is not None and not bs.empty and pbt is not None and it is not None \
                    and pd.notna(pbt[c1]) and pd.notna(it[c1]):
                eqc = _row(bs, "equity capital")
                if eqc is None:
                    eqc = _row(bs, "share capital")
                res, bor = _row(bs, "reserve"), _row(bs, "borrowing")

                def _ce(c):
                    if c not in bs.columns or eqc is None or res is None:
                        return None
                    v = [eqc[c], res[c], (bor[c] if bor is not None else 0.0)]
                    return None if any(pd.isna(x) for x in v) else float(sum(v))
                ce = [x for x in (_ce(c1), _ce(c0)) if x is not None and x > 0]
                if ce:
                    out["roce_pct"] = (float(pbt[c1]) + float(it[c1])) / (sum(ce) / len(ce)) * 100.0
    out["basis"] = "ttm" if used_ttm else "annual"
    known = [k for k in ("profit_growth_pct", "sales_growth_pct", "opm_now", "roce_pct", "net_profit")
             if out[k] is not None]
    return out if known else None


_TABLE_CACHE: dict = {}


def as_of(symbol: str, anchor, basis: str = "auto") -> dict | None:
    """bff_fields for a symbol, the parsed page cached per process."""
    sym = _clean(symbol)
    if sym not in _TABLE_CACHE:
        html = fetch_page(sym)
        _TABLE_CACHE[sym] = parse_tables(html) if html else None
    t = _TABLE_CACHE[sym]
    return bff_fields(t, anchor, basis) if t else None


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
