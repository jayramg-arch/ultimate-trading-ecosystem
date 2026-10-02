# Pre-registration — Day-2 follow-through exit for positional trades

**Registered:** 2 Oct 2026, 23:15 IST, before any outcome was looked at.
**Source of the idea:** Jay's note "Positional focus" (`E:\Notes\Positional focus.docx`) — a
"48-hour handoff gate": if the first two Daily closes after entry do not go your way, the
timing was wrong; take the small loss.
**Status:** NOT RUN. The scorer (`followthrough_d2.py`) prints counts only until the
sample threshold below is met, then runs once.

## The question

Do positional trades that show **no follow-through by the second Daily close after entry**
end worse — and would exiting them at that close beat holding them under the standing
exit rules?

## Data — the Reviewer Log only, prospective only

- **Population:** distinct triggers from `logs/ai_review_log.csv` picked by
  `review_priority.pick` (one row per symbol, timeframe and trigger bar; S4 alert > board >
  manual), with **review time on or after 2026-10-03** (the first session after this
  registration and after the 4 × ATR(D) positional stop floor), plan type **positional**
  (the review's Plan row; `commander_core.plan_type` if the row is unreadable).
- **Entry:** the `V_plan` fill from `entry_shadow.py` (S4's planned entry; limit if below
  the trigger close, stop if above; within 8 bars). Unfilled triggers are excluded.
- **Stop:** the floored positional stop — the lower of S4's plan stop and
  entry − 4 × ATR(14, daily) as of the trigger bar (`entry_shadow` variant `S_4atrD`).
- **Bars:** Dhan daily bars. NSE holidays skipped via `nse_calendar`.
- Historical replays may be shown alongside as supporting evidence; they cannot decide.

## Definitions (fixed)

- **Day 1 / Day 2** = the first and second completed NSE sessions **after** the fill
  session. A fill on the last bar of a session counts that session as Day 0.
- **FT-FAIL (primary):** the Day-2 close is at or below the entry price.
- **FT-FAIL-B (secondary, reported, cannot decide):** neither Day 1 nor Day 2 is a green
  candle (close > open).
- **Outcome R:** (price − entry) / (entry − stop), the stop checked on every daily bar after
  the fill (a gap through it fills at the open). **R20** = at the 20th session after the
  fill (primary); **R40** at the 40th (secondary). A trade stopped earlier keeps its stop R.
- **Exit-at-D2 counterfactual:** for FT-FAIL trades, R if exited at the Day-2 close instead.

## Hypotheses

- **H1 (descriptive):** mean R20 of FT-FAIL trades is lower than FT-PASS trades by
  **≥ 0.30R**.
- **H2 (the rule):** among FT-FAIL trades, exiting at the Day-2 close beats holding:
  mean(R_exitD2 − R20) **≥ +0.15R**, the **median of that difference is ≥ 0**, and the
  symbol-bootstrap 95% CI of the mean difference **excludes zero**.

The rule is adopted only if **H1 and H2 both pass**, and the sign of H2 is the same in
tier 1 (S4 alert) and tier 2 (board). Tiers are reported separately, never pooled into the
headline.

## Sample and procedure

- **Run once**, when there are **≥ 40 FT-FAIL trades** (tiers 1 + 2) with R20 elapsed. Until
  then the scorer prints counts only. A cell under n = 15 is reported as THIN and cannot
  pass.
- **Bootstrap by symbol** (10,000 resamples) — repeated triggers on one name share an
  outcome window.
- Missing data is excluded and counted, never filled with zero.
- A failed hypothesis is recorded as failed. No re-slicing, no new thresholds, no new
  definitions after the run; a different idea needs its own registration.
- **Placebo:** before the real run, `--placebo` shuffles the FT-FAIL labels across all trades
  so the code can be debugged without spending the run.

## Amendment 1 (2 Oct 2026, 23:35 IST — before any registered row exists)

The first placebo shuffled labels *within symbol*. Most symbols have one trade, so it left
real labels in place and printed real numbers for **September** rows (review dates before
3 Oct, Day-2 elapsed, R at ≤ 14 sessions): FT-FAIL 41 of 53, H2-style difference +0.24R.
Those rows are **outside the registered window** and are not evidence for or against the
rule — in a falling tape any earlier exit beats holding, which is exactly why the window,
the 20-session horizon and the tier-sign condition are fixed in advance. The placebo now
shuffles across all trades. No definition, threshold or window changed.

## Amendment 2 (2 Oct 2026, 23:45 IST — before any registered row exists)

The corrected placebo (labels shuffled across all trades, so FT-FAIL means nothing) still
"passed" H2: exit-at-D2 minus hold +0.23R, CI [+0.10, +0.38]. In a falling tape, exiting
ANY trade on Day 2 beats holding it. As written, H2 measured the tape, not the rule.
**H2 is replaced by a difference-in-differences:**

- **H2′:** the Day-2 exit benefit, mean(R_exitD2 − R20), is larger for FT-FAIL trades
  than for FT-PASS trades by **≥ +0.15R**, with the symbol-bootstrap 95% CI of that
  difference excluding zero, and the FT-FAIL median benefit ≥ 0.
- H1, the window, horizon, threshold (≥ 40 FT-FAIL with R20), tiers and the tier-sign
  condition are unchanged. A placebo must FAIL H2′; the scorer is checked against that
  before the real run.

## What a pass would change

Positional plans would carry a Day-2 check: an FT-FAIL trade is exited at the Day-2 close,
before the trail takes over. It would be wired into `pyramid_logic` (as an EXIT rung for
positions ≤ 2 sessions old) and the Risk Shield, and shown on the S4 Plan row as text only.
A fail changes nothing.
