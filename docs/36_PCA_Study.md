# 36 · Principal Component Analysis — what it says about ranking (11 Oct 2026)

Question: the board and S4 **gate** names (5 gates) but do not **rank** them, and most of the
metrics we track never touch selection. Does the metric set contain independent,
outcome-predicting structure that a ranking should use — the way a quant fund builds a factor
model?

Script: `pca_study.py` (reproducible: `python pca_study.py 20260819_112959`), output
`reports/pca_study_20260819_112959.json`.

## How PCA is used professionally
1. **Factor model / dimension reduction of signals.** Many correlated signals are compressed
   into a few orthogonal factors, so a score does not count the same thing five times.
2. **Statistical risk model.** PCA on the *return covariance* of a book finds the hidden common
   drivers (the market, a sector cluster) and the number of genuinely independent bets.
   Funds cap exposure to the top components rather than to names.
3. **Alpha research** happens only *after* 1, and only with out-of-sample tests — the
   components are fitted on one period and judged on another.

## Data and rules (set before looking)
515 bull trades (24 months, Nifty 500, catalyst-aware windows, 307 symbols) with 20 metrics
recorded **at entry** and the realised outcome. PCA fitted on the first 60% of anchors only
(in-sample, to 2025-07-15), applied unchanged out of sample. Outcome in **R** (return ÷
initial risk) and in matched alpha. Symbol-block bootstrap; Benjamini-Hochberg correction.
Families (positional / swing) reported separately.

## Finding 1 — 20 metrics carry about 5 independent pieces of information
- Effective dimensions **5.4** (participation ratio); 8 components hold 80% of the variance.
- **PC1 (38%) is one momentum / extension factor**, and most of the scoring stack sits on it:
  `Score` and `Catalyst_Score` correlate **1.00** (they are the same number); `Combined_Score`
  0.97 with Score; `Alpha`, `RSI`, `EMA20_Dist_ATR`, `SL_pct`, `Broke_Pivot` 0.6–0.86 with it.
- The other components are genuinely different things: **PC2** swing/leg geometry (swing %,
  leg velocity, impulse-correction ratio), **PC3/PC4** base age and VCP, **PC5/PC7** stage,
  **PC6** counter-trend.

## Finding 2 — none of the metrics ranks stocks by future return
The pooled numbers looked strong (PC1 vs R: ρ +0.46 out of sample; top-vs-bottom tercile
+0.46R, CI excluding zero). They do not survive two checks:

| | Top Score tercile | Bottom tercile |
|---|---:|---:|
| Share positional | 86% | 7% |
| Median stop distance | 11.2% | 2.9% |
| Stopped out at the initial stop | 19% | 70% |
| Mean return | **−2.4%** | **−0.6%** |
| Mean matched alpha | +0.40% | +0.72% |

- The "high score" group is mostly **positional trades with wide stops**, which stop out less
  and so read better **in R** — while their actual **returns are worse**. That is family mix
  and stop geometry, not selection.
- **Inside the positional family nothing predicts anything** (all 9 metrics |ρ| ≤ 0.12 against
  R, alpha and return, out of sample, n = 76).
- **Inside the swing family** the metrics correlate with R only through stop width: `SL_pct`
  ρ +0.51 with R but **−0.59 with return**; extension (EMA20 distance) is −0.17 with return.
  The one weak positive: relative volume, +0.17 with matched alpha (single test, n = 138).

This is the fourth time a pooled result turned out to be family composition (see the 28–29
July swing finding). It is consistent with every earlier test: Wyckoff veto and score, the GO
confirmation filter, stop re-tunes — none added out-of-sample selection.

## Finding 3 — the book: 18 holdings ≈ 8.6 independent bets
PCA on one year of daily returns of the 18 open positions:
- **PC1 = the market**: 29% of the book's variance, correlation +0.84 with the Nifty 500;
  median beta 1.08.
- **PC2 = a financials/consumer cluster**: BAJFINANCE, TVSMOTOR, AUBANK, NESTLEIND, M&MFIN
  move together, against the pharma names.
- 8.6 effective bets is reasonable diversification (the old "effective N ~4" critique does
  not hold), but a third of the risk is one market factor — in a Bear tape that is the risk
  the open-risk budget is really measuring.

## Recommendations
1. **Do not fit a weighted ranking from this data.** A PCA- or regression-weighted composite
   would learn the family/stop artefact and present it as skill. The evidence does not
   support any metric ranking names by future return.
2. **De-duplicate the scores.** `Score`, `Catalyst_Score`, `Combined_Score`, `Alpha`, RSI and
   EMA20 distance are one factor. Any summed score (board Overall, confluence) that rewards
   several of them is counting extension several times — and extension is, if anything, a
   negative for swing returns. Show the five factors as a **profile** (momentum/extension ·
   swing geometry · base/VCP · stage · counter-trend) instead of adding them up.
3. **Rank GO names on portfolio construction, not on claimed alpha.** Among names that pass
   the gates, prefer the one that **adds an independent bet** (low loading on the book's PC1
   and on any crowded cluster such as today's financials PC2), has **room to the first
   obstacle**, and fits the **risk budget**. That is the professional use of PCA here, and it
   needs no outcome data to be valid.
4. **Measure book risk in factor terms.** Report the book's market-factor share and aggregate
   beta beside the open-risk figure; in a Bear regime, cap market-factor exposure, not just
   rupee risk per name.
5. **Pre-register a forward test.** The metrics that never reached the backtest — BFF, RFF,
   Piotroski, X-Ray, options OI, confluence, zone quality, trend grade — exist only on the
   board and in the Reviewer Log. Log them on every trigger; when there are ≥ 150 filled
   triggers spanning more than one regime, run `pca_study.py`'s method **within family**, with
   the rules above fixed in advance. Condition on the HMM regime (calm vs volatile, see the
   REGIME HMM page) as one pre-declared split, not as a search.
