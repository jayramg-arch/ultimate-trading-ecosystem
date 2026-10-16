# PRE-REGISTRATION — the tournament on a survivorship-corrected universe

**Registered:** 16 Oct 2026 (IST), before the universe was built or any result computed.
**Owner:** Jay ("go ahead with the survivorship"). **Script:** `survivorship_backtest.py`.

## Why

Every earlier test used **today's** Nifty 500 list. A stock that is in the index today got there
partly by rising, so testing 2018–2026 on today's members quietly hands every variant the
winners in advance. The equal-weight universe of today's members (B2) beating almost everything
was the tell. This test removes most of that bias.

## The point-in-time universe (fixed now)

- **Candidates:** every NSE equity in Dhan's scrip master, series **EQ or BE** (≈ 2,950 names),
  daily bars `period="10y"`.
- **Membership:** at the last session of every **June and December** (NSE's semi-annual
  rebalance months), the **500 names with the highest median daily turnover (close × volume)
  over the previous 126 sessions**, among names with at least 260 sessions of history. That set
  is the universe for the next six months. Only data before the rebalance date is used.
- **Residual bias, stated now:** companies delisted before today (mergers, insolvencies) are not
  in the scrip master and cannot be included. Turnover is a proxy for NSE's free-float
  market-cap rule, not the rule itself.

## Variants re-run inside that universe (rules otherwise unchanged)

| ID | Variant | Change |
|---|---|---|
| B1 | Nifty 500 index | none (the real index is already survivorship-free) |
| B2 | Equal-weight universe | equal weight across the point-in-time members |
| B3 | Momentum-30 replica | its top-200-by-turnover pool drawn from the point-in-time members |
| V2 | Rank → portfolio | eligibility requires point-in-time membership |
| **P1** | **Stocks on the Move (the v2 core)** | eligibility requires point-in-time membership |
| P1E | ensemble (descriptive only — P1E is judged forward, never on this) | same |

C (the trigger proxy) is NOT re-run: its PA signals were computed on today's list only.

## Pass rule (P1)

Period and halves as the tournament (2018-06-01 .. 2022-07-31 / 2022-08-01 .. 2026-10-16).
**P1 SURVIVES** if, in **both** halves, its MAR is above B1's and B3's, and its full-period CAGR is
above B1's.

## Decision

- SURVIVES → the tournament's conclusion stands; P1/P1E stay the v2 core under Doc 40's gates.
- DOES NOT SURVIVE → the edge was largely survivorship; no real money goes into the v2 core
  without a new design, and Doc 40 is revised. The honest default becomes the momentum ETF.
- One run.
