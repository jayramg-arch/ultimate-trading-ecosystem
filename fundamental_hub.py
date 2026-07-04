# fundamental_hub.py — Fundamental Data Hub for Commander Web v4.0
#
# Provides fundamental data retrieval for NSE India stocks using yfinance.
# Covers: stock info, financial statements, quarterly results, screening,
#         valuation scorecards, and Gemini-ready plain-text summaries.
#
# Part of Weinstein Commander Web v4.0 — Hedge Fund Trading System
# Author: Commander Suite / Claude Agent
# Usage: from fundamental_hub import fetch_stock_fundamentals, screen_fundamentals

# =============================================================================
# SECTION 1 — IMPORTS & CONFIG
# =============================================================================

import time
import logging
import warnings
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import pytz
import yfinance as yf

logger = logging.getLogger(__name__)

# Suppress yfinance / urllib3 noise
warnings.filterwarnings("ignore", category=FutureWarning)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

# Module-level TTL cache store
_cache: Dict[str, Dict[str, Any]] = {}

# IST timezone
_IST = pytz.timezone("Asia/Kolkata")

# =============================================================================
# SECTION 2 — CACHE HELPER
# =============================================================================

def _cached(key: str, ttl_seconds: int, fn):
    """
    Simple in-memory TTL cache (same pattern as market_data_hub.py).

    Parameters
    ----------
    key         : unique cache key string
    ttl_seconds : how long to keep the cached result
    fn          : zero-argument callable that produces the data

    Returns the cached value if still fresh, otherwise calls fn() and stores result.
    """
    now = time.time()
    if key in _cache and now < _cache[key]["expires"]:
        return _cache[key]["data"]
    result = fn()
    _cache[key] = {"data": result, "expires": now + ttl_seconds}
    return result


def _ist_now_str() -> str:
    """Return current IST timestamp as a formatted string."""
    return datetime.now(_IST).strftime("%Y-%m-%d %H:%M:%S IST")


def _to_cr(value) -> Optional[float]:
    """Convert rupee value to Crores (divide by 1e7). Returns None on failure."""
    try:
        if value is None:
            return None
        v = float(value)
        return round(v / 1e7, 2)
    except (TypeError, ValueError):
        return None


def _pct(value) -> Optional[float]:
    """Convert a fraction (e.g. 0.15) to percentage (15.0). Returns None on failure."""
    try:
        if value is None:
            return None
        return round(float(value) * 100, 2)
    except (TypeError, ValueError):
        return None


def _safe_float(value, default=None) -> Optional[float]:
    """Safely cast to float, returning default on failure."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _fetch_screener_fundamentals(symbol: str) -> Optional[dict]:
    """
    Scrape key fundamentals directly from Screener.in's public company page.
    Provides extremely accurate Promoter Holding % and calculated Debt-to-Equity
    which yfinance often lacks or calculates incorrectly for Indian listings.
    """
    import requests
    from bs4 import BeautifulSoup
    import os

    clean_sym = symbol.strip().upper()
    for suffix in (".NS", ".BO", ".NSE", "-EQ"):
        if clean_sym.endswith(suffix):
            clean_sym = clean_sym[:-len(suffix)]
            break

    url = f"https://www.screener.in/company/{clean_sym}/"
    cookie_str = os.getenv("SCREENER_COOKIE", "")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    if cookie_str:
        headers["Cookie"] = cookie_str

    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
    except Exception as e:
        logger.warning("Screener company request failed for %s: %s", symbol, e)
        return None

    soup = BeautifulSoup(r.text, 'html.parser')

    # Parse name
    name = ""
    name_h1 = soup.find('h1')
    if name_h1:
        name = name_h1.text.strip()

    # Parse Top Ratios Card
    ratios = {}
    top_ratios_div = soup.find(id="top-ratios")
    if not top_ratios_div:
        top_ratios_div = soup.find('ul', class_=lambda x: x and 'columns' in x)
    if top_ratios_div:
        lis = top_ratios_div.find_all('li')
        for li in lis:
            name_span = li.find('span', class_='name')
            value_span = li.find('span', class_='number')
            if name_span and value_span:
                name_key = name_span.text.strip().replace(':', '')
                value_str = value_span.text.strip()
                ratios[name_key] = value_str.replace('%', '').replace(',', '').strip()

    # Parse Promoter Holding
    promoter_holding = None
    shareholding_section = soup.find('section', id='shareholding')
    if shareholding_section:
        table = shareholding_section.find('table')
        if table:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if cols:
                    header = cols[0].text.strip().lower()
                    if 'promoter' in header or 'owners' in header:
                        val = cols[-1].text.strip().replace('%', '').replace(',', '').strip()
                        try:
                            promoter_holding = float(val)
                        except:
                            pass
                        break

    # Parse Balance Sheet for D/E
    borrowings = 0.0
    reserves = 0.0
    equity_cap = 0.0

    balance_sheet_section = soup.find('section', id='balance-sheet')
    if balance_sheet_section:
        table = balance_sheet_section.find('table')
        if table:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if cols:
                    row_name = cols[0].text.strip().lower()
                    val_str = cols[-1].text.strip().replace(',', '').strip()
                    try:
                        val_float = float(val_str) if val_str and val_str != '' else 0.0
                    except:
                        val_float = 0.0

                    if 'borrowings' in row_name:
                        borrowings = val_float
                    elif 'reserves' in row_name:
                        reserves = val_float
                    elif 'equity capital' in row_name or 'share capital' in row_name:
                        equity_cap = val_float

    equity = equity_cap + reserves
    debt_equity = borrowings / equity if equity > 0 else 0.0

    # Extract price
    price = 0.0
    price_str = ratios.get("Current Price")
    if price_str:
        try:
            price = float(price_str)
        except:
            pass

    # Extract Book Value
    pb_ratio = None
    bv_str = ratios.get("Book Value")
    if bv_str and price > 0:
        try:
            bv = float(bv_str)
            if bv > 0:
                pb_ratio = round(price / bv, 2)
        except:
            pass

    earnings_growth = None
    for k in ["YOY Quarterly profit growth", "Quarterly profit growth", "Qtr Profit Var %", "Qtr Profit Var"]:
        if k in ratios:
            try:
                earnings_growth = float(ratios[k])
                break
            except:
                pass

    revenue_growth = None
    for k in ["YOY Quarterly sales growth", "Quarterly sales growth", "Qtr Sales Var %", "Qtr Sales Var"]:
        if k in ratios:
            try:
                revenue_growth = float(ratios[k])
                break
            except:
                pass

    return {
        "name": name,
        "price": price,
        "market_cap": float(ratios.get("Market Cap", 0)) if ratios.get("Market Cap") else 0.0,
        "pe_ratio": float(ratios.get("Stock P/E", 0)) if ratios.get("Stock P/E") else None,
        "roe": float(ratios.get("ROE", 0)) if ratios.get("ROE") else None,
        "roce": float(ratios.get("ROCE", 0)) if ratios.get("ROCE") else None,
        "dividend_yield": float(ratios.get("Dividend Yield", 0)) if ratios.get("Dividend Yield") else 0.0,
        "promoter_holding": promoter_holding,
        "debt_equity": round(debt_equity, 2),
        "pb_ratio": pb_ratio,
        "earnings_growth": earnings_growth,
        "revenue_growth": revenue_growth
    }


def fetch_screener_rff_row(symbol: str, ttl: int = 86400) -> Optional[dict]:
    """Live per-symbol Screener.in fetch mapped to the RFF canonical keys
    (2026-07-04, Jay: Screener.in is the PRIMARY fundamentals source; yfinance
    is fallback only).

    Scrapes the company page (same cookie/session as _fetch_screener_fundamentals)
    and returns a dict shaped for recovery_screener.compute_rff():
        Net profit                      P&L table, TTM/last column (₹ Cr)
        Cash from operating activity    Cash-flow table, last column (₹ Cr)
        Debt to equity / DE_Prev        computed from balance sheet (curr / prior col)
        ROCE                            top-ratios card
        Qtr Sales Var % / Qtr Profit Var %   top-ratios growth keys
        OPM_Now / OPM_Prev              P&L OPM %% row, last two columns
    ICR / Current ratio are NOT on the public page — the caller merges those
    from yfinance. Values are ₹ Cr (sign-based RFF checks are unit-agnostic;
    the caller must NOT mix Screener OCF with yfinance CapEx — drop CapEx when
    Screener OCF wins). Cached 24h. Returns None when the page yields nothing.
    """
    def _fetch():
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

        def _row_vals(section_id: str, contains: str):
            """Last-two numeric cells of the first table row whose header contains `contains`."""
            sec = soup.find("section", id=section_id)
            if not sec:
                return None, None
            table = sec.find("table")
            if not table:
                return None, None
            for tr in table.find_all("tr"):
                cells = tr.find_all("td")
                if not cells:
                    continue
                if contains in cells[0].text.strip().lower():
                    def _f(td):
                        try:
                            return float(td.text.strip().replace(",", "").replace("%", ""))
                        except Exception:
                            return None
                    last = _f(cells[-1]) if len(cells) >= 2 else None
                    prev = _f(cells[-2]) if len(cells) >= 3 else None
                    return last, prev
            return None, None

        out: dict = {}
        ni, _ = _row_vals("profit-loss", "net profit")
        if ni is not None:
            out["Net profit"] = ni
        opm_now, opm_prev = _row_vals("profit-loss", "opm")
        if opm_now is not None:
            out["OPM_Now"] = opm_now
        if opm_prev is not None:
            out["OPM_Prev"] = opm_prev
        ocf, _ = _row_vals("cash-flow", "operating activit")
        if ocf is not None:
            out["Cash from operating activity"] = ocf

        # Balance sheet -> D/E now + prior year (deleveraging check)
        borr, borr_p = _row_vals("balance-sheet", "borrowing")
        res, res_p = _row_vals("balance-sheet", "reserve")
        eqc, eqc_p = _row_vals("balance-sheet", "equity capital")
        if eqc is None:
            eqc, eqc_p = _row_vals("balance-sheet", "share capital")
        if borr is not None and res is not None and eqc is not None and (eqc + res) > 0:
            out["Debt to equity"] = round(borr / (eqc + res), 2)
        if borr_p is not None and res_p is not None and eqc_p is not None and (eqc_p + res_p) > 0:
            out["DE_Prev"] = round(borr_p / (eqc_p + res_p), 2)

        # Top-ratios card: ROCE + quarterly growth
        ratios = {}
        top = soup.find(id="top-ratios")
        if top:
            for li in top.find_all("li"):
                nm = li.find("span", class_="name")
                val = li.find("span", class_="number")
                if nm and val:
                    ratios[nm.text.strip().replace(":", "")] = val.text.strip().replace("%", "").replace(",", "")
        if ratios.get("ROCE"):
            try:
                out["ROCE"] = float(ratios["ROCE"])
            except Exception:
                pass
        for src_keys, dst in ((["YOY Quarterly profit growth", "Quarterly profit growth"], "Qtr Profit Var %"),
                              (["YOY Quarterly sales growth", "Quarterly sales growth"], "Qtr Sales Var %")):
            for k in src_keys:
                if ratios.get(k):
                    try:
                        out[dst] = float(ratios[k])
                        break
                    except Exception:
                        pass
        return out or None

    return _cached(f"screener_rff_{symbol.upper()}", ttl, _fetch)


# =============================================================================
# SECTION 3 — STOCK FUNDAMENTALS
# =============================================================================

def fetch_stock_fundamentals(symbol: str, ttl: int = 3600) -> dict:
    """
    Fetch key fundamental metrics for an NSE stock via yfinance.

    Parameters
    ----------
    symbol : NSE-format ticker e.g. "RELIANCE.NS", "INFY.NS"
    ttl    : cache TTL in seconds (default 1 hour)

    Returns
    -------
    dict with cleaned fundamental metrics, or {} on failure.

    Keys returned
    -------------
    symbol, name, sector, industry,
    price, prev_close, market_cap (Cr),
    pe_ratio, forward_pe, pb_ratio,
    ev_ebitda, ps_ratio,
    eps_ttm, eps_forward,
    revenue_ttm (Cr), net_income_ttm (Cr),
    profit_margin (%), operating_margin (%),
    roe (%), roa (%),
    debt_equity, current_ratio,
    dividend_yield (%), payout_ratio (%),
    week52_high, week52_low, week52_vs_high (%),
    beta, avg_volume, float_shares (Cr),
    fetched_at (IST timestamp string)
    """
    cache_key = f"fundamentals_{symbol.upper()}"

    def _fetch():
        clean_sym = symbol.strip().upper()
        is_indian = not clean_sym.startswith("^") and (clean_sym.endswith(".NS") or clean_sym.endswith(".BO") or ".NS" in clean_sym or ".BO" in clean_sym or len(clean_sym.split('.')) <= 1)
        screener_data = None
        if is_indian:
            try:
                screener_data = _fetch_screener_fundamentals(symbol)
            except Exception as se:
                logger.warning("Screener fallback fetch failed for %s: %s", symbol, se)

        try:
            logger.info("Fetching fundamentals for %s", symbol)
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # 52W vs high: % below 52-week high (negative means below)
            week52_high = _safe_float(info.get("fiftyTwoWeekHigh"), 0)
            price = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"), 0)
            week52_vs_high = None
            if week52_high and week52_high > 0 and price:
                week52_vs_high = round((price - week52_high) / week52_high * 100, 2)

            result = {
                # Identity
                "symbol":          symbol.upper(),
                "name":            info.get("longName") or info.get("shortName") or "",
                "sector":          info.get("sector", ""),
                "industry":        info.get("industry", ""),

                # Price
                "price":           price,
                "prev_close":      _safe_float(info.get("previousClose"), 0),
                "market_cap":      _to_cr(info.get("marketCap")),

                # Valuation multiples
                "pe_ratio":        _safe_float(info.get("trailingPE")),
                "forward_pe":      _safe_float(info.get("forwardPE")),
                "pb_ratio":        _safe_float(info.get("priceToBook")),
                "ev_ebitda":       _safe_float(info.get("enterpriseToEbitda")),
                "ps_ratio":        _safe_float(info.get("priceToSalesTrailing12Months")),

                # Earnings
                "eps_ttm":         _safe_float(info.get("trailingEps")),
                "eps_forward":     _safe_float(info.get("forwardEps")),

                # Financials (in Crores)
                "revenue_ttm":     _to_cr(info.get("totalRevenue")),
                "net_income_ttm":  _to_cr(info.get("netIncomeToCommon")),

                # Margins & returns (as %)
                "profit_margin":   _pct(info.get("profitMargins")),
                "operating_margin": _pct(info.get("operatingMargins")),
                "roe":             _pct(info.get("returnOnEquity")),
                "roa":             _pct(info.get("returnOnAssets")),

                # Leverage & liquidity
                "debt_equity":     _safe_float(info.get("debtToEquity")),
                "current_ratio":   _safe_float(info.get("currentRatio")),

                # Dividends (as %)
                "dividend_yield":  _pct(info.get("dividendYield")),
                "payout_ratio":    _pct(info.get("payoutRatio")),
                "promoter_holding": _pct(info.get("heldPercentInsiders")),

                # Growth (as %)
                "earnings_growth":  _pct(info.get("earningsGrowth")),
                "revenue_growth":   _pct(info.get("revenueGrowth")),

                # 52-week range
                "week52_high":     week52_high,
                "week52_low":      _safe_float(info.get("fiftyTwoWeekLow"), 0),
                "week52_vs_high":  week52_vs_high,

                # Market data
                "beta":            _safe_float(info.get("beta")),
                "avg_volume":      _safe_float(info.get("averageVolume"), 0),
                "float_shares":    _to_cr(info.get("floatShares")),

                "fetched_at":      _ist_now_str(),
            }

            # If Indian equity, override key metrics with Screener.in high-accuracy data
            if is_indian and screener_data:
                logger.info("Enriching %s with Screener.in data", symbol)
                if screener_data.get("promoter_holding") is not None:
                    result["promoter_holding"] = screener_data["promoter_holding"]
                if screener_data.get("debt_equity") is not None:
                    result["debt_equity"] = screener_data["debt_equity"]
                if screener_data.get("roe") is not None:
                    result["roe"] = screener_data["roe"]
                if screener_data.get("roce") is not None:
                    result["roce"] = screener_data["roce"]
                if screener_data.get("pe_ratio") is not None:
                    result["pe_ratio"] = screener_data["pe_ratio"]
                if screener_data.get("dividend_yield") is not None:
                    result["dividend_yield"] = screener_data["dividend_yield"]
                if screener_data.get("pb_ratio") is not None:
                    result["pb_ratio"] = screener_data["pb_ratio"]
                if screener_data.get("market_cap") is not None and screener_data["market_cap"] > 0:
                    result["market_cap"] = screener_data["market_cap"]
                if screener_data.get("earnings_growth") is not None:
                    result["earnings_growth"] = screener_data["earnings_growth"]
                if screener_data.get("revenue_growth") is not None:
                    result["revenue_growth"] = screener_data["revenue_growth"]

            logger.info(
                "Fundamentals OK: %s | P/E=%.1f | ROE=%.1f%% | Market Cap=%.0f Cr",
                symbol,
                result["pe_ratio"] or 0,
                result["roe"] or 0,
                result["market_cap"] or 0,
            )
            return result

        except Exception as exc:
            logger.error("yfinance fetch_stock_fundamentals(%s) failed: %s", symbol, exc)
            if is_indian and screener_data:
                logger.info("Falling back to pure Screener.in data for %s", symbol)
                price = screener_data.get("price", 0.0)
                result = {
                    "symbol":          symbol.upper(),
                    "name":            screener_data.get("name", ""),
                    "sector":          "",
                    "industry":        "",
                    "price":           price,
                    "prev_close":      price,
                    "market_cap":      screener_data.get("market_cap"),
                    "pe_ratio":        screener_data.get("pe_ratio"),
                    "forward_pe":      None,
                    "pb_ratio":        screener_data.get("pb_ratio"),
                    "ev_ebitda":       None,
                    "ps_ratio":        None,
                    "eps_ttm":         None,
                    "eps_forward":     None,
                    "revenue_ttm":     None,
                    "net_income_ttm":  None,
                    "profit_margin":   None,
                    "operating_margin": None,
                    "roe":             screener_data.get("roe"),
                    "roa":             None,
                    "debt_equity":     screener_data.get("debt_equity"),
                    "current_ratio":   None,
                    "dividend_yield":  screener_data.get("dividend_yield"),
                    "payout_ratio":    None,
                    "promoter_holding": screener_data.get("promoter_holding"),
                    "week52_high":     None,
                    "week52_low":      None,
                    "week52_vs_high":  None,
                    "beta":            None,
                    "avg_volume":      0.0,
                    "float_shares":    None,
                    "fetched_at":      _ist_now_str(),
                }
                # ROCE is unique to Screener data but we store it for recovery conviction calculations
                result["roce"] = screener_data.get("roce")
                result["earnings_growth"] = screener_data.get("earnings_growth")
                result["revenue_growth"] = screener_data.get("revenue_growth")
                return result
            return {}

    return _cached(cache_key, ttl, _fetch)


# =============================================================================
# SECTION 4 — FINANCIAL STATEMENTS
# =============================================================================

def _flatten_multiindex_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flatten MultiIndex columns produced by some yfinance versions.
    E.g. ('Total Revenue', '') → 'Total Revenue'
    """
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [" ".join(str(c) for c in col).strip() if isinstance(col, tuple) else str(col)
                      for col in df.columns]
    return df


def _convert_df_to_cr(df: pd.DataFrame) -> pd.DataFrame:
    """
    Divide all numeric columns by 1e7 to convert from Rupees to Crores.
    Non-numeric columns (like 'Period') are left as-is.
    """
    for col in df.columns:
        if col == "Period":
            continue
        try:
            df[col] = pd.to_numeric(df[col], errors="coerce") / 1e7
        except Exception:
            pass
    return df


def _process_statement(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Transpose a yfinance statement DataFrame so dates become rows,
    reset the index, rename the index column to 'Period', and convert to Crores.

    Returns empty DataFrame if input is empty or None.
    """
    try:
        if raw_df is None or raw_df.empty:
            return pd.DataFrame()

        # Transpose: yfinance returns metrics as rows and dates as columns
        df = raw_df.T.copy()
        df = _flatten_multiindex_columns(df)
        df = df.reset_index()

        # Rename the transposed index column to 'Period'
        # After T + reset_index, the first column is the date index
        first_col = df.columns[0]
        df = df.rename(columns={first_col: "Period"})

        # Convert Period to readable string if it's datetime
        if pd.api.types.is_datetime64_any_dtype(df["Period"]):
            df["Period"] = df["Period"].dt.strftime("%Y-%m-%d")
        else:
            df["Period"] = df["Period"].astype(str)

        # Convert numeric columns to Crores
        df = _convert_df_to_cr(df)
        return df.reset_index(drop=True)

    except Exception as exc:
        logger.error("_process_statement failed: %s", exc)
        return pd.DataFrame()


def fetch_financial_statements(symbol: str, ttl: int = 86400) -> dict:
    """
    Fetch annual financial statements for an NSE stock.

    Parameters
    ----------
    symbol : NSE-format ticker e.g. "RELIANCE.NS"
    ttl    : cache TTL in seconds (default 24 hours)

    Returns
    -------
    dict with keys:
        "income"   : pd.DataFrame — Income Statement (transposed, in Crores)
        "balance"  : pd.DataFrame — Balance Sheet (transposed, in Crores)
        "cashflow" : pd.DataFrame — Cash Flow Statement (transposed, in Crores)
    Returns dict with empty DataFrames on failure.
    """
    cache_key = f"statements_{symbol.upper()}"

    def _fetch():
        logger.info("Fetching financial statements for %s", symbol)
        empty = {"income": pd.DataFrame(), "balance": pd.DataFrame(), "cashflow": pd.DataFrame()}
        try:
            ticker = yf.Ticker(symbol)

            income_df   = _process_statement(ticker.financials)
            balance_df  = _process_statement(ticker.balance_sheet)
            cashflow_df = _process_statement(ticker.cashflow)

            logger.info(
                "Statements OK: %s | income=%d rows, balance=%d rows, cashflow=%d rows",
                symbol, len(income_df), len(balance_df), len(cashflow_df),
            )
            return {
                "income":   income_df,
                "balance":  balance_df,
                "cashflow": cashflow_df,
            }

        except Exception as exc:
            logger.error("fetch_financial_statements(%s) failed: %s", symbol, exc)
            return empty

    return _cached(cache_key, ttl, _fetch)


# =============================================================================
# SECTION 5 — QUARTERLY RESULTS
# =============================================================================

def fetch_quarterly_results(symbol: str, ttl: int = 86400) -> pd.DataFrame:
    """
    Fetch quarterly P&L history for an NSE stock.

    Parameters
    ----------
    symbol : NSE-format ticker e.g. "RELIANCE.NS"
    ttl    : cache TTL in seconds (default 24 hours)

    Returns
    -------
    pd.DataFrame with quarterly financials (rows = quarters, columns = metrics in Crores).
    Returns empty DataFrame on failure.
    """
    cache_key = f"quarterly_{symbol.upper()}"

    def _fetch():
        logger.info("Fetching quarterly results for %s", symbol)
        try:
            ticker = yf.Ticker(symbol)
            qf = ticker.quarterly_financials

            if qf is None or qf.empty:
                logger.warning("No quarterly data returned for %s", symbol)
                return pd.DataFrame()

            df = _process_statement(qf)
            logger.info("Quarterly results OK: %s | %d quarters", symbol, len(df))
            return df

        except Exception as exc:
            logger.error("fetch_quarterly_results(%s) failed: %s", symbol, exc)
            return pd.DataFrame()

    return _cached(cache_key, ttl, _fetch)


# =============================================================================
# SECTION 6 — FUNDAMENTAL SCREENER
# =============================================================================

_DEFAULT_CRITERIA: Dict[str, tuple] = {
    "pe_ratio":   (0, 30),
    "roe":        (15, 999),
    "debt_equity": (0, 1.5),
}


def screen_fundamentals(
    symbols: List[str],
    criteria: Optional[Dict[str, tuple]] = None,
    ttl: int = 3600,
) -> pd.DataFrame:
    """
    Screen a list of NSE stocks against fundamental criteria.

    Parameters
    ----------
    symbols  : list of NSE tickers e.g. ["RELIANCE.NS", "TCS.NS", ...]
               Capped at 50 symbols per call to avoid long waits.
    criteria : dict of {metric_key: (min, max)} range filters.
               Default: P/E 0-30, ROE 15%+, D/E 0-1.5
    ttl      : cache TTL for individual stock lookups (default 1 hour)

    Returns
    -------
    pd.DataFrame of stocks passing all criteria, sorted by ROE descending.
    Returns empty DataFrame if no stocks pass or on failure.
    """
    if criteria is None:
        criteria = _DEFAULT_CRITERIA

    # Cap at 50 symbols
    if len(symbols) > 50:
        logger.warning("screen_fundamentals: capping at 50 symbols (got %d)", len(symbols))
        symbols = symbols[:50]

    records = []
    for i, sym in enumerate(symbols, 1):
        if i % 10 == 0:
            logger.info("screen_fundamentals: processed %d / %d symbols", i, len(symbols))
        try:
            info = fetch_stock_fundamentals(sym, ttl=ttl)
            if not info:
                continue
            records.append(info)
        except Exception as exc:
            logger.error("screen_fundamentals: error on %s: %s", sym, exc)
            continue

    if not records:
        logger.info("screen_fundamentals: no data returned for any symbol")
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # Apply criteria filters
    for metric, (min_val, max_val) in criteria.items():
        if metric not in df.columns:
            logger.warning("screen_fundamentals: metric '%s' not in data, skipping filter", metric)
            continue
        # Convert to numeric; non-numeric become NaN and are excluded
        df[metric] = pd.to_numeric(df[metric], errors="coerce")
        df = df[
            df[metric].notna() &
            (df[metric] >= min_val) &
            (df[metric] <= max_val)
        ]

    if df.empty:
        logger.info("screen_fundamentals: no stocks passed the criteria filters")
        return pd.DataFrame()

    # Sort by ROE descending
    if "roe" in df.columns:
        df = df.sort_values("roe", ascending=False)

    logger.info(
        "screen_fundamentals: %d / %d symbols passed criteria",
        len(df), len(symbols),
    )
    return df.reset_index(drop=True)


# =============================================================================
# SECTION 7 — VALUATION SCORECARD
# =============================================================================

def get_valuation_scorecard(info_dict: dict) -> dict:
    """
    Score a stock's fundamentals and return a buy/hold/avoid rating.

    Parameters
    ----------
    info_dict : dict returned by fetch_stock_fundamentals()

    Scoring rubric (total out of 10 points)
    ----------------------------------------
    P/E ratio    : <20 → 2 pts | 20-30 → 1 pt | >30 → 0 pt
    ROE          : >20% → 2 pts | 15-20% → 1 pt | <15% → 0 pt
    D/E ratio    : <0.5 → 2 pts | 0.5-1 → 1 pt | >1 → 0 pt
    Profit margin: >15% → 2 pts | 8-15% → 1 pt | <8% → 0 pt
    EPS growth   : >20% → 2 pts | 10-20% → 1 pt | <10% → 0 pt
                   (forward EPS vs TTM EPS)

    Rating
    ------
    8-10 → STRONG BUY
    6-7  → BUY
    4-5  → HOLD
    <4   → AVOID

    Returns
    -------
    dict with keys: score (int), rating (str), breakdown (dict of metric → points)
    """
    breakdown: Dict[str, int] = {}
    total = 0

    try:
        # --- P/E ratio ---
        pe = _safe_float(info_dict.get("pe_ratio"))
        if pe is not None and pe > 0:
            if pe < 20:
                pts = 2
            elif pe <= 30:
                pts = 1
            else:
                pts = 0
        else:
            pts = 0
        breakdown["pe_ratio"] = pts
        total += pts

        # --- ROE ---
        roe = _safe_float(info_dict.get("roe"))
        if roe is not None:
            if roe > 20:
                pts = 2
            elif roe >= 15:
                pts = 1
            else:
                pts = 0
        else:
            pts = 0
        breakdown["roe"] = pts
        total += pts

        # --- Debt / Equity ---
        de = _safe_float(info_dict.get("debt_equity"))
        if de is not None and de >= 0:
            if de < 0.5:
                pts = 2
            elif de <= 1.0:
                pts = 1
            else:
                pts = 0
        else:
            pts = 0
        breakdown["debt_equity"] = pts
        total += pts

        # --- Profit margin ---
        pm = _safe_float(info_dict.get("profit_margin"))
        if pm is not None:
            if pm > 15:
                pts = 2
            elif pm >= 8:
                pts = 1
            else:
                pts = 0
        else:
            pts = 0
        breakdown["profit_margin"] = pts
        total += pts

        # --- EPS growth (forward vs TTM) ---
        eps_ttm     = _safe_float(info_dict.get("eps_ttm"))
        eps_forward = _safe_float(info_dict.get("eps_forward"))
        if eps_ttm and eps_forward and eps_ttm > 0:
            eps_growth_pct = (eps_forward - eps_ttm) / abs(eps_ttm) * 100
            if eps_growth_pct > 20:
                pts = 2
            elif eps_growth_pct >= 10:
                pts = 1
            else:
                pts = 0
        elif eps_ttm and eps_forward and eps_ttm < 0 and eps_forward > 0:
            # Turnaround case — positive forward EPS from negative TTM
            pts = 1
        else:
            pts = 0
        breakdown["eps_growth"] = pts
        total += pts

        # --- Determine rating ---
        if total >= 8:
            rating = "STRONG BUY"
        elif total >= 6:
            rating = "BUY"
        elif total >= 4:
            rating = "HOLD"
        else:
            rating = "AVOID"

        return {
            "score":     total,
            "rating":    rating,
            "breakdown": breakdown,
        }

    except Exception as exc:
        logger.error("get_valuation_scorecard failed: %s", exc)
        return {"score": 0, "rating": "AVOID", "breakdown": {}}


# =============================================================================
# SECTION 8 — GEMINI REPORT FORMATTER
# =============================================================================

def format_fundamentals_for_report(info_dict: dict) -> str:
    """
    Format fundamental data as a compact plain-text string for Gemini prompt injection.

    Parameters
    ----------
    info_dict : dict returned by fetch_stock_fundamentals()

    Returns
    -------
    Single-line pipe-delimited summary string, e.g.:
    "Symbol: RELIANCE.NS | Name: Reliance Industries | Sector: Energy | ..."
    Returns empty string on failure.
    """
    try:
        if not info_dict:
            return ""

        def _fmt(val, suffix="", decimals=2, na="N/A"):
            if val is None:
                return na
            try:
                return f"{round(float(val), decimals)}{suffix}"
            except (TypeError, ValueError):
                return na

        # Build the scorecard inline
        scorecard = get_valuation_scorecard(info_dict)

        parts = [
            f"Symbol: {info_dict.get('symbol', 'N/A')}",
            f"Name: {info_dict.get('name', 'N/A')}",
            f"Sector: {info_dict.get('sector', 'N/A')}",
            f"Industry: {info_dict.get('industry', 'N/A')}",
            f"Price: {_fmt(info_dict.get('price'))}",
            f"Market Cap: {_fmt(info_dict.get('market_cap'))} Cr",
            f"P/E: {_fmt(info_dict.get('pe_ratio'), decimals=1)}",
            f"Fwd P/E: {_fmt(info_dict.get('forward_pe'), decimals=1)}",
            f"P/B: {_fmt(info_dict.get('pb_ratio'), decimals=1)}",
            f"EV/EBITDA: {_fmt(info_dict.get('ev_ebitda'), decimals=1)}",
            f"P/S: {_fmt(info_dict.get('ps_ratio'), decimals=1)}",
            f"EPS TTM: {_fmt(info_dict.get('eps_ttm'))}",
            f"EPS Fwd: {_fmt(info_dict.get('eps_forward'))}",
            f"Revenue TTM: {_fmt(info_dict.get('revenue_ttm'))} Cr",
            f"Net Income TTM: {_fmt(info_dict.get('net_income_ttm'))} Cr",
            f"Profit Margin: {_fmt(info_dict.get('profit_margin'))}%",
            f"Operating Margin: {_fmt(info_dict.get('operating_margin'))}%",
            f"ROE: {_fmt(info_dict.get('roe'))}%",
            f"ROA: {_fmt(info_dict.get('roa'))}%",
            f"D/E: {_fmt(info_dict.get('debt_equity'))}",
            f"Current Ratio: {_fmt(info_dict.get('current_ratio'))}",
            f"Div Yield: {_fmt(info_dict.get('dividend_yield'))}%",
            f"52W High: {_fmt(info_dict.get('week52_high'))}",
            f"52W Low: {_fmt(info_dict.get('week52_low'))}",
            f"52W vs High: {_fmt(info_dict.get('week52_vs_high'))}%",
            f"Beta: {_fmt(info_dict.get('beta'))}",
            f"Scorecard: {scorecard['score']}/10 ({scorecard['rating']})",
            f"Fetched: {info_dict.get('fetched_at', 'N/A')}",
        ]

        return " | ".join(parts)

    except Exception as exc:
        logger.error("format_fundamentals_for_report failed: %s", exc)
        return ""


# =============================================================================
# QUICK SELF-TEST  (python fundamental_hub.py)
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-8s %(name)s — %(message)s",
    )

    TEST_SYMBOLS = ["RELIANCE.NS", "TCS.NS"]

    for sym in TEST_SYMBOLS:
        print(f"\n{'='*70}")
        print(f"  TESTING: {sym}")
        print(f"{'='*70}")

        # --- Stock fundamentals ---
        info = fetch_stock_fundamentals(sym)
        if info:
            print(f"  Name        : {info.get('name')}")
            print(f"  Sector      : {info.get('sector')}")
            print(f"  Price       : {info.get('price')}")
            print(f"  Market Cap  : {info.get('market_cap')} Cr")
            print(f"  P/E         : {info.get('pe_ratio')}")
            print(f"  Forward P/E : {info.get('forward_pe')}")
            print(f"  P/B         : {info.get('pb_ratio')}")
            print(f"  ROE         : {info.get('roe')}%")
            print(f"  D/E         : {info.get('debt_equity')}")
            print(f"  Profit Mgn  : {info.get('profit_margin')}%")
            print(f"  Revenue TTM : {info.get('revenue_ttm')} Cr")
            print(f"  EPS TTM     : {info.get('eps_ttm')}")
            print(f"  EPS Fwd     : {info.get('eps_forward')}")
            print(f"  52W High    : {info.get('week52_high')}")
            print(f"  52W vs High : {info.get('week52_vs_high')}%")
            print(f"  Fetched At  : {info.get('fetched_at')}")
        else:
            print("  [!] No data returned.")

        # --- Valuation scorecard ---
        if info:
            scorecard = get_valuation_scorecard(info)
            print(f"\n  Scorecard   : {scorecard['score']}/10 — {scorecard['rating']}")
            for metric, pts in scorecard["breakdown"].items():
                print(f"    {metric:<18} : {pts} pts")

        # --- Gemini report string ---
        if info:
            report_str = format_fundamentals_for_report(info)
            print(f"\n  Report Str  :\n  {report_str}")

        # --- Financial statements (first 2 rows) ---
        stmts = fetch_financial_statements(sym)
        for key in ("income", "balance", "cashflow"):
            df = stmts.get(key, pd.DataFrame())
            if not df.empty:
                print(f"\n  {key.upper()} STATEMENT (first 2 rows, selected cols):")
                preview_cols = ["Period"] + [c for c in df.columns if c != "Period"][:4]
                print(df[preview_cols].head(2).to_string(index=False))
            else:
                print(f"\n  {key.upper()} STATEMENT: No data.")

        # --- Quarterly results ---
        qdf = fetch_quarterly_results(sym)
        if not qdf.empty:
            print(f"\n  QUARTERLY RESULTS (latest 4 quarters, first 3 cols):")
            preview_cols = ["Period"] + [c for c in qdf.columns if c != "Period"][:2]
            print(qdf[preview_cols].head(4).to_string(index=False))
        else:
            print("\n  QUARTERLY RESULTS: No data.")

    # --- Screener demo ---
    print(f"\n{'='*70}")
    print("  SCREENER TEST — Nifty blue chips (default criteria)")
    print(f"{'='*70}")
    watchlist = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    ]
    screened = screen_fundamentals(watchlist)
    if not screened.empty:
        display_cols = ["symbol", "name", "pe_ratio", "roe", "debt_equity", "profit_margin"]
        display_cols = [c for c in display_cols if c in screened.columns]
        print(screened[display_cols].to_string(index=False))
    else:
        print("  No stocks passed the default criteria.")

    print("\nDone.")
