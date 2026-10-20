# PRE-REGISTRATION — a debate-style Reviewer (bull / bear / judge) vs the single Reviewer

Registered **20 October 2026**, before any model call for this test. Jay asked for it on 20 Oct after
the TradingAgents review ("test the debate-style Reviewer as a pre-registered A/B").
Harness: `debate_ab.py`. Results are appended to this file once, below the line, and are not re-run.

## Why

The Reviewer is one model making one ruling. On the live record its rulings do not separate outcomes:
on the 121 Log triggers with a 10-session score, TAKE −0.26R, PASS −0.17R, WAIT −0.41R. TradingAgents
(multi-agent LLM desk) claims an advocate debate before the decision improves it. This tests that claim
on Jay's own triggers and outcomes.

## Units and outcome

- **Units:** every row of `logs/entry_shadow.csv` with variant `S_4atrD` and status `scored` or
  `no fill`, whose review file (`logs/ai_reviews/*.md`) exists — **121 rows, 41 symbols,
  22 Sep → 13 Oct 2026** at registration. Rows scored after registration are not added.
- **Outcome:** `R10` of `S_4atrD` — S4's planned entry (`V_plan` fill rule), the stop = the lower of
  S4's stop and entry − 4 × ATR(14, daily) (the house positional floor), R after 10 sessions. A
  `no fill` row scores **0R** (the trade did not happen). `entry at/below stop` and `pending` rows are
  out.
- **Ruling:** the RULING line, parsed by `s4_review._ruling_line`. `TAKE` and `TAKE · reduced size`
  count as TAKE; WAIT and PASS are non-TAKE.

## The two arms (same model, same day, same inputs)

Both arms read the **identical saved panel read** from the review file. Both use
`s4_review.build_prompt` with an empty POSITION CONTEXT and **no current market-context line** (the panel
read already carries that day's market line; today's would leak the present). House gates (exposure,
index-first, held-name, flow) are **not** applied — this tests the model, not the gates. Model: the
live Reviewer's (`gemini-3.5-flash-lite`, fallback `gemini-3.1-flash-lite`).

- **A — single (control):** one deliberation, exactly as the live Reviewer.
- **B — debate:** a BULL advocate argues for taking the plan and a BEAR advocate argues against it
  (each ≤ 200 words, every point must cite a number from the panel, neither rules); then the JUDGE —
  the same Reviewer prompt plus both briefs — rules in the usual format.

A placeholder echo or an unparseable ruling is retried once in each arm (the live rule); still
unparseable → the row is dropped from that arm and the count reported.

## Measure and hypotheses

Separation **S = mean R10 of TAKE rows − mean R10 of non-TAKE rows**, per arm. Confidence intervals: 95 %,
10,000 bootstrap resamples **by symbol** (consecutive triggers on one name share an outcome window).

- **H1:** S(B) − S(A) ≥ **+0.15R**, and the CI of the difference lies above 0.
- **H2:** S(B) ≥ **+0.10R**, and its CI lies above 0 — the debate must create real separation, not just
  a smaller negative.

**PASS = H1 and H2.** Minimum sample: ≥ 100 rows in each arm with ≥ 20 TAKE and ≥ 20 non-TAKE;
otherwise the result is **THIN** and nothing is concluded.

**Power, stated now:** with ~121 rows and 41 symbol clusters the CI on a difference of separations will
be wide (roughly ±0.3R). Only a large effect can pass; a FAIL here is weak evidence against a small
effect and is recorded as such.

## Procedure

1. `python debate_ab.py --placebo` — the scoring code on RANDOM rulings for both arms (no model calls);
   it must FAIL. Run before any model output is scored.
2. `python debate_ab.py --plumbing 5` — 5 rows through both arms to check prompts and parsing;
   rulings printed, **outcomes not shown**.
3. `python debate_ab.py --run` — all units once. Model answers are cached per row so a crash resumes
   without re-asking; outcomes are joined only after both arms are complete. The script refuses to run
   again once results are written.

Descriptive only (not tested): agreement between the arms, TAKE share, the historical live rulings'
separation on the same rows, R5 and the `S_plan` stop, and the call count (B costs 3× A).

## Decision

- **PASS** → a `--debate` mode is added to the Reviewer behind a flag; switching live is Jay's call.
- **FAIL** → recorded here; the Reviewer stays single-model.
- **THIN** → no conclusion; re-registered on a larger forward sample if Jay wants it.

### Amendment 1 (20 Oct, before any model call)

The "121 rows" above was a miscount. Twelve of them are marked `scored` but carry only R5: their
10-session window had not closed (triggers of 6–13 Oct). Under the registered outcome rule they are
pending and are out. **The unit set is 113 rows, 37 symbols.** No rule changes; the minimum sample
(≥ 100 rows) still holds. The placebo, run on these 113, FAILED as required (S(B) − S(A) −0.131R,
CI [−0.357, +0.110]) — and shows that random rulings alone move a separation by about ±0.15R on
this sample.

---
## Result

*(not run yet)*
