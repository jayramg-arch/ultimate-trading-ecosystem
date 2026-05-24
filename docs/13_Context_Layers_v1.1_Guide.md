# Weinstein Context Layers v1.1 — User & Trading Guide

> **Module Role:** Institutional context overlay for the Weinstein Commander ecosystem. v1.1 consolidates four analytical frameworks — **Wyckoff** + **Volume Profile** + **SMC** + **Weinstein Stage** — into a single overlay with a 22-row panel, eight auto-detected entry setups, and a decayed composite **CONTEXT SCORE**. It does not generate signals on its own; it validates the *quality of the environment* in which signals from the Strategy and Dashboard are firing.

> **Supersedes:** `12_Context_Layers_v1_Guide.md` (kept alongside for v1.0 reference). Migrating from v1.0 is drop-in — same inputs, expanded panel.

---

## 0. What Changed from v1.0

### Bug Fixes
| ID | Fix |
|---|---|
| **B1** | SC ↔ SOW disambiguation. SOW now requires a confirmed **lower-low pivot break**. The earlier code allowed both labels to fire on the same bar; that's now impossible. |
| **B2** | BC ↔ SOS disambiguation. BC now requires `not up_bar`, SOS requires `up_bar`. Mutually exclusive. |
| **B3** | Volume Profile heavy loop (`vp_lookback × vp_num_rows`) now runs only on `barstate.isconfirmed`. Realtime ticks just redraw lines from cached bins. Eliminates intraday lag on volatile NSE stocks. |
| **B4** | CHoCH variable names corrected — `smc_choch_up` is genuinely the bullish reversal CHoCH. |
| **B5** | Spring condition tightened — now requires `wyk_cls_hi` AND `wyk_up_bar` (no more 0.5% noise triggers). |
| **B6** | Wyckoff score decays 25% per `wyk_decay_bars` (default 15). Half-life ≈ 45 bars. Solves the "stale SOS still scoring +4 a year later" problem mechanically. |
| **B7** | BOS/CHoCH/sweep labels gated by `barstate.isconfirmed` — no more duplicate labels on the live bar. |

### Color Fixes (theme unchanged — still light)
| ID | Fix |
|---|---|
| **C3** | `STRONG BULL` now uses bright spring `#1de9b6`, visually distinct from `BULL` teal `#26a69a`. |
| **C4** | `Bear OB inside` now uses deep red `#b71c1c`; "present overhead" uses regular red. |
| **C5** | Context Score uses ✓ / ✗ / ● prefixes per the documented mark legend. |

### New Features
- **Weinstein Stage input** — 4th scoring component (manual or auto via 30-WMA slope).
- **Setup Detector** — 8 mechanical entry setups, auto-flagged on panel.
- **Structure Health** — sliding 20-bar CHoCH counter (CLEAN / CHOPPY / BROKEN).
- **OB % distance** — Bull/Bear OB rows show `(+5.2%)` distance to price.
- **Freshness fade** — Wyckoff bias, last SMC event, last sweep fade their cell color as the event ages (0 → 30 → 60 → 80% transparency at 10 / 30 / 60 / 60+ bars).
- **Score breakdown row** — shows each component's contribution: `Wyk:3 VP:3 SMC:3 Stg:3`.
- **Alerts** — 7 `alertcondition()` calls (SOS, Spring, SOW, CHoCH ▲/▼, Sweep ▲/▼).

### Behavioral Changes
- **Panel grew from 16 → 22 rows.** Position/text-size inputs unchanged.
- **Score thresholds widened** (4 components now → max ±14): STRONG BULL ≥ 8, BULL ≥ 4, NEUTRAL −3..+3, CAUTION ≤ −4, BEAR ≤ −7. Old thresholds (≥6 / ≥3) no longer applicable — recalibrate any spreadsheets.

---

## 1. Architecture Overview

`Weinstein_Context_Layers_v1.1.pine` combines four modules:

| Module | Shorthand | What It Provides | Chart Output |
|---|---|---|---|
| **Wyckoff Phase Detector** | `WYK` | 13 event labels identifying accumulation/distribution | Labels above/below pivots |
| **Fixed-Range Volume Profile** | `VP` | POC, VAH, VAL with histogram | Lines + histogram bars on right edge |
| **Smart Money Concepts** | `SMC` | Order Blocks, FVGs, BOS/CHoCH, Liquidity Sweeps | Boxes, dashed lines, labels |
| **Weinstein Stage** | `STG` | Stage 1/2/3/4 classification, manual or auto via 30-WMA slope | Panel row only (no chart drawing) |
| **Setup Detector** | `STP` | 8 mechanical entry setups synthesizing all four modules | Panel row showing active setup |
| **Context Panel** | `PANEL` | 22-row light-theme table with composite CONTEXT SCORE | Floating table |

### Key Design Principles
1. **No background coloring** — overlay only; reserved for Unified Ecosystem v2.2.
2. **Every module independently toggleable.**
3. **Panel state persistent** via `var` — last events shown even when many bars old.
4. **Liquidity Sweep panel display resets after 20 bars** — older sweeps stale.
5. **VP heavy calculation on bar close only** (B3 fix).
6. **Wyckoff score decays mechanically** (B6 fix) — stale events lose weight automatically.

---

## 2. Input Groups — Field-by-Field

### 🎛 Master Controls

| Input | Default | Explanation |
|---|---|---|
| **Enable Wyckoff Module** | `true` | Toggles Wyckoff labels & panel rows |
| **Enable Volume Profile Module** | `true` | Toggles VP histogram, POC/VAH/VAL lines, panel rows |
| **Enable SMC Zones Module** | `true` | Toggles OBs, FVGs, BOS/CHoCH labels, sweep labels, panel rows |
| **Enable Setup Detector** | `true` | Toggles auto-detection of S1–S8 |
| **Show Context Panel** | `true` | Toggles the panel without disabling drawings |
| **Panel Position** | `Top Left` | 9 positions |
| **Panel Text Size** | `Small` | `Tiny` / `Small` / `Normal` |

### Weinstein Stage (manual input) — NEW

| Input | Default | Explanation |
|---|---|---|
| **Current Weinstein Stage** | `2 - Advancing` | Sets a 4th Context Score component. Options: `1 - Basing` (+1), `2 - Advancing` (+3), `3 - Topping` (−2), `4 - Declining` (−4), `Auto (30-WMA slope)`. |

**Auto mode logic:**
| 30-WMA slope (10-bar diff) | Price vs 30-WMA | Stage |
|---|---|---|
| Rising | Above | 2 - Advancing |
| Rising | Below | 1 - Basing |
| Falling | Above | 3 - Topping |
| Falling | Below | 4 - Declining |

The 30-WMA approximation on daily charts uses `ta.sma(close, 150)` (≈30 weeks × 5 trading days).

### Wyckoff — Swing Settings

| Input | Default | Notes |
|---|---|---|
| Pivot Length | `10` | Larger = fewer higher-conviction pivots |
| Volume Avg Lookback | `20` | SMA length for volume thresholds |
| High Volume Threshold (×avg) | `1.5` | For climax / SOS / SOW |
| Low Volume Threshold (×avg) | `0.7` | For ST / Spring / LPS |
| **Score decay step (bars)** *(NEW)* | `15` | Wyckoff score fades 25% every N bars. 15 = half-life ≈ 45 bars. Set to 5–10 for short-term trading, 30+ for positional. |

### Wyckoff — Display
| Show Accumulation Events | `true` | All green/teal/purple labels |
| Show Distribution Events | `true` | All red/orange/purple labels |
| Show Volume Multiplier in Label | `true` | Appends `(2.3×)` to each label |

### Wyckoff — Colours
| Accumulation | Green | PS, ST, LPS, AR |
| Distribution | Red | PSY, ARd, LPSY |
| SOS / Strength | Teal | SOS |
| SOW / Weakness | Orange | SOW |
| Climax | Purple | SC, BC |

### Volume Profile — Settings, Display, Colours
*(Unchanged from v1.0 — see [12_Context_Layers_v1_Guide.md](12_Context_Layers_v1_Guide.md) Section 2 for details.)*

### SMC — Order Blocks, FVGs, BOS/CHoCH, Liquidity
*(Unchanged from v1.0 — see v1.0 guide Section 2.)*

---

## 3. The Context Panel — Row-by-Row (22 rows)

### Panel Color Key

| Colour | Hex | Meaning |
|---|---|---|
| **Bright Spring** | `#1de9b6` | Strong bullish (STRONG BULL score, price inside Bull OB) |
| **Teal** | `#26a69a` | Bullish condition |
| **Red** | `#ef5350` | Bearish condition |
| **Deep Red** *(NEW)* | `#b71c1c` | Price inside Bear OB (maximum danger) |
| **Orange** | `#ff9800` | Caution / neutral-negative |
| **Light Gray** | `#f5f5f5` | Neutral / no data |
| **Dark Navy** | `#1e222d` | Section dividers and header |

### Mark Prefix Legend (NOW USED CONSISTENTLY)
| Mark | Meaning |
|---|---|
| **✓** | Bullish — favors long |
| **✗** | Bearish — favors short / against long |
| **●** | Neutral / informational |
| **—** | No data, module off, expired |

### Freshness Fade (NEW)
The cells for **Wyckoff Bias**, **Last SMC Event**, and **Last Liq Sweep** fade their background color based on how stale the event is:

| Bars since event | Transparency |
|---|---|
| 0–10 | 0% (fresh, full color) |
| 11–30 | 30% (slight fade) |
| 31–60 | 60% (significant fade) |
| 60+ | 80% (barely visible) |

This is a visual cue — older events still appear, but you can see at a glance that their signal is weak.

---

### Row 0 — Header
`◈ CONTEXT LAYERS` — `WCL v1.1`

### Row 1 — `── SMC ZONES ──` divider

### Row 2 — SMC TREND
| `✓ BULLISH ▲` (green) | `✗ BEARISH ▼` (red) | `— MODULE OFF` |

### Row 3 — LAST SMC EVENT
Last BOS/CHoCH event + bars ago. **Cell color fades with age.**

| `✓ CHoCH ▲ (3 bars ago)` | bullish reversal — high importance, fresh |
| `✓ BOS ▲ (45 bars ago)` | bullish break — older, cell will be 60% transparent |
| `✗ CHoCH ▼ (2 bars ago)` | bearish reversal warning |

### Row 4 — BULL OB ZONE *(now with % distance)*
| `✓ 215.50 – 220.00  (+5.2%)` | Bull OB exists 5.2% below price |
| `✓ 215.50 – 220.00  (+0.3%)` | Bright Spring color — price **inside** Bull OB |
| `● NONE` | No active Bull OB |

The `+5.2%` distance means **price is 5.2% above the OB midpoint** (positive = OB is below; negative = OB is above).

### Row 5 — BEAR OB ZONE *(now with % distance)*
| `✗ 280.00 – 285.50  (+4.1%)` | Bear OB 4.1% overhead — red |
| `✗ 280.00 – 285.50  (+0.2%)` | **Deep red** — price inside Bear OB |
| `✓ CLEAR` | No Bear OB overhead — green |

The `+4.1%` distance means **OB midpoint is 4.1% above price**.

### Row 6 — OPEN FVGs
| `✓ Bull: 7  Bear: 2` | bullish FVG dominance |
| `✗ Bull: 2  Bear: 5` | bearish FVG dominance |

### Row 7 — LAST LIQ SWEEP
Resets to `—` after 20 bars. **Cell color fades with age.**

| `✓ Sweep ▲ (5 bars ago)` | bullish sweep — stop hunt below reversed |
| `✗ Sweep ▼ (3 bars ago)` | bearish sweep — stop hunt above rejected |

### Row 8 — STRUCTURE HEALTH *(NEW)*
Sliding 20-bar CHoCH counter — measures choppiness.

| Value | Meaning |
|---|---|
| `✓ CLEAN (0)` / `✓ CLEAN (1)` | Trending environment, structure intact |
| `● CHOPPY (2)` / `● CHOPPY (3)` | Multiple structure breaks — caution, reduce size |
| `✗ BROKEN (4+)` | No coherent trend — sit out |

**Trading read:** A `BULL` Context Score with `BROKEN` structure is misleading — the trend is fragile. Wait for `CLEAN` or `CHOPPY (≤2)` before entering.

### Row 9 — `── WYCKOFF ──` divider

### Row 10 — WYCKOFF BIAS
Persistent. **Cell color fades with age.**
| `✓ ACCUMULATION` / `✗ DISTRIBUTION` / `● NEUTRAL` |

### Row 11 — LAST EVENT *(now shows decayed score)*
Format: `✓ SOS (2.1×) (8 bars ago)  [s:4]`

The `[s:N]` shows the **current decayed score** for this event:
| Bars ago | Decay multiplier | SOS base +4 becomes |
|---|---|---|
| 0–14 | 1.00 | 4 |
| 15–29 | 0.75 | 3 |
| 30–44 | 0.50 | 2 |
| 45–59 | 0.25 | 1 |
| 60+ | 0.00 | 0 |

So an SOS from 50 bars ago contributes `[s:1]` to the Context Score, not the old +4.

### Row 12 — `── VOL PROFILE ──` divider

### Row 13 — VP POSITION
| `✓ ABOVE VAH` (+3) | `✓ IN VA (upper)` (+1) | `✗ IN VA (lower)` (−1) | `✗ BELOW VAL` (−3) |

### Row 14 — VP LEVELS
`● POC 233.28 │ VAH 271.75 │ VAL 216.35`

### Row 15 — DIST TO POC *(asymmetric coloring)*

| Range | Color | Meaning |
|---|---|---|
| `0% to +5%` | Green | Sweet spot — at/just above POC |
| `+5% to +15%` | Orange | Extended above POC |
| `> +15%` | Red | Overextended above |
| `0% to −5%` | Orange | Slightly below POC |
| `< −5%` | Red | Deep below institutional value |

### Row 16 — `── STAGE & SETUP ──` divider

### Row 17 — WEINSTEIN STAGE *(NEW)*
Format: `✓ 2 - Advancing  [s:3]` or `✓ 2 - Advancing  [auto]  [s:3]`

| Stage | Color | Score |
|---|---|---|
| 2 - Advancing | Teal | +3 |
| 1 - Basing | Light Teal | +1 |
| 3 - Topping | Orange | −2 |
| 4 - Declining | Red | −4 |

### Row 18 — SETUP *(NEW — the key actionable row)*

Auto-detects 8 setups, prioritized 5 → 1. Higher priority overrides lower. See Section 4 for full setup specifications.

| Format example | Setup |
|---|---|
| `✓ S2 — Spring/LPS Reversal  (Full Kelly 1.25×)` | Highest conviction — Pri 5 |
| `✓ S3 — Sweep+CHoCH Reversal  (SWG-PB / SWG-BO trigger)` | Pri 4 |
| `✓ S1 — OB Retest + VP Support  (POS-AC / SWG-PB)` | Pri 3 |
| `✗ S7 — Distribution Breakdown  (SHORT / EXIT)` | Pri 3 bearish |
| `✓ S4 — VAL Bounce + Bull FVG Stack` | Pri 2 |
| `✓ S5 — Stage 2 Continuation Above VAH` | Pri 2 |
| `✓ S6 — SOS Momentum Push` | Pri 2 |
| `● S8 — Choppy Range  (no trade)` | Pri 1 |
| `● NONE` | No setup active |

### Row 19 — `── SCORE ──` divider

### Row 20 — CONTEXT SCORE *(thresholds widened)*

```
CONTEXT SCORE = Wyckoff (decayed) + VP + SMC + Weinstein Stage
              = (-4..+4) decayed + (-3..+3) + (-3..+3) + (-4..+3)
              = max ±14
```

| Range | Label | Color |
|---|---|---|
| **≥ 8** | `✓ STRONG BULL (N)` | Bright Spring `#1de9b6` |
| **4 to 7** | `✓ BULL (N)` | Teal |
| **−3 to +3** | `● NEUTRAL (N)` | Gray |
| **−6 to −4** | `✗ CAUTION (N)` | Orange |
| **≤ −7** | `✗ BEAR (N)` | Red |

### Row 21 — BREAKDOWN *(NEW)*
`Wyk:3  VP:3  SMC:3  Stg:3`

Shows exactly what each module contributes. Use this when the score surprises you — you can see which module is driving (or dragging down) the composite.

---

## 4. Setup Detector — Full Specification

The Setup Detector evaluates **8 mechanical setups** every bar. Higher-priority setups override lower ones. If no setup qualifies, panel shows `● NONE`.

### Setup S1 — OB Retest + VP Support (Priority 3)

**Conditions (all must be true):**
- Price **inside** an active Bull Order Block (`_in_bull_ob = true`)
- VP POSITION is `✓ IN VA (upper)` or `✓ ABOVE VAH` **OR** `|DIST TO POC| ≤ 5%`
- WYCKOFF BIAS = `✓ ACCUMULATION`
- CONTEXT SCORE ≥ 4 (BULL)

**External signal alignment:** Pair with Unified Ecosystem `POS-AC` or `SWG-PB` trigger for entry.

**Action:** Standard position size from Risk Allocator.

---

### Setup S2 — Spring/LPS Reversal (Priority 5 — MAX CONVICTION)

**Conditions:**
- LAST WYCKOFF EVENT contains "Spring" or "LPS"
- Event is within last **15 bars**
- SMC TREND = `✓ BULLISH`
- VP POSITION ≥ `✓ IN VA (upper)`
- CONTEXT SCORE ≥ 6

**Action:** **Maximum-conviction entry — use Full Kelly (1.25× standard size).** This is the textbook Weinstein + Wyckoff alignment.

---

### Setup S3 — Sweep + CHoCH Reversal (Priority 4)

**Conditions:**
- LAST LIQ SWEEP = `✓ Sweep ▲`, within last **10 bars**
- LAST SMC EVENT contains `CHoCH ▲`, within last **10 bars**
- VP POSITION ≠ `✗ BELOW VAL` (i.e., `_vp_score > -3`)

**External signal alignment:** Enter via Unified Ecosystem `SWG-PB` or `SWG-BO` trigger.

**Action:** High-probability counter-move. Standard position size, tight stop below the sweep low.

---

### Setup S4 — VAL Bounce + Bull FVG Stack (Priority 2, NEW)

**Conditions:**
- Current bar's low **wicks into VAL** (`low ≤ vp_val × 1.01`)
- Close back above VAL (`close > vp_val`)
- Bull FVG count > Bear FVG count
- WYCKOFF BIAS ≠ `✗ DISTRIBUTION`
- CONTEXT SCORE ≥ 2

**Trading rationale:** VAL is the lower edge of institutional value. A wick into VAL with a bull FVG stack above means buyers absorbed the test and the imbalance favors further upside.

**Action:** Half-size to standard position. Stop below the VAL wick low.

---

### Setup S5 — Stage 2 Continuation Above VAH (Priority 2, NEW)

**Conditions:**
- Weinstein Stage = `2 - Advancing`
- LAST SMC EVENT contains `BOS ▲`, within last **20 bars**
- Close > VAH
- Structure Health: CHoCH count ≤ 1 in last 20 bars

**Trading rationale:** A trending Stage 2 stock with recent bullish break and acceptance above VAH, in a clean structural environment. The textbook trend-continuation setup.

**Action:** Standard position size. Trail stop below recent swing low.

---

### Setup S6 — SOS Momentum Push (Priority 2, NEW)

**Conditions:**
- LAST WYCKOFF EVENT contains `SOS`, within last **10 bars**
- VP POSITION ≥ `✓ IN VA (upper)`
- SMC TREND = `✓ BULLISH`

**Trading rationale:** A recent Sign of Strength with price still in or above VA and bullish structure = institutional buying is being followed through.

**Action:** Standard position size. Stop below the SOS bar low.

---

### Setup S7 — Distribution Breakdown SHORT / EXIT (Priority 3, NEW)

**Conditions:**
- LAST WYCKOFF EVENT contains `SOW`, `LPSY`, or `UT`
- Event is within last **15 bars**
- SMC TREND = `✗ BEARISH`
- Either price inside Bear OB OR VP POSITION ≤ `✗ IN VA (lower)`
- CONTEXT SCORE ≤ −3

**Action:** **EXIT all longs.** Consider short entry via Unified Ecosystem bearish trigger. Stop above the SOW bar high or nearest Bear OB top.

---

### Setup S8 — Choppy Range / No Trade (Priority 1, NEW)

**Conditions:**
- Structure Health: CHoCH count ≥ 3 in last 20 bars
- No higher-priority setup is active

**Action:** **Sit out.** Multiple back-to-back CHoCH events = no coherent trend. Wait for `CLEAN` or `CHOPPY (≤2)` structure before re-engaging.

---

### Priority Resolution

When multiple setups qualify simultaneously:

```
S2 (Pri 5)  >  S3 (Pri 4)  >  S1 (Pri 3)  =  S7 (Pri 3)  >  S4/S5/S6 (Pri 2)  >  S8 (Pri 1)
```

S1 and S7 cannot both fire at once (S1 needs ACCUMULATION, S7 needs distribution events). S8 is a "fallback" — it only fires if nothing else qualifies.

---

## 5. Updated Entry Qualification Checklist

For a **full-size** position, all of these should hold:

```
☑  Dashboard: STAGE 2 (UP) + ALPHA ≥ 60 + REC = BUY or STRONG BUY
☑  Context Panel: CONTEXT SCORE = BULL or STRONG BULL (≥ 4)
☑  STRUCTURE HEALTH: CLEAN or CHOPPY (≤2)              ← NEW gate
☑  WEINSTEIN STAGE: 2 - Advancing (score +3)            ← NEW gate
☑  VP POSITION: ✓ ABOVE VAH or ✓ IN VA (upper)
☑  WYCKOFF BIAS: ✓ ACCUMULATION
☑  SMC TREND: ✓ BULLISH
☑  SETUP row: any S1–S6 active                          ← NEW gate
☑  BULL OB ZONE: ✓ [zone] OR ✓ CLEAR overhead
```

**Position sizing by Setup:**
| Setup | Size multiplier |
|---|---|
| S2 (Spring/LPS Reversal) | 1.25× (Full Kelly) |
| S3 (Sweep + CHoCH) | 1.00× |
| S1, S5, S6 | 1.00× |
| S4 (VAL Bounce) | 0.75× |
| S8 (Choppy) | 0× — skip |
| `● NONE` with score ≥ BULL | 0.75× (no specific setup confirmed) |

---

## 6. Alerts

v1.1 adds 7 `alertcondition()` entries. To enable in TradingView: right-click chart → Add alert → Condition: WCL → pick:

| Alert Title | Fires When |
|---|---|
| Wyckoff SOS | SOS event detected on confirmed bar |
| Wyckoff Spring | Spring event detected |
| Wyckoff SOW | SOW event detected |
| SMC CHoCH ▲ | Bullish CHoCH (reversal up) |
| SMC CHoCH ▼ | Bearish CHoCH (reversal down) |
| Liq Sweep ▲ | Bullish liquidity sweep (stop hunt below recovered) |
| Liq Sweep ▼ | Bearish liquidity sweep (stop hunt above rejected) |

**Note:** Context Score band transitions (e.g., crossing into STRONG BULL) are not yet wired to alerts — planned for v1.2.

---

## 7. Wyckoff Score Decay — How It Works

Each Wyckoff event sets `wyk_score_base` (e.g., SOS = +4, Spring = +3, SOW = −4) and stamps `wyk_last_bar`.

Every bar, the displayed score is computed as:
```
age            = bar_index − wyk_last_bar
decay_steps    = int(age / wyk_decay_bars)         // default wyk_decay_bars = 15
decay_mult     = max(0, 1.0 − decay_steps × 0.25)
wyk_score_comp = round(wyk_score_base × decay_mult)
```

**Decay table (default 15-bar step):**

| Bars since event | Decay mult | SOS (+4) | Spring (+3) | SC (+2) | PS (+1) |
|---|---|---|---|---|---|
| 0–14 | 1.00 | 4 | 3 | 2 | 1 |
| 15–29 | 0.75 | 3 | 2 | 2 | 1 |
| 30–44 | 0.50 | 2 | 2 | 1 | 1 |
| 45–59 | 0.25 | 1 | 1 | 1 | 0 |
| ≥ 60 | 0.00 | 0 | 0 | 0 | 0 |

**To tune decay:**
- Short-term scalping → set `wyk_decay_bars = 5` (full decay in 20 bars)
- Daily swing (default) → `15` (full decay in 60 bars ≈ 3 months)
- Positional → `30` (full decay in 120 bars ≈ 6 months)

The decayed value appears in the `LAST EVENT` row as `[s:N]`.

---

## 8. Updated Common Mistakes

1. **Using old v1.0 score thresholds.** v1.0 said BULL ≥ 3 and STRONG BULL ≥ 6. v1.1 has 4 components (max ±14), so thresholds are BULL ≥ 4 and STRONG BULL ≥ 8. Update any spreadsheets and Risk Allocator presets.

2. **Ignoring Structure Health.** A BULL Context Score with `✗ BROKEN` structure means the score is generated by stale events and broken structure. Always pass the Structure Health gate before entering.

3. **Reading the `LAST EVENT` score `[s:N]` as the full Wyckoff contribution.** Yes it is — that's the whole point. v1.0 contributed the raw base value forever. v1.1 contributes the decayed value. A SOS from 80 bars ago now adds 0, not +4.

4. **Setting `Auto` Stage on intraday timeframes.** The auto-stage logic uses `ta.sma(close, 150)` which on 5-min charts is 150 bars (~12 hours of session time, not 30 weeks). Manual Stage input is more reliable below daily timeframe.

5. **Expecting S2 (Full Kelly) to fire often.** S2 requires 5 conditions to align. Expect 2–5 S2 firings per year per stock. When it fires, take it seriously.

6. **Trying to short on S7 in a Stage 2 stock.** S7 requires SMC TREND = BEARISH AND distribution events. If Weinstein Stage = 2 but S7 still fires, treat it as EXIT signal only, not entry-short. The stage may be transitioning to 3.

7. **(Carried from v1.0) Loading WCL alongside the three separate modules.** Same as v1.0 — WCL replaces WWP, WVP, WSMC. Remove them.

---

## 9. Settings Quick Reference (v1.1 Defaults)

| Group | Parameter | Default | Notes |
|---|---|---|---|
| Master | Enable Setup Detector | `true` | **NEW** |
| Master | Panel Position | Top Left | |
| Master | Panel Text Size | Small | |
| Stage | Current Weinstein Stage | `2 - Advancing` | **NEW** |
| Wyckoff | Pivot Length | 10 | |
| Wyckoff | Volume Avg Lookback | 20 | |
| Wyckoff | High Volume Threshold | 1.5× | |
| Wyckoff | Low Volume Threshold | 0.7× | |
| Wyckoff | Score decay step | 15 | **NEW** |
| VP | Lookback Bars | 100 | |
| VP | Profile Rows | 40 | |
| VP | Value Area % | 70.0 | |
| VP | Histogram Width | 25 bars | |
| VP | Extend Lines Left | Off | |
| SMC | OB Swing Length | 5 | |
| SMC | Max OBs | 5 | |
| SMC | Min FVG Size | 0.05% | |
| SMC | Max FVGs | 10 | |
| SMC | BOS Swing Length | 10 | |
| SMC | Liq Sweep Length | 10 | |

---

## 10. Migration from v1.0 → v1.1

1. **Remove v1.0** from your TradingView indicators panel.
2. **Add v1.1** — `Weinstein_Context_Layers_v1.1.pine`.
3. **Set Weinstein Stage input** to match each chart (or use Auto for daily).
4. **Recalibrate Risk Allocator thresholds**:
   - Old: STRONG BULL ≥ 6, BULL ≥ 3
   - New: STRONG BULL ≥ 8, BULL ≥ 4
5. **Update entry checklist** to include Structure Health and Setup gates (Section 5).
6. **Configure alerts** for SOS, Spring, SOW, CHoCH, and Sweep events (Section 6).
7. **Keep v1.0 file** if you have historical analysis using its score thresholds — both files coexist without conflict.

---

*Last updated: 2026-05-17. v1.1 is the canonical Context Layers reference. v1.0 guide remains for historical analysis using the older score thresholds.*
