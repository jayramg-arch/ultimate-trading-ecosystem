# 38 · Paper Trades post-mortem — why 43 of 52 Reviewer TAKEs stopped out (16 Oct 2026)

Source: `data/paper_trades.csv` (cohort "Reviewer TAKE", 52 filled), `logs/ai_review_log.csv`,
`logs/gm_signal_log.csv` (outcomes filled 16 Oct), the MarketRegime table, and an independent
re-simulation from Dhan daily bars (`reports/paper_failure_sim_20261016.csv`).

## The headline

Stops were the visible cause, but not the only one. Five things stacked:

| # | Cause | Evidence | Share of the damage |
|---|---|---|---|
| 1 | **Stops inside normal noise** | Median stop 1.48 × ATR(D) on plans classed POSITIONAL; median adverse move before exit 1.59 × ATR; 19 of 43 stops hit on the first session, 27 within three | The largest single factor |
| 2 | **Entered into a falling market** | 50 of 52 fills between 14 Sep and 4 Oct while the Nifty 500 fell 23,529 → 21,858 (−7%); regime score 1 (BEAR) on 24 fill dates, 4 on the other 28 | Roughly a third of the stock loss is the index (−1.3% of −3.4%) |
| 3 | **The picks themselves lagged the index** | Fill to today, no stop at all: stocks −3.4% vs index −1.3%; only 29% beat the index; 15 of 52 above entry | Selection did not help in this window |
| 4 | **GO and TAKE did not pick better names** | Live boards Aug–Oct, 10 sessions after the row: GO rows trailed the index on every board (Daily −1.92pp, 30% beat; 125m −0.88pp, 37%; 75m −0.31pp, 41%) while non-GO rows sat at +0.3pp, 50%. Reviewer TAKE −0.51pp / 53% vs WAIT +0.36pp / 49% vs PASS +0.09pp / 42% | The timing layer added nothing, and in this tape slightly subtracted |
| 5 | **Clustered, correlated entries** | 17 fills in the week of 14 Sep, all 17 stopped — one market bet taken 17 times | Turned one bad week into most of the losses |

## What a different stop would have done (same 52 entries, to today's close)

| Stop | Stopped out | Mean R | Median R |
|---|---|---|---|
| 1.5 × ATR(D) (≈ what the plans used) | 79% | −0.65 | −1.00 |
| 2.5 × ATR(D) | 58% | −0.53 | −1.00 |
| **4.0 × ATR(D) (house floor since 3 Oct)** | **23%** | **−0.34** | −0.41 |

The 4×ATR floor alone moves the stop-out rate from 79% to 23% — inside the 40% you said you can
live with — but the result is still negative, because causes 2–4 remain. The trades taken after
the floor (S4 TAKE IT cohort, n = 10) are running at −0.33 R with 6 stopped, against −0.78 R
before: better, still small and still negative.

## What is already fixed (all live before this post-mortem)

- **4 × ATR(D) positional stop floor** — 3 Oct.
- **Exposure rule** — 6 Oct. On these 52 fill dates it would have blocked all 24 BEAR-score
  entries and limited the other 28 to half risk, three a week: about 9–10 trades instead of 52.
- **Open-risk budget** — 7 Oct.
- **Ladder grace period, two-tier stop, Chandelier anchored at entry** — 7–12 Oct.

So most of these losses come from a policy that is no longer the policy.

## What is NOT fixed — and the action plan

1. **Paper Trades measures a policy you do not run.** It takes every TAKE at full house size,
   regardless of the exposure tier, the weekly cap or the open-risk budget. Fix: the paper cohort
   honours the tier (BEAR = no entry, NEUTRAL = half risk, max 3 a week) and the open-risk
   budget, so it shows what the rules would actually have done.
2. **No baseline cohort.** Add a third paper cohort — "qualified, no timing": every Stage-2
   catalyst name bought at the close with the 4 × ATR stop. It answers, live, whether the GO
   gate and the reviewer add or subtract.
3. **GO selected against returns in this tape.** Pre-register a forward test: GO rows vs non-GO
   rows on the live boards, by regime tier, from 17 Oct. If GO keeps trailing non-GO in
   BEAR/NEUTRAL tapes, GO alerts are suspended in those tiers. Not acted on now: one regime, and
   it is the same falling tape that hurt everything.
4. **Breakout GOs were the worst bucket** (−1.27pp, 34% beat; pullbacks −0.75pp, 37%; recovery
   +0.37pp, 52%). Include in the same pre-registration: in non-BULL tiers, are breakout GOs
   worse than pullback GOs?
5. **The reviewer does not discriminate.** TAKE, WAIT and PASS returned the same over 10
   sessions. Keep it as the plan writer and checklist (it catches void stops, ceilings as
   targets, mis-stated R); stop reading TAKE as a signal. The paper cohort "Reviewer TAKE" is not
   a strategy and should be relabelled as a record.
6. **Concentration.** A weekly cap on new entries in every tier (not only NEUTRAL), and the
   correlation gate on new entries as well as adds.
7. **Hold positionals as positionals.** With the 4 × ATR stop, the trail (Chandelier 4.5 ×)
   does the work; 88% of positional exits in the backtests came off the trail. Do not tighten.

## The honest bottom line

The ecosystem's only measured edge is selection by stage and catalyst — about +1% per trade
against the index historically, with a confidence interval that includes zero. The timing layer
(GO, the reviewer) has not shown any edge in four separate tests, and in this falling tape it
picked slightly worse names. In a BEAR tape the right position is mostly cash, which the
exposure rule now enforces. The work ahead is not more indicators: it is fewer, wider-stopped
positional trades taken only when the tape allows, and a live baseline that tells us within a
few months whether the timing layer earns its keep.
