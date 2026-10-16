# PRE-REGISTRATION — 75m / 125m PA recency allowance

**Registered:** 16 Oct 2026 (IST), before any outcome was computed.
**Owner:** Jay. **Script:** `pa_recency_intraday_study.py` (committed with this file).

## Question

The Daily board now lets a PA 1–3 sessions back satisfy the PA gate and reach 5/5 GO
(`PREREG_pa_recency_daily.md`, H PASS). The 75m and 125m boards have let a PA 1–3 *bars*
back satisfy the PA gate since 31 Jul 2026, but capped the row at 4/5 because it was never
tested. Swing names are timed on these boards (plan clock), so a swing name whose PA fired
a bar or two ago can never reach 5/5. Is a PA 1–3 bars back as good an entry signal, on the
trigger timeframe, as a PA on the current bar? If yes for a timeframe, its cap is lifted.

## Definitions (fixed now)

- **Universe / bars:** the cached 25-minute Dhan bars in `validation_runs/_intraday_cache`
  (979 windows, 395 qualified catalyst names, 2023-07 .. 2026-07), merged per symbol
  (duplicate timestamps dropped), resampled with `pa_patterns.resample_intraday` to 75 and
  125 minutes; Dhan's zero-volume 15:30 stub dropped (as the board and `intraday_replay.py`).
- **Battery on bar j:** `pa_patterns.detect_bull_patterns(window, "", intraday=True,
  ema20_ref, ema10_ref)` over the 250 bars ending at j, with the DAILY EMA20/EMA10 of the
  sessions completed before bar j's day (the board's call). Σ = sum of fired weights.
- **Qualification on bar j** (the Daily test's proxy, on completed sessions only): the last
  completed daily close > SMA150, and SMA150 above its value 20 sessions earlier.
- **Cohorts on bar j:** **A** PA on j · **R** none on j, PA on one of j−1..j−3 (the allowance)
  · **E** none on j..j−3, PA on j−4..j−6 (descriptive) · **F** none on j..j−6 (descriptive).
- **Entry:** the next bar's open. **Stop:** entry − 1.5 × ATR14(D) (the house swing floor,
  `house_policy.SWING_STOP_FLOOR_ATR_D`; these boards time swing plans). **Outcome:** R over
  the next 5 sessions (25 bars on 75m, 15 bars on 125m): −1 if any bar's low reaches the stop
  first, else (close of the last bar − entry) / risk. A horizon that crosses a gap in the
  cached data (more than 12 calendar days from entry to its last bar) is dropped.
- **De-duplication:** one signal per symbol per cohort per 5 sessions (the first).
- **Windows:** chronological split by signal date at the median, per timeframe.
- **Uncertainty:** 95 % CI from 2,000 bootstrap resamples by symbol.

## Hypothesis (one per timeframe)

- **H75 / H125 (non-inferiority):** R is not worse than A. Passes only if, in **both**
  halves, mean R(R) − mean R(A) ≥ −0.05 R, median R(R) is not below median R(A) by more than
  0.10 R, and the CI lower bound of the mean difference is above −0.15 R. A and R each need
  n ≥ 100 per half, or that half is THIN and cannot pass.

## Decision rule

- H passes on a timeframe → that board's recency cap is lifted: a recency row can reach
  `5/5 GO · PA nb`, exactly as the Daily board. S4 gets the same allowance on that chart
  timeframe (one change, after the market).
- H fails → that board keeps the 4/5 cap. The two timeframes are decided separately.
- E and F are reported, never used to decide.

## Discipline

- `--placebo` (A/R labels shuffled) runs first, to check the plumbing only — a shuffle makes
  A and R equal, so H is expected to pass on it. The real analysis then runs **once**.
- Disclosure: these cached bars were used by `intraday_replay.py` (Entry optimizer Step A,
  2 Oct 2026), which measured GO-timed entries. No outcome by PA AGE was computed there or
  anywhere else; this split has not been seen.
- Known biases: the universe is names that qualified as catalysts (not the whole board);
  survivorship; a proxy context gate; next-bar-open entry, not S4's retest; a fixed 5-session
  horizon rather than the trail. The test is the A-vs-R DIFFERENCE, not the level.
- Disclosure: before this file was committed, the scan was smoke-tested on ONE symbol
  (TITAN, 3 windows) to check it runs. Only its signal COUNTS per cohort were printed
  (75m A 291 / R 413; 125m A 169 / R 238); no outcome was printed. TITAN stays in.

## RESULT (16 Oct 2026, run once) — H75 PASS · H125 PASS → cap lifted on both boards

347,796 signals built; after de-dup 32,029 (75m) and 26,559 (125m), 2023-07 .. 2026-07.
Placebo first: passed, as expected for a shuffle.

| | 75m 1st half | 75m 2nd half | 125m 1st half | 125m 2nd half |
|---|---|---|---|---|
| A  PA on the bar | +0.247 / +0.117 (4,738) | +0.039 / −0.074 (4,666) | +0.215 / +0.107 (4,119) | +0.037 / −0.074 (4,045) |
| R  PA 1–3 bars back | +0.255 / +0.130 (4,878) | +0.035 / −0.050 (4,813) | +0.214 / +0.109 (4,275) | +0.019 / −0.058 (4,238) |
| E  PA 4–6 back | +0.232 / +0.101 | +0.020 / −0.068 | +0.193 / +0.109 | +0.036 / −0.052 |
| F  none in 6 | +0.207 / +0.099 | +0.043 / −0.050 | +0.146 / +0.048 | +0.065 / −0.046 |

(mean / median R over 5 sessions, n in brackets)

- R − A: 75m +0.008 R (CI −0.034..+0.052) and −0.004 R (CI −0.041..+0.034); 125m −0.001 R
  (CI −0.046..+0.045) and −0.018 R (CI −0.061..+0.024). Median gaps all ≥ 0. PASS everywhere.
- Decision per the rule: both boards lift the 4/5 cap (a recency row can read `5/5 GO · PA nb`);
  S4 gets the allowance on 75m/125m charts too.
- Observation, NOT a conclusion: as on the Daily test, F (no PA in six bars) sits close to A
  (2nd halves slightly above). The allowance is safe; it is not evidence the PA gate selects
  better entries.
Output: `reports/pa_recency_intraday_result_20261016.txt`.
