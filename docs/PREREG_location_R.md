# Pre-registration — does LOCATION buy better risk geometry?

**Written 24 September 2026, BEFORE any stop was placed or any path simulated.** The
analysis runs **once**.

## Why

The panel-row audit (`PREREG_panel_row_audit.md`, 24 Sep) found that no location row ranks
60-day forward returns. That audit also named what it could NOT see: a location row's real
job on the S4 panel is **risk geometry** — a stop placed at a level the market has defended,
so that the same move pays more R, or the position is shaken out less often. A return-
ranking test is blind to that. This is the test of the claim the location rows actually
make. If they fail it too, they have no measured job left and stay on the panel as display.

## The sample — NOT Jay's trades

Identical to the panel-row audit, at Jay's instruction: current Nifty 500 constituents,
daily bars (`data_provider`, 5y), sample dates every 10th trading day from the first date
with ≥ 420 bars to the last with 60 forward bars, every quantity point-in-time. **Only
Stage-2 name-dates** (the 2×2 weekly stage == 2), because that is where the panel is used.
No journal row, taken trade, reviewed alert or backtest trade is used.

## The rows and their stops (defined exactly)

For each row, a name-date is **at location** when the production engine says so, and the
**structural stop** is placed beneath the level that engine returned:

| row | at location when | structural stop |
|---|---|---|
| **L1** zone_d | `zone_engine.zone_support(df,"D").at_support` | zone `distal` − 0.10 × ATR14 |
| **L2** zone_w | the same on confirmed weekly bars | weekly zone `distal` − 0.10 × ATR14 (daily ATR) |
| **L3** near_sr | `zone_engine.sr_support(df,"D").near_sr` | `level` − 0.25 × ATR14 |
| **L4** near_avwap | `zone_engine.avwap_support(df).near_avwap` | `nearest` AVWAP − 0.25 × ATR14 |
| **L5** at_vp | `zone_engine.vp_support(df).at_vp_support` | the near one of VAL/POC that is ≤ price − 0.25 × ATR14 |

Zones get a smaller buffer than lines because a zone's distal already sits beyond the
defended area; a line has no width.

**Valid stop:** distance from the entry (close at t) between **0.25 and 4.0 × ATR14**.
Outside that range it is not a usable stop (on top of price, or wider than the system's own
positional stop); such name-dates are counted and excluded, never forced.

## The trade (identical for every stop — only the stop moves)

Enter at the close at t. Exit at the stop the first time a later bar's low touches it (fill
at the stop), else at the close 60 bars later. No targets, no trail, no breakeven — the exit
study showed those move results by hundredths of an R, and they would blur the one thing
being measured. Cost 0.10% per leg (2 legs). **R** = net return ÷ initial risk %.

## Hypotheses

**H1 — shallower adverse excursion.** In Stage-2 names, entries at a location suffer a
smaller 20-bar maximum adverse excursion (MAE, in ATR14, from the entry close to the lowest
low) than entries on the same date that are not at that location.
*Statistic:* per date, median MAE (at location) − median MAE (not at location); the mean over
dates. *Pass:* ≤ **−0.15 ATR** in IS **and** OOS.

**H2 — placement beats arbitrary placement at the same distance.** For at-location
name-dates, the structural stop earns more R than a stop at an ARBITRARY distance drawn from
the same distribution.
*Baseline:* each trade is re-run with its stop distance (in ATR) replaced by the distance of
another at-location trade of the same row in the same window (a random permutation), averaged
over 20 permutations. This keeps the distance distribution exactly and removes only the
PLACEMENT — which is the claim.
*Statistic:* mean paired R(structural) − R(permuted). *Pass:* ≥ **+0.10R** mean and median
difference not worse than −0.10R, in IS **and** OOS.

Directional: the doctrine predicts both.

## Tests

- **IS/OOS:** the audit's split — dates in order, first 60% IS, last 40% OOS, IS dates within
  60 trading days of the first OOS date purged.
- **Uncertainty:** block bootstrap over dates, blocks of 6 sample dates (60 trading days),
  5,000 resamples, one-sided; a (hypothesis, row) p is the larger of IS and OOS.
- **Holm–Bonferroni** across all 10 (hypothesis, row) pairs at family-wise α = 0.10.
- **n ≥ 100** at-location trades in each of IS and OOS, else THIN and cannot pass.
- **Verdicts:** PASS (size bar + Holm) · suggestive (one of the two) · FAIL · THIN.

## Power — stated before the run, this time

The panel audit omitted a power statement and had to compute it afterwards. Here the
**placebo pass prints the minimum detectable effect** (2.8 × the bootstrap SE, per cell)
before the real run. Any cell whose MDE exceeds its pass bar is reported as
**UNDERPOWERED**, not as a failure, whatever its point estimate.

## Placebo

- H1: location labels permuted across names within each date.
- H2: the "structural" distances themselves replaced by a within-window permutation, so both
  arms are arbitrary placements.

Every contrast is noise by construction; any pass is a bug. The placebo and a coverage print
are the only runs before the real one.

## What a result can and cannot mean

- A PASS says the level is a better place for the stop than an arbitrary spot at the same
  distance — the precise claim the S4 Plan row makes when it anchors SL to a zone distal.
- A FAIL on H2 with a PASS on H1 would mean price does respect the level, but not enough to
  pay for placing the stop there — show the level, size by ATR.
- Daily bars only; S4 places intraday stops off the same levels. Provisional for 75/125m.

## Stopping rule

Runs **once**. No re-slice, no moved bar, no changed buffer. Results go in this file.

## Amendment 1 — 24 Sep 2026, BEFORE the build completed or any statistic was computed

Jay: *"target primarily positional trades, with an option for swing trades. I do not day
trade."* The design above (60-bar hold, 0.25–4.0 ATR stops) is **swing scale**, so the
headline cell measured a trade he mostly does not take. The build was stopped before it
wrote any data. The test now has two styles, run together in the single run:

| | **POSITIONAL — primary** | SWING — secondary (option) |
|---|---|---|
| hold (exit if the stop is not hit) | **120 bars** (~6 months) | 60 bars (as registered) |
| H1 MAE window | **40 bars** | 20 bars |
| valid structural stop | **1.0 – 6.0 × ATR14** (the system's positional stop is ~3.85×) | 0.25 – 4.0 × ATR14 |
| sample dates | those with 120 forward bars | those with 60 forward bars |
| IS/OOS purge | IS dates within **120** trading days of the first OOS date | 60 (as registered) |
| Holm family | its own 10 cells, α = 0.10 — **the verdicts** | its own 10 cells, α = 0.10 — reported |

Everything else is unchanged: rows, levels, buffers, pass bars (H1 ≤ −0.15 ATR; H2 ≥ +0.10R
with median not worse than −0.10R), n ≥ 100, the date-block bootstrap, the placebo and MDE
print.

**Expected consequence, stated in advance:** the line levels (S/R, AVWAP, VP) are "near"
only within 1.5% of price, so their stops mostly sit under 1 ATR, which is below the positional
floor. Those positional cells may well come back **THIN**. If so, that is a finding, not a
failure of the test: it would mean those rows are **swing-scale instruments**, and a positional
stop has to come from zone structure (L1/L2).

## Result

Run once, 24 Sep 2026 (`location_r_test.py --run`, log
`validation_runs/_location_r_real_run.log`). Protocol held: coverage (20,932 Stage-2
name-dates, 449 symbols) → placebo (nothing passed; MDEs printed) → the single real run.

**No cell passes, in either style.** Most are UNDERPOWERED by the registered rule (MDE
above the bar); the positional line-level H2 cells are THIN, as predicted in Amendment 1.

**Coverage confirmed the prediction.** The line levels put a valid POSITIONAL stop only
1–2% of the time (median stop 0.5 ATR below entry). Zones do: 65% (daily, median 1.65 ATR)
and 80% (weekly, 2.97 ATR). **S/R, AVWAP and VP are swing-scale instruments; a positional
stop can only come from zone structure.**

**POSITIONAL (the verdicts)**

| row | H1 MAE diff IS / OOS (ATR) | H2 R struct − perm IS / OOS | stop hit | verdict |
|---|---|---|---|---|
| L1 zone_d | −0.118 / −0.008 | +0.013 / −0.048 | 70 / 85% | H1 FAIL · H2 UNDERPOWERED |
| L2 zone_w | +0.120 / +0.017 | +0.083 / −0.086 | 57 / 75% | UNDERPOWERED |
| L3 near_sr | +0.164 / +0.116 | THIN (52 / 34) | | |
| L4 near_avwap | +0.116 / +0.107 | THIN (32 / 20) | | |
| L5 at_vp | +0.060 / +0.169 | THIN (15 / 16) | | |

**SWING (reported)** — H1 for S/R, AVWAP and VP: +0.09/+0.10, +0.08/+0.14, +0.02/+0.11 ATR.
H2 near zero everywhere (−0.09 to +0.24R, no consistent sign). Level stops at ~0.5 ATR hit
88–93% of the time within 60 bars.

**What the point estimates say — none is significant, so these are directions, not findings:**

1. **Placement buys nothing measurable.** In every cell with data, the structural stop and
   an arbitrary stop at the same distance earn almost the same R (e.g. positional daily
   zone 1.87R vs 1.86R IS, −0.09 vs −0.04 OOS). Nothing here supports the claim that a stop
   anchored to a level beats one at the same distance placed anywhere.
2. **Entries AT a line level draw DEEPER, not shallower, adverse moves** — positive MAE
   difference for S/R, AVWAP and VP in all four windows (positional and swing, IS and OOS).
   That is the opposite of the doctrine that a level cushions the entry. Not significant;
   noted as the direction to watch.
3. **Level stops mostly get hit.** A stop 0.5 ATR under a line is taken out ~90% of the time
   within 60 bars; a positional zone stop at ~1.7 ATR, 70–85% within 120 bars. Consistent
   with every stop study here: tight stops on a positional hold give the edge back.

**Stopping rule honoured.** Marker `validation_runs/_location_r_REAL_RUN_DONE.json`.
