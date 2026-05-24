# 04 — etf_backtest.py Guide

> **Module role:** Walk-forward backtest engine. Survivorship-corrected. Applies transaction costs + slippage. Produces equity curves, drawdowns, IS/OOS Sharpe gates.
> **Phase:** Validation (Phase 2 of the 6-phase fine-tuning roadmap).
> **Lines:** ~700.
> **Outputs:** `backtest_runs/etf_<run_id>/` directory with 7 files

---

## Why this module exists

You can't trust forward signals without rigorous backtest evidence. This module:

1. **Point-in-time correctness** — every rebalance date sees only data up to that date
2. **Survivorship correction** — only universe ETFs whose inception ≤ rebalance date
3. **Transaction costs modeled** — 0.03% commission + 2 bps slippage per side
4. **Walk-forward gate** — IS/OOS split with hard Sharpe gate (`OOS Sharpe < 60% of IS → STOP`)
5. **Mark-to-market every rebalance day** — equity curve reflects daily portfolio value

---

## User Guide

### Quick start

```bash
# Default: 2020-2024 monthly + walk-forward
python etf_backtest.py --walk-forward

# Custom window
python etf_backtest.py --start 2022-01-01 --end 2026-05-11 --walk-forward

# Weekly rebalance + Top-N=5
python etf_backtest.py --freq weekly --top-n 5 --walk-forward
```

### CLI arguments

| Flag | Default | Purpose |
|---|---|---|
| `--start` | 2020-01-01 | Backtest start date (ISO) |
| `--end` | 2024-12-31 | Backtest end date |
| `--freq` | **monthly** | weekly / monthly. Production default = monthly. |
| `--capital` | 1,000,000 | Initial capital (₹) |
| `--top-n` | 8 | Max picks per rebalance |
| `--min-hold` | 28 | Min calendar days before SELL allowed (Stage-4 / illiquid override) |
| `--walk-forward` | off | Split into IS/OOS and apply Sharpe gate |
| `--is-pct` | 0.6 | In-sample fraction (rest is OOS) |
| `--no-correlation-gate` | off | Disable correlation gate on picks |
| `--no-liquidity-gate` | off | Disable liquidity-collapse force exits |

### Output files (per run)

```
backtest_runs/etf_<run_id>/
├── config.json          (all knobs used)
├── equity_curve.csv     (daily equity + drawdown_pct + regime + holding count)
├── benchmark_curve.csv  (NIFTYBEES buy-hold, same period)
├── trades.csv           (every BUY/SELL with price + cost + quantity)
├── monthly_returns.csv  (76+ rows with strategy_pct, benchmark_pct, alpha_pct)
├── metrics.json         (CAGR, Sharpe, MaxDD, alpha, win-rate, IS/OOS breakdown)
└── summary.md           (institutional one-pager — for Sunday review)
```

### Metrics produced

```json
{
  "final_equity": 2882551.84,
  "total_return_pct": 188.27,
  "cagr_pct": 18.15,
  "vol_ann_pct": 11.16,
  "sharpe": 1.63,
  "max_dd_pct": -5.41,
  "win_months": 54,
  "loss_months": 22,
  "win_rate_pct": 71.05,
  "benchmark_cagr_pct": 12.54,
  "alpha_pct": 5.61,
  "years": 6.35,
  "walk_forward": {
    "in_sample":     { "cagr_pct": 10.81, "sharpe": 1.30, "alpha_pct": -4.01 },
    "out_of_sample": { "cagr_pct": 29.97, "sharpe": 2.08, "alpha_pct": +20.46 },
    "gate": "PASS"
  }
}
```

### Walk-forward gate logic

```
gate = PASS              if OOS Sharpe >= 60% of IS Sharpe
gate = FAIL_OOS_DEGRADED if OOS Sharpe falls below 60% threshold
gate = INSUFFICIENT_*    if either window is too short
```

This **hard gate matches Phase 2 of the 6-phase roadmap**: if FAIL_OOS_DEGRADED, the system is overfit and Phase 3 weight-fitting must NOT proceed.

### Programmatic use

```python
from etf_backtest import BacktestConfig, run_backtest

cfg = BacktestConfig(
    start="2022-01-01", end="2026-05-11",
    freq="monthly", top_n=8, min_hold_days=28,
    walk_forward=True, is_oos_split_pct=0.6,
)
result = run_backtest(cfg)
print(result["metrics"])
print("Output:", result["out_dir"])
```

### Production-locked config (12 May 2026 audit)

From `etf_config.json`:
```json
"backtest_defaults": {
  "freq": "monthly",
  "top_n": 8,
  "min_hold_days": 28
}
```

This config delivered, on the 6.35-year backtest:
- CAGR 18.15% vs NIFTYBEES 12.54% (+5.61% alpha)
- Sharpe 1.63
- Max DD only −5.41%
- Win rate 71%
- 418 trades over 6.35 years (vs 1,454 on weekly default — 71% fewer)

---

## Trading Guide

### When to backtest

| Trigger | What to test |
|---|---|
| Universe edits (new ETF added, mis-classification fixed) | Re-run baseline to verify metrics don't regress |
| Threshold tuning (LIQ_MIN_CR, stage_slope, etc.) | Run sensitivity grid around the new value |
| Before Phase 3 weight fitting | Lock the rules-based baseline first |
| Quarterly | Refresh the 6-year window — drift monitor |
| **Never** | Don't backtest a position you already have. That's hindsight. |

### Interpreting walk-forward output

**Gate = PASS** ≠ "ready to deploy fitted weights":

Look at the raw numbers, not just the gate. Production-locked config gives:
- IS alpha = −4.01% (NEGATIVE)
- OOS alpha = +20.46%

The gate passes because OOS Sharpe (2.08) > 60% × IS Sharpe (1.30 × 0.6 = 0.78). But the IS negative alpha tells you the system is **regime-dependent**. The 2020-2021 narrow-mega-cap bull was bad for rotation systems.

**Decision rule:**
- IS alpha NEGATIVE + OOS alpha STRONGLY POSITIVE = system is regime-dependent. Re-test on 2022+ window to confirm.
- IS alpha NEGATIVE + OOS alpha MODESTLY POSITIVE = potentially curve-fit. Be cautious.
- IS alpha POSITIVE + OOS alpha POSITIVE = robust. Safe to proceed with weight fitting.

### Reading the summary.md

The summary is your institutional one-pager. Key sections:

1. **Performance table** — top-line numbers
2. **Walk-Forward Check** — IS vs OOS Sharpe + alpha
3. **Regime Distribution** — what % of time in each regime

> Tip: if regime distribution is >70% RISK_ON, results may be overfit to a single market environment. Healthier distributions show 30-50% RISK_ON, 20-40% GOLD_LED/MIXED, < 10% RISK_OFF.

### Sensitivity protocol (before locking any change)

```bash
# 1. Baseline
python etf_backtest.py --walk-forward

# 2. Sub-period (confirms regime hypothesis)
python etf_backtest.py --start 2022-01-01 --walk-forward

# 3. Freq sensitivity
python etf_backtest.py --freq weekly --walk-forward
python etf_backtest.py --freq monthly --walk-forward

# 4. Concentration sensitivity
python etf_backtest.py --top-n 5 --walk-forward
python etf_backtest.py --top-n 8 --walk-forward
python etf_backtest.py --top-n 12 --walk-forward

# 5. Min-hold sensitivity
python etf_backtest.py --min-hold 0 --walk-forward    # no min-hold
python etf_backtest.py --min-hold 28 --walk-forward   # default
python etf_backtest.py --min-hold 56 --walk-forward   # double
```

Compare metrics across runs. **If two configs are within 0.5% CAGR and 0.1 Sharpe, prefer the one with lower max DD.**

### Common pitfalls

1. **Trusting OOS alpha alone** — always inspect IS alpha too. Negative IS + positive OOS = regime-dependent, not necessarily skill.
2. **Optimizing on the 2020-2026 window** — that period has a known regime shift in 2022. Fit on 2022+ if you want robustness in similar regimes.
3. **Skipping the min-hold** — `min_hold_days=0` looks good in backtest (no friction blocker) but accumulates excessive trades. Real-world commission + slippage degrade live results.
4. **Backtesting on weekly without correlation gate** — top picks become 5 correlated banking ETFs in a banking-led cycle. Correlation gate is mandatory.

### Limits & known issues

| Limitation | Impact |
|---|---|
| Equity curve approximated between rebalance days (forward-filled) | Daily DD slightly understated between rebalances |
| Slippage flat 2 bps regardless of order size | Larger positions in tier B/C ETFs realistically slip more |
| No regime-conditional weights | Phase 3 of roadmap (not yet implemented) |
| Benchmark = NIFTYBEES only | Add Sensex / 50/50 stock+gold alt benchmarks for richer alpha context |

### Files in `backtest_runs/`

Each run is preserved permanently with its full config + outputs. **Never modify** an old run — it's your audit trail. To repeat with different params, just run again — new timestamp folder.
