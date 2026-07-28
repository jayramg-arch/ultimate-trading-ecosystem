# PRE-REGISTRATION — exit policy: Dhan Trailing Target / Trailing SL vs the current scheme

**Written 28-Jul-2026, BEFORE the study simulator was run.** Author: Claude, at Jay's
request ("go ahead, start with these 6 configs").

## Why pre-register

"Find what's optimal" over a parameter grid is the single failure mode this desk's own
audit named as its largest statistical liability: 98 validation runs, 4 alpha-selected
sweeps, 3 A/Bs whose winners became production defaults, and no correction for multiple
testing anywhere. With ~1,100 trades, the best cell of a 30-cell grid is noise.

So: a SMALL, FIXED set of six doctrinally-motivated configurations, declared here before
any of them is run, evaluated per family, on a pre-declared in-sample / out-of-sample
split, with an adoption rule fixed in advance.

## What is being isolated

**Entries are held constant.** Every config replays the SAME 1,103 trades from run
`20260728_191035` (44 anchors, 2022-06-15 → 2026-01-15, bull screener, catalyst-aware
windows). Only the EXIT policy varies. This isolates exactly the question asked: given
the entries the system already produces, which exit scheme is best?

## Why the question changed shape

Under Dhan's Trailing SL the stop preserves its gap and ratchets — it can never become
tighter than where it started. Therefore **the initial SL distance IS the trail
distance**; they are one parameter, not two. That means this study also bears on the
largest known leak in the book (186 of 464 trades in the corrected-horizon run died at
the initial stop within ~7 days, 5.9% win, PF 0.02), not merely on the 12.7% that reach
T1.

## Baseline, stated so it is not misremembered

The CURRENT simulator already scales out, with catalyst-aware sizing:
SWG-GAP / SWG-REV 50/50 · other SWG 33/33 · POS / WYC / REV 25/25; stop moves to
BREAKEVEN after T1; the remainder trails on a peak-anchored Chandelier (highest close −
4.5 × ATR); same-bar priority SL → T1 → T2 (pessimistic); commission per leg.
Gemini's 50/50 proposal is therefore a VARIATION on an existing scale-out, not the
introduction of one.

## The six configurations (fixed)

| id | policy |
|----|--------|
| E0 | CONTROL — reproduce current behaviour exactly |
| E1 | Dhan-native: gap-preserving ratchet TSL, trailing target, no fixed target |
| E2 | E1 + tighten the stop ONCE at +1R (POS 4.5×ATR, SWG 1.5×ATR) |
| E3 | Gemini's plan as written: 50/50 both families, fixed T1 + trailing target on the runner, 1.5×ATR everywhere |
| E4 | Claude's recommendation: POS single order TT-on, no fixed target; SWG 50/50 fixed T1 + T2 with TT OFF |
| E5 | pure trail, no targets at all ("let it run" extreme) |

Trail jump for ratchet modes: 1.5 × ATR(14) unless the config says otherwise.
Target jump where a trailing target is used: 0.5 × ATR(14) — small on purpose, because
the jump is how close price gets to the target before it steps away (a LARGER jump makes
premature capping MORE likely, not less).

## Validity check — the study is void if this fails

E0 must reproduce the recorded per-trade `Return_pct` of the source run. The study
simulator is written separately from `replay.py` (production code left untouched), so
E0 is the control that proves the reimplementation is faithful. Acceptance: median
absolute difference <= 0.25pp and >= 95% of trades within 1.0pp. If E0 does not
reproduce, the comparison is meaningless and the result is reported as VOID.

## Split (fixed)

- **IN-SAMPLE:** anchors 2022-06-15 → 2024-05-15 (n≈639)
- **OUT-OF-SAMPLE:** anchors 2024-06-17 → 2026-01-15 (n≈464)

## Primary metric and adoption rule

Primary: **mean matched-horizon alpha, per family (POS / SWG), never pooled.**
Secondary, reported always: median alpha, win %, profit factor, days held, initial-SL
hit %, trail-SL hit %, and % of trades reaching T1.

A configuration is ADOPTED for a family only if:
- **A.** it beats E0's mean alpha by >= 1.0pp in-sample for that family, AND
- **B.** it also beats E0 out-of-sample for that family (any positive margin), AND
- **C.** it does not worsen the median by more than 1.0pp (guards the failure mode found
  in the 23-Jul stop A/B, where a wider stop lifted the mean while making the median
  materially worse — converting quick small losses into slow large ones).

If no configuration satisfies all three for a family, the verdict for that family is
**KEEP E0**. "Nothing beat the control" is a valid and expected result and will be
reported as such rather than resolved by picking the largest number.

## Known limits, stated up front

- Daily bars cannot reproduce a continuously ratcheting intraday trail; the ratchet is
  evaluated once per bar on the bar's high. This ranks policies; it does not forecast
  live P&L precisely.
- Same-bar stop-vs-target ordering is resolved pessimistically (stop first), inherited
  from the production simulator.
- The universe is present-day nifty500 applied to 2022-24 anchors (survivorship,
  already disclosed in `validation.py`).
- The two windows are different regimes (IS baseline alpha is materially higher than
  OOS). Cross-window magnitude comparisons are not meaningful; only the WITHIN-window
  ranking versus E0 is.
