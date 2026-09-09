# PREREG · The RV band as a DAILY SELECTION filter — confirmatory test

**Written 8 Sep 2026, BEFORE the confirmatory sample is generated.**
Third and final registration in the Wyckoff → RV thread. Supersedes nothing; the
intraday verdict (`rv_floor` unchanged) stands and is not reopened.

---

## 0. Full accounting of every test in this thread — the multiplicity problem

This desk's largest documented statistical liability is **uncorrected multiple testing**
(98 validation runs, 4 alpha-selected sweeps, 3 A/Bs whose winners became defaults, zero
Bonferroni/FDR/PBO). This thread has itself now run **seven** tests:

| # | test | result |
|---|---|---|
| 1 | Wyckoff veto — reproduction | reproduced; headline cell n=26, below its own floor |
| 2 | Wyckoff as a positive filter | FAILED — reverses out of sample |
| 3 | Wyckoff redundant with RV? | FAILED — corr +0.052, independent |
| 4 | RV band, daily | A-D pass, E fails (E was mis-specified) |
| 5 | RV band, intraday, all bars | FAILED — flat |
| 6 | RV band, intraday, PA-trigger bars | FAILED — shape points the OTHER way |
| 7 | RV regime partition | hypothesis falsified — shape stable in every regime |

The band is the one survivor of seven. **A survivor of seven tests needs a higher bar than
a single hypothesis would**, because the probability that at least one of seven cuts looks
good by chance is not small. That is priced into §4 rather than mentioned and forgotten.

## 1. Why the existing 464-trade run CANNOT be the confirmatory sample

`validation_20260726_225547` has now been used to **discover** the effect (post-hoc
tercile split), **test** the band, and **partition** it by regime. Testing on it again is
not confirmation — it is the fourth look at one sample.

Re-running the same anchors with different code (e.g. `20260819_112959`, `20260729_175838`)
does **not** fix this. Those are the same period, same universe, largely the same names,
re-scored after code changes. They are re-measurements, not independent samples.

## 2. The confirmatory sample — fresh anchors, decided before it is generated

Generate a validation run over a **longer window (36 months)** and evaluate the band on
**only the anchors NOT present in the 24-month run** — roughly 12 earlier anchors that
have never been looked at in this thread.

    python validation.py --months 36 --universe nifty500 --screener bull \
                         --catalyst_windows --bootstrap_n 10000

The scoring script must **drop every anchor whose date appears in
`validation_20260726_225547_details.csv`** before computing anything. That exclusion is
mechanical and is part of the test, not a judgement call made afterwards.

**Instrument check first, per the standing rule:** picks per anchor, family distribution,
and `forward_days_used` (must show 60/120/180, never the 30-day default) are verified
BEFORE any result is read. A zero-pick or wrong-window run is discarded, not interpreted.

## 3. Hypothesis

**H4** — On qualified daily bull picks from anchors never previously examined, the band
`0.8 <= Rel_Vol <= 1.5` produces a higher mean matched-horizon alpha than the unfiltered
pick set, AND a higher deployment (mean x retention).

Arms: **no filter** (every pick) vs **band** (picks inside the band only).

Note the comparison has changed from the earlier tests. There is no "floor" arm here,
because the daily selection layer does not currently apply an RV floor at all — the
relevant question is band-versus-nothing, not band-versus-floor.

## 4. Adoption rule — tightened for multiplicity, stated now

Adopt the band as a daily selection filter ONLY if ALL of:

- **A · n >= 100** picks inside the band on the fresh anchors.
- **B · band beats no-filter by >= +1.5pp** on mean matched-horizon alpha.
  *Raised from +1.0pp because this is the survivor of seven tests (§0).*
- **C · symbol-block bootstrap CI95 on (band − all) excludes zero at 99%, not 95%.**
  *Tightened for the same reason. Trade-level resampling remains unacceptable.*
- **D · the sign holds in both chronological halves of the fresh anchors.**
- **E' · deployment (mean x retention) beats the no-filter arm.**
  Replaces the mis-specified retention floor from the first registration; it cannot be
  satisfied by pruning to a prettier mean on a smaller book.
- **F · the humped SHAPE reproduces** — the peak bucket must be 0.8-1.0 or 1.0-1.5, with
  both tails below it. A band that "works" without the shape behind it is a threshold
  that happened to land well, not the effect this thread described.

**Falsifier:** any one of A-F failing means the band is a property of the original 464
trades and not of the strategy. In that case the correct entry in the notes is *"the RV
inverted U did not replicate out of sample"*, and no selection layer changes.

## 5. What changes if it PASSES — and what does not

**Does change:** the screener / board gains an RV band as a **hard filter or a ranking
input** on daily picks. Which of those two is a SEPARATE decision — this test measures the
hard filter, because that is what was measured throughout. Using it as a ranking tiebreak
is a different intervention with different behaviour and would need its own test.

**Does NOT change:** `rv_floor` in S4. The intraday tests (#5, #6) settled that
independently, and on the PA-trigger population the relationship runs the other way. A
daily-selection result never licenses an intraday gate change — that conflation is the
specific error §6 of the first registration was written to prevent.

**Also does not change:** anything about position sizing, stops or exits. This is a
selection test only.

## 6. Honest priors, recorded before the answer

Three things argue the band is real: it was located from an independent sample, it
strengthened out of sample on the chronological split, and its shape is stable across
every regime partition.

Three things argue caution: the peak buckets are thin (16-26 trades per regime slice), 20
serially-correlated anchors is a small sample however it is cut, and it is the one survivor
of seven tests in a single afternoon.

I do not have a confident expectation either way, and that is the correct state in which
to run a confirmatory test.

## 7. If it fails — the v2 path, decided in advance

If H4 fails on fresh anchors, the next question is not about RV at all. It is whether the
0.8-1.5 band is standing in for **volume dry-up as a setup property** rather than a
threshold: POS-ACCUM wants contraction, POS-BO wants expansion, and mid-RV may simply be
where accumulation-type setups sit. That is `PREREG_rv_band.md` §7, still unexecuted, and
it would be tested per-family rather than as a global band.

If that also fails, the honest conclusion is that RV carries no selection information
beyond what the catalyst gates already encode — which is a real finding about the funnel,
and considerably more useful than another null.

---

# OUTCOME · recorded 9 Sep 2026 — the band did NOT replicate

Run `20260908_230157` (36mo, nifty500, bull, catalyst-aware, bootstrap 10k).
Instrument: forward windows 60/120/180 (4 stray 30-day rows in 1010), `Rel_Vol` on
every row, 31 anchors of which **20 were dropped as already examined** and **11 are
fresh**. 453 trades scored.

## The two cells side by side — this is the whole result

| | no filter | band 0.8-1.5 | edge |
|---|---:|---:|---:|
| **20 anchors already looked at** (reference, NOT the test) | +0.13% | **+2.94%** | **+2.81pp** |
| **11 FRESH anchors** (the test) | **+3.43%** | +2.43% | **−1.01pp** |

The band beats the field by 2.81pp on the sample it was discovered on, and **loses by
1.01pp on anchors never examined.** That is what a post-hoc artifact looks like when you
finally give it a clean sample.

| criterion | value | |
|---|---|---|
| A · n ≥ 100 in band | 118 | PASS |
| B · edge ≥ +1.5pp | −1.01pp | **FAIL** |
| C · CI99 excludes zero | [−4.39, +2.48], P 21.3% | **FAIL** |
| D · sign holds in both halves | −1.38 / −1.68 | **FAIL** |
| E' · deployment beats no-filter | +0.63 vs +3.43 | **FAIL** |
| F · humped shape reproduces | peak moved to 0.5-0.8 | **FAIL** |

**VERDICT: DO NOT ADOPT.** Per section 4 the correct entry is *"the RV inverted U did not
replicate out of sample"*. No selection layer changes. `rv_floor` untouched — it was never
in scope.

**D is the decisive one.** It reverses in BOTH halves of the fresh anchors, which is the
criterion that killed the Wyckoff positive filter, and it is the criterion the earlier
chronological split appeared to pass (+2.58pp IS / +5.07pp OOS) — on the discovery sample.
A split inside one sample is not an out-of-sample test, and this pair of results is the
cleanest demonstration of that in the whole thread.

**F failed structurally, not marginally.** The fresh buckets are not humped at all:

    <0.5 +0.72 | 0.5-0.8 +5.74 | 0.8-1.0 +5.27 | 1.0-1.5 +0.57 | 1.5-2.5 +4.64 | 2.5+ +4.71

`1.0-1.5` — half the proposed band — is the **second-worst** bucket, while both high-RV
tails are strong. The shape the whole thread was built on is gone.

## The v2 (section 7) — run immediately, and it explains the artifact

Section 7 predicted the band might be standing in for **volume dry-up as a setup property**
rather than a threshold. Measured per family on the fresh anchors, the premise is confirmed
in the strongest possible form — **median RV differs ~3× across families**:

| family | n | median RV | p25–p75 | band edge |
|---|---:|---:|---|---:|
| SWG (60d) | 206 | **0.53** | 0.41–0.72 | −2.14pp |
| POS-BO/WYC (120d) | 215 | **1.64** | 1.13–2.52 | −1.95pp |
| POS-ACCUM (180d) | 31 | **0.68** | 0.53–0.89 | −0.89pp |

**The pooled RV distribution is a mixture of three families that live in different places
on the RV axis.** The pooled inverted U was composition: the high-RV tail is almost purely
POS-BO (median 1.64) which has high alpha, and the low-RV bulk is SWG. So a global RV
threshold is a **family filter wearing a volume filter's clothes** — which is precisely
what section 7 called the catalyst-mix artifact, written before any of this was measured.

The band is negative **within every family**, so there is no per-family rescue either.

Within-family shape, for the record (and read the n's — several cells are thin):

    SWG        <0.5 +1.05 | 0.5-0.8 +0.83 | 0.8-1.0 -1.22 | 1.0-1.5 -2.52      decreasing
    POS-BO     0.5-0.8 +23.19 (n=19) | 0.8-1.0 +9.28 | 1.0-1.5 +2.15 | 1.5-2.5 +4.80 | 2.5+ +4.71
    POS-ACCUM  <0.5 -7.71 (n=6) | 0.5-0.8 +9.30 | 0.8-1.0 +9.34

Inside a family the relationship is flat-to-**negatively** sloped — the good cells sit at
LOW-but-not-lowest RV, not at 1.0-1.5. **This says nothing about `rv_floor`**: tests #5 and
#6 already established that the daily relationship does not transfer to the intraday
PA-trigger population, where it runs the other way. A daily selection result never licenses
an intraday gate change; that conflation is what section 6 of the first registration exists
to prevent, and it is not being made here.

## Thread scoreboard, closed

Eight tests, one survivor, and the survivor has now failed its own confirmation. The
useful residue is not a filter — it is the mechanism: **RV is a family label on this book,
not an independent quality signal.** That is a real finding about the funnel and it is
worth more than the filter would have been.
