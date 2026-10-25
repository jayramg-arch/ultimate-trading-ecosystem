# PRE-REGISTRATION — does Kronos forecast volatility (and rank stocks) better than what we use?

**Registered:** 25 Oct 2026 (IST), before any Kronos forecast was produced and before any outcome
was computed. **Owner:** Jay. **Script:** `kronos_test.py` (committed with this file).

## Question

Kronos (Shi et al., AAAI 2026; MIT licence; `github.com/shiyu-coder/Kronos`) is a model pretrained on
candlestick data from 40+ exchanges. Jay asked how it could be used. Its entry-timing use is ruled
out by our own record (the entry optimizer A–D and `PREREG_pa_selects` all failed: timing adds no
edge here). Two uses could matter:

1. **Volatility** — we size every position and set every stop off ATR(14), which only looks
   back. If Kronos forecasts the next 20 sessions' realised volatility better, sizing and stop
   distance improve on both systems.
2. **Ranking** — v2 ranks the Nifty 500 by Clenow's momentum score. Kronos's headline metric
   (RankIC) is a ranking measure.

## Leakage — why the window is fixed

The paper states its pre-training data **ends June 2024** and its test data starts July 2024, and
it lists NSE among its exchanges. Every forecast **origin** here is on or after **1 July 2024**, so
every predicted bar is outside the training data. The 400 input bars before an origin may predate
July 2024; the model may have seen inputs, never outcomes. No fine-tuning of any kind.

## Definitions (fixed now)

- **Panel:** `data/surv_panel.pkl` (NSE EQ/BE daily bars to 16 Oct 2026), point-in-time
  universe = `survivorship_backtest.membership` (top 500 by median turnover, reset every June and
  December). Using today's Nifty 500 list would hand the ranking test the survivors.
- **Origins:** every 10th session from the first session on/after 2024-07-01 to the last session
  that has 20 later sessions in the panel. **Horizon H = 20 sessions.**
- **Names per origin:** a random sample of **N = 120** point-in-time members that have ≥ 400 bars
  before the origin (seed = the origin's date ordinal). N may be lowered in the plumbing step only,
  for run time, and only before any outcome exists (recorded as an amendment).
- **Model:** Kronos-small (`NeoQuasar/Kronos-small`, tokenizer `NeoQuasar/Kronos-Tokenizer-base`),
  CPU, lookback **400** bars of open/high/low/close/volume/amount (amount = close × volume),
  `pred_len` 20, `T` 1.0, `top_p` 0.9. **K = 10 independent paths** per name, each one call with
  `sample_count=1` and seed `origin_index·1000 + k` (the library's own `sample_count` averages
  paths, which would erase the volatility being measured).
- **Kronos forecasts:** volatility `KV = sqrt(mean over paths of Σ ln(c_i/c_{i-1})²)` over the 20
  predicted closes, with c_0 = the origin close; return `KR = mean over paths of ln(c_20/c_0)`.
- **Baselines** (data to the origin close only): **ATR** = Wilder ATR(14)/close (what we use);
  **RV20** = trailing 20-session close-to-close realised volatility (descriptive);
  **Clenow** = `pro_systems_backtest` clenow90 score (v2's rank).
- **Outcomes:** realised volatility `RV = sqrt(Σ_{i=1..20} ln(C_{t+i}/C_{t+i-1})²)`; return
  `R = ln(C_{t+20}/C_t)`. A name without all 20 future closes is excluded from that origin and
  counted.
- **Uncertainty:** 95 % CI from 5,000 bootstrap resamples of origins in blocks of 2 consecutive
  origins (each outcome window overlaps its neighbour). Halves = chronological split of origins.

## Hypotheses

Primary metric for volatility is cross-sectional: per origin, Spearman ρ across names between
forecast and RV, then averaged over origins. It is scale-free, which is what sizing needs
(position size is risk ÷ (k × volatility); k is a house multiple).

- **H1 (Kronos ranks next-month volatility better than ATR):** mean ρ(KV,RV) − mean ρ(ATR,RV)
  ≥ **+0.03**, CI lower bound > 0, and the difference positive in **both** halves.
- **H2 (Kronos's volatility level is more accurate than ATR's):** each method is scaled by one
  constant (median of RV/forecast) fitted on the **first 25 %** of origins; on the remaining 75 %,
  mean QLIKE on variances (`RV²/F² − ln(RV²/F²) − 1`) for Kronos ≤ **0.95 ×** ATR's, with the CI
  of the ratio wholly below 1.
- **H3 (Kronos ranks returns usefully — may be THIN):** mean RankIC = Spearman(KR, R) across
  names per origin ≥ **+0.03** with CI lower bound > 0 in **both** halves, **and** within each
  origin's top quartile by Clenow score (v2's buy zone) mean RankIC ≥ +0.03 with CI lower > 0.
  Clenow's own RankIC is reported beside it (descriptive).

**Minimum sample:** ≥ 40 origins and ≥ 80 scored names per origin on average; otherwise the result
is **THIN** and nothing is concluded. The ranking test has fewer independent observations than
the count of origins suggests (overlapping outcome windows); its CI says so.

## Procedure

1. `python kronos_test.py --prepare` — builds origins, samples, model inputs and baselines into
   `data/kronos_test/inputs.pkl`. **No outcomes are computed.**
2. `python kronos_test.py --placebo` — RANDOM forecasts in place of Kronos through the same
   scoring; H1, H2 and H3 must all **FAIL**. Runs before any Kronos output exists.
3. `kronos_test.py --forecast --plumbing 3` (Kronos venv) — 3 origins × 10 names: timing and
   forecast sanity only, **no outcomes**. Sets N if run time requires (amendment).
4. `kronos_test.py --forecast` (Kronos venv) — all origins; cached per origin, resumable.
5. `python kronos_test.py --run` — scores everything **once**, writes
   `data/kronos_test/result.json`, and refuses to run again.

## Decision

- **H1 and H2 PASS** → Kronos volatility goes into a **forward shadow**: both ATR-based and
  Kronos-based sizes are logged on every v1 plan and v2 order for three months. No sizing or stop
  changes until that shadow is read. Nothing about entries changes in any case.
- **H1 or H2 FAIL** → recorded here; ATR(14) stays; Kronos is not used for sizing.
- **H3** is separate: PASS → a pre-registered forward test as a v2 tie-break/filter; FAIL or THIN →
  recorded, no use.
- A failed hypothesis is recorded as failed. It is not re-sliced, re-windowed or re-run on a
  different model size.

Descriptive only: RV20's ρ and QLIKE, Kronos-vs-RV20, per-half tables, the excluded-name count,
run time.

---
## Placebo (25 Oct 2026, before any Kronos output) — FAILED as required

56 origins (2024-07-01 → 2026-09-17), 119.2 scored names per origin on average. Random forecasts:
H1 diff −0.633 (ρ random −0.002 vs ATR **0.631**), H2 QLIKE ratio 4.98, H3 RankIC −0.001 —
all FAIL, so the scoring cannot manufacture a pass. What it shows about the bar: ATR(14) already
ranks next-month volatility at ρ ≈ 0.63 (trailing RV20: 0.54), so H1 needs Kronos near 0.66; ATR's
level accuracy (QLIKE 0.25) is far better than RV20's (2.51). Clenow's own RankIC over this window
is −0.01 (descriptive).

---
## Amendment 1 (25 Oct 2026, after plumbing, before any outcome or stored forecast)

Plumbing (3 origins × 10 names, outcomes NOT computed) found two things:

1. **The registered volatility measure was contaminated.** It included the step from the real origin
   close to the first DECODED bar, and that step is the tokenizer's reconstruction error, not
   volatility (360ONE: last close 973 → first predicted bar 921, or 791 with volume removed; ABCAPITAL
   240 → 207). **KV is now computed from the 19 returns inside each predicted path, × √(20/19).**
   KR (the return forecast) is unchanged.
   Also observed, and left as is because it is the model's design: Kronos z-scores price LEVELS over
   the 400-bar input, so names near the top of their window get forecasts that revert toward the
   window mean (median plumbing KR −7 % to −16 %). The ranking test measures this behaviour as built.
2. **Run time.** Batching gives no speed-up on CPU (≈ 5.7 s per name-path). The registered size
   (56 × 120 × 10) is ≈ 106 h. **N 120 → 60 names per origin, K 10 → 5 paths,** and the minimum average
   names per origin 80 → 50 to match. Re-prepared at N = 60 (new seeded sample, 59.8 scored names per
   origin) and the placebo re-run: FAILED as required (ATR ρ 0.632; random −0.629 below it).
   Two workers (`--shard 0/2`, `1/2`), below-normal priority, paused 09:10–15:35 IST on weekdays.

Hypotheses, thresholds, window and model are unchanged.
