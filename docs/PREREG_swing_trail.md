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

## Amendment 1 — 24 Sep, after the placebo, before the real run

The placebo (shuffled, driftless prices) showed the 1.5× trail at +0.83R with a one-day
median hold — impossible on a random walk. Cause: SWG-PB enters after a pullback, so the
14-bar highest close sits ABOVE the entry and the Chandelier level lands above the market;
the harness raised the stop there and filled it at a price that never traded. Live, the
trail job reports such a level as BREACHED and never pushes it. The harness now applies the
same rule: the trail only rises to a level below the prior close. No other change; the
placebo is re-run before the real run.

## Result

**Run 24 Sep 2026, once** (`validation_runs/_swing_trail_run.log`, trades in
`_swing_trail_trades.csv`). Placebo after Amendment 1: every width flat to negative, none
passes. Validity: C reproduces the recorded returns exactly (median |err| 0.000pp, 100%
within 1pp). SWG-PB, 321 trades.

| trail | IS mean R | IS median | OOS mean R | OOS median | trail exits | median days |
|---|---:|---:|---:|---:|---:|---:|
| C (old backtest) | −0.400 | −1.056 | −0.325 | −1.065 | 24.9% | — |
| **W1.5 (live)** | **−0.232** | **−0.470** | **−0.103** | **−0.501** | 83.8% | 3 |
| W2.5 | −0.346 | −1.048 | −0.319 | −1.048 | 46.7% | 4 |
| W3.5 | −0.381 | −1.055 | −0.288 | −1.064 | 27.4% | 4 |
| W4.5 | −0.404 | −1.056 | −0.350 | −1.065 | 24.9% | 4 |

Every wider width **fails, and is worse**: ΔIS −0.11 to −0.17R, ΔOOS −0.19 to −0.25R, and
every pooled CI95 excludes zero *below* it (W2.5 [−0.26, −0.02], W4.5 [−0.31, −0.06]).

**Decision: 1.5× stays live; the backtest's swing trail is aligned to it** (`replay.py`
`SWING_TRAIL_MULT`/`SWING_TRAIL_WINDOW`, main replay path; verified against this harness to
≤ 0.005pp on 80 trades). Positional trails are unchanged.

**What this does NOT say:** the swing book is still negative at every width (−0.23R IS,
−0.10R OOS at the best one). The tight trail is the least-bad exit for SWG-PB, not an edge.
And the median hold of 3 days means the trail is doing most of the exiting — a tight trail
on a pullback entry takes you out on the first normal down day. Jay's instinct that 1.5×
is small is correct in kind; it is simply that wider was worse here, not better.
