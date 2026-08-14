"""
fundamental_replay.py — Historical fundamentals via yfinance, cached.

Sister module to chartink_replay.py. Phase 2 of Path 2: replicates the
matcher's Screener.in conviction filter using yfinance's quarterly
statements (which ARE point-in-time historical data — when you ask for
'2025-Q1 financials of HDFCBANK' yfinance returns the actually-reported
numbers for that quarter regardless of when you fetch).

Usage:
    fund = fundamentals_as_of("HDFCBANK", "2025-09-15")
    score = conviction_score_as_of("HDFCBANK", "2025-09-15")

For each (symbol, anchor_date), we:
  1. Pull the quarterly income/balance-sheet statements (cached to parquet)
  2. Find the latest reporting quarter ENDING on or before `anchor_date`
  3. Compute: profit_growth_q (YoY), sales_growth_q, ROE, ROCE, D/E,
     market_cap (Cr), div_yield, promoter_pct
  4. Apply the conviction-score formula from
     brute_force_match_pro.calculate_conviction_score

Cache layout:
  data/fundamentals_cache/<SYMBOL>_income.parquet
  data/fundamentals_cache/<SYMBOL>_balance.parquet
  data/fundamentals_cache/<SYMBOL>_meta.json   (info: shares_outstanding, etc.)

Promoter % is the one metric yfinance doesn't expose — we use today's
snapshot from MASTER_scan_results.csv when available, else default to
the matcher's threshold-passing value (50%).
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


# ─── Paths ────────────────────────────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "data", "fundamentals_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

CACHE_TTL_SECONDS = 30 * 24 * 3600   # 30 days — fundamentals only update quarterly

# Promoter snapshot from the master scan results — today's value used as a
# stand-in for historical anchors (acknowledged minor look-ahead, ~1-3pp/yr drift).
_PROMOTER_SNAPSHOT_FILE = os.path.join(HERE, "MASTER_scan_results.csv")
_promoter_snapshot: Optional[dict[str, float]] = None


def _load_promoter_snapshot() -> dict[str, float]:
    """Read today's promoter holdings from MASTER_scan_results.csv and FINAL_WATCHLIST.csv. Cached."""
    global _promoter_snapshot
    if _promoter_snapshot is not None:
        return _promoter_snapshot
    out: dict[str, float] = {}
    
    # Files to check in order (later files will overwrite earlier ones, so watchlist overrides master)
    files_to_load = [
        _PROMOTER_SNAPSHOT_FILE,
        os.path.join(HERE, "FINAL_WATCHLIST.csv")
    ]
    
    for file_path in files_to_load:
        if not os.path.exists(file_path):
            continue
        try:
            df = pd.read_csv(file_path, dtype=str)
            sym_col = next((c for c in df.columns
                              if c.lower() in ("symbol", "nsecode", "name", "ticker")),
                             None)
            prom_col = next((c for c in df.columns
                                if "promoter" in c.lower() and "holding" in c.lower()),
                              None)
            if sym_col and prom_col:
                for _, row in df.iterrows():
                    sym = str(row[sym_col]).strip().upper()
                    # Clean symbol (remove exchange prefix)
                    sym = sym.replace("NSE:", "").replace("BSE:", "").strip()
                    try:
                        pct = float(str(row[prom_col]).replace(",", "").replace("%", ""))
                        if sym and not np.isnan(pct):
                            out[sym] = pct
                    except Exception:
                        continue
        except Exception as e:
            logger.warning("promoter snapshot load failed for %s: %s", file_path, e)
            
    _promoter_snapshot = out
    return out


# ─── Symbol normalization ─────────────────────────────────────────────────────
def _yf_ticker(symbol: str) -> str:
    s = str(symbol).strip().upper().replace("NSE:", "").replace("BSE:", "")
    if s.endswith(".NS") or s.endswith(".BO"):
        s = s[:-3]
    for suf in ("-EQ", "-BE", "-SM", "-ST", "-BZ"):
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    if s.startswith("^"):
        return s
    return f"{s}.NS"


def _clean(symbol: str) -> str:
    """Canonical symbol (no .NS, no prefixes) for cache filenames + lookups."""
    yf_t = _yf_ticker(symbol)
    if yf_t.startswith("^"):
        return yf_t
    return yf_t[:-3] if yf_t.endswith(".NS") else yf_t


# ─── Cache layer ──────────────────────────────────────────────────────────────
def _cache_paths(symbol: str) -> dict:
    base = _clean(symbol)
    return {
        "income":  os.path.join(CACHE_DIR, f"{base}_income.parquet"),
        "balance": os.path.join(CACHE_DIR, f"{base}_balance.parquet"),
        "meta":    os.path.join(CACHE_DIR, f"{base}_meta.json"),
    }


def _is_fresh(path: str) -> bool:
    if not os.path.exists(path):
        return False
    age = time.time() - os.path.getmtime(path)
    return age < CACHE_TTL_SECONDS


def _read_parquet(path: str) -> pd.DataFrame:
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()


def _write_parquet(path: str, df: pd.DataFrame) -> None:
    try:
        df.to_parquet(path)
    except Exception as e:
        logger.warning("parquet write failed for %s: %s", path, e)


def _fetch_statements(symbol: str, force: bool = False) -> dict:
    """Pull quarterly financials + balance sheet + meta from yfinance.
    Cached via parquet (TTL 30 days). Returns dict with three keys: income,
    balance, meta. Empty DataFrames / dict on failure."""
    paths = _cache_paths(symbol)
    out = {"income": pd.DataFrame(), "balance": pd.DataFrame(), "meta": {}}

    # Cache hit
    if (not force and _is_fresh(paths["income"]) and _is_fresh(paths["balance"])
            and os.path.exists(paths["meta"])):
        out["income"]  = _read_parquet(paths["income"])
        out["balance"] = _read_parquet(paths["balance"])
        try:
            with open(paths["meta"], "r", encoding="utf-8") as f:
                out["meta"] = json.load(f)
        except Exception:
            out["meta"] = {}
        return out

    # Network fetch
    yf_t = _yf_ticker(symbol)
    try:
        tk = yf.Ticker(yf_t)
        q_inc = tk.quarterly_financials
        q_bs  = tk.quarterly_balance_sheet
        if q_inc is not None and not q_inc.empty:
            out["income"] = q_inc
            _write_parquet(paths["income"], q_inc)
        if q_bs is not None and not q_bs.empty:
            out["balance"] = q_bs
            _write_parquet(paths["balance"], q_bs)
        # Meta: snapshot of today's info.
        try:
            info = tk.info or {}
            meta = {
                "marketCap":          info.get("marketCap"),
                "sharesOutstanding":  info.get("sharesOutstanding"),
                "trailingPE":         info.get("trailingPE"),
                "dividendYield":      info.get("dividendYield"),
                "fetched_at":         datetime.now().isoformat(timespec="seconds"),
            }
            out["meta"] = meta
            with open(paths["meta"], "w", encoding="utf-8") as f:
                json.dump(meta, f, default=str)
        except Exception as e:
            logger.debug("meta fetch failed for %s: %s", symbol, e)
    except Exception as e:
        logger.warning("statement fetch failed for %s: %s", symbol, e)
    return out


# ─── Quarter lookup ───────────────────────────────────────────────────────────
def _latest_quarter_on_or_before(df: pd.DataFrame, anchor: str
                                    ) -> tuple[Optional[pd.Timestamp], pd.Series]:
    """yfinance returns statements as DataFrame indexed by metric, columns
    are quarter-end dates. Find the most recent column ≤ anchor."""
    if df is None or df.empty:
        return None, pd.Series(dtype=float)
    try:
        cols = pd.to_datetime(df.columns, errors="coerce")
    except Exception:
        return None, pd.Series(dtype=float)
    valid_mask = ~pd.isna(cols)
    if not valid_mask.any():
        return None, pd.Series(dtype=float)
    anchor_ts = pd.Timestamp(anchor)
    valid_cols = cols[valid_mask]
    eligible = valid_cols[valid_cols <= anchor_ts]
    if len(eligible) == 0:
        return None, pd.Series(dtype=float)
    target_date = eligible.max()
    # Find original column label that matches target_date
    for orig in df.columns:
        try:
            if pd.to_datetime(orig) == target_date:
                return target_date, df[orig]
        except Exception:
            continue
    return None, pd.Series(dtype=float)


def _row_value(series: pd.Series, *keys) -> float:
    """Extract first matching row from a yfinance statement Series."""
    if series is None or len(series) == 0:
        return float("nan")
    for k in keys:
        for idx in series.index:
            if str(idx).strip().lower() == k.strip().lower():
                v = series[idx]
                try:
                    return float(v)
                except (TypeError, ValueError):
                    continue
    return float("nan")


# ─── Public API ───────────────────────────────────────────────────────────────
def fundamentals_as_of(symbol: str, anchor: str) -> dict:
    """Return computed metrics as of the most recent quarter ≤ anchor.

    Output keys: profit_growth_qtr_pct, sales_growth_qtr_pct, roe_pct,
    roce_pct, debt_to_equity, mar_cap_cr, div_yield_pct, promoter_pct,
    quarter_end (str), ok (bool).
    """
    out = {
        "profit_growth_qtr_pct": float("nan"),
        "sales_growth_qtr_pct":  float("nan"),
        "roe_pct":               float("nan"),
        "roce_pct":               float("nan"),
        "debt_to_equity":        float("nan"),
        "mar_cap_cr":             float("nan"),
        "div_yield_pct":         float("nan"),
        "promoter_pct":           float("nan"),
        "quarter_end":           None,
        "net_income":            float("nan"),
        "ok":                    False,
    }
    stmts = _fetch_statements(symbol)
    inc = stmts["income"]
    bs  = stmts["balance"]
    meta = stmts["meta"]

    # Find latest reported quarter ≤ anchor
    q_end, inc_row = _latest_quarter_on_or_before(inc, anchor)
    _,     bs_row  = _latest_quarter_on_or_before(bs,  anchor)
    if q_end is None or inc_row.empty:
        return out
    out["quarter_end"] = q_end.strftime("%Y-%m-%d")

    # ─── Profit growth (YoY): find quarter ~365 days before q_end
    yoy_target = q_end - pd.Timedelta(days=365)
    _, inc_yoy = _latest_quarter_on_or_before(inc, yoy_target.strftime("%Y-%m-%d"))

    net_inc_q = _row_value(inc_row, "Net Income", "Net Income From Continuing Operations")
    net_inc_yoy = _row_value(inc_yoy, "Net Income", "Net Income From Continuing Operations")
    if not (np.isnan(net_inc_q) or np.isnan(net_inc_yoy)) and net_inc_yoy != 0:
        out["profit_growth_qtr_pct"] = round((net_inc_q - net_inc_yoy) / abs(net_inc_yoy) * 100, 2)

    rev_q = _row_value(inc_row, "Total Revenue", "Operating Revenue")
    rev_yoy = _row_value(inc_yoy, "Total Revenue", "Operating Revenue")
    if not (np.isnan(rev_q) or np.isnan(rev_yoy)) and rev_yoy != 0:
        out["sales_growth_qtr_pct"] = round((rev_q - rev_yoy) / abs(rev_yoy) * 100, 2)

    # ─── ROE = annualized Net Income / Stockholders Equity
    equity = _row_value(bs_row, "Stockholders Equity",
                          "Common Stock Equity", "Total Equity Gross Minority Interest")
    out["net_income"] = net_inc_q
    if not (np.isnan(net_inc_q) or np.isnan(equity)) and equity > 0:
        # Annualize quarterly net income (×4), divide by equity for ROE %
        out["roe_pct"] = round(net_inc_q * 4 / equity * 100, 2)

    # ─── ROCE = EBIT / Capital Employed (≈ TotalAssets - CurrentLiabilities)
    ebit = _row_value(inc_row, "EBIT", "Operating Income", "Pretax Income")
    total_assets = _row_value(bs_row, "Total Assets")
    current_liab = _row_value(bs_row, "Current Liabilities", "Total Current Liabilities")
    if not np.isnan(ebit) and not np.isnan(total_assets) and not np.isnan(current_liab):
        cap_emp = total_assets - current_liab
        if cap_emp > 0:
            out["roce_pct"] = round(ebit * 4 / cap_emp * 100, 2)

    # ─── D/E
    total_debt = _row_value(bs_row, "Total Debt", "Net Debt", "Long Term Debt")
    if not (np.isnan(total_debt) or np.isnan(equity)) and equity > 0:
        out["debt_to_equity"] = round(total_debt / equity, 2)

    # ─── Market Cap (Cr) — historical price × today's shares outstanding
    try:
        import data_provider as _dp
        df_d = _dp.fetch_ohlcv(symbol, period="2y", interval="1d")
        if not df_d.empty and "Close" in df_d.columns:
            sliced = df_d.loc[:anchor]
            if not sliced.empty:
                price = float(sliced["Close"].iloc[-1])
                shares = meta.get("sharesOutstanding")
                if shares and price > 0:
                    out["mar_cap_cr"] = round(price * float(shares) / 1e7, 2)
    except Exception:
        pass

    # ─── Dividend yield (TTM / price-at-anchor)
    try:
        tk = yf.Ticker(_yf_ticker(symbol))
        divs = tk.dividends
        if divs is not None and not divs.empty:
            anchor_ts = pd.Timestamp(anchor)
            try:
                if hasattr(divs.index, "tz") and divs.index.tz is not None:
                    divs.index = divs.index.tz_localize(None)
            except Exception:
                pass
            window = divs[(divs.index <= anchor_ts) &
                            (divs.index >= anchor_ts - pd.Timedelta(days=365))]
            ttm_div = float(window.sum()) if len(window) else 0.0
            # Reuse the price we computed for market cap if possible
            if not np.isnan(out["mar_cap_cr"]):
                # back-derive price
                shares = meta.get("sharesOutstanding")
                if shares:
                    price = (out["mar_cap_cr"] * 1e7) / float(shares)
                    if price > 0 and ttm_div > 0:
                        out["div_yield_pct"] = round(ttm_div / price * 100, 2)
    except Exception:
        pass

    # ─── Promoter % (today's snapshot — minor look-ahead)
    snap = _load_promoter_snapshot()
    pct = snap.get(_clean(symbol).upper())
    if pct is not None:
        out["promoter_pct"] = pct

    out["ok"] = True
    return out


# ─── Conviction scoring (port of brute_force_match_pro.calculate_conviction_score)
def bff_as_of(symbol: str, anchor: str, is_financial: bool = False) -> dict:
    """BFF computed POINT-IN-TIME from screener.in's own history tables.

    WHY NOT compute_bff: it reads TODAY's page. Scoring a 2024 anchor with 2026
    fundamentals leaks look-ahead into every historical row and makes the
    partition measure nothing - the class of error the matched-horizon and
    window-mismatch lessons already cost this repo.

    WHY NOT yfinance (the first attempt, 13 Aug): it returns only FIVE quarters,
    oldest 2025-03-31, while the bull anchors run 2024-06 to 2025-11. Most
    anchors had neither the quarter nor its year-ago pair, so every row came back
    INSUFFICIENT. screener_history reads the company page's #quarters (~13) and
    #ratios (~12y) sections instead - enough history for every anchor, AND it
    carries the OPM row, so this is the FULL 5-check BFF rather than the
    degraded 4-check version yfinance allowed.

    Returns compute_bff's exact shape so bff_passes() consumes it unchanged,
    including the scaling that makes a 4-check financial comparable to a
    5-check non-financial. Thresholds come from bull_fundamental_filter.CONFIG,
    so a threshold change moves the backtest and the live gate together.
    """
    import bull_fundamental_filter as bff
    import screener_history as sh

    def _blank(reason):
        return {"symbol": symbol, "score": None, "max": 5, "quality": "INSUFFICIENT",
                "checks": {}, "drivers": [], "as_of": anchor, "source": "screener-history",
                "is_financial": is_financial, "reason": reason}

    f = sh.as_of(symbol, anchor)
    if not f:
        return _blank("no history at anchor")

    C = bff.CONFIG
    checks, drivers = {}, []
    pg, sg = f.get("profit_growth_pct"), f.get("sales_growth_pct")
    opm_now, opm_prev = f.get("opm_now"), f.get("opm_prev")
    roce, ni = f.get("roce_pct"), f.get("net_profit")

    checks["profit_growth"] = None if pg is None else (
        pg >= (C["fin_profit_growth_min_pct"] if is_financial else C["profit_growth_min_pct"]))
    if pg is not None:
        drivers.append(f"Profit {pg:+.0f}%")

    checks["sales_growth"] = None if sg is None else (
        sg >= (C["fin_sales_growth_min_pct"] if is_financial else C["sales_growth_min_pct"]))
    if sg is not None:
        drivers.append(f"Sales {sg:+.0f}%")

    # Lenders do not report OPM — dropped for financials exactly as compute_bff
    # does, which is why bff_passes scales the floor to the APPLICABLE checks.
    if is_financial:
        checks["margin_expansion"] = None
    else:
        checks["margin_expansion"] = (None if (opm_now is None or opm_prev is None)
                                      else opm_now > opm_prev)
        if opm_now is not None and opm_prev is not None:
            drivers.append(f"OPM {opm_prev:.0f}->{opm_now:.0f}%")

    checks["return_quality"] = None if roce is None else (
        roce > C["fin_roce_min_pct"] if is_financial else roce >= C["roce_min_pct"])
    if roce is not None:
        drivers.append(f"ROCE {roce:.0f}%")

    checks["profitable"] = None if ni is None else ni > 0

    n_data = len([v for v in checks.values() if v is not None])
    if n_data < C["min_fields"]:
        return _blank(f"only {n_data} checks resolved")

    score = sum(1 for v in checks.values() if v is True)
    quality = ("STRONG" if score >= C["strong_min"] else
               "OK" if score >= C["ok_min"] else "WEAK")
    return {"symbol": symbol, "score": score, "max": 5, "quality": quality,
            "checks": checks, "drivers": drivers, "as_of": anchor,
            "source": "screener-history", "is_financial": is_financial,
            "roce": roce, "roe": None, "debt_to_equity": None,
            "quarter_end": f.get("quarter_end")}


def conviction_score_as_of(symbol: str, anchor: str) -> tuple[float, dict]:
    """Apply the matcher's bull conviction formula on historical fundamentals.
    Returns (score, breakdown_dict).

    Formula mirrors `calculate_conviction_score` in brute_force_match_pro.py:
      base                                     5.0
      profit_growth_qtr > 50  / > 20           +2.5 / +1.5
      sales_growth_qtr > 20                    +1.0
      roe > 20                                 +1.0
      market cap 1000-20000 Cr (mid-cap)       +0.5
    Capped at 10.0.

    Stocks with no fundamental data return score 0.0 with `ok=False`.
    """
    fund = fundamentals_as_of(symbol, anchor)
    if not fund.get("ok"):
        return 0.0, {**fund, "score": 0.0, "score_components": {}}

    score = 5.0
    components: dict[str, float] = {}

    pg = fund["profit_growth_qtr_pct"]
    if not np.isnan(pg):
        if pg > 50:
            score += 2.5; components["profit_growth_>50"] = 2.5
        elif pg > 20:
            score += 1.5; components["profit_growth_>20"] = 1.5

    sg = fund["sales_growth_qtr_pct"]
    if not np.isnan(sg) and sg > 20:
        score += 1.0; components["sales_growth_>20"] = 1.0

    roe = fund["roe_pct"]
    if not np.isnan(roe) and roe > 20:
        score += 1.0; components["roe_>20"] = 1.0

    mcap = fund["mar_cap_cr"]
    if not np.isnan(mcap) and 1000 < mcap < 20000:
        score += 0.5; components["midcap_bonus"] = 0.5

    final = round(min(10.0, score), 1)
    return final, {**fund, "score": final, "score_components": components}


# ─── Bulk helper for the validation harness ──────────────────────────────────
def warm_cache(symbols: list[str], log_every: int = 25) -> None:
    """Pre-fetch statements for a symbol list. Useful before a validation run."""
    for i, sym in enumerate(symbols, 1):
        _fetch_statements(sym)
        if i % log_every == 0:
            print(f"  warm_cache: {i}/{len(symbols)} symbols cached", flush=True)


__all__ = [
    "fundamentals_as_of",
    "conviction_score_as_of",
    "warm_cache",
    "CACHE_DIR",
]


if __name__ == "__main__":
    # Smoke test
    import sys
    if hasattr(sys.stdout, "encoding") and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try: sys.stdout.reconfigure(encoding="utf-8")
        except Exception: pass

    for sym in ("HDFCBANK", "TCS", "RELIANCE", "ITC"):
        for anchor in ("2025-04-15", "2025-12-15"):
            t0 = time.time()
            score, breakdown = conviction_score_as_of(sym, anchor)
            print(f"  {sym:<10} @ {anchor}  score={score}  "
                  f"q_end={breakdown.get('quarter_end','?')}  "
                  f"pg={breakdown.get('profit_growth_qtr_pct')}  "
                  f"roe={breakdown.get('roe_pct')}  "
                  f"({time.time()-t0:.2f}s)")
