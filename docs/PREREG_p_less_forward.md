# PRE-REGISTRATION — P-less 5/5 on the live boards

**Registered:** 16 Oct 2026 (IST), before any outcome was computed.
**Owner:** Jay. **Script:** `p_less_study.py` (committed with this file).

## Question

`PREREG_pa_selects.md` FAILED: on historical data the PA gate did not select better trades.
If P stopped being a gate, rows that pass every other gate but have no PA (`4/5 · no PA`)
would reach 5/5 — about 7 more name-days a session across the three boards (18 Aug–16 Oct).
Are those rows as good as the 5/5 rows the boards admit today, on the live boards themselves?

## Data and definitions (fixed now)

- **Source:** `logs/gm_signal_log.csv` — every board rebuild writes every row with its S4-GO
  label. Rows from **2026-08-18** (the five-gate GO). The log's outcome columns were never
  filled; outcomes are computed fresh here from the cached Daily bars, the same way for both
  groups. No outcome of this split has been seen.
- **Groups** (rows whose label does NOT start with the plan-clock tag `⏱` — the board's own
  clock): **GO** = label starts `5/5` · **NOP** = label contains `4/5 · no PA` (every gate but
  P passed).
- **De-duplication:** one row per symbol per board per group per 5 sessions (the first).
- **Entry:** the open of the first session after the signal date (same for both groups;
  an approximation for 75m/125m rows, whose live entry would be intraday).
- **Stop / horizon by board:** Daily = positional: entry − 4 × ATR14(D), R over 20
  sessions. 75m and 125m = swing: entry − 1.5 × ATR14(D), R over 5 sessions. R = −1 if a
  daily low reached the stop first, else (close at the horizon − entry) / risk.
- **Matured rows only:** the full horizon must have closed by the run date.
- **Uncertainty:** 95 % CI from 2,000 bootstrap resamples by symbol.

## Hypothesis (pooled across the three boards; per board descriptive)

- **H (non-inferiority):** NOP is not worse than GO. Passes only if mean R(NOP) − mean R(GO)
  ≥ −0.10 R, median R(NOP) is not below median R(GO) by more than 0.15 R, and the CI lower
  bound of the mean difference is above −0.30 R. Each group needs n ≥ 60, or the result is
  THIN and cannot pass. (Looser than the historical tests because the live sample is small
  and came from one mostly-BEAR regime; the CI bound is what stops a lucky small sample.)

## Decision rule

- **Now (first run, 16 Oct):** H passes → P-less is supported on the live boards too; Jay
  decides whether to turn P into a tag. H fails or THIN → P stays a gate.
- **Forward confirmation:** the same script runs once more on **2026-12-15** using ONLY rows
  whose signal date is after 2026-10-16 (`--after 2026-10-16`). If P has been made a tag by
  then and that run fails, the change is reverted.
- Per-board numbers are reported, never used to decide.

## Discipline

- `--placebo` (GO/NOP labels shuffled) runs first, to check the plumbing only — H is
  expected to pass on it (a shuffle makes the groups equal).
- Known biases: one regime (Aug–Oct 2026, mostly BEAR/NEUTRAL); next-session-open entry; a
  fixed horizon, not the trail; before 2 Oct the boards had no plan clock, so early intraday
  rows include positional names scored on the swing rule (both groups alike).

## AMENDMENT 1 (16 Oct 2026, before the real run — placebo output only)

The first placebo FAILED, which a shuffle should not do. Cause: about 45 % of outcomes sit at
exactly −1 R (stopped), so a group median jumps between −1.0 and about −0.4 on noise. Over 40
placebo shuffles (no real labels), each criterion failed this often with NO real difference:

| criterion | false fails |
|---|---|
| median gap ≥ −0.15 R | 9 / 40 (23 %) — unusable |
| mean gap ≥ −0.10 R | 5 / 40 (12 %) — conservative, kept |
| stop-out rate worse by > 10 pp | 0 / 40 |

**Change:** the median condition is replaced by **stop-out rate(NOP) − stop-out rate(GO) ≤ +10
percentage points**. The mean and CI conditions are unchanged. Nothing else changes, and the
real split had not been computed when this was written.

## RESULT (16 Oct 2026, first run) — H PASS (low power) → P-less supported; forward run 15 Dec

535 rows after de-dup, 461 matured and scored (signals 18 Aug .. mid-Oct; Daily rows need 20
sessions so only 63 matured).

| board | GO mean / median R (n) | NOP mean / median R (n) | stopped GO / NOP |
|---|---|---|---|
| Daily | −0.425 / −0.520 (28) | −0.408 / −0.397 (35) | 32.1 / 31.4 % |
| 75m | −0.372 / −0.478 (157) | −0.323 / −0.728 (58) | 43.3 / 46.6 % |
| 125m | −0.393 / −0.508 (125) | −0.348 / −0.823 (58) | 44.0 / 48.3 % |
| **pooled** | (310) | (151) | stop-out gap **+1.1 pp** |

- NOP − GO mean **+0.033 R**, CI **−0.155 .. +0.232**; stop-out gap +1.1 pp → PASS.
- Placebo (amended test, seed 7) still FAILED, narrowly (stop-out gap +10.5 pp, CI low
  −0.311): the test errs toward FAIL under no difference, so this does not inflate the PASS.
- Low power: the CI still allows NOP to be up to 0.155 R worse. Both groups are NEGATIVE in
  this BEAR/NEUTRAL window — this measures P's value, not the system's edge.
- Decision per the rule: P-less is supported; turning P into a tag is Jay's call. The forward
  confirmation runs on **2026-12-15**: `python p_less_study.py --run --after 2026-10-16`.
Output: `reports/p_less_result_20261016.txt`.
