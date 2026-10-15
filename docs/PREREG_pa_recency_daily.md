# PRE-REGISTRATION — Daily PA recency allowance

**Registered:** 15 Oct 2026 (IST), before any outcome was computed.
**Owner:** Jay. **Script:** `pa_recency_study.py` (committed with this file).

## Question

The 75m and 125m boards let a bull PA that fired 1–3 bars back satisfy the PA gate
(age printed, the row capped at 4/5). The Daily board does not: the PA must fire on the
latest bar. Is a PA that fired 1–3 sessions back as good an entry signal as one that
fired today? If yes, the Daily board gets the same allowance as the intraday boards.

This was raised by `PREREG_pa_combo.md`, whose result noted (not concluded) that all its
recency cohorts sat within ~0.06 R of "PA today". That was an unregistered observation on
the 2024-09 .. 2026-09 window. **This test uses only the EARLIER, unseen window.**

## Definitions (fixed now)

- **Universe:** `nifty500_symbols.json`, daily bars from the cache (`period="5y"`).
  Bull battery only (`pa_patterns.detect_bull_patterns`, default flags — the Daily board's
  call).
- **Window (holdout):** signal days from bar index 400 (history needed by the battery) up
  to, but excluding, the first signal day the pa_combo study used (index n − 521), and
  stopping 21 bars earlier still, so no outcome window overlaps a pa_combo signal date.
  On a 1,240-bar symbol that is roughly 2023-05 .. 2024-08. Symbols without enough
  history are skipped.
- **Qualification on day t** (same proxy as pa_combo): close > SMA150 and SMA150 above
  its value 20 sessions earlier.
- **Cohorts on day t** (Σ = sum of fired pattern weights on that bar's own slice):
  - **A** — PA fired on day t.
  - **R** — no PA on t; PA fired on at least one of t−1, t−2, t−3. (The allowance.)
  - **E** — no PA on t..t−3; PA on one of t−4..t−6. Descriptive only.
  - **F** — no PA on t..t−6. Descriptive only (does PA carry any information here?).
- **Entry:** next session's open. **Stop:** entry − 4 × ATR14(D), Wilder. **Outcome:**
  R20 = (close 20 sessions after entry − entry) / (entry − stop), or −1 if any low
  reached the stop first. In R, never per-trade %.
- **De-duplication:** one signal per symbol per 5 sessions per cohort (the first).
- **Windows:** chronological split by signal date at the median — first half / second
  half. Both must pass.
- **Uncertainty:** 95 % CI from 2,000 bootstrap resamples **by symbol**.

## Hypothesis (one)

- **H (non-inferiority):** R is not worse than A. Passes only if, in **both** halves,
  mean R20(R) − mean R20(A) ≥ −0.05 R, median R20(R) is not below median R20(A) by more
  than 0.10 R, and the CI lower bound of the mean difference is above −0.15 R.
  Each of A and R needs **n ≥ 100** per half, or the half is THIN and cannot pass.

## Decision rule

- H passes → the Daily board accepts a PA 1–3 sessions back exactly as the intraday
  boards do (`pa_recent`, age tag `PA nb`, row capped at 4/5 so it never reads as a
  chart-confirmed GO). S4 is not changed (it reads the current bar; the cap exists for
  that reason).
- H fails → the Daily board stays last-bar only.
- E and F are reported, never used to decide. If F ≈ A, that is recorded as a separate
  observation (PA timing carries little information in this window) and needs its own
  registration before anything is built on it.

## Discipline

- `--placebo` (A/R labels shuffled across those rows) is run first, only to debug the
  code. Note: a shuffle makes A and R equal, so H is EXPECTED to pass on the placebo —
  the placebo checks the plumbing, not the test's power. The real analysis then runs
  **once**; a failed hypothesis is recorded as failed, not re-sliced.
- Known biases, stated now: today's nifty500 list (survivorship, larger on an older
  window); a proxy context gate, not the full board qualification; next-open entry, not
  the S4 buy-stop / retest; 2023-24 was a strong tape, so absolute R will look better than
  the pa_combo window — the test is the A-vs-R DIFFERENCE, not the level.
- No outcome from this window has been computed before this file was committed.
