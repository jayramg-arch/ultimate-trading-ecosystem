# Pre-registration — does the recovery fundamental gate survive point-in-time data?

**Written 24 September 2026, BEFORE any historical fundamental was scraped or scored.**
The analysis runs **once**.

## Why

The 24-Sep audit (AUD-EVD-01) found that the recovery backtest pins prices to each anchor
date but reads fundamentals **live** — `recovery_screener._fundamental_row` scrapes today's
screener.in page and yfinance `.info`. So every recovery backtest scored 2024 anchors with
2026 balance sheets. The claim this re-tests is the one Doc 09 §14 calls *"the
best-evidenced gate change in the repo"*: RFF ≥ 5 of 6 separated outcomes by **+2.40pp**
matched alpha, CI [+0.92, +3.88], and strengthened out of sample. A company that recovered
after the anchor tends to show better fundamentals *today*, which biases exactly that
comparison in the gate's favour.

## Data

- **Fundamentals:** screener.in company pages, fetched once and cached to disk
  (`data/screener_pages/`), so the test is reproducible. Tables used: annual Profit & Loss,
  quarterly results, annual Balance Sheet, annual Cash Flows.
- **Point-in-time with a publication lag:** a figure counts at anchor date t only if its
  period was published by t. Quarterly results: period end **+ 45 days**. Annual statements
  (FY ending March): **+ 60 days** (i.e. usable from 30 May). Anything later is invisible
  at t.
- yfinance was ruled out: its quarterly history holds a median of 5 quarters, earliest
  Sep 2024, and rolls forward — no trailing-year figure exists for anchors before ~Aug 2025.

## The five checks (Tier A minus current ratio)

| check | rule | source, as of t |
|---|---|---|
| NI | net profit > 0 | sum of the last 4 published quarters |
| FCF | free cash flow > 0 | last published annual Cash Flows ("Free Cash Flow" row, else OCF − capex) |
| ICR | operating profit / interest > 3.5 | last 4 published quarters |
| D/E | borrowings / (equity capital + reserves) < 2 | last published annual Balance Sheet |
| ROA | net profit / total assets > 5% | last published annual P&L and Balance Sheet |

**Current ratio is out of scope**: screener.in's balance sheet has no current / non-current
split, so it cannot be formed point-in-time. The live gate is 5 of 6; the analogue here is
**at most one miss of five, i.e. ≥ 4 of 5** (primary). ≥ 5 of 5 is reported as secondary.
A name with fewer than 4 of the 5 checks computable is INSUFFICIENT and excluded, never
scored as a fail.

## The trade set

Recovery replay, same parameters as the 20-Sep run (24 months, Nifty 500, catalyst
windows, CB-Watch excluded), **with the RFF gate switched off and live fundamentals
disabled**, so every technically-qualified recovery pick is kept regardless of its books.
Point-in-time RFF is then attached to each (symbol, anchor). Two env flags, default off,
make the replay do this; with them unset it is byte-identical to before.

## Hypothesis

**H1 — the point-in-time gate still separates.** Picks with RFF_PIT ≥ 4/5 beat picks with
≤ 3/5 on matched alpha.

- Statistic: difference in mean matched alpha, high − low.
- Pass: **≥ +1.0pp** in IS **and** OOS (same chronological split and 45-day purge the OOS
  gate uses), symbol-block bootstrap CI (5,000) excluding zero on the pooled difference,
  and the median difference not negative.
- n ≥ 40 in each of the four cells (high/low × IS/OOS), else THIN and cannot pass.
- Also reported, not decisive: the same split in R-multiples, per family (REV-CB, REV-EARLY,
  REV-RS, WYC-*), and the 5/5 secondary cut.

## Controls

- **Coverage print first:** how many (symbol, anchor) pairs get a point-in-time score,
  per anchor. If coverage in either half is under 60%, the result is reported as
  UNDERPOWERED rather than read.
- **Placebo:** RFF_PIT shuffled across picks within each anchor. Any pass is a bug.

## What a result means

- **PASS** — the gate's evidence survives look-ahead removal; the RFF floor stays and Doc 09
  can cite this run instead.
- **FAIL** — the +2.40pp was substantially look-ahead. The gate becomes doctrine rather than
  evidence (it may still be kept on judgement — "fundamentally strong beaten-down names" is
  Jay's thesis), and Docs 09 and 25* are corrected.
- Either way the 5-check measure is not the live 6-check gate; the difference is the current
  ratio, stated above.

## Stopping rule

Runs **once**. No re-slice, no changed lag, no changed threshold. Result recorded here.

## Result

**Run 24 Sep 2026, once** (`validation_runs/_rff_pit_run.log`, trades in `_rff_pit_trades.csv`).
Input: recovery replay `20260924_122149` with `RECOVERY_NO_FUNDAMENTALS=1` (RFF gate off, no live
fundamentals), 24 months, nifty500, catalyst windows verified 90/120, CB-Watch excluded, 445 picks.
Coverage 99.6% IS / 100% OOS (443 scored, 2 no page). Placebo (scores shuffled within anchor):
FAIL, CI [−3.53, +1.12], as it should.

| cut ≥4 of 5 (primary) | high α | low α | Δ mean | Δ median |
|---|---:|---:|---:|---:|
| IS (180 / 65) | −0.49% | +0.08% | **−0.57pp** | +1.03 |
| OOS (123 / 51) | +0.36% | −0.42% | +0.78pp | −0.67 |
| ALL (321 / 122) | −0.07% | −0.28% | +0.22pp | −0.36 |

Pooled CI95 [−2.07, +2.38]. **Verdict: FAIL** — the IS difference has the wrong sign, neither
window reaches +1.0pp, the CI straddles zero and the median difference is negative. The
secondary cut (5 of 5) also fails: IS −1.02pp, OOS +0.79pp, CI [−2.71, +1.32].

**What this says:** once look-ahead is removed, the RFF fundamental gate shows no measurable
effect on recovery outcomes — it neither helps nor hurts at 90–120 days. The earlier "RFF ≥ 5
is the only near-breakeven bucket" reading came from live fundamentals applied to historical
anchors and does not survive point-in-time data. The whole technically-qualified pool, gate
off, runs about −0.1% matched α — the same neighbourhood as the gated book.

**What it does NOT say:** that the gate should come out. A null is not evidence of harm, and
the gate still does the job Jay set it for (only fundamentally strong names). It says the gate
is a *quality preference*, not a measured edge — so it should not be sold to the reviewer or the
docs as one. Current ratio (the sixth check) was not rebuildable and is not in the test.
