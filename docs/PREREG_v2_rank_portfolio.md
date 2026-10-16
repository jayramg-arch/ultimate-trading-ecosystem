# PRE-REGISTRATION — v2: rank → portfolio → execute, against the benchmarks

**Registered:** 16 Oct 2026 (IST), before any portfolio result was computed.
**Owner:** Jay. **Script:** `v2_backtest.py` (committed with this file). Design: Doc 39.

## Question

Does a layered, ranking-based portfolio of Nifty 500 stocks beat (a) the market, (b) a plain
momentum index method and (c) today's trigger-based approach — on return per unit of drawdown —
in both halves of 2018–2026? If not, the conclusion is to own the momentum ETF and stop building.

## Data (fixed now)

- **Universe:** `nifty500_symbols.json` (today's list — survivorship flatters every variant
  equally; the comparison between variants is what counts). Daily OHLCV, `period="10y"`, from
  the cache. A name enters the universe once it has 260 bars of history.
- **Period:** signals from **2018-06-01** to **2026-10-16**. Halves split at **2022-08-01**.
- **Costs:** 0.25 % of value per side on every buy and sell (STT, charges, slippage).
- **Execution:** signals on a week's last session close; trades at the **next session's open**.
  No information after the signal close is used.
- **Earnings:** no point-in-time earnings history exists here, so the earnings factor of Doc 39
  is NOT in this test. It can join v2 only after a separate forward check.

## The variants (fixed now — no others will be added after seeing results)

| ID | Variant | Rules |
|---|---|---|
| **B1** | Nifty 500 buy-and-hold | the index (^CRSLDX) |
| **B2** | Equal-weight universe | every name with data, equal weight, rebalanced monthly (survivorship-matched benchmark) |
| **B3** | Momentum-30 replica | 200 most liquid names (median 1-year turnover); score = mean z-score of 6- and 12-month return ÷ 1-year volatility; hold top 30 equal weight; rebalance at the end of June and December; no stops, no regime |
| **C** | Trigger proxy (today's idea) | eligible name (close > SMA150 rising) on a day the Daily bull PA battery fired (`data/pa_*_signals.csv` cohort A); buy next open into a free slot (max 15, equal weight); stop entry − 4×ATR(D); Chandelier exit (22-day highest close − 4.5×ATR, on a close); first-come, ties by symbol |
| **V2** | **Rank → portfolio (primary)** | see below |
| **R** | Random-eligible control | V2's rules but the 15 names drawn at random from the eligible set (mean of 20 seeds) — tells whether the RANK adds anything over eligibility alone |

### V2 rules

- **L0 Regime:** target 15 positions when the Nifty 500 closed above its 200-day SMA at the
  signal close, 7 when below. Above-target holdings are not force-sold; they leave by the exits.
- **L1 Eligibility:** close > SMA200; SMA200 above its value 20 sessions earlier; close >
  SMA50; median daily turnover over 50 sessions ≥ ₹5 crore.
- **L2 Rank:** among eligible names, the average percentile of four scores, equal weights, no
  fitting: (1) 12-month return ÷ 1-year volatility, (2) 6-month return ÷ 1-year volatility,
  (3) close ÷ 52-week high, (4) share of the last 126 sessions that closed above their SMA50.
- **L3 Portfolio:** weekly. Sell a holding that is no longer eligible or ranks below 45 (3 × 15).
  Then fill free slots (up to the regime target) from the top of the rank, names not held.
  Each new position = current equity ÷ 15. Sector caps are NOT applied (no sector history);
  stated as a limit.
- **Stops:** initial stop entry − 4×ATR(D), checked every session (fill at the stop, or at the
  open on a gap). No other intraweek exit.

## Metrics and pass rule

- Per variant and per half: CAGR, maximum drawdown, **MAR = CAGR ÷ |max drawdown|**, annualised
  volatility, Sharpe (weekly, risk-free 0), turnover, number of trades.
- **V2 PASSES** only if, in **both** halves, its MAR is higher than **B2 and B3**, and its CAGR is
  higher than **B1**. R is reported as the control: if R ≈ V2, the rank is not doing the work.
- **Decision:** PASS → v2 is built live as a paper portfolio first (forward, months), then
  real money only if it holds up. FAIL against B3 → own the momentum ETF; the ranking idea is
  dropped. FAIL against B2 only → report and decide with Jay.

## Discipline

- Plumbing is checked on 2018-06 .. 2018-12 only (printing trade counts, not returns) before
  the run. The full run happens **once**. Variants are not re-tuned after seeing results; any
  later variant is a new pre-registration on a new hold-out.
