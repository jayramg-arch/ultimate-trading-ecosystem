# PREREG · Relative volume as a BAND, not a floor

**Written 8 Sep 2026, BEFORE any test of this hypothesis is run.**
Arose from `PREREG_wyckoff_positive_filter.md` §5 — the control variable, not the
hypothesis, was the interesting thing.

---

## 0. Provenance — this is post-hoc, and that is why it needs registering

The Wyckoff positive-filter test failed (edge +0.20pp, CI straddles zero, sign reverses
out of sample). Its §5 fallback predicted DISTRIBUTION would prove redundant with
relative volume. **That was also wrong** — point-biserial correlation +0.052, essentially
independent.

But the control variable behaved oddly. On the 464-trade bull run, split into RV terciles:

| Rel_Vol tercile | n | mean matched α | win% |
|---|---:|---:|---:|
| low | 156 | −0.01% | 28.2 |
| **mid** | **153** | **+3.48%** | **37.9** |
| high | 155 | −1.02% | 30.3 |

**Non-monotonic.** Mid beats both tails by 3.5–4.5pp.

I found this by looking *after* a hypothesis failed. That is textbook post-hoc, and this
desk's largest documented statistical liability is uncorrected multiple testing. So it is
registered before it is tested, and the band is fixed from INDEPENDENT data (§2).

## 1. Independent corroboration — why this is worth a test rather than a shrug

The 13-Aug-2026 pullback study, a different sample (74,267 at-value bars, 250 names,
3 years) answering a different question, found the same shape:

| RV bucket | 0.0–0.5 | 0.5–0.8 | 0.8–1.0 | 1.0–1.5 | 1.5+ |
|---|---:|---:|---:|---:|---:|
| matched α | +0.84 | +1.05 | +1.15 | **+1.30** | +1.00 |

Rising, peaking at 1.0–1.5, then falling. Two independent samples, same inverted U.

The two also fit together rather than merely agreeing. 13-Aug concluded the floor
*"discards a mildly positive population"* — that is about the LEFT tail. Today's cut says
the RIGHT tail is worse than assumed. Together they describe a band.

**Mechanism, stated before the test:** below the band nobody is there and the move has no
fuel; above it you are buying a climax — the high-volume bar IS the exhaustion. Healthy
participation without a blow-off sits between.

## 2. The band is FIXED FROM PRIOR DATA, not fitted here

**Primary band: `0.8 <= RV <= 1.5`.** Taken directly from the 13-Aug bucket peak
(0.8–1.0 = +1.15, 1.0–1.5 = +1.30), which is an independent sample. It is NOT fitted to
the 464-trade run this test scores against.

This is the single most important design choice in the document. A band chosen by
maximising alpha on the test set is curve-fitting with extra steps, and would reproduce
exactly the failure that made the Wyckoff +5.60% cell meaningless.

## 3. Primary hypothesis

**H1** — On qualified bull picks, gating `0.8 <= RV <= 1.5` produces higher mean
matched-horizon alpha than the current one-sided floor `RV >= 1.0`.

Comparison arms, all on the same trades:
- **A · no gate** (baseline, every pick)
- **B · floor** `RV >= 1.0` — what S4 does today
- **C · band** `0.8 <= RV <= 1.5` — the proposal

## 4. Adoption rule — stated now, not renegotiated after

Adopt the band ONLY if ALL of:

- **A · n >= 100** in the banded cohort.
- **B · band beats floor by >= +1.0pp** on mean matched-horizon alpha.
- **C · symbol-block bootstrap CI95 on (band − floor) EXCLUDES zero.** Trade-level
  resampling is not acceptable.
- **D · the sign holds in BOTH halves of a chronological split.** This is the criterion
  that killed the Wyckoff positive filter (+1.46 IS, −1.53 OOS) and it is the one that
  matters most.
- **E · retention >= 40%.** A band cuts BOTH tails, so it necessarily rejects more than a
  floor. See §5 — this is the criterion most likely to bite.

**Falsifier:** if the band does not beat the floor by 1.0pp, or the CI straddles zero, or
either half reverses — the one-sided floor stands and the inverted U is an artifact of
two correlated samples.

## 5. The trap this test must not fall into

**A gate that improves mean alpha by rejecting trades has not necessarily improved the
book.** A band cuts both tails, so it will always show a better mean than a floor on the
survivors while taking fewer trades. Mean alpha alone would make it look good by
construction.

So the test reports **retention alongside every mean**, and the honest comparison is
per-opportunity, not per-trade. If the band lifts mean alpha 1pp while halving the number
of trades, that is a smaller book, not a better one — and the correct read is "same
expectancy, less deployment", which is a worse outcome for a desk that already struggles
to find setups in thin tapes.

## 6. Scope limit — stated before, because it will be tempting to ignore after

This is measured on **DAILY** bars from the validation run. S4 applies `rv_floor` on
**75m and 125m** charts. Those are not the same distribution, and RV on intraday carries a
measured time-of-day bias — the gate passes **48% at 10:30 and ~18% midday** (measured
18-Aug, 14,466 bar-observations), because RV divides by a baseline mixing every bar of the
session.

**A daily-bar result therefore does NOT license changing the intraday gate.** If H1
passes, the next step is to re-measure the band on intraday bars with a per-slot RV
baseline — not to edit `rv_floor` in S4.

## 7. If it fails — the v2 path, decided in advance

Per the standing method change (8-Sep): a negative result is not a finding until it comes
with a v2 or an explicit statement that none exists.

If the band fails, the next mechanism question is whether the mid-bucket advantage is
really about volume at all, or about **what kind of setup lands in the middle bucket**.
POS-ACCUM wants volume dry-up; POS-BO wants expansion. If mid-RV is simply where the
accumulation names sit, then the inverted U is a catalyst-mix artifact and the correct
control is per-family RV, not a global band. That is testable on the same data and would
be a more useful finding than "the band did not work".

---

# ADDENDUM · the intraday test (registered 8 Sep 2026, before it was run)

## A1. What the daily test returned, and the one criterion that was wrong

A, B, C and D all passed — including D, the chronological split that killed the Wyckoff
filter, and which here STRENGTHENED out of sample (+2.58pp IS, +5.07pp OOS). The band
location was fixed from the 13-Aug sample, so its position was never fitted to the trades
it scored against.

**E failed: retention 23.5% against a 40% floor. The verdict stands as DO NOT ADOPT and
is not renegotiated.**

But E was **mis-specified**, and that is recorded here rather than quietly fixed. E existed
as a proxy for one worry: *do not improve the mean by shrinking the book*. The direct
measure of that worry was also printed:

| arm | mean | retention | deployment (mean x retention) |
|---|---:|---:|---:|
| no gate | +0.80% | 100% | +0.80% |
| floor RV>=1.0 | +1.02% | 40.1% | **+0.41%** |
| band 0.8-1.5 | +4.63% | 23.5% | **+1.09%** |

The band wins on the metric E was standing in for. A raw retention floor is the wrong
instrument for that concern, because it cannot distinguish "rejected trades that were
worthless" from "rejected trades that were fine".

**Correction, made BEFORE the intraday data is touched:** criterion E is replaced by

  **E' · deployment (mean x retention) must beat BOTH the floor arm and the no-gate arm.**

This is stricter than E in the way that matters — it fails any gate that merely prunes to
a prettier mean — and it cannot be satisfied by shrinking the book.

## A2. Why the intraday test is a separate question, not a formality

The daily result does not license changing `rv_floor`, for two reasons already measured:

1. **S4 applies the gate on 75m/125m bars, not daily.** Different distribution.
2. **Intraday RV is time-of-day biased.** `chart_rv = volume / sma(volume, 50)[1]` uses a
   rolling mean that MIXES every bar of the session, and NSE intraday volume is U-shaped.
   Measured 18-Aug over 14,466 bar-observations: the V gate passes **48.2% at 10:30** and
   **~18% midday**, a 2.8x swing from clock position alone.

So a band fitted to daily RV may not even be measuring the same quantity intraday.

## A3. Hypotheses

**H2** — the inverted U survives on 75m bars: forward alpha is higher for mid-RV bars than
for either tail.

**H3** — a **per-slot** RV baseline (each bar divided by the mean volume of the SAME
bar-of-day over prior sessions) separates outcomes better than the current session-mixing
baseline. If the time-of-day bias is noise, debiasing should sharpen the effect; if the
bias is itself informative, it should not.

## A4. Design

- RV measured on 75m bars over the ~90 days Dhan serves intraday.
- **Outcome measured on DAILY bars** — forward return over 20 trading days from the
  intraday bar's date, minus the benchmark over the same window. Intraday history is
  capped at 90 days; using daily for the outcome avoids spending the sample on the
  horizon.
- Two RV definitions, same bars: **current** (`sma(volume,50)[1]`) and **per-slot**.
- Bars are labelled by their OPEN by `resample_intraday`; the gate fires at the CLOSE.
  Getting this backwards already inverted one finding on 18-Aug.

## A5. The overlap problem, stated up front

Roughly 5.5 bars per session share almost the same 20-day forward window, so bar-level
counts massively overstate independent evidence. Significance is symbol-block bootstrapped
and **bar counts are reported as bar counts, never as sample size**. Any comparison of
"n=40,000 bars" to the daily study's "n=464 trades" would be meaningless.

## A6. Adoption rule for the intraday test

Adopt an intraday band ONLY if ALL of: n_symbols >= 40; band beats floor by >= +1.0pp;
symbol-block CI95 excludes zero; the sign holds in both chronological halves; and **E'**
(deployment beats both floor and no-gate).

**Falsifier:** if the inverted U does not appear on 75m bars under either RV definition,
the daily finding does not transfer, `rv_floor` stays exactly as it is, and the daily band
is filed as a daily-only phenomenon — interesting for the validation harness, irrelevant
to the live gate.
