# Pre-registration — how wide should the swing trail be?

**Written 24 September 2026, BEFORE any width was simulated.** The analysis runs **once**.

## Why

Jay, 24 Sep: *"isn't 1.5×ATR too small?"* The live swing trail is a Chandelier at
**1.5 × ATR on a 14-bar window** (`risk_common.trail_mult_for`, set in July, never
measured). The backtest trails swing trades at **4.5 ×, from the highest close since
entry** — the positional width — so every swing result since July was produced under a
trail the book does not use (AUD-SIM-03). Jay chose to align the backtest to live; this test
decides the number both should use, instead of copying an untested one into the evidence.

What is already known: the exit study (this morning) tested widths 3.4 – 6.75 × on the
backtest's since-entry trail and found none better by 0.10R. 1.5 × was not in that grid.
Stop-out forensics (July) put ordinary SWG-PB shakeouts at 1–2 ATR.

## The trade set and what is frozen

The 515-trade bull re-baseline (`validation_20260819_112959`), **SWG-PB only** (321 trades;
SWG-BO n=2 and SWG-GAP n=1 are too thin to test). Entries, initial stops and the house exit
structure are frozen: T1 2R / T2 4R, 33 / 33 partials, stop to breakeven after T1, 0.10% per
leg, no time stop, same-bar order stop → T1 → T2. **Only the trail changes.**

## The trail (the live definition)

`risk_common.chandelier_exit` with the swing window: level = highest close of the last
**14** bars − k × ATR(14, Wilder), tighten-only, updated from the prior bar's values.

| config | k |
|---|---|
| **W15** (live today) | 1.5 |
| W25 | 2.5 |
| W35 | 3.5 |
| W45 | 4.5 |
| *C* (reported only) | the backtest's current trail: since-entry high close − 4.5 × ATR14 |

## Rule

Primary metric: mean R per trade, IS and OOS (the OOS gate's split, 45-day purge). The
width to use is decided by:

1. **Validity first:** config *C* must reproduce the recorded returns (median |error|
   ≤ 0.25pp, ≥ 95% within 1pp), else the study is void.
2. **Keep 1.5× unless it is beaten:** a wider k replaces 1.5 only if it beats W15 by
   **≥ 0.10R mean in IS and OOS**, its median R is not worse by more than 0.10R, a
   symbol-block bootstrap (5,000) of the pooled difference excludes zero, and it is not
   at the edge of the grid (4.5 can only win if 3.5 also beats W15 — the plateau rule).
3. If none qualifies, **1.5× stays live and the backtest is aligned to 1.5×.**

Holm–Bonferroni across the three wider-vs-W15 contrasts at family-wise α = 0.10.

## Controls

A placebo pass on shuffled, demeaned daily returns (the exit-study placebo) debugs the
harness first; any width "winning" there is a bug.

## Stopping rule

Runs **once**. Result recorded here, and the chosen k goes into both `risk_common` (live)
and `replay` (backtest) in the same commit.

## Result

*(Left empty deliberately. To be filled in ONCE, by the run.)*
