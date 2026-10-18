# 40 · Transition plan — from the trigger system to the v2 core (16 Oct 2026)

## Where the evidence stands

| Question | Answer | Source |
|---|---|---|
| Does the entry-timing layer (GO, PA, reviewer) add an edge? | No — five tests | Docs 38–39, PREREG_pa_*, PREREG_p_less_forward |
| Which architecture won? | Clenow "Stocks on the Move" (P1): regime gate + trend-quality rank + ATR risk parity + weekly rank exits | PREREG_pro_systems_tournament |
| Is P1's exact setting reliable? | **No — not robust.** 22 of 26 nearby settings beat the benchmarks, but the headline (MAR 1.16) is an optimistic peak; expect ~0.75 | PREREG_p1_robustness |
| Do fundamental floors help P1? | No — both cost return (RFF −0.5 pp; BFF weak-floor −6.4 pp/yr in 2018–22) | PREREG_p1_fundamental_floor, PREREG_p1_bff_floor |

## 1. The current book (legacy positions) — Jay's decision: hold for recovery

Jay is choosing to hold the current positions for a recovery and close some near break-even,
because a further drawdown on capital is not affordable. That is his call. The plan only asks
that holding is done with the protections that make it survivable:

- **The Disaster SL stays resting at Dhan on every holding** and is never cancelled or widened
  to "give it room". Holding for recovery means not selling at the thesis level; it does not
  mean removing the floor under the position.
- **No averaging down** on a losing holding.
- **A review date, not an open-ended wait:** each holding is looked at again at the first weekly
  close with the Nifty 500 back above its 200-day SMA, and in any case on **15 Jan 2027**.
- A note to keep beside it: the market does not know the entry price. At each review the question
  is "would I buy this today with this money?" — the break-even level is not part of that answer.

## 2. New entries — none until the market recovers

**"Recovered" is defined mechanically** so the decision is not made in the moment:
- the Nifty 500 closes a week **above its 200-day SMA** (P1's own regime gate), **and**
- the exposure rule's tier is **NEUTRAL or OPEN** (regime score 3+).

Until both hold, no new entries in either system. The P1 paper book enforces the first by itself.

## 3. Path to real money for the v2 core

P1 is paper-only today (robustness failed). Real money needs all of these:

1. **Three months of paper** (from 16 Oct 2026 → **16 Jan 2027** at the earliest).
2. **The market has recovered** (definition above).
3. **The paper book has done its job:** since its start, P1 paper is at or above the Nifty 500
   and its drawdown is shallower than the index's.
4. **A forward pre-registration that answers the robustness doubt.** Proposed: a third paper
   book, **P1E — an ensemble** (the average rank of the 60/90/120-session lookbacks, a 25 % cut-off,
   0.10 % risk), registered now and judged only on data from now on. Ensembles are the
   standard professional answer to parameter risk: no single setting has to be right.

**Stages once cleared:** one-third of the trading capital into the chosen book → two-thirds
after three more months if the live book tracks its paper twin (within 3 percentage points) →
full. Each stage is reversible: a live drawdown deeper than the backtest's worst (−19 % for P1,
−24 % allowed for the ensemble) stops the scale-up.

## 4. What happens to the existing tools (proposals — Jay approves each)

| Tool | Today | Proposed role under v2 |
|---|---|---|
| GM boards, S4, S5 | choose and time entries | **execution aids** for the weekly P1 buy list (place sensible limits; avoid buying straight into a wall) — never a veto on the list |
| S4 GO watchlist alerts, GM-POS GO alerts | trade triggers | keep running for the legacy book's monitoring; no longer entry signals |
| AI reviewer + Phase 13 board reviews | rules on every GO | **pause Phase 13** (`BOARD_REVIEWS=0`) to save API cost; use the reviewer only as a checklist on the weekly P1 buy list |
| Risk Shield, exposure rule, Disaster SL | live | **unchanged** — they protect both books |
| Paper Trades | trigger cohorts | the v2 panel is the main view; trigger cohorts stay as the control record |

## 5. Dates

| Date | What |
|---|---|
| Every Friday close | P1/P1F decide the next orders (auto-pilot Phase 12i) |
| 15 Dec 2026 | P-as-a-tag forward check (scheduled) |
| 15 Jan 2027 | GO vs non-GO by regime (scheduled); legacy-book review date |
| 16 Jan 2027 | earliest date the three-month paper condition can be met |
| 16 Apr 2027 | six-month re-read of P1 vs P1F (scheduled) |

## Decisions taken (16 Oct 2026)

- **P1E started** as a third paper book (forward only, docs/PREREG_p1e_ensemble_forward.md).
- **Phase 13 board reviews paused** by default (`BOARD_REVIEWS=1` turns them back on).
- **Survivorship correction (17 Oct):** P1 SURVIVES on a point-in-time top-500 universe (CAGR 19.3 %,
  max DD −22.4 %, MAR 0.86 vs Nifty 500 0.29 and Momentum-30 replica 0.40). Expectations for the
  v2 core are now set on these numbers, not the 21.9 % / 1.16 from today's list
  (docs/PREREG_survivorship_tournament.md).

## Decisions taken (17 Oct 2026) — both systems run in parallel

- **The current system is NOT retired.** Boards, S4, alerts, the reviewer (Phase 13 is back ON) and
  its paper record all continue. If the market recovers (the definition in §2) before 16 Jan 2027,
  Jay may trade recovery setups through the current system rather than sit idle.
- **The v2 system is built now, in parallel**, with its own paper-trading instance and page
  (ANALYSIS › 🧭 PAPER · v2 SYSTEM), routed through the same reviewer (execution check, tag `v2`).
  Design and open questions: Doc 41. Fine-tuning follows the P1E results via forward tests.

## Decisions taken (18 Oct 2026) — Jay's answers to Doc 41

- v2 gets one-third of trading capital when it goes live (Doc 41 Q2); 0.10 % risk per ATR stays.
- Every other answer was built into a house book (V2H) and a stop-only book (P1ES), pre-registered
  and tested once (docs/PREREG_v2_house_rules.md): both failed. The stop costs ~2.5 pp a year; the
  exposure tiers and F&O priority cost ~4.5 pp each. **P1E remains the candidate** for the gates in §3;
  P1ES and V2H run forward on paper. Which house rules to keep is Jay's call (Doc 41 §9).
