# Pre-registration — Rejection at the level

**Registered:** 12 Oct 2026, ~22:30 IST — written with the code, before the ledger holds a
single row. No outcome has been looked at.
**Source:** Jay, 12 Oct 2026: *"Are we waiting for price acceptance / rejection at key levels
(location) before we pick up the trade?"* Answer: the GO requires price to be AT a level (L),
a pattern (P), a bar that did not close weak (B) and volume (V) — but not that the bar probed
the level and was pushed back. Previous entry-timing ideas were measured and rejected (the bar
gate tightened three times in Aug; confirmation as a timing gate in Jul — a "wait tax"; the
entry optimizer's four hypotheses on 2 Oct). This exact definition has not been tested.
**Status:** NOT RUN. `rejection_test.py` prints counts until the threshold below is met,
then runs once.

## The definition (fixed)

A board GO row (S4-GO starting `5/5`) is a **rejection** when its trigger bar — the last
CLOSED bar on the board's timeframe (75m, 125m or Daily) —

1. reached a level that passed location: its low is at or below the level plus 10% of the
   bar's range (a D/W/M demand zone's proximal edge, a Daily/Weekly S/R level, the AVWAP,
   or VAL — `support["loc_levels"]`), **and**
2. closed **above** that level, **and**
3. closed in the **upper half** of its range.

Computed by `gm_trigger_board.rejection_read`; shown as the board's **Rej** column. It moves
no gate.

## Data — prospective only

- **Population:** `logs/rejection_ledger.csv`, written by the board on every rebuild for every
  `5/5` row, logged **after** this registration (from 13 Oct 2026). One row per symbol,
  timeframe and trigger bar (first logged wins).
- **Entry:** the trigger bar's close (the house retest convention — a limit at the trigger
  close fills on that bar).
- **Stop:** the board's plan stop for that row (`sl`). Rows with no stop, or a stop at or
  above the entry, are excluded and counted.
- **Outcome R:** on Daily bars after the trigger bar's date: stop checked every bar (a gap
  through it fills at the open), else (close − entry) / (entry − stop). **R10** = 10 sessions
  (primary), **R20** (secondary).

## Hypothesis and decision

- **H:** mean R10 of rejection rows exceeds non-rejection rows by **≥ +0.25R**, the median
  R10 of rejection rows is **≥** the non-rejection median, and the symbol-bootstrap 95% CI of
  the mean difference **excludes zero** on the positive side.
- Judged **per plan type** (positional / swing) — never pooled into the headline; timeframes
  reported alongside.
- **If H passes:** it earns a proposal to become a GO condition — a separate decision with
  Jay, made only after a second look at double the sample. **If it fails:** the Rej mark stays
  a display read and nothing changes.

## Sample and procedure

- Run **once**, when a plan-type cell has **≥ 30 rejection rows and ≥ 30 non-rejection rows**
  with R10 elapsed. Until then only counts. A cell under n = 15 is THIN and cannot pass.
- Bootstrap **by symbol**, 10,000 resamples.
- The definition (10% tolerance, upper-half close, the level set) is not tuned before the
  run. A failed result is recorded as failed, not re-sliced.

## Amendment 1 — H2: weak latest bar (registered 12 Oct 2026, ~22:45 IST, ledger rows: 0)

**Source:** Jay, 12 Oct 2026: the B gate passes a green bar with a long top wick (green OR
upper-half close), and he reads the latest closed bar by eye before ordering. Tightening B
was measured and rejected three times in Aug (fills 314 → 241, removed trades were net
winners), so this is registered as a read to be measured, not a gate.

**Definition (fixed — `gm_trigger_board.bar_grade`, same constants in
`Commander_Addons_v1.0.pine (module M1)`):** on the same trigger bar the ledger already records
(o, h, l, c),
- **weak** = close in the lower third of the range, OR upper wick ≥ 50% of the range;
- **strong** = close in the upper third AND upper wick < 25%;
- **neutral** = otherwise. Zero-range bars are excluded and counted.

**H2:** mean R10 of NOT-weak rows (strong + neutral) exceeds weak rows by **≥ +0.25R**, the
median R10 of weak rows is **≤** the not-weak median, and the symbol-bootstrap 95% CI of
the mean difference excludes zero on the positive side.

Same population, entry, stop, R10 definition, per-plan-type judgement, bootstrap and
run-once rule as H1. Threshold: **≥ 30 weak and ≥ 30 not-weak rows** in a plan-type cell.
H1 and H2 are run together, once each cell is ready for its own hypothesis; one passing
does not rescue the other.

**If H2 passes:** a proposal (with Jay, after a second look at double the sample) to make
the weak read change the ENTRY — e.g. a buy-stop above a weak trigger bar instead of the
retest limit — not to suppress the alert. **If it fails:** the Bar column and the
indicator stay display reads, and the manual check can be dropped with a clear conscience.

## Amendment 2 — which bar H2 reads (12 Oct 2026, ~22:57 IST, before any ledger row)

**Source:** Jay, 12 Oct 2026: the PA may have fired a few bars back (the board's recency
window, up to 3 bars), on a bar that was bearish, while the latest bar is bullish; the
order is decided on the latest bar. **H2 is unchanged and stays on the LATEST closed bar**
(the ledger's o/h/l/c) — that is the decision rule being tested.

The ledger now also records `pa_age` (0 = the PA is on the latest bar) and `pa_bar` (the
PA bar's grade, same definition). These are **descriptive only**: reported beside the H1/H2
result as counts (e.g. weak PA bar followed by a not-weak latest bar), never tested, never
used to rescue a failed H2. A test on the PA-bar grade, if wanted, is a new registration
made before looking at these columns' outcomes.
