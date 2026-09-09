# PREREG · the stop's TRIGGER BASIS — intraday low vs daily close

**Written 9 Sep 2026 during market hours, BEFORE the arms are run. Code queued for after
15:30 IST.** Source: Jay's `E:\Notes\Premature SL hits.docx`, Part 1.2 and Step 1.

---

## 1. Why this is a new question and not a fifth stop study

Four stop studies on this desk have all tested stop **DISTANCE** — tighter, wider,
structural, catalyst-aware — and all four were rejected. The settled position is that the
POS 4×ATR stop and the SWG 1.5×ATR stop stay where they are.

**None of them touched the trigger BASIS.** `replay.py:340` triggers on

    if bar_low <= trail_sl

i.e. the intraday low. A stop resting at the broker on LTP behaves exactly that way. The
doc's claim is that this is the actual defect: geopolitical opens and morning panics print
a wick through the stop, institutions buy the low, and the bar closes back above — you sold
the bottom of the wick to the people who then took it up without you.

That is an orthogonal axis to distance, and it is cheap to decide.

## 2. Instrument check, run BEFORE designing the arms

On run `20260909_055448` (s4go, 36mo, catalyst qualify), for every trade whose exit reason
was "SL hit", the bar that first traded through the stop was re-read from daily bars:

| the triggering bar | n | share |
|---|---:|---:|
| closed **below** the stop — a real breakdown | 94 | 48.0% |
| closed **above** the stop — an intraday **wick** | 102 | **52.0%** |

196 of 196 stop-outs resolved. **The mechanism is real and large**, and it matches Jay's own
observation ("around 50% initially go down, then pick up") from an independent direction.

**But a wick survived is not a trade rescued.** The 26-Jul stop-out forensics found that of
trades stopped at the initial SL, **POS reached T1 later only 1.9%** of the time and holding
through them averaged **−6.65%**, while **SWG reached T1 36.4%** of the time. So surviving
the wick may simply postpone the loss, and the two families are likely to answer
differently. That is why the primary read is **per family, never pooled**.

## 3. The change under test

`replay.SL_BASIS`, default `"intraday"` — every prior run reproduces byte-for-byte.

* `"intraday"` — unchanged: `bar_low <= trail_sl`, fill at `trail_sl`.
* `"close"` — while the stop is still the INITIAL structural stop (`trail_sl == sl_price`),
  exit only when `bar_close <= sl_price`, and **fill at the CLOSE**, not at the stop.
  Once the Chandelier has ratcheted above the initial stop, triggering reverts to intraday,
  because that leg IS a resting broker order in live use.
* **Disaster floor** (the doc's Step 1, and it is not optional): an intraday hard stop at
  `sl_price − (disaster_mult − 1) × (entry − sl_price)`, default 1.5×, fills at its own
  price regardless of basis. Without it, "close basis" is really "no stop until 15:30",
  which is a different and much more dangerous thing than what the doc proposes.

### The fill asymmetry, stated up front
The control fills at `trail_sl` even when the bar GAPS below it — an optimism that has been
in the simulator since it was written. The treatment fills at the close, which on a genuine
breakdown day is *below* the stop. So the treatment pays an honest fill cost while the
control keeps a flattering one. **This biases against the treatment**, which is the safe
direction, but it means a narrow loss for close-basis is not conclusive. The control is
deliberately NOT changed: byte-identical reproduction of prior runs is a standing
requirement, and fixing gap fills is its own change with its own blast radius.

## 4. Hypothesis

**H8** — triggering the initial structural stop on the daily CLOSE rather than the
intraday low raises mean matched-horizon alpha, per family, without raising the loss taken
on the trades that do stop out.

## 5. Adoption rule — fixed now

Adopt `"close"` as the default ONLY if ALL of:

- **A · it bites** — ≥ 15% of control stop-outs change outcome.
- **B · per-family edge ≥ +1.0pp** on mean matched-horizon alpha, in the family it is
  adopted for. Pooled is reported but never decides — three false conclusions on this desk
  came from pooling families.
- **C · symbol-block bootstrap CI95 on (treat − control) excludes zero.**
- **D · the sign holds in both chronological halves.**
- **E · median R does not worsen by more than 0.25R.** This is the criterion that killed
  the structural-SL study, which had the best mean of any variant and still failed.
- **F · the average loss on the trades that DO stop out does not worse than the control's
  by more than 0.25R.** Specific to this test: close-basis exits at a worse price by
  construction, so it must be shown that the trades it saves outweigh the extra cost on the
  ones it does not.

**Falsifier:** any of A-F failing per family means the stop keeps its intraday basis for
that family, and the 52% wick figure is recorded as a real but unprofitable observation —
the wick is survived and the loss simply arrives later, exactly as the POS forensics
suggest it might.

## 6. What CANNOT be concluded from this test

A pass would license changing the SIMULATOR's stop basis and, from there, the live scheme
in the doc's Step 1 (wide disaster GTT resting at the broker + a close-basis structural
stop). It would **not** license:

* removing the resting broker stop altogether — the disaster floor is part of the tested
  arm, not an optional extra;
* a **manual** 3:15pm ritual. `gtt_auto_shield --trail` sat silently dead for six weeks
  because it needed a human, and the doc's workflow asks for a daily discretionary decision
  on every open position. If close-basis pays, it ships as a **15:15 scheduler job** beside
  the existing `gtt_trail` 15:45 and `exit_scan` 16:00, which Telegrams only the positions
  actually closing below their structural stop;
* any change to stop DISTANCE. That axis is settled and is not reopened here.

## 7. Honest prior

For: the 52% wick rate is large, measured on this desk's own trades, and the axis has never
been tested. Against: the POS forensics say stopped-out positional trades rarely recover
(1.9% reach T1), so for the family the doc is aimed at, close-basis may buy a worse fill on
the same loss. My expectation is that this passes for SWG and fails for POS — the opposite
of the document's framing — and I have written that down before running it.
