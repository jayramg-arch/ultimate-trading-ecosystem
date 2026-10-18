# 41 · The v2 System — design (17 Oct 2026, living document)

> Status: **paper trading**, built beside the current system. Jay's decision (17 Oct): both systems
> run in parallel — the current one keeps monitoring trades, its reviewer and its paper record; v2
> is designed and built now and fine-tuned as the P1E results come in. Comments welcome on every
> section — the open questions at the end are where Jay's input decides the direction.

## 1. What v2 is, in one paragraph

A **weekly ranked portfolio** of NSE stocks, based on Andreas Clenow's *Stocks on the Move*.
Once a week it ranks every eligible stock by the *quality* of its trend, holds the strongest,
sizes each position so all carry the same risk, sells what drops out of the top of the ranking,
and stops buying altogether when the market itself is in a downtrend. It does not try to time
the perfect entry — five tests showed that timing adds nothing here — it decides *what to own
and how much*.

## 2. The two systems side by side

| | Current system | v2 system |
|---|---|---|
| Question it answers | is this the right moment to buy this name? | which stocks should I own this week, and how much? |
| Selection | watchlists + board gates (location, volume, bar, fundamentals; PA as a tag) | rank of the whole eligible Nifty 500 by trend quality |
| Timing | S4 GO on 75m/125m/Daily, alerts | none — orders at the week's close, filled at the next open |
| Exits | Disaster SL, thesis close, Chandelier trail, targets | weekly: out of the top 25 % or no longer eligible |
| Sizing | 0.5 % / 0.75 % risk per trade at the plan stop | equal risk: 0.10 % of equity per ATR(20) |
| Market filter | exposure rule (regime score tiers) | Nifty 500 above its 200-day SMA for new buys |
| Reviewer | rules on every GO (TAKE / WAIT / PASS) | checks the week's buys for execution only |
| Paper record | ANALYSIS › 📄 PAPER · CURRENT SYSTEM | ANALYSIS › 🧭 PAPER · v2 SYSTEM |
| Evidence | timing layer: no measured edge (Docs 38–39) | tournament winner; survives survivorship correction (MAR 0.86) |

## 3. Architecture — the layers, in order

| Layer | Rule today | Why this rule | Evidence |
|---|---|---|---|
| **L0 Regime** | new buys only when the Nifty 500 closed the week above its 200-day SMA; holdings can stay | momentum strategies lose most in falling markets; staying out halves the drawdown | tournament; Clenow |
| **L1 Eligibility** | close above its 100-DMA · no single-day move over 15 % in 90 sessions · median daily turnover ≥ ₹5 crore · 260 sessions of history | only names already trending; gaps distort the trend measure; liquidity for real fills | tournament |
| **L2 Rank** | trend quality = annualised exponential-regression slope × R²; **ensemble**: percentile ranks at 60, 90 and 120 sessions, averaged | smooth climbers rank above jumpy ones; the ensemble removes the single-setting risk the robustness test exposed | PREREG_p1_robustness |
| **L3 Portfolio** | weekly: sell holdings outside the top **25 %** or no longer eligible; buy from the top while cash lasts | holding winners while they lead, swapping laggards for leaders — the Sell-to-Buy rotation in rule form | tournament |
| **L3 Sizing** | 0.10 % of equity ÷ ATR(20) per position (≈ 25–40 positions) | equal risk per name; volatile names get smaller positions | tournament; robustness grid |
| **L4 Execution** | orders at Friday's close, filled at Monday's open; the reviewer checks the buys | no timing edge was found, so execution is kept simple and cheap | Docs 38–39 |
| **Fundamentals** | displayed, never a filter | both floors tested cost return (RFF −0.5 pp; BFF −6.4 pp/yr in 2018–22) | PREREG_p1_*_floor |

## 4. The books (the v2 paper-trading instance)

| Book | What it is | Role |
|---|---|---|
| **P1E** | the rules above | **the v2 system** |
| **P1ER** | P1E, but a buy is skipped when the reviewer rules WAIT or PASS on it | measures what the reviewer adds |
| **P1ES** | P1E + a resting 4 × ATR14 disaster stop (18 Oct) | answers Q5: what the stop costs |
| **V2H** | P1E + Wednesday rebalance + the stop + tax-aware runners + ETF sleeve (18 Oct, §9) | the house version |
| P1 | single setting (90 sessions, top 20 %) — the tournament winner | research control |
| P1F | P1 + point-in-time fundamental floor | research control |

All start at ₹30,00,000 on the 16 Oct 2026 close. Every Friday (V2H: every Tuesday): orders
decided, a Telegram summary, the buys queued on the reviewer (tagged `v2`), and
`reports/p1_paper/orders_<date>.md`. Engine for P1ES/V2H: `v2_house.py` (one `decide()` for the
backtest and the paper book).

## 5. Data flow and schedule

1. Nightly (auto-pilot **Phase 12i**): `p1_paper.py` loads two years of daily bars for the Nifty 500,
   fills last week's orders at the open (Monday), marks every book at each close, writes the
   rank board `data/v2/board.csv`.
2. On a week's last close: decides the next orders for every book, writes the order list, sends the
   Telegram summary, and posts P1E's buys to the receiver as `SYMBOL S4 GO D - v2`.
3. The reviewer reads the S4/S5 panels for each name on the Daily chart and gets a **V2 CONTEXT**
   block: the selection is done, judge execution only (extension, earnings in the next 5 sessions,
   a wall within 1 ATR, gaps, illiquidity). Rulings land in the Reviewer Log with source `v2`.
4. Monday's open: P1E buys everything; P1ER skips the names ruled WAIT/PASS.
5. The v2 page shows the board, books, orders + reviews, positions and the trade blotter.

Code: `p1_paper.py` (engine), `pro_systems_backtest.p1_weekly` (the rules — the same function the
backtests ran, so paper and backtest cannot drift), `v2_core.py` (board, reviewer context, review
lookups), `commander_pages/v2_system.py` (the page).

## 6. What we expect (honest numbers)

Survivorship-corrected backtest, 2018–2026, costs included: **CAGR ~19 %, worst drawdown ~22 %,
return ÷ drawdown ~0.86** (P1); the robustness grid says to plan on **~0.75**. The ensemble P1E read
0.94 on the same data but is judged forward only. Benchmarks: Nifty 500 0.29, Momentum-30 replica
0.40. Expect long spells in cash when the market is below its 200-day SMA — that is the rule
working, not failing.

## 7. How v2 gets fine-tuned (the rule for changes)

- Every change is a **pre-registered forward test**: a new paper book with the change, run beside
  P1E, judged on data after it starts. No tuning on data already seen.
- First reads: **16 Jan 2027** (three months) and **16 Apr 2027** (six months, scheduled).
- Candidate changes already on the list: the cut-off (20 % vs 25 % vs 30 %), a sector cap, a
  catastrophic stop (see Q5), Wednesday vs Friday rebalancing, and an earnings-momentum factor
  (point-in-time data now exists from 2024).

## 8. Open design questions — answered by Jay on 18 Oct (see §9 for what the test said)

1. **Universe.** Live v2 ranks today's Nifty 500. The survivorship test used the 500 most-traded
   NSE names point-in-time. Keep the Nifty 500, or rank the top 500 by turnover (adds names before
   they enter the index)?
2. **Capital split.** When both systems trade real money, how much goes to each? (Proposal: v2
   starts at one-third of trading capital per Doc 40; the current system keeps the rest.)
3. **Rebalance day.** Friday close → Monday open (today), or Wednesday as Clenow uses (avoids the
   Monday gap)?
4. **Market filter.** 200-day SMA only (tested), or also the house exposure tiers (untested for v2)?
5. **Stops.** v2 has no hard stop — exits are weekly. The DNA says ATR stops are mandatory. Options:
   (a) keep it as tested; (b) add a wide catastrophic stop (e.g. entry − 4 × ATR or −15 %) on the
   live book only; (c) test (b) as a forward paper book first. *(Recommendation: c.)*
6. **The reviewer's veto.** Advisory only (P1E ignores it, P1ER obeys it) until P1E vs P1ER shows
   whether it helps — agreed?
7. **Position count.** At 0.10 % risk per ATR the book holds ~25–40 names. Comfortable, or would
   you rather fewer, larger positions (higher risk per name)?
8. **Taxes.** The backtest ignores tax. Weekly rotation means most gains are short-term (20 % STCG).
   Should the live version prefer holding past one year where the rank is close (a tax-aware
   tie-break)?
9. **ETFs.** v2 ranks stocks only. Should sector/index ETFs compete in the same rank?

## 9. Jay's decisions (18 Oct 2026) and what the test said

Every answer became a rule in the house book **V2H**, pre-registered (PREREG_v2_house_rules) and
measured once on the survivorship panel (2018–2026) beside the pure P1E. Each rule was also added
to P1E on its own, so its cost is visible.

| # | Jay's decision | Rule in V2H | Effect alone (CAGR / MAR H1·H2) | Recommendation |
|---|---|---|---|---|
| 1 | Nifty 500, F&O names first | F&O names bought first inside the top-25 % cut | **−4.4 pp**, 0.46 · 0.88, DD −24.6 % | **dropped (Jay, 18 Oct)**; F&O is a tag on the board, and the review still reads OI |
| 2 | v2 at one-third of capital | Doc 40 staging | – | agreed |
| 3 | Wednesday rebalance | decide Tuesday's close, fill Wednesday's open | −0.6 pp, 0.72 · 1.19 | keep (within noise) |
| 4 | SMA200 alone too lenient | + house exposure tiers (score 3+, half risk and 70 % cap at 3–5) | **−4.7 pp**, 0.42 · 0.96, DD −23.7 % | **dropped (Jay, 18 Oct)** — it delayed re-entry and did not reduce the drawdown |
| 5 | no trading without stops | 4 × ATR14 resting disaster stop (book P1ES) | **−2.5 pp**, 0.58 · 0.99, DD −23.8 % | keep (Jay's rule); expect P1ES's numbers; a wider stop is worth one pre-registered check |
| 6 | reviewer veto? | V2H skips a WAIT/PASS buy for one week (live only) | measured forward by P1E vs P1ER | obey as a deferral until 16 Jan says otherwise |
| 7 | 0.10 % per ATR | unchanged | – | agreed |
| 8 | let profitable runners pass a year, partials OK | tax-hold band 300–364 days (top 50 %) + monthly risk trim at 1.5 × | −0.3 pp, 0.75 · 1.19 | keep, but it rarely acts: median hold is 49 days, LT gains ~1 % |
| 9 | ETFs too | ETF sleeve ranked within ETFs (below) | +0.3 pp, 0.79 · 1.23 | keep |

All rules together (V2H): 12.3 % CAGR, MAR 0.39 · 1.10 — the pre-registered test FAILED (H1 MAR not
above the Momentum-30 replica's 0.39). Almost all of the gap is rules 1 and 4. P1E stays the
candidate; P1ES and V2H run forward on paper as registered.

**Amended (Jay, 18 Oct):** V2H drops the tiers and F&O priority before its first decision. V2H is
now P1E + Wednesday + the stop + tax/trim + the ETF sleeve. Descriptive backtest (chosen after the
ablations, so not evidence): 16.8 % CAGR, max DD −20.8 %, MAR 0.71 · 1.05 (registered V2H 12.3 %,
0.39 · 1.10; P1E 19.6 %, 0.78 · 1.21). Judged forward only.

### How stocks and ETFs are ranked (Q9)

- **Never in one rank.** An ETF is a basket, so its trend is smoother (higher R²) and its ATR lower:
  in a joint rank ETFs would crowd the top in calm markets and equal-risk sizing would make them
  2–3× larger than a stock. An Indian index ETF also duplicates the stocks already ranked.
- **Two pools, one score.** The same ensemble trend-quality score, as a percentile *within* its own
  pool. ETF pool: the curated tradeable list (`etf_universe`, no debt), one per underlying (the most
  traded), median turnover ≥ ₹2 crore; above the 100-DMA; no 15 % single-day move in 90 sessions.
- **Hold** the top 25 % of eligible ETFs (at least 2, at most 5), ≤ 10 % of equity each, ≤ 30 % in all,
  bought after the stocks from the cash they leave.
- **Regime per asset class.** Indian-equity ETFs follow the stock rules; gold, silver and
  international ETFs follow only their own trend (close above their own 200-day SMA). This is what
  lets the book hold something useful while Indian equities are in a downtrend.
- Today (16 Oct): 4 ETFs eligible; only **MAFANG** (NYSE FANG+) qualifies as a non-Indian ETF; gold
  and silver are below both their 100- and 200-day averages, so they are correctly out.
- **NAV premium (Jay, 18 Oct):** an ETF trading more than 3 % away from its NAV is out of the pool.
  International ETFs currently sit at +14 % to +105 % over NAV (creations suspended at the overseas
  limit), so their price measures the premium, not the holdings. On 16 Oct this removes MAFANG
  (+53.8 %) and ITBEES (+3.7 %, likely T-1 NAV noise); gold and silver are within ±1.2 %.
