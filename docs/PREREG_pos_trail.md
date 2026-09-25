# Pre-registration — the positional trail: align the backtest to the live Chandelier?

**Written 25 September 2026, BEFORE any positional trade was simulated under the live trail.**
The analysis runs **once**.

## Why

Step 4 of the 24-Sep audit (AUD-SIM-03): the backtest must trade the way the book does. The
swing half is settled (`docs/PREREG_swing_trail.md`: live 14-bar 1.5× beat every wider width;
the backtest now uses it). The positional half is still two different trails:

| | anchor | ATR | stop update |
|---|---|---|---|
| **Backtest** (`replay._simulate_one_trade`) | highest close **since entry** | 14-bar **simple** ATR, current bar | every bar |
| **Live** (`risk_common.chandelier_exit`, positional) | highest close of the **last 22 bars** | 22-bar **Wilder** ATR, prior bar | tighten-only; a level at/above the prior close is BREACHED, never pushed |

Both use 4.5×. Jay's standing call (24 Sep) is **"backtest to live"**. This test does not
reopen that call; it checks one thing first: that the live trail is not materially worse than
the backtest's, since if it were, the thing to change would be the live trail, not the backtest.

## Trade set and what is frozen

The bull re-baseline `validation_20260819_112959`, **positional catalysts only** (`POS-*`).
Entries, initial stops, the recorded T1 / T2 prices, partials (`bull_screener.partial_qty_for`,
POS 25 / 25), breakeven after T1, 0.10% per leg, no time stop, same-bar order stop → T1 → T2 —
all frozen. **Only the trail changes.**

| config | trail |
|---|---|
| **C** | the backtest's current trail (must reproduce the recorded returns) |
| **L** | the live positional Chandelier: 22-bar highest close − 4.5 × Wilder ATR(22), prior bar, tighten-only, BREACHED rule |
| *L-bear* (reported only) | L with +0.5× when `^CRSLDX` was not in the bull regime (close > SMA200 and SMA50 > SMA200) on the prior bar — the live bear widening, reconstructed point-in-time |

## Rule

Primary metric: **mean R per trade** (house rule), IS and OOS (chronological 60/40 by anchor,
45-day purge — the split the exit study used), per family.

1. **Validity first:** C must reproduce the recorded returns (median |error| ≤ 0.25pp, ≥ 95%
   within 1pp), else the study is void.
2. **Decision family: POS-BO** (the larger book). POS-ACCUM is reported; if it has fewer than 40
   trades in a window it is THIN and cannot block anything.
3. **Align the backtest to live UNLESS** L is worse than C by **≥ 0.10R in IS and in OOS**, its
   median is worse too, and a **symbol-block bootstrap** (5,000) CI of the pooled difference
   excludes zero. If that happens the backtest is **not** changed and the finding goes to Jay —
   the live trail would be the thing to revisit.
4. Otherwise the positional trail in `replay` becomes the live one (all `POS-*`), in one commit
   with this result, exactly as the swing half was done.

## Controls

- **Placebo first** on shuffled, demeaned returns (`exit_ladder_study._placebo`); any "win"
  there is a harness bug and is fixed before the real run.
- The BREACHED rule is applied from the start (the swing placebo found that omitting it lets a
  pullback entry's trail sit above the market and fill at prices that never traded).

## Stopping rule

Runs **once** (marker `validation_runs/_pos_trail_REAL_RUN_DONE.json`). No re-slice, no changed
bar. Result recorded below.

## Result

*(Left empty deliberately. To be filled in ONCE, by the run.)*
