# Pre-registration — FLOW-GATE (failed breakout overrules a breakout TAKE)

**Registered:** 12 Oct 2026, ~16:10 IST — written with the code, before the gate has fired
once. No outcome has been looked at.
**Source:** Jay, 12 Oct 2026: a FAILED BREAKOUT should not touch current holdings, but
should touch new trades. Agreed scope: the reviewer, not S4's GO gate (S4 cannot see S5,
and GO drives the alerts).
**Status:** LIVE, NOT EVALUATED. The gate runs from the next receiver restart; it is judged
once, on the rule below, and removed if it fails.

## The rule being tested

In `s4_review.py`, a model ruling of **TAKE** (incl. "TAKE · reduced size") is overruled to
**WAIT — for a close back above the level on stacked buy imbalances** when **all** hold:

1. S5's ORDER-FLOW READ is **FAILED BREAKOUT**;
2. its signal bar is the last closed bar or the one before (**age ≤ 1**);
3. the entry is **breakout-type**: POS-BO / SWG-BO, a Breakout setup on the panel, or a
   buy-STOP in the panel's or the model's plan;
4. the failed level is within **0.5 × ATR** (the trigger chart's ATR, from S4's title row)
   of the plan's entry;
5. the name is **not held**.

It never rules PASS. It runs on the **model's own ruling, before** the index, held and
exposure gates, so a firing is recorded even when another house rule would also have
stopped the trade (otherwise a Bear tier would leave this test with no data).
Every firing writes `flow_gate = "TAKE->WAIT @ <level>"` to `logs/ai_review_log.csv`.

## The worry it has to clear

Order flow cannot be backtested (TradingView-only, bar by bar), and the last flow-type veto
tested here — Wyckoff distribution, 28 Jul 2026 — ran **backwards**: the vetoed names did
better (+5.60% vs +0.52%). A veto that feels right is not evidence. So the gate stays only
if the names it held back did no better than the TAKEs it left alone.

## Data — prospective only

- **Overruled (FG):** every review row with a non-empty `flow_gate`.
- **Control (C):** review rows where the **model ruled TAKE**, the entry was breakout-type
  (condition 3), the name was not held, and FLOW-GATE did **not** fire — from the same
  dates. (`ai_ruling` is the post-gate ruling; the model's own ruling is in the review
  `.md` above the gate lines, and FG rows carry it in `flow_gate`.)
- **Entry / stop:** the plan's entry and stop as recorded in the row (`entry`, `stop`); the
  entry fill is simulated as in `entry_shadow.py` (stop entry above the trigger close,
  within 8 bars of the trigger TF). Unfilled rows are excluded from both groups and
  counted.
- **Outcome R:** (price − entry) / (entry − stop), stop checked on every bar of the trade's
  own clock (Daily for positional, the trigger TF for swing); **R10** = 10 sessions after
  the fill (primary), **R20** (secondary).

## Hypothesis and decision

- **H (the gate earns its place):** mean R10 of FG is lower than C by **≥ 0.25R**, the
  median difference is ≤ 0, and the symbol-bootstrap 95% CI of the mean difference
  **excludes zero** on the negative side.
- **Decision:** if H fails — including the case where FG did as well or better than C —
  **the gate is removed.** If H passes, it stays and is re-checked at double the sample.
- Swing and positional are reported separately; a cell under n = 15 is THIN and cannot
  pass. The headline is never pooled across them.

## Sample and procedure

- Run **once**, when FG has **≥ 30 rows** with R10 elapsed (and C at least as many).
  Until then only counts are reported (a counter in the evening digest is a follow-up).
- Bootstrap **by symbol**, 10,000 resamples.
- No threshold in the gate (0.5 × ATR, age ≤ 1, the breakout test) is tuned before the
  run. A failed result is recorded as failed, not re-sliced.
