# PREREG · roleMismatch as a GO gate — the setup-coherence v2

**Written 8 Sep 2026, BEFORE the confirmatory arms are run.**
Follows `--setup_coherent` (runs `20260908_191448` control / `20260908_192530` treat),
which returned no meaningful effect and, more importantly, **could not test the idea**.

---

## 1. Why v1 could not answer the question

The coherence cell gated on `setup_pairing.PLAYBOOK[...].roles` — the pattern must be the
right KIND for the playbook. Measured outcome:

| | control | treat |
|---|---:|---:|
| GOs | 152 | 138 |
| anchor avg α | −1.12% | −0.96% |
| anchor hit | 33.3% | 26.7% |

It blocked **14 of 152 GOs (9.2%)**, and that ceiling was structural, not empirical:

- **PULLBACK accepts all three roles**, so `_accepted_roles` is a no-op there by
  construction — and pullbacks are a large share of the bull book.
- **BREAKOUT requires ignition**, and most GO bars *are* ignitions.
- So it only ever bit on ACCUM and REVERSAL, a small minority.

Fourteen blocked trades cannot move a 145-trade result in either direction. The honest
verdict on v1 is therefore **"the implementation was too weak to test the idea"**, not
"setup coherence does not help". This document tests the idea properly.

## 2. The rule — Pine's, ported, not invented here

S4 already computes the missing case and shows it as the `⚠role` tag:

    roleMismatch = z_inDZ and pa_ign and not (pa_rev or pa_con or kVCP)

An **ignition** pattern — a breakout's evidence — firing while price sits **inside a fresh
demand zone**. A breakout's trigger in a pullback's location. It is a *location* test,
which is exactly why the accepted-role set could not express it, and `_location_at` was
already being called on every GO bar, so the replay can.

`kVCP` is exempt: a VCP breakout out of a base inside demand is the setup working. That
exemption is Pine's, carried over unchanged.

The tag is **display-only on the chart** (per the standing note: *"Tag first, gate only
after measurement"*). This is that measurement.

## 3. ⚠ INSTRUMENT CHECK — run first, and it changes what this test can claim

Per the standing rule the instrument is checked before the result. On the control run's
152 GOs:

| | count |
|---|---:|
| GOs with a location src of `zone` or `pivot` | **145 of 152** |
| ignition present | 136 |
| ignition with no reversal alongside | 104 |
| roleMismatch (upper bound) | **104 = 68.4%** |

**`z_inDZ` is near-universal in this replay because the GO gate ALREADY REQUIRES
location.** The rule therefore degenerates here to *"an ignition fired with no reversal or
contraction alongside it"*.

That is recorded now, before the run, because it bounds the claim:

- This cell measures a **pattern-role filter**, not the role-vs-location filter the tag
  represents on a live chart, where a GO can also pass on S/R or AVWAP.
- A pass therefore **does NOT validate S4's `⚠role` tag** and does not license promoting
  it from display to gate. It would say only that ignition-only triggers underperform.
- The bite is an **upper bound**: `GO_Triggers` carries no contraction patterns (they are
  not triggers), so some flagged bars will carry a coil the CSV cannot see and will pass.

## 4. Why the existing 152 GOs cannot be the answer

Splitting those same 152 by the rule gives blocked −1.43% / kept +0.07%, a 1.50pp gap.
**That number is post-hoc on the sample the gate was designed against and is not
evidence.** It is written down here so it cannot later be presented as a result, and so
the confirmatory arms can be compared against a stated prior.

## 5. Design

Both arms at **36 months**, so anchors exist that this thread has never examined:

    python validation.py --months 36 --universe nifty500 --screener bull \
                         --gate s4go --catalyst_windows --bootstrap_n 10000 [--role_mismatch]

Two readings, both reported:
- **pooled** over all 36-month anchors;
- **fresh only** — anchors absent from `validation_20260908_191448_details.csv`, i.e. never
  looked at in this thread.

Instrument gate before any result is read: `role_mismatch` present in both metas,
`forward_days_used` showing 60/120/180 (never the 30-day default), and a non-zero
difference in GO counts between the arms. A run failing any of these is discarded.

## 6. Hypothesis

**H5** — blocking ignition-only triggers inside demand raises mean matched-horizon alpha
on GO-timed entries, without costing more deployment than it earns.

## 7. Adoption rule — fixed now

Adopt ONLY if ALL of:

- **A · the gate bites** — blocks ≥ 15% of control GOs (v1's 9% was the failure mode).
- **B · treat beats control by ≥ +1.0pp** on mean matched-horizon alpha.
- **C · symbol-block bootstrap CI95 on (treat − control) excludes zero.** Trade-level
  resampling is not acceptable.
- **D · the sign holds in both chronological halves.**
- **E' · deployment (mean × retention) beats the control arm.** A gate that lifts the mean
  by shrinking the book has not improved anything.
- **F · it holds on the FRESH anchors alone**, not only pooled.

**Falsifier:** any of A–F failing means ignition-only triggers are not the leak, the
`⚠role` tag stays display-only, and `--role_mismatch` stays off by default.

## 8. Honest prior

The direction looks strong on the discovery sample (1.50pp, 68% bite) and the mechanism is
one Jay has independently described — *don't buy the breakout inside the pullback*. Against
that: it is a large gate on a book whose base rate is already negative (control anchor
avg α −1.12%), and a filter that removes two thirds of trades has many ways to look good on
survivors. **E' is the criterion most likely to bite**, exactly as it was for the RV band.

## 9. If it fails — the v2 path, decided in advance

If H5 fails, the next question is whether the discriminator is the ROLE at all or simply
**which patterns** the ignition set contains. `POWER_PLAY_STRONG_CLOSE` and `POCKET_PIVOT`
are 71% of all GO triggers between them; a per-pattern forward-alpha table would say
whether "ignition" is carrying information or is just a label wrapped around two common
detectors. That is a cheaper test than this one and it is the correct next step, because a
role filter that works only through one detector is not a role filter.

---

# OUTCOME · recorded 9 Sep 2026

## First A/B pair — DISCARDED before any result was read

`20260908_231202` / `20260908_234147` failed the section-5 instrument gate. The runner
omitted `--qualify`, which **defaults to `armed`** — the Stage-2+RS set, not the strict
catalyst set this test extends: ~300 picks per anchor instead of ~26, no catalyst labels,
so `forward_days_used` fell through to per-pattern horizons (15/20/30/45/90). Same anchor,
2024-08-15: 314 picks vs 26. The arms were consistent with each other, so the internal
comparison was not corrupt — it was simply not the registered test. `--qualify catalyst` is
now pinned in the runner and the scorer fails any pair that disagrees on it.

## Confirmatory pair — `20260909_001033` (control) / `20260909_002932` (treat)

Instrument: qualify `catalyst` both · flags `False` / `True` · forward windows 60/120/180
(one stray 30-day row out of 331) · gate blocked 222 of 354 GOs.

| | control | treat |
|---|---:|---:|
| GOs | 354 | 132 |
| trades | 331 | 121 (keep 36.6%) |
| mean matched α | **−0.70%** | **+0.09%** |
| median | −2.91% | −2.42% |
| win | 32.6% | 33.9% |
| deployment (mean × retention) | −0.70% | **+0.03%** |

| criterion | value | |
|---|---|---|
| A · bites ≥ 15% | 62.7% | **PASS** |
| B · edge ≥ +1.0pp | +0.79pp | FAIL |
| C · CI95 excludes zero | [−0.51, +2.16], P 87.6% | FAIL |
| D · both halves same sign | +1.33 / −0.36 | FAIL |
| E' · deployment beats control | +0.03 vs −0.70 | **PASS** |
| F · holds on fresh anchors | +1.06pp (12 unseen anchors) | **PASS** |

**VERDICT: DO NOT ADOPT** — `role_mismatch` stays off by default. Three of six, and the
three that failed are the ones the rule exists to protect against.

## This is UNPROVEN, not disproven — and the distinction is load-bearing

Every point estimate is positive except a 42-trade OOS half (−0.36pp) and a 7-trade
POS-ACCUM cell. The gate flips the book's sign (−0.70% → +0.09%) and passes **E'**, the
deployment criterion that killed the RV band. It is the first intervention in this thread
to clear both A and E'. What it does not do is clear the significance bar on 331 trades.

By family (forward window as the family proxy — the details CSV carries no `Catalyst`):

| family | control | treat | keep | edge |
|---|---:|---:|---:|---:|
| SWG (60d) | −1.28% / win 27.9% | −0.08% / win 36.8% | 41.2% | **+1.20pp** |
| POS-BO/WYC (120d) | −0.03% / win 36.2% | +0.79% / win 31.1% | 32.6% | +0.82pp |
| POS-ACCUM (180d) | −0.68% | −3.08% (n=7) | 25.9% | −2.40pp |

The effect is concentrated in **SWG**, the documented drag family, where it lifts the win
rate 27.9% → 36.8%. POS-ACCUM's n=7 cannot be read.

## The v2 diagnostic (section 9) — run, and it answers the question

Per-pattern forward alpha on the control arm, and the role ladder the gate keys on:

| cohort | n | mean α | win |
|---|---:|---:|---:|
| ignition only | 241 | **−1.17%** | 31.1% |
| ignition + reversal | 60 | +0.20% | 38.3% |
| reversal only | 29 | **+1.45%** | 34.5% |

Monotone. **More reversal evidence is better**, and the ordering is not an artifact of one
detector: every individual ignition detector is negative (POWER_PLAY_STRONG_CLOSE −0.62%
n=226, POCKET_PIVOT −0.79% n=162, **BREAKOUT_CONFIRMED −6.53% with 0 wins in 14**), while
the best single detector is THREE_BAR_REV (+0.51%, 44.8% win). So "ignition" is carrying
information rather than standing in for POWER_PLAY and POCKET_PIVOT — section 9's question
is answered, and answered in the rule's favour even though the rule did not clear the bar.

**Gap found in passing:** `OUTSIDE_BAR_BULL` belongs to no role group in either Pine or
`pa_patterns` — consistently, so it is not drift — yet it fires on 41 of 331 GOs at −2.16%
and 19.5% win, the second-worst detector. It is roleless, so `roleMismatch` can never block
it. In this sample it fires alone only once, so it is not a live hole; it is a question
about the role map, not a bug.

## What would settle it

Not another pass on this sample. Three things, in order of value:

1. **More anchors.** The gap is +0.79pp with a CI half-width of ~1.3pp. n=331 control GOs
   is the binding constraint, not the effect size.
2. **Test the POSITIVE form.** The rule as written is a veto on ignition-only. The ladder
   above says the informative variable is *reversal evidence present*, which is the same
   cut stated the other way round — but as a positive filter it can be graded (how much
   reversal evidence) rather than binary, and graded filters have more power per trade.
3. **`BREAKOUT_CONFIRMED` on its own.** 0 wins in 14 GO-timed trades is either a real
   defect in that detector or a 14-trade coincidence. It is cheap to check and it is a
   pattern S4 currently treats as an ignition in good standing.

---

# ADDENDUM · the GRADED POSITIVE form — ladder read 9 Sep 2026, threshold registered

Control run `20260909_055448` (36mo, nifty500, bull, s4go, qualify catalyst,
catalyst-aware). 331 trades, 27 anchors, windows 60/120/180 (one stray 30).
`Rev_N` / `Con_N` / `NonIgn_Score` emitted on every trade; nothing gated.

## The ladder

| NonIgn_Score | n | mean α | median | win |
|---:|---:|---:|---:|---:|
| 0 | 234 | −1.31% | −3.04% | 30.3% |
| 1 | 64 | +0.41% | −2.33% | 34.4% |
| 2 | 30 | +1.46% | −1.82% | 46.7% |
| 3 | 3 | +1.42% | −9.54% | (thin) |

Monotone across the three levels with n ≥ 25, and the ordering **survives trimming the
top two alphas from each level** (−1.55 / −0.71 / −0.22).

## What the ladder is actually made of — read this before the pass

Two things are true at once and only one of them is good news.

**The ordering is real.** It holds after trimming, and the reversal-count axis it replaces
does not (0/1/2 → −1.18 / +1.33 / **−1.25**, non-monotone, unchanged).

**The absolute positive means are not.** Every trimmed level mean is still NEGATIVE. The
positive figures are big-winner-carried — the same profile documented across this book.

And the level-2 cell decomposes badly:

| subcell | n | mean α |
|---|---:|---:|
| Rev_N=2, Con_N=0 | 25 | **−1.25%** |
| Rev_N=1, Con_N=1 | 2 | +18.85% |
| Rev_N=0, Con_N=2 | 3 | +12.40% |

**Five trades averaging +14.98% are what lift level 2 above level 1**, one of them at
+30.5%. Contraction fires on only **3.0%** of trigger bars, so the half that makes this
score different from the ruled-out reversal count barely exists. Remove every
contraction-carrying row and the ladder reverts to non-monotone (0/1/≥2 → −1.31 / +0.73 /
−0.96).

**A criterion of mine failed here and is now fixed.** The resolution rule was "3 levels
with n ≥ 25, monotone". Level 2 cleared n=30 while its entire ordering rested on 5 rows —
a cell can pass a count floor and still be one outlier wide. `score_nonign_ladder.py` now
also reports top-2-trimmed level means and requires the ordering to survive them.

## Conclusion on GRADING, and the threshold that follows

**There is no usable graded structure.** Thresholds on all 331 trades:

| gate | n | keep | mean | edge | deployment |
|---|---:|---:|---:|---:|---:|
| ≥1 | 97 | 29.3% | +0.77% | +1.47pp | **+0.22%** |
| ≥2 | 33 | 10.0% | +1.45% | +2.15pp | +0.14% |
| ≥3 | 3 | — | degenerate | | |
| off | 331 | 100% | −0.70% | — | −0.70% |

Above 1 the retention collapses and **deployment falls**, and the level-2 advantage is the
5 rows above. So the informative cut is **0 vs ≥1** — binary after all, exactly as the
reversal-count axis was. Grading bought the monotonicity, not a second useful level.

**Registered threshold: `--nonign_min 1`.** Selection freedom is minimal: ≥2 loses on
deployment and ≥3 is degenerate, so 1 is the only non-degenerate choice. That the threshold
was read off this control run is stated plainly rather than dressed up.

## Why this is worth an arm when roleMismatch already failed

On the same 331 trades, at the same time, with the same instrument:

| | keep | mean | edge | deployment |
|---|---:|---:|---:|---:|
| roleMismatch | 36.6% | +0.09% | +0.79pp | +0.03% |
| **NonIgn ≥ 1** | 29.3% | **+0.77%** | **+1.47pp** | **+0.22%** |

And on the 12 fresh anchors: keep 27.4%, mean **+1.83%** vs −0.46% unfiltered, edge
+2.29pp, deployment +0.50% vs −0.46%.

The two rules differ in exactly two ways: NonIgn ≥ 1 has **no location condition** and no
VCP exemption. So the readable hypothesis is that **the location half was diluting it** —
the informative variable is "is there non-ignition evidence on the trigger bar", not "is
there an ignition in the wrong place". That is a different claim from the one already
tested, which is why it earns its own arm.

## H6 and the adoption rule — fixed before the arm runs

**H6** — requiring ≥1 piece of non-ignition evidence on the trigger bar raises mean
matched-horizon alpha AND deployment on GO-timed entries.

Adopt ONLY if ALL of: **A** bite ≥ 15% · **B** edge ≥ +1.0pp · **C** symbol-block CI95 on
(treat − control) excludes zero · **D** sign holds in both chronological halves ·
**E'** deployment beats control · **F** holds on the fresh anchors alone.

**D is the one to watch.** roleMismatch failed it (+1.33 / −0.36) and the RV band failed it
twice. If the ordering above is real rather than a property of these 27 anchors, D should
hold. If D fails again on a third consecutive intervention, the honest reading is not "this
gate is bad" but **"a 331-trade GO-timed book cannot resolve a 1pp effect"** — which is a
statement about the sample, and the next move would be more anchors, not another gate.

---

# OUTCOME · H6, the graded positive arm — 9 Sep 2026

`20260909_063606` (`--nonign_min 1`) against control `20260909_055448`. Instrument:
`nonign_min` 0 → 1, qualify `catalyst` both, windows 60/120/180, gate blocked 225 of 354.

| | roleMismatch | **NonIgn ≥ 1** |
|---|---:|---:|
| bite | 62.7% | 63.6% |
| keep | 36.6% | 36.3% |
| mean α | +0.09% | +0.12% |
| edge | +0.79pp | +0.82pp |
| CI95 | [−0.51, +2.16] | [−0.49, +2.20] |
| D halves | +1.33 / −0.36 | +1.38 / −0.36 |
| fresh | +1.06pp | +1.12pp |

**Statistically the same result.** Dropping the location condition changed nothing, because
location is near-universal in this harness (section 3) — the two rules select almost the
same trades. 3 of 6, same three failing. H6 not adopted.

## But the arm contradicted the ladder, and THAT is the finding

The ladder predicted keep 29.3% at **+0.77%**. The arm delivered keep 36.3% at **+0.12%**.
A gate cannot *raise* retention, so the two are not the same operation:

| treat trade vs its control counterpart | n | treat α | control α |
|---|---:|---:|---:|
| same GO bar | 97 | +0.77% | +0.77% |
| **LATER GO bar** | 22 | **−2.60%** | −1.36% |
| no counterpart | 1 | −3.29% | — |

**A blocked bar does not drop the name — the scan continues and takes a later entry.**
Median defer 8 days, p75 26, max 42, and those 22 trades cost **−1.23pp** versus entering
at the original bar. They drag the arm from +0.77% to +0.12%.

This is the confirmation-wait tax measured a third time (23-Jul entry A/B, the GO-timing
result, now here), and isolated cleanly for the first time: **the same signal is worth
+1.47pp as SELECTION and +0.82pp as an in-scan VETO.** Half the value is given back by
re-entering later.

## The ABANDON variant — 5 of 6, and the first PASS on D in this thread

Blocking the NAME for the anchor instead of deferring is, by construction, post-hoc
selection on the control arm (each control row has exactly one GO bar, the first
qualifying one, so dropping rows whose GO bar scored 0 IS abandon-on-block). No extra run
needed:

| | all 30 anchors | fresh 12 anchors |
|---|---:|---:|
| keep | 29.3% (n=97) | 27.4% (n=51) |
| mean α | **+0.77%** vs −0.70% | **+1.83%** vs −0.46% |
| edge | **+1.47pp** | **+2.29pp** |
| CI95 | [−0.12, +3.17] · P 96.5% | [−0.47, +5.41] · P 94.6% |
| deployment | +0.22% vs −0.70% | +0.50% vs −0.46% |

| criterion | | |
|---|---|---|
| A bite 70.7% | PASS |
| B edge +1.47pp | **PASS** |
| C CI95 [−0.12, +3.17] | FAIL — by 0.12pp, P 96.5% |
| D **+2.30 / +0.44, both positive** | **PASS — the first in this thread** |
| E' +0.22 vs −0.70 | **PASS** |
| F fresh +2.29pp | **PASS** |

D is the criterion that killed the Wyckoff filter and the RV band (twice) and that both
veto arms failed. It passes here. C misses by 0.12pp on the sample the threshold was read
from, which is weak evidence either way.

**Still not an adoption** — C fails and the threshold is post-hoc. But the direction is now
consistent across every cut, and the design lesson is independent of the statistics.

## What this changes in practice

**Use non-ignition evidence as a SELECTION/RANKING input, never as a scan-forward veto.**
On the GM board that means a column and a sort key, not a gate: rank the day's qualified
names by whether the trigger bar carries a turn or a coil, and take from the top. A gate
that says "not this bar, keep looking" actively harms the book, because the replacement
entry is 8+ days later and worse.

That is a change to a live surface, so it needs its own registration before shipping. It is
NOT covered by this document.

## Next, and the honest limit

The binding constraint is the sample: 331 control GOs cannot resolve a ~1.5pp effect with a
CI half-width of ~1.6pp. Three interventions have now landed in the same place — positive
point estimate, interval touching zero. The next move is **more anchors** (a 60-month run,
or nifty500 → a wider universe), not a fourth gate variant. Registering another threshold
against this sample would be the multiple-testing problem the whole thread is trying to
avoid.

---

# PREREG · the 60-month confirmatory — written 9 Sep 2026, BEFORE the run

## What is under test, and why it needs no treat arm

The **ABANDON variant**: block the NAME for that anchor when its first qualifying GO bar
carries no non-ignition evidence, rather than deferring to a later bar. Each control row
holds exactly one GO bar — the first qualifying one — so dropping rows whose GO bar scored
0 **is** abandon-on-block, exactly. One instrumented control run therefore scores it; a
second arm would only re-measure the DEFER behaviour already shown to give back half the
value.

    python validation.py --months 60 --universe nifty500 --screener bull \
                         --gate s4go --qualify catalyst --catalyst_windows \
                         --bootstrap_n 10000

## Everything is fixed before the data exists

- **Threshold: `NonIgn_Score >= 1`.** Carried over unchanged from the 36-month ladder. Not
  re-read, not re-optimised, and no other threshold will be scored.
- **The confirmatory set is the anchors ABSENT from `20260909_055448`** (the 30 anchors of
  the 36-month run, roughly 2023-08 onward). Those are already spent — they discovered the
  ladder, chose the threshold, and produced the +1.47pp. Anything from 2021-08 to 2023-07
  is new. The exclusion is mechanical.
- **Rule A-F as already written**, unchanged, including C at 95%.
- Instrument first: anchor count, picks per anchor, `forward_days_used` ∈ {60,120,180}, and
  `NonIgn_Score` present on every row. A run failing any of these is discarded, as the
  first roleMismatch pair was.

## Hypothesis

**H7** — on anchors never examined, requiring ≥1 piece of non-ignition evidence on the
trigger bar (abandoning the name otherwise) beats the unfiltered book on mean
matched-horizon alpha AND on deployment.

## Why this run and not another variant

Three interventions have now produced the same shape: positive point estimate, interval
touching zero, on 331 control GOs against a CI half-width of ~1.6pp. That is a POWER
problem, not a specification problem, and the only honest response is more anchors. Testing
a fourth threshold against the same 331 trades would be exactly the uncorrected
multiple-testing this desk already carries as its largest statistical liability.

## Honest prior

For: the direction has held on every cut so far, the abandon variant passed D (+2.30 /
+0.44) where two veto arms failed it, and the threshold is genuinely frozen.

Against: 2021-2023 is a different regime, and this book's alpha has already been shown to
be regime-amplified (POS-BO returns ~2.3x the index in a rising tape and roughly matches it
otherwise). A period effect could move the result in either direction for reasons that have
nothing to do with the filter. And the deeper history may simply be thinner — if the early
anchors produce few picks, the power problem is not solved and the correct answer is to say
so rather than to read a small cell.

**Falsifier:** if the edge on the fresh anchors is not positive, the non-ignition signal is
a property of 2023-2026 and not of the strategy, and the ranking recommendation is withdrawn.
