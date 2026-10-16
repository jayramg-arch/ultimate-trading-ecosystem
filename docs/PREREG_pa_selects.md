# PRE-REGISTRATION — does the PA gate select better trades?

**Registered:** 16 Oct 2026 (IST), before any outcome was computed.
**Owner:** Jay. **Script:** `pa_select_study.py` (committed with this file).

## Question

Every GO requires a bull PA pattern (gate P). Three earlier tests — Daily recency
(2023-05..2024-08), PA→now combo (2024-09..2026-09) and 75m/125m recency (2023-07..2026-07)
— each showed, as an unregistered observation, that inside a qualified uptrend a bar with
**no PA in the last six bars** did about as well as a bar where a PA fired. If that is true,
the PA gate is not selecting trades; it only times them. This test asks it directly, on data
none of those tests touched.

## Definitions (fixed now)

- **Universe:** `nifty500_symbols.json`, daily bars from the cache (`period="10y"`); bull
  battery `pa_patterns.detect_bull_patterns(window, "")` over the 400 bars ending at day t
  (the Daily board's call). Σ = sum of fired weights.
- **Window (unseen):** signal days from bar index 400 up to and including **2023-04-28**, so
  every 20-session outcome ends before the earliest window already examined (2023-05-30).
  Roughly 2018-05 .. 2023-04.
- **Qualification on day t** (the proxy all three earlier tests used): close > SMA150 and
  SMA150 above its value 20 sessions earlier.
- **Cohorts:** **A** PA fired on day t · **F** no PA on t..t−6 (the comparison) · **R** PA
  1–3 back and **E** PA 4–6 back (descriptive only).
- **Entry:** next session's open. **Stop:** entry − 4 × ATR14(D) (house positional floor).
  **Outcome:** R20 = (close 20 sessions after entry − entry) / risk, or −1 if a low reached
  the stop first. In R.
- **De-duplication:** one signal per symbol per cohort per 5 sessions.
- **Windows:** chronological split at the median signal date; both halves must pass.
- **Uncertainty:** 95 % CI from 2,000 bootstrap resamples by symbol.

## Hypothesis

- **H (the PA gate selects):** A beats F. Passes only if, in **both** halves, mean R20(A) −
  mean R20(F) ≥ **+0.10 R**, median R20(A) ≥ median R20(F), and the CI lower bound of the mean
  difference is above **0**. A and F each need n ≥ 100 per half, or that half is THIN.

## Decision rule

- **H passes** → the PA gate earns its place as a filter. Nothing changes.
- **H fails** → the PA gate is recorded as a TIMING cue, not a selector. No code changes
  follow from this test alone: turning P from a gate into a tag would change what reaches
  5/5 and what fires an alert, and that is Jay's decision, to be made with this result and a
  separate look at what a P-less GO would admit. The result is written into the Golden Rules.

## Discipline

- `--placebo` (A/F labels shuffled) runs first, to debug the code: H must FAIL on it (a
  shuffle makes A and F equal, so the +0.10 R bar cannot be met).
- The real analysis runs **once**; a failed hypothesis is recorded as failed, not re-sliced.
- Known biases, stated now: today's nifty500 list on a 2018-2023 window (survivorship is
  larger the older the window); a proxy context gate, not the full board qualification;
  next-open entry; a fixed 20-session horizon rather than the trail. F is defined by the
  absence of a PA, so it is not a random sample of uptrend days either.
- No outcome from this window has been computed before this file was committed.

## RESULT (16 Oct 2026, run once) — H FAIL → the PA gate times, it does not select

198,968 signals built, 81,028 after de-dup (nifty500, 2018-05-28 .. 2023-04-28, split at
2021-05-03). Placebo first: FAILED, as required.

| | A  PA today | F  no PA in 6 sessions | A − F (mean) |
|---|---|---|---|
| 2018-05 .. 2021-05 | +0.166 / +0.072 (14,611) | +0.214 / +0.088 (2,935) | −0.049 R, CI −0.167..+0.030 |
| 2021-05 .. 2023-04 | +0.109 / +0.025 (14,436) | +0.056 / +0.001 (2,992) | +0.054 R, CI +0.016..+0.091 |

(mean / median R20, n in brackets. R and E, PA 1–6 back, sit with A in both halves.)

- H fails in both halves: the first half points the wrong way; the second half has a small
  edge whose CI excludes zero, but at +0.05 R it is half the pre-registered +0.10 R bar.
- Read with the three earlier windows (2023-05 onward), the PA gate does not pick better
  trades inside a qualified uptrend; it marks a moment. Recorded in the Golden Rules.
- Per the decision rule, NO code change follows. Turning P from a gate into a tag would
  change what reaches 5/5 and what fires an alert — Jay's call, made separately.
Output: `reports/pa_select_result_20261016.txt`.
