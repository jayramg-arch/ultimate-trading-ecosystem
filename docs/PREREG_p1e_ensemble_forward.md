# PRE-REGISTRATION — P1E, the ensemble version of the v2 core (forward only)

**Registered:** 16 Oct 2026 (IST). **Owner:** Jay. Plan: Doc 40 §3.
**Code:** `pro_systems_backtest.p1_weekly(..., ensemble=True)` and the P1E book in `p1_paper.py`.

## Why

PREREG_p1_robustness: P1's exact setting (90 sessions, top 20 %, 0.10 %) is an optimistic peak;
the approach holds across the grid but no single setting can be trusted. The standard
professional answer to parameter risk is an **ensemble** — average several reasonable settings
so none has to be right.

## P1E rules (fixed now)

Identical to P1 except the rank and the cut-off:
- **Rank:** for every eligible name, its percentile rank on each of the three trend-quality
  scores (exponential-regression slope × R² over **60, 90 and 120** sessions), averaged.
- **Cut-off:** sell outside the top **25 %**; buy from the top.
- Risk 0.10 % of equity per ATR(20); regime gate (Nifty 500 > 200-day SMA for new buys); SMA100
  and 15 %-gap eligibility; weekly; paper only; same start (16 Oct 2026 close) and capital.

## How it is judged (forward only — no historical run is used to judge it)

The grid that motivated P1E has been seen, so a historical backtest of P1E would be tuned on its
own evidence. P1E is judged ONLY on paper results from 16 Oct 2026 onward, at the Doc 40 gates:

- **At each gate (16 Jan 2027 earliest; 16 Apr 2027 re-read):** P1E passes if, since the start,
  its return is at or above the Nifty 500's and its maximum drawdown is shallower than the
  index's.
- **Choice of the book for real money** (once Doc 40's other gates clear): if P1E and P1 both
  pass, **P1E** gets the money (less parameter risk). If only one passes, that one. If neither,
  no money.
- A period spent mostly in cash (regime down) is reported as THIN, not as a pass.
