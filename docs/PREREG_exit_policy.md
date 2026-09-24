# Pre-registration — trim, or let it run?

**Written 24 September 2026, BEFORE the configs were run.** Hypotheses, parameters, pass
bars, the correction and the stopping rule are fixed here. The analysis runs **once**.

*Why now.* Jay is at 22 holdings and capital-capped, so the daily decision has shifted from
"what do I buy" to "what do I add to, and what do I harvest". That makes `pyramid_logic`
the primary surface — and it is imported by twelve files, none of which is a test. Every
threshold in the ladder was asserted, never measured: ⅓ at 2R, ½ at 3R, over-extension at
4.0×ATR, time stops at 60/180 days.

---

## Read this before reading the hypotheses: what this test CAN see

The nine previously pre-registered hypotheses (P3, cash levels) all failed, and Jay
reasonably asked why frameworks from serious practitioners keep coming back empty. Part of
the answer is that **those tests were underpowered and this one is not**, so the same null
would mean something different here.

Those tests compared different SUBGROUPS of trades — cells of 24, of 21, of 4. This one
compares exit policies **on the same trades**, so the difference is paired and most of the
noise cancels.

Measured on the 515-trade set (mean R −0.273, median −1.011, sd 1.29, 307 symbols), the
smallest shift detectable at 80% power, one-sided α = 0.10:

| correlation between configs | n = 515 trades | n = 307 symbols |
|---|---|---|
| 0.9 | 0.063 R | 0.082 R |
| 0.7 | 0.110 R | 0.142 R |
| 0.5 | 0.142 R | 0.183 R |

**So a pass bar of 0.10R is honest here** — inside what the data can resolve even on the
conservative by-symbol count. A null will mean "no effect of a size worth trading", not
"we could not see it". That distinction is the whole point of stating this first.

## What is and is not being tested

**Entries are frozen.** Every config replays the SAME 515 entries, on the same bars, with
the same stop. Only the exit ladder changes. This test cannot and does not say anything
about selection.

## The configs

| | |
|---|---|
| **E0 control** | What ships today: 25% at T1, 25% at T2, 50% on the catalyst-aware Chandelier trail. Canon targets — POS 2R/4R, SWG 2R/4R. |
| **E1 pure trail** | No partials at all. 100% rides the same Chandelier. The honest null for "does harvesting help?" |
| **E2 ladder** | `pyramid_logic`'s rungs as written: ⅓ at 2R, ½ of the remainder at 3R, rest trails. |
| **E3 trail width** | E1 with the Chandelier multiple at 0.75×, 1.25× and 1.5× of current. The trail ends 88% of positional trades and has never been A/B'd. |
| **E4 extension only** | No R-multiple trims. Book half when price is ≥ 4.0×ATR above the 20-EMA, rest trails. Isolates the one trim rung that is not an R-multiple. |

## Hypotheses

| # | Hypothesis | Comparison | Pass bar |
|---|---|---|---|
| **H1** | Harvesting beats letting it all run | E0 − E1 | **≥ +0.10R mean**, median not worse by >0.10R, IS *and* OOS |
| **H2** | The ladder's rungs beat the shipped 25/25 | E2 − E0 | same |
| **H3** | The over-extension rung earns its place | E4 − E1 | same |
| **H4** | The current trail width is not dominated | E3 variants vs E1 | current must be within 0.10R of the best, and the surface must be a **plateau** — a winner at the edge of the grid FAILS, as it did in the July SL sweep |

Directional, because the doctrine predicts each one.

## Measurement rules

Unchanged from the two prior pre-registrations, plus one correction:

1. **R, never per-trade %.** Size is risk / (k × ATR); a % metric structurally rewards wide
   stops and has already inverted a conclusion here once.
2. **PER-CONFIG BENCHMARK.** `exit_policy_study.py` (28-Jul) charged every config E0's hold
   length, so alternatives holding 6 days were billed a 16-day benchmark — the 26-Jul
   horizon bug, reintroduced, and biased **in favour of** the conclusion then reported.
   Each config's benchmark is recomputed from **its own** `days_held`. This is why that
   study's magnitudes are not being reused.
3. **Per family**, never pooled. POS-BO · POS-ACCUM · SWG-PB. Pooling has produced a false
   conclusion here three times.
4. **IS/OOS** on the same chronological split the OOS gate uses.
5. **Bootstrap by symbol**, not by trade.
6. **n ≥ 40 per cell**, else THIN and cannot pass.
7. **Holm–Bonferroni at family-wise α = 0.10** across H1–H4, in addition to the size bar.
   Both required; clearing one alone is "suggestive, not passing".

## The one thing that would make a pass suspect

This book is **big-winner-carried**: negative median, mean rescued by a few large trades,
and only 8.4% of positional trades ever reach 3R. Any trim rung amputates that tail by
construction. So a config that wins on MEAN while making the **median** worse is harvesting
noise and paying for it in the tail — which is why the median clause is in every pass bar
rather than being a footnote.

Equally, the trail currently ends 88% of positional trades at a mean of −0.01R. If E1 wins,
the reading is not "trailing is good" but "our trail gives back everything, and harvesting
is the only thing that books a gain". Those are different conclusions with different fixes.

## Stopping rule

Runs **once**. No re-slicing, no moving a bar, no dropping a family that came out wrong. A
failed hypothesis is recorded as failed **in this file**, and `pyramid_logic` keeps the
thresholds it has — with the honest note that they are asserted, not measured.

## Result

*(Left empty deliberately. To be filled in ONCE, by the run.)*

- H1 —
- H2 —
- H3 —
- H4 —
