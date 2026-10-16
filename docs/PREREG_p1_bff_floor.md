# PRE-REGISTRATION — the growth (BFF) floor on the v2 core, 2018–2026

**Registered:** 16 Oct 2026 (IST), before any result with the floor was computed.
**Owner:** Jay. **Script:** `pro_systems_backtest.py --bff` (committed with this file).

## Background

`fundamental_replay.bff_as_of` had been dead (it called a function a later commit removed).
Rebuilt as `screener_history.bff_fields` / `as_of`: the five BFF checks point-in-time from
screener.in's history tables. Parity with the live BFF today: **90 % of individual checks
agree** (141/156 on 35 names; scores mostly within one). Differences: ROCE is computed
(PBT + interest over average capital employed) where the live page shows screener's own, and
the 45/60-day publication lag that a live page does not apply.

The **annual** basis (latest published financial year vs the one before; OPM; ROCE; net profit
> 0) reaches back to 2018, so this test uses the full tournament window and both halves. The
TTM basis needs 8 published quarters and exists only from ~May 2025.

## Variants (fixed now)

- **P1** — the v2 core exactly as in the tournament (reference; its halves are already known).
- **P1G** — P1, but a name whose annual BFF reads **WEAK** (score 0–1 of 5, quality not
  INSUFFICIENT) is ineligible. Financials use the lender branch (no OPM; ROCE > 10).
- **P1S** — P1, but only names whose annual BFF is **STRONG** (score ≥ 4) are eligible; a name
  with no score is kept (missing data is not a verdict on the company).
- Same panel, costs, calendar and rules as `PREREG_pro_systems_tournament.md`; halves H1
  2018-06-01 .. 2022-07-31, H2 2022-08-01 .. 2026-10-16.

## Hypotheses (non-inferiority — the floor is Jay's risk preference; it only must not cost)

- **H1 (weak-floor):** in **both** halves, MAR(P1G) ≥ 0.90 × MAR(P1) and CAGR(P1G) ≥ CAGR(P1) − 2.0 pp.
- **H2 (strong-only):** the same test for P1S.

## Decision

- H1 passes → **P1G replaces P1 as the live primary** (the paper books become P1G primary,
  P1 control). If H2 also passes and P1S has the higher MAR in both halves, P1S is the primary.
- Neither passes → P1 stays primary; the floors stay on paper only as P1F (RFF) beside it.
- One run; no re-tuning of thresholds after seeing results.
