# PRE-REGISTRATION — does a fundamental floor help the v2 core (P1, Stocks on the Move)?

**Registered:** 16 Oct 2026 (IST), before any result with the floor was computed.
**Owner:** Jay ("we definitely do not want to go with the fundamentally weak ones").
**Script:** `pro_systems_backtest.py --floor` (committed with this file).

## Question

P1 won the tournament on price alone (no point-in-time fundamentals existed for 2018–2026).
Does refusing fundamentally weak names keep P1's result (or improve it)?

## Data and definitions (fixed now)

- **Fundamentals, point-in-time:** `screener_history.rff_pit` — screener.in's own history tables,
  a period counted only after it was published (quarter + 45 days, annual + 60 days). Five
  checks: TTM net income > 0, free cash flow > 0, interest cover > 3.5, debt/equity < 2,
  ROA > 5 %. Usable ("OK", ≥ 4 checks known) from **June 2024** — before that the quarterly
  table is too short. Current ratio cannot be rebuilt (stated in the module).
- **Weak** = quality OK and **2 or fewer** checks passed. A name whose read is not OK is NOT
  excluded — missing data is a judgement about our data, not about the company.
- **P1F** = P1 exactly, plus: a weak name is ineligible (not bought; a holding that turns weak
  after new results is sold at the weekly rebalance like any ineligible holding).
- **Window:** 2024-06-03 .. 2026-10-16, both P1 and P1F started fresh on 2024-06-03 with the
  same panel, costs (0.25 % per side) and rules. Index = Nifty 500.

## Hypothesis (non-inferiority — the floor is a risk preference, it only has to not cost much)

- **H:** MAR(P1F) ≥ 0.90 × MAR(P1) **and** CAGR(P1F) ≥ CAGR(P1) − 2.0 pp.

## Decision rule

- H passes → **P1F is the live primary** paper portfolio; P1 runs beside it as the control.
- H fails → **P1 is the primary**; P1F still runs beside it on paper, and the comparison is
  re-read forward after 6 months (a new pre-registration).

## Discipline

- One run. The P1 numbers for this window are new (the tournament reported 2018–2026 halves,
  not this window), and P1F has never been run. Known limits: a 2.4-year window (one market
  cycle at most); survivorship from today's list (equal for both); screener restatements.

## RESULT (16 Oct 2026, run once) — H FAIL (narrowly) → P1 is the primary, P1F runs beside it

| 2024-06-03 .. 2026-10-16 | CAGR | max DD | MAR | Sharpe | trades |
|---|---|---|---|---|---|
| P1 (price only) | 2.68 % | −17.28 % | 0.16 | 0.26 | 855 |
| P1F (fundamental floor) | 2.19 % | −17.10 % | 0.13 | 0.23 | 921 |
| Nifty 500 | 0.91 % | −18.84 % | 0.05 | 0.14 | – |

MAR(P1F) 0.13 < 0.90 × 0.16 = 0.144 → FAIL by a hair; the CAGR condition (−0.49 pp vs −2.0) held.
Both portfolios beat the index in a weak window. Forward re-read of P1 vs P1F after 6 months.
Output: `reports/p1_floor_result_20261016.txt`.
