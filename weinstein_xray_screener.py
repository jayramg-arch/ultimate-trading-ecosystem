import time
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# C1 sweep: route OHLCV through data_provider when available. The .info /
# .financials endpoints are NOT cached here (different yfinance code path).
try:
    import data_provider as _dp
    USE_DATA_PROVIDER = True
except Exception:
    _dp = None
    USE_DATA_PROVIDER = False

# Try to use fundamental_hub for caching if available, otherwise fallback
try:
    from fundamental_hub import _cached
except ImportError:
    _cache = {}
    def _cached(key, ttl_seconds, fn):
        now = time.time()
        if key in _cache and now < _cache[key]["expires"]:
            return _cache[key]["data"]
        res = fn()
        _cache[key] = {"data": res, "expires": now + ttl_seconds}
        return res

logger = logging.getLogger(__name__)

# =====================================================================
# MACRO TRENDS
# =====================================================================
def get_macro_health():
    """
    Evaluates India 10Y Yield, USDINR, and CNX500 (using NIFTY 500 equivalent if possible, 
    or Nifty 50 ^NSEI as proxy) to match the TradingView script's Macro score.
    """
    def _fetch():
        macro_score = 0
        details = {}
        try:
            # 1. Yield Trend (India 10Y) — C1 sweep: cached
            if USE_DATA_PROVIDER and _dp is not None:
                hist_y = _dp.fetch_ohlcv("^IN10YR", period="2mo", interval="1d")
            else:
                hist_y = yf.Ticker("^IN10YR").history(period="2mo")
            if len(hist_y) >= 21:
                cur_y = hist_y['Close'].iloc[-1]
                prev_y = hist_y['Close'].iloc[-21]
                if cur_y < prev_y:
                    macro_score += 1
                    details['Yield'] = f"FALLING ({cur_y:.2f}%)"
                else:
                    details['Yield'] = f"RISING ({cur_y:.2f}%)"
            else:
                details['Yield'] = "N/A"

            # 2. USDINR — C1 sweep: cached
            if USE_DATA_PROVIDER and _dp is not None:
                hist_fx = _dp.fetch_ohlcv("INR=X", period="2mo", interval="1d")
            else:
                hist_fx = yf.Ticker("INR=X").history(period="2mo")
            if len(hist_fx) >= 21:
                cur_fx = hist_fx['Close'].iloc[-1]
                prev_fx = hist_fx['Close'].iloc[-21]
                if cur_fx < prev_fx: # INR Strengthening
                    macro_score += 1
                    details['USDINR'] = f"STRENGTHENING ({cur_fx:.2f})"
                else:
                    details['USDINR'] = f"WEAKENING ({cur_fx:.2f})"
            else:
                details['USDINR'] = "N/A"

            # 3. Market Trend (Nifty 50 as proxy for CNX500) — C1 sweep: cached
            if USE_DATA_PROVIDER and _dp is not None:
                hist_n = _dp.fetch_ohlcv("^NSEI", period="1y", interval="1d")
            else:
                hist_n = yf.Ticker("^NSEI").history(period="1y")
            if len(hist_n) >= 200:
                c = hist_n['Close'].iloc[-1]
                sma50 = hist_n['Close'].rolling(50).mean().iloc[-1]
                sma200 = hist_n['Close'].rolling(200).mean().iloc[-1]
                if c > sma50 and sma50 > sma200:
                    macro_score += 1
                    details['Market'] = "STRONG UPTREND"
                elif c < sma50 and c < sma200:
                    details['Market'] = "DOWNTREND"
                else:
                    details['Market'] = "SIDEWAYS"
            else:
                details['Market'] = "N/A"

            return macro_score, details
        except Exception as e:
            logger.error(f"Macro fetch failed: {e}")
            return 0, {}

    return _cached("xray_macro", 3600, _fetch)

# =====================================================================
# X-RAY EVALUATOR
# =====================================================================
_XR_SCR_CACHE: dict = {}


def _screener_xray_metrics(symbol: str, ttl: int = 86400) -> dict:
    """Screener.in-PRIMARY fundamentals for the X-Ray scorecard (data-provider
    rule: screener.in first, yfinance fallback). Parses the company page's P&L /
    Balance Sheet / Cash Flow / Compounded-Growth / Quarters / top-ratios tables
    and returns DERIVED metrics. All figures are ₹ Cr from ONE source, so every
    ratio is source-pure (no unit mixing). Current + prior-year where a Piotroski
    trend needs it. Returns {} on any failure so the caller keeps the yfinance
    fallback. Screener.in cannot supply gross profit, current assets/liabilities,
    capex or per-year share count — those stay on yfinance. Cached 24h."""
    import os
    import time as _t
    import requests
    from bs4 import BeautifulSoup

    key = f"_xr_scr_{symbol.upper()}"
    now = _t.time()
    hit = _XR_SCR_CACHE.get(key)
    if hit and now < hit["exp"]:
        return hit["data"]

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
            _XR_SCR_CACHE[key] = {"data": {}, "exp": now + ttl}
            return {}
    except Exception:
        return {}
    soup = BeautifulSoup(r.text, "html.parser")

    def _f(t):
        try:
            return float(str(t).strip().replace(",", "").replace("%", "").replace("₹", ""))
        except (TypeError, ValueError):
            return None

    def _row(section_id, contains, n=2):
        sec = soup.find("section", id=section_id)
        if not sec:
            return []
        tbl = sec.find("table")
        if not tbl:
            return []
        for tr in tbl.find_all("tr"):
            cells = tr.find_all("td")
            if cells and contains in cells[0].text.strip().lower():
                vals = [_f(c.text) for c in cells[1:]]
                vals = [v for v in vals if v is not None]
                return vals[-n:] if n else vals
        return []

    def _ranges_ttm(label):
        for tbl in soup.find_all("table", class_="ranges-table"):
            h = tbl.find("th")
            if h and label in h.text.strip().lower():
                for tr in tbl.find_all("tr"):
                    tds = tr.find_all("td")
                    if len(tds) >= 2 and "ttm" in tds[0].text.strip().lower():
                        return _f(tds[-1].text)
        return None

    def _top(label):
        top = soup.find(id="top-ratios")
        if not top:
            return None
        for li in top.find_all("li"):
            nm = li.find("span", class_="name"); val = li.find("span", class_="number")
            if nm and val and label in nm.text.strip().lower():
                return _f(val.text)
        return None

    def _last(a, i=-1):
        return a[i] if a and len(a) >= abs(i) else None

    sales = _row("profit-loss", "sales", 2) or _row("profit-loss", "revenue", 2)
    npf = _row("profit-loss", "net profit", 2)
    opf = _row("profit-loss", "operating profit", 2)
    opm = _row("profit-loss", "opm", 2)
    assets = _row("balance-sheet", "total assets", 2)
    borr = _row("balance-sheet", "borrowing", 2)
    eqc = _row("balance-sheet", "equity capital", 2)
    res = _row("balance-sheet", "reserves", 2)
    ocf = _row("cash-flow", "operating activit", 1)
    npq = _row("quarters", "net profit", 3)
    sg = _ranges_ttm("compounded sales growth")
    pg = _ranges_ttm("compounded profit growth")
    pe = _top("p/e"); bv = _top("book value"); price = _top("current price")

    ni_l, ni_p = _last(npf, -1), _last(npf, -2)
    as_l, as_p = _last(assets, -1), _last(assets, -2)
    eq_l = ((_last(eqc, -1) or 0) + (_last(res, -1) or 0)) if (eqc or res) else None
    eq_p = ((_last(eqc, -2) or 0) + (_last(res, -2) or 0)) if (eqc or res) else None
    bo_l, bo_p = _last(borr, -1), _last(borr, -2)
    sa_l, sa_p = _last(sales, -1), _last(sales, -2)
    ocf_l = _last(ocf, -1)

    out: dict = {}
    if ni_l is not None:
        out["ni_ttm"] = ni_l
    if ni_l is not None and eq_l:
        out["roe_ttm"] = ni_l / eq_l * 100
    if ni_l is not None and as_l:
        out["roa_ttm"] = ni_l / as_l * 100
    if ni_p is not None and as_p:
        out["roa_ly"] = ni_p / as_p                         # fraction (pf3 uses *100)
    if bo_l is not None and eq_l:
        out["de_ratio"] = bo_l / eq_l
    if bo_p is not None and eq_p:
        out["de_ly"] = bo_p / eq_p
    if _last(opm, -1) is not None:
        out["op_margin"] = _last(opm, -1)
    elif _last(opf, -1) is not None and sa_l:
        out["op_margin"] = _last(opf, -1) / sa_l * 100
    if sa_l is not None and as_l:
        out["asset_turn"] = sa_l / as_l
    if sa_p is not None and as_p:
        out["at_ly"] = sa_p / as_p
    if ni_l is not None and ocf_l is not None and as_l:
        out["accrual_ratio"] = (ni_l - ocf_l) / as_l * 100
    if sg is not None:
        out["rev_yoy"] = sg
    if pg is not None:
        out["ni_yoy"] = pg
    if ocf_l is not None:
        out["ocf_fy"] = ocf_l
    if pe is not None:
        out["pe"] = pe
    if price and bv and bv > 0:
        out["pb"] = price / bv
    if len(npq) >= 3:
        q0, q1, q2 = npq[-1], npq[-2], npq[-3]
        out["accel_available"] = True
        _g1 = (q0 - q1) / abs(q1) if q1 else 0
        _g2 = (q1 - q2) / abs(q2) if q2 else 0
        out["is_accelerating"] = bool(_g1 > _g2 and _g1 > 0)

    _XR_SCR_CACHE[key] = {"data": out, "exp": now + ttl}
    return out


def get_xray_scorecard(symbol: str) -> dict:
    """
    Computes the Minervini Score (0-8), Piotroski F-Score (0-9), and
    Overall Fundamental Rating (0-17) matching Weinstein Fundamental X-Ray v2.2.pine.

    Data-provider rule: screener.in is PRIMARY (via _screener_xray_metrics);
    yfinance is the FALLBACK for the fields screener can't supply (gross margin,
    current ratio, FCF, dilution) and whenever the screener parse misses.
    """
    def _fetch():
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Financials (Annual)
        fin_a = ticker.financials
        bs_a = ticker.balance_sheet
        cf_a = ticker.cashflow
        
        # Quarterly
        fin_q = ticker.quarterly_financials
        bs_q = ticker.quarterly_balance_sheet
        cf_q = ticker.quarterly_cashflow

        # Screener.in is PRIMARY — fetch it first. Only error out if BOTH the
        # screener parse AND the yfinance statements are empty (so the scorecard
        # still works when yfinance is unavailable, per the data-provider rule).
        scr = _screener_xray_metrics(symbol)
        _yf_empty = (fin_a is None or bs_a is None or cf_a is None
                     or fin_a.empty or bs_a.empty or cf_a.empty)
        if _yf_empty and not scr:
            return {"error": "Insufficient data"}

        def get_val(df, keys, col_idx=0, default=None):
            if df is None or df.empty or col_idx >= len(df.columns):
                return default
            for k in keys:
                if k in df.index:
                    val = df.loc[k].iloc[col_idx]
                    if pd.notna(val):
                        return val
            return default

        # 1. Fetch current/trailing data (TTM/FQ equivalents)
        rev_ttm = info.get("totalRevenue", get_val(fin_a, ["Total Revenue", "Operating Revenue"]))
        ni_ttm = info.get("netIncomeToCommon", get_val(fin_a, ["Net Income", "Net Income Common Stockholders"]))
        ebitda_ttm = info.get("ebitda", get_val(fin_a, ["EBITDA", "Normalized EBITDA"]))
        
        # We use latest annual for BS/CF items (as we fixed in the pine script)
        ocf_fy = get_val(cf_a, ["Operating Cash Flow", "Total Cash From Operating Activities", "Cash Flow From Continuing Operating Activities"])
        capex_fy = get_val(cf_a, ["Capital Expenditure", "Capital Expenditures"])
        
        assets_fy = get_val(bs_a, ["Total Assets"])
        equity_fy = get_val(bs_a, ["Total Stockholder Equity", "Total Equity Gross Minority Interest", "Stockholders Equity"])
        debt_fy = get_val(bs_a, ["Total Debt"])
        curr_assets_fy = get_val(bs_a, ["Current Assets", "Total Current Assets"])
        curr_liab_fy = get_val(bs_a, ["Current Liabilities", "Total Current Liabilities"])
        shares_fy = get_val(bs_a, ["Ordinary Shares Number", "Share Issued"])
        
        gross_profit_fy = get_val(fin_a, ["Gross Profit"])
        rev_fy = get_val(fin_a, ["Total Revenue", "Operating Revenue"])
        op_inc_fy = get_val(fin_a, ["Operating Income"])
        
        # Prior Year (LY)
        roa_ly = None
        de_ly = None
        cr_ly = None
        gm_ly = None
        at_ly = None
        shares_ly = get_val(bs_a, ["Ordinary Shares Number", "Share Issued"], 1)
        
        ni_ly = get_val(fin_a, ["Net Income", "Net Income Common Stockholders"], 1)
        assets_ly = get_val(bs_a, ["Total Assets"], 1)
        debt_ly = get_val(bs_a, ["Total Debt"], 1)
        equity_ly = get_val(bs_a, ["Total Stockholder Equity", "Total Equity Gross Minority Interest"], 1)
        curr_assets_ly = get_val(bs_a, ["Current Assets", "Total Current Assets"], 1)
        curr_liab_ly = get_val(bs_a, ["Current Liabilities", "Total Current Liabilities"], 1)
        gross_profit_ly = get_val(fin_a, ["Gross Profit"], 1)
        rev_ly = get_val(fin_a, ["Total Revenue", "Operating Revenue"], 1)
        
        if ni_ly and assets_ly: roa_ly = ni_ly / assets_ly
        if debt_ly is not None and equity_ly and equity_ly > 0: de_ly = debt_ly / equity_ly
        if curr_assets_ly and curr_liab_ly and curr_liab_ly > 0: cr_ly = curr_assets_ly / curr_liab_ly
        if gross_profit_ly and rev_ly and rev_ly > 0: gm_ly = gross_profit_ly / rev_ly
        if rev_ly and assets_ly and assets_ly > 0: at_ly = rev_ly / assets_ly
        
        # Ratios
        roa_ttm = (ni_ttm / assets_fy) * 100 if ni_ttm and assets_fy else None
        roe_ttm = (ni_ttm / equity_fy) * 100 if ni_ttm and equity_fy and equity_fy > 0 else None
        gross_margin = (gross_profit_fy / rev_fy) * 100 if gross_profit_fy and rev_fy and rev_fy > 0 else None
        ebitda_margin = (ebitda_ttm / rev_ttm) * 100 if ebitda_ttm and rev_ttm and rev_ttm > 0 else None
        op_margin = (op_inc_fy / rev_fy) * 100 if op_inc_fy and rev_fy and rev_fy > 0 else None
        de_ratio = (debt_fy / equity_fy) if debt_fy is not None and equity_fy and equity_fy > 0 else None
        curr_ratio = (curr_assets_fy / curr_liab_fy) if curr_assets_fy and curr_liab_fy and curr_liab_fy > 0 else None
        fcf_fy = (ocf_fy - abs(capex_fy)) if ocf_fy is not None and capex_fy is not None else None
        asset_turn = (rev_fy / assets_fy) if rev_fy and assets_fy and assets_fy > 0 else None
        accrual_ratio = ((ni_ttm - ocf_fy) / assets_fy) * 100 if ni_ttm is not None and ocf_fy is not None and assets_fy and assets_fy > 0 else None
        
        # Growth
        rev_yoy = info.get("revenueGrowth", 0) * 100 if info.get("revenueGrowth") else None
        ni_yoy = info.get("earningsGrowth", 0) * 100 if info.get("earningsGrowth") else None
        eps_yoy = ni_yoy # Approximation if earningsGrowth exists
        
        # Earnings Accel (QoQ)
        is_accelerating = False
        accel_available = False
        if fin_q is not None and len(fin_q.columns) >= 3:
            ni_q0 = get_val(fin_q, ["Net Income", "Net Income Common Stockholders"], 0)
            ni_q1 = get_val(fin_q, ["Net Income", "Net Income Common Stockholders"], 1)
            ni_q2 = get_val(fin_q, ["Net Income", "Net Income Common Stockholders"], 2)
            if ni_q0 is not None and ni_q1 is not None and ni_q2 is not None:
                accel_available = True
                g1 = (ni_q0 - ni_q1) / abs(ni_q1) if ni_q1 != 0 else 0
                g2 = (ni_q1 - ni_q2) / abs(ni_q2) if ni_q2 != 0 else 0
                if g1 > g2 and g1 > 0:
                    is_accelerating = True

        # -------------------------------------------------------------
        # SCREENER.IN PRIMARY OVERRIDE (data-provider rule). Where screener.in
        # supplies a metric it WINS; the yfinance values computed above remain the
        # FALLBACK for anything screener lacks (gross margin, current ratio, FCF,
        # dilution). Screener figures are ₹ Cr and internally consistent, so the
        # ratios are source-pure — no cross-source unit mixing.
        # -------------------------------------------------------------
        if scr:                                    # fetched above (screener primary)
            if scr.get("ni_ttm") is not None:      ni_ttm = scr["ni_ttm"]
            if scr.get("ocf_fy") is not None:      ocf_fy = scr["ocf_fy"]
            if scr.get("roa_ttm") is not None:     roa_ttm = scr["roa_ttm"]
            if scr.get("roe_ttm") is not None:     roe_ttm = scr["roe_ttm"]
            if scr.get("roa_ly") is not None:      roa_ly = scr["roa_ly"]
            if scr.get("de_ratio") is not None:    de_ratio = scr["de_ratio"]
            if scr.get("de_ly") is not None:       de_ly = scr["de_ly"]
            if scr.get("op_margin") is not None:   op_margin = scr["op_margin"]
            if scr.get("asset_turn") is not None:  asset_turn = scr["asset_turn"]
            if scr.get("at_ly") is not None:       at_ly = scr["at_ly"]
            if scr.get("accrual_ratio") is not None: accrual_ratio = scr["accrual_ratio"]
            if scr.get("rev_yoy") is not None:     rev_yoy = scr["rev_yoy"]
            if scr.get("ni_yoy") is not None:      ni_yoy = scr["ni_yoy"]; eps_yoy = ni_yoy
            if scr.get("accel_available"):
                accel_available = True
                is_accelerating = scr.get("is_accelerating", is_accelerating)

        # -------------------------------------------------------------
        # SCORE: MINERVINI (0-8)
        # -------------------------------------------------------------
        sc_rev = None if rev_yoy is None else (1 if rev_yoy > 20 else 0)
        sc_ni  = None if ni_yoy is None else (1 if ni_yoy > 25 else 0)
        sc_acc = 1 if is_accelerating else (None if not accel_available else 0)
        sc_roe = None if roe_ttm is None else (1 if roe_ttm > 15 else 0)
        sc_gm  = None if gross_margin is None else (1 if gross_margin > 15 else 0)
        sc_de  = None if de_ratio is None else (1 if de_ratio < 1.5 else 0)
        sc_cr  = None if curr_ratio is None else (1 if curr_ratio > 1.0 else 0)
        sc_fcf = None if fcf_fy is None else (1 if fcf_fy > 0 else 0)
        
        miner_score = sum(x for x in [sc_rev, sc_ni, sc_acc, sc_roe, sc_gm, sc_de, sc_cr, sc_fcf] if x is not None)
        
        # -------------------------------------------------------------
        # SCORE: PIOTROSKI F-SCORE (0-9)
        # -------------------------------------------------------------
        pf1 = None if roa_ttm is None else (1 if roa_ttm > 0 else 0)
        pf2 = None if ocf_fy is None else (1 if ocf_fy > 0 else 0)
        pf3 = None if (roa_ttm is None or roa_ly is None) else (1 if roa_ttm > (roa_ly * 100) else 0)
        pf4 = None if accrual_ratio is None else (1 if accrual_ratio < 0 else 0)
        pf5 = None if (de_ratio is None or de_ly is None) else (1 if de_ratio < de_ly else 0)
        pf6 = None if (curr_ratio is None or cr_ly is None) else (1 if curr_ratio > cr_ly else 0)
        pf7 = None if (shares_fy is None or shares_ly is None) else (1 if shares_fy <= shares_ly else 0)
        pf8 = None if (gross_margin is None or gm_ly is None) else (1 if gross_margin > (gm_ly * 100) else 0)
        pf9 = None if (asset_turn is None or at_ly is None) else (1 if asset_turn > at_ly else 0)
        
        pio_score = sum(x for x in [pf1, pf2, pf3, pf4, pf5, pf6, pf7, pf8, pf9] if x is not None)

        # -------------------------------------------------------------
        # OVERALL RATING (0-17)
        # -------------------------------------------------------------
        macro_score, _ = get_macro_health() # 0-3
        
        ov_mom = 0
        if rev_yoy and rev_yoy > 20: ov_mom += 1
        if ni_yoy and ni_yoy > 25: ov_mom += 1
        if eps_yoy and eps_yoy > 25: ov_mom += 1
        if is_accelerating: ov_mom += 1
        if ni_ttm and ni_ttm > 0: ov_mom += 1
        
        ov_mgn = 0
        if gross_margin and gross_margin > 30: ov_mgn += 1
        if ebitda_margin and ebitda_margin > 20: ov_mgn += 1
        if op_margin and op_margin > 15: ov_mgn += 1
        if roe_ttm and roe_ttm > 20: ov_mgn += 1
        
        ov_hlth = 0
        if de_ratio is not None and de_ratio < 1.0: ov_hlth += 1
        if curr_ratio and curr_ratio > 1.5: ov_hlth += 1
        if fcf_fy and fcf_fy > 0: ov_hlth += 1
        
        pe_calc = info.get("trailingPE")
        pb_calc = info.get("priceToBook")
        if scr:                                    # screener.in primary for valuation too
            if scr.get("pe") is not None: pe_calc = scr["pe"]
            if scr.get("pb") is not None: pb_calc = scr["pb"]
        if pe_calc and 0 < pe_calc < 40: ov_hlth += 1
        if pb_calc and 0 < pb_calc < 5.0: ov_hlth += 1
        
        # Replicate Conviction (0-10 scale)
        conv_val = 5.0
        pg_val = ni_yoy if ni_yoy is not None else 0.0
        if pg_val > 50: conv_val += 2.5
        elif pg_val > 20: conv_val += 1.5
        
        sg_val = rev_yoy if rev_yoy is not None else 0.0
        if sg_val > 20: conv_val += 1.0
        
        roe_val = roe_ttm if roe_ttm is not None else 0.0
        if roe_val > 20: conv_val += 1.0
        
        mcap_val = (info.get("marketCap", 0) or 0) / 10000000.0
        if 1000 < mcap_val < 20000: conv_val += 0.5
        conviction = round(min(10.0, conv_val), 1)

        # Replicate Tech_Score (0-100 scale) dynamically
        try:
            import technical_enrichment as _te
            tech_data = _te.enrich_symbol(symbol)
            tech_score = float(_te.calc_tech_score(tech_data))
        except Exception:
            tech_score = 50.0

        # Calculate Combined_Score (0-100 scale)
        combined_score = conviction * 5.0 + tech_score * 0.5

        # Weighted overall score (0-100 scale)
        ov_total = (0.30 * combined_score) + (0.15 * (conviction * 10.0)) + (0.15 * tech_score) + \
                   (0.20 * (miner_score / 8.0 * 100.0)) + (0.20 * (pio_score / 9.0 * 100.0))
        ov_total = round(ov_total, 1)
        
        ov_grade = "A+ EXCEPTIONAL" if ov_total >= 90 else \
                   "A STRONG" if ov_total >= 80 else \
                   "B GOOD" if ov_total >= 70 else \
                   "C FAIR" if ov_total >= 55 else \
                   "D WEAK" if ov_total >= 40 else "F POOR"

        return {
            "symbol": symbol,
            "Minervini_Score": miner_score,
            "Minervini_Details": {
                "Rev YoY > 20%": sc_rev,
                "NI YoY > 25%": sc_ni,
                "Accel EPS": sc_acc,
                "ROE > 15%": sc_roe,
                "Gross Margin > 15%": sc_gm,
                "D/E < 1.5": sc_de,
                "Current Ratio > 1.0": sc_cr,
                "FCF Positive": sc_fcf
            },
            "Piotroski_Score": pio_score,
            "Piotroski_Details": {
                "F1 ROA Positive": pf1,
                "F2 OCF Positive": pf2,
                "F3 ROA Improving": pf3,
                "F4 Accrual Ratio < 0": pf4,
                "F5 Leverage Decreasing": pf5,
                "F6 Liquidity Improving": pf6,
                "F7 No Dilution": pf7,
                "F8 Gross Margin Increasing": pf8,
                "F9 Asset Turnover Increasing": pf9
            },
            "Overall_Rating": ov_total,
            "Overall_Grade": ov_grade,
            "Overall_Details": {
                "Combined Score": f"{combined_score:.1f}/100",
                "Conviction Score": f"{conviction:.1f}/10",
                "Technical Score": f"{tech_score:.1f}/100",
                "Minervini Score": f"{miner_score}/8",
                "Piotroski Score": f"{pio_score}/9"
            },
            "Raw_Metrics": {
                "ROE": f"{roe_ttm:.1f}%" if roe_ttm else "N/A",
                "D/E Ratio": f"{de_ratio:.2f}" if de_ratio is not None else "N/A",
                "P/E Ratio": f"{pe_calc:.1f}" if pe_calc else "N/A",
                "Accrual Ratio": f"{accrual_ratio:.1f}%" if accrual_ratio else "N/A",
            }
        }

    return _cached(f"xray_scorecard_{symbol.upper()}", 86400, _fetch)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sym = "RELIANCE.NS"
    print(f"Testing X-Ray Screener for {sym}...")
    res = get_xray_scorecard(sym)
    import json
    print(json.dumps(res, indent=2))
