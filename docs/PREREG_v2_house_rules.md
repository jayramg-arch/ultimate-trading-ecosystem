# PREREG · v2 house rules (V2H) and the disaster stop (P1ES) — 18 Oct 2026

Written BEFORE any result below exists. Jay's answers to Doc 41's open questions (18 Oct 2026)
become a "house" version of the v2 system. P1E stays exactly as registered (pure Clenow,
ensemble) so the house rules can be measured against it.

## The books

| Book | Rules | Role |
|---|---|---|
| P1E | as registered (PREREG_p1e_ensemble_forward) | pure reference |
| **P1ES** | P1E + a resting disaster stop (below) | answers Q5 on its own |
| **V2H** | P1E + every house rule below | the v2 candidate for real money |

## The house rules (V2H), fixed now

1. **Universe** — Nifty 500 stocks (live) / the point-in-time top 500 by turnover (backtest).
   **F&O priority:** inside the top-25 % cut, F&O names are bought first (in rank order), then
   the rest. Exits are unchanged. Live F&O list = the latest date in `data/fno_history.csv`;
   backtest proxy = the 210 most-traded members at each June/December rebalance (point-in-time
   F&O history only starts Jul-2024; eligibility is largely size- and liquidity-driven).
2. **Wednesday rebalance** — orders are decided at the close of the session before the week's
   first session on or after Wednesday (normally Tuesday) and filled at that next open.
3. **House exposure tiers** on top of the 200-day SMA. New Indian-equity buys need the Nifty 500
   above its 200-day SMA **and** a regime score of 3+. Score 3–5 (NEUTRAL): risk per position
   halved (0.05 % of equity per ATR20) and Indian-equity exposure capped at 70 % of equity.
   Score 6+ (OPEN): full rules. Thresholds are imported from `house_policy.EXPOSURE_TIERS`.
   NOT applied, on purpose: the 3-new-entries-a-week limit (it would take ten weeks to build a
   30-name portfolio), the pilot entries and the circuit breaker (built for discretionary
   trades; weekly rotation produces many small losing exits by design). Exits are never forced
   by the tier. **Backtest score:** rebuilt with `market_regime`'s own components — breadth of the
   point-in-time members above their 200-day (+3) and 50-day (+2) SMAs, distribution days (+2),
   no death cross (+1), follow-through day (+1), breadth thrust from member advances/declines (+1).
   The live V2H book uses the same reconstruction on the Nifty 500, so paper and backtest cannot drift.
4. **Disaster stop** (also P1ES) — at each fill: entry − 4 × ATR14 (daily, the house positional
   floor), resting; hit when the day's low touches it, filled at the lower of the open and the stop.
   It never trails. A stopped name may be bought again at a later rebalance if it re-qualifies.
5. **Tax-aware runners + partial profits** — a holding that is in profit and has been held 300–364
   days stays while it is inside the top 50 % (instead of 25 %), so it can cross the one-year mark
   (LTCG 12.5 % instead of STCG 20 %). Every fourth rebalance (≈ monthly), a holding whose risk
   (shares × ATR20) has grown above 1.5 × the target risk (0.10 % of equity) is trimmed back to the
   target — Clenow's position rebalance, one way only; it books part of a runner when its
   volatility balloons.
6. **ETF sleeve** — ETFs never compete with stocks in one rank. Pool: the curated tradeable ETFs in
   `etf_universe.ETF_UNIVERSE` (no DEBT), one per underlying (the most traded), median turnover
   ≥ ₹2 crore, the same data-quality screen as the stocks (GOLDIETF's series is corrupt → GOLDBEES
   stands in). Rank = the same ensemble trend-quality score, as a percentile **within the ETF pool**.
   Hold the top 25 % (at least 2, at most 5); same eligibility (above the 100-DMA, no 15 % day).
   Regime: Indian-equity ETFs (broad, sector, smart beta, thematic) follow the stock rules and
   tiers; gold, silver and international ETFs follow only their own trend (close above their own
   200-day SMA). Size: 0.10 % of equity per ATR20, at most 10 % of equity per ETF and 30 % for the
   sleeve. ETFs are bought after the stocks, from the cash the stocks leave.

Not testable in history and live-only: the reviewer's deferral (V2H skips a buy the reviewer rules
WAIT or PASS; the name is reconsidered at the next rebalance).

## The one backtest run

Survivorship panel (`data/surv_panel.pkl`), 2018-06-01 .. 2026-10-16, halves split 2022-08-01,
costs 0.25 % a side, ETFs removed from the STOCK pool for every book in this run (so P1E here will
not equal the 17-Oct figure, which ranked a few ETFs as stocks). Equivalence check first: this
engine with every house flag off must reproduce `pro_systems_backtest.run_sys` P1E on the same pool.

- **H1 (Q5 — the stop):** MAR(P1ES) ≥ MAR(P1E) − 0.10 in BOTH halves → the stop is affordable.
  Either way Jay trades with stops; a FAIL sets the live expectation on P1ES's numbers.
- **H2 (the house book):** V2H's MAR beats the Nifty 500 and the Momentum-30 replica in BOTH halves,
  **and** MAR(V2H) ≥ MAR(P1E) − 0.15 in BOTH halves → V2H is the v2 candidate for real money.
  FAIL → the single-rule ablations below show which rule costs; the choice goes back to Jay and
  P1E stays the candidate meanwhile.
- **Descriptive only (no pass/fail):** single-rule ablations (P1E + Wednesday / + tiers / + F&O /
  + tax-and-trim / + ETF sleeve); an after-tax CAGR estimate (FY netting, STCG 20 %, LTCG 12.5 %,
  losses carried forward, today's rates throughout, no exemption); trades a year; median holding
  days; share of realised gains that were long-term; the ETF sleeve's average weight.
- One run. Thresholds above are judgement calls fixed now; nothing is re-tuned after the result.

## Forward

P1ES starts with P1E (its 16 Oct close decision; both in cash). V2H's first decision is the close
of Tue 20 Oct 2026. Both are read with P1E on 16 Jan 2027 (three months) and 16 Apr 2027.
Doc 40's real-money gates apply to whichever book is the candidate.
