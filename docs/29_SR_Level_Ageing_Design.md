# S/R level ageing — design, and what it will and will not fix

**Written 9 Sep 2026, during market hours. NO CODE APPLIED — the patch is designed here
and held until after 15:30 IST**, per the standing protocol. Source research: Jay's
`E:\Notes\Validity of S-R levels.docx`.

Directive (Jay, verbatim): *"Do not remove the S/R lines from the chart. However, they
should show the ageing on the level/line and beyond the age, it shouldn't be counted
towards no room."*

That is exactly the right shape and it matches the doctrine already in the codebase — a
level is **price memory** and is never deleted; only its standing changes. The MTTWR grade
already works this way: an MTTWR level stays drawn and is excluded from the picker
(`s.a1t < c.mttwr`). Ageing is the same mechanism with a different clock.

---

## 1. What the research says

| timeframe | active lifespan | why |
|---|---|---|
| Monthly | 3-10+ years | macro cycles, secular turns; sovereign/pension horizons |
| Weekly | 6 months - 2-3 years | Stage 1 bases, Stage 3 tops, business cycles |
| **Daily** | **3 weeks - 3-6 months** | swing pivots, quarterly earnings reactions |
| Intraday | 1-10 sessions | session highs/lows, VWAP bands, liquidity pools |

Decay mechanism, for daily: resistance is trapped buyers waiting for breakeven. On a daily
pivot that overhang is a small slice of float, and within 3-6 months most of those holders
have capitulated or rotated. Institutional order flow works on 90-day cycles, so an
imbalance 180 days old has been cleared and audited out.

Practical schedule:

    < 1 month    high-conviction supply
    1-3 months   standard swing reference
    3-6 months   soft; needs volume or AVWAP confluence
    > 6 months   speed bump, not supply — prioritise weekly structure

**Three exceptions where an old daily level keeps its power** (all three are already
computable from parts this repo has):
1. **HTF confluence** — the daily high is also a weekly/monthly Stage 1 ceiling or Stage 3 top.
2. **AVWAP magnet** — huge volume traded at that pivot; the AVWAP anchored there tracks the
   collective breakeven and persists.
3. **Major unfilled gap** — a 3-5x-volume gap leaves an explicit zone that resists for 6-12
   months.

---

## 2. MEASURED FIRST — and the payload is not where it looks

> ⚠ **THE PIVOT NUMBERS IN THIS SECTION ARE WRONG — SEE SECTION 7.** The pivot-ceiling
> figures (45.2% stale, ~28% of names) came from a proxy that scanned all history for
> pivot highs; `overhead_room` never does that, and its pivot ceilings already age on a
> per-TF calendar. Measured through the real function the change moves **2%**, not 28%.
> The S/R findings in this section stand; the pivot ones do not.

Read-only audits on the live 55-name board (`sr_age_audit.py`, `room_source_audit.py`).

**The level pool is genuinely ancient.** 1,458 daily levels: **67.8% are >6 months old**,
median age **14.9 months**, oldest 99.6. So the ageing display is worth having on its own
merits — right now a 2-year-old line looks identical to a 3-week-old one.

**But stale S/R levels are NOT what caps Room.** The level that binds is:

    FRESH <1mo   50.0%      AGED 3-6mo   5.3%
    SEASONED     34.2%      STALE >6mo  10.5%

Room takes the NEAREST obstacle, and old levels are mostly far from price because price has
moved. Dropping every stale daily level frees room for **1 name in 55** (HONASA, +3.1%).

**Which source actually caps Room:**

| source | share | median distance |
|---|---:|---:|
| **pivot · D** | **56.4%** | +0.7% |
| S/R · D | 23.6% | +1.1% |
| S/R · W | 5.5% | +0.3% |
| supply zone | 5.5% | +1.1% |
| no ceiling | 9.1% | — |

**And the binding PIVOTS are old in a way the levels are not:**

    <1mo 19.4%  ·  1-3mo 29.0%  ·  3-6mo 6.5%  ·  >6mo 45.2%
    median binding-pivot age: 3.6 months

**So the rule has to cover pivot ceilings or it barely bites:**

    age out S/R levels only ....... 4 of 38 names  (~10%)
    age out S/R + pivot ceilings .. 14 of 50 names (~28%)

A pivot high is ONE bar's extreme — a single touch by a single day's traders. Every decay
argument in the research applies to it *more* strongly than to a multi-touch level, so
including it is faithful to the research, not an extension of it.

**Honest scope, stated up front: this does not "fix no room."** Median room across the board
is **0.28 x ATR (+0.7%)**, and 90% of names sit under 1 ATR. At a 2.5x-ATR swing stop that
is a median **0.11R**, with 98% under 1R. Even with every stale obstacle removed, the
nearest live swing high is still ~0.7% above price. Room is tight because the ceiling is
genuinely close, not because it is a ghost. What this change fixes is the ~28% of cases
where the ceiling is a ghost.

---

## 3. The change

### 3a. Age clock = time since LAST touch
Not first touch. The research decays a level from when it was last *tested*, and a level
retested last month is live regardless of when it was born.

Both engines already track it and neither exposes it:
* Pine `S4Core.srLevels` keeps `Lb` — "last-touch bar (distinct-test spacing)".
* Python `zone_engine.detect_sr_levels` keeps `Lb` in the same role.

`SRSig` currently carries `a1x` = *first*-touch TIME, used as the ray anchor. That field
stays as-is; last-touch is a new one.

### 3b. Per-TF expiry, measured in each TF's OWN bars
Never a flat 6 months — that is the [[s4_zone_tf_mismatch_and_diagnostics]] error, where a
weekly zone was killed by a daily EMA cross.

| TF | expiry (own bars) | ≈ |
|---|---|---|
| Monthly | 120 bars | 10 years |
| Weekly | 130 bars | 2.5 years |
| Daily | 126 bars | 6 months |
| 125m / 75m | 10 sessions | 10 sessions |

Each surfaced as an input so it is tunable, not a magic number.

### 3c. Display — the line NEVER goes away
Age tag appended to the level label, alongside the existing touch count:

    4,230  ·2T ·1.4mo        FRESH      full opacity
    4,297  ·3T ·2.8mo        SEASONED   full opacity
    4,410  ·2T ·4.9mo        AGED       dimmed border
    4,655  ·2T ·11mo  ⌛     STALE      dimmed + hourglass, still drawn

Colour/opacity carries the band so it reads at a glance; the price and touch count are
unchanged. Same treatment for pivot-derived ceilings.

### 3d. Room participation — the only behavioural change
`srAutoAbove` / `srAutoBelow` already gate on `s.a1t < c.mttwr`. Add `and not stale`:

    r := (s.a1t < c.mttwr and not srStale(c, s.a1b)) ? srAbovePick(r, s.a1) : r

and the same for the daily/weekly pivot-ceiling sources feeding `_ovh` (S4 ~5221-5226).

**A stale level is excluded from the ceiling ONLY.** It stays on the chart, stays in the
counts, and stays available as a *support* reference and a stop anchor — being old does not
make it a bad place to put a stop, it makes it a weak place to expect rejection.

### 3e. The three rescues
> ⚠ **SUPERSEDED BY SECTION 6.** These three were proposed from the research and then
> controlled. Only **HTF confluence** discriminates; the AVWAP and gap rescues fire at the
> same rate on FRESH ceilings and are pass-throughs. Ship HTF only. Kept here as written so
> the correction is visible rather than edited away.

A stale daily level is NOT excluded when any of:
1. a W or M level sits within `sr_tol x ATR` of it (HTF confluence);
2. one of the three AVWAP anchors sits within tolerance (the AVWAP magnet);
3. it coincides with an unfilled gap / FVG zone edge.

All three read existing values — `srW`/`srM`, `avwap_support`, the FVG tagging in
`zone_engine`. No new computation, and it stops the rule from deleting the exact levels the
research says survive.

---

## 4. Files (patch held until after 15:30 IST)

| file | change | note |
|---|---|---|
| `S4Core.pine` | `SRSig` += `a1b/a2b/b1b/b2b` (APPENDED, never inserted); `srLevels` sets them from `Lb`; `SRCtx` += expiry; `srStale()`; `srAutoAbove/Below` gate | **new library version — publish first** |
| `Section 4 ... .pine` | import the new version; age inputs; label tag + dim; pivot-ceiling age gate in `_ovh` | recompile, then **re-run `BIND_S4_SOURCES.bat`** and **recreate both GO alerts** |
| `zone_engine.py` | `detect_sr_levels` emits `last_bar` / `age_bars` / `age_band` / `stale`; `sr_support` and the Room consumers skip stale | keeps board↔chart parity |
| `gm_trigger_board.py` / web | age tag in the S/R display; Room excludes stale | restart Web Commander |

Token cost in S4 is small — four int fields and one comparison per pick — but S4 has run at
the ceiling before, so it gets measured before the compile, not after.

---

## 5. What is NOT claimed

This is a **correctness** change: the engine currently treats a 99-month-old line exactly
like a 3-week-old one, which contradicts both the research and how the levels are traded.
It is not backed by a forward test, and the measurement above is of the gate's INPUTS, not
of outcomes.

Whether excluding stale obstacles produces better trades is a separate question. If it is
worth testing, the honest form is a `--gate s4go` arm with stale ceilings excluded from the
Room/target computation, scored on fresh anchors under a pre-registered rule — the same
harness the roleMismatch thread used. Room-source removal has been measured once before
(the pivot-ceiling ablation) and did not pay, which is a reason to keep the display change
and the Room change separable.

---

## 6. The rescues were controlled, and two of three FAILED (9 Sep 2026)

Section 3e proposed all three of the research's rescue conditions. Before writing them
into the engines they were controlled the same way a gate is: **a rescue is only real if it
fires more often on STALE ceilings than on FRESH ones.** Equal rates mean it carries no
information about age — it is a pass-through that would silently undo the exclusion.

Measured on the live 55-name board, with a random-price base rate as a third arm:

| rescue | STALE | FRESH | RANDOM | verdict |
|---|---:|---:|---:|---|
| **HTF confluence** | **14.3%** (3/21) | **0.0%** (0/29) | 1.7% | **DISCRIMINATES** |
| AVWAP magnet | 38.1% (8/21) | 37.9% (11/29) | 17.6% | no information |
| AVWAP + hi-volume anchor | 52.4% (11/21) | 55.2% (16/29) | 61.0% | no information |
| unfilled gap | 19.0% (4/21) | 17.2% (5/29) | 34.3% | no information |

**Only HTF confluence survives.** It is close to a clean instrument: it never fires on a
fresh ceiling and almost never on a random price.

**AVWAP is a pass-through.** It fires at the same rate on fresh ceilings, so it is not
detecting a level that resisted decay — it is detecting that AVWAPs and ceilings both sit
near price. Adding the research's own "massive volume at that pivot" condition made it
*worse*, not better (52.4% vs a 61.0% random rate): once every 3x-volume pivot high in 500
bars is an anchor, there are so many that everything matches.

**The gap rescue fires BELOW its own random rate.** Gap edges are denser away from price
than near it, so as a filter it is worse than a coin flip.

### Consequence for the patch
* **Implement the HTF-confluence rescue only.**
* AVWAP and gap coincidence may still be *annotated* on the level for the eye — they are
  useful context — but they must never lift the stale exclusion.
* This is also what makes the change worth applying: the two vacuous rescues were eating
  most of it. With HTF only, **13 of 50 names (26%)** lose a ghost ceiling, against 5 of 50
  (10%) if all three had shipped.

### The general lesson
Every exemption is a gate in the other direction and needs the same control. Written into
the design because I proposed all three rescues from the research without testing them, and
two would have quietly cancelled the feature they were meant to refine.

---

## 7. RETRACTION — the pivot-ceiling figure was my own measurement error (9 Sep 2026)

Section 2 claimed the payload was in the PIVOT ceilings: *"45.2% of binding pivots are >6
months"*, and *"age out S/R + pivot ceilings .. 14 of 50 names (~28%)"*.

**That is wrong, and the cause was my proxy, not the engine.** `room_source_audit.py`
approximated the pivot ceiling as *the nearest confirmed pivot high above price across all
history*. `overhead_room` never does that. Its actual pivot ceilings come from
`detect_zones`, and **zones already age on a calendar, per timeframe** — `TF_CFG` has
carried `age_days` since the v3.x zone work:

| TF | age_days | ≈ |
|---|---:|---|
| Monthly | 1460 | 4 years |
| Weekly | 730 | 2 years |
| **Daily** | **182** | **6 months** |
| 125m | 28 | ~4 weeks |
| 75m | 21 | ~3 weeks |

Pivot zones are not exempt: `PvH` and `PvL` are appended to the same `zones` list and the
lifecycle loop ages every member alike (`if last_ms - z.origin_ms > cap_ms: continue`). And
the third source, `lastPH`, only scans the last 60 bars, so it cannot be stale either.

**So the daily obstacle set was already on the research's schedule. S/R LEVELS were the one
class with no clock at all** — which is exactly the gap Jay named.

### The real before/after, measured through `overhead_room` itself

| | n=55 |
|---|---:|
| ceiling unchanged | 54 (98%) |
| ceiling changed | **1 (2%)** |

    HONASA   S/R·D 478.70  ->  SZ band top 491.75   (+2.7% room)

Not 28%. **2%.** The honest scope of this change is: a correctness and display fix that
today alters one Room verdict in fifty-five.

### Why the display half is still worth shipping
67.8% of daily levels are last-touched >6 months ago, median 14.9 months, oldest 99.6 — and
every one of them currently renders identically to a three-week-old level. The chart is
withholding the single most important thing about a level's authority. That is a real
information gap whatever the Room arithmetic does.

### And the actual answer to "no room"
Median room across the board is **0.28 x ATR (+0.7%)**, 90% of names under 1 ATR, median
**0.11R** at a swing stop. With every stale obstacle removed it barely moves. **The board is
not wrong — those names genuinely are sitting under live resistance.** "No room" is mostly a
correct reading of a bad entry location, and the lever is which names get traded, not how
the ceiling is measured. S4 v4.7's BREAKOUT PIVOT ruling already encodes the right response
for the Stage-2 case: do not buy inside the band, arm a buy-stop above it.

### Method note
This is the second time in one session that a proxy I wrote produced a confident wrong
number (the other: reading `git ls-files` as proof the cache was tracked, when it was
showing the index I had just staged). Both were caught by going to the real function. The
rule that applies: measure through the code path that actually runs, not through a
reimplementation of it.
