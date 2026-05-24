# PA Field Validation Report — NIFTY500

**Generated:** 2026-05-24 13:31
**Universe:** NIFTY500 (470/500 symbols loaded successfully)
**Period:** 5y (catalyst-aware horizons per state)
**Benchmark:** ^CRSLDX
**Bootstrap iterations:** 5,000
**Total trades:** 179,492
**Compute time:** 1.0 min

---

## Per-State Predictive Effectiveness (sorted by predictive alpha)

**Predictive alpha** is sign-aware: for bullish detectors, it's stock_ret − bench_ret. For bearish detectors (predicting underperformance), it's bench_ret − stock_ret. A positive predictive alpha means the detector's directional thesis paid off. See memory/bull_market_base_rate_warning.md for why raw alpha alone misleads in bull markets.

| State | Dir | Horizon (d) | N Trades | Pred Alpha % | Median % | Win Rate % | CI95 (lo, hi) | P>0 % | Raw α % |
|---|:---:|---:|---:|---:|---:|---:|:---:|---:|---:|
| **STAGE_2_LAUNCH** | 🐂 | 180 | 469 | +14.37 | +4.49 | 56.5 | (+10.04, +19.14) | 100 | +14.37 |
| **GAP_UP_BO** | 🐂 | 90 | 4,851 | +6.69 | +1.71 | 53.7 | (+5.94, +7.41) | 100 | +6.69 |
| **VCP_BO** | 🐂 | 90 | 762 | +5.33 | -0.67 | 48.0 | (+3.34, +7.38) | 100 | +5.33 |
| **SPRING** | 🐂 | 120 | 2,412 | +4.11 | -0.99 | 48.0 | (+3.05, +5.18) | 100 | +4.11 |
| **BULL_ENGULF** | 🐂 | 20 | 201 | +3.46 | +2.16 | 55.7 | (+1.88, +5.18) | 100 | +3.46 |
| **POCKET_PIVOT** | 🐂 | 30 | 38,805 | +2.10 | +0.11 | 50.5 | (+1.97, +2.24) | 100 | +2.10 |
| **UNDERCUT_50SMA** | 🐂 | 45 | 7,066 | +2.04 | -0.34 | 48.8 | (+1.66, +2.42) | 100 | +2.04 |
| **HAMMER_AT_200SMA** | 🐂 | 60 | 331 | +1.34 | -0.28 | 48.6 | (-0.20, +2.93) | 95 | +1.34 |
| **THREE_BAR_REV** | 🐂 | 20 | 6,455 | +1.05 | -0.14 | 49.3 | (+0.81, +1.31) | 100 | +1.05 |
| **HAMMER_AT_50SMA** | 🐂 | 30 | 534 | +0.83 | +0.20 | 50.4 | (-0.06, +1.72) | 96 | +0.83 |
| **HAMMER_REVERSAL** | 🐂 | 15 | 18,137 | +0.70 | -0.03 | 49.8 | (+0.58, +0.82) | 100 | +0.70 |
| **IB_NR7_COIL** | 🐂 | 10 | 31,903 | +0.58 | -0.07 | 49.4 | (+0.51, +0.65) | 100 | +0.58 |
| **OUTSIDE_BAR_BULL** | 🐂 | 15 | 11,205 | +0.46 | -0.40 | 47.5 | (+0.29, +0.62) | 100 | +0.46 |
| **DISTRIBUTION_DAY** | 🐻 | 30 | 51,881 | -1.62 | -0.29 | 48.7 | (-1.72, -1.51) | 0 | +1.62 |
| **SHOOTING_STAR_RESIST** | 🐻 | 20 | 3,732 | -2.11 | -0.46 | 47.7 | (-2.50, -1.74) | 0 | +2.11 |
| **FAILED_BREAKOUT** | 🐻 | 30 | 748 | -2.20 | -0.46 | 48.8 | (-3.35, -1.11) | 0 | +2.20 |


---

## Regime-Conditional Predictive Alpha

Regime = benchmark close vs its 200-day SMA at entry date. Bull = bench above 200d SMA; Bear = below. Reveals whether detector edges hold across both regimes or were artifacts of one regime only.

| State | Dir | Bull N | Bull α % | Bull WR % | Bear N | Bear α % | Bear WR % |
|---|:---:|---:|---:|---:|---:|---:|---:|
| **STAGE_2_LAUNCH** | 🐂 | 366 | +16.16 | 57.9 | 85 | +7.65 | 50.6 |
| **VCP_BO** | 🐂 | 528 | +4.53 | 45.5 | 147 | +8.66 | 56.5 |
| **GAP_UP_BO** | 🐂 | 3,815 | +7.08 | 54.5 | 544 | +5.75 | 52.0 |
| **SPRING** | 🐂 | 1,327 | +1.46 | 45.6 | 762 | +8.55 | 55.0 |
| **BULL_ENGULF** | 🐂 | 95 | +1.35 | 45.3 | 78 | +6.92 | 69.2 |
| **UNDERCUT_50SMA** | 🐂 | 4,740 | +1.90 | 48.2 | 1,422 | +2.71 | 52.5 |
| **POCKET_PIVOT** | 🐂 | 29,536 | +2.41 | 51.5 | 5,092 | +1.28 | 49.9 |
| **HAMMER_AT_200SMA** | 🐂 | 263 | +1.00 | 46.4 | 68 | +2.63 | 57.4 |
| **HAMMER_AT_50SMA** | 🐂 | 409 | +0.75 | 51.8 | 78 | +2.28 | 52.6 |
| **THREE_BAR_REV** | 🐂 | 4,473 | +1.10 | 49.7 | 1,155 | +0.80 | 51.7 |
| **HAMMER_REVERSAL** | 🐂 | 11,708 | +0.65 | 49.4 | 3,956 | +0.84 | 52.3 |
| **IB_NR7_COIL** | 🐂 | 21,014 | +0.63 | 49.5 | 6,337 | +0.74 | 52.0 |
| **OUTSIDE_BAR_BULL** | 🐂 | 7,347 | +0.59 | 47.9 | 2,293 | +0.19 | 48.3 |
| **SHOOTING_STAR_RESIST** | 🐻 | 3,223 | -2.38 | 46.7 | 304 | -0.78 | 52.3 |
| **DISTRIBUTION_DAY** | 🐻 | 31,933 | -1.67 | 48.7 | 12,010 | -1.56 | 47.0 |
| **FAILED_BREAKOUT** | 🐻 | 537 | -2.30 | 49.0 | 112 | -1.36 | 45.5 |

**Reading:** if a detector's alpha is positive in BOTH regimes (and CI doesn't straddle zero), it has regime-independent edge — the strongest result. If alpha is positive in one regime and negative or zero in the other, the edge is regime-conditional.

## Interpretation Guide

- **Mean Alpha:** stock return − benchmark return over horizon, averaged across all firings.
- **Win Rate:** fraction of firings where alpha > 0.
- **Alpha CI95:** bootstrap confidence interval for the mean alpha. If the interval excludes 0, the alpha is statistically distinguishable from random.
- **P(α > 0):** probability the true mean alpha is positive, per bootstrap.
- States with N < 30 should be read with care — small-sample noise.

## Methodology Notes

- One firing = one entry. Stock held for the state's design horizon (FWD_DAYS_BY_PA_STATE).
- No SL/TP — raw signal alpha, not execution mechanics.
- Forward window is **per-state** per the project's locked window-mismatch discipline.
- Benchmark return measured over the same window as each stock trade.
- No commission, no slippage modeled at this layer (use replay.py for that).
- Multiple firings on the same symbol are independent — no position-overlap concurrency control.

## Known Simplifications vs Dashboard

- `dLockH` ≈ 20-bar rolling high shifted (vs dashboard's strict-trend locked high).
- `stage2_up` proxy = `close > 30WMA AND 30WMA rising 4w` (vs full Weinstein stage classifier).
- All other detectors verified faithful via v67.4.9/v1.1 cross-check on HDFCBANK.
