# Commander Risk Allocator v1.0 — User Guide

> [!WARNING]
> **LEGACY REFERENCE MANUAL - ARCHIVAL USE ONLY**
> This document covers the standalone Risk Allocator v1.0. It has been superseded by the **Unified Ecosystem v2.2** integrated risk management framework.
> For the current canonical guide, please refer to:
> - [10_Risk_Allocator_v1_Guide.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/10_Risk_Allocator_v1_Guide.md)
> - [00_INDEX.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/00_INDEX.md)

---

## Overview

Commander Risk Allocator v1.0 is a standalone TradingView indicator that calculates precise position sizes for any trade setup you mark on the chart. You click three price levels — Entry, Stop Loss, and Target — and the panel instantly tells you how many shares to buy, how much capital is deployed, and how much you risk, all adjusted dynamically for market regime, stock volatility, and setup probability.

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
| 1 | **Entry Price** | Click the price level where you plan to enter the trade |
| 2 | **Stop Loss Price** | Click the price level where you will exit if wrong |
| 3 | **Target Price (T1)** | Click your primary profit target |

After the third click the panel and chart lines appear immediately.

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
| Entry Price | (chart click) | The price you intend to enter the trade. |
| Stop Loss Price | (chart click) | Your structural stop. Click below the key support level, demand zone, or swing low you are using as your risk reference. |
| Target Price (T1) | (chart click) | Your primary target. This becomes the T1 exit level. T2 is computed automatically. |
| Price Tick Size | 0.10 | All three clicked prices are rounded to the nearest multiple of this value. NSE stocks typically trade in ₹0.05 or ₹0.10 ticks. Change to 0.05 if your broker uses 5-paise ticks. Set to 0 to disable rounding. |

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
| 0 | Risk Allocator / Stock or ETF | Blue header | Title + detected asset class |
| 1 | Entry | White | Your clicked entry price, rounded to tick |
| 2 | Stop | Red | Your clicked stop price, rounded to tick |
| 3 | Adjusted Risk % | Orange | The final risk % after all adjustments, with the raw base % shown in brackets. E.g. `0.38% (Base: 0.75%)` means the base is 0.75% but after regime + vol + kelly adjustments the effective risk is 0.38%. |
| 4 | Quantity | Yellow (large) | **Shares to buy.** This is the primary output of the indicator. |
| 5 | Invested | White | Total capital deployed = Quantity × Entry Price |
| 6 | Risk Amt | White | Maximum loss if SL is hit = Quantity × (Entry − Stop) |
| 7 | T1 50% (xR) | Green | Your clicked target price. The xR shows how many multiples of your stop distance T1 is from entry. At T1, the convention is to exit 50% of the position. |
| 8 | T2 25% (xR) [AUTO] | Lime | Auto-computed second target. In a bull market (CNX500 healthy) T2 = Entry + 3R. In a bear market T2 = Entry + 3.5R. Exit 25% of the position here. |
| 9 | Trade Validation | Orange / Green | `✅ Clear Room to T1` means no major overhead resistance between entry and T1. `⚠️ T1 > Overhead Res (price)` means T1 sits above either the 52-week high or the 200-day SMA — a significant resistance that may cap the move. |
| 10 | CE Mode | Green / Red | Shows whether the Chandelier Exit is running in Bull mode (tighter stop, ×3.0 ATR) or Bear mode (looser stop, ×3.5 ATR). This mirrors the same regime calculation used in the strategy. |
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


# Commander Risk Allocator v1.0 — Trading Guide

> [!WARNING]
> **LEGACY REFERENCE MANUAL - ARCHIVAL USE ONLY**
> This document covers the standalone Risk Allocator v1.0. It has been superseded by the **Unified Ecosystem v2.2** integrated risk management framework.
> For the current canonical guide, please refer to:
> - [10_Risk_Allocator_v1_Guide.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/10_Risk_Allocator_v1_Guide.md)
> - [00_INDEX.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/00_INDEX.md)

---

## Purpose

This guide explains how to interpret the Risk Allocator panel to make better trade decisions — not just how many shares to buy, but when to trust the number, when to override it, and how to read the market context rows (RRG, CE Mode, Trade Validation) before placing an order.

---

## The Core Principle: Risk-First Sizing

Most retail traders start with a share quantity and then calculate the money at risk. The Risk Allocator reverses that: you define the maximum loss you are willing to accept on this trade (as a % of your total portfolio), and the indicator works backwards to tell you how many shares that corresponds to.

**You never risk more than you decide in advance. The position size is the output, not the input.**

---

## Step-by-Step Trade Planning Workflow

### 1. Identify the Setup First, Then Add the Indicator

Do your analysis independently. Identify:
- **Entry**: The exact price where you will place your buy order — typically the breakout level, VWAP reclaim, or your pullback zone trigger.
- **Stop Loss**: The price that invalidates the setup — below the demand zone, below the key swing low, or below the structure low with a small buffer.
- **Target (T1)**: The first logical resistance — the next supply zone, prior high, measured move, or round-number confluence.

Only after you have decided these three levels independently should you add the Risk Allocator and click them. Never let the indicator choose your levels — it sizes your position based on what you tell it, so bad levels produce a correctly sized bad trade.

### 2. Click in Sequence: Entry → Stop → Target

TradingView prompts you in order. Be precise. Use the crosshair and zoom in if needed. The indicator rounds to the nearest ₹0.10 tick automatically, so minor cursor imprecision is forgiven.

### 3. Read the Panel Top to Bottom

After placement, read the panel systematically before committing to the trade:

```
Entry / Stop          → Confirm the numbers match your plan
Adjusted Risk %       → Understand what the market conditions are doing to your risk budget
Quantity              → The only number you need to place the order
Invested / Risk Amt   → Sanity check against your account balance
T1 / T2               → Know your exit levels before you enter
Trade Validation      → Is T1 structurally clear?
CE Mode               → What type of trailing stop will you use?
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

## CE Mode Row — Choosing Your Trailing Stop Method

| Display | Colour | Meaning |
|---------|--------|---------|
| Bull ×3.0 | Green | Market is in a bull regime. Use a tight Chandelier Exit (ATR × 3.0) to trail your stop once in profit. This captures more of the trend. |
| Bear ×3.5 | Red | Market is in a bear regime. Use a looser Chandelier Exit (ATR × 3.5) to avoid whipsaws on the wider bear-market candles. |

**How to use it practically:**
- Once your trade is profitable, set a trailing stop in your broker using an ATR-based formula.
- Bull mode: trail at (Highest High over last 22 bars) − (ATR(22) × 3.0).
- Bear mode: trail at (Highest High over last 22 bars) − (ATR(22) × 3.5).
- These numbers match exactly what the Weinstein_Minervini_Strategy uses for its Chandelier Exit.

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

## T1 and T2 — The Exit Framework

### T1 — Your Tactical Exit (50%)
T1 is the price you clicked. The `50%` label means at T1, the convention is to exit half your position. This:
- Locks in a guaranteed profit on the trade
- Reduces your position size going into the uncertain second half
- Means your remaining 25% runs with a stop now at or above breakeven

**When T1 is hit:** Sell 50% of your Quantity. Move your stop to entry price (breakeven stop).

### T2 — The Runner Target (25%) [AUTO]
T2 is automatically calculated:
- **Bull market (CE Mode: Bull):** Entry + 3× stop distance (3R)
- **Bear market (CE Mode: Bear):** Entry + 3.5× stop distance (3.5R)

The 3.5R in bear markets is deliberately higher because in bearish conditions, the trades that do work tend to be stronger trend moves — and you want to let them run further before exiting.

The `[AUTO]` label means this level is not your click — it is computed. You do not need to do anything to set T2.

**When T2 is hit:** Sell another 25% of original position (the final runner lot). The remaining 25% can be trailed with the CE stop to let it run.

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
