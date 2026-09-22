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
| **H4** | Max pain inside the entry→T1 path **drags** the target | `Hit_T1` rate with/without, split by **≤ 10 vs 11–31** days to expiry | **≥ 8 pp** inside 10 days, and **weaker** further out — an effect that is flat across the expiry clock falsifies the mechanism |

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

### Amendment 1 — 22 Sep, before the run, after a placebo pass only

H4's original split (≤ 30 vs > 30 days to expiry) has an **empty control group by
construction**: the near-month contract is never more than ~31 days out, so "> 30 days"
matches nothing. Found by running the analysis in **placebo mode** (derivative columns
shuffled, every number noise) to exercise the code without spending the single real run.
The split becomes **≤ 10 vs 11–31 days**, which tests the same mechanism — pinning should
strengthen into expiry — with two populated cells. No real result has been seen at the time
of this amendment.

---

## Results — the single run, 22 September 2026

`python derivatives_p3.py` · full output in `logs/p3_run_20260922.txt` · history
1 Jul 2024 → 22 Sep 2026 (114,439 rows, 276 symbols) · **195 of the 515 trades joined**
(F&O underlyings only) across 127 symbols and the full anchor range 2024-07-15 → 2026-02-16 ·
families SWG-PB 109 · POS-BO 64 · POS-ACCUM 22.

### Verdict: **all four fail. H1 fails BACKWARDS.**

| | Predicted | Measured | Verdict |
|---|---|---|---|
| **H1** | T1 beyond the call wall reached **≥10 pp less** often | **+3.1 pp MORE** often pooled (CI95 −4.8 to +10.9). **SWG-PB +13.3 pp more, CI95 [+2.3, +24.1] — excludes zero in the WRONG direction** | **FAIL — inverted** |
| **H2** | wall-capped T1 ≥ **+0.15R** mean, median not worse, IS *and* OOS | IS **+0.150R**, **OOS −0.160R** | **FAIL — OOS** |
| **H3** | stop above the put wall stops out **≥8 pp more** | pooled +22.6 pp (CI95 [+10.5, +34.3]) but **every family ≤ 0**: SWG-PB −5.5, POS-BO −1.9, POS-ACCUM thin | **FAIL — pooled effect is composition** |
| **H4** | max pain in the path drags T1 **≥8 pp**, inside 10 days only | **+9.4 pp HIGHER** inside 10 days; −5.0 pp further out; both cells thin | **FAIL — inverted** |

### What the failures mean

**H1 is the significant one, and it points the other way.** SWG-PB trades whose T1 sat beyond
the call wall reached T1 *more* often, and that cell's CI excludes zero. One run cannot say why
— a wall between entry and a 2R target may simply mark a name whose strikes are clustered close
to price, which is not the same population as one with distant strikes. **Recorded as a finding
to pre-register, not a result to act on.**

**H3 is a textbook composition artifact** and the reason measurement rule 2 exists. Pooled, a
stop above the put wall looks decisively worse (+22.6 pp, CI excluding zero). Split by family,
**no family shows it** — SWG-PB, the only non-thin cell, runs the other way. SWG-PB both stops
out far more often (77–83%) and places more stops above walls, so the pooled number is reading
the family mix, not the wall. Pooling has now produced a false conclusion in this estate four
times.

**H2's median improved in every window** (+0.88R pooled) while its mean failed OOS — capping
turns a few big winners into moderate ones, which lifts the middle and costs the tail. The bar
was written as mean *and* median for exactly this reason. **Caveat on construction:** the capped
replay is a proxy — a trade is treated as having filled the cap when its maximum run-up reached
the wall, without bar-by-bar sequencing. A real replay could move these numbers; it cannot rescue
an OOS mean that is negative.

**Sample honesty:** only 195 of 515 trades have F&O, so most per-family × window cells are
**thin** (n < 40) and are reported as such. Nothing thin is treated as evidence either way.

### Actions taken

Per the stopping rule, no bar was relaxed and nothing was re-sliced.

- **No rule is promoted.** The wall cap does **not** become the default T1; the put-wall line
  does **not** become a sizing input; the max-pain drag stays a note. All of `level_check()`
  stays exactly what it already was: **display, never a gate**.
- **The LEVEL CHECK header now says so**, so a reader cannot mistake a printed fact for a
  validated edge: the walls are reported because a trader should see them, not because the
  backtest showed they predict.
- **"A ceiling is not a target" stays** — it is a canon-floor rule (nothing under 2R), not a
  derivatives claim, and this test says nothing about it.
- **H1's inversion is pre-registered for a future test**, with its own hypothesis and cells,
  rather than being reported now as though it had been predicted.

### What this test could not answer

Footprint (excluded by construction — TradingView-only, per-bar, unbackfillable), the *live*
question of whether seeing these facts improves Jay's own decisions (that needs scored reviews
in `logs/ai_review_log.csv`, not history), and any effect on trades taken at prices other than
the validation's entries.
