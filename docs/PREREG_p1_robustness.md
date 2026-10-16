# PRE-REGISTRATION — is P1 a plateau or a lucky peak? (robustness neighbourhood)

**Registered:** 16 Oct 2026 (IST), before any neighbour was run.
**Owner:** Jay. **Script:** `pro_systems_backtest.py --robust` (committed with this file).

## Question

The tournament tested ONE setting of Stocks on the Move: 90-session regression, sell outside the
top 20 %, 0.10 % of equity per ATR. If the result is real, nearby settings must do almost as
well. If only this exact setting works, it was luck and P1 must not get real money.

## The grid (fixed now — 27 configurations, P1 is the centre)

| parameter | values |
|---|---|
| regression lookback (sessions) | 60 · **90** · 120 |
| rank cut-off (sell outside, buy within) | top 10 % · **20 %** · 30 % |
| risk per position (% of equity per ATR20) | 0.05 % · **0.10 %** · 0.20 % |

Everything else exactly as the tournament: panel, costs 0.25 %/side, regime gate (Nifty 500 >
200-day SMA for new buys), SMA100 and 15 %-gap eligibility, weekly cadence, halves H1
2018-06-01 .. 2022-07-31 / H2 2022-08-01 .. 2026-10-16. No other parameter is touched.

## Pass rule (a plateau)

P1 is ROBUST only if all three hold:

1. **Beats the plain alternatives:** at least 21 of the 26 neighbours (≈ 80 %) have a full-period
   MAR above the Momentum-30 replica's (0.48) AND a CAGR above the Nifty 500's (11.05 %).
2. **No cliff:** in **each** half, the median MAR of the 26 neighbours is at least 0.70 × P1's
   MAR in that half (H1 0.70 × 1.00 = 0.70; H2 0.70 × 1.43 = 1.00).
3. **Not a spike:** P1's full-period MAR is not more than 1.30 × the neighbours' median.

## Decision

- ROBUST → P1 is cleared for real money under the transition plan (Doc 40), subject to its
  other gates (three months of paper, the regime).
- NOT ROBUST → P1 stays paper-only; the neighbourhood is reported and a new pre-registration is
  needed before any money.
- The grid is a check, not a search: the best-scoring neighbour is NOT adopted. P1 stays at
  90 / 20 % / 0.10 % whatever the grid shows.

## RESULT (16 Oct 2026, run once) — P1 is NOT ROBUST (passes 1, fails 2 and 3)

- **1. Beats the plain alternatives:** 22 of 26 neighbours beat the Momentum-30 replica's MAR and
  the Nifty 500's CAGR (need 21) — **pass**. The approach itself is broadly sound.
- **2. No cliff:** neighbour median MAR H1 **0.58** (needed 0.70) — **fail**; H2 1.30 (needed 1.00) — pass.
- **3. Not a spike:** P1's MAR 1.16 vs 1.30 × neighbour median 0.76 = 0.99 — **fail**.

Full grid: `reports/pro_systems/robustness.csv`, `reports/p1_robustness_result_20261016.txt`.
Where the weakness sits: risk 0.05 % per ATR (positions too small, mostly cash: MAR 0.14–0.77)
and the tight 10 % cut-off (heavy churn), mostly in 2018–22. Settings around 20–30 % cut-off and
0.10–0.20 % risk hold MAR 0.8–1.15.

**Reading:** P1's 1.16 is an optimistic point estimate; ~0.75 (the neighbour median) is the
honest expectation — still above the Momentum-30 replica (0.48) and the Nifty 500 (0.29).
**Decision per the rule:** P1 stays paper-only; real money needs a NEW pre-registration
(forward, not on this grid). The best neighbour is not adopted.
