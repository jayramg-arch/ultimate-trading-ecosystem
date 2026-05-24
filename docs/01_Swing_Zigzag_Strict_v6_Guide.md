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
| **Panel rows** | 11 rows: TIMEFRAME, TREND, MTF, STRUCTURE, SWING COUNT, SWING RANGE, CHOPPINESS, INVALIDATION, BOS LEVEL, VOL CONFIRM, BAR AGE |
| **Sideways colour** | Sideways trend is now **amber** (🟡 `#FFBF00`), not white — matches Structure colour |

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

## 4. The Information Panel — Row by Row (11 rows)

### Row 0 — TIMEFRAME

Human-readable label for the current chart resolution: `Monthly` / `Weekly` / `Daily` / `75 min` / `125 min` etc.

### Row 1 — TREND

| Value | When |
|---|---|
| 🟢 UPTREND | trendState = +1 (confirmed or developing) |
| 🔴 DOWNTREND | trendState = −1 |
| 🟡 SIDEWAYS | trendState = 0 |

Colour mirrors the trend.

### Row 2 — MTF (xx)

Trend state of the higher timeframe (label shows which TF, e.g. `MTF (W)` on a daily chart). Uses `request.security()` to evaluate this same indicator's `trendState` on the parent TF.

**Use:** confluence check. UPTREND on current TF + UPTREND on MTF = aligned. Conflict = countertrend setup, lower probability.

### Row 3 — STRUCTURE

Format: `<high class> / <low class>` — e.g. `HH / HL`, `LH / LL`, `EH / EL`. Reflects developing values where applicable.

Colour mirrors Trend.

### Row 4 — SWING COUNT

`N swing(s)` — consecutive pivots in the **same trend state**. Counts up by 1 for each confirmed (or projected developing) pivot that maintains the state. Resets to 1 on state change (CHoCH).

≥ 3 turns yellow — extended trend, statistically more likely to pause.

### Row 5 — SWING RANGE

% distance of the **currently developing** swing:

```
(projSyncHigh − projSyncLow) / projSyncLow × 100
```

One end always equals `activePivotPrice` (by construction of the projSync window), the other is the developing extreme on the opposite side.

Colour bands tied to `majorThresh`:
- **Gray** — `< majorThresh` (minor)
- **Green** — `1× to 2× majorThresh` (healthy major swing)
- **Yellow** — `> 2× majorThresh` (extended)

### Row 6 — CHOPPINESS

`N flips / KW` — count of confirmed direction flips (H↔L) in a rolling lookback window (configurable, default 52 weeks → auto-converted to bars per TF).

**+1 added live** when a developing pivot is in progress (the in-flight flip pre-registers).

Colour bands:
- **Green** ≤ 4 flips — clean / trending
- **Yellow** 5–8 — moderate
- **Red** > 8 — choppy

### Row 7 — INVALIDATION

**Longs-Only Mode (default):** Latest swing **low** — your structural stop for a long.
- `active=="L"` → `activePivotPrice` (the deepest extending low)
- `active=="H"` → `lockedLow` (most recent confirmed low)

**Legacy mode:** active pivot price (could be a high).

Format: `<price> (<class>)`, e.g. `3479.00 (LL)`. Colour matches Trend.

### Row 8 — BOS LEVEL

**Longs-Only Mode:** Latest swing **high** (`lockedHigh`) — the price above which a bullish BoS triggers.

We keep showing the prior locked high **even after** price breaks above it (developing HH) — the broken level remains the actionable retest zone until a new HH formally locks (option-a behaviour).

Format: `<price> (<class>)`, e.g. `3595.00 (LH)`.

**Class label tells you BoS type:**
- `(LH)` → CHoCH (trend change, high conviction)
- `(HH)` → continuation BoS (add to existing trend)
- `(EH)` → range breakout (context-dependent)

**Legacy mode:** shows `—`.

### Row 9 — VOL CONFIRM

Volume on the **most recent BoS bar**, expressed as ratio of the 50-bar volume SMA. Captured once on the BoS trigger bar, persists until the next BoS overwrites it.

In Longs-Only Mode, only **bullish** BoS (`bosUp`) is captured — bearish breakdowns are ignored.

Format: `✅ ↑ 1.85×` (passes) or `❌ ↑ 0.92×` (fails). Threshold = `volConfirmMult` input (default 1.5×).

| Ratio | Interpretation |
|---|---|
| < 1.0× | Below average — usually fakeout |
| 1.0–1.5× | Average — ❌ no conviction |
| 1.5–2.5× | ✅ Weinstein-grade minimum |
| 2.5–5.0× | ✅ Strong, institutional |
| > 5.0× | 🔥 Exceptional accumulation/distribution event |

### Row 10 — BAR AGE

`bar_index − activePivotIndex` → bars elapsed since the active pivot formed. A swing-maturity gauge — pairs with Swing Count to read time + structure together.

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
| **Weinstein and Swing Pro Dashboard v67.0** | Displays the current trend state derived from this identical logic |
| **Weinstein Minervini Strategy v4.53** | `f_getStrictTrend()` is a direct port of this pivot-based classification; gates every entry |
| **Recovery Strategy v1.4** | Uses `f_getStrictTrend(leftBars, piv_d_right)` to validate the REV-RS pillar |
| **Capitulation Screener v1.5** | Ports the same `f_getStrictTrend` helper to gate the `dTrend == 1` requirement for REV-RS signals |
| **Beta Screener v2.6** | Uses the pivot-based trend state to qualify POS-BO and SWG-BO setups |
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

*Last updated: 2026-05-22. v6.2 is the canonical Swing Zigzag reference. v6.0 / v6.1 guides are deprecated.*
