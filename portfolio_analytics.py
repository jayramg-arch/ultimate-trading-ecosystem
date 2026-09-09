# portfolio_analytics.py
# Phase 3 — Portfolio Analytics Engine
# Covers: overview, factor exposure, VaR/CVaR, stress tests, walk-forward backtest

import pandas as pd
import numpy as np
import yfinance as yf
import warnings
import os
import re
from concurrent.futures import ThreadPoolExecutor
warnings.filterwarnings("ignore")

# C1 sweep: route OHLCV through data_provider when available.
try:
    import data_provider as _dp
    USE_DATA_PROVIDER = True
except Exception:
    _dp = None
    USE_DATA_PROVIDER = False

BENCHMARK = "^NSEI"

STRESS_SCENARIOS = {
    "COVID Crash (Feb–Mar 2020)":        ("2020-02-17", "2020-03-23"),
    "COVID Recovery (Apr–Dec 2020)":     ("2020-04-01", "2020-12-31"),
    "2022 Rate Hike Selloff (Jan–Jun)":  ("2022-01-03", "2022-06-17"),
    "2022-23 Recovery (Jul–Dec 2022)":   ("2022-07-01", "2022-12-30"),
    "2024 Election Shock (May–Jun)":     ("2024-05-20", "2024-06-04"),
    "2025 Tariff Shock (Mar–Apr 2025)":  ("2025-03-03", "2025-04-09"),
}

# ── Internal helpers ───────────────────────────────────────────────────────────

def _to_yf(sym: str) -> str:
    s = sym.strip().upper()
    if not s.endswith(".NS") and not s.startswith("^"):
        s += ".NS"
    return s


# ── Sector Mapping Logic ──────────────────────────────────────────────────────
SECTOR_MAP_FILE = "Stock to Sector mappings for pine script.txt"
_SECTOR_CACHE = {}

def _load_sector_mapping():
    """Parse the Pine-style mapping file into a local dict."""
    global _SECTOR_CACHE
    if _SECTOR_CACHE: return
    
    # Map ETF tickers to friendly names
    etf_to_name = {
        "NSE:BANKNIFTY": "Banks",
        "NSE:CNXENERGY": "Energy",
        "NSE:CNXAUTO": "Auto",
        "NSE:CNXIT": "IT",
        "NSE:CNXPHARMA": "Pharma",
        "NSE:CNXMETAL": "Metals",
        "NSE:CNXINFRA": "Infra",
        "NSE:CNXFMCG": "FMCG",
        "NSE:CNXREALTY": "Realty",
        "NSE:CNXCOMMODITIES": "Commodities",
        "NSE:CNXCONSUMPTION": "Consumption",
        "NSE:CNXMNCS": "MNC",
        "NSE:CNX500": "Others",
        "NSE:CNXFINANCE": "Financials",
        "NSE:CNXMEDIA": "Media",
    }
    
    if os.path.exists(SECTOR_MAP_FILE):
        try:
            with open(SECTOR_MAP_FILE, "r") as f:
                content = f.read()
                # Matches "TICKER" => "NSE:ETFTICKER"
                matches = re.findall(r'"([^"]+)"\s*=>\s*"([^"]+)"', content)
                for sym, etf in matches:
                    yf_sym = _to_yf(sym)
                    _SECTOR_CACHE[yf_sym] = etf_to_name.get(etf, "Others")
        except Exception:
            pass

def _get_sector_single(symbol: str) -> str:
    """Helper for parallel lookup."""
    if symbol in _SECTOR_CACHE:
        return _SECTOR_CACHE[symbol]
    try:
        # Avoid full .info if possible, but sector is usually there
        info = yf.Ticker(symbol).info
        return info.get("sector", "Unknown") or "Unknown"
    except Exception:
        return "Unknown"


def parse_holdings(raw: str) -> list:
    """
    Parse multi-line text into holdings list.
    Accepted formats (one per line, comma or space separated):
      RELIANCE.NS, 100, 2500
      INFY 50 1800
      TCS,20
    Returns: [{"symbol": "RELIANCE.NS", "quantity": 100.0, "avg_cost": 2500.0}, ...]
    """
    holdings = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.replace(",", " ").split() if p.strip()]
        if len(parts) < 2:
            continue
        sym = _to_yf(parts[0])
        try:
            qty = float(parts[1])
        except ValueError:
            continue
        avg_cost = float(parts[2]) if len(parts) >= 3 else 0.0
        holdings.append({"symbol": sym, "quantity": qty, "avg_cost": avg_cost})
    return holdings


def _fetch_prices(symbols: list, period: str = "1y") -> pd.DataFrame:
    """C1 sweep: cached batch via data_provider; yf fallback."""
    all_syms = list(set(symbols + [BENCHMARK]))
    import data_provider as dp
    bd = dp.fetch_batch_ohlcv(all_syms, period=period, interval="1d", use_cache=True, auto_adjust=True)
    if bd:
        return pd.DataFrame({
            (k if k.startswith("^") else f"{k}.NS"): df["Close"]
            for k, df in bd.items() if "Close" in df.columns
        }).dropna(how="all")
    return pd.DataFrame()


def _get_current_prices(symbols: list) -> dict:
    """C1 sweep: per-symbol cached latest_close — short, hot calls."""
    import data_provider as dp
    out = {}
    for sym in symbols:
        try:
            price = dp.latest_close(sym)
            if price > 0:
                out[sym] = price
        except Exception:
            continue
    return out


def _get_weights(holdings: list, prices: pd.DataFrame, portfolio_value: float = None):
    """Return (weights_dict, total_value) from holdings + latest prices."""
    latest = prices.ffill().iloc[-1]
    total_val = portfolio_value or 0.0
    mvs = {}
    for h in holdings:
        sym = h["symbol"]
        if sym not in latest.index:
            continue
        mv = float(latest[sym]) * h["quantity"]
        mvs[sym] = mv
        if not portfolio_value:
            total_val += mv
    if total_val <= 0:
        return {}, 0.0
    return {sym: mv / total_val for sym, mv in mvs.items()}, total_val


# ── Public API ─────────────────────────────────────────────────────────────────

def portfolio_overview(raw_holdings: str, portfolio_value: float = None) -> dict:
    """
    Returns summary dict:
      holdings, total_value, total_cost, total_pnl_pct,
      sector_weights, hhi, top5, num_positions
    """
    holdings = parse_holdings(raw_holdings)
    if not holdings:
        return {}

    symbols = [h["symbol"] for h in holdings]
    prices_live = _get_current_prices(symbols)

    # 10 May 2026: track which symbols had to fall back to avg_cost so the UI
    # can warn the user. Previously a silent fallback meant P&L always read
    # 0.0% when ALL live prices failed (no warning, just stale-looking 0%).
    fallback_symbols = []
    total_val = portfolio_value or 0.0
    for h in holdings:
        live = prices_live.get(h["symbol"])
        if live and live > 0:
            cp = live
            h["price_source"] = "live"
        else:
            cp = h.get("avg_cost", 0)
            h["price_source"] = "fallback (avg_cost)"
            fallback_symbols.append(h["symbol"])
        h["current_price"] = cp
        h["market_value"]  = cp * h["quantity"]
        avg_c = h.get("avg_cost", 0)
        h["pnl_pct"] = ((cp / avg_c) - 1) * 100 if avg_c > 0 else 0.0
        if not portfolio_value:
            total_val += h["market_value"]

    if total_val <= 0:
        return {}

    # ── Sector Lookup (Optimized) ─────────────────────────────────────────────
    _load_sector_mapping()
    missing_syms = [h["symbol"] for h in holdings if h["symbol"] not in _SECTOR_CACHE]
    
    if missing_syms:
        with ThreadPoolExecutor(max_workers=10) as executor:
            fetched_sectors = list(executor.map(_get_sector_single, missing_syms))
        for sym, sec in zip(missing_syms, fetched_sectors):
            _SECTOR_CACHE[sym] = sec

    for h in holdings:
        h["weight"] = h["market_value"] / total_val if total_val > 0 else 0.0
        h["sector"] = _SECTOR_CACHE.get(h["symbol"], "Unknown")

    total_cost = sum(h["avg_cost"] * h["quantity"]
                     for h in holdings if h.get("avg_cost", 0) > 0)
    total_pnl  = ((total_val / total_cost) - 1) * 100 if total_cost > 0 else 0.0

    sector_weights: dict = {}
    for h in holdings:
        sec = h.get("sector", "Unknown")
        sector_weights[sec] = sector_weights.get(sec, 0.0) + h["weight"]
    sector_weights = {k: round(v * 100, 2)
                      for k, v in sorted(sector_weights.items(), key=lambda x: -x[1])}

    hhi = sum((h["weight"] * 100) ** 2 for h in holdings)

    top5 = sorted(holdings, key=lambda h: h["weight"], reverse=True)[:5]

    return {
        "holdings":          holdings,
        "total_value":       round(total_val, 2),
        "total_cost":        round(total_cost, 2),
        "total_pnl_pct":     round(total_pnl, 2),
        "sector_weights":    sector_weights,
        "hhi":               round(hhi, 1),
        "top5":              [{"symbol": h["symbol"].replace(".NS",""),
                                "weight_pct": round(h["weight"]*100,2)} for h in top5],
        "num_positions":     len(holdings),
        # 10 May 2026: fallback diagnostics so the UI can warn when live
        # prices failed to fetch (P&L would otherwise mechanically read 0%
        # because avg_cost == "current_price" was used as fallback).
        "live_price_failures": fallback_symbols,
        "live_price_ok_count": len(holdings) - len(fallback_symbols),
    }


def compute_factor_exposure(raw_holdings: str, period: str = "1y") -> dict:
    """
    Returns portfolio beta, correlation, alpha, Sharpe, Sortino vs Nifty50,
    plus per-symbol betas.
    """
    holdings = parse_holdings(raw_holdings)
    if not holdings:
        return {}

    symbols = [h["symbol"] for h in holdings]
    prices  = _fetch_prices(symbols, period=period)
    if BENCHMARK not in prices.columns:
        return {}

    weights, total_val = _get_weights(holdings, prices)
    if not weights:
        return {}

    rets       = prices.pct_change().dropna()
    bench_rets = rets[BENCHMARK]
    port_rets  = sum(rets[sym] * w for sym, w in weights.items()
                     if sym in rets.columns)

    cov        = np.cov(port_rets, bench_rets)
    beta       = cov[0, 1] / cov[1, 1] if cov[1, 1] != 0 else 1.0
    corr       = float(np.corrcoef(port_rets, bench_rets)[0, 1])
    active     = port_rets - bench_rets
    te_annual  = float(active.std() * np.sqrt(252)) * 100
    alpha_ann  = float((port_rets.mean() - beta * bench_rets.mean()) * 252) * 100

    rf_daily   = 0.065 / 252
    excess     = port_rets - rf_daily
    sharpe     = float(excess.mean() / excess.std() * np.sqrt(252)) \
                 if excess.std() > 0 else 0.0
    downside   = excess[excess < 0].std()
    sortino    = float(excess.mean() / downside * np.sqrt(252)) \
                 if downside > 0 else 0.0

    symbol_betas = {}
    for sym in weights:
        if sym not in rets.columns:
            continue
        c = np.cov(rets[sym].dropna(), bench_rets)
        symbol_betas[sym.replace(".NS", "")] = \
            round(c[0, 1] / c[1, 1], 2) if c[1, 1] != 0 else 1.0

    return {
        "portfolio_beta":         round(beta, 3),
        "benchmark_corr":         round(corr, 3),
        "tracking_error_annual":  round(te_annual, 2),
        "alpha_annual":           round(alpha_ann, 2),
        "sharpe":                 round(sharpe, 3),
        "sortino":                round(sortino, 3),
        "symbol_betas":           symbol_betas,
    }


def compute_var(raw_holdings: str, confidence: float = 0.95,
                lookback_days: int = 252, portfolio_value: float = None) -> dict:
    """
    Returns historical VaR, parametric VaR, CVaR, 10-day VaR,
    max drawdown, annual vol and return.
    """
    holdings = parse_holdings(raw_holdings)
    if not holdings:
        return {}

    symbols = [h["symbol"] for h in holdings]
    prices  = _fetch_prices(symbols, period="2y").drop(columns=[BENCHMARK], errors="ignore")
    if prices.empty:
        return {}

    weights, total_val = _get_weights(holdings, prices, portfolio_value)
    if not weights or total_val <= 0:
        return {}

    rets      = prices.pct_change().dropna().tail(lookback_days)
    port_rets = sum(rets[sym] * w for sym, w in weights.items()
                    if sym in rets.columns)

    # Historical VaR
    var_pct  = float(np.percentile(port_rets, (1 - confidence) * 100))
    var_inr  = abs(var_pct) * total_val

    # CVaR / Expected Shortfall
    tail     = port_rets[port_rets <= var_pct]
    cvar_pct = float(tail.mean()) if len(tail) > 0 else var_pct
    cvar_inr = abs(cvar_pct) * total_val

    # Parametric VaR (normal) — z-score lookup, no scipy/math.erfinv needed
    _Z = {0.90: -1.2816, 0.95: -1.6449, 0.99: -2.3263}
    z             = _Z.get(round(confidence, 2), -1.6449)
    var_param_pct = float(port_rets.mean() + z * port_rets.std())

    # 10-day VaR (sqrt-of-time scaling)
    var_10d_pct = var_pct * np.sqrt(10)

    # Max drawdown
    cum  = (1 + port_rets).cumprod()
    dd   = (cum - cum.cummax()) / cum.cummax()
    max_dd = float(dd.min())

    return {
        "var_1d_pct":            round(abs(var_pct) * 100, 3),
        "var_1d_inr":            round(var_inr, 0),
        "var_parametric_pct":    round(abs(var_param_pct) * 100, 3),
        "cvar_1d_pct":           round(abs(cvar_pct) * 100, 3),
        "cvar_1d_inr":           round(cvar_inr, 0),
        "var_10d_pct":           round(abs(var_10d_pct) * 100, 3),
        "max_drawdown_pct":      round(abs(max_dd) * 100, 2),
        "volatility_annual_pct": round(float(port_rets.std() * np.sqrt(252)) * 100, 2),
        "annualized_return_pct": round(float(port_rets.mean() * 252) * 100, 2),
        "confidence":            confidence,
        "lookback_days":         lookback_days,
        "portfolio_value":       round(total_val, 0),
    }


def run_stress_test(raw_holdings: str, portfolio_value: float = None) -> list:
    """
    Run portfolio through STRESS_SCENARIOS.
    Returns list of {scenario, start, end, portfolio_return, benchmark_return,
                      excess_return, pnl_inr}.
    """
    holdings = parse_holdings(raw_holdings)
    if not holdings:
        return []

    # C1 sweep: this is a multi-year start-anchored fetch (date range, not
    # period). data_provider keys by period+interval, so we use 'max' here
    # and slice client-side. First call is network; subsequent stress runs
    # in the same hour are cache hits.
    symbols = [h["symbol"] for h in holdings]
    import data_provider as dp
    bd = dp.fetch_batch_ohlcv(symbols + [BENCHMARK], period="max", interval="1d", use_cache=True, auto_adjust=True)
    if bd:
        prices = pd.DataFrame({
            (k if k.startswith("^") else f"{k}.NS"): df["Close"]
            for k, df in bd.items() if "Close" in df.columns
        })
        prices = prices.loc["2019-01-01":] if not prices.empty else prices
    else:
        prices = pd.DataFrame()
    prices  = prices.dropna(how="all").ffill()

    weights, total_val = _get_weights(holdings, prices, portfolio_value)
    if not weights:
        return []

    results = []
    for name, (s_date, e_date) in STRESS_SCENARIOS.items():
        try:
            sub = prices.loc[s_date:e_date]
            if len(sub) < 3:
                continue

            port_ret = 0.0
            for sym, w in weights.items():
                if sym not in sub.columns:
                    continue
                col = sub[sym].dropna()
                if len(col) < 2:
                    continue
                port_ret += w * ((col.iloc[-1] / col.iloc[0]) - 1)

            bench_ret = 0.0
            if BENCHMARK in sub.columns:
                bc = sub[BENCHMARK].dropna()
                if len(bc) >= 2:
                    bench_ret = (bc.iloc[-1] / bc.iloc[0]) - 1

            results.append({
                "scenario":         name,
                "start":            s_date,
                "end":              e_date,
                "portfolio_return": round(port_ret * 100, 2),
                "benchmark_return": round(bench_ret * 100, 2),
                "excess_return":    round((port_ret - bench_ret) * 100, 2),
                "pnl_inr":          round(port_ret * total_val, 0),
            })
        except Exception:
            continue

    return results


def run_walkforward_backtest(universe_raw: str, start: str = "2022-01-01",
                              end: str = None, rebalance_weeks: int = 4) -> dict:
    """
    Walk-forward Weinstein Stage 2 backtest.
    Entry criteria: price > SMA50 AND price > SMA200.
    Equal-weight portfolio, rebalances every `rebalance_weeks` weeks.

    Returns: equity_curve, cagr_pct, benchmark_cagr_pct, sharpe,
             max_drawdown_pct, total_return_pct, benchmark_total_return_pct,
             num_rebalances, avg_positions.
    """
    import datetime as dt
    universe = [_to_yf(s) for s in universe_raw.strip().splitlines() if s.strip()]
    if not universe:
        return {}

    end_date  = end or dt.date.today().strftime("%Y-%m-%d")
    all_syms  = list(set(universe + [BENCHMARK]))
    # C1 sweep: cached batch (period=max, slice client-side); yf fallback.
    prices = pd.DataFrame()
    import data_provider as dp
    bd = dp.fetch_batch_ohlcv(all_syms, period="max", interval="1d", use_cache=True, auto_adjust=True)
    if bd:
        prices = pd.DataFrame({
            (k if k.startswith("^") else f"{k}.NS"): df["Close"]
            for k, df in bd.items() if "Close" in df.columns
        })
        if not prices.empty:
            prices = prices.loc[start:end_date]
    prices    = prices.dropna(how="all").ffill()

    bench       = prices[BENCHMARK] if BENCHMARK in prices.columns else None
    port_prices = prices.drop(columns=[BENCHMARK], errors="ignore")
    if port_prices.empty:
        return {}

    daily_rets  = port_prices.pct_change().fillna(0)
    bench_rets  = bench.pct_change().fillna(0) if bench is not None else None
    trading_days = port_prices.index

    rebalance_interval = rebalance_weeks * 5
    next_rebalance     = 0
    current_weights: dict = {}
    portfolio_value    = 100.0
    benchmark_value    = 100.0
    equity_curve       = []
    num_rebalances     = 0
    positions_counts   = []

    for i, date in enumerate(trading_days):
        if i >= next_rebalance:
            hist = port_prices.loc[:date]
            if len(hist) >= 50:
                sma50  = hist.tail(50).mean()
                sma200 = hist.tail(200).mean() if len(hist) >= 200 else sma50
                today  = hist.iloc[-1]
                qual   = [sym for sym in port_prices.columns
                          if sym in today.index
                          and not pd.isna(today[sym])
                          and today[sym] > sma50.get(sym, 0)
                          and today[sym] > sma200.get(sym, 0)]
                if qual:
                    w = 1.0 / len(qual)
                    current_weights = {sym: w for sym in qual}
                    positions_counts.append(len(qual))
            next_rebalance = i + rebalance_interval
            num_rebalances += 1

        if i > 0 and current_weights:
            port_ret = sum(current_weights.get(sym, 0) * float(daily_rets.loc[date, sym])
                           for sym in current_weights if sym in daily_rets.columns)
            portfolio_value *= (1 + port_ret)

        if i > 0 and bench_rets is not None and date in bench_rets.index:
            benchmark_value *= (1 + float(bench_rets.loc[date]))

        equity_curve.append({
            "date":            date.strftime("%Y-%m-%d"),
            "portfolio_value": round(portfolio_value, 4),
            "benchmark_value": round(benchmark_value, 4),
        })

    n_years   = len(trading_days) / 252
    cagr      = ((portfolio_value / 100) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0
    bench_cagr= ((benchmark_value / 100) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0

    port_series = pd.Series([e["portfolio_value"] for e in equity_curve])
    port_ret_s  = port_series.pct_change().dropna()
    excess      = port_ret_s - 0.065 / 252
    sharpe      = float(excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0.0

    rolling_max = port_series.cummax()
    max_dd      = float(((port_series - rolling_max) / rolling_max).min()) * 100

    return {
        "equity_curve":               equity_curve,
        "cagr_pct":                   round(cagr, 2),
        "benchmark_cagr_pct":         round(bench_cagr, 2),
        "sharpe":                     round(sharpe, 3),
        "max_drawdown_pct":           round(abs(max_dd), 2),
        "total_return_pct":           round((portfolio_value / 100 - 1) * 100, 2),
        "benchmark_total_return_pct": round((benchmark_value / 100 - 1) * 100, 2),
        "num_rebalances":             num_rebalances,
        "avg_positions":              round(float(np.mean(positions_counts)), 1) if positions_counts else 0,
    }
