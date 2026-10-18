# PREREG · the Minervini trend template as a v1 gate (18 Oct 2026)

Jay (18 Oct): "why did we not consider the Minervini template as a gate in v1?" — in v1 the
8-point template (`commander_core.minervini_checks`) is a ranking overlay at GM Step 2, not a
veto (except the trend stack inside SWG-BO). Its effect as a gate on v1's own signals has never
been measured. Written BEFORE any number below exists.

## Data and unit

- `logs/gm_signal_log.csv`, signals from 2026-08-18 (the same window and unit as
  PREREG_p_less_forward): rows whose S4-GO reads **5/5** on their OWN clock (no `⏱` prefix) on the
  Daily, 75m and 125m boards — the signals v1 actually trades. De-duplicated per symbol × TF:
  a repeat within 5 business days is dropped.
- **Outcome (identical to P-less):** entry at the next session's open; stop = 4 × ATR14(D) on Daily,
  1.5 × ATR14(D) on 75m / 125m; result in R after 20 sessions (Daily) or 5 sessions (intraday);
  −1 R if the stop is touched. Only matured rows count.
- **The template, rebuilt as of the signal date** exactly as v1 reads it live: price = the row's
  `cmp`; SMA50/150/200 of daily closes; SMA200 vs its value 21 sessions earlier; 52-week high/low =
  252-session max High / min Low; RS = JdK RS-Ratio > 100 on confirmed weekly bars vs the Nifty 500
  (`bull_screener.compute_weekly_indicators`, weeks labelled after the signal date excluded).

## Hypothesis (primary: BULL-path rows)

Recovery-path names sit below their 200-DMA and fail the template by construction, so pooling
would compare paths, not the template. Primary population = rows with `path` = bull.

- **H:** mean R(template 8/8) − mean R(template ≤ 7/8) ≥ **+0.10 R**, the symbol-bootstrap 95 % CI
  of that difference above **0**, and the 8/8 group's stop-out rate not more than 5 pp worse.
  Each group needs n ≥ 60, else THIN.
- **Placebo first:** the 8/8 labels shuffled must FAIL H.
- **Descriptive only:** results by score (≤ 5, 6, 7, 8), by timeframe, ≥ 7 vs ≤ 6, and the
  recovery path.

## Decision

- PASS → propose the template (8/8) as a hard gate for bull-path names at GM Step 2 — Jay's call,
  with a forward check on new signals.
- FAIL → it stays a ranking overlay; recorded in the Golden Rules.
- THIN → the counts are reported and the run is repeated when both groups reach 60.
- One run. Known limits: one regime (Aug–Oct 2026, mostly BEAR / NEUTRAL); a fixed horizon, not
  the trail; the template here is v1's version (RS = JdK > 100, not Minervini's RS rating ≥ 70).
