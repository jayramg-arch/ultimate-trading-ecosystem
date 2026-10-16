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

## RESULT (17 Oct 2026, run once) — P1 SURVIVES the survivorship correction

Universe built from 2,423 NSE EQ/BE names with history; 1,013 different names were members at
some point. Point-in-time members that are ALSO in today's Nifty 500: 282 of 500 in Jul-2018,
312 (2020), 327 (2022), 372 (2024), 378 (2026) — the size of the bias the earlier tests carried.

| variant | CAGR full | max DD | MAR full | MAR H1 | MAR H2 | Sharpe |
|---|---|---|---|---|---|---|
| **P1 (v2 core)** | **19.33 %** | **−22.35 %** | **0.86** | **0.68** | **1.17** | 1.06 |
| P1E ensemble (descriptive) | 20.43 % | −21.81 % | 0.94 | 0.75 | 1.29 | 1.11 |
| V2 rank → portfolio | 17.02 % | −37.84 % | 0.45 | 0.40 | 0.65 | 0.87 |
| B3 Momentum-30 replica | 16.32 % | −41.28 % | 0.40 | 0.42 | 0.50 | 0.84 |
| B1 Nifty 500 | 11.05 % | −38.30 % | 0.29 | 0.31 | 0.54 | 0.71 |

- Verdict per the rule: P1's MAR beats B1 and B3 in both halves, CAGR beats B1 → **SURVIVES**.
- vs today's-list results: P1 CAGR 21.9 → 19.3 %, MAR 1.16 → 0.86. Survivorship was worth about
  2.5 pp a year and 0.3 of MAR; the edge over the benchmarks remains.
- **Data-quality note (after the run, does not change the verdict):** the B2 line in the run
  (302 % CAGR) was garbage — NV20 (an ETF in the EQ series) has a price series flipping ~1,000×.
  Rerun with every series having ≥ 3 days beyond ±50 % removed (GOLDIETF, NV20, PATANJALI,
  THOMASCOOK): **P1 19.49 % / −22.65 % / MAR 0.86 (0.66 / 1.18)** — unaffected; B3 0.39; **B2
  (equal-weight, point-in-time) 13.89 % / −52.86 % / MAR 0.26**. On today's list the same
  benchmark had shown 22.11 % — the plainest measure of the survivorship bias.
Output: `reports/survivorship/`, `reports/survivorship_result_20261017.txt`.
