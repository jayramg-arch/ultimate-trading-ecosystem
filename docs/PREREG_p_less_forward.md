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
