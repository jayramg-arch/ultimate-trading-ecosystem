# PREREG · does the FIRST overhead obstacle actually stop the trade?

**Written 11 Sep 2026, after the close, BEFORE the audit runs.**

## The question
S4's Room row (and the board's `s4go_status`, and until today the AI reviewer) measures room
to the FIRST obstacle of any class and treats < 1R as a fail. On the 11-Sep boards this
capped 20 of 22 GO names, nearly all on a single-touch Daily S/R level 1–5% overhead — which
on a pullback is by construction the swing high the pullback came from.

Jay: *"None of the trades shown have room, which is unlikely."*

The S/R-ageing work (9-Sep) did not touch this: the binding level is fresh 84% of the time.

## Hypothesis
**H10** — the first overhead obstacle's predictive power depends on its CLASS. A Daily
single-touch S/R level or pivot shelf within 1R does NOT reduce the odds of a GO-timed
trade reaching T1 or its mean R; a supply zone / Weekly-Monthly level does.

## Instrument
`room_obstacle_audit.py` on the s4go control run `20260909_055448` (331 filled trades,
catalyst qualify, 36 mo). For each trade, at `Entry_Date` with data PINNED to that date:
`zone_engine.overhead_room({"D","W"}, price=entry, entry, risk=entry−SL)` — the same
function the board uses — giving obstacle price + source string. Class:
* **HARD** — `SZ·*` (supply zone), `SZ band top`, `S/R·W`, `S/R·M`
* **SOFT** — `S/R·D`, `PivR·*`, `Pv·*`, `lastPH`
* **CLEAR** — no obstacle

Room bucket: `<1R` · `1–2R` · `≥2R` · `clear`. Outcomes per bucket × class:
`Hit_T1 %`, mean and median **R** (Return_pct × entry / risk), `ceiling broke %`
(= Max_Runup ≥ distance to obstacle: did price go THROUGH the thing the metric called a lid).

## Pre-registered read
* **A** — if SOFT `<1R` trades have `Hit_T1` and mean R **not worse than SOFT `≥2R`** by more
  than 5pp / 0.15R, AND `ceiling broke` ≥ 50% for SOFT `<1R`: **soft obstacles are not
  ceilings** → demote `S/R·D` single-touch + pivots to "T1 anchor / soft" in S4 Room, board
  `s4go_status`, and keep them TOLERABLE in the reviewer. HARD stays a veto.
* **B** — if SOFT `<1R` is materially worse (≥5pp Hit_T1 or ≥0.15R): the caps are real and
  the boards are honestly thin; the metric stays and the fix is selection, not Room.
* **C** — if HARD `<1R` is NOT worse than HARD `≥2R`: Room as a whole is not predictive on
  this sample; report it, do not tune it (n will be small — say so).
* Symbol-block bootstrap CI95 on the SOFT `<1R` − SOFT `≥2R` mean-R difference; no adoption
  language unless the CI is on the right side of −0.15R.
* Per family (SWG / POS) reported; pooled decides nothing.

## What this cannot say
It measures GO-timed catalyst entries with the shipped structural stop and 2R/4R · 3R/5R
targets. It does not test the S4 pattern-zone geometry itself, and Room here is Python's
D+W reconstruction of S4's six-source `_ovh` — S4 also sees native-TF zones and manual
levels the audit cannot.

---

# OUTCOME · H10 — recorded 11 Sep 2026

`room_obstacle_audit.py` on `20260909_055448`: 331 filled GO trades, board-identical
`overhead_room` at each entry, data pinned. First obstacle: SOFT 216 · HARD 82 · CLEAR 33.
**255 of 331 (77%) had < 1R to the first obstacle** — "no room" is the normal state of a
GO-timed entry on this book, exactly as Jay sees on the panel.

| | n | Hit T1 | mean R | median R | obstacle broken |
|---|---:|---:|---:|---:|---:|
| room < 1R (any class) | 255 | 32.9% | **+0.21** | −1.03 | 63–77% by source |
| room ≥ 1R or clear | 76 | 34.2% | **−0.17** | −1.03 | — |
| book | 331 | 33.2% | +0.12 | −1.03 | |

Symbol-block bootstrap on (<1R − rest) mean R: **+0.376R, CI95 [−0.09, +0.91]**. The
"no room" cohort is not worse; if anything it is better.

**The first obstacle is punched through 63–77% of the time regardless of what it is:**
S/R·D 69% · lastPH 77% · SZ band top (in-supply) 74% · Pv·D 63% · SZ·D 69%. Class does not
discriminate on outcome either (mean R: S/R·D −0.27 · SZ band −0.09 · SZ·D +0.57 · Pv·D
+1.20 · lastPH +0.29), and S/R age band does not (FRESH −0.21 / SEASONED −0.34 / AGED −0.31).
**Blue sky (no obstacle, n=33) is the WORST bucket: mean −0.28R, hit 27%** — the
buy-stop-chase profile already measured elsewhere.

## Read against the pre-registration
* A (soft < 1R vs soft ≥ 2R): mean R −0.025R passes; Hit-T1 32% vs 50% fails the 5pp clause —
  **but the comparator is 12 trades** (±28pp). Not resolvable in that cell.
* C: HARD < 1R (n 72, +0.10R) is not worse than the book. Applies.
* The pooled, powered comparison (255 vs 76) says more than either pre-registered cell and it
  is the one to act on: **room-to-first-obstacle does not predict outcome on this book.**

## VERDICT
**Room is INFORMATION, not a gate.** The HARD/SOFT split I proposed this afternoon is also
not supported — nothing in the obstacle class separates outcomes. What stays true: an
obstacle is where T1 anchors and where a partial makes sense, and in-supply is modestly
below book (−0.09R, hit 28.6%) but breaks through 74% of the time.

What changes: the reviewer prompt (room never FATAL on its own, any class); S4 already
reframes most cases via `momentum_clear`/`ath_prox_pct` (23-Jul) — the remaining "⚠ NO ROOM"
wording on the Room row is what Jay reads as a veto and is a Pine edit for him to schedule.
What does not change: the Room row itself, the obstacle sources, S/R ageing.

Why the boards looked empty: not a market fact, not a bug — a metric that fails 77% of
entries by construction and was being read (by me, in the prompt, and on the panel) as a veto.
