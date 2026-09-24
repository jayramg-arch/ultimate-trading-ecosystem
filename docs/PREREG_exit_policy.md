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

## Amendment 1 — 24 Sep 2026, BEFORE any config was run

Written after reading `replay._simulate_one_trade` and the recorded trade set, and before a
single config was simulated. Nothing below was informed by a result.

### 1a. E0 is corrected to what the recorded run actually did

The E0 row above was written from memory and is wrong in two places. The control must
reproduce the 515 recorded trades, so it is defined by the code that produced them
(`replay.py`, run `20260819_112959`), not by the canon as remembered:

| | recorded behaviour |
|---|---|
| targets | POS-* **3R / 5R**, SWG-* 2R / 4R (read from the recorded `T1_price` / `T2_price`) |
| partials | POS **25/25**, SWG-BO/PB **33/33**, SWG-GAP/REV 50/50 (`bull_screener.partial_qty_for`) |
| stop | recorded `SL_price`, intraday trigger (`bar_low <=`), fills at the stop |
| after T1 | stop to breakeven |
| trail | Chandelier = highest close since entry − **4.5** × ATR14 (simple mean), **on every family** |
| hold | no time stop (`NO_TIME_STOP`, 400-bar data ceiling) |
| cost | 0.10% per leg, 2 legs + 1 per partial |

**Finding recorded in passing, not tested here:** the backtest trails swing trades at 4.5×,
while the live system (`risk_common.trail_mult_for`) trails them at 1.5× on a 14-bar window.
The swing results in every validation run since July were produced under a positional
trail. That is a harness–live mismatch in its own right and is filed separately.

**Validity gate (unchanged in spirit):** E0 must reproduce the recorded `Return_pct` with
median |error| ≤ 0.25pp and ≥ 95% of trades within 1.0pp. If it fails, the study is void and
nothing else is read.

### 1b. Rungs specified exactly

- **E1 pure trail** — no partials, no breakeven move (breakeven is tied to T1, and there is
  no T1). Same stop, same 4.5× trail.
- **E2 ladder** — `pyramid_logic` as written: at the first bar whose high reaches entry + 2R,
  sell ⅓ at the 2R price and raise the stop to entry + 0.5R; at entry + 3R, sell ½ of what
  remains at the 3R price. The rest rides the 4.5× trail.
- **E3 trail width** — E1 with multiples **3.375 / 4.5 / 5.625 / 6.75** (0.75× / 1× /
  1.25× / 1.5× of 4.5).
- **E4 extension only** — at the first CLOSE ≥ 4.0 × ATR14 above the daily EMA20, sell ½ at
  that close. The rest rides the 4.5× trail. No R-multiple targets, no breakeven move.

### 1c. NEW — E5, Weinstein's own exit (H5)

*Why it was added.* Jay's question on 24 Sep: the frameworks are sound, so why doesn't the
system add up? The reading proposed was that selection comes from Weinstein (a 6–8-month
positional method) while the exit — ATR stop, Chandelier, R-multiple partials — comes from
neither Weinstein nor Minervini. Each author's exit is built for his own entry. If that
mismatch is the leak, running Weinstein's exit on Weinstein's selection should beat E0. It
is a test of how the frameworks were put together, not of any one of them.

- **E5** — the recorded initial stop is kept (entries and risk stay frozen); **no partials,
  no Chandelier, no breakeven move.** Exit the whole position at the **next session's open**
  after the first COMPLETED week (W-FRI) whose close is below the **30-week simple moving
  average of weekly closes**. The forming week is never used. The initial stop still fills
  intraday at the stop price, exactly as in E0.

| # | Hypothesis | Comparison | Pass bar |
|---|---|---|---|
| **H5** | Weinstein's own exit beats the mixed exit on Weinstein's own selection | E5 − E0 | ≥ +0.10R mean, median not worse by >0.10R, IS *and* OOS |

H5 is tested on **POS-BO and POS-ACCUM only**. It is a positional rule; applying it to a
swing book with a median 4-day hold would be testing something neither Weinstein nor this
system intends. The SWG-PB cell is **reported, not tested**.

### 1d. Mechanics that were ambiguous

- **R** = realized return % (net of cost) ÷ initial risk % (`(entry − SL) / entry`).
- **IS/OOS** — the OOS gate's rule exactly: anchors sorted, first 60% IS (12 of 20), last 40%
  OOS (8), and IS anchors within **45 calendar days** of the first OOS anchor purged.
- **Per-config benchmark** — Nifty 500 close-to-close from the anchor over **that config's
  own** `days_held`. Matched alpha is reported alongside R; the pass bars are on R.
- **p-value** — one-sided, from 5,000 symbol-block bootstrap resamples of the paired mean
  difference (config − reference) ≤ 0. For a (hypothesis, family) pair, p = the larger of
  the IS and OOS p-values.
- **Holm–Bonferroni** runs across every tested (hypothesis, family) pair that is not THIN,
  H1–H5 together, at family-wise α = 0.10. For H4 the tested contrast is best-of-grid minus
  current.
- **THIN** — fewer than 40 trades in the IS **or** the OOS cell. POS-ACCUM has 44 trades in
  total, so it will be THIN, and it is reported as such rather than pooled into POS-BO.
- **Placebo pass first** — the code is debugged on each symbol's own daily returns, demeaned
  and shuffled (volatility kept, drift and serial structure removed). On a driftless series
  every exit rule has the same expected return before cost, so any config showing a real
  edge there is a bug. The placebo and the E0 validity check are the ONLY runs made before
  the real one, and neither prints a config comparison on real prices.

## Result

*(Left empty deliberately. To be filled in ONCE, by the run.)*

- H1 —
- H2 —
- H3 —
- H4 —
- H5 —
