# 28 · S3 and S6 — Setup Specifications

**Status:** DRAFT for review · 8 Sep 2026
**Built for:** S5 (display) first, S4 (decision) only after measurement
**Author's note:** these are NEW setups wearing OLD names. Read §0 before anything else.

---

## 0. Provenance — what we actually recovered

Nothing. This matters, because a spec that pretends to be a restoration will be trusted
more than it has earned.

| searched | result |
|---|---|
| current S4 | comment remnants only, no live code |
| `Section4_Entry_Trigger_v5.9.pine` | nothing |
| `Section4_Entry_Trigger_v3.0.pine` | nothing |
| `_restore_20260826/pre_renumber.pine`, `pre_sep.pine` | nothing |
| git history for S4 | **none — the file is staged but never committed (`AM`, 0 commits)** |
| CLAUDE.md | one line: setups S3/S6 and the SMC liquidity-sweep block were removed for tokens, "S3 was its only reader" |

So the entire surviving record of S3 is *it read the liquidity-sweep block*, and the
entire surviving record of S6 is *it existed*. S3 below is a reconstruction from that
one clue. **S6 is an invention** — it fills a real gap in the playbook taxonomy, but no
claim is made that it resembles whatever S6 originally was.

---

## 1. S3 — Liquidity Sweep Reclaim

### The mechanic

An obvious swing low is where stops sit. Price takes them, fails to follow through, and
reclaims the level. You are buying **the failure of the break**, not the break — the
sweep is what creates the fuel, and the reclaim is what proves it was a trap rather than
a trend change.

This is the setup form of `kLIQ` ("Liq Sweep Reclaim"), which already exists in S4's
17-pattern bull battery. The pattern says *a sweep-reclaim happened on this bar*; the
setup says *this is a trade, here is where it dies, here is what it pays*.

### Gates

| gate | rule | why this and not looser |
|---|---|---|
| **Context** | Stage 1 or 2, above the 200-DMA | A trap setup, not a falling-knife setup. Below the 200-DMA a sweep is usually just supply. |
| **The level** | a pivot low with **≥2 touches** | It has to be a level *other people can see*. A one-touch low has no stops under it, so there is nothing to sweep. |
| **Sweep depth** | low pierces the level by **≤1.0×ATR** | Deeper is not a sweep, it is a breakdown. This is the single most important parameter. |
| **Reclaim** | close back above the level within **3 bars** | Slower than that and the level has been redefined, not defended. |
| **Trigger** | reclaim bar closes in its **upper half**, RV ≥ **1.0** | Confirmation before entry — the standing rule. Never the touch. |

### Plan

- **Entry:** buy-stop above the reclaim bar's high.
- **Stop:** below the sweep low. Not an ATR multiple — the sweep low *is* the thesis, and
  if price trades there the trap has become a trend.
- **Target:** the swing high that defined the range. **Fixed**, not trailed: this is mean
  reversion inside structure, not a trend entry, and the exit study is unambiguous that
  the trail belongs to trend setups.
- **Trade type:** SWING (2R/4R canon). It is a structural bounce, not a positional thesis.

### How it fails

1. **The sweep keeps going.** Handled by the depth cap and the stop.
2. **It fires constantly in a downtrend** — every lower low sweeps the last one. This is
   what the Stage/200-DMA gate exists for, and the first thing to check in the funnel if
   S3 turns out to be noisy.
3. **The reclaim is on dead volume.** The RV floor. Note the measured caveat: RV is
   time-of-day biased on intraday (48% pass at 10:30, ~18% midday), so on 75/125m this
   gate is harsher at midday than the number suggests.

---

## 2. S6 — Range Edge

### Why this one exists at all

S5 now classifies `Range / rectangle`, and **the playbook taxonomy has no entry for a
range.** A ranging name currently resolves to BREAKOUT, gets judged by a breakout's
standards, and fails the room test by construction — the ceiling is *right there*, which
is what a range is. That is precisely the incoherence the Setup row was built to surface,
and today it has no correct answer to give.

S6 is that answer: in a range, the **edge is the trade and the middle is noise**.

### Gates

| gate | rule |
|---|---|
| **Context** | S5 geometry reads `Range / rectangle` — both edges flat within `geo_flat` |
| **Age** | the range is fresh per `geo_maxage`; a stale rectangle is history |
| **Location** | price in the **lower third** of the range |
| **Trigger** | a **reversal-family** PA pattern at the lower edge |
| **Excluded** | ignition patterns. At a range low an ignition is a *breakdown*, not an entry |

### Plan

- **Entry:** buy-stop above the trigger bar's high.
- **Stop:** below the range floor.
- **Target:** the range ceiling, minus a tick. **Never beyond.** A range trade that hopes
  for a breakout is two trades stapled together, and it is how a 2R plan becomes a 0.3R
  outcome.
- **Invalidation:** the geometry stops reading as a range. Ranges resolve; when this one
  does, the setup ceases to exist — it is not "stopped out", it is void.
- **Trade type:** SWING.

### How it fails

1. **The range breaks down** — the stop, and it will happen often. Ranges resolve down as
   readily as up; this setup does not predict direction, it plays location.
2. **The classifier is wrong.** Directly dependent on the geometry read, which was the
   defect behind open item #11 (an obvious rectangle called "Symmetrical triangle" on
   APOLLOHOSP and GLAXO). S5 v1 addresses that with `geo_maxfit` ON and `geo_flat` 0.5,
   **but that fix is itself unverified.** S6 inherits every error the classifier makes.
3. **Too few instances to ever measure.** A real risk — if ranges are rare in the
   qualified universe, S6 may never accumulate enough trades to clear a gate, in which
   case it stays a display tag permanently. That is an acceptable outcome.

---

## 3. Parameters

| setup | parameter | default | note |
|---|---|---|---|
| S3 | `s3_min_touches` | 2 | fewer means no stops under it |
| S3 | `s3_max_sweep_atr` | 1.0 | **the load-bearing one** |
| S3 | `s3_reclaim_bars` | 3 | |
| S3 | `s3_rv_floor` | 1.0 | shares S4's RV time-of-day bias |
| S6 | `s6_zone_frac` | 0.33 | lower third of the range |
| S6 | inherits | `geo_flat`, `geo_maxfit`, `geo_maxage` | from the S5 geometry engine |

---

## 4. Before either one gates anything

**Both ship display-only.** Not caution — pattern. Every setup-level idea tested this
year looked obviously right beforehand and did not survive:

- Wyckoff as a GO veto ran **backwards** (vetoed cohort +5.60% vs +0.52% kept)
- Wyckoff as a score input was **null** (held-out ρ +0.013, p 0.74)
- Round-number proximity **did not replicate** on an independent sample (flipped sign)
- The S4-GO gate turned out to be a **classifier, not an entry filter** — GO-timed entry
  erased a +2.56% buy@close edge

### Test protocol

1. Emit `S3` / `S6` as their own catalyst labels — never pooled with SWG. Pooling has
   produced a false conclusion three separate times (the SWG-PB/SWG-REV artifact, the
   40% stop-out figure, June's NO-EDGE verdict).
2. Run `validation.py` with catalyst-aware windows; confirm `forward_days_used` before
   reading a single number.
3. Report in **R-multiples**, never per-trade %. A % metric structurally rewards wide
   stops and has already inverted one conclusion.
4. Gate on the pre-registered bars: plateau, OOS retains ≥50% of the IS margin, bootstrap
   stability, median not worse by 0.25R, interior optimum.
5. Minimum n before any verdict. S3 and S6 are both narrow; a 6-name cell decides nothing.

---

## 5. Open questions for Jay

1. **Is S3's reconstruction right?** The sweep-reclaim reading comes from one line of
   notes. If the original S3 was something else, this is a new setup and should be named
   as one.
2. **S6 is invented outright.** Is the range gap worth filling, or should a ranging name
   simply resolve to "no setup" and be skipped?
3. **`s3_max_sweep_atr` = 1.0** is the parameter that decides whether S3 is a trap setup
   or a knife-catcher. Your call before it is coded, not tuned after.
4. **Where do they live first?** S5 (named, no plan) or straight into S4's taxonomy as
   display-only playbooks?
