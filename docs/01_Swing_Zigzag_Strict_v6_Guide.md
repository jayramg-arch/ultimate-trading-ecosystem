# Weinstein Swing Zigzag [Strict v6.2] — User & Trading Guide

> **Module Role in Ecosystem:** The structural backbone of the entire Weinstein Commander suite. Every other module — the Dashboard, the Minervini Strategy, the Recovery Strategy, and both Screeners — derives its "Strict Trend" determination from the same HH/HL/LH/LL pivot logic implemented here. Think of this indicator as the **market structure engine**: it defines whether a stock is in an uptrend, downtrend, or neutral state using only verified price pivots — no lagging averages.

> **File:** `Wesinstein Swing Zigzag [Strict v6.2].pine` (Pine Script v6, repo root)

> **Supersedes:** v6.0 / v6.1. This guide is the canonical reference for v6.2.

---

## 0. What Changed Since v6.0

### Core fixes (v6.1 → v6.2)

- **v6.2** — Section 3 (developing BoS) now **gates by `activePivotType`** so the high-side and low-side are not both evaluated when only one side is structurally relevant. Fixes false HH/LL flips on extending pivots (NEULANDLAB, GRSE, RRKABEL cases).
- **v6.2** — `syncBars` now includes the pivot bar itself (`bar_index − activePivotIndex + 1`). Previously the +1 was missing, missing the pivot bar's own extreme.
- **v6.2** — Developing opposite-side classification reuses the confirmed `lastHighClass` / `lastLowClass` instead of re-classifying. Eliminates micro-drift from `projSync*` rounding.
- **v6.1** — Structure panel reflects **developing** pivot structure, not just confirmed.

### Trader-facing additions (this guide's focus)

| Area | What's new |
|---|---|
| **Classification** | **EH** (Equal High) and **EL** (Equal Low) classes added — pivots within a configurable % of the prior pivot are flagged as Equal, preventing false trend confirmation |
| **Major / Minor** | Auto-detected pivot magnitude classes (Stock ≥ 8%, ETF ≥ 4%, or custom). Major pivots render with thicker lines and larger labels |
| **MTF pivot lengths** | Separate Pivot Length inputs for Monthly / Weekly / Daily / Intraday — auto-resolves per chart timeframe |
| **Developing pivot awareness** | Trend, Structure, Swing Count, Swing Range, and Choppiness fields **all** reflect the developing pivot when a BoS or CHoCH is projected — not just the last confirmed pivot |
| **Longs-Only Mode** | Default ON. Invalidation tracks latest swing low, BoS Level tracks latest swing high, Vol Confirm captures bullish BoS only |
| **Volume Confirmation** | Most recent BoS bar's volume vs 50-SMA, ✅/❌ flagged against a tunable multiplier (default 1.5×) — Weinstein's volume-confirmation rule made visible |
| **MTF Trend Confluence** | Higher-timeframe trend state surfaced on the panel — auto-resolves (intraday→D, D→W, W→M, M→12M) or manual override |
| **Fibonacci levels** | 50% / 61.8% retracements (pullback support) and 1.272 / 1.618 extensions (long profit targets) — auto-dimmed in confirmed downtrends with no break above lockedHigh |
| **Panel rows** | 19 rows completely un-clubbed into a colour-coded heat-map: TIMEFRAME, TREND, EMA20 DIST, MTF, MTF2, ALIGNMENT, STRUCTURE, I:C RATIO, SWING COUNT, SWING RANGE, CHOPPINESS, INVALIDATION, BOS LEVEL, BOS VOL THRUST, VOL CONFIRM, BAR AGE, VELOCITY, REGIME, ATR % |
| **Sideways colour** | Sideways trend is now **amber** (🟡 `#FFBF00`), not white — matches Structure colour |
| **Heat-map Design** | All panel rows dynamically shade their cell backgrounds Green, Red, Amber, or Gray depending on the health of the metric based on Weinstein/Minervini rules. Emojis replaced with clean white text arrows (↑, ↓, →) for maximum readability |

---

## 1. What It Does

The Zigzag draws a connected line between **confirmed swing highs** and **swing lows**, then classifies each new pivot relative to the prior pivot of the same type. The result is a clean, objective structural map.

### Six pivot classes (v6.2 adds EH / EL)

| Class | Meaning | Trend impact |
|---|---|---|
| **HH** Higher High | New swing high > previous swing high | Bullish — confirms uptrend (with HL) |
| **HL** Higher Low | New swing low > previous swing low | Bullish — confirms uptrend (with HH) |
| **LH** Lower High | New swing high < previous swing high | Bearish — confirms downtrend (with LL) |
| **LL** Lower Low | New swing low < previous swing low | Bearish — confirms downtrend (with LH) |
| **EH** Equal High *(new)* | New swing high within `eq_pct%` of prior swing high | **Sideways** — uptrend NOT confirmed |
| **EL** Equal Low *(new)* | New swing low within `eq_pct%` of prior swing low | **Sideways** — downtrend NOT confirmed |

### Trend states

| Trend State | Condition | Colour |
|---|---|---|
| **🟢 Uptrend (+1)** | HH after HL **or** HL after HH | Green |
| **🔴 Downtrend (−1)** | LH after LL **or** LL after LH | Red |
| **🟡 Sideways (0)** | EH, EL, broadening (HH after LL or LL after HH), or mixed | **Amber** (`#FFBF00`) |

---

## 2. Inputs — Field-by-Field

### Group: MTF Pivot Settings (Left/Right)

The script auto-resolves which Pivot Length input to use based on the current chart timeframe.

| Input | Default | Explanation |
|---|---|---|
| **Monthly Pivot Length** | `1` | Applied when chart is on Monthly resolution |
| **Weekly Pivot Length** | `5` | Applied when chart is on Weekly resolution |
| **Daily Pivot Length** | `2` | Applied when chart is on Daily resolution |
| **Intraday Pivot Length** | `2` | Applied on all intraday timeframes (e.g., 75m, 125m) |

The same value is used for both Left and Right (symmetric pivot detection).

### Group: Display Settings

| Input | Default | Explanation |
|---|---|---|
| **Show Trend State Panel** | `true` | Toggles the 11-row info table |
| **Show Projection Line** | `true` | Dashed line from active pivot to live price extreme — visualises the developing swing |
| **Show Pivot Labels (HH/HL/LH/LL/EH/EL)** | `true` | Text labels at each confirmed pivot |
| **Show Pivot % Change** | `true` | Adds `(±X.X%)` under each label — magnitude from prior pivot |
| **Panel Position** | Top Right | Top/bottom × left/right |
| **Choppiness Lookback (weeks)** | `52` | Rolling window for the CHOPPINESS field. Converts to bars automatically per timeframe |
| **Show Invalidation & BoS Level Lines** | `true` | Dotted horizontal lines at the structural stop and entry trigger |
| **Longs-Only Mode** | `true` | ON: Invalidation = swing low, BoS Level = swing high, Vol Confirm captures ↑ only. OFF: legacy behaviour (active pivot as invalidation, both BoS directions captured) |
| **Volume Confirmation Multiplier** | `1.5` | A BoS bar is ✅ when volume ≥ this × 50-bar volume SMA. Weinstein's volume-confirmation threshold |
| **MTF Trend Timeframe** | `Auto` | Higher-TF resolution for the MTF row. Auto: intraday→D, D→W, W→M, M→12M. Override: D / W / M / 3M / 12M |

### Group: Fibonacci Levels

| Input | Default | Explanation |
|---|---|---|
| **Show 50% & 61.8% Retracement** | `true` | Pullback support levels (purple / orange) |
| **Show 1.272 & 1.618 Extensions (Long Targets)** | `true` | Upward profit objectives (teal / lime) |
| **Extend Lines (bars right)** | `20` | How far past current bar the fib + invalidation + BoS lines extend |

### Group: Major / Minor Pivot

| Input | Default | Explanation |
|---|---|---|
| **Major Pivot Mode** | `Auto` | Auto detects ETFs via `syminfo.type == "fund"`. Override: Stock (≥8%) / ETF (≥4%) / Custom |
| **Custom Threshold (%)** | `8.0` | Magnitude % above which a pivot is "Major" (thick line, normal label size) |

### Group: Equal High / Equal Low (EH/EL)

| Input | Default | Explanation |
|---|---|---|
| **Equal Pivot Threshold (%)** | `0.5` | Two consecutive same-side pivots within this % are flagged EH / EL. Increase for wider instruments; decrease for precision |

---

## 3. Detection Logic Deep-Dive

### 3.1 Pivot Identification

Uses Pine's `ta.pivothigh()` / `ta.pivotlow()` with the timeframe-resolved length. Confirmed pivots update persistent state:

- `lockedHigh` / `lockedLow` — most recent **confirmed** pivot of each type
- `prevLockedHigh` / `prevLockedLow` — saved just before lock-overwrite, used as structural reference when an active pivot extends
- `activePivotPrice` / `activePivotType` / `activePivotIndex` — the latest extreme of the current direction (may equal lockedHigh/Low at confirmation, then drifts if the pivot extends)
- `lastHighClass` / `lastLowClass` — the classification of the most recent confirmed pivot on each side

### 3.2 The `f_updateTrend` State Machine

Called on every confirmed direction change. Returns `[newTrend, newSwing]` for the panel:

| New Pivot | Prior Opposite Class | Trend | Swing Count |
|---|---|---|---|
| HH | HL | 🟢 +1 | continuation (+1) |
| HL | HH | 🟢 +1 | continuation (+1) |
| LH | LL | 🔴 −1 | continuation (+1) |
| LL | LH | 🔴 −1 | continuation (+1) |
| EH / EL | any | 🟡 0 | continuation (+1) of sideways |
| HH after LL | (broadening) | 🟡 0 | continuation (+1) of sideways |
| LL after HH | (broadening) | 🟡 0 | continuation (+1) of sideways |

**Sideways counting rule (v6.2):** consecutive sideways pivots count too — the count only resets to 1 when the **trend state itself** changes. Previously sideways pivots zeroed the count.

### 3.3 Developing Pivot Treatment (Section 3)

Section 3 detects when the developing leg has structurally exceeded the locked opposite pivot, classifying what the next confirmed pivot *would* be:

- **Active = L, projSyncHigh > lockedHigh** → developing HH. If confirmed `lastLowClass == "HL"` → bullish BoS / CHoCH → `bosUp := true`, trendState := +1
- **Active = H, projSyncLow < lockedLow** → developing LL. If confirmed `lastHighClass == "LH"` → bearish BoS / CHoCH → `bosDn := true`, trendState := −1
- Other developing combinations (broadening, mixed) → trendState := 0

The panel reads developing values where they exist, otherwise falls back to confirmed. This means **Trend, Structure, Swing Count, Swing Range, and Choppiness all reflect the live, in-progress structure** — not just the last locked pivot.

### 3.4 Major / Minor Pivot Detection

A pivot is **Major** when its magnitude from the opposite locked level exceeds `majorThresh`:

```
isMajor = |pivotPrice − oppositePivot| / oppositePivot × 100 ≥ majorThresh
```

`majorThresh` resolves to: 8.0 for Stocks, 4.0 for ETFs (auto by `syminfo.type`), or the custom value. Major pivots render with `width=3` and `size.normal`; minor with `width=1` and `size.small`.

---

## 4. The Information Panel — Row by Row (19 rows)

The panel was fully expanded and redesigned into a 19-row "heat-map" to allow instant visual assessment of setup quality. All fields use white text on dynamically coloured backgrounds (Green/Red/Amber/Gray).

### Row 0 — TIMEFRAME
Displays the current chart resolution (e.g., "75", "D", "W").
- **Background:** Static Dark Blue.
- **Interpretation:** A quick visual check to ensure you are analyzing the intended primary timeframe.

### Row 1 — TREND
Displays the current directional Trend State (`UPTREND ↑`, `DOWNTREND ↓`, or `SIDEWAYS →`) based on the most recent confirmed high/low pair.
- **Green:** Confirmed Uptrend (+1)
- **Red:** Confirmed Downtrend (-1)
- **Amber:** Sideways / Broadening (0)
- **Interpretation:** The foundational directional bias. Always trade with the primary trend (Green for longs).

### Row 2 — EMA20 DIST
Measures the distance of the current price from the 20-period Exponential Moving Average, normalized into Average True Range (ATR) units. This field anchors to the Daily EMA on intraday charts (if enabled).
- **Green:** ≤ 1.5 ATR. Ideal, healthy pullback distance indicating low-risk entry potential near the mean.
- **Gray:** 1.5 – 3.0 ATR. Normal trend extension.
- **Amber:** 3.0 – 5.0 ATR. Warning—price is getting stretched. Entering here carries elevated mean-reversion risk.
- **Red:** > 5.0 ATR. Climax territory. Severe overextension; highly prone to snapback corrections.

### Row 3 & Row 4 — MTF (TF1) / MTF (TF2)
Displays the Trend State of the two higher timeframes (e.g., Daily and Weekly).
- **Green/Red/Amber:** Same color mapping as Row 1 (Trend).
- **Interpretation:** Used for multiple timeframe confluence checking. If your current trend is Uptrend but MTF is Downtrend, you are trading a counter-trend bounce.

### Row 5 — ALIGNMENT
Evaluates the combined trend state across all three monitored timeframes (Current, MTF 1, and MTF 2).
- **Green (ALIGNED ↑):** All three timeframes are in a confirmed Uptrend.
- **Red (ALIGNED ↓):** All three timeframes are in a confirmed Downtrend.
- **Dark Red (CONFLICT):** Direct directional fight (e.g., Daily is Uptrend, but Weekly is Downtrend). Highly dangerous chop environment.
- **Amber (MIXED):** No direct conflict, but imperfect alignment (e.g., Daily Uptrend, Weekly Sideways). Indicates consolidation or a maturing trend.

### Row 6 — STRUCTURE
Displays the specific pivot pair governing the current trend (e.g., `HH / HL`, `LH / LL`, `EH / EL`).
- **Text Color:** Matches the trend state (Green for Uptrend, Red for Downtrend, Amber for Sideways).
- **Interpretation:** Provides the structural "why" behind the trend state.

### Row 7 — MOMENTUM EXP.
Measures the momentum thrust of the current developing leg relative to the previous completed leg of the SAME direction. (e.g., Current Pullback vs Previous Pullback).
- **Impulse (With-Trend) Leg:**
  - **Green:** ≥ 1.0x. Momentum is expanding/healthy (current rally is bigger than the last).
  - **Red:** < 1.0x. Momentum is shrinking (failure to expand).
- **Correction (Counter-Trend) Leg:**
  - **Green:** < 1.0x. Pullback is shallower than the previous pullback (bullish sign).
  - **Amber:** 1.0x – 1.5x. Deep pullback.
  - **Red:** ≥ 1.5x. Dangerous momentum expansion against the trend; bears/bulls are hitting back much harder than last time.

### Row 8 — SWING COUNT
Tracks how many consecutive pivots have occurred in the current trend state without breaking structure.
- **Green:** 1 or 2 swings. Fresh, young trend with high probability of continuation.
- **Amber:** 3 swings. Maturing trend.
- **Red:** > 3 swings. Late stage / Exhaustion risk. Trend is highly mature and prone to reversal.

### Row 9 — SWING RANGE
Measures the percentage (%) distance of the current developing swing leg. The background color alerts you if a swing is getting dangerously over-extended by comparing it to a dynamic `majorThreshold`.
*   **The Math:** By default (Auto mode), `majorThreshold` is **8.0%** for standard stocks and **4.0%** for ETFs. 
*   **Gray:** `< 1x Threshold` (e.g., `<8%`). Minor swing, hasn't covered enough ground to be considered a major structural move.
*   **Green:** `1x to 2x Threshold` (e.g., `8% - 16%`). Healthy, well-developed major swing.
*   **Amber:** `> 2x Threshold` (e.g., `>16%`). Extended/Loose swing. If a single leg travels this far without a pullback, entering carries a highly elevated risk of an impending mean-reversion snapback.

### Row 10 — CHOPPINESS
Calculates the number of bars per structural flip (direction change) over the lookback window. Indicates if the asset respects trends or thrashes around.
- **Green:** Clean / Trending. Price moves smoothly between pivots (requires ≥ 20 bars/flip for standard stocks).
- **Amber:** Moderate choppiness.
- **Red:** Choppy. Price whipsaws frequently (requires < 10 bars/flip for standard stocks). Avoid trading these assets.

### Row 11 — INVALIDATION
Displays the exact price level of the structural stop (e.g., the Swing Low for longs), alongside its pivot type label (e.g., `HL`).
- **Text Color:** Matches Trend State.
- **Interpretation:** If price crosses this line, the current trend structure is formally broken/invalidated. (This forms the denominator in your Risk:Reward math: `Risk = Entry - Invalidation`).

### Row 12 — BOS LEVEL
Displays the exact price of the entry trigger / Break of Structure level (e.g., the previous Swing High to break for an uptrend).
- **Text Color:** Matches Trend State.
- **Interpretation:** The price that must be breached to confirm trend continuation. (If you enter here, this is your Entry Price in your Risk:Reward math).

### Row 13 — BOS VOL THRUST
Measures the quality of the volume leading into and during the most recent Break of Structure. Format: `[Pass/Fail] [Lead-in Direction]`.
- **Icon (`✅` or `❌`):** Did the breakout bar itself pass the volume multiplier threshold?
- **Arrow (`↑` or `↓` or `→`):** Did volume build up (expand) into the breakout (`↑`), dry up (`↓`), or stay flat (`→`)?
- **Green Background:** `✅ ↑` (Passed threshold AND had expanding lead-in volume). A Grade-A breakout.
- **Amber Background:** Failed the volume test OR had shrinking lead-in volume.

### Row 14 — VOL CONFIRM
Displays the exact volume multiplier on the most recent Break of Structure bar compared to the 50-SMA volume.
- **Green Background:** `✅` (Volume exceeded the required multiplier, e.g., > 1.5x).
- **Red Background:** `❌` (Volume failed the required multiplier).

### Row 15 — BAR AGE
Tracks the number of bars elapsed since the active pivot was formed.
- **Green:** ≤ 5 bars. Fresh, immediate breakout or structural move.
- **Amber:** 6 to 15 bars. Maturing move; momentum may be slowing.
- **Gray:** > 15 bars. Stale, consolidating, or aging move.

### Row 16 — VELOCITY
Measures the speed of the current developing leg as a percentage moved per bar (`%/bar`), compared to the previous leg.
- **Green (`↑`):** Accelerating. The current leg is moving at least 10% faster per bar than the previous leg.
- **Amber (`↓`):** Decelerating. The current leg is moving at least 10% slower per bar than the previous leg.
- **Gray (`→`):** Steady. Speed is roughly unchanged.

### Row 17 — REGIME
Dynamically categorizes the volatility personality of the asset based on its Average True Range (ATR), and displays the adaptively adjusted Choppiness thresholds (e.g., `15/8 b/flip`).
- **HIGH-VOL (Amber):** ATR > standard threshold (e.g., >3.0% Daily). Fast-moving, wild stock. Lowers choppiness requirements.
- **STD (Green):** Standard volatility stock. Normal choppiness requirements (20/10).
- **ETF (Aqua):** Detected index fund (low volatility). Raises choppiness strictness.
- **Interpretation:** Ensures the script judges clean trends differently for wild biotech stocks versus stable index funds.

### Row 18 — ATR %
Displays the asset's current 14-period Average True Range as a percentage, followed by the absolute monetary value in parentheses (e.g., `5.9% (114.05)`).
*   **The Math:** `(Absolute ATR / Current Price) * 100`. E.g. A stock moving $114 per week on a $1933 price has a 5.9% Weekly ATR.
*   **Background Colors (Dynamic by Timeframe):** The script sets a `volCut` threshold that changes based on your chart resolution (Daily = 3.0%, Weekly = 8.0%, Monthly = 15.0%). 
    *   **Green:** `≤ volCut` threshold. Normal, stable volatility for that specific timeframe (e.g. 5.9% is Green on a Weekly chart because it is under 8.0%).
    *   **Amber:** `1.0x – 1.5x volCut`. Elevated volatility.
    *   **Red:** `> 1.5x volCut`. Extreme volatility / wide swings.

---

## 5. On-Chart Drawings

### Pivot lines

Connected line between confirmed pivots. Colour by trend pair:
- **Green** — confirmed uptrend pair (HH+HL or HL+HH)
- **Red** — confirmed downtrend pair (LH+LL or LL+LH)
- **Orange** — EH / EL (equal pivot)
- **White (30% transparent)** — broadening / mixed
- Major pivots: width 3 + `size.normal` label. Minor: width 1 + `size.small`.

### Projection line

Dashed line from active pivot to the developing extreme. Colour matches trend. Toggle: `Show Projection Line`.

### Invalidation + BoS Level lines (Longs-Only)

- **Red dotted** at latest swing low — your structural stop
- **Green dotted** at latest swing high (lockedHigh) — your bullish BoS trigger

Both extend right by `fib_ext` bars. Toggle: `Show Invalidation & BoS Level Lines`.

### Fibonacci levels (on `barstate.islast`)

| Level | Formula | Colour | Use |
|---|---|---|---|
| 50% retr | `lockedHigh − 0.500 × range` | Purple | Pullback support |
| 61.8% retr | `lockedHigh − 0.618 × range` | Orange | Deeper pullback support |
| 1.272 ext | `lockedLow + 1.272 × range` | Teal | Long target T1 |
| 1.618 ext | `lockedLow + 1.618 × range` | Lime | Long target T2 (golden ratio) |

**Style:** solid when actionable (uptrend / sideways / developing HH BoS). Dotted + dimmed when confirmed downtrend with no break above lockedHigh (reference only).

---

## 6. Practical Trading Workflow (Longs-Only)

### Step 1 — Read the top of the panel for regime

- **TIMEFRAME** — confirm you're on your intended analysis TF
- **TREND** — current TF state (developing-aware)
- **MTF** — confluence check. Both green = align. Conflict = caution

### Step 2 — Read structural detail

- **STRUCTURE** — what's the high/low pair right now?
- **SWING COUNT** — how mature is this run?
- **SWING RANGE** — has the move covered a meaningful magnitude yet?

### Step 3 — Read regime quality

- **CHOPPINESS** — is this instrument trustworthy or thrashy?
- **BAR AGE** — is the current swing fresh or aged?

### Step 4 — Pull the trade levels

- **BOS LEVEL** — your entry trigger price (the swing high to break)
- **INVALIDATION** — your stop (the swing low to defend)
- **R:R math** = (1.272 ext − BoS) / (BoS − Invalidation) for T1, or use 1.618 for T2

### Step 5 — Vol Confirm gate

- **VOL CONFIRM** — was the most recent ↑ BoS on Weinstein-grade volume (✅ ≥ 1.5×)?
- If ❌ or N/A → either wait for a fresh ↑ BoS with ✅, or take reduced size

### Step 6 — Cross-reference with Dashboard

The Weinstein Dashboard's "Strict Trend" field reads directly from this logic. Decisions remain consistent across tools.

---

## 7. Configuration Recommendations

### Positional / Weinstein-style (NSE Mid-Cap, Daily)

| Setting | Value |
|---|---|
| Daily Pivot Length | `2` or `3` |
| Major Pivot Mode | `Auto` |
| Equal Pivot Threshold | `0.5%` |
| Longs-Only Mode | `ON` |
| Volume Confirmation Multiplier | `1.5×` |
| MTF Trend Timeframe | `Auto` (→ Weekly) |
| Choppiness Lookback | `52` weeks |

### Swing (NSE Large/Mid, 125m or 75m)

| Setting | Value |
|---|---|
| Intraday Pivot Length | `2` |
| Major Pivot Mode | `Auto` |
| Equal Pivot Threshold | `0.5%` |
| Longs-Only Mode | `ON` |
| MTF Trend Timeframe | `Auto` (→ Daily) |
| Choppiness Lookback | `26` weeks |

### ETF Trading

| Setting | Value |
|---|---|
| Major Pivot Mode | `Auto` (auto-detects fund) — uses 4% threshold |
| Equal Pivot Threshold | `0.3%` (tighter — ETFs are less volatile) |

---

## 8. Alerts

| Alert | Condition | Message Token |
|---|---|---|
| Bullish BoS | `bosUp` fires | `Bullish Break of Structure on {{ticker}}! Price broke above locked high.` |
| Bearish BoS | `bosDn` fires | `Bearish Breakdown on {{ticker}}! Price broke below locked low.` |
| Uptrend Confirmed | `trendState == 1 and trendState[1] != 1` | `UPTREND confirmed on {{ticker}} (HH+HL).` |
| Downtrend Confirmed | `trendState == −1 and trendState[1] != −1` | `DOWNTREND confirmed on {{ticker}} (LH+LL).` |

---

## 9. Common Mistakes to Avoid

1. **Chasing a pivot label** — labels appear `rightBars` bars late. The pivot already happened; you're seeing confirmation. Use the **developing pivot fields** on the panel to read live structure instead of waiting for the label.
2. **Trading sideways trend** — amber (🟡) means no structural consensus. Wait for resolution or trade the range edges with extra caution.
3. **Ignoring MTF row** — if current TF is UPTREND but MTF is DOWNTREND, you're in a counter-trend bounce. Reduce size or skip.
4. **Acting on stale VOL CONFIRM** — the field is sticky from the last BoS. If many bars have passed since the trigger, treat it as historical context, not a fresh signal.
5. **Entering longs on negative BoS direction** — in Longs-Only Mode, the ↓ arrow shouldn't appear at all (capture is gated to bullish BoS only). If you see ↓, your toggle is OFF — turn it back ON.
6. **Mismatching pivot lengths** across modules — if this indicator uses Daily `2` but the strategy uses `3`, the "Strict Trend" labels will differ between tools, causing confusion.
7. **Stretching majorThresh for ETFs** — Auto already handles `syminfo.type == "fund"`. Don't manually override to Stock (8%) for ETFs — you'll miss most of their structural pivots.
8. **Reading INVALIDATION as the active pivot in legacy mode and assuming it's the swing low** — toggle Longs-Only Mode ON for the longs interpretation.

---

## 10. Ecosystem Integration

| Connected Module | How It Uses This Module |
|---|---|
| **Weinstein and Swing Pro Dashboard v67.4.12** | Displays the current trend state derived from this identical logic |
| **Weinstein Unified Ecosystem v3.4** | `f_getStrictTrend()` is a direct port of this pivot-based classification; gates every entry |
| **Weinstein Unified Ecosystem v3.4 (Recovery)** | Uses `f_getStrictTrend(leftBars, piv_d_right)` to validate the REV-RS pillar |
| **Commander Recovery Screener v2.0** | Ports the same `f_getStrictTrend` helper to gate the `dTrend == 1` requirement for REV-RS signals |
| **Commander Bull Screener v3.2** | Uses the pivot-based trend state to qualify POS-BO and SWG-BO setups |
| **Weinstein Context Layers v1.2** | The SMC module's CHoCH and BoS detection logic mirrors Section 3 of this indicator |

> **Important:** Keep your **Pivot Length** consistent across all modules. If you use Daily `2` here, set the same value in the Recovery Strategy and Capitulation Screener inputs for structural alignment.

---

## 11. Migration Path v6.0 / v6.1 → v6.2

1. **Remove v6.0 / v6.1** from your TradingView indicators panel.
2. **Add v6.2** — `Wesinstein Swing Zigzag [Strict v6.2].pine` from repo root.
3. **Defaults are sane** — Longs-Only Mode ON, Major Pivot Auto, Vol Confirm 1.5×, MTF Auto, all fib levels ON.
4. **Verify the MTF row** is populating. If empty, your symbol may not have higher-TF data (rare on NSE — check after first bar refresh).
5. **Sanity-check on a known chart** — load ANANDRATHI 125m or similar; verify INVALIDATION shows the latest LL price and BOS LEVEL shows the latest LH/HH price.
6. **Re-run any screening / strategy workflows** that read `trendState` exports — logic is unchanged for confirmed pivots, but Section 3 developing-state detection is more accurate.

### Expected behavioural differences from v6.0

- **More accurate developing-BoS detection** — Section 3 gating eliminates false HH/LL flips on extending pivots
- **Sideways pivots now count in Swing Count** — previously zeroed out
- **Trend and Structure cells now reflect developing pivots** — change in real-time as projSync extremes cross locked levels
- **Sideways trend renders amber, not white** — consistent with structure colour
- **EH / EL classes appear** where previously only HH/HL/LH/LL existed — pivots within 0.5% (default) get equal classification

---

*Last updated: 2026-06-04. v6.2 is the canonical Swing Zigzag reference. v6.0 / v6.1 guides are deprecated.*
