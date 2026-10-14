# PRE-REGISTRATION — PA → now combo on the Daily board

**Registered:** 14 Oct 2026 (IST), before any outcome was computed.
**Owner:** Jay. **Script:** `pa_combo_study.py` (committed with this file).

## Question

The Daily GO needs the PA battery to fire on the **latest** bar. A pattern that fired one
to three bars back is lost even when price has followed through. Jay's proposal: find the
last PA bar and grade the bars **from the PA bar to the latest bar as one candle**; if that
combined candle is bullish, treat the PA as still standing.

## Definitions (fixed now)

- **Universe:** `nifty500_symbols.json`, daily bars from the cache, the last 2 years.
  Bull battery only (`pa_patterns.detect_bull_patterns`); recovery has no measured edge.
- **Qualification on day t** (a proxy for the board's context gate, applied to every
  cohort alike): close > SMA150 and SMA150 above its value 20 sessions earlier.
- **Combo** = `gm_trigger_board.pa_combo` — the one function the board uses. Combined
  candle: PA bar's open, highest high and lowest low since, latest close; graded by
  `bar_grade` (weak / neutral / strong). `held` = latest close ≥ PA bar close;
  `kept_low` = no close since below the PA bar's low.
- **Cohorts on day t:**
  - **A** — PA fired on day t (today's rule).
  - **B** — no PA on t; PA within 1–3 bars back; combo **strong**, `held` and `kept_low`.
  - **C** — no PA on t; PA within 1–3 bars back; combo **weak**.
  - **D** — the rest of the recency rows (descriptive only).
- **Entry:** next session's open. **Stop:** entry − 4 × ATR14(D) (the house positional
  floor). **Outcome:** R20 = (close 20 sessions after entry − entry) / (entry − stop),
  or −1 if any low reached the stop first. Measured in R, never per-trade %.
- **De-duplication:** one signal per symbol per 5 sessions per cohort (the first).
- **Windows:** chronological split by signal date, first 60 % in-sample, last 40 %
  out-of-sample.
- **Uncertainty:** 95 % CI from 2,000 bootstrap resamples **by symbol** (signals on one
  name share outcome windows).

## Hypotheses

- **H1 (promotion):** B is not worse than A. Passes only if, in **both** windows,
  mean R20(B) − mean R20(A) ≥ −0.05 R, median R20(B) is not below median R20(A) by
  more than 0.10 R, and the CI lower bound of the mean difference is above −0.15 R.
- **H2 (the grade discriminates):** mean R20(B) − mean R20(C) ≥ +0.15 R in both windows,
  with the CI excluding 0.
- Each cohort needs **n ≥ 100** signals per window, or that cell is THIN and cannot pass.

## Decision rule

- H1 and H2 pass → promote: the Daily GO accepts a PA 1–3 bars back when the combo is
  strong, held and kept its low, on the board **and** in S4 (S4 work scheduled then).
- H1 passes, H2 fails → the combo adds nothing over plain recency; do not promote the
  grade (recency itself can be raised as a separate question).
- H1 fails → stays display-only.

## Discipline

- `--placebo` (cohort labels shuffled across all recency rows) is run first to debug the
  code; H2 must fail on it. The real analysis then runs **once**. A failed hypothesis is
  recorded as failed, not re-sliced.
- Known biases, stated now: today's nifty500 list (survivorship); a proxy context gate,
  not the full board qualification; entry at the next open ignores the S4 buy-stop.
- Forward record: the Daily board logs every combo row to `logs/pa_combo_ledger.csv`.
  It is counted, not scored, until the historical result is in.
- Disclosure: before this file was committed, the scan was smoke-tested on ONE symbol
  (TITAN, 224 signals) to check it runs; its cohort means were printed. No other outcome
  was seen. TITAN stays in the universe.

## RESULT (14 Oct 2026, run once) — H1 PASS · H2 FAIL → the grade adds nothing

33,466 signals after de-dup (nifty500, 2024-09-06 .. 2026-09-11; split 2025-11-12).
Placebo first: H2 failed with shuffled labels, as required.

| | IS mean / median R20 | OOS mean / median R20 |
|---|---|---|
| A  PA today | −0.067 / −0.124 (n 7,466) | −0.036 / −0.088 (n 4,907) |
| B  PA 1–3b, strong + held + kept low | −0.095 / −0.142 (n 2,120) | −0.047 / −0.074 (n 1,462) |
| C  PA 1–3b, weak combo | −0.069 / −0.118 (n 5,787) | −0.013 / −0.056 (n 3,803) |
| D  other recency rows | −0.079 / −0.129 (n 4,766) | −0.040 / −0.096 (n 3,155) |

- H1 (B not worse than A): PASS in both windows (B−A −0.028 R IS, −0.011 R OOS; CIs
  straddle 0).
- H2 (B beats C by 0.15 R): FAIL in both windows — B is slightly *worse* than C
  (−0.026 R IS, −0.033 R OOS; CIs straddle 0).
- Decision per the rule above: do **not** promote the combo grade. A bullish
  follow-through candle after the PA does not pick better trades than a weak one.
- Not concluded here (would be re-slicing): that a PA 1–3 bars back is as good as one
  today. A, B, C and D all sit within ~0.06 R of each other, which points that way, but
  the hypothesis was not registered; it needs its own pre-registration.
- Context: every cohort is slightly negative at 20 sessions with a next-open entry —
  this test measures the timing question only, not the system's edge.
Output: `reports/pa_combo_result_20261014.txt`.
