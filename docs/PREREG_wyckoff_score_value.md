# PRE-REGISTRATION — does the Wyckoff term earn its place in the WCL context score?

**Written 28-Jul-2026, BEFORE the held-out sample was generated or inspected.**
Author: Claude (at Jay's request, option #3 of three).

## Why this document exists

The Wyckoff DISTRIBUTION *veto* was tested on 28-Jul (`wyckoff_veto_study.py`) and
rejected outright — the vetoed cohort outperformed. That study also produced a
*secondary* observation: names the engine marks DOWN via Wyckoff did **+0.74pp
better** (V2, n=189), hinting the term may be uninformative or mildly inverted in
the score as well.

That observation is not evidence. It came from the fourth cut of the same 464
trades in a study designed to answer a different question. Acting on it would be
precisely the failure mode this desk's own audit named as its largest statistical
liability: 98 validation runs, alpha-selected sweeps whose winners became
production defaults, and no correction for multiple testing anywhere.

So the question gets its own pre-registered test, on data that has never been used
to look at Wyckoff.

## The question

The Wyckoff term (`wyk_score_comp`, the decayed tier, +4..-4) feeds `total_base` →
`total_final` → Pine confluence (`cf_w_wcl`) and the Trigger Board's `overall_score`.
Signed as it is, the engine asserts: **higher Wyckoff score → better trade.**

**H2 (primary):** `wyk_score_comp` at signal time is POSITIVELY associated with
forward matched-horizon alpha on qualified catalyst picks.

## Held-out sample — defined before it exists

Run: `validation.py --months 48 --universe nifty500 --screener bull --catalyst_windows`

- **HELD-OUT (primary):** anchors strictly **before 2024-06-17**. Never touched by
  the veto study, which spanned 2024-06-17 → 2026-01-15.
- **BURNED (reference only):** anchors on/after 2024-06-17. Reported for comparison
  and explicitly NOT used for the decision.

If the run yields fewer than 150 held-out trades the result is INCONCLUSIVE by rule,
not "no effect".

## Primary test

1. **Tercile split** of held-out picks by `wyk_score_comp` (negative / zero / positive),
   comparing mean matched-horizon alpha.
2. **Spearman rank correlation** between `wyk_score_comp` and `Alpha_Matched_pct`,
   with a permutation p-value (10,000 shuffles).

Point-in-time is enforced by truncating each symbol's daily frame at the anchor date
before the detector runs — identical to the veto study, and unable to look ahead.

## Decision rule — fixed now, not renegotiable after seeing the answer

- **KEEP the term as scored** if ALL of: terciles increase monotonically; Spearman
  rho > 0 with permutation p < 0.05; n_heldout >= 150.
- **DEMOTE to display-only** (drop the score contribution, keep the panel label) if
  rho <= 0 AND the tercile pattern is flat or inverted.
- **INCONCLUSIVE — change nothing** in every other case, including n < 150. Report it
  as unresolved rather than reading a null as a licence to act.

An INCONCLUSIVE or KEEP result means yesterday's shipped behaviour stands unchanged.

## Secondary, pre-declared (reported in full, decision-irrelevant)

- Same two tests on `smc_score`, which also feeds `total_base` and has never been
  tested either.
- Same two tests on the composite `total_final`.
- The burned-sample versions of all of the above.

These are reported whether or not they flatter the engine, so the whole family is
visible and can be discounted accordingly. They cannot by themselves trigger a change.

## Known limits, stated up front

- Universe membership is present-day nifty500 applied to 2022-24 anchors —
  survivorship, already disclosed in `validation.py`.
- Matched-horizon alpha carries its own caveat: the benchmark leg now exits with the
  trade (the 26-Jul horizon fix), so these are the honest numbers, but direction
  labels derived from it are endogenous and are NOT used here.
- A single held-out window is one sample. A KEEP verdict means "not refuted", not
  "validated".
