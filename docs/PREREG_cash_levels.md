# Pre-registration — can a cash-only name get a LEVEL CHECK worth having?

**Written 23 September 2026, BEFORE any of it was measured.** Hypotheses, parameters, pass
bars, the multiple-testing correction and the stopping rule are fixed here. The analysis
runs **once** against this file. Anything learned that is not written below is a *finding
to pre-register next time*, never a result to report as though it had been predicted.

*Why this exists.* Since 21 September the reviewer answers the plan's four levels — entry,
stop, T1, T2 — against the options book: call wall, put wall, max pain, futures basis. On a
cash-only name it prints "no options — cash-only name" and falls through to footprint delta
alone. Roughly half the board is cash-only, so half the names get no level validation at
all. This asks whether the cash substitutes carry the same information.

**Read the prior before reading the hypotheses.** P3 (22-Sep) pre-registered four
derivative rules and **all four failed**. The rules in `level_check()` are display-only
today for exactly that reason, and the printed block says so. The base rate for "plausible
level rule survives measurement" in this estate is, so far, zero out of four. The expected
outcome here is failure, and failure is a result — it stops half the board acquiring a
confident-sounding number that predicts nothing.

---

## The substitution being tested

Each options input is asking a question. The claim under test is that the cash column
answers the *same* question, not merely a similar-sounding one.

| Options input | The question | Cash substitute |
|---|---|---|
| Call wall | Where is size committed above, that will defend? | **VAH**, and the nearest **HVN** above entry |
| Put wall | Where is the defended floor? | **VAL** |
| Max pain | What price is a magnet? | **POC** |
| Futures long basis | What did the trapped cohort pay? | **AVWAP-BO** |
| ATM ΔOI | Is commitment building or leaving? | **Delivery %** vs its own 20-day mean |
| Footprint delta | Flow on the bar | unchanged — already symbol-agnostic |

**The epistemic downgrade is real and is not being papered over.** An options wall is a
*forward* commitment: someone has written that strike and must defend it or buy it back. A
POC or an AVWAP is a *backward* record of where trade already happened. They can coincide
without being the same kind of fact. H0 exists precisely to test whether they coincide at
all before anything is built on the assumption.

## Data

| | |
|---|---|
| Trades | `validation_runs/validation_20260819_112959_details.csv` — 515 bull trades, 20 monthly anchors, matched-horizon, catalyst-aware windows, RRG/forming-week fixes in. The same file P3 used, so the two are directly comparable. |
| Primary population | **cash-only** names — the complement of P3's F&O set (measured overlap there: 156 of 307 symbols had F&O). These are the names the rule would actually serve. |
| Secondary population | F&O names, for **H0 only** — the only place both columns exist, so the only place the substitution can be checked against ground truth. |
| Price / volume | daily OHLCV from `data_provider`, pinned to the trade's `as_of`. No forward information: every profile is built from bars **strictly before** the entry bar. |
| Delivery | NSE `sec_bhavdata_full` daily bhavcopy (`DELIV_PER`), backfilled the same way `fno_bhavcopy.py` did the F&O book. **This file does not exist yet — building it is a prerequisite, not part of the test.** If the backfill cannot reach the trade window, H5 is reported as NOT RUN rather than run on a short sample. |

## Parameters — fixed here so they cannot be tuned later

Every number below is chosen now, from convention, not from looking at outcomes.

| Parameter | Value |
|---|---|
| Volume-profile lookback | **120 trading days** ending on the bar before entry |
| Profile bins | **50** |
| Value area | **70%** of volume around the POC |
| HVN | a bin whose volume is **≥ 1.5 ×** the mean bin volume |
| AVWAP-BO anchor | the most recent day whose close was a **20-day high** on volume **≥ 1.5 ×** its 50-day average |
| Delivery baseline | **20-day mean** of `DELIV_PER`, compared to the entry day's value |
| Ceiling for H1/H2 | nearest of {VAH, first HVN above entry} that lies **above entry** |
| Floor for H3 | **VAL** |

If a parameter turns out to matter, that is a *new* pre-registration, not an edit to this one.

## Hypotheses

**H0 — construct validity (gate for everything else).**
On F&O names, where both columns exist, the cash substitute locates the same price as the
options book.

- `|VAH − call_wall| / ATR` and `|POC − max_pain| / ATR`, median over all F&O trades.
- Control: the same distances after **shuffling** the derivatives rows across symbols
  within the same date, which destroys the pairing but keeps every marginal distribution.
- **Pass:** median distance **≤ 1.0 ATR** AND materially below the shuffled control
  (bootstrap CI of the difference excludes zero).
- **If H0 fails, H1–H4 are reported but carry no claim of substitution** — they would then
  be testing volume-profile levels on their own merits, which is a different question and
  must be labelled as such.

**H1–H4 mirror P3 exactly**, so a pass here can be read against the F&O failure there.

| # | Hypothesis | Test | Pass bar |
|---|---|---|---|
| **H1** | A T1 beyond the VP ceiling is reached **less often** | `Hit_T1` rate, split by whether the ceiling lies between entry and T1 | **≥ 10 pp** lower, n ≥ 40 per cell |
| **H2** | Capping T1 at the ceiling **improves realised R** | replay with `T1 = min(T1, ceiling − 0.25×ATR)`; mean and median R vs the shipped plan | **≥ +0.15R mean AND median not worse**, IS *and* OOS |
| **H3** | A stop **below** VAL — i.e. the defended floor sits inside the trade — stops out more | `Hit_Initial_SL` rate, split by stop vs VAL | **≥ 8 pp** higher, n ≥ 40 per cell |
| **H4** | POC inside the entry→T1 path **drags** the target | `Hit_T1` with/without, split by entry's distance from POC: **≤ 1 ATR vs > 2 ATR** | **≥ 8 pp** in the near cell, and **weaker** in the far one — an effect flat across distance falsifies the pin mechanism |
| **H5** | Entries on **rising** delivery % outperform | mean R, entry-day `DELIV_PER` above vs below its 20-day mean | **≥ +0.15R**, IS *and* OOS |

H4's conditioning variable is doing the job the expiry clock did in P3: a pin should weaken
with distance. If it does not, the result is an artifact of something else.

## Measurement rules

Unchanged from P3, because they are what make the two comparable:

1. **R, never per-trade %.** Size is risk / (k × ATR); a % metric structurally rewards wide
   stops, and it inverted a stop conclusion in this estate once already.
2. **Per family, never pooled.** POS-BO · POS-ACCUM · SWG-PB separately. Pooling two
   families has produced a false conclusion here three times.
3. **In-sample / out-of-sample** on the same chronological split the OOS gate uses.
4. **Bootstrap by symbol**, not by trade — consecutive trades on one name share an outcome
   window, so a trade-level resample overstates n.
5. **n ≥ 40 per cell**, else the cell is **thin** and cannot pass.
6. **Missing is excluded, never zero.**

### New this time: a multiple-testing correction

P3 ran four hypotheses with no correction, and this estate's largest stated statistical
liability is ~100 variants with none anywhere. H1–H5 are five tests on one dataset, so:

> Each hypothesis must clear its **effect-size bar above** *and* its bootstrap p-value must
> survive **Holm–Bonferroni at family-wise α = 0.10** across H1–H5.

Both are required. An effect that clears the size bar but not the correction is reported as
**suggestive, not passing**, and changes nothing. H0 is a validity gate, not a claim, and is
excluded from the family.

## Stopping rule

The analysis runs **once**. No re-slicing after seeing a result, no moving a threshold to
meet a bar, no dropping a family that came out wrong. A failed hypothesis is recorded as
failed **in this file**, and the corresponding line in `cash_level_check()` stays
display-only — which is all it will be at birth anyway.

## What a pass would and would not license

| | |
|---|---|
| **Would** | The passing line may print a **cap** the way the options block does ("T1 beyond the VP ceiling — reachable R is X"), and may be quoted in the reviewer's LEVEL VALIDATION. |
| **Would not** | Gate a trade, veto a GO, or change position size. Derivatives grade and never gate; a weaker backward-looking proxy does not get more authority than the thing it substitutes for. |

## Result

*(Left empty deliberately. To be filled in ONCE, by the run, against the bars above.)*

- H0 —
- H1 —
- H2 —
- H3 —
- H4 —
- H5 —
