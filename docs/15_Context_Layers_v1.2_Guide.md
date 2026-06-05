# Weinstein Context Layers v1.2 — User & Trading Guide

> **Module Role:** Institutional context overlay for the Weinstein Commander ecosystem. v1.2 closes the feedback loop between the Setup Detector and the Context Score — confirmed setups now contribute a signed bonus to the composite score, so a high-conviction S2 (Spring/LPS Reversal) firing can tip a borderline BULL into STRONG BULL automatically.

> **Supersedes:** [13_Context_Layers_v1.1_Guide.md](13_Context_Layers_v1.1_Guide.md) (kept for historical reference). v1.1 → v1.2 is drop-in compatible — same inputs, expanded panel, recalibrated thresholds.

---

## 0. What Changed from v1.1

### NEW — Setup Bonus Feeds the Context Score

In v1.1, the 8 setups were pure *consumers* of the Context Score — S2 required `_total ≥ 6`, S1 required `_total ≥ 3`, etc. The score itself was the sum of just four components (Wyckoff + VP + SMC + Stage). A fired setup never influenced the score.

In v1.2, the Setup Detector contributes a **signed bonus** to the score *after* setup detection runs. This breaks the chicken-and-egg cleanly:

```
1. Components compute → BASE SCORE (raw _total)
2. Setup Detector runs using BASE SCORE (no bonus yet — no circularity)
3. Setup Bonus computed from detected setup
4. FINAL SCORE = BASE SCORE + Setup Bonus
5. Score band assigned from FINAL SCORE
```

### Bonus Table

| Setup | Priority | Bonus | Why |
|---|---|---|---|
| **S2** Spring/LPS Reversal | 5 | **+2** | Max-conviction bullish — 5 conditions aligned |
| **S3** Sweep + CHoCH Reversal | 4 | **+2** | High-prob bullish reversal |
| **S1** OB Retest + VP Support | 3 | **+1** | Solid bullish entry pattern |
| **S7** Distribution Breakdown | 3 | **−2** | Bearish — pushes score DOWN |
| **S4** VAL Bounce + Bull FVG | 2 | 0 | Already reflected in component scores |
| **S5** Stage 2 Continuation | 2 | 0 | Same |
| **S6** SOS Momentum Push | 2 | 0 | Same |
| **S8** Choppy Range | 1 | **−1** | Sit-out penalty |
| NONE | 0 | 0 | — |

### Panel Layout — 24 Rows (was 22)

Two new rows are inserted between the Score divider and the BREAKDOWN row:

| Row | Label | Content |
|---|---|---|
| 20 | **BASE SCORE** | `● N` — raw _total before bonus |
| 21 | **SETUP BONUS** | `✓ +2 (from S2)` or `✗ −2 (from S7)` or `● 0 (no bonus)` |
| 22 | **FINAL SCORE** | `✓ STRONG BULL (6+2=8)` — band assigned from base + bonus |
| 23 | **BREAKDOWN** | `Wyk:3 VP:3 SMC:3 Stg:3 Bns:+2` — adds Bns:±N |

The Context Score row from v1.1 is renamed **FINAL SCORE** for clarity.

### Recalibrated Score Thresholds (for new ±16 max)

| Band | v1.1 (±14 max) | v1.2 (±16 max) |
|---|---|---|
| STRONG BULL | ≥ 8 | **≥ 9** |
| BULL | 4 to 7 | 4 to 8 |
| NEUTRAL | −3 to +3 | −3 to +3 |
| CAUTION | −4 to −6 | −4 to −6 |
| BEAR | ≤ −7 | ≤ −7 |

Only the STRONG BULL threshold moved (+1 to account for the +2 bonus headroom). All other bands unchanged.

### Preserved from v1.1

- All bug fixes (B1–B7) and color fixes (C3, C4, C5)
- All v1.1 enhancements (E2 Stage, E3 alerts, E4 asymmetric POC, E5 freshness fade, E6 OB%, E7 Structure Health)
- All 8 setups (S1–S8) with identical detection logic
- `wcl_setup_pri_export` plot for Unified Ecosystem v2.5 E11 wiring
- Light theme (per prior user instruction)

---

## 1. Architecture Overview (Updated)

```
Wyckoff Module ─┐
VP Module     ──┤
SMC Module    ──┼──→ BASE SCORE ──┐
Stage Module  ──┘                   │
                                    ├──→ FINAL SCORE ──→ Band → Display
Setup Detector ──→ Setup Bonus ────┘
       │
       └─→ (uses BASE SCORE as input — no circular feedback)
```

The Setup Detector reads `_total` (BASE SCORE) and evaluates which of S1–S8 qualifies. The detected setup's priority maps to a bonus per the table in Section 0, and that bonus is added to produce FINAL SCORE. The score band (STRONG BULL / BULL / etc.) is then assigned from FINAL SCORE.

---

## 2. The Setup Bonus — Detailed Logic

### When Setup Bonus is Added

Bonus is added when a setup is *detected* (i.e., `_setup_pri > 0`). The bonus value depends on:

1. Whether the setup is bullish (✓ prefix), bearish (✗ prefix), or choppy (● S8)
2. The setup's priority (5 highest, 0 = none)

Pine v6 implementation:
```pine
bool _setup_is_bear = str.startswith(_setup_str, "✗")
bool _setup_is_chop = str.startswith(_setup_str, "● S8")
int _setup_bonus = 0
if _setup_is_bear
    _setup_bonus := _setup_pri >= 4 ? -2 : _setup_pri >= 3 ? -2 : 0
else if _setup_is_chop
    _setup_bonus := -1
else if _setup_pri >= 4
    _setup_bonus := 2
else if _setup_pri == 3
    _setup_bonus := 1
```

### Why S4/S5/S6 Get 0 Bonus

These priority-2 setups (`VAL Bounce`, `Stage 2 Continuation`, `SOS Momentum`) detect conditions that **already drive component scores**:
- S4 fires when bull FVGs dominate → already reflected in VP/SMC scoring
- S5 fires when Stage 2 + above VAH → Stage score is already +3, VP is already +3
- S6 fires when recent SOS + bull SMC → Wyckoff `wyk_score_comp` already +4

Adding bonus would double-count. Better to keep these as informational status indicators (panel shows the setup label) without inflating the score.

### Why S8 Gets a Penalty

S8 (Choppy Range) fires when CHoCH count ≥ 3 in last 20 bars and no other setup qualifies. This is a "sit out" signal — the structural environment is broken. A small −1 penalty pushes the score slightly toward CAUTION to remind the trader that the regime is fragile.

### Why S7 Gets −2 (Symmetric with S3)

S7 (Distribution Breakdown) is the bearish mirror of S3 (Sweep + CHoCH Reversal). Both fire when 4 strong conditions align. The score should reflect this — a confirmed distribution event is as load-bearing for shorts as a sweep+CHoCH is for longs.

---

## 2.5. The 8 Setups — Detailed Specifications

The Setup Detector classifies the current bar into **at most one** of S1–S8 (the highest-priority setup wins). Each setup is a multi-condition AND-gate of Wyckoff bias, Volume Profile location, SMC structure, Stage, and BASE SCORE. Setups are evaluated **in priority order**; once a higher-priority setup fires, lower ones are suppressed on the same bar.

Priority hierarchy (high → low): **S2 (5) → S3 (4) → S1 (3) = S7 (3) → S4 (2) = S5 (2) = S6 (2) → S8 (1) → NONE (0)**.

### S2 — Spring/LPS Reversal *(priority 5, bonus +2)*

**The max-conviction long setup.** Identifies the textbook Wyckoff Phase C / Phase D transition: a Spring (false breakdown that recovers on an up-close) or an LPS (Last Point of Support — successful retest of the spring low) followed by SMC trend-flip and Value Area support.

**Conditions (ALL required):**
- Most recent Wyckoff event is **Spring** OR **LPS**
- Event is **fresh** — fired within the last 15 bars
- SMC trend is **bullish** (`smc_trend_up = true`)
- VP score ≥ 1 (price above POC / inside or above VA — i.e., demand-side acceptance)
- BASE SCORE ≥ 6 (composite context already constructive)

**What it captures:** The institutional accumulation phase has resolved upward. The "smart money" exit liquidity has been swept (Spring) and the retest has held (LPS). This is the highest-quality long entry the system can flag.

**Action:** Full Kelly × 1.25 long. Stop below the Spring/LPS low.

---

### S3 — Sweep + CHoCH Reversal *(priority 4, bonus +2)*

**High-probability reversal long off a liquidity sweep.** Captures the SMC textbook reversal: price sweeps a prior swing low (stops out trapped longs / triggers shorts), then breaks structure to the upside with a Change of Character (CHoCH ▲).

**Conditions (ALL required):**
- No higher-priority setup (S2) is active
- Most recent liquidity sweep is **bullish** (`Sweep ▲`) within the last 10 bars
- A **bullish CHoCH** has printed within the last 10 bars
- VP score > −3 (price not deep below the entire profile — a sweep at extreme distribution is a dead-cat, not a reversal)

**What it captures:** The "stop run + reversal" pattern. The sweep removes hidden supply at the obvious swing low; the CHoCH confirms buyers have taken control of the structure. Maps directly to the **SWG-PB** (swing pullback) and **SWG-BO** (swing breakout) catalysts in the screener.

**Action:** Long on next pullback into the sweep candle or CHoCH origin block. Stop below the sweep low.

---

### S1 — OB Retest + VP Support *(priority 3, bonus +1)*

**The bread-and-butter accumulation entry.** Price is mitigating (retesting) a previously-formed **Bullish Order Block** while still inside the Wyckoff accumulation phase and supported by Volume Profile.

**Conditions (ALL required):**
- No higher-priority setup (S2, S3) is active
- Price is currently **inside a bullish OB** (`_in_bull_ob = true`)
- VP support: either VP score ≥ 1 **OR** price within 5% of POC (`_abs_poc_dist ≤ 5`)
- Wyckoff bias = **ACCUMULATION** (i.e., most recent Wyckoff event was bullish — Spring/LPS/SOS/SC/PS/ST)
- BASE SCORE ≥ 3 (modest composite confirmation)

**What it captures:** A clean, repeatable demand-zone entry — the institutional footprint (OB) is being defended at a high-volume node. Maps to **POS-AC** (positional accumulation) and **SWG-PB** (swing pullback) catalysts.

**Action:** Long inside OB. Stop below OB low.

---

### S4 — VAL Bounce + Bull FVG Stack *(priority 2, bonus 0)*

**Mean-reversion long at the lower edge of Value Area.** Price has tagged Value Area Low (VAL) and bounced, with more Bullish Fair Value Gaps unfilled than bearish ones — implying buyers are still aggressive above.

**Conditions (ALL required):**
- No higher-priority setup is active
- `_val_bounce`: VAL exists, current close is above VAL, current low has tagged VAL within 1% (`low ≤ VAL × 1.01`)
- Bull FVG count > Bear FVG count
- Wyckoff bias is **not DISTRIBUTION** (it can be ACCUMULATION or NEUTRAL — i.e., not actively topping)
- BASE SCORE ≥ 2

**What it captures:** Auction-theory mean reversion. VAL is the consensus lower bound; a defended VAL with bullish gaps above is a tight-stop long. Bonus = 0 because the conditions (VP + FVG) are already accounted for in the component scores.

**Action:** Long with stop just below VAL. Target POC, then VAH.

---

### S5 — Stage 2 Continuation Above VAH *(priority 2, bonus 0)*

**Trend continuation in a confirmed Stage 2 advance.** Price has broken structure to the upside (BOS ▲), is trading **above Value Area High**, and the structure is clean (not whipsawing).

**Conditions (ALL required):**
- No higher-priority setup is active
- Weinstein stage = **2 — Advancing**
- A bullish BOS (BOS ▲, not CHoCH) printed within the last 20 bars
- VAH exists and close > VAH (price has accepted above the entire prior value area)
- CHoCH count in last 20 bars ≤ 1 (clean structure — not choppy)

**What it captures:** A pure trend-follow setup — Stage 2 stock pulling away from its value cluster on confirmed BOS. The "ride the trend" entry. Bonus = 0 because Stage = +3 and VP above VAH = +3 are already maxing the component contribution.

**Action:** Long on any minor pullback to prior VAH (now support) or to the breakout candle. Trail with ATR.

---

### S6 — SOS Momentum Push *(priority 2, bonus 0)*

**Wyckoff Sign-of-Strength continuation.** A wide-range, high-volume, closing-strong up-bar (SOS) has just printed, confirming demand is overpowering supply.

**Conditions (ALL required):**
- No higher-priority setup is active
- Most recent Wyckoff event is **SOS** within the last 10 bars
- VP score ≥ 1
- SMC trend = bullish

**What it captures:** The "vertical move" within Phase D — Wyckoff's institutional jump-across-the-creek bar. Bonus = 0 because Wyckoff component is already maxed (+4 for SOS).

**Action:** Long on the first shallow pullback (3-bar low or back to SOS midpoint). Trail aggressively — SOS bars often precede further mark-up but also climaxes.

---

### S7 — Distribution Breakdown *(priority 3, bonus −2)* — bearish

**The bearish mirror of S3.** Confirmed Wyckoff distribution event, broken SMC trend, bearish VP position, and broadly negative context. This is the **EXIT / SHORT** flag.

**Conditions (ALL required):**
- No higher-priority bull setup (S2) is active
- Most recent Wyckoff event is **SOW**, **LPSY**, or **UT** (distribution events)
- Event is **fresh** — within the last 15 bars
- SMC trend = **bearish** (`smc_trend_up = false`)
- Either price is **inside a bearish OB** OR VP score ≤ −1
- BASE SCORE ≤ −3

**What it captures:** Composition of supply has fully revealed itself — exit-volume bars (SOW/UT) plus structural breakdown plus VP rejection above. Symmetric to S3 in conviction, hence the −2 (same magnitude as S3's +2).

**Action:** Exit longs immediately. Consider short with stop above the SOW/UT/LPSY high.

---

### S8 — Choppy Range *(priority 1, bonus −1)* — sit out

**Structural-noise warning.** The market structure has flipped (CHoCH) three or more times in the last 20 bars, indicating no trend regime — only mean reversion at best, random walk at worst.

**Conditions (ALL required):**
- **No other setup** has fired (`_setup_pri == 0` — S8 never overrides anything; it only labels the bar when nothing else qualifies)
- CHoCH count in last 20 bars ≥ 3

**What it captures:** The "do not trade trend strategies here" signal. Multiple character changes in a tight window means each prior signal was a false start. The −1 bonus is a gentle nudge toward NEUTRAL — not a panic, just "step aside."

**Action:** No new positions. Tighten stops on existing positions or reduce size. Wait for one clean BOS to clear the chop.

---

### Setup Selection Order — Reading the Detector

When multiple setups *could* fire, the priority order resolves the conflict:

```
Bar evaluation:
  if S2 conditions met        → flag S2 (pri 5), done
  elif S3 conditions met      → flag S3 (pri 4), done
  elif S1 conditions met      → flag S1 (pri 3), done
  elif S4/S5/S6 conditions    → flag whichever fires first (pri 2)
  if S7 conditions met        → S7 overrides anything < pri 3
  if no setup fired and chop  → flag S8 (pri 1)
  else                        → NONE
```

Note that **S7 is evaluated independently of bull setups** — it can override S1/S4/S5/S6 (priority ≤ 3) but cannot override S2 (priority 5). This is by design: if a Spring/LPS just printed but you also see fresh distribution, S2 wins. Treat the rare S2-vs-S7 ambiguity as a flag to re-examine the chart manually.

### Setup → Screener Catalyst Mapping

| Setup | Maps to screener catalyst(s) |
|---|---|
| S1 | POS-AC, SWG-PB |
| S2 | POS-BO (Spring) / POS-AC (LPS) — strongest tier |
| S3 | SWG-PB, SWG-BO |
| S4 | SWG-PB (VA support variant) |
| S5 | POS-BO (Stage 2 continuation) |
| S6 | POS-BO (momentum), SWG-BO |
| S7 | REV-* (distribution / exit / short candidate) |
| S8 | — (no trade) |

This mapping is informational — the screener computes catalysts independently from OHLCV; WCL setups are the **chart-level confirmation** that the same conditions exist on the timeframe you're trading.

---

## 3. Real-World Scenarios — How v1.2 Differs from v1.1

### Scenario 1 — Borderline BULL tips into STRONG BULL on S2

A stock in Stage 2 with mid-strength components (Wyk +2 from old Spring, VP +1 from VA upper, SMC +3 from bullish trend, Stage +3 from Stage 2). Total = 9. In v1.1 this is BULL. Now a fresh S2 (Spring/LPS) fires.

| Version | Base | Bonus | Final | Band | Action |
|---|---|---|---|---|---|
| v1.1 | 9 | — | 9 | STRONG BULL (≥ 8) | Full Kelly OK |
| v1.2 | 9 | +2 | 11 | STRONG BULL (≥ 9) | Full Kelly OK + much stronger signal |

The band is the same, but the displayed score `(9+2=11)` makes the conviction visible.

### Scenario 2 — v1.2 promotes a setup that v1.1 missed

Wyk +2 + VP +1 + SMC +2 + Stage +1 = 6. v1.1 = BULL borderline. S3 fires.

| Version | Base | Bonus | Final | Band |
|---|---|---|---|---|
| v1.1 | 6 | — | 6 | BULL (≥ 4) |
| v1.2 | 6 | +2 | 8 | BULL (still — needs ≥ 9 in v1.2) |

Wait — in v1.1 the band was BULL (≥ 4 to < 8), in v1.2 it's also BULL (4 to 8). So same. But the score is more informative (8 vs 6).

### Scenario 3 — S7 turns CAUTION into BEAR

Wyk −2 + VP −1 + SMC −2 + Stage 0 = −5. v1.1 = CAUTION. S7 fires.

| Version | Base | Bonus | Final | Band |
|---|---|---|---|---|
| v1.1 | −5 | — | −5 | CAUTION |
| v1.2 | −5 | −2 | −7 | **BEAR** |

v1.2 escalates the warning. The trader sees BEAR + S7 attribution = exit/short conviction.

### Scenario 4 — S8 nudges BULL closer to NEUTRAL

Wyk +2 + VP +1 + SMC +1 + Stage 0 = 4. v1.1 = BULL borderline. S8 fires (3+ CHoCH in 20 bars).

| Version | Base | Bonus | Final | Band |
|---|---|---|---|---|
| v1.1 | 4 | — | 4 | BULL |
| v1.2 | 4 | −1 | 3 | **NEUTRAL** |

v1.2 demotes choppy-structure setups out of the actionable zone. This is desirable — sitting out is the right call.

---

## 4. Updated Panel Layout (24 rows)

### Score Section (rows 19–23) — NEW

```
── SCORE ──                                        ← row 19 divider
BASE SCORE       ● 6                               ← row 20 (NEW: raw _total)
SETUP BONUS      ✓ +2  (from S2)                   ← row 21 (NEW: signed bonus + attribution)
FINAL SCORE      ✓ STRONG BULL  (6+2=8)            ← row 22 (was CONTEXT SCORE in v1.1)
BREAKDOWN        Wyk:3 VP:3 SMC:0 Stg:0 Bns:+2     ← row 23 (NEW: adds Bns)
```

The FINAL SCORE cell color matches the band (Spring/Teal/Gray/Orange/Red). The displayed math `(6+2=8)` shows base + bonus = final so attribution is transparent.

### Other Panel Rows (Unchanged)

Rows 0–18 identical to v1.1 — see [v1.1 guide Section 3](13_Context_Layers_v1.1_Guide.md#3-the-context-panel--row-by-row-22-rows).

---

## 5. Updated Entry Qualification Checklist

For a **full-size** position in v1.2:

```
☑  Dashboard: STAGE 2 (UP) + ALPHA ≥ 60 + REC = BUY or STRONG BUY
☑  Context Panel: FINAL SCORE = BULL or STRONG BULL (≥ 4)
☑  STRUCTURE HEALTH: CLEAN or CHOPPY (≤2)
☑  WEINSTEIN STAGE: 2 - Advancing (score +3)
☑  VP POSITION: ✓ ABOVE VAH or ✓ IN VA (upper)
☑  WYCKOFF BIAS: ✓ ACCUMULATION
☑  SMC TREND: ✓ BULLISH
☑  SETUP row: any S1–S6 active (non-zero bonus or S5/S6)
☑  BULL OB ZONE: ✓ [zone] OR ✓ CLEAR
☑  SETUP BONUS: ≥ 0  (positive bonus = added conviction; 0 = neutral; never enter on a negative bonus)
```

The only addition is the last item — explicitly require non-negative bonus. A negative bonus means S7 or S8 is active, both of which are exit / sit-out signals.

### Position Sizing by Setup (Updated)

The bonus table aligns naturally with position size:

| Setup | Bonus | Suggested Size |
|---|---|---|
| S2 | +2 | **1.25× Full Kelly** |
| S3 | +2 | 1.00× |
| S1 | +1 | 1.00× |
| S4/S5/S6 | 0 | 0.75–1.00× |
| NONE (FINAL SCORE ≥ BULL) | 0 | 0.75× (no specific setup) |
| S8 | −1 | 0× (sit out) |
| S7 | −2 | 0× longs / consider short |

---

## 5.5. Trading Playbook — How to Trade Each Setup

This section is the **execution manual**: for every S1–S8 you get entry trigger, stop placement, profit targets, trade-management rules, and the invalidation criteria that force an immediate exit. Position sizes assume the standard 1% risk-per-trade DNA rule; the Kelly multiplier scales that 1% per setup conviction.

> **Universal rules across all setups:**
> - Confirm the WCL panel reading on the **same timeframe you are entering on** (don't trade an S2 reading on the Daily by entering on a 15-min impulse — the panel state is timeframe-specific).
> - Position size = (Account × 1% × Kelly multiplier) / |Entry − Stop|.
> - All stops are **ATR-aware**. Use 14-period ATR of the entry timeframe; clamp the stop to at least 1×ATR away from entry to survive normal noise.
> - **Never** enter on a NEGATIVE SETUP BONUS (S7 or S8 active) for a long. Mirror the rule for shorts.

### S2 — Spring/LPS Reversal (Full Kelly × 1.25)

| Field | Detail |
|---|---|
| **Entry trigger** | Close above the Spring/LPS pivot high on volume ≥ 1.5× the 20-bar average. If LPS variant: enter on the first up-bar that holds above the prior swing low. |
| **Stop** | Below the Spring/LPS bar's low (the swept low), minus 0.25 × ATR buffer. This is the structural invalidation — if price re-enters the swept zone, the spring failed. |
| **Target 1 (50% off)** | POC (Point of Control) — the high-volume midpoint of the value area. Typically a 2-3R take. |
| **Target 2 (25% off)** | VAH (Value Area High). Often the next supply node. |
| **Runner (25%)** | Trail with 2 × ATR or the 20-EMA — whichever is wider. Hold for full Stage 2 mark-up. |
| **Trade management** | Move stop to break-even at +1R. After T1, trail at the most recent confirmed HL (higher low) printed by the BOS module. |
| **Invalidation (force exit)** | (a) Spring low broken intrabar; (b) WCL prints CHoCH ▼ within 10 bars of entry; (c) Wyckoff bias flips to DISTRIBUTION. |
| **Holding period** | 4-12 weeks (positional). S2 typically launches multi-week Stage 2 advances. |

### S3 — Sweep + CHoCH Reversal (Full Kelly × 1.00)

| Field | Detail |
|---|---|
| **Entry trigger** | Don't chase the CHoCH bar. Wait for the **pullback into the sweep candle origin** OR into the most recent Bullish OB created by the BOS that printed the CHoCH. |
| **Stop** | Below the sweep low (the wick that took out the prior swing low) − 0.25 × ATR. |
| **Target 1 (50% off)** | The most recent **lower high** that the CHoCH broke — usually a 2-3R take. |
| **Target 2 (50% off)** | Next major liquidity pool above (prior swing high, VAH, or a known supply zone). |
| **Trade management** | Aggressive — at +1.5R, trail to BE; at +2R, take 50% off. The remainder rides the new trend with a 2 × ATR stop. |
| **Invalidation** | (a) Bear CHoCH ▼ prints; (b) price closes back below the sweep low; (c) BASE SCORE drops below 0. |
| **Holding period** | Swing — 1-3 weeks. Faster trade than S2. |

### S1 — OB Retest + VP Support (Full Kelly × 1.00)

| Field | Detail |
|---|---|
| **Entry trigger** | A bullish reaction candle (hammer / bullish engulfing / inside-bar break) inside the OB box on the panel. The OB box on chart is the entry zone, not a precise price. |
| **Stop** | Below the OB low − 0.25 × ATR. The OB low is the institutional footprint; a close below it invalidates the block. |
| **Target 1 (50% off)** | POC or VAH (whichever is closer, typically 1.5-2.5R). |
| **Target 2 (50% off)** | Prior swing high or next supply zone above. |
| **Trade management** | Move stop to BE at +1R. If the trade stalls inside VA for >5 bars without making a higher high, exit at BE — the setup has timed out. |
| **Invalidation** | (a) OB low broken on close; (b) Wyckoff bias flips off ACCUMULATION; (c) BASE SCORE falls below 3. |
| **Holding period** | 5-15 bars on the entry timeframe. This is a **mean-reversion-to-trend** trade, not a multi-month hold. |

### S4 — VAL Bounce + Bull FVG Stack (Full Kelly × 0.75-1.00)

| Field | Detail |
|---|---|
| **Entry trigger** | Confirmed bullish bar (close > open, close in upper 50% of range) with low at or within 1% of VAL. Volume should be at least average. |
| **Stop** | Below VAL − 0.5 × ATR. VAL is a "soft" floor; a close below it invalidates the auction-rotation thesis. |
| **Target 1 (60% off)** | POC. This is a high-probability scalp/swing — VAL→POC is the standard auction-rotation play. |
| **Target 2 (40% off)** | VAH. If price punches through POC with momentum, hold for the full value-area traverse. |
| **Trade management** | Tight management — at +1R, trail stop just below the most recent bullish FVG that's been mitigated. The remaining bull FVGs above are stepping-stone targets. |
| **Invalidation** | (a) Close below VAL; (b) more bear FVGs created than bull FVGs above; (c) Wyckoff flips to DISTRIBUTION. |
| **Holding period** | 2-10 bars. This is a **value-area auction** trade — fast. |

### S5 — Stage 2 Continuation Above VAH (Full Kelly × 0.75-1.00)

| Field | Detail |
|---|---|
| **Entry trigger** | Two paths: (a) pullback entry — wait for a 3-bar low into prior VAH (now support) and enter on bullish reaction; (b) breakout add — enter on the next BOS ▲ that prints above current price. |
| **Stop** | Below prior VAH (the support level the pullback bounced from) − 0.5 × ATR. |
| **Target 1 (33% off)** | +1.5R — quick profit lock to fund the runner. |
| **Target 2 (33% off)** | Measured move: width of the prior value area projected up from VAH. |
| **Runner (34%)** | Trail with 30-WMA (weekly anchor) — the position rides Stage 2 until the weekly Stage flips. |
| **Trade management** | This is a **trend-follow**. Resist tightening stops; let normal pullbacks breathe. Only exit the runner on weekly Stage 3 print or close back below 30-WMA. |
| **Invalidation** | (a) Close below 30-WMA; (b) Stage flips to 3 - Topping; (c) CHoCH ▼ on entry TF. |
| **Holding period** | 6 weeks to 6 months. The runner is positional, not swing. |

### S6 — SOS Momentum Push (Full Kelly × 0.75)

| Field | Detail |
|---|---|
| **Entry trigger** | DON'T enter on the SOS bar itself (too extended). Wait for the **first 2-3 bar pullback** that holds above the SOS midpoint, then enter on the next up-close. |
| **Stop** | Below the SOS bar's low − 0.25 × ATR. If price violates the SOS low, the entire momentum thesis is broken. |
| **Target 1 (50% off)** | +1.5R-2R. SOS bars often produce one further leg but climaxes are common. |
| **Target 2 (50% off)** | Trail with a 3-bar trailing stop (most recent 3-bar low) — aggressive, locks gains on stalls. |
| **Trade management** | Watch for **BC (Buying Climax)** or **UT (Upthrust)** on the panel — both are exit signals even before stop hit. Reduce size if Wyckoff event flips to PSY/BC. |
| **Invalidation** | (a) BC / UT prints; (b) close below SOS midpoint; (c) Wyckoff bias decays out of ACCUMULATION (use the decay-aware `wyk_score_comp` reading on panel). |
| **Holding period** | 5-15 bars. Momentum trades fade fast. |

### S7 — Distribution Breakdown (EXIT longs / SHORT candidate)

| Field | Detail |
|---|---|
| **For existing longs** | **Exit immediately** — no waiting. S7 means the distribution thesis is confirmed by 4 independent conditions; the burden of proof has shifted. |
| **For shorts (if mandate allows)** | Entry on first pullback into the SOW/UT/LPSY bar or into the nearest Bearish OB (panel shows it). |
| **Stop (short)** | Above the SOW/UT/LPSY high + 0.5 × ATR. For UT specifically: stop above the upthrust wick. |
| **Target 1 (50% off)** | POC (if price was above VA) or VAL (if rejection happened at VAH). |
| **Target 2 (50% off)** | Prior swing low / 30-WMA. |
| **Invalidation (short)** | (a) Bull CHoCH ▲ prints; (b) close back above the SOW high; (c) BASE SCORE recovers above 0. |
| **Holding period** | 5-20 bars for shorts; immediate for long-exits. |
| **NSE caveat** | Indian retail traders often can't short equity beyond intraday. Use S7 primarily as an **exit / no-buy** signal, not a short entry, unless you trade derivatives. |

### S8 — Choppy Range (SIT OUT)

| Field | Detail |
|---|---|
| **Action** | No new entries. Period. |
| **For existing positions** | Tighten stops to half the normal ATR distance OR scale out to 50% size. Choppy structure leads to whipsaw stops. |
| **What to watch for** | Wait for **one clean BOS** (no CHoCH within 20 bars after it) — that's the signal the chop is resolving. Or wait for the chop to print an S2 / S3 inside the range (range failure swing). |
| **Time discipline** | If S8 persists for >40 bars, the symbol is in a true balance regime — move it off the active watchlist and recheck monthly. |
| **Common mistake** | Forcing a "mean reversion" trade inside chop. Without a defined edge (such as a clear S4 with positive bonus), random range-trading is negative-expectancy after slippage. |

### Cheat Sheet — Setup at a Glance

| Setup | Kelly × | Stop Reference | Target | Hold | Trade Class |
|---|---|---|---|---|---|
| S2 | 1.25× | Spring low − 0.25 ATR | POC → VAH → trail | 4-12 wk | Positional |
| S3 | 1.00× | Sweep low − 0.25 ATR | Prior LH → next pool | 1-3 wk | Swing |
| S1 | 1.00× | OB low − 0.25 ATR | POC/VAH → swing high | 5-15 bars | Swing |
| S4 | 0.75-1.00× | VAL − 0.5 ATR | POC → VAH | 2-10 bars | Auction |
| S5 | 0.75-1.00× | Prior VAH − 0.5 ATR | +1.5R → measured → trail 30WMA | 6 wk-6 mo | Positional |
| S6 | 0.75× | SOS low − 0.25 ATR | +1.5R-2R → 3-bar trail | 5-15 bars | Momentum |
| S7 | 0× longs / 1× short | SOW high + 0.5 ATR | POC/VAL → swing low | 5-20 bars | Mean revert |
| S8 | 0× | — | — | — | No trade |

### Multi-Setup Sequencing — How Setups Chain in Real Trading

A clean Stage 2 advance often produces a textbook setup *sequence*. Watching for the sequence rather than the isolated event improves conviction:

```
Phase C/D:  S2 (Spring/LPS)       → first entry
Phase D:    S6 (SOS Momentum)     → add on first 2-3 bar pullback
Phase D/E:  S1 (OB Retest)        → add on each clean retest of new OBs
Phase E:    S5 (Stage 2 Cont.)    → trailing position; ride the mark-up
Phase E top: S7 (Distribution)    → exit signal
```

Conversely, the failed-setup tell: **S2 → S8 within 10 bars** means the Spring was a bull-trap — exit immediately, do not wait for stop.

---

## 6. Anti-Circularity — How v1.2 Avoids the Loop

The naive design "setup uses score, score uses setup" would be circular. v1.2 breaks this with strict ordering:

```pine
// 1. Components compute first
_smc_score = ...
_ob_score  = ...
_total     = wyk_score_comp + _vp_score + (_smc_score + _ob_score) + stage_score

// 2. Setup Detector runs using _total (BASE SCORE) only
if en_stp
    if ... and _total >= 6
        _setup_pri := 5   // S2
    ...

// 3. NOW compute bonus from detected setup
_setup_bonus = ...   // 0 / +1 / +2 / −1 / −2

// 4. FINAL score uses bonus
_total_final = _total + _setup_bonus

// 5. Band assigned from FINAL score
if _total_final >= 9
    _score_str := "STRONG BULL"
```

Setup conditions on lines like `_total >= 6` (S2) and `_total <= -3` (S7) explicitly use the raw `_total` — they never see their own bonus. This is enforced by code order, not just convention.

---

## 7. Updated Common Mistakes

1. **(NEW v1.2) Reading FINAL SCORE without checking SETUP BONUS attribution.** A score of 8 (BULL) generated by base 6 + S2 bonus +2 is a fundamentally different signal than a pure base 8 with no setup. The bonus attribution tells you *why* the score is what it is.

2. **(NEW v1.2) Using v1.1 thresholds (≥ 8 for STRONG BULL).** v1.2 raises this to ≥ 9 because the bonus adds headroom. Don't import old Risk Allocator presets blindly.

3. **(NEW v1.2) Expecting S4/S5/S6 to add bonus.** They don't — by design. Their conditions already drive component scores. The setup label still appears in the SETUP row for situational awareness, but bonus = 0.

4. **(NEW v1.2) Entering longs on negative SETUP BONUS.** A negative bonus comes from S7 (distribution) or S8 (choppy). Both are exit / sit-out signals. If FINAL SCORE is still in BULL band despite negative bonus, that's a stale signal — wait for it to roll over.

5. (Carried from v1.1) Loading WCL alongside the three separate modules (WWP/WVP/WSMC) — WCL replaces all three.

6. (Carried from v1.1) Acting on Wyckoff events in isolation without VP context.

---

## 8. Migration Path v1.1 → v1.2

1. **Remove v1.1** from your TradingView indicators panel.
2. **Add v1.2** — `Weinstein_Context_Layers_v1.2.pine`.
3. **Recalibrate Risk Allocator and screening thresholds:**
   - STRONG BULL threshold: ≥ 8 → **≥ 9**
   - Other bands unchanged
4. **Update entry checklist** to require non-negative SETUP BONUS (Section 5).
5. **Verify Unified Ecosystem v2.5 E11 wiring** still works — `wcl_setup_pri_export` plot is preserved.
6. **Run side-by-side on 5–10 stocks** with both v1.1 and v1.2 to see where the FINAL SCORE diverges.

### Expected Behavioral Differences

- **More STRONG BULL signals on S2/S3 firings** — bonus pushes borderline BULL into STRONG BULL.
- **More BEAR signals on S7 firings** — bonus pushes CAUTION into BEAR.
- **Slightly fewer BULL signals on choppy stocks** — S8 penalty demotes them.
- **No change** on stocks with no detected setup or S4/S5/S6 active.

---

## 9. Module Parameters — Complete Reference

All inputs are identical to v1.1 (the v1.2 Setup Bonus is computed automatically from detection — no new inputs). This section is the full operator manual: defaults, valid ranges, what each parameter actually changes, and tuning guidance per timeframe.

### 9.1 Master Controls

| Input | Default | Range | What it does |
|---|---|---|---|
| Enable Wyckoff Module | `true` | bool | Turns off Wyckoff event detection and labels. The Wyckoff score component still feeds the panel if disabled here — only chart labels are suppressed. |
| Enable Volume Profile Module | `true` | bool | Disables VP histogram, POC, VAH, VAL drawing. VP score still contributes. |
| Enable SMC Zones Module | `true` | bool | Disables OB boxes, FVG boxes, BOS/CHoCH labels, sweep markers. SMC scores still contribute to context. |
| Enable Setup Detector | `true` | bool | When OFF, the Setup row displays "OFF" and the bonus is 0. Use OFF for component-only review. |
| Show Context Panel | `true` | bool | Toggle the right-side info panel entirely. |
| Panel Position | `Top Left` | 9 options | Place the panel where it doesn't overlap your draws/zones. |
| Panel Text Size | `Small` | Tiny / Small / Normal | Use Tiny on multi-pane layouts; Normal for screenshots. |

### 9.2 Weinstein Stage

| Input | Default | Range | What it does |
|---|---|---|---|
| Current Weinstein Stage | `2 - Advancing` | 1/2/3/4 + Auto | Drives the **Stage Score** component (+3 / +1 / −2 / −4). **Auto** uses 30-WMA slope (rising → Stage 2; flat → Stage 1; falling+above → Stage 3; falling+below → Stage 4). |

**Tuning guidance:** Auto is convenient but the 30-WMA needs ~30 weekly bars of history. For newly listed stocks or post-merger tickers, set the stage manually. Disagreement between manual and Auto is a useful signal — it usually means the stock is transitioning between stages.

### 9.3 Wyckoff Parameters

#### Swing Settings

| Input | Default | Range | What it does |
|---|---|---|---|
| Pivot Length | `10` | 3-30 | Number of bars left+right required to confirm a swing high/low. **Higher = fewer, stronger pivots** (good for positional). Lower = more pivots, more events (good for swing/intraday). |
| Volume Avg Lookback | `20` | 10-50 | Bar count for the volume SMA baseline. 20 is the institutional default; raise to 50 for very low-volatility names. |
| High Volume Threshold (× avg) | `1.5` | 1.1-5.0 | A bar qualifies as "high volume" when volume > avg × this multiplier. Used to detect SC, BC, SOS, SOW, UT events. **Higher = stricter, fewer events**. |
| Low Volume Threshold (× avg) | `0.7` | 0.2-1.0 | A bar qualifies as "low volume" when volume < avg × this multiplier. Used to detect Spring, LPS, ST, LPSY (events that DEMAND low supply). Lower = stricter. |
| Score decay step (bars) | `15` | 5-60 | Wyckoff score fades by 25% every N bars after the event fires. Default of 15 gives half-life ≈ 45 bars. **Lower = score decays faster, prefers fresh setups**. Raise to 30+ for very long-hold positional. |

**Tuning by timeframe:**
- **Daily positional:** defaults (Pivot 10, Vol Lookback 20, Decay 15) work well.
- **Weekly positional:** Pivot 5-7, Decay 30, High Vol Threshold 1.3 (weekly volume is smoother).
- **75/125-min swing:** Pivot 5-7, Decay 10 (events fade faster on lower TFs).

#### Display

| Input | Default | What it does |
|---|---|---|
| Show Accumulation Events | `true` | SC, PS, ST, Spring, LPS, SOS, AR labels |
| Show Distribution Events | `true` | BC, PSY, UT, LPSY, SOW, AR labels |
| Show Volume Multiplier in Label | `true` | Appends `(2.3×)` to labels for at-a-glance event-strength reading |

### 9.4 Volume Profile Parameters

| Input | Default | Range | What it does |
|---|---|---|---|
| Lookback Bars | `100` | 20-500 | The profile is built over the last N bars. **100 daily bars ≈ 5 months**, the institutional "intermediate-term value" lookback. For swing trades on the 75/125-min, use 60-80 (1-2 weeks of session bars). |
| Profile Rows | `40` | 10-80 | Number of price bins. More rows = finer POC resolution but choppier histogram. 40 is a good balance. |
| Value Area % | `70.0` | 50-95 | The %-of-volume cutoff for VA. 70% is the institutional / TPO standard. Lower (60%) tightens VA — more breakouts; higher (80%) widens — more rotations. |
| Histogram Width (bars) | `25` | 5-60 | Visual only — controls how wide the histogram stretches into the chart. |

**Display flags:** `Show Histogram`, `Show POC`, `Show Value Area`, `Show Price Labels`, `Extend POC/VA Left` (extend lines back to the start of the lookback for context).

**Critical tuning:** If you change `Lookback Bars`, the entire profile rebuilds. Be aware that a Lookback that doesn't include the most recent major swing high+low will produce a misleading POC. Rule of thumb: lookback should encompass at least one full price excursion of the symbol's typical range.

### 9.5 SMC Parameters

#### Order Blocks

| Input | Default | Range | What it does |
|---|---|---|---|
| Swing Length for OB | `5` | 3-20 | Pivot length for OB identification. Lower = more (smaller) OBs; higher = fewer (more significant) OBs. |
| Max OBs to Show | `5` | 1-20 | Cap on active OB boxes on chart. The oldest is dropped when the cap is reached. |
| Keep Mitigated OBs | `false` | bool | When OFF (default), an OB is removed once price closes through it (mitigation). When ON, kept as historical reference (gets visually faded). |

#### Fair Value Gaps

| Input | Default | Range | What it does |
|---|---|---|---|
| Show FVGs | `true` | bool | Toggle FVG box drawing. |
| Min Gap Size (% of price) | `0.05` | 0.0-2.0 | Filters noise. Default catches small daily gaps; raise to 0.15-0.25 on volatile small-caps to avoid micro-gaps. |
| Auto-remove Mitigated FVGs | `true` | bool | Remove FVG when price fully fills it. Recommended ON. |
| Max FVGs to Show | `10` | 1-30 | Cap. Affects the panel's Bull/Bear FVG counter — only currently active FVGs are counted. |

#### BOS / CHoCH

| Input | Default | Range | What it does |
|---|---|---|---|
| Show BOS Labels | `true` | bool | Draw BOS ▲ / BOS ▼ labels and structure lines. |
| Show CHoCH Labels | `true` | bool | Draw CHoCH ▲ / CHoCH ▼ labels. CHoCH is the **first BOS against trend** — i.e., a character change. |
| Swing Length for BOS | `10` | 3-30 | Pivot length defining swing highs/lows whose break = BOS. Higher = trades only on major structure (positional); lower = sensitive to every minor swing (intraday). |

The CHoCH count over a sliding 20-bar window also drives:
- **Structure Health** row on panel (CLEAN ≤ 0, CHOPPY 1-2, BROKEN ≥ 3)
- **S5 gate** (rejected if CHoCH count > 1)
- **S8 trigger** (fires if CHoCH count ≥ 3)

#### Liquidity Sweeps

| Input | Default | Range | What it does |
|---|---|---|---|
| Show Liquidity Sweeps | `true` | bool | Draw `Liq Sweep ▲` / `Liq Sweep ▼` markers. |
| Swing Length for Sweeps | `10` | 3-30 | Pivot length for the "prior swing" that's being swept. Match this to the timeframe's typical stop-hunt range. |

A sweep requires: price prints a low **below** the prior pivot low AND closes **above** it (bullish sweep) — or mirror for bearish. The S3 setup checks for a bullish sweep + bullish CHoCH within 10 bars.

### 9.6 Colors (cosmetic, not strategy-affecting)

All color inputs are grouped per module (Wyckoff Colours / VP Colours / OB Bull/Bear / FVG Bull/Bear / BOS Bull/Bear / Sweep). The light theme is the canonical choice per project DNA — the STRONG BULL teal (`#1de9b6`) and the darker "in-Bear-OB" red (`#b71c1c`) are intentionally distinct for instant visual reading.

### 9.7 Recommended Profile Presets

Three battle-tested presets covering the project's trading styles:

#### Daily Positional (default — keep as-is)
- Pivot 10 / Vol Lookback 20 / Decay 15 / VP Lookback 100 / OB len 5 / BOS len 10 / Sweep len 10
- Stage = Auto
- Use for: Hunter / EarlyBird / Pullback picks on the daily timeframe.

#### Weekly Positional (Phase A/E of Stage 2 trades)
- Pivot 5 / Vol Lookback 15 / Decay 30 / VP Lookback 80 / OB len 4 / BOS len 6 / Sweep len 6
- High Vol Thresh 1.3 / Low Vol Thresh 0.6
- Stage = Manual (set to 2)
- Use for: long-hold trail decisions on positional names.

#### 75/125-min Swing
- Pivot 7 / Vol Lookback 30 / Decay 10 / VP Lookback 80 / OB len 5 / BOS len 8 / Sweep len 8
- Stage = manual to match the Daily reading (don't recompute Stage on intraday — it's noisy)
- Use for: tactical entries on the LTF for swing/Pullback trades.

### 9.8 Inter-Module Dependencies (Don't Break)

Some parameter combinations create degenerate states — avoid:

1. **Wyckoff Vol Lookback < Pivot Length** → events confirm before there's enough volume history. Keep `wyk_vol_lookbk ≥ wyk_pivot_len × 2`.
2. **VP Lookback shorter than the most recent significant move** → POC anchors to noise. If the chart has just made a 6-month high, lookback should be at least 100 bars.
3. **OB Swing Length > BOS Swing Length** → OBs are identified from larger pivots than the structure-defining pivots. Keep `smc_ob_len ≤ smc_bos_len`.
4. **Score decay step < 5** → score evaporates in days. Use only on intraday TFs.
5. **Setup Detector OFF + relying on FINAL SCORE** → bonus is always 0, so FINAL = BASE. Acceptable but you lose the v1.2 feedback loop.

### 9.9 What is NOT Tunable (by design)

- The 8 setup detection thresholds (`_total ≥ 6` for S2, `_total ≥ 3` for S1, etc.) — hardcoded for reproducibility. To change them, fork the file.
- The Setup Bonus values (+2 / +1 / 0 / −1 / −2) — locked per the priority table in §0.
- The score band thresholds (≥ 9 STRONG BULL, ≥ 4 BULL, etc.) — see §0 recalibration table.
- The 5-bar / 10-bar / 15-bar / 20-bar freshness windows used in setup gates — hardcoded.

To change any of the above, edit the Pine source directly and re-publish as a private fork (`v1.2-jay`, e.g.).

---

## 10. Ecosystem Integration (Updated)

| Component | v1.2 Integration |
|---|---|
| **Dashboard v67.4.12** | Same as v1.1 — provides Stage + Alpha + Recommendation. Cross-check FINAL SCORE before acting. |
| **Unified Ecosystem v2.5** | `wcl_setup_pri_export` plot preserved. E11 gate now responds to setups that ALSO contribute to the bonus — alignment is tighter. |
| **Risk Allocator v1.0** | Use FINAL SCORE (not BASE SCORE) for position sizing. S2 with +2 bonus = full Kelly trigger. |
| **Bull Screener v3.2** | Screener output → load in WCL v1.2 → check FINAL SCORE + SETUP BONUS for entry timing. |

---

*Last updated: 2026-05-17. v1.2 is the canonical Context Layers reference. v1.1 guide preserved for historical analysis using the older thresholds (STRONG BULL ≥ 8).*
