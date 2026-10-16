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

## RESULT (16 Oct 2026, run once) — P1 "Stocks on the Move" chosen on H1 and PASSES H2

| system | CAGR full | max DD | MAR full | MAR H1 | MAR H2 | Sharpe | trades |
|---|---|---|---|---|---|---|---|
| **P1 Stocks on the Move (Clenow)** | **21.88 %** | **−18.9 %** | **1.16** | **1.00** | **1.43** | **1.19** | 3,503 |
| P3 SEPA/CANSLIM proxy | 18.95 % | −38.9 % | 0.49 | 0.87 | 0.19 | 0.93 | 989 |
| C trigger proxy (ours) | 22.89 % | −36.3 % | 0.63 | 0.71 | 0.67 | 1.13 | 562 |
| V2 rank → portfolio | 17.70 % | −33.3 % | 0.53 | 0.54 | 0.55 | 0.89 | 1,573 |
| B3 Momentum-30 replica | 18.30 % | −38.3 % | 0.48 | 0.51 | 0.56 | 0.92 | 990 |
| P4 vol-managed momentum | 16.36 % | −38.0 % | 0.43 | 0.40 | 0.61 | 0.89 | 5,970 |
| P2 Turtle-style trend | 10.20 % | −45.3 % | 0.22 | 0.42 | 0.07 | 0.53 | 1,548 |
| B2 EW universe | 22.11 % | −42.2 % | 0.52 | 0.46 | 1.16 | 1.10 | – |
| B1 Nifty 500 | 11.05 % | −38.3 % | 0.29 | 0.31 | 0.54 | 0.71 | – |

- H1 selection order (MAR): P1 1.00, P3 0.87, C 0.71, V2 0.54, P2 0.42, P4 0.40 → **P1 chosen**.
- H2 confirmation: P1 MAR 1.43 vs B3 0.56 and B1 0.54; CAGR 24.67 % vs 10.11 % → **PASS**.
- P1's maximum drawdown (−18.9 %) is about half of every other system and of the index.
- Calendar years (2018 from June): P1 −5.4, +2.3, +25.0, +89.7, −0.8, +74.8, +37.7, −6.2, +1.9 (2026 YTD).
- Survivorship (today's list) flatters every stock variant; the comparison between systems is
  the fair one. P1's turnover is high (3,503 trades); 0.25 % per side is already charged.
- Decision per the rule: P1 becomes the v2 core, as a live PAPER portfolio for at least three
  months before real money; the board and S4 become its execution tools.
Output: `reports/pro_systems/` (equity.csv, metrics.csv), `reports/pro_systems_result_20261016.txt`.
