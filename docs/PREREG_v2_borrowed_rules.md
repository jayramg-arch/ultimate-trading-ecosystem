# PREREG · v1 rules borrowed into v2 (18 Oct 2026)

Jay (18 Oct): borrow the useful v1 rules into v2 instead of building v2 from scratch. Written
BEFORE any result below exists. Baseline = the live V2H book (P1E + Wednesday rebalance + 4 × ATR14
disaster stop + tax-aware runners and risk trims + ETF sleeve; PREREG_v2_house_rules Amendment 1).

## Group A — protective plumbing, borrowed as is (no edge claimed, live only, not tested)

| v1 rule | where it lives in v1 | in V2H |
|---|---|---|
| NAV premium gate (3 %) | `etf_inav` | ETF out of the pool (Amendment 2) |
| ETF liquidity floor | `etf_quality` | ≥ ₹2 crore median turnover |
| Earnings inside the hold window | `earnings_calendar` (pyramid TRIM rung, reviewer) | a BUY is deferred one rebalance when results are due within 7 calendar days of the fill; unknown date never blocks |
| Stale data never reads as a decision | `data_provider` As_Of / Stale_Data, cache-poisoning fix | a held name with no bar on the decision date is kept and flagged, never sold on a missing price |
| NSE holiday calendar | `nse_calendar` | schedule and fills |
| Reviewer as an execution check | `s4_review` | one-week deferral on WAIT / PASS |

At go-live (not before), the v1 operating rules also apply to real v2 positions: journal rows with
Timeframe = Positional and setup = V2, the disaster stop as the journal's initial and Dhan stop,
one stop price per holding with full share cover and limit below trigger, Risk Shield and the
16:30 journal sync.

## Group B — v1 rules that change what v2 holds (tested here, once)

Each is added to the baseline ON ITS OWN:

| # | v1 rule | constant (imported, never copied) | in the test |
|---|---|---|---|
| B1 | sector cap | `house_policy.SECTOR_CAP_PCT` (25 %) | skip a buy that takes its sector above 25 % of equity (sector from `sector_lookup`; unknown = no cap) |
| B2 | correlation block | `sniper_trigger.CORRELATION_BLOCK` (0.90) | skip a buy whose 250-session daily-return correlation with any holding exceeds 0.90 |
| B3 | first test: no Stage 3/4 | `bull_screener.compute_weekly_stage_and_wks` (the 2×2 shared by S4/v67/GM) | only weekly Stage 1 or 2 is eligible (last confirmed week), so a Stage 3/4 holding drops out and is sold |
| B4 | per-trade cap | `house_policy.MAX_ALLOC_DEFAULT / CAPITAL_DEFAULT` (₹1 lakh of ₹30 lakh = 3.33 %) | no position larger than 3.33 % of equity at entry |
| B5 | open-risk budget | `house_policy.HEAT_BUDGET_PCT["OPEN"]` (6 %) | skip a buy that takes Σ shares × (price − stop) above 6 % of equity |
| B6 | max open positions | `house_policy.MAX_OPEN_POSITIONS` (25) | no new buy once 25 positions are held |
| B7 | house trailing stop | `house_policy.CHANDELIER_MULT` POS 4.5, 22-bar window, entry-anchored | the static disaster stop also trails up: highest close since entry (22-bar window) − 4.5 × ATR22, tighten only |

**Decision rule (per rule):** ADOPT if MAR(baseline + rule) ≥ MAR(baseline) − 0.05 in BOTH halves
(a protective rule may cost a little); otherwise REJECT. Max drawdown and Sharpe are reported
beside it. The adopted rules are then run TOGETHER once, descriptively, to check for interactions;
if the combination's MAR in either half falls more than 0.10 below the baseline, only the single
best adopted rule is kept and the rest go back to Jay.

Same panel, windows, costs and stock pool as PREREG_v2_house_rules. One run. B5 and B7 need the
stop, which the baseline has.

## Group C — v1 rules not borrowed (already measured, or not applicable)

- Exposure tiers, F&O priority, fundamental floors (RFF/BFF): tested for v2, rejected.
- S4 GO / PA patterns / zones / bar and volume gates: entry timing — five tests found no edge; v2
  does not time entries.
- Recovery path, Wyckoff, base rates: selection tools for the trigger system, not for a ranked book.

## RESULT (18 Oct 2026, run once) — four adopted, three rejected; the combination holds

| book | CAGR | max DD | MAR | MAR H1 | MAR H2 | after-tax CAGR | trades / yr | verdict |
|---|---|---|---|---|---|---|---|---|
| V2H baseline | 16.78 % | −20.75 % | 0.81 | 0.71 | 1.05 | 14.91 % | 378 | – |
| B1 sector cap 25 % | 17.79 % | −20.93 % | 0.85 | 0.74 | 1.12 | 15.92 % | 375 | ADOPT |
| B2 correlation > 0.90 | 16.68 % | −20.75 % | 0.80 | 0.71 | 1.04 | 14.79 % | 377 | ADOPT |
| B3 Stage 1/2 only | 16.60 % | −24.22 % | 0.69 | 0.52 | 1.17 | 14.84 % | 473 | REJECT |
| B4 per-trade cap 3.33 % | 17.88 % | −19.94 % | 0.90 | 0.76 | 1.11 | 16.01 % | 400 | ADOPT |
| B5 open-risk budget 6 % | 4.91 % | −11.19 % | 0.44 | 0.28 | 1.15 | 4.21 % | 86 | REJECT |
| B6 max 25 positions | 13.60 % | −19.68 % | 0.69 | 0.52 | 1.34 | 12.05 % | 245 | REJECT |
| B7 house Chandelier trail | 15.94 % | −19.78 % | 0.81 | 0.66 | 1.09 | 14.13 % | 447 | ADOPT (at the boundary) |
| **combined B1+B2+B4+B7** | **17.34 %** | **−20.08 %** | **0.86** | **0.74** | **1.12** | **15.51 %** | 477 | holds |

- Sector names were known for 592 of 981 historical names; the rest were uncapped, as registered.
- B2 almost never binds (two stocks rarely correlate above 0.90 on daily returns) — harmless.
- B3 churns: the weekly stage flips 2↔3 on flat averages, which sells names the rank still holds.
- B5 and B6 starve the book (at 0.10 % per ATR with a 4 × ATR stop each position risks ~0.4 %, so a
  6 % budget allows ~15 names). Those two house limits were sized for the discretionary book; how
  they apply to real v2 money is Jay's call (Doc 41).
- Per the rule, B1, B2, B4 and B7 join the live V2H (`v2_house.V2H_LIVE`) before its first decision.
Output: `reports/v2_house/borrowed_metrics.csv`, `reports/v2_borrowed_result_20261018.txt`.

## AMENDMENT 1 (18 Oct 2026, before any run of it) — B8 pyramid top-up (Jay: "why don't we pyramid?")

**B8:** every fourth rebalance (the trim days), a v2 holding still inside the top-25 % cut whose
risk (shares × ATR20) has fallen below **half** the target risk (0.10 % of equity) is topped back
up to the target — the other half of Clenow's two-way position rebalance (v2 so far only trims).
The add is sized off today's ATR, keeps the position's entry date (tax lot simplified), obeys the
per-trade cap and the sector cap, and is paid from cash only after the week's new buys.
**Baseline:** the live V2H (`V2H_LIVE`, with the four adopted rules). **Decision rule — stricter
than B1–B7, because this adds complexity rather than protection:** ADOPT only if MAR(V2H + B8) ≥
MAR(V2H) in BOTH halves; otherwise REJECT. One run.

**A name the CURRENT system holds** (not tested — routing, live only): the real v2 book does not
open a second position in it (one owner per holding: one stop price, one journal row, one exit
rule); the v2 pick is reported on the order sheet as a confirmation for the current system's
pyramid ladder (its rung from `FINAL_Portfolio_Picks.csv`), and the v2 money goes to the next name.

### RESULT of Amendment 1 (18 Oct 2026, run once) — B8 ADOPT by the letter; it almost never acts

| book | CAGR | max DD | MAR | MAR H1 | MAR H2 | after-tax CAGR | trades / yr |
|---|---|---|---|---|---|---|---|
| V2H live | 17.34 % | −20.08 % | 0.86 | 0.74 | 1.12 | 15.51 % | 477.2 |
| V2H live + B8 | 17.34 % | −20.09 % | 0.86 | 0.74 | 1.12 | 15.51 % | 478.3 |

MAR equal in both halves → ADOPT under the rule, but B8 fires about once a year: under equal-risk
sizing a winner's rupee size already grows with its price (its ATR grows with it), so a holding
only drops below half its target risk when its volatility collapses. The live V2H carries it
(`V2H_LIVE`, topup); it changes nothing measurable. Output: `reports/v2_b8_result_20261018.txt`.
