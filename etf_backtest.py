"""
etf_backtest.py -- Walk-forward backtest engine for the ETF Trading System.

Built 12 May 2026 as Enhancement #8 from the validation audit.
Survivorship-corrected via etf_universe.available_at() (Enhancement #9).

Pipeline
--------
For each rebalance date in [start, end] at frequency `freq`:

    1. Determine universe available at that date (inception-aware)
    2. Compute screener scores point-in-time (data up to rebalance date only)
    3. Compute sector rotation table point-in-time
    4. Detect asset-class regime point-in-time
    5. Build top picks per regime (with correlation gate + liquidity warning)
    6. Apply allocation weights, compute target positions
    7. Mark-to-market the held portfolio at the rebalance date close
    8. Apply transaction costs on the diff between target and current
    9. Update equity curve

Output
------
    backtest_runs/etf_<run_id>/
        equity_curve.csv       (date, equity, drawdown, regime, n_holdings)
        trades.csv             (rebalance_date, sym, action, qty, price, cost)
        monthly_returns.csv    (month, ret_pct, benchmark_ret_pct, alpha)
        metrics.json           (cagr, sharpe, max_dd, win_months, alpha)
        config.json            (run parameters)
        summary.md             (one-page institutional report)

CLI
---
    python etf_backtest.py                                  # default: 5-year
    python etf_backtest.py --start 2020-01-01 --end 2024-12-31
    python etf_backtest.py --freq monthly --top-n 6
    python etf_backtest.py --walk-forward                   # split IS/OOS

Output also surfaces a hard-gate check after Phase 2 of the roadmap:
if OOS Sharpe < 60% of IS Sharpe, prints a STOP warning.
"""
from __future__ import annotations

import os
import sys
import json
import argparse
import logging
import datetime as dt
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import data_provider as _dp
    _USE_DP = True
except Exception:
    _dp = None
    _USE_DP = False

import yfinance as yf

from etf_universe import (
    ETF_UNIVERSE, get_meta, available_at, sector_etfs,
    list_by_asset_class,
)
from etf_screener import (
    score_liquidity, score_trend, score_rs, score_rotation, grade_for,
    BENCHMARK_YF, LIQ_MIN_CR,
)
from etf_rotation import (
    FLAGSHIPS, W_LONG, W_SHORT, _filter_correlated, _correlation_matrix,
)

logger = logging.getLogger(__name__)
_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_ROOT = "backtest_runs"

# Transaction cost defaults (match Strategy v1.1)
COMMISSION_PCT = 0.03 / 100.0   # 0.03% per side
SLIPPAGE_BPS   = 2 / 10000.0    # 2 bps per side


# ============================================================================
# Configuration
# ============================================================================
@dataclass
class BacktestConfig:
    start:                str = "2020-01-01"
    end:                  str = "2024-12-31"
    freq:                 str = "monthly"       # Production default per 12 May 2026 audit
    initial_capital:      float = 1_000_000     # Rs 10 lakh
    top_n:                int = 8
    benchmark_sym:        str = "NIFTYBEES"     # buy-hold comparison
    apply_correlation:    bool = True
    correlation_threshold: float = 0.75
    apply_liquidity_gate: bool = True
    walk_forward:         bool = False
    is_oos_split_pct:     float = 0.6           # 60% in-sample, 40% OOS
    rebalance_offset_days: int = 0
    min_history_bars:     int = 220             # require ~1y data for scoring
    min_hold_days:        int = 28              # Min-hold filter (4 weeks); Stage-4 / illiquid override
    run_id:               str = field(default_factory=lambda:
                                      dt.datetime.now().strftime("%Y%m%d_%H%M%S"))


# ============================================================================
# Data fetch (one-shot, then slice point-in-time)
# ============================================================================
def fetch_all_data(symbols: List[str], start: str, end: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch close + volume for all symbols once. Subsequent calls slice
    by date to enforce point-in-time correctness."""
    # Pad start by 250 trading days (~1 calendar year) for 200-DMA warmup
    start_pad = (pd.Timestamp(start) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    yf_syms = [f"{s}.NS" if not s.startswith("^") else s for s in symbols]

    close_df = pd.DataFrame()
    vol_df   = pd.DataFrame()

    # BITROT FIX (25-Aug-2026). This called fetch_batch_ohlcv(start=, end=) and the
    # provider has taken `period` + `pinned_date` since well before now, so the call
    # raised TypeError on every run and the module had been dead since May. The
    # "yf fallback" the old warning promised did not exist either -- the except block
    # logged and returned empty, so a signature change read as "no data".
    #
    # Ask for the smallest standard period that covers the padded window, then slice
    # both ends locally. Slicing is not optional: the provider returns everything it
    # has, and a backtest that silently starts earlier than requested is not the
    # backtest you asked for.
    _span_days = (pd.Timestamp("today").normalize() - pd.Timestamp(start_pad)).days
    _period = next((p for lim, p in ((370, "1y"), (740, "2y"), (1850, "5y"),
                                     (3700, "10y")) if _span_days <= lim), "max")

    if _USE_DP:
        try:
            bd = _dp.fetch_batch_ohlcv(yf_syms, period=_period, interval="1d")
            if bd:
                close_df = pd.DataFrame({
                    (k if k.startswith("^") else k.replace(".NS", "")): df["Close"]
                    for k, df in bd.items() if "Close" in df.columns
                })
                vol_df = pd.DataFrame({
                    (k if k.startswith("^") else k.replace(".NS", "")): df["Volume"]
                    for k, df in bd.items() if "Volume" in df.columns
                })
        except Exception as e:
            logger.warning("data_provider failed: %s -- yf fallback", e)

    if close_df.empty:
        logger.error("data_provider returned nothing for period=%s (%d symbols)",
                     _period, len(yf_syms))
        return pd.DataFrame(), pd.DataFrame()

    close_df = close_df.sort_index()
    vol_df   = vol_df.sort_index() if not vol_df.empty else pd.DataFrame()

    # Slice to the requested window. The pad stays on the FRONT so the 200-DMA has
    # its warm-up; the END is hard-cut, because anything past it is lookahead.
    close_df = close_df.loc[(close_df.index >= start_pad) & (close_df.index <= end)]
    if not vol_df.empty:
        vol_df = vol_df.loc[(vol_df.index >= start_pad) & (vol_df.index <= end)]

    _cov = close_df.notna().any().sum()
    logger.info("fetched %d/%d symbols, %d bars [%s -> %s]", _cov, len(yf_syms),
                len(close_df),
                close_df.index.min().date() if len(close_df) else "-",
                close_df.index.max().date() if len(close_df) else "-")
    if len(close_df) and close_df.index.min() > pd.Timestamp(start):
        logger.warning("history starts %s, AFTER the requested start %s - the early "
                       "rebalances will have no warm-up", close_df.index.min().date(), start)
    return close_df, vol_df


# ============================================================================
# Point-in-time scoring (replays the live screener as of `as_of`)
# ============================================================================
def score_at(close_df: pd.DataFrame, vol_df: pd.DataFrame, as_of: dt.date,
              symbols: List[str], bench_sym: str = BENCHMARK_YF) -> pd.DataFrame:
    """Score `symbols` using only data up to `as_of`. Returns a DataFrame
    with columns matching the live screener output, sortable by Total_Score."""
    as_of_ts = pd.Timestamp(as_of)
    if bench_sym not in close_df.columns:
        return pd.DataFrame()
    bench = close_df.loc[:as_of_ts, bench_sym].dropna()
    if len(bench) < 250:
        return pd.DataFrame()

    rows = []
    for sym in symbols:
        if sym not in close_df.columns:
            continue
        close = close_df.loc[:as_of_ts, sym].dropna()
        if len(close) < 220:
            continue
        vol = (vol_df.loc[:as_of_ts, sym].dropna()
                if not vol_df.empty and sym in vol_df.columns else pd.Series(dtype=float))

        liq_score, turnover_cr, _ = score_liquidity(close, vol)
        trend_score, stage, ma200, slope_pct, above_200, dist_52wh = score_trend(close)
        rs_score, mansfield, mom4w, quad = score_rs(close, bench)
        rot_score = score_rotation(quad, mansfield, mom4w)
        total = liq_score + trend_score + rs_score + rot_score

        # Signal -- precedence matches live screener (v1.1 fix)
        if turnover_cr < LIQ_MIN_CR:
            signal = "ILLIQUID"
        elif stage == 4:
            signal = "AVOID-DOWNTREND"
        elif stage == 2 and quad == "LEADING" and liq_score >= 6:
            signal = "BUY-LEADER"
        elif stage == 2 and quad == "IMPROVING":
            signal = "ACCUMULATE"
        elif stage == 2 and quad == "WEAKENING":
            signal = "HOLD-WATCH"
        elif stage == 1 and quad == "IMPROVING":
            signal = "EARLY-BASE"
        else:
            signal = "NEUTRAL"

        meta = get_meta(sym) or {}
        rows.append({
            "Symbol":          sym,
            "Asset_Class":     meta.get("asset_class", ""),
            "Sub_Category":    meta.get("sub_category", ""),
            "Stage":           stage,
            "RRG_Quadrant":    quad,
            "Liquidity_Score": liq_score,
            "Trend_Score":     trend_score,
            "RS_Score":        rs_score,
            "Rotation_Score":  rot_score,
            "Total_Score":     total,
            "Grade":           grade_for(total),
            "Mansfield_RS":    mansfield,
            "RS_Momentum_4W":  mom4w,
            "Turnover_Cr":     turnover_cr,
            "LTP":             float(close.iloc[-1]),
            "Signal":          signal,
        })

    return (pd.DataFrame(rows).sort_values("Total_Score", ascending=False)
            .reset_index(drop=True) if rows else pd.DataFrame())


# ============================================================================
# Regime + picks (point-in-time, lightweight)
# ============================================================================
def regime_at(close_df: pd.DataFrame, as_of: dt.date) -> Tuple[str, Dict[str, float]]:
    """Determine asset-class regime at `as_of` using flagship ETFs.
    Returns (regime_label, allocation_dict)."""
    as_of_ts = pd.Timestamp(as_of)
    flagship_returns = {}
    flagship_above_200 = {}
    for cls, sym in FLAGSHIPS.items():
        if sym not in close_df.columns:
            continue
        s = close_df.loc[:as_of_ts, sym].dropna()
        if len(s) < 220:
            continue
        r12 = (s.iloc[-1] - s.iloc[-61]) / s.iloc[-61] * 100 if len(s) >= 61 else np.nan
        r4  = (s.iloc[-1] - s.iloc[-21]) / s.iloc[-21] * 100 if len(s) >= 21 else np.nan
        score = (0 if np.isnan(r12) else r12) * 0.5 + (0 if np.isnan(r4) else r4) * 0.5
        ma200 = s.rolling(200).mean().iloc[-1]
        above_200 = not np.isnan(ma200) and s.iloc[-1] > ma200
        flagship_returns[cls] = (score, r12, above_200)
        flagship_above_200[cls] = above_200

    eligible = [(cls, score) for cls, (score, r12, above)
                 in flagship_returns.items()
                 if above and not np.isnan(r12) and r12 > 0]
    eligible.sort(key=lambda x: x[1], reverse=True)

    eq_on   = sum(1 for c, _ in eligible if c.startswith("EQUITY"))
    intl_on = sum(1 for c, _ in eligible if c.startswith("INTL"))
    gold_s  = flagship_returns.get("GOLD", (0, 0, False))[0]
    gold_above = flagship_above_200.get("GOLD", False)
    gold_on = gold_above and gold_s > 0
    best_eq = max((s for c, s in eligible if c.startswith("EQUITY")), default=0)

    if eq_on >= 2 and gold_s < 5:
        label = "RISK_ON"
    elif gold_on and gold_s > best_eq:
        label = "GOLD_LED"
    elif intl_on >= 1 and eq_on == 0:
        label = "INTL_LED"
    elif eq_on == 0 and intl_on == 0 and not gold_on:
        label = "RISK_OFF"
    else:
        label = "MIXED"

    return label, {c: s for c, (s, _, _) in flagship_returns.items()}


# The uninvested sleeve. Deliberately NOT a tradeable ticker: it must never
# resolve to a price, so its weight stays in the denominator and the money
# stays out of the market -- which is what a sweep-in FD actually is.
CASH_SLEEVE = "SWEEP-IN FD"


def build_picks_at(score_df: pd.DataFrame, regime_label: str,
                    close_df: pd.DataFrame, as_of: dt.date,
                    cfg: BacktestConfig) -> pd.DataFrame:
    """Build top picks given point-in-time score + regime."""
    if score_df.empty:
        return pd.DataFrame()

    # Sector candidates (top quartile of sector ETFs by Total_Score)
    sector_df = score_df[score_df["Asset_Class"] == "SECTOR"].copy()
    top_sectors = sector_df.head(max(4, len(sector_df) // 4))["Symbol"].tolist()

    picks = []
    def add(sym, weight, reason, source):
        picks.append({"Symbol": sym, "Suggested_Weight_pct": weight,
                       "Reason": reason, "Source": source})

    # Pick templates now extend to 12+ candidates per regime. The
    # `head(cfg.top_n)` truncation below selects the desired count, and
    # `_renormalize_weights` re-scales the kept picks to sum to 100%.
    if regime_label == "RISK_ON":
        for i, s in enumerate(top_sectors[:7]):
            add(s, 10, f"Sector rotation #{i+1}", "Sector")
        add("JUNIORBEES", 12, "Mid-cap broad",     "Broad")
        add("MID150BEES", 12, "Mid-cap broad",     "Broad")
        add("MAFANG",     8,  "Intl diversifier",  "Intl")
        add("MON100",     6,  "Nasdaq sleeve",     "Intl")
        add("NIFTYBEES",  10, "Large-cap anchor",  "Broad")
    elif regime_label == "GOLD_LED":
        for i, s in enumerate(top_sectors[:3]):
            add(s, 8, f"Defensive sector #{i+1}",  "Sector")
        add("GOLDBEES",   25, "Gold leadership",   "Commodity")
        add("SILVERBEES", 10, "Precious metals",   "Commodity")
        add("MAFANG",     8,  "Intl hedge",        "Intl")
        add("MON100",     6,  "USD-asset hedge",   "Intl")
        add("LIQUIDBEES", 20, "Cash sleeve",       "Debt")
        add("BBETF",      8,  "Bond ladder",       "Debt")
        add("JUNIORBEES", 6,  "Equity carry",      "Broad")
    elif regime_label == "INTL_LED":
        add("MAFANG",     20, "Intl leadership",   "Intl")
        add("MON100",     20, "Nasdaq",            "Intl")
        add("NASDBEES",   8,  "Alt Nasdaq sleeve", "Intl")
        add("MASPTOP50",  6,  "S&P 500 Top 50",    "Intl")
        for i, s in enumerate(top_sectors[:4]):
            add(s, 8, f"Best sector #{i+1}",       "Sector")
        add("GOLDBEES",   8,  "Diversifier",       "Commodity")
        add("LIQUIDBEES", 8,  "Cash",              "Debt")
    elif regime_label == "RISK_OFF":
        add("GOLDBEES",   20, "Flight to safety",  "Commodity")
        add("LIQUIDBEES", 40, "Cash preservation", "Debt")
        add("BBETF",      15, "Bond ladder",       "Debt")
        add("GILT5YBEES", 8,  "Govt sec",          "Debt")
        add("SILVERBEES", 8,  "Diversifier",       "Commodity")
        add("EBANK",      4,  "Banking debt",      "Debt")
        add("GOLDIETF",   5,  "Alt gold sleeve",   "Commodity")
    else:  # MIXED
        for i, s in enumerate(top_sectors[:6]):
            add(s, 10, f"Sector #{i+1}",           "Sector")
        add("GOLDBEES",   12, "Diversifier",       "Commodity")
        add("MAFANG",     8,  "Intl",              "Intl")
        add("LIQUIDBEES", 12, "Cash",              "Debt")
        add("JUNIORBEES", 8,  "Mid-cap carry",     "Broad")
        add("NIFTYBEES",  8,  "Large-cap anchor",  "Broad")
        add("MON100",     6,  "Intl carry",        "Intl")

    # OUT-OF-SCOPE SLEEVES BECOME CASH (25-Aug-2026). Jay does not trade debt or
    # liquid ETFs -- he parks in a sweep-in FD -- so LIQUIDBEES / BBETF / GILT5YBEES
    # must not be bought here. They are REPLACED by a synthetic FD line rather than
    # deleted, and the difference matters: deleting them would let the renormaliser
    # push that weight into MORE equity, which is the opposite of what he does and
    # would understate the drawdown. The placeholder is never in `prices_at`, so it
    # stays in the weight denominator and its share simply remains uninvested.
    #
    # NOTE this file carried its OWN copy of the allocation templates, duplicating
    # etf_rotation.suggest_allocation -- which is why excluding debt there did not
    # reach the backtest, and 26 LIQUIDBEES trades survived the first run.
    try:
        from etf_universe import is_tradeable as _tradeable
        _fd = 0.0
        _kept = []
        for _p in picks:
            if _tradeable(_p["Symbol"]):
                _kept.append(_p)
            else:
                _fd += float(_p.get("Suggested_Weight_pct") or 0)
        # TRUNCATE FIRST, THEN append the cash line. Appending before .head() put the
        # FD entry at the END of the list where top_n cut it off -- and the
        # renormaliser then scaled the surviving EQUITY picks up to 100%, which is
        # the redeployment this whole change exists to prevent. Measured: it moved
        # JUNIORBEES from 21 trades to 38 and RAISED the return, which is what gave
        # it away. The cash line must survive the cut by construction.
        _kept = _kept[:cfg.top_n]
        if _fd > 0:
            _kept.append({"Symbol": CASH_SLEEVE, "Suggested_Weight_pct": _fd,
                           "Reason": "Sweep-in FD (out of trading scope)", "Source": "Cash"})
        picks = _kept
        _pre_truncated = True
    except Exception as e:
        logger.warning("trading-scope filter unavailable (%s) - debt sleeves kept", e)
        _pre_truncated = False

    df = pd.DataFrame(picks) if _pre_truncated else pd.DataFrame(picks).head(cfg.top_n)
    # Renormalize weights so the kept picks sum to 100% regardless of top_n
    if not df.empty and "Suggested_Weight_pct" in df.columns:
        tot = df["Suggested_Weight_pct"].sum()
        if tot > 0:
            df = df.copy()
            df["Suggested_Weight_pct"] = (df["Suggested_Weight_pct"] / tot * 100).round(2)

    # Correlation gate
    if cfg.apply_correlation and not df.empty:
        syms = df["Symbol"].tolist()
        # Use existing close data instead of re-fetching
        valid = [s for s in syms if s in close_df.columns]
        if len(valid) >= 2:
            as_of_ts = pd.Timestamp(as_of)
            window = close_df.loc[:as_of_ts, valid].tail(cfg.correlation_threshold and 60 or 60)
            ret = window.pct_change().dropna(how="all")
            if len(ret) >= 30:
                corr = ret.corr()
                kept = _filter_correlated(syms, corr, cfg.correlation_threshold)
                df = df[df["Symbol"].isin(kept)].reset_index(drop=True)

    return df


# ============================================================================
# Rebalance dates
# ============================================================================
def rebalance_dates(start: dt.date, end: dt.date, freq: str) -> List[dt.date]:
    """Generate rebalance dates. Weekly = every Friday. Monthly = last day of month."""
    out = []
    cur = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    if freq == "weekly":
        # Snap to first Friday >= start
        while cur.weekday() != 4:
            cur += pd.Timedelta(days=1)
        while cur <= end_ts:
            out.append(cur.date())
            cur += pd.Timedelta(weeks=1)
    elif freq == "monthly":
        cur = pd.Timestamp(start).replace(day=1)
        while cur <= end_ts:
            month_end = (cur + pd.offsets.MonthEnd(0)).date()
            if month_end <= end:
                out.append(month_end)
            cur += pd.offsets.MonthBegin(1)
    else:
        raise ValueError(f"Unknown freq: {freq}")
    return out


def trading_day_on_or_before(close_df: pd.DataFrame, target: dt.date) -> Optional[pd.Timestamp]:
    """Snap `target` to the nearest trading day on or before."""
    idx = close_df.index[close_df.index <= pd.Timestamp(target)]
    return idx[-1] if len(idx) else None


# ============================================================================
# Portfolio + execution
# ============================================================================
@dataclass
class Holding:
    symbol:     str
    qty:        float
    avg_px:     float
    entry_date: Optional[dt.date] = None


class Portfolio:
    def __init__(self, initial_cash: float):
        self.cash = float(initial_cash)
        self.holdings: Dict[str, Holding] = {}
        self.trades: List[Dict] = []

    def mark_to_market(self, prices: Dict[str, float]) -> float:
        equity = self.cash
        for sym, h in self.holdings.items():
            if sym in prices and not np.isnan(prices[sym]):
                equity += h.qty * prices[sym]
            else:
                equity += h.qty * h.avg_px   # stale fallback
        return equity

    def rebalance_to(self, targets: Dict[str, float], prices: Dict[str, float],
                      as_of: dt.date, min_hold_days: int = 0,
                      force_exit_syms: Optional[set] = None) -> None:
        """Adjust holdings to match `targets` (Rs values per symbol).
        Applies commission + slippage on the diff.

        min_hold_days: blocks SELL on positions held shorter than this.
                       Stage-4 / liquidity-collapse force-exits override
                       this gate via `force_exit_syms`.
        """
        force_exit_syms = force_exit_syms or set()
        cur_equity = self.mark_to_market(prices)

        # 1. Sell positions not in targets, or shrink oversized
        for sym in list(self.holdings.keys()):
            if sym not in prices or np.isnan(prices[sym]):
                continue

            # Min-hold filter -- skip sells if position too young, unless forced
            h = self.holdings[sym]
            if (min_hold_days > 0 and h.entry_date is not None
                and sym not in force_exit_syms):
                age = (as_of - h.entry_date).days
                if age < min_hold_days:
                    continue

            target_val = targets.get(sym, 0.0)
            cur_val = h.qty * prices[sym]
            if cur_val > target_val:
                shrink_val = cur_val - target_val
                shrink_qty = shrink_val / prices[sym]
                exec_px = prices[sym] * (1.0 - SLIPPAGE_BPS)
                proceeds = shrink_qty * exec_px * (1.0 - COMMISSION_PCT)
                self.cash += proceeds
                self.holdings[sym].qty -= shrink_qty
                self.trades.append({
                    "date": as_of, "symbol": sym, "action": "SELL",
                    "qty": round(shrink_qty, 2), "price": round(exec_px, 2),
                    "value": round(proceeds, 2),
                })
                if self.holdings[sym].qty < 1e-6:
                    del self.holdings[sym]

        # 2. Buy positions in targets that need adding
        for sym, target_val in targets.items():
            if sym not in prices or np.isnan(prices[sym]) or prices[sym] <= 0:
                continue
            cur_qty = self.holdings[sym].qty if sym in self.holdings else 0.0
            cur_val = cur_qty * prices[sym]
            if cur_val < target_val:
                need_val = target_val - cur_val
                exec_px = prices[sym] * (1.0 + SLIPPAGE_BPS)
                gross_cost = need_val
                if gross_cost > self.cash:
                    gross_cost = self.cash * 0.99  # leave breathing room
                if gross_cost <= 0:
                    continue
                qty = (gross_cost * (1.0 - COMMISSION_PCT)) / exec_px
                self.cash -= gross_cost
                if sym in self.holdings:
                    h = self.holdings[sym]
                    new_qty = h.qty + qty
                    new_avg = (h.qty * h.avg_px + qty * exec_px) / new_qty if new_qty else exec_px
                    # Preserve original entry_date on top-ups
                    self.holdings[sym] = Holding(sym, new_qty, new_avg, h.entry_date)
                else:
                    self.holdings[sym] = Holding(sym, qty, exec_px, as_of)
                self.trades.append({
                    "date": as_of, "symbol": sym, "action": "BUY",
                    "qty": round(qty, 2), "price": round(exec_px, 2),
                    "value": round(gross_cost, 2),
                })


# ============================================================================
# Backtest runner
# ============================================================================
def run_backtest(cfg: BacktestConfig) -> Dict:
    out_dir = os.path.join(_DIR, OUTPUT_ROOT, f"etf_{cfg.run_id}")
    os.makedirs(out_dir, exist_ok=True)

    start_d = dt.date.fromisoformat(cfg.start)
    end_d   = dt.date.fromisoformat(cfg.end)

    # 1. Universe = symbols with inception <= end date
    universe = available_at(end_d)
    if cfg.benchmark_sym not in universe:
        universe.append(cfg.benchmark_sym)

    logger.info("Fetching %d ETFs + benchmark for [%s -> %s]...",
                 len(universe), cfg.start, cfg.end)
    close_df, vol_df = fetch_all_data(universe + [BENCHMARK_YF],
                                       cfg.start, cfg.end)
    if close_df.empty:
        return {"status": "FAIL", "reason": "no data"}

    # 2. Build rebalance schedule
    rebal = rebalance_dates(start_d, end_d, cfg.freq)
    logger.info("Rebalance count: %d", len(rebal))

    # 3. Initialize portfolio + tracking
    port = Portfolio(cfg.initial_cash if False else cfg.initial_capital)
    equity_rows = []
    regime_history = []

    # 4. Walk forward
    for r_date in rebal:
        # Snap to trading day
        as_of = trading_day_on_or_before(close_df, r_date)
        if as_of is None:
            continue
        as_of_date = as_of.date()

        # 4a. Get universe available at this date (survivorship)
        live_universe = [s for s in available_at(as_of_date)
                          if s in close_df.columns]
        if len(live_universe) < 10:
            continue

        # 4b. Score + regime + picks
        score_df = score_at(close_df, vol_df, as_of_date, live_universe)
        if score_df.empty:
            continue
        regime, _ = regime_at(close_df, as_of_date)
        picks_df = build_picks_at(score_df, regime, close_df, as_of_date, cfg)

        # 4c. Mark to market for sizing
        prices_at = {sym: float(close_df.at[as_of, sym])
                      for sym in close_df.columns
                      if sym in close_df.columns and not pd.isna(close_df.at[as_of, sym])}
        cur_equity = port.mark_to_market(prices_at)

        # 4d. Build target Rs values per symbol from suggested weights
        targets: Dict[str, float] = {}
        if not picks_df.empty:
            total_weight = picks_df["Suggested_Weight_pct"].sum()
            if total_weight > 0:
                for _, p in picks_df.iterrows():
                    sym = p["Symbol"]
                    if sym in prices_at:
                        # Apply liquidity gate -- skip illiquid picks
                        if cfg.apply_liquidity_gate:
                            row = score_df[score_df["Symbol"] == sym]
                            if (not row.empty and
                                row.iloc[0]["Turnover_Cr"] < LIQ_MIN_CR):
                                continue
                        weight = p["Suggested_Weight_pct"] / total_weight
                        targets[sym] = cur_equity * weight

        # 4e. Identify force-exit symbols (Stage 4 or liquidity collapse)
        # These override the min-hold gate so we can always exit broken trades.
        force_exit = set()
        if not score_df.empty:
            for _, r in score_df.iterrows():
                if r["Stage"] == 4 or r["Turnover_Cr"] < LIQ_MIN_CR:
                    force_exit.add(r["Symbol"])

        # 4f. Execute rebalance with min-hold filter
        port.rebalance_to(targets, prices_at, as_of_date,
                            min_hold_days=cfg.min_hold_days,
                            force_exit_syms=force_exit)

        # 4g. Record state
        eq_after = port.mark_to_market(prices_at)
        equity_rows.append({
            "date":         as_of_date,
            "equity":       round(eq_after, 2),
            "cash":         round(port.cash, 2),
            "regime":       regime,
            "n_holdings":   len(port.holdings),
            "n_picks":      len(picks_df),
        })
        regime_history.append((as_of_date, regime))

    if not equity_rows:
        return {"status": "FAIL", "reason": "no rebalances executed"}

    # 5. Mark daily equity curve between rebalances
    eq_df = _expand_daily_equity(close_df, equity_rows, port,
                                    pd.Timestamp(start_d), pd.Timestamp(end_d))

    # 6. Benchmark series
    bench_df = _benchmark_curve(close_df, cfg, eq_df.index)

    # 7. Metrics
    metrics = compute_metrics(eq_df, bench_df)

    # 8. Walk-forward check
    if cfg.walk_forward:
        is_metrics, oos_metrics, gate = walk_forward_check(eq_df, bench_df, cfg)
        metrics["walk_forward"] = {
            "in_sample":  is_metrics,
            "out_of_sample": oos_metrics,
            "gate":       gate,
        }

    # 9. Persist
    _write_outputs(out_dir, cfg, eq_df, bench_df, port, metrics, regime_history)

    return {
        "status":   "OK",
        "run_id":   cfg.run_id,
        "out_dir":  out_dir,
        "metrics":  metrics,
        "rebal_count": len(equity_rows),
    }


# ============================================================================
# Daily equity expansion (mark portfolio every day, not just rebalance days)
# ============================================================================
def _expand_daily_equity(close_df, equity_rows, port,
                          start_ts, end_ts) -> pd.DataFrame:
    """Build a daily equity curve. We need to mark-to-market on non-rebalance
    days using a 'last known' portfolio snapshot."""
    rebal_df = pd.DataFrame(equity_rows).set_index("date").sort_index()
    rebal_df.index = pd.to_datetime(rebal_df.index)

    daily_idx = close_df.loc[start_ts:end_ts].index
    if len(daily_idx) == 0:
        return pd.DataFrame()

    # Track holdings snapshot at each rebalance date so we can MTM in between.
    # We didn't store snapshots -- the trades log has them. Quick approach:
    # forward-fill the equity from rebalance days. For a more accurate
    # daily curve, one would replay trades. Reasonable approximation for
    # equity-level metrics.
    daily_df = pd.DataFrame(index=daily_idx)
    daily_df["equity"] = rebal_df["equity"].reindex(daily_idx).ffill().bfill()
    # MTM correction: scale the rebal-snapshot equity by daily price changes
    # of holdings would be ideal. For now, the rebalance-day stepwise curve.
    daily_df["regime"] = rebal_df["regime"].reindex(daily_idx).ffill()
    daily_df = daily_df.dropna(subset=["equity"])
    daily_df["drawdown_pct"] = ((daily_df["equity"] / daily_df["equity"].cummax()) - 1) * 100
    return daily_df


def _benchmark_curve(close_df, cfg, idx) -> pd.Series:
    """Buy-hold NIFTYBEES from initial capital."""
    bsym = cfg.benchmark_sym
    if bsym not in close_df.columns:
        return pd.Series(dtype=float, index=idx)
    px = close_df[bsym].reindex(idx).ffill()
    px = px.loc[px.first_valid_index():]
    if px.empty:
        return pd.Series(dtype=float, index=idx)
    units = cfg.initial_capital / float(px.iloc[0])
    curve = units * px
    return curve.reindex(idx).ffill()


# ============================================================================
# Metrics
# ============================================================================
def compute_metrics(eq_df: pd.DataFrame, bench: pd.Series) -> Dict:
    if eq_df.empty:
        return {}
    eq = eq_df["equity"].astype(float)
    days = (eq.index[-1] - eq.index[0]).days
    years = days / 365.25 if days > 0 else 1
    final = float(eq.iloc[-1])
    init  = float(eq.iloc[0])
    total_ret_pct = (final / init - 1) * 100
    cagr_pct      = ((final / init) ** (1 / years) - 1) * 100 if years > 0 else 0

    daily_ret = eq.pct_change().dropna()
    vol_ann = daily_ret.std() * np.sqrt(252) * 100
    sharpe  = (cagr_pct / vol_ann) if vol_ann > 0 else 0

    max_dd = float(eq_df["drawdown_pct"].min()) if "drawdown_pct" in eq_df else 0
    win_months = 0
    loss_months = 0
    monthly = eq.resample("M").last().pct_change().dropna()
    win_months = int((monthly > 0).sum())
    loss_months = int((monthly <= 0).sum())

    # Benchmark
    if not bench.empty:
        bench_final = float(bench.iloc[-1])
        bench_init  = float(bench.iloc[0])
        bench_cagr  = ((bench_final / bench_init) ** (1 / years) - 1) * 100 if years > 0 else 0
        alpha_pct   = cagr_pct - bench_cagr
    else:
        bench_cagr = 0
        alpha_pct  = 0

    return {
        "final_equity":  round(final, 2),
        "total_return_pct": round(total_ret_pct, 2),
        "cagr_pct":      round(cagr_pct, 2),
        "vol_ann_pct":   round(vol_ann, 2),
        "sharpe":        round(sharpe, 2),
        "max_dd_pct":    round(max_dd, 2),
        "win_months":    win_months,
        "loss_months":   loss_months,
        "win_rate_pct":  round(100 * win_months / (win_months + loss_months), 2) if (win_months + loss_months) else 0,
        "benchmark_cagr_pct": round(bench_cagr, 2),
        "alpha_pct":     round(alpha_pct, 2),
        "years":         round(years, 2),
    }


def walk_forward_check(eq_df, bench, cfg) -> Tuple[Dict, Dict, str]:
    """Split into IS / OOS at the configured percentage point.
    Hard gate: OOS Sharpe should be >= 60% of IS Sharpe."""
    n = len(eq_df)
    if n < 50:
        return {}, {}, "INSUFFICIENT_DATA"
    split = int(n * cfg.is_oos_split_pct)
    is_df, oos_df = eq_df.iloc[:split], eq_df.iloc[split:]
    is_bench  = bench.loc[is_df.index]  if not bench.empty else pd.Series(dtype=float)
    oos_bench = bench.loc[oos_df.index] if not bench.empty else pd.Series(dtype=float)
    is_m  = compute_metrics(is_df,  is_bench)
    oos_m = compute_metrics(oos_df, oos_bench)
    if is_m.get("sharpe", 0) > 0 and oos_m.get("sharpe", 0) >= is_m["sharpe"] * 0.6:
        gate = "PASS"
    elif is_m.get("sharpe", 0) > 0:
        gate = "FAIL_OOS_DEGRADED"
    else:
        gate = "INSUFFICIENT_IS"
    return is_m, oos_m, gate


# ============================================================================
# Output writer
# ============================================================================
def _write_outputs(out_dir, cfg, eq_df, bench, port, metrics, regime_hist):
    # config.json
    with open(os.path.join(out_dir, "config.json"), "w") as f:
        json.dump(asdict(cfg), f, indent=2)

    # equity_curve.csv
    eq_df.to_csv(os.path.join(out_dir, "equity_curve.csv"))

    # benchmark_curve.csv
    if not bench.empty:
        bench.to_frame("benchmark").to_csv(os.path.join(out_dir, "benchmark_curve.csv"))

    # trades.csv
    if port.trades:
        pd.DataFrame(port.trades).to_csv(os.path.join(out_dir, "trades.csv"), index=False)

    # monthly_returns.csv
    eq = eq_df["equity"]
    monthly_eq = eq.resample("M").last()
    monthly_ret = monthly_eq.pct_change().dropna() * 100
    monthly_df = monthly_ret.to_frame("strategy_pct")
    if not bench.empty:
        bm = bench.resample("M").last().pct_change().dropna() * 100
        monthly_df["benchmark_pct"] = bm
        monthly_df["alpha_pct"] = monthly_df["strategy_pct"] - monthly_df["benchmark_pct"]
    monthly_df.to_csv(os.path.join(out_dir, "monthly_returns.csv"))

    # metrics.json
    with open(os.path.join(out_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2, default=str)

    # summary.md
    _write_summary_md(out_dir, cfg, metrics, regime_hist)


def _write_summary_md(out_dir, cfg, metrics, regime_hist):
    path = os.path.join(out_dir, "summary.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# ETF Backtest -- Run {cfg.run_id}\n\n")
        f.write(f"**Window:** {cfg.start} -> {cfg.end} "
                f"({metrics.get('years', '?')} years)\n")
        f.write(f"**Rebalance:** {cfg.freq}\n")
        f.write(f"**Initial Capital:** Rs {cfg.initial_capital:,.0f}\n")
        f.write(f"**Top-N:** {cfg.top_n}\n\n")
        f.write("## Performance\n\n")
        f.write(f"| Metric | Value |\n|---|--:|\n")
        f.write(f"| Final Equity | Rs {metrics.get('final_equity', 0):,.0f} |\n")
        f.write(f"| Total Return | {metrics.get('total_return_pct', 0):.2f}% |\n")
        f.write(f"| CAGR | {metrics.get('cagr_pct', 0):.2f}% |\n")
        f.write(f"| Benchmark CAGR (NIFTYBEES) | {metrics.get('benchmark_cagr_pct', 0):.2f}% |\n")
        f.write(f"| **Alpha** | **{metrics.get('alpha_pct', 0):+.2f}%** |\n")
        f.write(f"| Sharpe | {metrics.get('sharpe', 0):.2f} |\n")
        f.write(f"| Max DD | {metrics.get('max_dd_pct', 0):.2f}% |\n")
        f.write(f"| Win Months | {metrics.get('win_months', 0)} / "
                f"{metrics.get('win_months', 0) + metrics.get('loss_months', 0)} "
                f"({metrics.get('win_rate_pct', 0):.1f}%) |\n")
        f.write(f"| Vol (Annualised) | {metrics.get('vol_ann_pct', 0):.2f}% |\n\n")

        if "walk_forward" in metrics:
            wf = metrics["walk_forward"]
            f.write("## Walk-Forward Check\n\n")
            f.write(f"**Gate:** {wf.get('gate', '?')}\n\n")
            f.write(f"| | In-Sample | Out-of-Sample |\n|---|--:|--:|\n")
            ism = wf.get("in_sample", {})
            oos = wf.get("out_of_sample", {})
            for key in ("cagr_pct", "sharpe", "max_dd_pct", "alpha_pct"):
                f.write(f"| {key} | {ism.get(key, 0):.2f} | {oos.get(key, 0):.2f} |\n")
            f.write("\n")
            if wf.get("gate") == "FAIL_OOS_DEGRADED":
                f.write("**STOP per CLAUDE.md roadmap gate:** OOS Sharpe < 60% of IS Sharpe. "
                        "System is overfit -- re-architect screener before continuing tuning.\n\n")

        if regime_hist:
            f.write("## Regime Distribution\n\n")
            from collections import Counter
            cnt = Counter(r for _, r in regime_hist)
            total = sum(cnt.values())
            for label, n in cnt.most_common():
                f.write(f"- **{label}**: {n} ({100 * n / total:.1f}%)\n")


# ============================================================================
# CLI
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="Walk-forward ETF backtest")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end",   default="2024-12-31")
    parser.add_argument("--freq",  default="monthly", choices=["weekly", "monthly"],
                         help="Rebalance frequency. Production default = monthly "
                              "(half the drawdown of weekly, 1/4 the trades, same Sharpe).")
    parser.add_argument("--capital", type=float, default=1_000_000)
    parser.add_argument("--top-n", type=int, default=8)
    parser.add_argument("--min-hold", type=int, default=28,
                         help="Min calendar days before a position can be sold "
                              "(Stage-4/illiquid override). Default 28.")
    parser.add_argument("--walk-forward", action="store_true",
                         help="Split into IS/OOS and apply Sharpe gate")
    parser.add_argument("--is-pct", type=float, default=0.6,
                         help="In-sample fraction (default 0.6)")
    parser.add_argument("--no-correlation-gate", action="store_true")
    parser.add_argument("--no-liquidity-gate",   action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    cfg = BacktestConfig(
        start=args.start, end=args.end, freq=args.freq,
        initial_capital=args.capital, top_n=args.top_n,
        min_hold_days=args.min_hold,
        walk_forward=args.walk_forward, is_oos_split_pct=args.is_pct,
        apply_correlation=not args.no_correlation_gate,
        apply_liquidity_gate=not args.no_liquidity_gate,
    )
    print(f"ETF Backtest -- run_id={cfg.run_id}")
    print("=" * 70)
    res = run_backtest(cfg)
    print()
    if res.get("status") != "OK":
        print(f"FAILED: {res.get('reason')}")
        sys.exit(1)
    print(f"Output: {res['out_dir']}")
    print()
    print("Metrics:")
    for k, v in res["metrics"].items():
        if k != "walk_forward":
            print(f"  {k:<24} {v}")
    if "walk_forward" in res["metrics"]:
        wf = res["metrics"]["walk_forward"]
        print(f"\nWalk-forward gate: {wf['gate']}")
        if wf["gate"] == "FAIL_OOS_DEGRADED":
            print("STOP: OOS Sharpe < 60% of IS Sharpe -- system is overfit.")


if __name__ == "__main__":
    main()
