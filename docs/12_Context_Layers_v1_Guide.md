# Weinstein Context Layers v1.0 — User & Trading Guide

> **Module Role:** The **institutional context overlay** for the Weinstein Commander ecosystem. Context Layers consolidates three independent analytical frameworks — Wyckoff Phase Detection, Fixed-Range Volume Profile, and Smart Money Concepts (SMC) — into a single overlay indicator with a unified dark-theme panel showing a composite **CONTEXT SCORE**. It does not generate trade signals on its own; it **validates the quality of the environment** in which signals from the Strategy and Dashboard are firing.

---

## 1. Architecture Overview

`Weinstein_Context_Layers_v1.0.pine` is a **single-script combination** of three formerly separate indicators:

| Module | Shorthand | What It Provides | Chart Output |
|---|---|---|---|
| **Wyckoff Phase Detector** | `WYK` | 13 event labels identifying accumulation/distribution narrative | Labels above/below pivots |
| **Fixed-Range Volume Profile** | `VP` | POC, VAH, VAL with histogram showing volume-by-price | Horizontal lines + histogram bars on right edge |
| **Smart Money Concepts** | `SMC` | Order Blocks, Fair Value Gaps, BOS/CHoCH structure breaks, Liquidity Sweeps | Boxes, dashed lines, labels |
| **Context Panel** | `PANEL` | 16-row dark-theme table synthesising all three modules into a CONTEXT SCORE | Floating table (default: Top Left) |

### Key Design Principles

1. **No background colours** — the combined indicator suppresses all `bgcolor()` calls from the original modules. Background colouring is reserved for the **Unified Ecosystem v2.2** indicator that handles stage-phase shading.
2. **Each module is fully toggleable** — individual modules can be disabled via Master Controls without affecting the others.
3. **Panel state is persistent** — Wyckoff bias and last event are stored with `var` variables, so the panel always shows the *most recent* event even if it fired many bars ago.
4. **Liquidity Sweep display resets to `—` after 20 bars** — sweeps older than 20 bars are dropped from the panel to avoid stale information.
5. **VP only recalculates on bar close** — the `barstate.isconfirmed` guard prevents expensive VP recalculation on every real-time tick.

---

## 2. Input Groups — Field-by-Field

### 🎛 Master Controls

| Input | Default | Explanation |
|---|---|---|
| **Enable Wyckoff Module** | `true` | Turns on all Wyckoff event labels and panel rows. Turn off on higher timeframes where Wyckoff signal density is too low. |
| **Enable Volume Profile Module** | `true` | Turns on the VP histogram, POC/VAH/VAL lines, and panel rows. |
| **Enable SMC Zones Module** | `true` | Turns on Order Blocks, FVGs, BOS/CHoCH labels, Liquidity Sweep labels, and panel rows. |
| **Show Context Panel** | `true` | Toggles the floating table on/off without disabling any chart drawings. |
| **Panel Position** | `Top Left` | Moves the panel to any corner. Options: `Top Left`, `Top Right`, `Bottom Left`, `Bottom Right`. |
| **Panel Text Size** | `Small` | Options: `Tiny` (4K/dense charts), `Small` (default), `Normal` (large monitor). |

---

### Wyckoff — Swing Settings

| Input | Default | Explanation |
|---|---|---|
| **Pivot Length** | `10` | The left/right bar lookback for `ta.pivothigh` / `ta.pivotlow`. Larger = fewer but higher-conviction pivots. Match to the timeframe: 10 on daily, 5 on weekly. |
| **Volume Avg Lookback** | `20` | The SMA length used to compute average volume for the high/low volume thresholds. |
| **High Volume Threshold (×avg)** | `1.5` | Volume must exceed `avg × 1.5` to qualify as "high volume" for climax/SOS/SOW detection. |
| **Low Volume Threshold (×avg)** | `0.7` | Volume must be below `avg × 0.7` to qualify as "low volume" for ST/Spring/LPS detection. |

### Wyckoff — Display

| Input | Default | Explanation |
|---|---|---|
| **Show Accumulation Events** | `true` | Toggles all green/teal/purple labels on low-pivot bars (PS, SC, ST, Spring, LPS) and high-pivot bars (SOS, AR). |
| **Show Distribution Events** | `true` | Toggles all red/orange/purple labels (PSY, BC, ARd, UT, SOW, LPSY). |
| **Show Volume Multiplier in Label** | `true` | Appends `(2.3×)` to each label showing how many times above average the volume was. |

### Wyckoff — Colours

| Input | Default | What it colours |
|---|---|---|
| **Accumulation Labels** | Green | PS, ST, LPS, AR (accumulation) |
| **Distribution Labels** | Red | PSY, ARd, LPSY |
| **SOS / Strength** | Teal | Sign of Strength labels |
| **SOW / Weakness** | Orange | Sign of Weakness labels |
| **Climax Events** | Purple | SC (Selling Climax) and BC (Buying Climax) |

---

### Volume Profile — Settings

| Input | Default | Explanation |
|---|---|---|
| **Lookback Bars** | `100` | The fixed window of bars over which the volume profile is calculated. 100 bars covers approximately 4–5 months of daily data or ~1 month of hourly data. |
| **Profile Rows** | `40` | The number of price bins the range is divided into. More rows = finer resolution but noisier histogram. |
| **Value Area %** | `70.0` | The percentage of total volume that defines the Value Area (VA). The algorithm expands the VA symmetrically from the POC until this threshold is met. Standard Wyckoff/TPO setting is 70%. |
| **Histogram Width (bars)** | `25` | The maximum visual width of the histogram, measured in bars. Proportional — the row with the highest volume is drawn at this width; all others scaled relative to it. |

### Volume Profile — Display

| Input | Default | Explanation |
|---|---|---|
| **Show Histogram** | `true` | Toggles the proportional volume-by-price bars on the right edge of the chart. |
| **Show POC Line** | `true` | The horizontal line at the Point of Control (price level with the most volume). |
| **Show Value Area** | `true` | The VAH (Value Area High) and VAL (Value Area Low) dashed lines. |
| **Show Price Labels** | `true` | Text labels "POC 233.28", "VAH 271.75", "VAL 216.35" attached to each line. |
| **Extend POC/VA Lines Left** | `false` | When `false` (default), POC/VAH/VAL extend to the right (always visible). When `true`, they extend in both directions, acting as full-chart historical reference lines. |

### Volume Profile — Colours

| Input | Default | What it colours |
|---|---|---|
| **Histogram** | Blue (65% transparent) | Volume bars outside the Value Area |
| **Value Area** | Teal (55% transparent) | Volume bars inside the VAH–VAL range |
| **POC Line** | Red | Point of Control horizontal line |
| **VAH Line** | Green (20% transparent) | Value Area High line |
| **VAL Line** | Orange (20% transparent) | Value Area Low line |

---

### SMC — Order Blocks

| Input | Default | Explanation |
|---|---|---|
| **Show Order Blocks** | `true` | Toggles OB boxes on/off. |
| **Swing Length for OB** | `5` | The pivot lookback used to detect the BOS that creates an OB. Smaller = more reactive OBs. |
| **Max OBs to Show** | `5` | Oldest OBs are removed when this limit is reached (FIFO). |
| **Keep Mitigated OBs** | `false` | When `false`, OBs are automatically removed when price closes through them. When `true`, they persist permanently (historical reference). |
| **Bullish OB Fill / Border** | Green (80% / 20%) | The last bearish candle before a bullish BOS. |
| **Bearish OB Fill / Border** | Red (80% / 20%) | The last bullish candle before a bearish BOS. |

### SMC — Fair Value Gaps

| Input | Default | Explanation |
|---|---|---|
| **Show FVGs** | `true` | Toggles FVG boxes on/off. |
| **Min Gap Size (% of price)** | `0.05` | Minimum gap size relative to price to register as an FVG. Filters micro-gaps from noise. For large-cap NSE stocks, `0.05%` is a good floor. |
| **Auto-remove Mitigated FVGs** | `true` | Removes FVG box when price closes through it (gap filled). |
| **Max FVGs to Show** | `10` | Oldest FVGs removed when limit reached. |
| **Bullish FVG / Bearish FVG Fill** | Teal / Orange (80%) | 3-bar imbalance: bull FVG = gap up (low[0] > high[2]), bear FVG = gap down (high[0] < low[2]). |

### SMC — BOS / CHoCH

| Input | Default | Explanation |
|---|---|---|
| **Show BOS Labels** | `true` | Break of Structure — a close above the last significant pivot high (BOS ▲) or below the last pivot low (BOS ▼). Trend-confirming move. |
| **Show CHoCH Labels** | `true` | Change of Character — a BOS that goes *against* the current trend direction. The first warning that a trend may be reversing. CHoCH labels are drawn in full-opacity colour vs BOS which are 40% transparent. |
| **Swing Length for BOS** | `10` | Pivot lookback for the structure swing highs/lows that BOS compares against. Larger = only major breaks register. |

### SMC — Liquidity

| Input | Default | Explanation |
|---|---|---|
| **Show Liquidity Sweeps** | `true` | Labels bars where price briefly breaks a prior swing high/low but closes back inside — a classic stop-hunt / liquidity grab. |
| **Swing Length for Sweeps** | `10` | Pivot lookback for the sweep comparison. |
| **Sweep Label Colour** | Purple (30%) | "Liq Sweep ▲" / "Liq Sweep ▼" label colour. |

---

## 3. The Context Panel — Row-by-Row

The panel is a **16-row × 2-column** dark-theme floating table. Left column = field labels (bright white). Right column = values with colour coding and ✓/✗/● prefix marks.

### Panel Colour Key

| Colour | Meaning |
|---|---|
| **Bright Green (#00D26A)** | Bullish condition |
| **Bright Spring (#00FF88)** | Strong bullish (price *inside* bull OB) |
| **Red (#FF4B4B)** | Bearish condition |
| **Orange (#FFA040)** | Caution / neutral-negative |
| **Bright White (#FFFFFF)** | Neutral or absent (no data) |
| **Gray (#8899AA)** | Reserved for CONTEXT SCORE NEUTRAL state only |

### Mark Prefix Logic

Every value field is prefixed with one of three marks:

| Mark | Meaning |
|---|---|
| **✓** | Bullish condition — acts in favour of a long trade |
| **✗** | Bearish condition — acts against a long trade |
| **●** | Neutral / informational — no directional bias |
| **—** | No data, module disabled, or event expired |

---

### Row 0: Header

`◈  CONTEXT LAYERS` — `WCL v1.0`. Fixed header row. No actionable data.

---

### Row 1: ── SMC ZONES ── (section divider)

---

### Row 2: SMC TREND

| Value | Colour | Meaning |
|---|---|---|
| `✓ BULLISH  ▲` | Green | `smc_trend_up = true`: the last BOS was bullish — structure is rising |
| `✗ BEARISH  ▼` | Red | `smc_trend_up = false`: the last BOS was bearish — structure is falling |
| `— MODULE OFF` | White | SMC module disabled |

**Trading read:** Only take long setups when SMC TREND is BULLISH. A BEARISH SMC TREND in an otherwise bullish stock is a warning — the most recent structure break was down.

---

### Row 3: LAST SMC EVENT

Shows the most recent BOS or CHoCH event and how many bars ago it fired.

| Value example | Meaning |
|---|---|
| `✓ CHoCH ▲ (3 bars ago)` | Change of Character — bullish reversal signal, very recent |
| `✓ BOS ▲ (14 bars ago)` | Bullish break of structure — trend continuation |
| `✗ CHoCH ▼ (2 bars ago)` | Bearish CHoCH — warning, trend may be turning down |
| `✗ BOS ▼ (8 bars ago)` | Bearish break of structure — downtrend continuation |

**Trading read:** A CHoCH ▲ within the last 10 bars alongside a bullish Stage 1→2 transition on the Dashboard is a strong setup alignment. The CHoCH adds 1 point to the Context Score when recent.

---

### Row 4: BULL OB ZONE

Shows the nearest active Bullish Order Block (price range of the last bearish candle before a bullish BOS).

| Value example | Colour | Meaning |
|---|---|---|
| `✓ 215.50 – 220.00` | Green | Bull OB exists below current price — support zone |
| `✓ 215.50 – 220.00` | Bright Spring | Price is *inside* the Bull OB — sitting in institutional support |
| `● NONE` | White | No active Bull OB in range — no defined support reference |

**Trading read:** A pullback into the Bull OB zone is one of the highest-probability SMC entry triggers. When price enters a Bull OB and the Panel shows STRONG BULL context, the setup quality is maximum.

---

### Row 5: BEAR OB ZONE

Shows the nearest active Bearish Order Block (last bullish candle before a bearish BOS).

| Value example | Colour | Meaning |
|---|---|---|
| `✗ 280.00 – 285.50` | Red | Bear OB overhead — supply zone that may cap rallies |
| `✗ 280.00 – 285.50` | Bright Red | Price is *inside* the Bear OB — in institutional supply |
| `✓ CLEAR` | Green | No Bear OB overhead — upside is structurally unobstructed |

**Trading read:** A Bear OB directly above a potential entry is a reason to reduce position size or wait for a clean break through it. `✓ CLEAR` is the ideal entry environment.

---

### Row 6: OPEN FVGs

Count of active (unmitigated) bullish and bearish Fair Value Gaps.

| Value example | Colour | Meaning |
|---|---|---|
| `✓ Bull: 7  Bear: 2` | Green | More bullish imbalances than bearish — buying pressure embedded in structure |
| `✗ Bull: 2  Bear: 5` | Red | More bearish imbalances — selling pressure in structure |
| `● Bull: 4  Bear: 4` | White | Equal — no directional FVG bias |

**Trading read:** A heavily bull-FVG-dominant chart (Bull > Bear by 3+) in an uptrend confirms the trend is institutionally driven. Multiple bull FVGs below current price act as a support staircase.

---

### Row 7: LAST LIQ SWEEP

Shows the most recent liquidity sweep event. **Resets to `—` after 20 bars** — older sweeps are considered stale information.

| Value example | Colour | Meaning |
|---|---|---|
| `✓ Sweep ▲ (5 bars ago)` | Green | Liquidity swept *below* a prior low (stop hunt on longs), then closed back above — bullish reversal signal |
| `✗ Sweep ▼ (3 bars ago)` | Red | Liquidity swept *above* a prior high, then closed back below — bearish reversal signal |
| `—` | White | No sweep in last 20 bars |

**Trading read:** A `✓ Sweep ▲` within the last 10 bars is a powerful signal — it means the market cleared weak-hand longs below support and reversed. Combined with a Bull OB nearby, this is a high-conviction long entry setup.

---

### Row 8: ── WYCKOFF ── (section divider)

---

### Row 9: WYCKOFF BIAS

The persistent Wyckoff narrative bias derived from the most recent event sequence.

| Value | Colour | Meaning |
|---|---|---|
| `✓ ACCUMULATION` | Green | The most recent Wyckoff event chain suggests accumulation (SC → AR → ST → Spring → SOS → LPS) |
| `✗ DISTRIBUTION` | Red | The most recent Wyckoff event chain suggests distribution (BC → ARd → UT → SOW → LPSY) |
| `● NEUTRAL` | White | No recent directional Wyckoff signal, or conflicting signals |
| `— MODULE OFF` | White | Wyckoff module disabled |

**Trading read:** ACCUMULATION bias on the daily chart while the Dashboard shows Stage 1 BASE → Stage 2 transition is the textbook Weinstein/Wyckoff long setup. Never enter a long when WYCKOFF BIAS is DISTRIBUTION.

---

### Row 10: LAST EVENT

The most recent Wyckoff event label and how many bars ago it fired. This value is **persistent** — it stays until replaced by a newer event.

| Value example | Meaning / Score contributed |
|---|---|
| `✓ SOS (2.1×) (8 bars ago)` | Sign of Strength — +4 to Context Score. Strongest bullish Wyckoff signal. |
| `✓ Spring (1.8×) (15 bars ago)` | Spring — +3. False breakdown → recovery. Classic Wyckoff long entry. |
| `✓ LPS (0.6×) (3 bars ago)` | Last Point of Support — +3. Pullback on low volume = smart money holding. |
| `✓ SC (3.2×) (22 bars ago)` | Selling Climax — +2. Capitulation bar, initial floor established. |
| `✓ PS (2.0×) (35 bars ago)` | Preliminary Support — +1. First halt to decline. |
| `✓ ST (0.5×) (12 bars ago)` | Secondary Test — +1. Retest of SC low on low volume = holding. |
| `✗ SOW (2.8×) (4 bars ago)` | Sign of Weakness — −4. Strong breakdown = distribution confirmed. |
| `✗ LPSY (0.4×) (7 bars ago)` | Last Point of Supply — −4. Weak rally before markdown. |
| `✗ UT (2.1×) (11 bars ago)` | Upthrust — −3. False breakout above resistance. |
| `✗ BC (3.5×) (25 bars ago)` | Buying Climax — −2. Exhaustion top. |
| `✗ PSY (1.7×) (18 bars ago)` | Preliminary Supply — −1. First resistance failure. |

The volume multiplier `(2.1×)` shows how many times above the 20-bar average volume the event fired at.

**Trading read:** A Spring or LPS within the last 20 bars at a Volume Profile support level (VAL or POC) is one of the most reliable long setups in the entire ecosystem. The `bars ago` counter tells you whether the event is fresh or historical.

---

### Row 11: ── VOL PROFILE ── (section divider)

---

### Row 12: VP POSITION

Where the current price sits relative to the Volume Profile key levels.

| Value | Colour | Score | Meaning |
|---|---|---|---|
| `✓ ABOVE VAH` | Green | +3 | Price accepted above the Value Area — strong bullish momentum |
| `✓ IN VA (upper)` | Light Green | +1 | Inside the VA and above POC — slight bullish tilt |
| `✗ IN VA (lower)` | Orange | −1 | Inside the VA but below POC — slight bearish tilt |
| `✗ BELOW VAL` | Red | −3 | Price rejected below the Value Area — bearish distribution |
| `— MODULE OFF` | White | 0 | VP module disabled |

**Trading read:** Entries with VP POSITION = `✓ ABOVE VAH` have the highest probability of continuation. Entries from `✓ IN VA (upper)` — especially on a pullback to POC — represent lower-risk reentries on a working trend. Never initiate a positional long when the price is `✗ BELOW VAL`.

---

### Row 13: VP LEVELS

Raw reference prices for the three key Volume Profile levels.

`● POC 233.28  │  VAH 271.75  │  VAL 216.35`

These are the same prices shown by the horizontal lines on the chart. Use this row when the chart lines are temporarily off-screen during a zoom.

---

### Row 14: DIST TO POC

The percentage distance between the current close and the Point of Control.

| Value example | Colour | Meaning |
|---|---|---|
| `✓ +32.33%` | Green | Price is 32.33% above POC — extended, but momentum is confirmed |
| `✓ +2.10%` | Green | Price just reclaimed POC from above — ideal pullback entry zone |
| `✗ -5.21%` | Red | Price is 5.21% below POC — under institutional value consensus |

**Trading read:** A DIST TO POC between `+0%` and `+5%` is the highest-quality VP entry zone — price is right at value but has confirmed bullish acceptance. Values above `+15%` suggest the position is extended on a VP basis; wait for a pullback to POC before adding.

---

### Row 15: CONTEXT SCORE

The synthesised composite score across all three modules. This is the key output of the entire indicator.

**Score formula:**
```
CONTEXT SCORE = Wyckoff Component + VP Component + SMC Component + OB Component

Wyckoff Component  : wyk_score_comp  (−4 to +4)    — see Last Event table above
VP Component       : _vp_score       (−3 to +3)    — from VP Position
SMC Component      : trend ±2 + CHoCH±1            (−3 to +3)
OB Component       : inside Bull OB +2 / Bear OB −2 / neutral 0

Maximum: +12    Minimum: −12
```

| Score Range | Label | Colour | Background |
|---|---|---|---|
| **≥ 6** | `● STRONG BULL` | Bright Spring (#00FF88) | Dark green |
| **3 to 5** | `● BULL` | Green (#00D26A) | Dark green |
| **−2 to +2** | `● NEUTRAL` | Gray (#8899AA) | Dark background |
| **−5 to −3** | `● CAUTION` | Orange (#FFA040) | Dark amber |
| **≤ −6** | `● BEAR` | Red (#FF4B4B) | Dark red |

The score in brackets `(6)` shows the exact numeric value for fine-grained comparison between setups.

**Trading read:**
- **STRONG BULL (≥ 6):** All three modules aligned bullish. Highest-conviction environment for long entries. Use full position size from Risk Allocator.
- **BULL (3–5):** Two of three modules bullish. Good environment. Proceed with normal position size.
- **NEUTRAL (−2 to +2):** Mixed signals. Wait for resolution or reduce size by 25–50%.
- **CAUTION (−3 to −5):** Two of three modules bearish. Do not initiate new longs. Tighten stops on existing positions.
- **BEAR (≤ −6):** All three modules aligned bearish. No long entries. Consider exiting existing positions.

---

## 4. The Wyckoff Event Reference

### Accumulation Schematic

```
Market decline →
  PS  (Preliminary Support)     — first halt to the decline; elevated vol, close off lows
  SC  (Selling Climax)          — capitulation: very high vol, wide down-bar, close near low
  AR  (Automatic Rally)         — relief bounce off SC low on decent volume
  ST  (Secondary Test)          — retest of SC area on LOW volume — demand absorbing supply
  Spring                        — false break below SC low, immediate recovery (trap)
  SOS (Sign of Strength)        — strong advance on HIGH vol, wide up-bar, close near high
  LPS (Last Point of Support)   — pullback after SOS on LOW vol — smart money holds
→ Markup begins
```

### Distribution Schematic

```
Market advance →
  PSY  (Preliminary Supply)     — first failure near resistance; high vol, close off high
  BC   (Buying Climax)          — exhaustion top: very high vol, wide up-bar, close near high
  ARd  (Automatic Reaction)     — decline from BC
  UT   (Upthrust)               — false break above BC high, closes near low — trap
  SOW  (Sign of Weakness)       — strong breakdown on HIGH vol, wide down-bar
  LPSY (Last Point of Supply)   — weak rally on LOW vol before markdown begins
→ Markdown begins
```

### Priority Rules (when multiple conditions fire on same bar)

The indicator uses priority ordering to assign a single event when conditions overlap:

| Chain | Priority Order |
|---|---|
| Accumulation | SOS > Spring = LPS > SC > PS = ST |
| Distribution | SOW = LPSY > UT > BC > PSY |

Note: Accumulation and Distribution use separate `if` chains, so an SOS (high pivot) and SC (low pivot) can appear on the same bar if both conditions are met.

---

## 5. Volume Profile Methodology

### How the Profile Is Calculated

1. The indicator takes the last `vp_lookback` bars (default: 100) as the fixed range.
2. The high–low range of this window is divided into `vp_num_rows` bins (default: 40).
3. For each bar in the window, the bar's volume is distributed proportionally across whichever price bins the bar's high–low range overlaps.
4. The bin with the highest accumulated volume is the **POC**.
5. Starting from the POC, bins are added upward and downward alternately (taking the higher-volume side each time) until the accumulated volume reaches `vp_va_pct`% (default: 70%) of total volume. The outer edges of this range are the **VAH** and **VAL**.

### Why VP Recalculates on Bar Close Only

The VP calculation iterates over all 100 bars every time it runs. Running this on every real-time tick would cause heavy CPU load and indicator lag. The `barstate.isconfirmed` guard fires the calculation only once per completed bar, keeping the indicator responsive during live trading.

### POC/VAH/VAL Line Visibility

All three key level lines use `extend.right` by default — they always extend to the right edge of the chart regardless of zoom level. If `Extend POC/VA Lines Left` is enabled, they extend in both directions, which is useful for identifying historical confluences.

---

## 6. SMC Zones Methodology

### Order Block Logic

An OB is identified at the candle that was the last opposing candle *before* a Break of Structure:

- **Bullish OB:** The last **bearish** candle before a bullish BOS. This is where institutional buying began.
- **Bearish OB:** The last **bullish** candle before a bearish BOS. This is where institutional selling began.

OBs are drawn as boxes that extend to the right (`extend.right`) — they remain visible as horizontal zones even as future bars print. When price returns to these zones, they act as high-probability support (Bull OB) or resistance (Bear OB).

### BOS vs CHoCH

| Event | What happened | What it means |
|---|---|---|
| `BOS ▲` | Close above the last swing high | Trend continuation — uptrend confirmed |
| `BOS ▼` | Close below the last swing low | Trend continuation — downtrend confirmed |
| `CHoCH ▲` | Bullish BOS when current trend is *bearish* | Potential trend reversal — first bullish structure break |
| `CHoCH ▼` | Bearish BOS when current trend is *bullish* | First warning of trend breakdown |

CHoCH is drawn in full-opacity colour; BOS is drawn at 40% transparency to visually differentiate importance.

### Fair Value Gap Logic

A 3-bar imbalance where:
- **Bull FVG:** `low[0] > high[2]` — gap up; the bar between them left untraded price (net buyer imbalance).
- **Bear FVG:** `high[0] < low[2]` — gap down; net seller imbalance.

FVGs are natural price magnets — markets tend to revisit and fill them. An active Bull FVG below current price acts as a support target on pullbacks.

---

## 7. Daily Trading Workflow

### Pre-Market — Context Assessment (2 min per stock)

1. Load the stock on the **Dashboard v67.0** — confirm STAGE 2, ALPHA ≥ 60, RS = LEADING.
2. Switch to the **Context Layers panel** (already loaded as overlay).
3. **Check CONTEXT SCORE first** — STRONG BULL or BULL = proceed with analysis. NEUTRAL = be selective. CAUTION/BEAR = skip.
4. **Check VP POSITION** — `✓ ABOVE VAH` or `✓ IN VA (upper)` near POC = structural support present.
5. **Check WYCKOFF BIAS** — ACCUMULATION = confirm. DISTRIBUTION = skip regardless of Dashboard signal.
6. **Check SMC TREND** — `✓ BULLISH` = structure is rising. Any `✗ BEARISH` SMC = reduce conviction.

### Entry Qualification Checklist

Before entering, all of these should be true for a full-size position:

```
☑  Dashboard: STAGE 2 (UP) + ALPHA ≥ 60 + RECOMMENDATION = BUY or STRONG BUY
☑  Context Panel: CONTEXT SCORE = BULL or STRONG BULL (≥ 3)
☑  VP POSITION = ✓ ABOVE VAH or ✓ IN VA (upper) near POC
☑  WYCKOFF BIAS = ✓ ACCUMULATION
☑  SMC TREND = ✓ BULLISH
☑  BULL OB ZONE = ✓ [zone] OR ✓ CLEAR (no Bear OB overhead)
```

Reduce to 50% position size if 1–2 boxes are unchecked. Skip if 3+ are unchecked.

### The Three Highest-Conviction SMC Entry Patterns

**Pattern 1: OB Retest**
- Price pulls back into a `BULL OB ZONE` after a BOS ▲
- Panel shows `✓ IN VA (upper)` or `✓ ABOVE VAH` for VP context
- WYCKOFF BIAS = ACCUMULATION
- Entry: on close back above the Bull OB mid-price with volume surge

**Pattern 2: Liquidity Sweep Reversal**
- `✓ Sweep ▲` fired within the last 5–10 bars
- Price swept a prior low, flushed longs, then recovered
- CHoCH ▲ fired on the same bar or within 3 bars
- Entry: on the next bar above the sweep candle's high

**Pattern 3: FVG Fill and Bounce**
- Price pulls back into an active `Bull FVG` (visible on chart as teal box)
- FVG is located above the `VAL` (VP support)
- `OPEN FVGs` shows Bull > Bear (bullish imbalance dominant)
- Entry: on close back above the FVG midpoint

### During Market — What to Watch

| Event | Action |
|---|---|
| `LAST SMC EVENT` changes to `CHoCH ▼` | Immediate alert — raise stop to near entry. The structure may be reversing. |
| `SMC TREND` flips to `✗ BEARISH` | Consider exiting or tightening stop by 50% |
| `DIST TO POC` drops below `✗ −5%` | Stock trading below institutional value — reassess position |
| `WYCKOFF BIAS` updates to DISTRIBUTION | Treat as a warning sign — verify Dashboard stop-loss distance |
| `CONTEXT SCORE` drops from BULL to NEUTRAL | Begin partial exit protocol — sell half, trail stop |
| `LAST LIQ SWEEP` shows `✗ Sweep ▼` (bar 1–3) | Stop-hunt on your longs just occurred — do NOT panic exit unless SL is hit |

---

## 8. Timeframe Guide

| Timeframe | Recommended Settings | Use Case |
|---|---|---|
| **Weekly** | Pivot Length: 5, VP Lookback: 52, Wyckoff Off | Macro Wyckoff phase context — is this a Stage 1/2 stock? |
| **Daily** | Pivot Length: 10, VP Lookback: 100 (default) | Primary trading timeframe — all signals active |
| **Hourly** | Pivot Length: 7, VP Lookback: 200 | Intraday swing entry timing using Context Score |
| **15-min** | Pivot Length: 5, VP Lookback: 300, Wyckoff Off | SMC-only mode for precise OB/FVG entry |

**Recommendation:** Keep the indicator on the **daily chart** as your primary reading. For entry timing, load a 1-hour chart with the same indicator and reduce the Pivot Length to 5. A STRONG BULL score on both timeframes is the maximum-conviction entry.

---

## 9. Context Score in Different Market Regimes

| Macro Regime (Dashboard MACRO row) | How to adjust Context Score thresholds |
|---|---|
| **BULL** | Use standard thresholds: STRONG BULL ≥ 6, BULL ≥ 3 |
| **RECOVERY** | Raise the BULL threshold to ≥ 4 — be more selective in uncertain conditions |
| **BEAR** | Only trade longs with STRONG BULL ≥ 7 AND Wyckoff Spring/SOS within last 15 bars |

---

## 10. Common Mistakes

1. **Loading WCL alongside the three original modules (WWP, WVP, WSMC)** — Context Layers *replaces* all three. Running both simultaneously doubles every label, line, and box on the chart, creating a cluttered, unreadable display. Remove the three originals when loading WCL.

2. **Acting on Wyckoff events in isolation without VP context** — A Spring that fires below the VAL is a weak Spring. A Spring that fires at the VAL (institutional value) is high-conviction. Always cross-check the Wyckoff event with VP POSITION.

3. **Ignoring SMC TREND when it conflicts with Dashboard STAGE** — A stock in Dashboard Stage 2 (bullish) with SMC TREND = BEARISH means the shorter-timeframe structure is cracking. Do not add to the position. Wait for SMC TREND to confirm bullish.

4. **Misreading LAST LIQ SWEEP ▼ as a sell signal** — A Liq Sweep ▼ means the market hunted stops *above* a prior high and reversed down. If you're already long, this is a warning. But in a strong Stage 2 trend, a `✗ Sweep ▼` often resets and is followed by a higher high. Context matters — check WYCKOFF BIAS and VP POSITION before reacting.

5. **Over-relying on CONTEXT SCORE without checking staleness** — The LAST EVENT (Wyckoff) and LAST LIQ SWEEP persist. A SOS event from 60 bars ago still contributes +4 to the score. Check the `bars ago` value — events older than 30 bars have reduced forward relevance.

6. **Using VP Lookback of 100 on weekly charts** — On weekly timeframes, 100 bars = nearly 2 years. The profile will be too diffuse to identify meaningful current support/resistance. Use 52 bars (1 year) on weekly charts.

7. **Interpreting ● NONE (Bull OB) as bearish** — No active Bull OB simply means the indicator hasn't identified a recent demand zone. It's neutral, not bearish. The chart may still have context from other sources (VAL, prior swing lows).

---

## 11. Ecosystem Integration

| Module | How Context Layers Works With It |
|---|---|
| **Dashboard v67.0** | Dashboard provides the Stage + Alpha Score + Recommendation. Context Layers provides the three-module environmental validation. Check Context Score ≥ BULL before acting on any Dashboard BUY signal. |
| **Unified Ecosystem v2.2** | The ecosystem generates all 9 edge signals (SWG-PB, SWG-BO, POS-BO, REV-CB, REV-EARLY, etc.). A POS-BO firing into a Bull OB zone (OB Retest pattern) or at the POC raises conviction materially. A Spring firing alongside REV-CB is a maximum-conviction recovery entry. |
| **Risk Allocator v1.0** | Use the Context Score to modulate position size: STRONG BULL = full Kelly size; BULL = 75%; NEUTRAL = 50%; CAUTION = skip. |
| **Beta Screener v2.6 / Capitulation Screener v1.5** | Screeners find candidates. Context Layers validates them. After the screener surfaces a ticker, load it with Context Layers to confirm VP POSITION and SMC TREND before committing capital. |
| **Swing Zigzag Strict v6.0** | Zigzag defines the HH/HL structural state (weekly). SMC BOS/CHoCH in Context Layers defines the shorter-timeframe structure state (daily). A bullish Zigzag trend + bullish SMC TREND on the daily = double-confirmation of trending environment. |

---

## 12. Settings — Quick Reference (Default Values)

| Group | Parameter | Default |
|---|---|---|
| Master | Panel Position | Top Left |
| Master | Panel Text Size | Small |
| Wyckoff | Pivot Length | 10 |
| Wyckoff | Volume Avg Lookback | 20 |
| Wyckoff | High Volume Threshold | 1.5× |
| Wyckoff | Low Volume Threshold | 0.7× |
| VP | Lookback Bars | 100 |
| VP | Profile Rows | 40 |
| VP | Value Area % | 70.0 |
| VP | Histogram Width | 25 bars |
| VP | Extend Lines Left | Off |
| SMC | OB Swing Length | 5 |
| SMC | Max OBs | 5 |
| SMC | Min FVG Size | 0.05% |
| SMC | Max FVGs | 10 |
| SMC | BOS Swing Length | 10 |
| SMC | Liq Sweep Length | 10 |
| SMC | Keep Mitigated OBs | Off |
| SMC | Auto-remove Mitigated FVGs | On |
