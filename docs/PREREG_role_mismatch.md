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
