# PA Field Validation Report — NIFTY100

**Generated:** 2026-05-24 09:17
**Universe:** NIFTY100 (10/10 symbols loaded successfully)
**Period:** 5y (catalyst-aware horizons per state)
**Benchmark:** ^CRSLDX
**Bootstrap iterations:** 1,000
**Total trades:** 3,542
**Compute time:** 0.1 min

---

## Per-State Effectiveness (sorted by mean alpha)

| State | Horizon (d) | N Trades | Mean Alpha % | Median Alpha % | Win Rate % | Alpha CI95 (lo, hi) | P(α > 0) % |
|---|---:|---:|---:|---:|---:|:---:|---:|
| **HAMMER_AT_200SMA** | 60 | 10 | +4.33 | +6.61 | 70.0 | (-2.58, +11.78) | 89 |
| **SPRING** | 120 | 45 | +3.36 | -2.75 | 44.4 | (-3.07, +10.40) | 86 |
| **DISTRIBUTION_DAY** | 30 | 1,063 | +0.67 | -0.42 | 48.4 | (+0.09, +1.28) | 99 |
| **STAGE_2_LAUNCH** | 180 | 8 | +0.60 | -3.93 | 37.5 | (-10.35, +11.69) | 55 |
| **THREE_BAR_REV** | 20 | 116 | +0.30 | -0.67 | 47.4 | (-1.42, +1.92) | 63 |
| **IB_NR7_COIL** | 10 | 653 | +0.07 | -0.49 | 45.3 | (-0.41, +0.54) | 62 |
| **HAMMER_REVERSAL** | 15 | 402 | +0.07 | -0.48 | 47.8 | (-0.70, +0.84) | 57 |
| **UNDERCUT_50SMA** | 45 | 155 | -0.18 | -1.88 | 42.6 | (-2.14, +1.65) | 42 |
| **POCKET_PIVOT** | 30 | 664 | -0.35 | -1.32 | 44.4 | (-1.06, +0.35) | 17 |
| **SHOOTING_STAR_RESIST** | 20 | 36 | -0.49 | -1.57 | 44.4 | (-3.14, +1.96) | 34 |
| **OUTSIDE_BAR_BULL** | 15 | 255 | -0.73 | -0.98 | 43.9 | (-1.56, +0.07) | 4 |
| **GAP_UP_BO** | 90 | 79 | -0.99 | -1.20 | 44.3 | (-4.86, +3.06) | 30 |
| **BULL_ENGULF** | 20 | 16 | -1.02 | -1.23 | 37.5 | (-4.07, +2.07) | 25 |
| **FAILED_BREAKOUT** | 30 | 12 | -2.32 | -2.03 | 41.7 | (-7.78, +3.90) | 21 |
| **HAMMER_AT_50SMA** | 30 | 14 | -2.43 | -3.40 | 35.7 | (-7.32, +2.38) | 17 |
| **VCP_BO** | 90 | 14 | -5.91 | -10.14 | 35.7 | (-12.38, +0.71) | 4 |

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
