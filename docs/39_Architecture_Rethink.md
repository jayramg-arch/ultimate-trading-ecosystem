# 39 · Architecture rethink — from "the perfect entry" to "own the strongest stocks" (16 Oct 2026)

## What the evidence says about the system we built

| Layer | Effort spent | Measured edge |
|---|---|---|
| Qualification (stage, catalyst, trend template, RS) | moderate | **the only positive one**: about +1% a trade vs the index historically, CI includes zero |
| Entry timing (S4 GO, PA battery, zones, AVWAP, OI, footprint, S5) | **most of the build** | none in five tests (entry optimizer A–D, S4-GO replay, PA-selects, P-less, live GO vs non-GO) |
| AI reviewer | large | none: TAKE ≈ WAIT ≈ PASS on 10-session returns |
| Stops and exits | large | the 4×ATR floor and Chandelier trail are right; tight stops were the main leak |
| Regime / exposure rule | recent | keeps you out of falling tapes — it would have cut 52 trades to about 7 |
| Portfolio construction (what to own, how much, when to swap) | **almost none** | never built |

The architecture is **trigger-centric**: it asks "is this the right moment to buy this name?"
and answers with ever more metrics. Serious systematic equity managers ask a different question:
"of everything I could own, which 10–20 are strongest right now, and is the market letting me be
invested?" Their edge comes from *what they own and how much*, not from the minute they buy —
which is exactly what our five timing tests found.

## Why "more gates" was never going to work

You noticed it: dozens of metrics, four gates. Gates are binary — a name either passes or does
not, and everything the metric knew about *how much* better one name is than another is thrown
away. Adding gates makes the funnel narrower and the sample smaller, which is how systems get
overfit. The professional answer is a **ranking**: combine the few metrics that have evidence
behind them into one score across the *whole* universe, and own the top of the list.

One caution from our own work (Doc 36): inside a pre-selected list of momentum names, no metric
ranked future returns. Ranking works across a broad universe, not within a list that has already
been filtered to look alike. That is a reason to rank the whole Nifty 500, not the 50-name board.

## Benchmarks — what we have been competing against without measuring

| Benchmark | What it is | Why it matters |
|---|---|---|
| Nifty 500 | the market | the floor: if we cannot beat it after costs, we are paying to underperform |
| **Nifty 200 Momentum 30** (and its ETFs) | 30 strongest stocks by 6- and 12-month momentum, rebalanced twice a year, no timing | the honest competitor: a passive version of what we are trying to do |
| Minervini / O'Neil practice | market direction first, leaders by RS rank, earnings acceleration, cut losers, let winners run, concentrate | the discretionary standard our DNA is based on |
| Trend-following overlay (dual momentum) | be invested only when the index trend is up | what our exposure rule now does |

Last year every one of them lost money (Nifty 500 −5.5%, Nifty 50 −9.5%, Momentum 30 −8.3%).
That does not excuse the system — it sets the bar it must clear over a full cycle.

## What is missing (the parts serious systems have and we do not)

1. **A portfolio layer.** Rank, hold the top N, swap the weakest for the strongest on a schedule.
   Your Sell-to-Buy rotation matrix is in the DNA and was never built.
2. **A cross-sectional strength rank.** We use the RRG quadrant (a rotation picture) where the
   evidence supports a percentile rank of 6- and 12-month risk-adjusted return across the
   universe (IBD's RS rating, the momentum index's method).
3. **Earnings momentum as an input.** Post-earnings drift and earnings acceleration are among
   the most robust effects in equities; our earnings data is display-only (BFF) or a risk flag.
4. **A benchmark comparison in every report.** Paper Trades, the Live Record and the journal
   report R and rupees, never "vs Nifty 500" and "vs Momentum 30".
5. **A schedule.** Positional systems rebalance weekly or monthly; ours reacts to 75-minute bars.

## The proposed architecture (v2): rank → portfolio → execute

| Layer | Job | What it reuses |
|---|---|---|
| L0 Regime | how much to be invested (100% / 50% / mostly cash) | the exposure rule, as is |
| L1 Eligibility | a few coarse yes/no filters: Stage 2, above a rising 200-DMA, liquidity, a fundamentals floor | stage engine, BFF/RFF, liquidity |
| **L2 Rank** (new) | one score across all eligible Nifty 500 names: vol-adjusted 6/12-month momentum, earnings growth and acceleration, distance from the 52-week high, trend quality | existing data; new combination |
| **L3 Portfolio** (new) | hold the top 10–15, sector cap, equal risk; each week swap a holding that falls out of the top 30 or breaks trend for the best name not held | sector map, correlation gate, heat budget |
| L4 Execution | buy the chosen names during the rebalance week at a sensible price (pullback limit, no chasing) | GM / S4 as an execution assistant, not a gate |
| Exits | rank exit + 4×ATR stop + Chandelier trail | house stop rules, as is |

The board, S4, S5 and the reviewer do not disappear: they become the *execution and checking*
tools for names the rank has already chosen, instead of the thing that chooses them.

## How we find out before you risk money (pre-registered, run once)

A point-in-time rotation backtest, Nifty 500, 2018–2026, weekly rebalance, real costs,
compared with: (a) the Nifty 500, (b) a replica of the Momentum 30 method on the same data,
(c) today's system. Pass only if v2 beats both benchmarks on return per unit of drawdown in both
halves of the period. **If v2 cannot beat a plain momentum replica, the honest conclusion is to
own the momentum ETF and stop building** — that would also be a result.

Known limit stated now: today's Nifty 500 list on an older window flatters every variant
(survivorship), equally; the comparison between variants is what counts.

## What to stop doing

- Adding panel fields, gates and patterns to S4/S5 in search of an edge in the entry.
- Reading a reviewer TAKE as a signal.
- Judging the system on 10-session trade outcomes instead of on the portfolio against a benchmark.
