# Pre-registration — can GM+S4 time the ENTRY? (entry optimizer, step C)

**Written 2 October 2026, BEFORE the holdout data was qualified or looked at.** Hypotheses,
data, cells, pass bars and the stopping rule are fixed here; the analysis runs **once**
against this file. Anything learned that is not in this document is a finding to
pre-register next time, never a result to report as though it had been predicted.

## Why this exists

The Golden Rules say *"the GO gate is a trade CLASSIFIER, not an entry optimizer."* Jay
wants GM+S4 to optimise entries. Three steps so far:

| Step | What | Result |
|---|---|---|
| B | Daily-bar re-run of the 23-Jul entry A/B, like-for-like, in R | GO entries no better than buying at the qualification close (buy-stop −0.24R, retest −0.13R) |
| D | Shadow record of live GOs (`entry_shadow.py`, nightly) | 61 GOs at 5 sessions: entry methods within ±0.03R of market-at-close |
| A | **75m/125m replay** of the board's GO (`intraday_replay.py`, commit `f214434d`) | No method significant overall; **positional names gained from GO timing in 5 of 6 rows (+0.15 to +0.24R on 125m), swing names lost in all 6** |

Step A was **exploratory**: the family split was noticed in its output, not predicted. A
pattern found by looking cannot be confirmed on the data it was found in. So step C tests
it on candidates step A never saw.

## Data

| | |
|---|---|
| Anchors (holdout) | **Jul 2023 – May 2024** (monthly, mid-month: 2023-07-17 … 2024-05-15, 11 anchors) and **Dec 2025 – Apr 2026** (2025-12-15 … 2026-04-15, 5 anchors). None overlaps step A's 18 anchors (2024-06-17 … 2025-11-17). The late window stops at April so every positional trade has its full 180 days. |
| Candidates | Qualified fresh at each anchor by the **current production** bull screener (`bull_screener.run_bull_screener(strict=True)`, pinned to the anchor date, nifty500). Cached to `validation_runs/_c_qual_cache/`. The commit hash is recorded in the result file. |
| Bars | Dhan 25-minute history resampled to 75m/125m (verified available from June 2023); daily from `data_provider`. |
| GO, entries, stop, exits | Exactly as `intraday_replay.py` at commit `f214434d` (gates, fills, 3× daily-ATR cap, entry-day stop check, daily exit simulator, 2R/3R targets, 33/33 partials, 4.5× trail, catalyst horizon, 0.10% per side). Any change to that logic before the run is an **amendment** recorded below; none after it. |
| Baseline | **E0** — buy at the anchor-day close with the daily structural stop (`entry_rebaseline.e0_trade`), on the same names. |
| Families | **POS** = forward window ≥ 120 days (POS-BO, POS-ACCUM). **SWG** = SWG-*. Recovery is not in this test. |

## Hypotheses

Every comparison is **paired**: GO-entry R minus E0 R on the same (anchor, symbol).

| # | Hypothesis | Cell | Pass bar |
|---|---|---|---|
| **H1** | For **positional** names, a GO entry on **125m** beats buying at qualification | POS × 125m × **I_close** (primary) | mean paired diff **≥ +0.15R**, median paired diff **≥ 0**, the same sign in **both** holdout windows, n ≥ 40, and the symbol-bootstrap 95% interval **excludes zero** |
| **H1b** | Same, with the buy-stop entry | POS × 125m × I_buystop | as H1, at a **Bonferroni** bar: the 97.5% interval excludes zero (two entries tested for one question) |
| **H2** | For **swing** names, waiting for GO is **worse** than buying at qualification | SWG × 125m and SWG × 75m, I_close | mean paired diff **≤ −0.10R** on both TFs, same sign in both windows, n ≥ 40 |
| **H3** | A **minimum stop of 1× daily ATR** under a GO entry cuts stop-outs without costing the trade | all names × 125m × I_close, stop = max-distance(structure, 1× ATR) vs the unfloored stop | initial-stop rate **≥ 10 pp lower**, mean R **not lower**, median R not worse by more than **0.25R** (the standing sweep gate), in both windows |

H3 needs one switch added to `intraday_replay.py` before the run (`--stop-floor`, default
off = byte-identical to `f214434d`). That is the only code change permitted before the run.

## Measurement rules

1. **R, never per-trade %.** R = realised % ÷ initial risk %.
2. **Per family, never pooled.** A pooled number is reported for context only.
3. **Both windows.** A result that exists in one holdout window only fails.
4. **Bootstrap by symbol** (5,000 resamples): a name appearing at several anchors shares an
   outcome history, so resampling trades would overstate certainty.
5. **n ≥ 40 per cell**, or the cell is reported THIN and **cannot pass**.
6. **Missing is excluded, never zero.** A name with no GO in its window is a non-fill, reported
   with its E0 R (what the gate gave up), never scored as 0R.
7. **Run once.** The result file is written whatever it says. A failed hypothesis is recorded
   as failed; it is not re-sliced, re-windowed or re-thresholded.

## Decision rules

| Outcome | Action |
|---|---|
| **H1 passes** | Positional names get a GO-timed entry instruction on 125m: S4's Plan row and the board's entry text say so, and the Golden Rules line is amended to *"GO times positional entries on 125m; swing names enter at qualification"*, citing this file and its result. |
| **H1 directional, not significant** (mean ≥ +0.15R in both windows, interval includes zero) | No change to S4 or the board. The shadow record keeps the cell under watch; revisit only after ≥ 60 live positional GOs have 10-session scores. |
| **H1 fails** | The Golden Rules line stands as written. Recorded here. |
| **H2 passes** | Swing names: the board says *enter at qualification, GO not required*. |
| **H3 passes** | The 1× daily-ATR floor becomes S4's and the board's stop rule for GO entries, as a separate change with its own compile. Until then the stop buffer is untouched (Jay, 2 Oct). |

Nothing ships on a hypothesis that did not pass its own bar, even if a neighbouring cell looks good.

## Known limitations, stated up front

- **Exits are daily** after the entry day; only the GO, the fill and the stop are intraday.
- **Order flow is not testable.** Footprint delta and arrival style are TradingView-only; the
  live shadow record (step D) is the only evidence for them.
- **Two regimes, unevenly:** Jul 2023 – May 2024 was largely a rising tape; Dec 2025 – Apr 2026
  includes weaker conditions. Requiring the same sign in both windows is the guard.
- **The candidate screener has changed** since step A (stage, location and RRG fixes). That is
  deliberate — the test is of the gate as it runs today — but step A and step C numbers are not
  directly comparable.

## Amendments

*(none — any amendment before the run is dated and listed here; none are permitted after it)*

## Result

*(written after the single run: `validation_runs/entry_optimizer_C/result.txt`, with the commit
hash and the date)*
