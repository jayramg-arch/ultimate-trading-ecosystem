# Pre-registration — IMPROVING→LEADING vs LEADING→LEADING on the trades we actually take

**Written 25 September 2026, BEFORE any trade in the test set was labelled with an RRG cell.**
The analysis runs **once**.

## Why

Jay, 25 Sep: *"when a stock is moving from improving to leading, its RS and momentum are
increasing — why are we considering it negative, when the whole industry says that move is
good?"*

The negative reading comes from the 18-Aug universe study (`rrg_cell_remeasure.py`, 473
symbols, ~90,000 weekly observations): against every other cell, IMPROVING→LEADING returned
**−0.33pp at 4 weeks** (CI [−0.61, −0.06]) and **−0.87pp at 12** (CI [−1.55, −0.14]), while
LEADING→LEADING returned **+0.66pp** and **+0.97pp**, both CIs excluding zero. That study
covered every Nifty 500 name every week. It never looked at the trades this system takes:
Stage-2 names that clear the GO gate. Whether the difference survives inside that funnel is
the open question, and it decides whether the RRG confluence point should keep crediting
L→L and ignoring I→L.

## What the cells mean (the exact definition — not a crossing)

`rrg_cell_remeasure.py` / `bull_screener._rrg_trajectory`, verbatim:
- **Current quadrant** from JdK RS-Ratio and RS-Momentum vs NIFTY 500 (`calculate_jdk_rrg`,
  `strike_cal`), on confirmed weekly bars (`pa_patterns._confirmed_weekly_ohlcv`).
- **Next quadrant** from the 4-week tail (`TRAIL = 4`, noise floor `THRESH = 0.30`), via
  `next_quadrant()`.
- **I→L** = currently IMPROVING (RS-Ratio < 100, RS-Momentum ≥ 100) with RS-Ratio rising
  more than 0.30 over 4 weeks — a laggard heading toward LEADING, **not** one that has crossed.
- **L→L** = currently LEADING and not flagged to leave it.

## The trade set

GO-timed bull trades from run **`validation_20260909_190451`** (Aug 2021 → Jan 2026; 1,580
armed rows, **513 filled**). Outcomes are taken **as recorded** — no re-simulation. Each filled
trade is labelled with its cell **as of the last confirmed weekly bar on or before its
`GO_Date`**: daily data truncated at `GO_Date`, the forming week dropped, so the label uses
only what was known when the trade fired.

Kept: trades whose stage at `GO_Date` is 2 on the shared stateless 2×2 (the funnel this
system trades). Trades with no computable cell are excluded and counted, never guessed.

## Outcome and comparison

- **Primary metric: R per trade** = `Return_pct / SL_pct` (house rule: stop and sizing studies
  in R, never per-trade %). Matched alpha (`Alpha_Matched_pct`) reported alongside.
- **H1:** mean R(L→L) − mean R(I→L) > 0.
- **Pass:** difference **≥ +0.10R in IS and in OOS**, the median difference not negative, and a
  **symbol-block bootstrap** (5,000) CI of the pooled difference excluding zero.
- IS/OOS: chronological 60/40 by `GO_Date`, **45-day purge** at the boundary.
- **n ≥ 40 in each of the four cells** (L→L / I→L × IS / OOS), else **THIN** — reported, cannot
  pass, and not rescued by relaxing the bar. *Expect THIN is possible:* 513 trades across twelve
  cells may leave I→L short in one window.
- Reported only, not decisive: W→L vs I→L; each of L→L, W→L, I→L vs all other filled trades;
  hit rates (initial-stop share, trail share, T1 reached).

## Controls

- **Coverage print first:** share of filled trades that get a cell, and the cell counts per
  window. Under 90% coverage → reported as UNDERPOWERED rather than read.
- **Label check:** on 20 random trades, the cell from this harness must equal
  `bull_screener._rrg_trajectory` computed on the same truncated data. Any mismatch → stop and fix
  the harness before the real run.
- **Placebo:** cell labels shuffled within `GO_Date` month. Any pass is a bug.

## What each result means

- **PASS** — the universe result holds inside the funnel: keep crediting L→L (and W→L) and not
  I→L. The RRG point stays at 1.
- **FAIL / THIN** — no evidence either way inside the funnel. The RRG point stays as it is (the
  universe evidence is what it rests on); nothing is removed on a null.
- **BACKWARDS** — I→L beats L→L by ≥ 0.10R in both windows with a CI excluding zero: the
  confluence point is re-examined for GO-timed use, and the finding goes to Jay before any change.

## Stopping rule

Runs **once** (marker file `validation_runs/_rrg_IL_LL_REAL_RUN_DONE.json`). No re-slice, no
changed window, no changed threshold. Result recorded below.

## Result

*(Left empty deliberately. To be filled in ONCE, by the run.)*
