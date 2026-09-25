# Pre-registration — does pyramiding a winner pay, and does it beat a new position?

**Written 25 September 2026, BEFORE any pyramid add was simulated.** The analysis runs **once**.

## Why

Jay, 24 Sep: *"As I cannot keep adding more stocks every day beyond my 22 count, I need to
focus more on Pyramid/Trim of the existing portfolio stocks. How can we make the
Pyramid/Trim system more effective?"*

The trim side is settled: the exit-policy study (24 Sep) measured the ladder's trim rungs as
**inert** (they move R by hundredths — they almost never engage) and the 4.5× trail as not
dominated. So every open lever is on the **ADD** side, and the ADD rung has never been
measured. In a capped book it answers a capital question: **given ₹X, is it better spent adding
to a position the ladder rates ADD, or opening a new name?** If adds lose, the right ladder has
no ADD rung and capital goes to new entries; if adds win, the ADD queue and trim→add pairing
are worth building. Nothing gets built on the ADD side until this is known.

## The trade set and the simulation

The bull re-baseline `validation_20260819_112959`, **positional trades (`POS-*`)** — the book's
horizon and the one pyramiding applies to. Each trade is replayed bar by bar exactly as the
backtest trades it now: recorded entry, stop, T1 / T2, POS 25 / 25 partials, breakeven after T1,
0.10% per leg, **the live Chandelier** (22-bar, 4.5 × Wilder ATR, BREACHED rule — aligned today),
no time stop.

**The ADD trigger — `pyramid_logic.classify`'s ADD rung, rebuilt point-in-time:**
- **Leader:** weekly RRG quadrant (strike_cal vs `^CRSLDX`, last confirmed week) LEADING or
  WEAKENING with open P&L ≥ +5%, **or** LEADING with open P&L ≥ +8%.
  *The live rung also requires the screener Score ≥ 60 on the first branch. Score cannot be
  rebuilt historically, so this test drops that clause — stated, not hidden; it makes the
  trigger fire somewhat more often than live.*
- **Location:** close above a rising 200-DMA, close ≤ close[5] × 1.10, close above the 20-EMA,
  and (close − EMA20) / ATR14 ≤ 2.0 (`ADD_MAX_EXT_ATR`).
- **First add only**, on the first bar both hold, while the position is still open.

**The add leg:** bought at that bar's close. Its stop is the position's stop at that moment,
raised to the live Chandelier if the Chandelier is higher (the rung's "RAISE stop" rule). It
has **no targets of its own** — it rides the trail with the runner and exits when the position's
stop is hit or the data ends. Add-leg R = return ÷ (add price − add stop). Costs 0.10% per leg.

## Hypotheses

- **H1 — adds pay.** Mean add-leg R > 0.
- **H2 — an add beats a new position.** Mean add-leg R − mean R of the new POS entries
  (the same trade set's initial legs, same simulation) > 0.

## Rules

- **R, never %.** IS / OOS: chronological 60 / 40 by anchor, 45-day purge (the exit study's split).
- **Pass (each hypothesis):** ≥ **+0.10R in IS and in OOS**, the median not worse (H1: add-leg
  median ≥ 0 is **not** required — the book is big-winner-carried and a negative median is its
  shape; H2: the median difference must not be negative), and a **symbol-block bootstrap**
  (5,000) CI excluding zero on the pooled figure.
- **n ≥ 40 adds in each window**, else **THIN** — reported, cannot pass, not rescued.
- Reported only: the add trigger's fire rate; the add legs by exit reason; a simpler trigger
  ("first close ≥ entry + 1R", no location test); the position's total R with and without the
  add at equal risk.

## Controls

- **Placebo first** on shuffled, demeaned returns (`exit_ladder_study._placebo`). Any pass is a
  harness bug, fixed before the real run.
- **Validity:** the simulation without adds must reproduce the positional trail run
  (`_pos_trail_trades.csv`, config L) to median |error| ≤ 0.25pp.

## What each result means

- **H1 and H2 PASS** — build the ranked ADD queue and the trim→add pairing on this rung.
- **H1 passes, H2 fails** — adds pay but no better than new names: keep the rung, but in a capped
  book it is a tie-breaker, not a priority.
- **H1 fails (or BACKWARDS)** — the ADD rung is removed from the ladder's recommendations
  (after Jay's say); freed capital goes to new entries through the normal funnel.
- **THIN** — no change; the rung stays as it is and is watched on live adds.

## Stopping rule

Runs **once** (marker `validation_runs/_add_premise_REAL_RUN_DONE.json`). No re-slice, no
changed trigger, no changed bar. Result recorded below.

## Result

**Run 25 Sep 2026, once** (`validation_runs/_add_premise_run.log`, trades
`_add_premise_trades.csv`). Placebo: noise-level, cannot pass (and it warned adds fire on ~a
quarter to a half of trades). Validity: the no-add simulation reproduces the positional-trail run
exactly (191/191, median |err| 0.0000pp). Adds fired on **95 of 191** positional trades (50%),
median 16 bars in, +6.6% up, held 35 bars.

| | IS n | IS mean R | IS median | OOS n | OOS mean R | OOS median |
|---|---:|---:|---:|---:|---:|---:|
| **Add legs** | 50 | −0.396 | −0.698 | 39 | +0.223 | −0.027 |
| **New entries** (same trades' initial legs) | 105 | −0.352 | −0.609 | 76 | +0.137 | −0.386 |

H1 (adds pay): pooled CI [−0.29, +0.06]. H2 (add − new entry): IS −0.045R, OOS +0.086R,
median +0.040R, CI [−0.12, +0.15]. **Verdict: THIN on both** — 39 OOS adds against the 40
required. Per the rule, nothing changes: the ADD rung stays as it is.

**What it says, stated no more strongly than the numbers allow:** an add behaved like a new
position — both lost about 0.4R in the in-sample window and both made money out-of-sample,
within 0.1R of each other in each window, with every interval straddling zero. There is no
evidence that pyramiding a winner beats opening a new name, and none that it is worse. The
simpler "+1R" trigger (reported only) did worse than the rung (−0.20R mean), so the rung's
location test appears to earn its keep, though that too is unconfirmed.

**For the capped book this means** the choice between adding and opening a new name cannot be
made on expected return — the data does not separate them — so it has to be made on RISK: an add
raises concentration in a name already held, a new name diversifies. That points the ADD queue
at a single capital queue where adds and new entries compete on one scale and concentration is
the tie-breaker — a design decision for Jay, not a measured edge.
