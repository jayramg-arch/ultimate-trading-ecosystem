# PREREG · Minervini template ≥ 7/8 vs ≤ 6/8 on v1, FORWARD only (18 Oct 2026)

The in-sample test (PREREG_minervini_gate_v1) FAILED on its CI, but its descriptive table
suggested the useful split is 7/8-or-better against 6/8-or-lower (7/8 −0.334 R ≈ 8/8 −0.333 R;
≤ 6/8 −0.50 to −0.57 R). That split was found by looking, so it is judged ONLY on signals that
did not exist when it was seen.

- **Data:** `logs/gm_signal_log.csv`, signals dated **after 2026-10-18**; the unit, de-duplication,
  outcome (R) and template reconstruction are exactly those of PREREG_minervini_gate_v1
  (`minervini_gate_study.py --forward --after 2026-10-18`).
- **Population:** bull path, 5/5 GO on the row's own clock.
- **H:** mean R(≥ 7/8) − mean R(≤ 6/8) ≥ **+0.10 R**, symbol-bootstrap 95 % CI above **0**, and the
  ≥ 7/8 group's stop-out rate not more than 5 pp worse. Each group needs n ≥ 60, else THIN.
- **Read:** **15 Jan 2027** (scheduled). THIN then → read again on 16 Apr 2027 with the same rule.
- **Decision:** PASS → propose "≥ 7/8 for bull-path names" as a GM Step 2 gate (Jay's call).
  FAIL → the template stays an overlay and this line of enquiry closes.
- One read per date; no change to the split, the threshold or the unit after today.
