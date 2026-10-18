# PREREG · the Minervini template as a v2 eligibility filter (18 Oct 2026)

Jay (18 Oct): does adding Minervini's trend template to Clenow's eligibility help the v2 rank?
Written BEFORE any number below exists.

## What is tested

- **Baseline:** V2H_LIVE (the live v2 book: P1E ensemble rank 60/90/120, top 25 %, 0.10 % equity
  per ATR20, Wednesday rebalance, 4×ATR stop, Chandelier trail, tax hold, trims, B8 top-up, ETF
  sleeve, sector cap, correlation block, per-trade cap), on the survivorship panel
  (`survivorship_backtest.PANEL`, point-in-time top 500), 2018-06 → 2026, halves split at
  `v2_backtest.SPLIT`.
- **T8 (primary):** baseline + the template as an ELIGIBILITY rule for stocks: a name must score
  **8/8** at the decision close. Eligibility governs both entry and hold (Clenow's semantics: a
  holding that fails it leaves the pool and is sold at the next rebalance like any ineligible
  name). ETFs are not touched.
- **The template, point-in-time** (`commander_core.minervini_checks`, vectorised): close of d vs
  SMA50/150/200 of daily closes; SMA200 vs its value 21 sessions earlier; 52-week high/low =
  252-session max High / min Low; RS = JdK RS-Ratio > 100 on CONFIRMED weekly bars vs the Nifty 500
  (STRIKE_CAL 25/10, the bull_screener formula; fewer than 52 weekly bars → RS fails).
- **Control (placebo):** a random filter with the same average pass rate as T8 among eligible
  names (draw per symbol per calendar quarter, seed 7).
- **Descriptive only:** T7 (≥ 7/8 as eligibility), T8-entry (8/8 required to BUY, ranking and holds
  unchanged), and P1E + T8 (the plain Clenow book).

## Decision rule (one run)

ADOPT T8 into V2H only if ALL hold:
1. MAR(T8) ≥ MAR(baseline) in **both** H1 and H2;
2. MAR(T8) > MAR(control) in both halves;
3. full-period max drawdown no more than 3 pp worse than the baseline.
Else REJECT; v2 stays price-only. The descriptive variants cannot be adopted from this run.

Known limits: one panel; the template adds turnover; MAR is noisy over ~8 years.

## RESULT (18 Oct 2026, run once) — REJECT: v2 stays price-only

Vectorised template checked against `commander_core.minervini_checks` first: 1 of 261 random
(symbol, date) samples differed (a thin micro-cap, one weekly-RS check). T8 passed 39.7 % of
eligible names; the placebo used the same rate.

| book | CAGR % | max DD % | MAR | MAR H1 | MAR H2 | trades/yr |
|---|---|---|---|---|---|---|
| V2H (baseline) | 17.34 | −20.09 | 0.86 | 0.74 | 1.12 | 478 |
| **T8 (primary)** | 6.83 | −31.48 | 0.22 | 0.08 | 0.60 | 1,102 |
| control: random filter | 8.21 | −30.55 | 0.27 | 0.18 | 0.57 | 1,075 |
| T7 (descriptive) | 14.21 | −23.68 | 0.60 | 0.47 | 0.92 | 773 |
| T8-entry (descriptive) | 15.56 | −22.26 | 0.70 | 0.46 | 1.22 | 533 |
| P1E (descriptive) | 19.55 | −20.87 | 0.94 | 0.78 | 1.21 | 326 |
| P1E + T8 (descriptive) | 12.23 | −27.99 | 0.44 | 0.46 | 0.60 | 939 |

All three conditions fail: T8 is below the baseline in both halves, **no better than a random
filter that removes the same share of names** (MAR 0.22 vs 0.27), and its drawdown is 11 pp deeper.
Mechanism: as eligibility, the template churns the book — a holding that drops to 7/8 is sold and
often bought back, so turnover more than doubles (478 → 1,102 trades a year). Even buy-only
(T8-entry) is below the baseline in H1 (0.46 vs 0.74). The template does not add to Clenow's
rank; the rank already selects strong trends. Output: `reports/v2_house/minervini_filter_run_20261018.txt`,
`reports/v2_house/minervini_filter_metrics.csv`.
