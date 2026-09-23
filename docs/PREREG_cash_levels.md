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
| Delivery | NSE `sec_bhavdata_full` daily bhavcopy (`DELIV_PER`) via `cash_bhavcopy.py` -> `data/delivery_history.parquet`. **BUILT 23-Sep, after this was written and before anything was measured: 1,381,433 rows · 3,191 symbols · 2024-07-01 -> 2026-09-23 (567 trading days, 12 holidays skipped). Coverage of the trade set: 307 of 307 symbols, none missing.** H5 can therefore run. `delivery_signal(symbol, as_of)` is the single accessor, shared with the live check, and it REFUSES a baseline whose 21 sessions are not contiguous — mid-backfill that silently produced a mean spanning Aug-2025 to Sep-2026. |

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

## Amendment 1 — ceiling and floor are the nearest HVN, not the value-area edge

**Made 23 September 2026, before the analysis was run, on a specification fault found by
running the live check on real panels.** Recorded here rather than silently changed.

The table above mapped the call wall to VAH and the put wall to VAL. Built on the
pre-registered 120-day daily profile, ANANDRATHI came back `POC 1785 · VAH 2090 · VAL
1703` against an entry of 2173 — **VAL sits 22% below price**. "The stop should be below
VAL" would have demanded a 22% stop on a swing trade, which is not a rule, it is a
reductio.

The fault is in the analogy, not the parameters. An options wall is **near the money by
construction** — writers sell strikes around the current price. A four-month value-area
edge has no such anchoring and drifts arbitrarily far from price. The level that *is*
anchored near price is the **HVN**: the shelf where size actually changed hands closest to
where we are trading.

So, for H1–H4:

- **Ceiling** = the lowest **HVN above entry**; VAH, then the nearest S/R above, are
  fallbacks used only when the profile yields no node on that side.
- **Floor** = the highest **HVN below entry**; VAL is the fallback on the same terms.
- POC is unchanged — a magnet is a magnet wherever it sits, and H4 already conditions on
  distance from it.

The HVN definition itself (≥ 1.5 × mean bin volume) is unchanged and was fixed before any
of this. No pass bar moves. This is the same class of amendment as P3's Amendment 1, which
fixed an empty control group found by a placebo pass — a defect in the test's construction,
caught before it consumed the single run.

## Amendment 2 — H3's direction was transcribed backwards

**Made 23 September 2026, before the analysis was run.** Found while writing the analysis
code, by checking H3 against the P3 hypothesis it claims to mirror.

H3 below reads "a stop **below** VAL — i.e. the defended floor sits inside the trade —
stops out more". That is inverted. P3's H3, which this says it mirrors exactly, is "a stop
**above** the put wall stops out more often", and the logic is plain: if the defended level
sits *above* your stop it absorbs the decline before your stop is reached, so a stop
*below* the floor should stop out **less**. The live `level_check()` already prints it that
way ("stop below the shelf — the defended shelf is inside the trade ✓").

So H3 is tested in the P3 direction: **a stop ABOVE the floor stops out MORE often**, floor
being the nearest HVN below entry per Amendment 1. The pass bar (≥ 8 pp, n ≥ 40 per cell)
is unchanged. Recording this rather than quietly testing the sensible direction, because a
pre-registration that gets silently corrected to whatever the analyst meant is not a
pre-registration.

## Amendment 3 — H2 is NOT RUN, and why

**Made 23 September 2026, before the analysis was run.**

H2 asks whether capping T1 at the ceiling improves realised R, and specifies "replay each
trade". The shipped exit ladder books 25% at T1, 25% at T2 and trails the rest, and moving
T1 changes *when* the breakeven move and the trail engage — so a faithful answer needs a
bar-level re-simulation of all 515 trades, not an arithmetic adjustment to the recorded
outcome. The details file does not carry enough to reconstruct that ladder.

H2 is therefore reported **NOT RUN**, on the same principle the data section already
applies to H5 ("reported as NOT RUN rather than run on a short sample"). It is excluded
from the Holm family, which then covers H1, H3, H4 and H5. A supplementary, clearly
non-inferential observation about how often a cap would have bound is reported alongside —
labelled as an observation, carrying no pass or fail.

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

**Run once, 23 September 2026.** `cash_levels_test.py`, full log at
`validation_runs/_cash_levels_RESULT.log`. Plumbing was debugged first on a placebo pass
(levels shuffled across trades), which correctly failed everything including H0.

Population: 515 trades, of which **190 cash-only** and 325 F&O. Families: SWG-PB 321,
POS-BO 147, POS-ACCUM 44. IS/OOS split at 2025-07-15.

### Nothing passed.

| | Verdict | Number |
|---|---|---|
| **H0** validity gate | **FAIL** | ceiling vs call wall median **3.52 ATR** (n=195); POC vs max pain **3.97 ATR**. Bar was ≤ 1.0 ATR. |
| **H1** T1 beyond the ceiling | **THIN — cannot pass** | 169 beyond vs **21** below. Needed n ≥ 40 per cell. |
| **H2** capping T1 | **NOT RUN** (Amendment 3) | — |
| **H3** stop above the floor | **FAIL** | −17.6 pp, i.e. **opposite** to the prediction. p 0.977. |
| **H4** POC drags the target | **FAIL** | pooled **+9.9 pp**, also opposite. Both conditioning cells thin. p 0.933. |
| **H5** rising delivery | **FAIL** | **+0.014R** against a +0.15R bar. IS −0.013R, OOS +0.034R. p 0.461. |

### What the numbers actually say

**H0 is more interesting than a bare FAIL.** The substitutes beat the shuffled control
enormously — 3.52 ATR against 48.87, and 3.97 against 50.29 — so they are emphatically
*not* noise; they carry real information about where the options levels sit. They simply
are not in the same *place*. On a book whose stops are 1.5–4 × ATR, a level 3.5 ATR away
is a different level, not a proxy for the same one. **Related, not interchangeable**, and
the pre-registration asked for interchangeable.

**H1 could not be tested, and why is itself a finding.** Only 21 of 190 cash trades put T1
*below* the nearest volume shelf: the R-canon targets (swing 2R/4R, positional 3R/5R)
systematically reach past the first shelf above entry. There is no control group because
the system almost never does the other thing.

**H3 came back backwards, like P3's H1.** Trades whose stop sat ABOVE the defended shelf
stopped out on the initial stop **less** often (43.5% vs 61.1%), not more. The mechanism
was plausible and the data contradicts it. The likely mundane explanation is selection: a
stop above the nearest shelf is a *tight* stop, and tight stops here belong to swing
setups with different base rates — the test does not separate that, so the reverse is
**not** established either. What it does establish is that the live warning built on this
was pointing the wrong way; it has been demoted to a neutral line.

**H4's mechanism test never got off the ground** — the near cell held 24 and the far cell
4. A 120-day POC sits *below* entry on a breakout almost by construction, so "POC between
entry and T1" is rare. The pooled number runs opposite to the prediction anyway.

**H5 is a clean null.** Delivery % — the one genuinely new input, the closest thing a cash
market has to open interest — separates nothing: +0.014R across 178 trades, and the sign
flips between IS and OOS.

### The supplementary observation from H2 (not a test, no verdict)

A cap would have bound on **169 of 190** cash trades. Price reached the capped level in
**143 (85%)**, and the shipped plan's own T1 in **29 (17%)**. The shelf is reached five
times more often than the canon target.

That is suggestive and must not be over-read. This book is big-winner-carried — the
documented profile is a negative median with the mean rescued by a few large trades — so
booking at the first shelf would convert many small losses into small wins *and* cap the
few trades that pay for everything. Which effect dominates is precisely what H2 was
written to settle, and H2 did not run. **Do not act on this line.** It is the strongest
remaining candidate for a future, separately pre-registered replay.

### Consequences

1. The cash LEVEL CHECK **stays display-only**, which is all it ever was.
2. The H3-derived **warning is removed** — not because the reverse is proven, but because
   a ⚠ that the measurement contradicts is worse than no ⚠ at all.
3. Nothing gates, nothing sizes, no number changes.
4. Combined with P3: **nine pre-registered hypotheses across two families, zero
   survivors.** The correct conclusion is not that this estate cannot find edges — the
   selection edge measured in the validation runs is real — but that *plausible level
   rules do not survive contact with data*, at a rate now approaching certainty. Cheap to
   propose, cheap to test, and the testing is what stops them accumulating.
