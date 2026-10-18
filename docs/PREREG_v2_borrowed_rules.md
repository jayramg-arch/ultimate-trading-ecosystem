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
