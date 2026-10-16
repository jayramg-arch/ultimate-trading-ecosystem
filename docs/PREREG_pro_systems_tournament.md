# PRE-REGISTRATION — tournament of professional trading systems (Nifty 500, 2018–2026)

**Registered:** 16 Oct 2026 (IST), before any result for the four new systems was computed.
**Owner:** Jay. **Script:** `pro_systems_backtest.py` (committed with this file).
**Why:** Jay — "take cues from the best systems built and used by the most experienced
professional traders; do not get carried away with what we have already built."

## Common ground (same as PREREG_v2_rank_portfolio)

Panel `data/v2_panel.pkl` (today's Nifty 500 list — survivorship flatters all equally), daily
bars, signals at a session close, fills at the next open, costs 0.25 % per side, stops filled at
the stop or at the open on a gap. Period 2018-06-01 .. 2026-10-16. **Selection half H1** =
2018-06-01 .. 2022-07-31; **confirmation half H2** = 2022-08-01 .. 2026-10-16. Index = Nifty 500.
Where a published rule needs data we do not have (intraday, fundamentals, true base patterns,
pyramiding fills), the stated proxy is used and the deviation is listed.

## The entrants

### P1 — Stocks on the Move (Andreas Clenow, 2015)
- Rank: annualised exponential-regression slope of ln(close) over 90 sessions × R².
- Eligible: close > SMA100; no absolute daily move > 15 % in the last 90 sessions; median
  turnover ≥ ₹5 crore.
- New buys only when the Nifty 500 is above its 200-day SMA.
- Weekly (last session of the week): sell holdings that are no longer eligible or not in the top
  20 % of the ranked eligible list; then buy from the top of the rank while cash remains.
- Size: shares = 0.10 % of equity ÷ ATR(20) (risk parity). No stop (the weekly rules are the exit).
- Deviation: the book's every-other-week position-size rebalance is omitted.

### P2 — Turtle-style trend (Dennis/Eckhardt System 2, adapted to stocks)
- Entry: close above the prior 55-session closing high, close > SMA200 (long-only adaptation).
- Exit: close below the prior 20-session closing low, or a 2 × ATR(20) stop from entry.
- Size: shares = 0.5 % of equity ÷ ATR(20) (1 % risk at the 2N stop); at most 20 positions;
  when more names trigger than slots are free, the highest 12-1 month momentum first.
- Deviation: no pyramiding (units added at +0.5N), no System-1 filter.

### P3 — SEPA / CANSLIM proxy (Minervini, O'Neil)
- Trend template, all of: close > SMA150 and SMA200; SMA150 > SMA200; SMA200 above its value
  21 sessions earlier; SMA50 > SMA150; close > SMA50; close ≥ 1.30 × 52-week low; close ≥
  0.75 × 52-week high; RS rating ≥ 70 (percentile of 0.4×3m + 0.2×6m + 0.2×9m + 0.2×12m return).
- Entry: close above the prior 50-session closing high on volume ≥ 1.4 × its 50-session average
  (pivot-breakout proxy). Market: Nifty 500 above its 50-day SMA.
- Stop 8 % below entry; exit on a close below SMA50.
- 10 positions, equal weight (equity ÷ 10); ties by RS rating.
- Deviation: real VCP/base patterns, earnings acceleration and follow-through days are not
  modelled — proxies above.

### P4 — Volatility-managed momentum (AQR-style; Barroso & Santa-Clara 2015)
- Monthly (last session): 300 most liquid names; score = 12-month return skipping the last
  month; hold the top 30 equal weight.
- Exposure = min(1, 15 % ÷ the strategy's own realised volatility over the last 126 sessions);
  the rest in cash. Full rebalance monthly. No stops.

### Already built (reference only, re-run unchanged)
B1 Nifty 500 · B2 equal-weight universe · B3 Momentum-30 replica · V2 rank → portfolio ·
C trigger proxy (ours).

## Selection and pass rule

1. **Selection (H1 only):** the entrant with the highest H1 MAR (CAGR ÷ |max drawdown|) among
   P1–P4, V2 and C is the **chosen system**.
2. **Confirmation (H2):** the chosen system PASSES if in H2 its MAR > B3's MAR and > B1's MAR,
   and its CAGR > B1's CAGR.
3. All entrants are reported in both halves; nothing is re-tuned after seeing results.

## Decision

- PASS → the chosen system becomes the v2 core and runs as a live paper portfolio (the Paper
  Trades page) for at least 3 months before real money; the board/S4 become its execution tools.
- FAIL → the honest default is the momentum ETF plus the exposure rule; any new idea is a new
  pre-registration on forward data.
