# PRE-REGISTRATION — does a GO pick better names, by market tier? (forward)

**Registered:** 16 Oct 2026 (IST), before any of the data it will use exists.
**Owner:** Jay. **Script:** `go_by_regime_study.py` (committed with this file).
**Runs once on:** **2027-01-15** (scheduled), on signals from **2026-10-17** onward.

## Why

Doc 38: on the live boards from 18 Aug to 16 Oct, rows at 5/5 GO trailed the Nifty 500 over the
next 10 sessions on every board (Daily −1.92pp, 30 % beat; 125m −0.88pp; 75m −0.31pp) while
non-GO rows sat near +0.3pp / 50 %. Breakout GOs were worst. That window was one regime (a 7 %
fall), so nothing was acted on. This test decides it on new data.

## Definitions (fixed now)

- **Rows:** `logs/gm_signal_log.csv`, all three boards, signal date ≥ 2026-10-17.
  **GO** = label starts `5/5` (own clock, no `⏱`); **non-GO** = every other row that is not
  stage-blocked (`⛔`) and not on the wrong clock (`⏱`). Playbook from the log's `playbook`.
- **De-duplication:** one row per symbol per board per group per 5 sessions.
- **Outcome:** 10-session excess return = stock close 10 sessions after the signal ÷ close on
  the signal date − the same for the Nifty 500 (^CRSLDX), in percentage points. Daily closes
  for every board.
- **Tier:** the exposure tier on the signal date from the MarketRegime score (≥ 6 OPEN, 3–5
  NEUTRAL, ≤ 2 BEAR); no score → BEAR.
- **Uncertainty:** 95 % CI, 2,000 bootstrap resamples by symbol. Each group needs n ≥ 60.

## Hypotheses

- **H1 (GO hurts in weak tapes):** in BEAR + NEUTRAL tiers pooled, mean excess(GO) − mean
  excess(non-GO) ≤ −0.50 pp **and** the CI upper bound < 0.
- **H2 (breakouts are the problem):** in BEAR + NEUTRAL, mean excess(breakout GO) − mean
  excess(pullback GO) ≤ −0.50 pp **and** the CI upper bound < 0.
- OPEN-tier numbers are reported, never used to decide.

## Decision rule

- H1 true → GO alerts are suspended in BEAR and NEUTRAL tiers (the board still shows GO; no
  alert, no Phase-13 review, no GM-POS alert).
- H2 true (H1 false) → only BREAKOUT GOs are suppressed in BEAR and NEUTRAL.
- Neither → nothing changes; the Aug–Oct result is recorded as specific to that fall.
- THIN (n < 60 in a needed group) → nothing changes; rerun once more on 2027-03-15.

## Discipline

- `--placebo` (GO/non-GO labels shuffled) runs first to check the plumbing: H1 must be false.
- One run; a failed hypothesis is recorded, not re-sliced. Known biases: overlapping 10-session
  windows across boards (handled by the by-symbol bootstrap), regime mix outside our control.
