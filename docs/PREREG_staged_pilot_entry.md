# PREREG · STAGED PILOT ENTRY — half now, half on confirmation

**Written 9 Sep 2026, BEFORE any arm is run.** Source: Jay's
`E:\Notes\Premature SL hits.docx`, Step 3. The last untested idea in that document, and
the only one that attacks where the evidence actually points.

---

## 1. Why this and not another exit change

Everything else in that document is closed:

| step | status |
|---|---|
| 1 · two-tier / close-basis stop | **tested, rejected** (H8) — win rate rose in all three families, worse fills cancelled it exactly |
| 2 · widen the stop, cut size | already measured and rejected; in R the optimum came out TIGHTER |
| 4 · order split 25/25/50 at 3R/5R | **already shipped** — `target_r_for` + `partial_qty_for` |
| 5 · pre-exit checklist | not built; discretionary, collides with the no-overrides rule |

And a target audit run today says the exit apparatus is not misplaced: on 513 trades the
positional book hits **T1 39.3%** and **T2 25.6%**, with max-runup reaching 3R on 26.3%
and 5R on 13.4%. T1 at 3R sits where the distribution thins. There is no mis-set level to
fix. *(This also corrects a figure carried in the notes and repeated earlier today — "only
8.4% ever reach 3R" — which came from a different, much smaller population.)*

**The leak is at the entry.** Initial-SL hit rate is 50-60% on GO-timed entries against
11.8% on the buy@close positional book. That is the same finding as the deferred-entry tax
(−1.23pp, median 8 days) and the GO-timing result (+2.56% → ~0% matched alpha). Five stop
studies and one target audit all point the same way.

Staging is an **ENTRY** change. That is the point.

## 2. The change under test

`replay.ENTRY_STAGING`, default `"full"` — every prior run reproduces byte-for-byte.

* `"full"` — unchanged: the whole position fills at the GO entry.
* `"pilot"` — **50% at the GO entry**, the remaining **50% on a confirmation event** within
  `add_window` bars (default 20), whichever comes first:
  1. **Retest-and-turn** — price trades at or below the GO bar's close and then closes back
     above it; or
  2. **New high** — close above the GO bar's HIGH.

  If neither fires inside the window, the trade simply runs at half size. It is never
  topped up late.

### Risk accounting — fixed before it can be argued about
* **The stop is the same structural stop for both tranches.** Staging changes SIZE, not the
  invalidation level. A per-tranche stop would be a second change and would confound this one.
* **R is measured against the INITIAL risk unit, fixed at entry**, exactly as the live
  policy does — `(entry_1 − stop) × full_intended_qty`. Not re-based when the second tranche
  fills, or a half-size trade would score a full R for half the move.
* **Returns are scored on the TOTAL position**, weighted by what actually filled. Per-tranche
  reporting is diagnostic only.
* The doc's "move tranche 1 to breakeven when tranche 2 fills" is **NOT** included. It is a
  separate intervention, it interacts with the trail, and bundling it would make a pass
  unattributable.

## 3. Hypothesis

**H9** — entering half at the GO and half on confirmation improves mean matched-horizon
alpha per R-unit of risk, per family, without reducing capital deployed enough to offset it.

## 4. The way this most plausibly FAILS, stated first

**This book's edge is carried by a small number of large winners.** Measured repeatedly:
median max-runup 1.40R, only 13.4% reach 5R, and every family's MEDIAN trade is negative
while the mean is positive.

A staged entry is **half-size on any winner that never pulls back**. If the runners are
exactly the trades that go straight up — which is what a breakout that works looks like —
then staging systematically halves the position in the trades that pay for everything, and
doubles down only on the hesitant ones. That is the opposite of what you want from a
big-winner-carried strategy.

So the diagnostic that matters is not the mean. It is: **among trades that reached 3R+, what
fraction ever triggered the add?** If that is low, staging is a tax on the winners and no
amount of loss reduction rescues it. That number is reported BEFORE the alpha.

The competing mechanism — halved loss on the 50-60% that stop out — is real and is why the
test is worth running.

## 5. Adoption rule — fixed now

Adopt `"pilot"` ONLY if ALL of:

- **A · it bites** — the add triggers on ≥ 40% of filled trades (below that it is a
  half-size book with extra steps).
- **B · per-family edge ≥ +0.15R** on mean R-multiple. **Measured in R, never in per-trade
  %** — a % metric structurally rewards changes that alter position size, which is exactly
  what this change does, and that error already inverted one stop conclusion on this desk.
- **C · symbol-block bootstrap CI95 on (treat − control) excludes zero.**
- **D · the sign holds in both chronological halves.**
- **E' · deployment** — mean R × capital-weighted fill rate must beat the control. A book
  that is systematically half-invested has to earn its way past that.
- **F · the winner-capture check** — among control trades reaching 3R+, ≥ 60% must have
  triggered the add. This is the §4 failure mode as a hard gate.

**Falsifier:** any of A-F failing per family means full-size entry at the GO stands, and the
finding is recorded as *"staging protects the losers by taxing the winners"* — which would
itself be worth knowing, because it is the same shape as the deferred-entry result and would
make it two independent confirmations that hesitation costs this book more than it saves.

## 6. What a pass would and would not license

**Would:** a staged entry convention in the guided-execution checklist, sized so total risk
at full allocation is unchanged.

**Would NOT:** the breakeven-stop-on-tranche-2 rule (§2, separate test) · any change to
SL/T1/T2 levels, which this test holds fixed · a discretionary "add when it feels right",
which is the thing a mechanical add trigger exists to replace.

## 7. Honest prior

For: it directly targets the measured leak (entry, not exit), it halves exposure to the
50-60% initial-stop cohort, and it matches Jay's own confirmation-before-entry doctrine.

Against: §4 is a serious mechanism and I expect it to bite. My expectation is that **A and
E' pass, F fails**, and the net is roughly flat — protecting losers at the cost of the
winners that carry the book. Written down before running it.

Against, second: this is the tenth pre-registered test in a fortnight and none has been
adopted. If it fails, the correct read is not "try an eleventh" — it is that entry and exit
tuning have both been searched fairly hard on a sample that cannot resolve ~1pp effects, and
the regime term (+0.85% vs −0.63% between periods, same screener) remains larger than
anything found.
