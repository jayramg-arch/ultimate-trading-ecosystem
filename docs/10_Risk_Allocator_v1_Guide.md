# Commander Risk Allocator v1.1 — User Guide

> **File:** `Commander_Risk_Allocator_v1.0.pine` (indicator title `v1.1`). Standalone discretionary sizing tool — complements, does not replace, the Unified Ecosystem's automated risk engine.

## 🆕 v1.1 (June 2026) — Catalyst + Regime aware targets & trail

The auto-targets and trail were synced to the post-backtest **Unified Ecosystem v3.4** config (they previously carried the legacy v4.52 hard-coded `3R bull / 3.5R bear` T2 and a flat `3.0/2.5×` Chandelier, which pre-dated the entire backtesting campaign).

- **New "Catalyst" selector** drives canonical R-multiple targets and the trail width (full table in the Panel Reference below).
- **T1 click is now an OPTIONAL override** — leave it at 0 to auto-derive T1 from the catalyst; click only to impose a discretionary target (e.g. a visible supply zone).
- **T2 is always catalyst + regime based** (POS/WYC 10R, SWG 5R, GAP 4R, SWG-REV 2R, recovery REV = 52-week high; WYC = max(10R, 52wH)).
- **Trail (Chandelier ATR mult) is catalyst-based + regime-adjusted:** POS 4.5 · WYC 3.5 · REV 2.5 · SWG 1.5 in a bull tape, **+0.5 each in a bear tape** — mirroring the strategy's `active_ce_mult = mkt_bull ? base : base + 0.5`.

---

## Overview

Commander Risk Allocator v1.1 is a standalone TradingView indicator that calculates precise position sizes for any trade setup you mark on the chart. You pick the **Catalyst** (which sets the canonical targets + trail), click your Entry and Stop Loss (and, optionally, override T1), and the panel instantly tells you how many shares to buy, how much capital is deployed, and how much you risk — all adjusted dynamically for market regime, stock volatility, and setup probability.

It is extracted from the Weinstein_Minervini_Strategy v4.52 Risk Allocator panel and enhanced with chart-click price placement (the same UX as the built-in Long Position drawing tool).

---

## Installation

1. Open TradingView Desktop.
2. Click the **Pine Editor** tab at the bottom.
3. Click **Open** → **New indicator**.
4. Paste the full source from `Commander_Risk_Allocator_v1.0.pine`.
5. Click **Save** → name it `Commander Risk Allocator v1.0`.
6. Click **Add to chart**.
7. TradingView will immediately prompt you to click three price levels on the chart (see Workflow below).

To make it easy to re-add on any chart, save it as an **Indicator Template**:
- Click the grid icon (Indicator Templates) in the top toolbar → **Save Indicator Template As** → `Risk Allocator`.

---

## Workflow — Adding a Trade Setup

Every time you add the indicator (or delete and re-add it), TradingView runs the three-click placement sequence:

| Step | Prompt | What to do |
|------|--------|------------|
| 0 | **Catalyst** (setting, not a click) | Pick the setup type — this sets your T1/T2 R-multiples and trail width before you click anything |
| 1 | **Entry Price** | Click the price level where you plan to enter the trade |
| 2 | **Stop Loss Price** | Click the price level where you will exit if wrong |
| 3 | **Target Price (T1)** — optional | Leave at 0 to auto-derive T1 from the catalyst, **or** click to override with your own target |

After the clicks the panel and chart lines appear immediately. (If you leave T1 at 0, only Entry + Stop need clicking.)

**To re-plan a trade on a different stock:**
Delete the indicator from the chart (right-click indicator status line → Remove), then re-add via your Indicator Template. The three-click sequence re-runs automatically.

---

## Settings Reference

### Master Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Asset Type | Auto | `Auto` detects ETF vs Stock from the symbol type. Override with `ETF` or `Stock` to force a specific risk tier. NSE equity funds are classified as ETF; all other NSE stocks are classified as Stock. |

### Portfolio & Risk

| Setting | Default | Description |
|---------|---------|-------------|
| Total Portfolio Capital | ₹1,00,000 | Your full tradeable capital. Set this to your actual portfolio value. All risk calculations are percentages of this number. |
| ETF Risk % | 1.00% | Maximum risk per trade when the symbol is an ETF. ETFs carry lower single-stock risk, so a slightly higher base % is appropriate. |
| Stock Risk % | 0.75% | Maximum risk per trade for individual stocks. This is the base before dynamic adjustments. |
| Max Allocation per Trade | ₹25,000 | Hard ceiling on capital deployed in any single trade, regardless of what the risk math says. Acts as a position-size cap. Set to a value that represents your maximum comfortable exposure per trade (e.g., 10–20% of portfolio). |
| Lot Multiplier | 1 | Set to 1 for NSE equity (cash segment). For F&O, set this to the lot size (e.g., 50 for Nifty, 25 for Bank Nifty) so Qty shows number of lots, not shares. |

### Interactive Trade Setup

| Setting | Default | Description |
|---------|---------|-------------|
| **Catalyst (sets T1/T2 + trail)** | POS-BO / POS-ACCUM | The setup family you are trading. Drives the canonical R-multiple targets and the Chandelier trail width, mirroring Unified Ecosystem v3.4. Options: `POS-BO / POS-ACCUM`, `WYC (Wyckoff)`, `SWG-BO / SWG-PB`, `SWG-GAP`, `SWG-REV`, `REV-CB / RS / EARLY`. See the target/trail matrix below. |
| Entry Price | (chart click) | The price you intend to enter the trade. |
| Stop Loss Price | (chart click) | Your structural stop. Click below the key support level, demand zone, or swing low you are using as your risk reference. |
| Target Price (T1) — OPTIONAL override | (chart click, or 0) | **Leave at 0** to auto-derive T1 from the selected catalyst's R-multiple. **Click** only if you want a discretionary T1 (e.g. a visible supply zone or measured move). T2 is always catalyst+regime based regardless. |
| Price Tick Size | 0.10 | All clicked prices are rounded to the nearest multiple of this value. NSE stocks typically trade in ₹0.05 or ₹0.10 ticks. Change to 0.05 if your broker uses 5-paise ticks. Set to 0 to disable rounding. |

### Risk Adjustment

These three toggles refine the raw risk % before the position size is calculated. All three are independent and additive.

| Setting | Default | Description |
|---------|---------|-------------|
| Enable Kelly Probability Sizing | On | Scales the risk budget up or down based on setup quality. See the Kelly section below for full details. |
| Reduce Risk if ATR > 3% | On | If the stock's 14-day ATR exceeds 3% of its price (i.e., it is moving more than 3% per day on average), risk is scaled down proportionally. Protects you from over-sizing on high-volatility stocks. |
| Bear-Market Risk Discount (−0.25%) | On | In a bear market (CNX500 below its 200-day SMA or 50-day below 200-day), a flat 0.25% is deducted from the base risk %. Stock Risk 0.75% becomes 0.50% in a bear market. The floor is always 0.25%. |

### Visuals

| Setting | Default | Description |
|---------|---------|-------------|
| Show Allocator Table | On | Toggles the panel on/off. |
| Table Position | Bottom Right | Where on the chart the panel appears. Six positions available. |
| Show Entry/Stop/Target Lines | On | Draws dashed horizontal lines and labels for Entry (blue), SL (red), T1 (green), T2 (lime) extending to the right of the last bar. |
| Line Extension (Bars) | 8 | How far the lines extend to the right in bars. Increase if you want longer reference lines. |

---

## Panel Reference

The panel has 12 rows. Here is what each row means:

| Row | Label | Colour | Meaning |
|-----|-------|--------|---------|
| 0 | Risk Allocator / `Stock · POS` | Blue header | Title + detected asset class + active catalyst family |
| 1 | Entry | White | Your clicked entry price, rounded to tick |
| 2 | Stop | Red | Your clicked stop price, rounded to tick |
| 3 | Adjusted Risk % | Orange | The final risk % after all adjustments, with the raw base % shown in brackets. E.g. `0.38% (Base: 0.75%)` means the base is 0.75% but after regime + vol + kelly adjustments the effective risk is 0.38%. |
| 4 | Quantity | Yellow (large) | **Shares to buy.** This is the primary output of the indicator. |
| 5 | Invested | White | Total capital deployed = Quantity × Entry Price |
| 6 | Risk Amt | White | Maximum loss if SL is hit = Quantity × (Entry − Stop) |
| 7 | T1 `n`% (xR) **[AUTO]** or **[MANUAL]** | Green | First target. The `n`% is the catalyst's partial-exit size (POS/WYC/REV 25%, SWG 33%, GAP/SWG-REV 50%). `[AUTO]` = derived from the catalyst's T1 R-multiple; `[MANUAL]` = you clicked an override. The xR shows how many stop-distances T1 sits from entry. |
| 8 | T2 25% (xR) **[AUTO]** / **[52wH]** / **[≥10R/52wH]** | Lime | Second target, catalyst+regime based. Exit 25% here. Tag shows the rule used: plain `[AUTO]` = R-multiple (POS/WYC 10R, SWG 5R, GAP 4R, SWG-REV 2R); `[52wH]` = recovery REV targets the 52-week high; `[≥10R/52wH]` = Wyckoff targets the *larger* of 10R or the 52-week high. |
| 9 | Trade Validation | Orange / Green | `✅ Clear Room to T1` means no major overhead resistance between entry and T1. `⚠️ T1 > Overhead Res (price)` means T1 sits above either the 52-week high or the 200-day SMA — a significant resistance that may cap the move. |
| 10 | Trail (`Chandelier` / `EMA20 (≈ATR)`) | Green / Red | The trailing-stop method + width for this catalyst, regime-adjusted. Shows `Bull ×N.N ATR` or `Bear ×N.N ATR`. POS/WYC/REV trail via Chandelier; SWG live-trails EMA20 (the ATR width shown is the equivalent stop-distance reference). Bull base widths: POS 4.5 · WYC 3.5 · REV 2.5 · SWG 1.5; bear adds +0.5. |

### Catalyst → Target / Trail matrix (the v1.1 core)
This is the canonical mapping, mirrored byte-for-byte from `Weinstein_Unified_Ecosystem_v3.4.pine` §7 (targets) and the shared Chandelier block (trail):

| Catalyst (selector) | T1 | T1 partial | T2 | Trail — Bull / Bear |
|---|---|---|---|---|
| **POS-BO / POS-ACCUM** | 5R | 25% | 10R | Chandelier 4.5× / 5.0× |
| **WYC (Wyckoff)** | 5R | 25% | max(10R, 52W-High) | Chandelier 3.5× / 4.0× |
| **SWG-BO / SWG-PB** | 3R | 33% | 5R | EMA20 ≈ 1.5× / 2.0× |
| **SWG-GAP** | 2R | 50% | 4R | EMA20 ≈ 1.5× / 2.0× |
| **SWG-REV** | 2R | 50% | 2R | EMA20 ≈ 1.5× / 2.0× |
| **REV-CB / RS / EARLY** | 5R | 25% | 52W-High | Chandelier (CE-REC) 2.5× / 3.0× |

> **Regime** = CNX500 above its 200-day SMA **and** 50-day above 200-day → "Bull". It widens the trail by +0.5× ATR in a bear tape (whipsaw protection) and also triggers the −0.25% bear risk discount (if enabled). Targets themselves are catalyst-driven, not regime-shifted — matching the post-backtest strategy.
| 11 | RRG Quadrant | Quad colour | Mansfield RS vs CNX500 (`M value`) and its 4-week rate of change (`mom value`). Quadrant: **LEADING** (lime) = strong and improving, **IMPROVING** (aqua) = recovering, **WEAKENING** (yellow) = strong but fading, **LAGGING** (red) = weak and deteriorating. |

---

## How Adjusted Risk % is Calculated

The indicator applies three sequential adjustments to produce the final risk %:

**Step 1 — Market Regime**
- CNX500 (NSE 500 index) is checked daily: is price above the 200-day SMA AND is the 50-day above the 200-day (Golden Cross)?
- If yes → Bull market → base risk % is used as-is.
- If no → Bear market → base risk % is reduced by 0.25% (floor: 0.25%).

**Step 2 — Volatility Discount**
- 14-day ATR is expressed as a % of the current price.
- If ATR% > 3%, risk is scaled by `3.0 / ATR%`. A stock with 6% ATR gets risk halved.
- If ATR% ≤ 3%, no discount is applied.
- The combined Vol + Kelly discount can never exceed 25% (floor: 0.75× regime risk).

**Step 3 — Kelly Probability Multiplier**
The indicator scores the current setup on three conditions:
- **Stage 2**: Daily price > 50 SMA > 150 SMA > 200 SMA (classic Weinstein Stage 2 uptrend)
- **RS positive**: Mansfield RS vs CNX500 is above zero (stock outperforming the index)
- **Volume expanding**: Current volume > 50-day average volume × 1.1

| Conditions met | Kelly multiplier | Meaning |
|----------------|-----------------|---------|
| All 3 | 1.25× | High-probability setup — size up slightly |
| Any 2 | 1.0× | Neutral — no adjustment |
| 1 or 0 | 0.75× | Low-probability setup — size down |

**Final floor**: The adjusted risk % can never fall below 0.25%, regardless of how adverse conditions are.

---

## Position Size Formula

```
Risk Amount    = Portfolio Capital × Adjusted Risk %
Qty by Risk    = floor(Risk Amount ÷ Stop Distance ÷ Lot Multiplier)
Qty by Cap     = floor(Max Allocation ÷ Entry Price ÷ Lot Multiplier)
Final Qty      = min(Qty by Risk, Qty by Cap)
```

When both quantities are equal in the panel, the Max Allocation cap is binding (the cap row shows `⚠️ Capped by X% Max Allocation`). To let the risk math drive sizing, raise Max Allocation.

---

## Chart Lines

When **Show Entry/Stop/Target Lines** is on, four dashed lines appear to the right of the last bar:

| Line | Colour | Label |
|------|--------|-------|
| Entry | Blue dashed | `Entry: xxxx.xx` |
| Stop Loss | Red dashed (thick) | `SL: xxxx.xx` |
| T1 Target | Green dashed | `T1 (xR): xxxx.xx` |
| T2 Target | Lime dashed | `T2 (xR): xxxx.xx` |

Lines are cleanly redrawn every bar (no stacking). They disappear if you reset the indicator.

---

## F&O Usage (Lot Multiplier)

For futures and options, set **Lot Multiplier** to the contract lot size:

| Instrument | Lot Size |
|-----------|---------|
| Nifty 50 futures | 75 |
| Bank Nifty futures | 30 |
| Mid Cap Nifty | 75 |
| Individual stock F&O | Check NSE circular |

With Lot Multiplier = 75, **Quantity** shows number of lots (not shares). Invested and Risk Amt scale accordingly.

---

## Resetting a Trade Plan

The indicator holds the last three clicked prices until you reset it. To start fresh:

1. Hover over the indicator name in the status line at the top of the chart.
2. Click **Settings** (gear icon) → go to **Interactive Trade Setup** → manually clear each price field to 0, then click **OK**. TradingView will re-run the three-click sequence.

Or, faster: right-click the indicator status line → **Remove** → re-add from your Indicator Template. Clean slate every time.


# Commander Risk Allocator v1.1 — Trading Guide

> The Risk Allocator is the **discretionary, chart-click** sizing companion to the automated Unified Ecosystem engine. Use it when you are placing a manual trade and want catalyst-correct targets, a regime-correct trail, and a risk-first share count.

---

## Purpose

This guide explains how to interpret the Risk Allocator panel to make better trade decisions — not just how many shares to buy, but when to trust the number, when to override it, and how to read the market context rows (RRG, Trail, Trade Validation) before placing an order. In v1.1 the **Catalyst** you select drives the targets and trail, so the panel's exits now match exactly what the strategy would do for that setup family.

---

## The Core Principle: Risk-First Sizing

Most retail traders start with a share quantity and then calculate the money at risk. The Risk Allocator reverses that: you define the maximum loss you are willing to accept on this trade (as a % of your total portfolio), and the indicator works backwards to tell you how many shares that corresponds to.

**You never risk more than you decide in advance. The position size is the output, not the input.**

---

## Step-by-Step Trade Planning Workflow

### 1. Identify the Setup First, Then Add the Indicator

Do your analysis independently. Identify:
- **Catalyst**: Which setup family is this? POS-BO/ACCUM (positional breakout/accumulation), WYC (Wyckoff accumulation), SWG-BO/PB (swing breakout/pullback), SWG-GAP, SWG-REV, or REV (recovery). This is your first decision — it sets the R-targets and trail.
- **Entry**: The exact price where you will place your buy order — typically the breakout level, VWAP reclaim, or your pullback zone trigger.
- **Stop Loss**: The price that invalidates the setup — below the demand zone, below the key swing low, or below the structure low with a small buffer.
- **Target (T1)**: *Optional.* By default the catalyst auto-derives T1 (e.g. 5R for positional). Only override by clicking if you see a hard structural target first — the next supply zone, prior high, or measured move — that comes *before* the catalyst's R-target.

Only after you have decided the catalyst and levels independently should you add the Risk Allocator. Never let the indicator choose your *entry/stop* — it sizes your position based on what you tell it, so bad levels produce a correctly sized bad trade.

### 2. Select Catalyst, then Click Entry → Stop (→ optional Target)

First set the **Catalyst** dropdown. Then TradingView prompts you for Entry and Stop in order. Leave the Target (T1) prompt at 0 to accept the catalyst's auto T1, or click your override. Be precise — use the crosshair and zoom in if needed. The indicator rounds to the nearest ₹0.10 tick automatically, so minor cursor imprecision is forgiven.

### 3. Read the Panel Top to Bottom

After placement, read the panel systematically before committing to the trade:

```
Entry / Stop          → Confirm the numbers match your plan
Adjusted Risk %       → Understand what the market conditions are doing to your risk budget
Quantity              → The only number you need to place the order
Invested / Risk Amt   → Sanity check against your account balance
T1 / T2               → Catalyst-correct exit levels (auto unless you overrode T1)
Trade Validation      → Is T1 structurally clear?
Trail                 → Catalyst+regime trailing-stop method & width
RRG Quadrant          → Is this stock leading the market?
```

---

## Reading Adjusted Risk % — What the Market Is Telling You

The orange row is one of the most important rows in the panel. It shows two numbers: `X.XX% (Base: Y.YY%)`.

- **Base %** is your raw setting (e.g., 0.75% for stocks).
- **Adjusted %** is what the indicator has decided to actually use after reading current market conditions.

### When Adjusted = Base (e.g., `0.75% (Base: 0.75%)`)
All conditions are favourable:
- CNX500 is in a bull market (Golden Cross intact)
- Stock ATR is ≤ 3%
- Kelly score is neutral (2 of 3 conditions met)

**Interpretation:** Normal conditions. Full position size. This is a routine trade in a cooperative environment.

### When Adjusted < Base (e.g., `0.38% (Base: 0.75%)`)
One or more adverse conditions are active. The indicator has reduced your risk exposure automatically. Common causes:

| Reduction | Cause | What it means |
|-----------|-------|--------------|
| −0.25% flat | Bear market | CNX500 lost its Golden Cross. The broad market is in a downtrend. Even good stocks face headwinds. |
| Proportional reduction | High ATR | This stock is moving more than 3%/day. You are seeing large candles. A smaller position keeps your rupee risk constant even on a volatile name. |
| 0.75× Kelly | Weak setup | The stock is not in Stage 2, RS is negative, and/or volume is below average. The probability of this setup working is lower than usual. |

**Interpretation:** The indicator is protecting you. Accept the smaller size. Do not manually override to a larger quantity — the market is telling you something.

### When Adjusted > Base (e.g., `0.94% (Base: 0.75%)`)
Kelly multiplier is at 1.25×, meaning all three high-probability conditions are met: Stage 2 uptrend, positive RS vs CNX500, volume expanding. This is a high-quality setup.

**Interpretation:** The indicator is giving you permission to size up slightly. Take the full calculated quantity.

---

## Reading the Quantity Row

The large yellow **Quantity** number is what you type into your broker's order entry. Nothing else.

### When Both Columns Show the Same Number (Allocation Cap Active)
If the Trade Validation row shows `⚠️ Capped by X% Max Allocation`, the Max Allocation setting is binding — the risk math wanted a larger position but the cap reduced it. This means:

- Your stop loss distance is small relative to your risk budget (so the math wants many shares).
- But your Max Allocation cap is limiting exposure.

**What to do:**
- If the cap feels appropriate, accept the quantity and move on.
- If you want the full risk-based sizing, raise Max Allocation in settings.
- Do not interpret this as a problem — the cap is a safety feature for position concentration.

### Zero Quantity
If Quantity shows 0, either:
- Entry or Stop is 0 (prices not yet placed — check if the click sequence completed).
- Entry equals Stop (zero stop distance — your SL click landed on the same level as Entry).
- Max Allocation is set too low for the current stock price (floor(Max Alloc ÷ Entry) = 0).

---

## Trade Validation Row — Before You Enter

### ✅ Clear Room to T1
T1 is below both the 52-week high and the 200-day SMA. There is no known major overhead resistance between your entry and your first target. The trade has structural room to reach T1.

**Action:** Proceed normally.

### ⚠️ T1 > Overhead Res (price)
Your T1 click lands above a major overhead level — either the 200-day SMA (if you are currently below it) or the 52-week high. This resistance level has historically caused selling pressure.

**What this means in practice:**
- T1 may not be reached cleanly. The stock may stall at the resistance level shown.
- You have three options:
  1. **Lower T1** to just below the resistance level. Re-click Target to a more realistic price. The panel will update.
  2. **Accept the warning** and plan a partial exit at the resistance level (e.g., take 30% off at resistance, let 20% run to your original T1).
  3. **Skip the trade** if the resistance level is too close to entry to give an acceptable R:R.

The resistance price is shown in brackets, e.g., `⚠️ T1 > Overhead Res (1065)`. Use that level as your practical first target.

---

## Trail Row — Catalyst + Regime Trailing Stop (v1.1)

The Trail row shows the method (`Chandelier` for POS/WYC/REV, `EMA20 (≈ATR)` for swing) plus a regime-adjusted ATR width. The width is set by **catalyst** and widened **+0.5× in a bear tape**:

| Catalyst | Bull width | Bear width | Method |
|---|---|---|---|
| POS-BO / POS-ACCUM | ×4.5 ATR | ×5.0 ATR | Chandelier |
| WYC (Wyckoff) | ×3.5 ATR | ×4.0 ATR | Chandelier / CE-REC |
| REV-CB / RS / EARLY | ×2.5 ATR | ×3.0 ATR | Chandelier / CE-REC |
| SWG-BO / PB / GAP / REV | ×1.5 ATR | ×2.0 ATR | EMA20 (live); ATR width = equivalent reference |

**How to use it practically:**
- Once your trade is profitable, set a trailing stop in your broker.
- **POS / WYC / REV:** trail at (Highest Close over last 22 bars) − (ATR(22) × the width above). Wide multiples (4.5×) are deliberate — they let a 10R positional runner breathe through ~30% pullbacks without stopping out.
- **Swing:** trail under the rising EMA-20 (the ATR width shown is just the equivalent stop distance for sizing intuition).
- These widths match exactly what `Weinstein_Unified_Ecosystem_v3.4.pine` applies per catalyst (`active_ce_mult = mkt_bull ? base : base + 0.5`).

---

## RRG Quadrant Row — Stock Momentum vs the Market

The RRG (Relative Rotation Graph) row shows two numbers: **M** (Mansfield RS × 100) and **mom** (4-week rate of change of Mansfield RS). Together they classify the stock into one of four quadrants.

| Quadrant | Colour | M value | Mom value | Meaning |
|----------|--------|---------|-----------|---------|
| LEADING | Lime | > 0 | > 0 | Stock is outperforming CNX500 AND the outperformance is accelerating. Best quadrant to be long in. |
| WEAKENING | Yellow | > 0 | ≤ 0 | Stock is still outperforming but the relative momentum is fading. Can still be traded but watch closely. |
| IMPROVING | Aqua | ≤ 0 | > 0 | Stock is underperforming the index but the relative strength is starting to recover. Early-stage setups. |
| LAGGING | Red | ≤ 0 | ≤ 0 | Stock is underperforming and deteriorating. Avoid new longs except with very clear catalysts. |

### Practical RRG Rules

**Minimum for a long trade:** IMPROVING or better. Do not initiate new longs in LAGGING stocks.

**Highest-quality setups:** LEADING quadrant with mom > 50. The stock is leading the index and accelerating. These are the setups where Kelly multiplier will be at 1.25× and the full risk budget is deployed.

**WEAKENING alert:** If you are already in a position and the RRG shifts from LEADING to WEAKENING, consider tightening your trailing stop or taking partial profits at T1 even if the stock has not reached T1 yet.

---

## T1 and T2 — The Exit Framework (catalyst-driven in v1.1)

### T1 — Your Tactical Exit
T1 is now **auto-derived from the catalyst** (or your `[MANUAL]` override). The partial-exit size shown next to it is catalyst-specific:

| Catalyst | T1 | Partial exit at T1 |
|---|---|---|
| POS / WYC / REV | 5R | 25% (keep a big runner — these are positional/recovery) |
| SWG-BO / PB | 3R | 33% |
| SWG-GAP / SWG-REV | 2R | 50% (quick setups — take more off early) |

**When T1 is hit:** Sell the partial % shown. Move your stop to entry price (breakeven stop) — the remaining position can no longer lose.

### T2 — The Runner Target (25%)
T2 is automatically calculated from the catalyst, not the regime:

| Catalyst | T2 | Tag |
|---|---|---|
| POS-BO / POS-ACCUM | 10R | `[AUTO]` |
| WYC (Wyckoff) | max(10R, 52-Week High) | `[≥10R/52wH]` |
| SWG-BO / PB | 5R | `[AUTO]` |
| SWG-GAP | 4R | `[AUTO]` |
| SWG-REV | 2R | `[AUTO]` |
| REV-CB / RS / EARLY | 52-Week High | `[52wH]` |

The wide positional/Wyckoff T2 (10R) is the post-backtest "let winners run" target — the old flat 3R/3.5R was clipping trend runners far too early. T2 is not your click; you do not need to set it.

**When T2 is hit:** Sell another 25% (the runner lot). Trail the final 25% with the catalyst's Trail-row stop to let it run.

### Summary Exit Plan

| Milestone | Action | Position remaining |
|-----------|--------|-------------------|
| Stop Loss hit | Exit 100% | 0% |
| T1 hit | Exit 50% | 50% |
| Move stop to breakeven | No exit | 50% (risk-free) |
| T2 hit | Exit 25% | 25% |
| Trail remaining 25% with CE stop | Exit when stop hit | 0% |

---

## Common Scenarios

### Scenario A: High-Quality Bull Setup
- CNX500 healthy (Golden Cross), stock in Stage 2, RS positive, volume expanding.
- Adjusted Risk = Base Risk (0.75%), Kelly = 1.25×, so effective risk ≈ 0.94%.
- RRG: LEADING. Trade Validation: ✅ Clear.
- **Decision:** Take the full calculated Quantity. Strong conviction trade.

### Scenario B: Bull Setup, Volatile Stock
- CNX500 healthy but stock ATR = 5% (very wide daily moves).
- Adjusted Risk = 0.45% (Base 0.75% × vol discount 0.60).
- **Decision:** Accept the smaller quantity. The rupee risk is still the same — you are just buying fewer shares of a wider-moving stock. Trying to force the full size would mean risking 1.5× your plan on a single bad day.

### Scenario C: Bear Market, Relative Strength Survivor
- CNX500 below 200 SMA (bear market).
- Stock is in IMPROVING quadrant — it is holding up while others fall.
- Adjusted Risk = 0.38% (0.75% − 0.25% regime − some vol discount).
- **Decision:** The indicator is right to reduce size. Bear market longs need smaller initial positions. If the stock confirms and breaks out, you can add on strength.

### Scenario D: T1 Blocked by 52-Week High
- T1 is set at ₹1,200 but the 52-week high is ₹1,150 and Trade Validation shows ⚠️.
- **Decision:** Adjust T1 to ₹1,140 (just below the 52-week high). Re-click Target. The R:R will be lower — if it falls below 1.5R, this trade may not be worth taking until the stock breaks through and clears the 52-week high.

### Scenario E: Max Allocation Cap Binding
- Risk math says buy 74 shares but Max Allocation caps at 11.
- **Decision:** First check if Max Allocation is set correctly for your portfolio size. If it is intentional, accept 11 shares — you are controlling position concentration. If you want the risk math to drive sizing, raise Max Allocation to at least 10–15% of portfolio capital.

---

## Key Settings for Indian NSE Swing Trading

These settings work well as a starting point for NSE swing and positional trades:

| Setting | Recommended Value | Rationale |
|---------|------------------|-----------|
| Portfolio Capital | Your actual capital | Use the capital you actively deploy, not your total net worth |
| Stock Risk % | 0.75% | Standard Weinstein/Minervini position sizing |
| ETF Risk % | 1.00% | ETFs are less volatile than individual stocks |
| Max Allocation | 10–20% of capital | Prevents over-concentration; 15% is a sensible starting point |
| Lot Multiplier | 1 | For cash equity; adjust for F&O |
| Price Tick Size | 0.10 | NSE standard for most stocks; use 0.05 for some SEBI-permitted ticks |
| Kelly Sizing | On | Accept the probability adjustment — it has statistical backing |
| Vol Scale | On | Protects against oversizing on erratic stocks |
| Bear Discount | On | Forces conservatism in adverse markets |

---

## What the Indicator Does NOT Do

- **It does not tell you whether to take the trade.** It only sizes the trade after you decide to take it. Setup quality, fundamental screening, and timing are your responsibility.
- **It does not set alerts.** Use TradingView's native Alert tool to set price alerts at your Entry, SL, T1, and T2 levels.
- **It does not manage the trade after entry.** Once you are in, you manage the CE trailing stop and partial exits manually or via the Weinstein_Minervini_Strategy's automated exit system.
- **It does not account for brokerage and taxes.** The Risk Amt shown is the gross loss before charges. NSE trades attract brokerage, STT, and exchange charges. Budget 0.1–0.3% for round-trip costs on intraday; 0.05–0.1% for delivery.
- **T2 is a reference level, not a hard exit signal.** In strongly trending stocks, it is valid to hold past T2 and trail the remaining 25% with the CE stop. T2 is the minimum runner target, not the maximum.
