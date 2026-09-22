# Pre-registration — do the derivatives improve the levels? (P3)

**Written 22 September 2026, BEFORE the data was looked at.** Hypotheses, cells, pass bars
and the stopping rule are fixed here; the analysis runs once against this file. Anything
learned that is not in this document is a **finding to pre-register next time**, never a
result to report as though it had been predicted.

*Why the formality.* This estate has run ~100 validation variants, four alpha-selected
sweeps and three A/Bs whose winners became defaults, with no multiple-testing correction
anywhere — the "hundreds of iterations" strength is also its largest statistical liability.
Six additions have been tested and **rejected**, one of them backwards. The derivatives
layer (P0–P2) currently only *grades*; this test decides whether any of it earns the right
to change a number.

---

## The question

S4 prints the call wall, the put wall, max pain and the futures basis. Since 21 September
the reviewer's LEVEL CHECK answers the plan's four levels against them. **Does that
information actually predict anything, or does it only sound like it should?**

## Data

| | |
|---|---|
| Derivatives | `data/fno_history.csv` — NSE F&O bhavcopy, one row per symbol per day: near-month futures OI / ΔOI / settle, PCR, max pain, call wall, put wall, CE/PE OI, ATM ΔOI, days-to-expiry. Reconstruction verified identical to the live chain (UNOMINDA 18-Sep: max pain 1240.0, walls 1300/1200, PCR 0.73). |
| Trades | `validation_runs/validation_20260819_112959_details.csv` — 515 bull trades, 20 monthly anchors, matched-horizon, catalyst-aware windows, the RRG/forming-week fixes in. |
| Join | trade's `as_of` × `Symbol` → the derivatives row of the **same date** (the settled reading of the day the trade was taken). No forward information. |
| Coverage | Only F&O underlyings have walls; cash-only names are **excluded, not imputed**. Measured overlap before backfill: 156 of 307 symbols. |

**Known limitation, stated up front:** the walls are the *near-month* book on the entry
date. A positional trade held 120–180 days outlives several expiries, so any wall effect
should be **strongest on short holds and weakest on long ones**. If an effect appears
*equally* at all horizons that is evidence of an artifact, not of a mechanism.

## Hypotheses

Each is directional, stated as the derivatives doctrine would predict.

| # | Hypothesis | Test | Pass bar |
|---|---|---|---|
| **H1** | A T1 beyond the call wall is reached **less often** than one that sits below it | `Hit_T1` rate, split by whether the wall lies between entry and T1 | **≥ 10 pp** lower, n ≥ 40 per cell |
| **H2** | Capping T1 at the wall **improves realised R** | replay each trade with `T1 = min(T1, wall − 0.25×ATR)`; compare mean and median R against the shipped plan | **≥ +0.15R mean AND median not worse**, in-sample *and* out-of-sample |
| **H3** | A stop **above** the put wall stops out more often | `Hit_Initial_SL` rate, split by stop vs wall | **≥ 8 pp** higher, n ≥ 40 per cell |
| **H4** | Max pain inside the entry→T1 path **drags** the target | `Hit_T1` rate with/without, split by ≤ 30 vs > 30 days to expiry | **≥ 8 pp**, and **only** inside 30 days — an effect that persists past expiry falsifies the mechanism |

**Footprint is deliberately excluded.** `request.footprint()` is TradingView-only and
per-bar; it cannot be reconstructed for a past date by any feed wired here, so it can never
be backtested and stays a live confirmation only. Saying so now prevents a later claim that
it was "validated".

## Measurement rules

1. **R, never per-trade %.** Position size is risk / (k × ATR), so a % metric structurally
   rewards wide stops — it inverted a stop conclusion here once already.
2. **Per family, never pooled.** POS-BO · POS-ACCUM · SWG-PB separately. Pooling two
   families has produced a false conclusion in this estate three times.
3. **In-sample / out-of-sample** by the same chronological split the OOS gate uses; a result
   that exists only in-sample fails.
4. **Bootstrap by symbol**, not by trade — consecutive trades on one name share their
   outcome window, so a trade-level resample overstates n.
5. **n ≥ 40 per cell.** Below that the cell is reported as **thin** and cannot pass.
6. **Missing is excluded, never zero.** A name with no wall drops out of that test.

## Stopping rule

The analysis is run **once**. No re-slicing after seeing the result; no changing a threshold
to make a bar. If a hypothesis fails it is recorded as failed **in this file**, and the
corresponding rule in `level_check()` stays **display-only** — which is what it already is.
Nothing here can promote a rule to a gate on its own: a gate needs this test *and* live
confirmation from the review log.

## What passing changes

| Outcome | Action |
|---|---|
| H1 + H2 pass | the wall cap becomes the **default T1** in the reviewer's plan, and the board's R:R is computed against it |
| H3 passes | the stop-vs-put-wall line is promoted from a note to a **sizing input** |
| H4 passes | the max-pain drag applies **only** inside 30 days to expiry, and says so |
| Any fails | the line stays informational; it is still printed, because a trader reading the book is not the same as a rule trading it |

---

## Results

*(filled in by the single run, 22 September 2026 — see `derivatives_p3.py` and the section
appended below)*
