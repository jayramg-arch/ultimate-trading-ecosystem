# GOLDEN RULES — identifying and shortlisting trades

> **What this is:** the standing doctrine for the GM + S4 system, written from what the
> measurements and the mistakes actually showed — not from trading theory. Every rule
> here has a specific incident or a number behind it, and the number is quoted so you can
> re-open the argument later if the evidence changes.
>
> **How to use it:** read PART 1 before the session. Use PART 8 as the checklist at the
> moment of the trade. Everything between is the reasoning, for when you want to know
> *why* a rule exists before you break it.
>
> **Last updated:** 19 Aug 2026

---

## PART 1 — THE TEN RULES (the one-page version)

1. **The watchlists QUALIFY. The board TIMES. S4 is the plan of record.** Never re-litigate
   qualification on the chart, and never take the plan from the board.
2. **Never buy the touch. Buy the confirmation.** Alert at the level → wait for a CLOSED
   bar → act on *that* bar. Never a resting order at the level.
3. **A stop closer than 1×ATR(D) is not a stop.** Any R-multiple measured against it is
   fiction. Re-price before you believe it.
4. **INVALIDATION is not the STOP.** Know both prices before you enter, and know which one
   you will act on.
5. **A GO is not a trade.** The setup can be sound while the plan is wrong. Fix the entry,
   the stop or the target — or pass.
6. **Room decides tradeability.** If T1 *is* the resistance you distrust, you have no
   trade — you have a breakout candidate.
7. **Sector and weekly trend are gates, not footnotes.** Stage 3/4 sector, or a weekly
   downtrend, changes what the same chart is worth.
8. **Read results per family × direction. Never pooled.** Pooling has produced three false
   conclusions in this system already.
9. **Log the decision — especially the passes.** A log that only records entries cannot
   tell you whether your instinct beats the system.
10. **Confidence comes from executed trades, not from built features.** When the urge is to
    build, check whether there is a trade you are avoiding.

---

## PART 2 — BEFORE YOU LOOK AT A SINGLE CHART

**DO**

- **Restart properly.** `STOP_COMMANDER.bat`, then relaunch. `python -m streamlit` forks a
  child that keeps port 8501, so Ctrl+C leaves the OLD code serving. Two separate "the fix
  didn't work" hours this month were this.
- **Check the data is today's.** The board prints `As_Of` and a provenance strip. A stale
  cache once had 15 names frozen on 9-day-old bars, and VIJAYA "fired" a catalyst on a
  dead bar.
- **Rebuild after any Trigger-TF or X-Ray change.** Cached rows predate the change.
- **Confirm the board's source lists are not empty.** The header names unreadable or
  header-only CSVs — that is how Hunter names silently vanished from the board.

**DON'T**

- Don't assume a browser reload reloaded the code. It does not. Only a process restart does.
- Don't read a mid-session board snapshot after the close, or a >15-minute-old snapshot
  during the session. The AGE guard warns you; believe it.
- Don't compare today's Overall against a screenshot from last week. Stage, RS and RRG were
  all recalibrated on 18–19 Aug.

---

## PART 3 — SHORTLISTING: THE FUNNEL, AND WHERE EACH ANSWER COMES FROM

| Stage | Surface | Answers | Never ask it for |
|---|---|---|---|
| QUALIFY | Chartink / Screener.in / `pullback_finder` | *Does this name belong on the list at all?* | timing |
| TIME | GM Trigger Board | *Which qualified names deserve attention now?* | the plan |
| EXECUTE | S4 on TradingView | *What is the entry, stop, target — and is it worth taking?* | qualification |
| MANAGE | Risk Shield / Pyramid | *What do I do with it now that I own it?* | entries |

**DO**

- **Inherit qualification.** A name on the Hunter/EarlyBird/Pullback/Leader list was already
  qualified; the board times it. Re-qualifying is what dead-ended the rigorous lists for
  weeks.
- **Use the board's default view** — all-gates (4/4) only, sorted by Overall. Untick it when
  you want to see the near-misses; the header tells you how many it is hiding.
- **Treat `4/4 · PA 3b` as real.** All four gates pass; the pattern fired a few bars ago.
  CHOLAFIN was exactly that and was worth a full review.
- **Read S4 on the SAME timeframe as the board tab the name came from.**

**DON'T**

- Don't chase names off the catalyst scan that no longer carry a live catalyst — the board
  marks those `WATCHLIST · catalyst expired`.
- Don't expect the board and S4 to agree perfectly. The board leads slightly by design (PA
  recency), the feeds differ (Dhan vs TradingView), and the board's location is a proxy for
  S4's zone engine. Disagreement is information; identical output would be suspicious.
- Don't trade a **Recovery** name off S4 alone. Recovery qualification is RFF *fundamentals*
  and the chart cannot see them. The GM is the authority on whether it belongs on the list.

---

## PART 4 — CONTEXT: THE GATES THAT COME BEFORE THE CHART

**DO**

- **Check the trend stack — weekly, daily, entry-TF.** The best long is a dip inside a
  weekly uptrend. Down at all three degrees is a counter-trend bounce and must be traded as
  one: smaller size, first obstacle as target, no expectation of follow-through.
- **Respect the sector.** Stage 4 sector = you are long inside a group being distributed,
  the most common way a good-looking chart fails. Stage 3 = no tailwind, the name must
  carry itself.
- **Prefer leadership.** Outperforming index *and* sector with rotation intact is the
  strongest single argument a name has.
- **Note the stage age.** A Stage-2 leg only weeks old is early — where the move is, but
  unproven. Thirty weeks in, demand more from the entry.

**DON'T**

- **Don't hold Stage 3 or Stage 4.** This is the rule you have historically been slowest
  on; RELIANCE sat as a known Stage-4 violation for weeks before the exit.
- Don't read the RRG quadrant as a gate. It was measured: the tradeable-cell whitelist is
  worth **+0.12pp at 4 weeks and +0.00pp at 12**. Only `LEADING → LEADING` and
  `WEAKENING → LEADING` survived both horizons — those two are worth your eye, the rest is
  noise.
- Don't treat "RS is positive" as leadership when rotation has rolled over. Strength being
  *given back* is not strength.

---

## PART 5 — LOCATION AND GEOMETRY (where the money is actually lost)

### 5a. Location

**DO**

- **Buy at a level, not at a price.** A zone gives you an area and a distal that defines
  wrong. A line (S/R, AVWAP, EMA) gives way without warning.
- **Know which kind of level you are on.** A *pattern* zone (DBR/RBR) marks an imbalance —
  breaking it means the demand that caused the advance is gone. A *pivot* zone is a shelf —
  breaking it means a lower low. Both are real; the pivot one is weaker and scores nothing
  in confluence.
- **Remember tests WEAKEN a level.** 1 touch = fresh, 2–5 = tested, **6+ = spent and a
  breakout candidate**. Your instinct that "tested four times = weak" is directionally right
  but two touches early.

**DON'T**

- Don't buy inside supply and call it a pullback. If price is in a supply zone, the only
  coherent long is one that gets *paid for breaking it*.
- Don't buy extended. Above ~2.5×ATR from the daily EMA20 with no zone underneath, any stop
  is arbitrary and every dip looks like an entry.

### 5b. Geometry — the single most expensive recurring error

> **CHOLAFIN, 18 Aug:** engine printed `T1 5.6R`. The stop was **13 points** against an
> **ATR(D) of 46.3** — 0.28×ATR. Re-priced against a 1×ATR stop, T1 was **~1.6R**.
> **COFORGE, 19 Aug:** `3.1R` off a 0.33×ATR stop. Same fiction.

**DO**

- **Measure every stop in ATR before believing any R.** Under 0.5×ATR the panel now says so
  outright; under 1×ATR treat the R as optimistic.
- **Set the stop from the instrument's volatility, then let the reward fall where it falls.**
  A 2R trade priced honestly beats a 5R trade priced on a stop that cannot survive a Tuesday.
- **Know your invalidation separately.** Hard stop for the wick, closing-basis exit at the
  structural level for the thesis. The panel prints both: `SL` and `INVAL`.
- **Check room before anything else pleases you.** `⛔ IN SUPPLY` or under 1R to the first
  obstacle means the trade is being asked to pay before it reaches anything.

**DON'T**

- **Don't accept an R-multiple the panel hands you.** It derives the stop from the nearest
  structure without asking whether that structure is closer than a day's noise.
- Don't set entry and invalidation a point apart. If being *in* and being *wrong* are the
  same price, you have no room to be wrong — wait for a deeper entry.
- Don't widen a stop to make the R look better without re-sizing. Wider stop, smaller
  position, same rupee risk — or it is not the same trade.

---

## PART 6 — TRIGGER AND ENTRY

> **Your #1 historical mistake:** entering at the zone on the touch, skipping confirmation.
> This is the rule with the most evidence behind it and the one worth being rigid about.

**DO**

- **Alert at the level. Wait for a CLOSED bar. Then act.**
- **Prefer the RETEST to the buy-stop.** Measured in your own harness: buy-stop **−0.02%**
  mean matched alpha vs retest **+0.38%**, better in *every* family, and the retest filled
  **320 names vs 268** — the buy-stop rejected 63 that never made a new high. `replay.py`
  defaults to retest for this reason.
- **For a breakout above a known ceiling:** wait for a closed bar above it on volume, then
  buy-stop above *that bar's* high, or bid the retest of the level as new support.
- **Insist on volume — the V gate is not optional.** RV is the most reliable confirmation the
  panel offers and the thing most often missing from failed breakouts — with one exception below.
  **What RV is:** the *current bar's* volume divided by a rolling 50-bar average of the same
  series, computed **on the timeframe of the chart you are looking at**. On a 75m chart it is
  a 75m bar vs the average 75m bar — so on an intraday chart RV *is* intraday volume. It is
  not a daily figure, and there is no separate non-intraday volume measure anywhere in S4 or
  the board. Read RV against the clock: the same 1.0 means different things at 10:30 and at
  13:00 (§8c).

**DON'T**

- **Never park a resting order at the level.** Price tags it, fills you, closes back below,
  and you are long inside supply with the level overhead.
- Don't treat a coil as a trigger. NR7 / inside bars are *compression*, not ignition.
- Don't act on a dead-volume reclaim. VIJAYA's RV-0.2 fade-bounce was a skip.
- Don't read "buy-limit at the trigger close" as a pullback entry when that close *is* the
  current bar — the panel will tell you it fills at market.

**The one volume exception:** at a demand zone in a pullback context, thin volume is
*dry-up* — sellers exhausted, which is what you want. It stops being a virtue the moment
you need follow-through. The RV floor drops to 0.5 in pullback context for exactly this.

---

## PART 7 — SIZING, MANAGEMENT AND EXITS

**DO**

- **1% risk per trade** (0.25% for new/unproven entries; 1% on pyramid adds). Volatility-
  adjusted off the 14-day ATR, always.
- **Let the trail do the work.** Measured over 203 POS trades: **88% exit on the trail**,
  11.8% at the initial stop, and **only 8.4% ever reach 3R**. Targets are upside; the trail
  is the mechanism.
- **Use the R-canon:** swing 2R/4R, positional 3R/5R, nothing under 2R. Half the position
  carries no target and rides.
- **Trail tighten-only, never loosen.** The Chandelier is catalyst-aware (POS 4.5× / SWG
  1.5×) and four separate studies have rejected tightening it.

**DON'T**

- Don't re-tune the stop or the trail on a hunch. Four stop studies have now rejected
  tightening; the structural-SL variant had the best mean, passed the OOS gate, and was
  **still** rejected because the median went −0.48R → −1.01R and stop-outs 11.8% → 52.7%.
- Don't hold a positional target on a swing-shaped trade. If the structure says swing, book
  into strength.
- Don't leave a position without a resting stop. 445 shares once sat with no cover.

---

## PART 8 — THE CHECKLIST (use this at the moment of the trade)

Run it in order. **Stop at the first NO.**

| # | Question | Where |
|---|---|---|
| 1 | Is it still valid — not Stage 3/4, not broken down? | S4 Structure basis |
| 2 | What is the trend stack — weekly / daily / entry-TF? | S4 SUMMARY, line 1 |
| 3 | Is the sector Stage 1/2, or am I fighting the group? | S4 Sector row |
| 4 | Am I at a level, or nowhere in particular? | S4 Location (L) |
| 5 | Am I inside supply? Is there ≥1R of room to the first obstacle? | S4 Room |
| 6 | Has a trigger fired on a CLOSED bar, with volume? | S4 TRIGGER chip |
| 7 | **What is the stop in ATR?** Under 1× → re-price or pass. | S4 Entry·SL·T1·T2 |
| 8 | **Where is invalidation, and is it a different price from the stop?** | S4 `INVAL` |
| 9 | What does the R look like *after* fixing the stop? Under 2R → pass. | your arithmetic |
| 10 | Does the SUMMARY say "take it", or "setup sound, plan is not"? | S4 SUMMARY, last line |
| 11 | Size at 1% risk on the honest stop. | Risk Allocator |
| 12 | Log the decision — including a pass, with the reason. | `log_trade_review.py` |

---

### 8b. When the alert fires on a name you have NOT armed

This is the one case the checklist above does not cover — it assumes you arrived at the
chart deliberately. An alert can introduce you to a stock instead.

**It is not a contradiction.** Arming is a manual attention marker, not a gate. A qualified
name that triggers before you got round to arming it is the alert doing the watching you
did not. The name is on the watchlist, so it is already qualified; nothing is missing from
the chain.

**Spend 30 seconds on WHY first, because the likeliest cause is a stale board.**

1. Is the board rebuilt for *this* bar? Check the AGE strip. A hidden tab gets its refresh
   fragment throttled by Chrome and you are reading an earlier bar.
2. Same timeframe? An alert on 75m against a board tab on Daily is two different bar
   closes and two different answers.
3. What does the row actually say?

| Board row | Do |
|---|---|
| agrees, or merely behind ("Wait for Pullback", 3/4) | take it through the checklist — S4 is the plan of record |
| **`INVALIDATED`** | **stop.** Board and S4 share the same stage 2x2, so they should not disagree — one of them has stale data. Reconcile before acting. |
| board unavailable (app down) | S4 alone can evaluate the trade, but the cross-check is gone — be stricter on geometry |

**The real cost is not the missing arm, it is the missing homework.** An unarmed name is
usually one you have not studied: you may not know its archetype, which scan qualified it,
whether it is the Bull or Recovery path, or — if Recovery — whether the RFF fundamentals
hold, which **S4 cannot see**. You would be doing that research at the trigger, under time
pressure, which is the condition your worst entries have come from.

> **The rule:** take it if the checklist passes AND you can answer *"why is this name on the
> list at all"* without guessing. If you cannot answer that, the pass reason writes itself —
> and it is a better reason to pass than anything on the chart.

**The structural fix is upstream.** Arm names during the evening review, so a trigger
arrives on a stock you have already thought about. The alert should tell you *when* — it
should not be making the introduction.


### 8c. The alert marks a BAR, not a state — and the first bar of the day lies

Three of the four gates are fixed at the trigger bar. **Location is not.**

| Gate | Nature | Still true an hour later? |
|---|---|---|
| **P** pattern | structural — a pattern *formed* | yes |
| **V** volume | a property of that bar | yes |
| **B** bar | a property of that bar | yes |
| **L** location | *price is at a level right now* | **no — price moves off it** |

An alert can fire correctly at 10:30 and the panel read `L·` when you open it at 11:45.
Neither is wrong. There is a second route too: a **tested zone is deleted** by the
lifecycle, so the touch that fired the alert can consume the zone that justified it.

> **20-Aug:** nine alerts on the 10:30 bar. By the time the panels were read, SONACOMS and
> COFORGE showed `no location` — SONACOMS still `P✓ L· V✓ B✓`, with the AVWAP-BO at 840.90
> pressed against price at 836.90. It had drifted off the anchor it triggered on.

**So: arriving late, re-evaluate at the CURRENT bar.** If location has gone, the entry
premise has gone with it — the trade was *buy at the level*, and price is no longer at the
level. This is also why the plan latches the trigger bar instead of re-deriving the entry
from the live price.

**And treat the 10:30 cluster with suspicion — this one is MEASURED.**

S4 computes `chart_rv = volume / sma(volume, 50)[1]`, a rolling baseline that **mixes every
bar of the day**. NSE intraday volume is U-shaped, so that single baseline is too low for
the opening bar and too high for the midday ones. Measured over 55 board names × 90 days,
**14,466 bar-observations** (`rv_time_of_day_study.py`):

| 75m bar closes | median RV | share of session volume | **V-gate pass ≥1.0** |
|---|---:|---:|---:|
| **10:30** | 0.97 | 27.3% | **48.2%** |
| 11:45 | 0.53 | 15.5% | **20.5%** |
| 13:00 | 0.50 | 13.6% | **18.6%** |
| 14:15 | 0.48 | 13.4% | **17.3%** |
| **15:30** | 1.05 | 28.8% | **52.8%** |

**The V gate passes ~50% of the time at the open and close, and ~18% midday — a 2.8×
difference caused purely by time of day.** So:

- **A 10:30 GO cleared the weakest volume test of the day**, at the bar most exposed to
  auction noise and gap resolution. Several firing at once is the bar's character, not a
  sign of a good day.
- **An 11:45 or 13:00 GO cleared a test only ~1 bar in 5 passes.** On the volume dimension
  those are *stronger* evidence, which is the opposite of the "later is worse" intuition.
- **15:30 is as inflated as 10:30** — and it is post-close, so it is tomorrow's decision
  anyway.
- **125m is milder** (36% / 17% / 37%): wider bars average more of the session, so the
  distortion is smaller. An unanticipated second argument for running the 125m set.

⚠ **This measures the GATE, not outcomes.** It does not say 10:30 triggers lose money —
that needs an intraday backtest, and none exists (the s4go replay is daily-bar, `GO_Date`
has no time component). Treat it as "the volume gate is not the same test at every hour",
which is enough to change how much weight you give V at each bar.

**The latent fix**, not yet made: an RV baseline computed per time-of-day slot rather than
across all bars. It would remove the distortion both ways. It is a signal change, so it
gets measured before it ships.

---

### 8d. Pyramid ADDs — you do NOT need all four, but you need location MORE

An add is a different trade from an entry. You already own it, it is already working, and
the thesis is proven by the position. What you are buying is more of a winner **at a good
price** — so the gates change weight.

| Gate | New entry | **ADD** |
|---|---|---|
| **P** pattern | required | **not required** — the position is the thesis |
| **V** volume | required | **not required** — and demanding RV ≥ 1 is wrong at a pullback, where dry-up is what you want |
| **B** bar | required | keep it — do not add on a collapsing bar |
| **L** location | required | **the whole game** — a bad add raises your average and turns a winner into a bigger loser |

**Three ADD-only checks that outrank all four:**

1. **The stop must rise.** An add comes with the Chandelier raise for the WHOLE position.
   If the stop cannot move up, you are only increasing risk.
2. **Combined heat and correlation.** The board prints `⛔ r0.93` against the rest of the
   book. An add concentrates exposure you already have — sector cap included.
3. **Is it actually working?** ADD is for winners. R > 0, in profit, leading.

> ⚠ **CORRECTION (20-Aug, same day).** An earlier version of this rule claimed that on
> SONACOMS "pyramid said ADD while S4 said NOT AT LOCATION". **That was wrong.**
> `pyramid_logic` live said **HOLD** for SONACOMS. The `ADD +8.7% · 0.57R` visible on the
> S4 panel comes from the **v67 portfolio slot** — a snapshot written by Sync-to-TV, not a
> live pyramid verdict. I read one panel field and inferred a disagreement between two
> engines that were not actually disagreeing.
>
> **The general rule still stands, for a different reason:** `pyramid_logic._at_location`
> WAS a trend test wearing a location test's name —
> `ltp > sma200 and slope > 0 and ltp <= close_5d × 1.10 and ltp > ema20` — where
> `ltp > ema20` passes at any distance above the 20-EMA. It now carries an ATR extension
> cap (`ADD_MAX_EXT_ATR`, default 2.0), measured the same way S4 measures it, so the two
> surfaces answer the same question on the same scale.
>
> **Measured on the live 17-position book: the cap changes nothing today** — the two ADDs
> sit at 1.46× and 0.89× ATR above the 20-EMA. It is a guard against a case that has not
> occurred yet, not a fix for one that has. The cap is 2.0 rather than 1.5 because 1.5
> would have sat 0.04 ATR above a live ADD, one bar from deleting it silently.

**And a rule that came out of getting it wrong:** a value on the S4 panel is not always
computed by S4. The **v67 slot rows** (MY TRADE / POSITION) are *synced snapshots* — they
are as old as the last Sync-to-TV. When a portfolio field on the chart disagrees with the
Pyramid page, the page is live and the chart is a photograph.



## PART 9 — READING THE SYSTEM'S OWN OUTPUT

**DO**

- **Trust your chart read over the mechanical verdict.** The engine is a measuring
  instrument; your eyes have a veto. It can talk you *out* of a trade — never *into* one.
- **Treat an unknown as unknown.** `?`, `n/a`, `—` mean the data is absent, not that the
  answer is "no". Every gate in the system fails OPEN on missing data by design.
- **Believe the tags.** `⚠ role`, `⧖D` (daily fallback), `⚠ unval` (unvalidated recovery
  book), `· RRG·`, `⚖` (knife-edge pattern) are all telling you the row is softer than it
  looks.

**DON'T**

- Don't read a number without asking which bar it came from. Weekly readings taken
  mid-week rest on a partial bar — SYRMA read LEADING on confirmed weeks and WEAKENING with
  the forming week included, one Monday session deciding the quadrant.
- Don't take a confluence score as conviction. It grades; it does not gate.
- Don't assume two panels showing the same field agree. When they disagree, find out which
  bar and which producer — that is where the information is.

---

## PART 10 — READING EVIDENCE (so a bad conclusion doesn't become a rule)

These are methodology rules. They exist because each one has already produced a wrong
answer in this system.

- **Per family × direction, never pooled.** Pooling produced three false conclusions:
  June's "NO-EDGE" verdict (17 POS winners drowned by swing losers), "swing has no OOS
  edge" (SWG-PB is the *most stable* catalyst; SWG-REV was the drag), and the 40% stop-out
  figure.
- **Match the horizon to the setup.** Never judge a positional or recovery setup on a 30-day
  window. And the benchmark must exit when the trade exits — a full-window benchmark against
  an early exit inflated alpha from +0.80% to +2.56%.
- **Measure stops in R, never in per-trade %.** Position size = risk ÷ (k × ATR), so a %
  metric structurally rewards wide stops. Re-running one study in R *inverted* its answer.
- **Demean before comparing.** Almost every RRG cell looked "positive" because the universe
  drifted +0.97%; the signal is the deviation, not the level.
- **Bootstrap by symbol, not by row.** Overlapping windows are not independent observations.
- **A gate is not live until a name that should fail actually fails.** Verify with a
  counter-example, not by reading the code.
- **Re-fit when the formula changes.** The RRG whitelist was fitted on the old formula and
  quietly became worthless when the calibration changed.

---

## PART 10b — WHAT THE MEASUREMENTS ACTUALLY SAY

Part 10 is how to read evidence. This is the evidence. Every number here came out of a
run in `validation_runs/`, with its sample size attached. Where a result is thin, it says
so — a thin result is still worth more than an opinion, but not much more.

### The single most important sentence

**Plan around +1% matched alpha per trade, and a MEDIAN trade that loses to the index.**
The selection edge is real and survives beta adjustment (median ex-ante beta 1.11; the
adjustment moves POS-BO OOS from +1.01% to +1.11%). But it is a low-hit-rate,
big-winner-carried profile — the beta-adjusted median is *negative* (POS-BO −2.49% IS,
−3.44% OOS). Sizing and drawdown tolerance matter more than the mean implies. Any number
you remember above about +1% is from one exceptional stretch, 2023-05 to 2024-01.

### Where to enter, relative to the EMA20 (515 trades)

| ext (ATR) | n | mean α | win % | initial-SL % | days held | max DD |
|---|---:|---:|---:|---:|---:|---:|
| < 0 | 159 | +0.04 | 27.0 | **75.5** | 12.6 | −3.62 |
| 0–1 | 178 | −0.07 | 27.5 | **70.2** | 15.7 | −4.00 |
| **1–2** | 62 | **+3.65** | **41.9** | **4.8** | 43.1 | −8.31 |
| 2–3 | 83 | +0.30 | 34.9 | 10.8 | 36.5 | −8.96 |
| 3–4 | 22 | −2.42 | 31.8 | 4.5 | 37.5 | −9.16 |
| 4+ | 11 | −3.10 | 36.4 | 27.3 | 32.8 | −11.63 |

- **Max drawdown rises monotonically with extension**, −3.6% → −11.6%, every bin. This is
  the robust result in the table and the one to trust.
- **Extension predicts how long you are stuck.** `corr(ext, days_held) = +0.373`; holds
  stretch 13d → 43d. That is the cost of chasing, and it is not the stop.
- **Alpha turns negative at 3 ATR, not 4.**
- **`corr(ext, alpha) = 0.00` overall.** Extension is a *tail* risk, not a linear one.
- **The counterintuitive one: do not wait all the way back to the EMA20.** Under 1 ATR the
  initial stop-out rate is **70–75%**, the worst in the table, against 4.8% in the 1–2
  band. "Wait for the pullback" is right; "buy at the EMA20" is not.

Thin tails: n=22 and n=11 in the top two bins, p90 is 2.72 ATR.

### How you exit is not where you think (203 POS trades)

| exit | share | mean R |
|---|---:|---:|
| **Trail SL** | **88.2%** | −0.01 |
| Initial SL | 11.8% | −1.02 |

- **Only 8.4% of POS trades ever reach 3R.** Targets are upside, not the mechanism.
- **The trail owns the book and has never been properly A/B'd.** It is the untested lever;
  the stop is not.
- **T1-vs-SL is 0.98:1, not 2:1** — T1 pays 2R on *half* the shares, the SL costs 1R on
  *all* of them. For a true 2:1 you need T1 at 4R with a 50/50 split.
- **Four separate studies have rejected tightening the stop.** The structure-anchored stop
  had the best mean AND passed the OOS gate, and was still rejected: median −0.484R →
  −1.014R, stop-outs 11.8% → 52.7%. Stop tuning cannot fix an unproven edge.
- **Every cell of every stop study is negative in R.** Absolute R is −0.13 mean / −0.48
  median while matched alpha is +1.05% — a falling benchmark. Quote both or neither.

### Confirmation times entries badly — but selects them well

- Entering on a **buy-STOP above the confirmed GO bar erases the edge**: +2.56% at the
  anchor close → −0.02% GO-timed, across every family, cell by cell. Not a composition
  artifact.
- **A retest limit is strictly better than a buy-stop** in every family, and fills 52 more
  names. It is now the default. But it recovers only ~0.4 of the 2.6pp gap — the residual
  is the **confirmation-wait tax**, and no entry tweak removes it.
- Widening the stop does **not** rescue a GO-timed entry. It converts quick −2% shakeouts
  into slow, larger losses: win 34% → 30%, median −1.19% → −2.92%.
- **So the GO gate is a trade CLASSIFIER, not an entry optimizer.** Use it to arm and
  focus; do not expect it to improve fills.

### Per family, because pooling has lied three times

| catalyst | in-sample | out-of-sample | verdict |
|---|---:|---:|---|
| SWG-PB | +0.42% (n=171) | **+0.52%** (n=141) | most stable in the book |
| POS-ACCUM | +5.23% | +2.09% | keep |
| POS-BO | +5.61% | +1.01% | keep |
| SWG-REV | +0.54% (n=43) | **−0.44%** (n=74) | the drag |

- **POS-BO's "decay" is regime amplification, not decay.** The benchmark over matched holds
  went +4.17% → −1.59%. In a rising tape these breakouts return ~2.3× the index; flat to
  falling, they roughly match it. With beta excluded as the mechanism, that is *conditional
  skill*.
- **SWG-REV's problem is payoff geometry, not stop-outs.** It stops out *less* than SWG-PB
  (89.3% vs 74.0% of exits at the initial SL is the wrong read — SWG-PB stops out 78% and
  is profitable). Payoff ratio 1.62 vs 3.14; a reversal bounce is structurally a smaller
  move than a trend continuation. No stop setting fixes "the move isn't big enough."

### Gate behaviour worth knowing

- **The bar gate's errors are asymmetric, so it stays loose.** It fires the alert; a false
  positive costs one glance, a false negative costs the trade because the name never
  surfaces. Tightening it cut fills 314 → 241 **and the removed trades were net winners.**
  Proposed, measured and rejected three times.
- **RV is time-of-day biased.** The volume gate passes **48% at 10:30, ~18% midday, 53% at
  15:30** — a 2.8× swing from the clock alone, because RV divides by a baseline mixing
  every bar of the day. A burst of alerts at the close is partly that artifact.
- **Wyckoff failed twice** — as a GO veto it was *backwards* (vetoed cohort +5.60% vs kept
  +0.52%), and as a score input it was null (held-out ρ +0.013, p 0.74). 49% of qualified
  picks read DISTRIBUTION at signal time, because Wyckoff events fire at high-volume pivot
  highs, which is structurally what a breakout looks like.

### And what the journal does NOT say

**The −₹4.99L realized loss is not a verdict on this system.** It is substantially
tax-loss harvesting — 21 of ~25 harvest exits in a single FY-end batch — of **random,
discretionary picks that never came from the Catalyst/GM+S4 pipeline** (ETFs and large-cap
defensives). The journal mixes system and hand-picked trades and cannot be separated
retroactively, so **no clean live system track record exists yet.** The only clean evidence
is the backtest, and it is positive. Build the live record forward from trades carrying a
true entry snapshot.

---

## PART 11 — THE BEHAVIOURAL RULES

The hardest ones, and the reason the rest exist.

- **Building is not trading.** The long-standing pattern is to build features when a trade
  needs taking. Confidence comes from executed trades. When the urge to build arrives
  mid-session, ask what you are avoiding.
- **Act on the alert, not the touch.** Watching a name tick-by-tick is how the confirmation
  rule gets broken.
- **Write the override down.** Going against the system is allowed — it is your money and
  your read — but log it with the reason. After twenty rows the log tells you whether your
  instinct beats the system, and nothing else will.
- **Log the passes.** A log of entries only is a survivorship-biased diary.
- **One decision per name per session.** Re-opening a chart you already passed on is how a
  pass becomes a chase.
- **Judge the fix, not the P&L, on the day you make it.** A correct change that lowers the
  headline number is still correct — the 19-Aug re-baseline made the measurement honest and
  the alpha smaller.

---

## APPENDIX — DEFAULTS WORTH KNOWING BY HEART

| Thing | Value | Why |
|---|---|---|
| Risk per trade | 1% (0.25% new entry) | DNA |
| Targets | swing 2R/4R · positional 3R/5R · **never under 2R** | Jay's ruling, 10-Aug |
| Partials | POS 25/25 · SWG 33/33 · GAP/REV 50/50 | half rides the trail |
| Chandelier | POS 4.5× · SWG 1.5× ATR, tighten-only | `risk_common` |
| Stop sanity floor | **1×ATR(D)** | below this, R is fiction |
| RV floor | 1.0 breakout · 0.5 pullback context | measured |
| MTTWR | 6 touches = spent | house rule |
| Stage | above: rising 2 / falling 3 / flat (RS up ? 1 : 3) · below: (falling & RS down) 4 : 1 | all four surfaces |
| Forward windows | POS-BO 120d · POS-ACCUM 180d · REV 90d · SWG 30–60d | never test outside these |

---

*This document is doctrine, not dogma. Every rule names its evidence — if the evidence
changes, change the rule and record why. What is not allowed is breaking one silently.*
