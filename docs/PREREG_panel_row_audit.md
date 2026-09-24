# Pre-registration — which panel rows deserve a vote?

**Written 24 September 2026, BEFORE any row was computed on the sample.** Rows, their
definitions, the population, the outcome, the pass bars, the verdict rules and the stopping
rule are fixed here. The analysis runs **once**.

## Why

Jay, 24 Sep: *"All the fields/rows we introduced in the S4 panel were meant to make sure we
have enough confluence/confidence in taking or exiting trades. The intent was not to
complicate it, it was meant to make it bullet-proof."*

Confluence only buys confidence when the things it counts are **independent** and each one
**separates outcomes**. Correlated rows agreeing with each other look like corroboration
but are close to one fact counted several times. This audit asks three things of every row
that can be rebuilt from price history:

1. **Does it carry information?** — does it rank forward outcomes at all?
2. **Is it new information?** — once the other informative rows are known, does it still add?
3. **Does it point the way the panel reads it?** — or is it backwards?

The answer is a short list of rows that earn a vote. Everything else stays on the panel as
information, not as a confluence point.

## The sample — NOT Jay's trades

At Jay's instruction, **no journal row, no taken trade, no reviewed alert and no
system-backtest trade is used.** The sample is the market itself:

- **Universe:** the current Nifty 500 constituents. *Survivorship is disclosed, not fixed:*
  names that left the index are missing. That biases LEVELS; this audit reads
  cross-sectional RANKS on each date, which it biases far less.
- **Data:** daily bars from `data_provider` (period 5y), plus `^CRSLDX` (Nifty 500).
- **Sample dates:** every 10th trading day, from the first date with ≥ 420 bars of history
  (enough for a 52-week high and a weekly 30-SMA with its slope) to the last date with 60
  forward bars.
- **Point-in-time:** every row at date t is computed on bars up to and including t only.

## The outcome

- **Primary Y60:** the 60-trading-day forward return from the close at t, minus the
  Nifty 500's return over the same 60 days. A pure information test — no stops, no targets,
  no exit policy (the exit study just showed the exit moves results by hundredths of an R).
- **Secondary Y20:** the same over 20 days. Reported, not used for verdicts.
- Missing values are excluded, never zeroed.

## The rows (defined exactly)

Rows are rebuilt from the Python engines the board and the reviewer already use, so this
tests the definitions in production, not new ones.

| id | panel row | definition | panel reads as favourable |
|---|---|---|---|
| **C1** stage2 | Structure basis | weekly 2×2 (`bull_screener.compute_weekly_stage_and_wks`, confirmed weeks) == 2 | 1 |
| **C2** above200 | Structure basis | close > SMA200 | 1 |
| **C3** off52 | Structure basis | close / 52-week high − 1 | higher |
| **C4** minervini | Minervini template | count of 7 price legs: close>SMA150>SMA200 · SMA200 up over 20d · SMA50>SMA150 & SMA200 · close>SMA50 · ≥30% above 52w low · within 25% of 52w high · close>SMA200 (the RS leg is C5) | higher |
| **C5** rs_ratio | RS row | weekly JdK RS-Ratio vs N500, `rrg_engine.calculate_jdk_rrg` (strike_cal) | higher |
| **C6** rs_mom | RRG row | weekly JdK RS-Momentum, same call | higher |
| **C7** rsi14 | Signal·Quality·RSI | daily RSI(14) | *not declared* |
| **C8** adx_di | Momentum & value | ADX(14) × sign(DI+ − DI−) | higher |
| **L1** zone_d | Support Zone | `zone_engine.zone_support(df, "D").at_support` | 1 |
| **L2** zone_w | Zones (MTF) | the same on confirmed weekly bars | 1 |
| **L3** near_sr | S/R (nearest) | `zone_engine.sr_support(df, "D").near_sr` | 1 |
| **L4** near_avwap | AVWAP | `zone_engine.avwap_support(df).near_avwap` | 1 |
| **L5** at_vp | Volume Profile | `zone_engine.vp_support(df).at_vp_support` | 1 |
| **L6** ema_ext | EMA20 row | (close − EMA20) / ATR14 | **lower** |
| **L7** room | Room for Trade | (`overhead_room({"D": df}).obstacle` − close) / ATR14; "clear" (no obstacle) takes the 95th percentile of observed room on that date | higher |
| **X1** pa_sigma | PA battery | sum of weights of fired patterns, `pa_patterns.detect_bull_patterns(df)` (daily) | higher |
| **X2** bar_ok | Bar (B) | close ≥ open, or close in the upper half of the bar's range | 1 |
| **X3** rv | Volume (V) | volume / SMA50 of the prior 50 volumes (S4 `chart_rv`) | higher |
| **X4** arrival | Arrival | (highest high of the last 20 bars − close) / ATR14 ÷ bars since that high | higher (FAST) |

**Out of scope, and why** — stated so the audit's silence is not read as a verdict:

- **BFF / RFF / Piotroski** — no point-in-time fundamentals history exists here; a today's
  snapshot applied to 2023 is look-ahead.
- **Futures OI / Options OI** — tested separately (derivatives P3, F&O subset only).
- **WCL (Wyckoff)** — tested and rejected 28-Jul; not re-litigated.
- **Intraday row, Arrival Δ, intraday PA** — no multi-year intraday history (Dhan serves ~90
  days). S4 reads X1–X3 on 75/125-minute bars; this audit tests their **daily** analogue,
  a proxy, and says so.
- **Pattern / Shape** — the geometry engine is withheld from the reviewer pending tuning.
- **Setup (catalyst), Base rate, GM rank, Signal quality score, Confluence** — composites
  or family constants; the catalyst's value is what the validation runs measure, and
  Confluence is the thing being rebuilt.
- **Plan, Entry/SL/T1/T2, Qty, verdict rows** — outputs, not evidence.

## Populations

- **P_all** — every sampled name-date. Context rows (C1–C8) are judged here: they define
  the context.
- **P_s2** — name-dates where C1 = 1 (Stage 2), which is where the panel is actually used.
  Location and execution rows (L*, X*) are judged here.
- Each row's result in the other population is reported, not used for its verdict.

## Tests

**IS / OOS.** Sample dates in order; first 60% in-sample, last 40% out-of-sample; IS dates
within 60 trading days of the first OOS date are purged (their outcome windows overlap it).

**Q2 — information.** On each sample date, the cross-sectional Spearman correlation between
the row and Y60 (a date with fewer than 20 names, or a constant row, is skipped). The row's
IC is the mean over dates. Uncertainty: block bootstrap over dates, blocks of 6 sample dates
(60 trading days, the outcome length), 5,000 resamples, two-sided; a row's p is the larger of
its IS and OOS p. **Pass:** |mean IC| ≥ 0.02 in IS **and** OOS, the same sign in both, and
Holm–Bonferroni across all 19 rows at family-wise α = 0.10.

**Q3 — incremental.** Among the rows passing Q2, on each date regress rank(Y60) on the
standardised ranks of all of them together (Fama–MacBeth). A row's coefficient is the mean
over dates, bootstrapped as above. **Pass:** same sign in IS and OOS, and Holm at α = 0.10
across the rows tested.

**Q1 — redundancy (descriptive).** Pooled Spearman correlation between every pair of rows on
P_all; rows with |ρ| ≥ 0.6 are grouped (complete linkage). Used to NAME the partner a merged
row duplicates, not to decide anything.

## Verdicts

| verdict | rule | what it means on the panel |
|---|---|---|
| **VOTE** | Q2 pass, sign as the panel reads it, Q3 pass | earns a confluence point |
| **MERGED** | Q2 pass, Q3 fail | real information, already carried by another row — show, don't count |
| **INFO-ONLY** | Q2 fail | no measurable ranking power — show, don't count |
| **BACKWARDS** | Q2 pass, sign opposite to how the panel reads it | remove from confluence; flag the row |
| *(C7)* | no declared direction | can earn VOTE in whichever sign IS finds, if OOS confirms |

## Controls before the one run

1. **Placebo:** Y60 permuted across names within each date. Every IC is then noise by
   construction; if any row passes, the code is wrong. This is the only full pass made
   before the real one.
2. **Plumbing check:** row coverage and missing counts per row are printed (no ICs) to
   confirm every engine actually returned values point-in-time.

## What a result can and cannot mean

- A row that fails is not "useless for Jay" — it is **not a confluence vote** as defined. A
  display row can still be the thing that makes a chart legible.
- IC measures ranking across names on a date, not whether one trade works. An IC of 0.03 is
  small per name and still worth a vote — that is the scale real cross-sectional signals
  run at.
- Daily reconstruction cannot see intraday reads; those rows' verdicts are provisional.

## Stopping rule

Runs **once**. No re-slice, no moved bar, no swapped horizon. A failed row is recorded as
failed **in this file**.

## Result

Run once, 24 Sep 2026 (`panel_row_audit.py --run`, log
`validation_runs/_panel_audit_real_run.log`). Protocol held: plumbing check (32,822
name-dates, 459 symbols, 76 dates Jun 2023 → Jun 2026, every row 100% populated; 41 names
lacked 420 bars) → placebo (Y60 permuted within date: all 19 rows INFO-ONLY, noise ICs up to
±0.03) → the single real run. IS 40 dates, OOS 30, 6 purged.

**Every row: INFO-ONLY. No row earns a vote; none is BACKWARDS.**

| row | pop | IC IS | IC OOS | p |
|---|---|---:|---:|---:|
| C1 stage2 | all | +0.005 | +0.041 | 0.86 |
| C2 above200 | all | +0.017 | +0.036 | 0.51 |
| C3 off52 | all | +0.003 | +0.058 | 0.91 |
| C4 minervini | all | +0.033 | +0.050 | 0.40 |
| C5 rs_ratio | all | +0.053 | +0.005 | 0.89 |
| C6 rs_mom | all | +0.018 | −0.050 | 0.48 |
| C7 rsi14 | all | +0.007 | −0.005 | 0.88 |
| C8 adx_di | all | +0.016 | −0.021 | 0.60 |
| L1 zone_d | stage2 | +0.010 | +0.039 | 0.26 |
| L2 zone_w | stage2 | +0.005 | −0.027 | 0.71 |
| L3 near_sr | stage2 | −0.025 | −0.009 | 0.44 |
| L4 near_avwap | stage2 | −0.020 | −0.010 | 0.65 |
| L5 at_vp | stage2 | −0.012 | −0.003 | 0.90 |
| L6 ema_ext | stage2 | +0.013 | −0.001 | 0.97 |
| L7 room | stage2 | +0.012 | +0.023 | 0.32 |
| X1 pa_sigma | stage2 | −0.010 | −0.003 | 0.71 |
| X2 bar_ok | stage2 | −0.017 | −0.012 | 0.26 |
| X3 rv | stage2 | −0.012 | −0.013 | 0.52 |
| X4 arrival | stage2 | −0.003 | +0.009 | 0.84 |

**Power — computed after the run, stated because it changes what the null means.** The
prereg omitted a power statement (the exit-study prereg had one; this one should have).
Block-bootstrap standard errors of the mean IC:

- **Location and execution rows: SE 0.008–0.020 → detectable IC ≈ 0.02–0.05.** A
  well-powered null. In Stage-2 names, none of zone/S-R/AVWAP/VP/room/PA/bar/RV ranks 60-day
  outcomes by as much as that; S/R, AVWAP, VP, bar and RV lean slightly *negative* in both
  windows (not significant).
- **Context rows: SE 0.026–0.039 → detectable IC ≈ 0.07–0.11.** Underpowered: their daily
  IC swings with the market regime. C1–C4 are positive in BOTH windows and the cluster
  composite reads +0.035 / +0.041 — consistent with the selection edge the validation runs
  measure (+~1% matched alpha), but not established by this test.

**Redundancy (Q1, descriptive):** C1–C5 form one cluster at |ρ| ≥ 0.6 (stage, above-200,
off-52w, Minervini, RS-Ratio); C7, C8 and L6 form another (RSI, ADX, EMA20 extension).
Counting the members of a cluster as separate confluence points counts one fact several
times.

**What this does and does not say.**

- It **does** say: summing these rows into a confluence count adds confidence without adding
  measurable information about where price goes over 60 days. The context rows are one
  vote at most, not five.
- It **does not** say the location rows are useless. Their job on the panel is RISK
  GEOMETRY — where the stop sits and how far the entry is from it (the R). A 60-day
  close-to-close IC cannot see that; it asks whether the location predicts return, not
  whether it gives a better entry for the same return. That is a separate, measurable
  question.
- **L1 (daily demand zone)** is the one row with a notable OOS read (+0.039, ~4 SE) but a
  weak IS (+0.010). It fails as registered. It is the natural candidate for a forward,
  pre-registered confirmatory test on dates after this sample.
- The execution rows were tested on DAILY bars; S4 reads them on 75/125-minute bars. Their
  verdicts are provisional, as stated.

**Stopping rule honoured.** Marker `validation_runs/_panel_audit_REAL_RUN_DONE.json`.
