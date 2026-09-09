# PREREG · Wyckoff DISTRIBUTION as a POSITIVE filter

**Written 8 Sep 2026, BEFORE computing any significance on the positive direction.**
Companion to `PREREG_wyckoff_score_value.md` (score input → null) and
`wyckoff_veto_study.py` (veto → ran backwards).

---

## 0. Why this test exists at all

Jay, 8 Sep 2026: *"You suggest an idea, we debate it, you build it, you backtest it and
prove it worthless, you advise me to discard it. In this process you are not guiding me
on how to improve it."*

That is accurate, and Wyckoff is the clearest instance. Two tests were run in July:

| test | result | what I did |
|---|---|---|
| DISTRIBUTION as a GO **veto** | vetoed cohort **+5.60%** vs kept **+0.52%** | filed as "null / backwards", discarded |
| Wyckoff tier as a **score** input | held-out ρ +0.013, p 0.74 | filed as null, discarded |

The veto result is **not** a null. A veto whose vetoed cohort *outperforms* is a signal
with the sign inverted. The mechanism was even written down at the time and then walked
past: *49% of qualified picks read DISTRIBUTION at signal time, because Wyckoff events
fire at high-volume pivot highs — which is structurally what a breakout looks like.*

That sentence says DISTRIBUTION is behaving as a **breakout detector** on a pre-qualified
long universe. This test asks whether it can be used as one.

## 1. What reproduction already showed (before this test)

Re-running `wyckoff_veto_study.py` on 8-Sep reproduces July exactly, and exposes two
things I did not report then:

- The headline **+5.60% cell is n=26**, below the study's own pre-registered n≥30 floor.
- The edge **decays monotonically with sample size**: +5.08pp (n=26) → +1.36pp (n=47) →
  +0.74pp (n=189) → +0.20pp (n=228).

A monotonic decay in n is the signature of a small-sample artifact. So the honest prior
here is **weak-positive, not dramatic**, and the only cells worth testing are the wide
ones where n is large enough to mean anything.

## 2. Primary hypothesis (one, stated up front)

**H1** — Among already-qualified bull picks, those whose point-in-time Wyckoff reading is
DISTRIBUTION have **higher** mean matched-horizon alpha than those that are not.

Tested on the WIDE cut (`V1 any DISTRIBUTION`, n≈228). The narrow tier≤−3 cells are
reported for completeness but are **not** the primary — they already failed n≥30.

## 3. Adoption rule — stated before the answer, not renegotiated after

Adopt DISTRIBUTION as a positive selection filter ONLY if ALL of:

- **A · n ≥ 100** in the selected cohort. Not 30 — the July lesson is that small cells
  produce large numbers.
- **B · edge ≥ +1.0pp** over the rejected cohort, on matched-horizon alpha.
- **C · symbol-block bootstrap CI95 on the edge EXCLUDES zero.** Trade-level resampling
  is not acceptable: established 13-Aug (bar-level bootstrap overstated n) and again
  8-Sep (three estimands on one recovery run gave three different answers).
- **D · the sign holds in BOTH halves of a chronological split.** No window where the
  selected cohort is worse.
- **E · retention ≥ 30%.** A filter keeping fewer than a third of picks is not a filter,
  it is a different strategy on a much smaller opportunity set.

**Falsifier, stated now:** if the wide-cut edge is under +1.0pp, or its symbol-block CI
straddles zero, or either chronological half reverses — DISTRIBUTION is not a usable
positive filter and the July "null" verdict stands on better evidence than it had.

## 4. What is NOT being claimed

This does not revisit Wyckoff as a **score** input — that was tested on held-out data
(ρ +0.013, p 0.74) and is not reopened here.

This tests **selection only**: given the screener has qualified a name, does the Wyckoff
reading help choose among them. It says nothing about Wyckoff as an entry timer, an exit,
or a sizing input.

## 5. If it fails — the v2 path, decided in advance

Per the standing change of method (8-Sep): a negative result is not a finding until it
comes with a v2 or an explicit statement that none exists.

If H1 fails, the next mechanism-level question is **why DISTRIBUTION and price strength
co-occur at all**. The candidate is that `wyckoff_state` fires on high-volume pivot highs,
so it is a proxy for *recent upside volume expansion* — which the screener may already
capture via `Rel_Vol` and the breakout gates. Test: does DISTRIBUTION carry any
information **after** controlling for relative volume at the anchor? If not, the honest
conclusion is that it is a redundant restatement of a signal already in the funnel, which
is a different and more useful finding than "null".
