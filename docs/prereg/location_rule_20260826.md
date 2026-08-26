# PRE-REGISTRATION — location rule A/B (26-Aug-2026)

Written BEFORE running. Jay asked for this on 25-Aug when he accepted A2 as an
interim: *"I personally do not rely on pivot zones and want to bank on pattern zones
only. However, as the pattern zones' hit rate is too low, let's go with A2 for now.
However, record my concern and perform a thorough backtest."*

## The question
Does requiring a PATTERN (leg-base-leg) zone for location beat admitting pivot
shelves — and is A2 (pivot allowed only with a second source) better than either?

## Arms (identical candidates, identical everything else)
- `any`     — legacy: any fresh demand zone, else S/R, else AVWAP. What every prior
              s4go run measured, and what replay still ran until today.
- `a2`      — pattern stands alone; a pivot shelf needs one confirming source.  SHIPPED
- `pattern` — pattern zones only; pivots never satisfy location.  JAY'S PREFERENCE

## Primary metric
Mean matched-horizon alpha per trade, benchmarked to the ACTUAL hold (the 26-Jul fix).
Reported with median, win%, fill%, and stop-out%.

## Decision rule, fixed in advance
Adopt `pattern` over `a2` only if BOTH:
  (a) mean alpha is at least as good, AND
  (b) the fill count stays workable — a rule that fires on too few names is not an
      edge, it is an absence. Pre-set floor: >= 60% of a2's filled trades.
If `pattern` wins on alpha but fails the fill floor, the honest conclusion is
"better per trade, too rare to run" — report it, do not adopt it silently.
If `any` wins, A2 was a mistake and pivots carry real information.

## What would make this UNINTERPRETABLE
- Any arm with < 40 filled trades: report n, draw no conclusion.
- A result inside +/- 0.3pp across arms: call it a null, not a ranking. These arms
  share most of their trades, so small gaps are noise.

## Known limits, stated up front
- Candidate cache predates the 3-Aug screener changes (vdu_window). All three arms
  see the SAME candidates, so the comparison is internally valid, but the book is
  not today's book.
- Location inside replay is DAILY-only; the live board also reads trigger-TF zones.
- This is a RE-BASELINE: reaction-as-location and tested-rule 3 both entered
  zone_support today, so these numbers are not comparable to s4go runs before
  26-Aug.
- Multiple-testing debt is real and uncorrected across this project. Three arms on
  one pre-registered question is the cheapest version of this test, not a sweep.
