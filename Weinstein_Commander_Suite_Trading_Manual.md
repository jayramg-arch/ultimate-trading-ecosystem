# Weinstein Commander Suite — Complete Trading Manual & User Guide

> [!WARNING]
> **LEGACY REFERENCE MANUAL - ARCHIVAL USE ONLY**
> This comprehensive manual (v4.5) has been superseded by the **Unified Ecosystem v2.2** documentation framework.
> For the current canonical source of truth and operational workflow, please refer to:
> - [13_Unified_Ecosystem_User_Guide.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/13_Unified_Ecosystem_User_Guide.md)
> - [14_Unified_Ecosystem_Trading_Guide.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/14_Unified_Ecosystem_Trading_Guide.md)
> - [00_INDEX.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/00_INDEX.md)

---

### Version: Suite v4.5 | Reference Date: April 2026

---

> **This document is your single source of truth for operating the Weinstein Commander Suite. It covers every module, every signal, every setting, and the complete end-to-end trading process from universe screening to trade exit.**

---

## TABLE OF CONTENTS

| # | Section |
|---|---------|
| 1 | [The Philosophy — Weinstein + Minervini Unified Method](#philosophy) |
| 2 | [Suite Architecture & Module Roles](#architecture) |
| 3 | [Module 1: Swing Pro Dashboard v63.0](#dashboard) |
| 4 | [Module 2: Strategy v4.4 (Backtesting Engine)](#strategy) |
| 5 | [Module 3: Swing Zigzag Strict v6.0](#zigzag) |
| 6 | [Module 4: Fundamental X-Ray v2.1](#fundamental) |
| 7 | [Module 5: Commander Screener ULTIMATE v3.5](#ultimate) |
| 8 | [Module 6: Commander Screener Beta Edition v2.2](#beta) |
| 9 | [The Complete Trading Workflow (End-to-End)](#workflow) |
| 10 | [Risk Management Framework](#risk) |
| 11 | [Signal Glossary & Decision Trees](#glossary) |
| 12 | [Common Mistakes & How to Avoid Them](#mistakes) |
| 13 | [Quick Reference Cheat Sheet](#cheatsheet) |

---

<a name="philosophy"></a>
## 1. THE PHILOSOPHY — Weinstein + Minervini Unified Method

The Commander Suite is built on two interlinked methodologies:

### Stan Weinstein's Stage Analysis
Weinstein classifies every stock into one of four lifecycle stages based on its **weekly 30-SMA** (Simple Moving Average). Your job is simple: **only buy in Stage 2 (Advancing)** and never hold through Stage 3 or 4.

| Stage | Description | 30-WMA Direction | Price vs MA | Action |
|-------|-------------|-----------------|-------------|--------|
| **1 — Basing** | Accumulation / Flat base | Flat | Around MA | Watch List only |
| **2 — Advancing** | 🟢 Uptrend with rising MA | Rising | Above MA | **BUY zone** |
| **3 — Topping** | Distribution / Churn | Flattening | Starting below MA | AVOID / Exit |
| **4 — Declining** | 🔴 Downtrend | Falling | Below MA | NEVER BUY |

### Mark Minervini's Trend Template
Within Stage 2, Minervini's Trend Template filters for stocks with exceptional momentum. A stock passes if all 6 conditions hold simultaneously:
1. Price > 50-Day SMA
2. Price > 150-Day SMA
3. Price > 200-Day SMA
4. 50-DMA > 150-DMA > 200-DMA (all aligned upward)
5. Price >= 75% of its 52-week high
6. Price >= 30% above its 52-week low

### The Unified Principle
> *"Stage 2 filters the universe to only uptrending stocks. Minervini's template filters that universe to only the strongest. You then trade the catalyst (breakout or pullback) within that elite group."*

### Six Catalyst Types
The Suite detects six distinct entry catalysts:

| Code | Name | Description |
|------|------|-------------|
| **POS-BO** | Positional Breakout | Stage 2 breakout above 20-day pivot high with volume surge |
| **POS-ACCUM** | Positional Accumulation | OBV making new highs while price lags — institutional load |
| **SWG-PB** | Swing Pullback | EMA20 bounce in RSI 40-60 pocket with volume dry-up |
| **SWG-BO** | Swing VCP Breakout | Volatility Contraction Pattern pivot break with volume |
| **SWG-REV** | Swing Mean Reversion | Extreme RSI-3 (<20) oversold with volume spike |
| **SWG-GAP** | Gap & Go | 4%+ gap up with 3x daily average volume |

---

<a name="architecture"></a>
## 2. SUITE ARCHITECTURE & MODULE ROLES

```
UNIVERSE (NSE/BSE ~5000 stocks)
         |
         v
+-----------------------------+
|  MODULE 5: ULTIMATE         |  <- Batch screener: rank up to 30 stocks
|  Commander Screener v3.5    |    by Score, Stage, RS, Catalyst
+-------------+---------------+
              |  Top-ranked candidates
              v
+-----------------------------+
|  MODULE 6: BETA EDITION     |  <- Single-stock deep scan on TradingView
|  Screener v2.2              |    via data window; use in Stock Screener
+-------------+---------------+
              |  Shortlisted candidates
              v
+-----------------------------+
|  MODULE 3: SWING ZIGZAG     |  <- Validate structure: HH/HL pattern
|  Strict v6.0                |    Fib levels, trend state, choppiness
+-------------+---------------+
              |  Structure-confirmed candidates
              v
+-----------------------------+
|  MODULE 4: FUNDAMENTAL      |  <- Validate business quality
|  X-Ray v2.1                 |    Minervini Score, Overall Grade
+-------------+---------------+
              |  High-quality setup candidates
              v
+-----------------------------+
|  MODULE 1: SWING PRO        |  <- Full per-stock analysis on chart
|  Dashboard v63.0            |    Portfolio tracking, all 30 slots
+-------------+---------------+
              |  Trade decision (Entry / Wait / Avoid)
              v
+-----------------------------+
|  MODULE 2: STRATEGY v4.4    |  <- Backtesting engine + Live trade
|  (Backtest & Live Engine)   |    execution, SL, targets, position size
+-----------------------------+
```

---

<a name="dashboard"></a>
## 3. MODULE 1: WEINSTEIN & SWING PRO DASHBOARD v63.0

### 3.1 Purpose
The **Swing Pro Dashboard** is your primary per-stock command center. Once you have a candidate, apply this indicator to its chart to get a complete 360-degree assessment: Stage, Market Health, Relative Strength, Entry/Exit Recommendations, Portfolio P&L tracking, and Algorithmic recommendations — all in a single overlay.

### 3.2 Installation
1. In TradingView, open Pine Script editor -> paste the v63.0 code -> **Save & Add to Chart**
2. Apply on the **stock's own chart** on a Daily timeframe (it auto-fetches Weekly data internally)
3. Recommended overlay position: `Bottom Right`

### 3.3 Input Groups — Complete Reference

#### 3.3.1 Portfolio Slots 1-30 (Groups 1-6)
The Dashboard can track up to **30 live positions simultaneously**. It auto-detects when the current chart matches a portfolio slot and activates full tracking mode.

| Field | What to Enter | Example |
|-------|---------------|---------|
| **Slot N** (Ticker) | Full TradingView ticker with exchange prefix | `NSE:RELIANCE` |
| **Entry** | Your actual purchase price | `1358.33` |
| **SL** | Your hard stop loss price | `1285.00` |
| **Sector** | The matching sector index symbol | `NSE:CNXENERGY` |
| **Date** | Trade entry date (click calendar icon) | `2026-01-15` |

**Valid Sector Symbols:**
```
NSE:BANKNIFTY   NSE:CNXIT      NSE:CNXPHARMA  NSE:CNXAUTO
NSE:CNXFMCG     NSE:CNXMETAL   NSE:CNXENERGY  NSE:CNXREALTY
NSE:CNXINFRA    NSE:CNX500
```

> **TIP:** Leave Slot N Ticker blank ("") to disable that slot. The dashboard ignores empty slots.

#### 3.3.2 Quick Check (Overrides Portfolio)
Use this for **temporary analysis** when charting a stock not in your portfolio:
- **Temporary Entry Price**: Set to a hypothetical entry for RR analysis
- **Temporary Hard SL**: Set a test stop loss

When these are non-zero, they **override** any portfolio slot match for the current stock.

#### 3.3.3 Strategy Inputs
| Setting | Default | What It Controls |
|---------|---------|-----------------|
| Weinstein SMA Length (Weekly) | 30 | The core Weinstein 30-Week MA period |
| 30 WMA Slope Lookback (Weeks) | 4 | How many weeks back to measure slope |
| 30WMA Slope Threshold (Flat) | 0.0005 | % below which slope is "flat" (not rising) |
| Benchmark 1 (Nifty 50) | `NSE:NIFTY` | RS comparison against large-cap market |
| Benchmark 2 (Nifty 500) | `NSE:CNX500` | RS comparison against broad market |
| Mansfield RS Length | 26 | Weeks for Mansfield RS SMA (approx 130 daily bars) |
| RS Slope Lookback (Weeks) | 8 | RS trend direction lookback |

#### 3.3.4 Daily MA Settings
| Setting | Default | Purpose |
|---------|---------|---------|
| 50 DMA Length | 50 | Short-term trend MA |
| 150 DMA Length | 150 | Medium-term trend MA (approx 30-WMA proxy) |
| 200 DMA Length | 200 | Long-term trend MA (institutional benchmark) |
| 50DMA Slope Lookback (Days) | 21 | Measures 50-DMA trend direction |
| Slope Flat Threshold (Daily) | 0.0005 | % below which 50-DMA slope is "flat" |

#### 3.3.5 Technical Settings
| Setting | Default | Purpose |
|---------|---------|---------|
| Est. Pullback Lookback (Days) | 21 | Fibonacci swing reference window |
| Pivot Lookback Left (Daily) | 2 | Bars left of pivot high/low for detection |
| Pivot Lookback Right (Daily) | 2 | Bars right of pivot for confirmation |
| ATR Length | 14 | ATR period for volatility calculations |
| VP Lookback Bars | 100 | Volume Profile reference window |

#### 3.3.6 Mathematical Edges (Backtested)
These are **the most important filters** — backtested over 5 years to provide statistical edge:

| Toggle | Default | Effect When Enabled |
|--------|---------|---------------------|
| **Macro Edge: Institutional Vol Bias** | ON | Requires VWMA(50) > SMA(50) (Vol Shelf) AND 10+ accumulation days before firing STRONG BUY signals. Penalizes setups lacking institutional volume participation. |
| **Micro Edge: Price & Squeeze Validation** | ON | PULLBACK signal only fires if Price > CPR (Central Pivot Range) AND Price > Monthly VWAP AND 20/50 are in squeeze. |

> **Best Practice:** Leave both ON unless you are deliberately stress-testing a setup without edge filters.

#### 3.3.7 Alerts & Visuals
| Toggle | Description |
|--------|-------------|
| Show Buy/Breakout Labels | Triangle labels on chart when signals trigger |
| Show Trade Lines (Entry/Targets) | Horizontal dashed lines for SL, T1, T2 |
| Show % Distance on Trade Lines | Annotates each line with % from current price |
| Mark Fresh Signals (star) | Adds star to signal labels on the first candle only |
| Show Auto-Anchored VWAP | Draws VWAP anchored to the Stage 2 start date |

#### 3.3.8 Dashboard Style
| Setting | Options | Purpose |
|---------|---------|---------|
| Position | Top-Right / Bottom-Right / Top-Left / Bottom-Left | Table location on chart |
| Data Size | Tiny / Small / Normal | Text size for readability |
| Background Color | Color picker | Dashboard background |
| Label Text Color | Color picker | Row label text |
| Value Text Color | Color picker | Data value text |

---

### 3.4 Reading the Dashboard — Row-by-Row Guide

When loaded on a chart, the Dashboard renders a scrollable table with the following sections:

#### SECTION A: Market Climate
| Row | What It Shows | How to Interpret |
|-----|--------------|-----------------|
| **Market State** | BULLISH / CORRECTION / RECOVERY / BEARISH | Only take STRONG BUY in BULLISH. Reduce size in CORRECTION. No new longs in BEARISH. |
| **Stage** | Stage 1-4 with weeks elapsed and nuanced label | See Stage Guide below |
| **30-WMA Slope** | RISING / FLAT / FALLING | Must be RISING for positional trade |
| **Weekly Health** | HEALTHY / NORMAL / WEAK | HEALTHY = Low vol pullback (ideal for entries) |

**Stage Display Labels:**
| Label | Meaning | Action |
|-------|---------|--------|
| STAGE 2 (Full Confluence) | Stage 2 + Above 200DMA + RS Leading | Optimal buy zone |
| STAGE 2 (Weak Leadership) | Stage 2 + Above 200DMA + RS Lagging | Buy with caution, await RS improvement |
| STAGE 2 (Value Zone) | Stage 2 Weekly + Below 200DMA Daily | Deep pullback; aggressive traders only |
| STAGE 2 (Dip Opportunity) | Rising MA; price briefly dipped below | Ideal pullback entry |
| STAGE 1 (Constructive) | Basing + Above 200DMA | Watchlist, approaching breakout |
| STAGE 1 (Dormant) | Basing + Below 200DMA | Skip, too early |
| STAGE 3 (Volatile Churn) | Topping phase | Exit existing; never enter |
| STAGE 4 (Liquidate) | Downtrend | Exit all; never enter |

#### SECTION B: Relative Strength (RS)
| Row | Description |
|-----|-------------|
| **RS vs Nifty 50** | Mansfield RS state vs large-cap benchmark |
| **RS vs Nifty 500** | Mansfield RS state vs broad market benchmark |
| **RS vs Sector** | How the stock performs vs its own sector |
| **Sector Velocity** | ACCELERATING LEADER / EXHAUSTED LEADER / HIDDEN ACCUMULATION / DEAD MONEY |

**RS State Classifications:**
- `Leading (Rising)` -> Stock outperforming, momentum increasing -> **Strongest signal**
- `Weakening (Flat)` -> Outperforming but momentum slowing -> Take partial profits
- `Improving (Flat)` -> Underperforming but recovering -> Watchlist
- `Lagging (Falling)` -> Underperforming and weakening -> Avoid / Exit

#### SECTION C: Daily Technical Health
| Row | Description | Ideal State |
|-----|-------------|-------------|
| **50DMA Slope** | RISING / FLAT / FALLING | RISING |
| **EMA Distance** | % from 20-EMA | 0-5% above = pullback zone |
| **52W Position** | % from 52-week high | Within 10% of 52W high = strong |
| **ATH Distance** | % from all-time high | Closer = stronger |
| **S/R Proximity** | Near Resistance / Support / Mid-Range | Avoid entries near resistance |
| **Overhead Resistance** | # of weekly pivot highs between CMP and ATH | 0-2 = clear path; >5 = blocked |

#### SECTION D: Entry Recommendation
| Row | Description |
|-----|-------------|
| **Recommendation** | STRONG BUY / BUY / PULLBACK / WAIT / AVOID |
| **Setup** | The specific catalyst detected (POS-BO, SWG-PB, etc.) |
| **Trade Style** | POSITIONAL / SWING / BOTH / WAIT |
| **Persona** | LEADER / MOMENTUM / TURNAROUND / VOLATILE / EXTENDED / LAGGARD |

**Recommendation Hierarchy:**
- STRONG BUY -> All edges confirmed: Stage 2 + RS Leading + Vol Shelf + Macro Edge
- BUY -> Core setup valid; one or more edges partially met
- PULLBACK -> In Stage 2, RSI 40-60, near 20-EMA, Volume drying up + Micro Edge
- WAIT -> Setup not complete yet
- AVOID -> Stage 4 or all edges failing

#### SECTION E: Trade Management (Active Position)
Appears only when the current chart matches a Portfolio Slot ticker.

| Row | Description |
|-----|-------------|
| **Entry Price** | Your actual entry from the slot |
| **Stop Loss** | Your hard SL from the slot |
| **Current R** | Profit in units of Risk (e.g., 1.5R = profit = 1.5x your initial risk) |
| **Days Held** | Calendar days since entry date |
| **T1 / T2** | Calculated Target 1 (2R) and Target 2 (3.5R) |
| **Trade Status** | IN PROFIT / AT RISK / NEAR SL / AT BREAKEVEN |

#### SECTION F: Portfolio Summary
| Row | Description |
|-----|-------------|
| **Portfolio Score** | Win/Loss/Stop count across all active slots |
| **Score Grade** | A+ / A / B / C / D / F based on composite technical score |
| **Volume State** | ACCUMULATION / DISTRIBUTION / NEUTRAL |
| **Volume Pattern** | HEALTHY (Low Vol Pullback) / SPIKE / NORMAL |

---

### 3.5 Signal Workflow for the Dashboard (Step-by-Step)

**Step 1: Check Market State**
- If BEARISH -> Stop. No new longs today.
- If CORRECTION -> Only trade pullbacks with 75% of normal position size.

**Step 2: Confirm Stage (Weekly)**
- Must be STAGE 2 (any variant). Skip all other stages.

**Step 3: Check RS**
- RS vs Nifty 500 must be Leading or Weakening (Rising) at minimum.
- RS vs Sector should not be Lagging.

**Step 4: Read the Recommendation**
- STRONG BUY or BUY -> Check entry zone (EMA distance, S/R)
- PULLBACK -> Enter on the close or next open if all conditions met
- WAIT -> Add to watchlist, check again tomorrow
- AVOID -> Remove from consideration

**Step 5: Validate Entry**
- Ensure S/R Proximity = MID-RANGE or NEAR SUPPORT
- Overhead Resistance Count <= 3
- 52W position within 15% of high

**Step 6: Record in Portfolio Slot**
- Add ticker, entry, SL, sector, date to the appropriate slot
- Dashboard auto-tracks from this point

---

<a name="strategy"></a>
## 4. MODULE 2: WEINSTEIN-MINERVINI STRATEGY v4.4

### 4.1 Purpose
The **Strategy v4.4** is a full backtesting engine AND live signal generator. It implements all 6 catalyst types with precise position sizing, trailing stops, time-decay exits, and an integrated Risk Allocator table. Use it to:
- **Backtest** the hybrid system on any stock/ETF/timeframe
- **Get live entry/SL/target signals** for active trading
- **Validate** a setup before committing capital

### 4.2 Placing on Chart
- Set TradingView chart to **Daily timeframe** (most accurate for the hybrid system)
- The strategy supports Weekly and Intraday via dynamic Chandelier Exit parameter switching

### 4.3 Input Groups — Complete Reference

#### 4.3.1 Master Configuration
| Setting | Options | Recommended | Purpose |
|---------|---------|-------------|---------|
| **Strategy Mode** | Breakout Only / Pullback Only / Hybrid (Both) | Hybrid (Both) | Which catalyst types to trade |
| **Asset Type** | Auto / ETF / Stock | Auto | Determines position sizing. Auto detects ETFs via syminfo.type |

> **How Auto works:** Auto checks TradingView's syminfo.type == "fund" flag. If true -> ETF risk %. If false -> Stock risk %. Override to ETF or Stock if the auto-detect is wrong for your instrument.

#### 4.3.2 Portfolio & Risk
| Setting | Default | Range | Purpose |
|---------|---------|-------|---------|
| Total Portfolio Capital | 100000 | Your actual capital | Base for position sizing calculations |
| ETF Risk % | 1.0% | 0.5-2.0% | Max loss per ETF trade as % of portfolio |
| Stock Risk % | 0.75% | 0.25-1.5% | Max loss per Stock trade as % of portfolio |
| Max Allocation per Trade | 25000 | <= 25% of capital | Hard cap on single trade capital |
| Time Stop (Days Stagnant) | 10 | 5-20 | Exit trades with <0.5R gain after N days |

> **Risk Math Example:**
> Portfolio = 100000 | Stock Risk = 0.75% -> Risk Amount = 750
> Stock at 500, SL at 475 -> Risk per share = 25
> Shares to buy = 750 / 25 = **30 shares** (capped at Max Allocation / price)

#### 4.3.3 Kelly Fraction Probability Sizing
| Setting | Default | Effect |
|---------|---------|--------|
| **Use Kelly Fraction?** | ON | Dynamically scales risk % up or down based on setup quality |

**Kelly Multiplier Logic:**
| Conditions Met | Kelly Multiple | Explanation |
|----------------|----------------|-------------|
| Stage 2 + RS Leading + Volume > avg | 1.25x | High-prob setup -> trade bigger |
| Two of three conditions above | 1.0x | Standard risk |
| One or zero conditions | 0.75x | Weak setup -> trade smaller |

#### 4.3.4 Strategy A: Weinstein Positional Settings
| Setting | Default | Purpose |
|---------|---------|---------|
| [EDGE] Stage 2 Breakout | ON | Enables positional breakout entries |
| [EDGE] Smart Money Accumulation (OBV) | ON | Enables OBV divergence entries |
| Breakout Lookback (Days) | 20 | How many days high to watch for breakout |
| Max Stage 2 Duration (Weeks) | 20 | Skip entries if stock has been in Stage 2 too long (extended) |
| Max Breakout/Gap Extension (%) | 5.0% | Don't enter if price already >=5% above breakout level |
| Breakout Confirmation | Daily Close | Use "Daily Close" (stricter, fewer false signals); "High/Touch" = more aggressive |
| Global ATR Length | 14 | ATR period for stop calculations |

#### 4.3.5 Mathematical Edges (Backtested)
| Edge | Default | Effect |
|------|---------|--------|
| **Macro Edge: Institutional Vol Bias** | ON | Entry only if VWMA(50) > SMA(50) AND vol accumulation in last 10 days |
| **Micro Edge: Price & Squeeze Validation** | ON | Entry only if Price > CPR (Central Pivot Range top) AND > Monthly VWAP AND in MA squeeze |
| **SMC Liquidity Sweep Filter** | ON | Boosts confidence when 50MA was swept intrabar then reclaimed |

#### 4.3.6 Strategy B: Hybrid Swing Engine
| Setting | Default | Purpose |
|---------|---------|---------|
| [EDGE] Pullback / Moving Avg Bounce | ON | EMA20 bounce entries |
| [EDGE] Momentum Breakout (VCP) | ON | VCP pivot breaks |
| [EDGE] Mean Reversion (Oversold) | ON | RSI-3 < 20 bounce entries |
| [EDGE] Gap & Go | ON | 4%+ gap up entries |
| Daily RSI Pullback Pocket Min/Max | 40/60 | RSI must be in [40,60] for pullback entries |
| Weekly RSI Momentum Min | 60 | Weekly RSI must be above 60 for swing pullbacks |
| Daily EMA Length | 20 | The anchoring moving average for pullbacks |
| EMA Zone Tolerance (%) | 1.5% | Price must touch EMA +/- 1.5% to be in pullback zone |
| Max Pullback Depth (%) | 15% | Reject pullbacks deeper than 15% from swing high |
| **Use Dynamic R:R Targets?** | ON | T1 = 2.5R in bull market, 2.0R in bear market |
| Pullback Target 1 R:R (Static) | 2.0 | Used when Dynamic R:R is OFF |

#### 4.3.7 Shared Filters
| Setting | Default | Purpose |
|---------|---------|---------|
| Use Relative Strength Filter? | ON | Requires RS > 0 vs Nifty 500 AND sector |
| Auto-Detect Sector? | ON | Automatically maps to correct sector index |
| Manual Sector Override | NSE:BANKNIFTY | Used only if Auto-Detect is OFF or wrong |

#### 4.3.8 Core Mechanics (Dashboard Synced)
| Setting | Default | Purpose |
|---------|---------|---------|
| Est. Pullback Lookback (Days) | 21 | Fibonacci swing calculation window |
| Trailing Stop ATR Multiplier (Base) | 3.0 | Chandelier Exit multiplier |
| Adaptive TSL: Tighten Trigger (R) | 1.5 | When to tighten the trailing stop |
| Adaptive TSL: Tightening Ratio | 0.75 | Multiply ATR by 0.75x when 1.5R hit |
| Adaptive TSL: Super-Tight Trigger (R) | 3.0 | When to tighten even further |
| Adaptive TSL: Super-Tight Ratio | 0.50 | Multiply ATR by 0.50x when 3.0R hit |

#### 4.3.9 Backtest Period
| Setting | Default | Purpose |
|---------|---------|---------|
| Filter Date Range? | OFF | Enable to restrict backtests to a specific period |
| Start Date | 1 Jan 2020 | Backtest start date |
| End Date | 1 Jan 2025 | Backtest end date |

#### 4.3.10 Risk Allocator (Manual)
| Setting | Purpose |
|---------|---------|
| Show Allocator Table? | Toggle the on-chart position sizing table |
| Entry Price (Set from chart) | Your planned entry; set with confirm dialog |
| Stop Price (Set from chart) | Your planned stop; set with confirm dialog |
| Lot Multiplier | For F&O use (e.g., 50 for NIFTY lots); keep at 1 for equity |
| Table Position | Where the allocator table appears on chart |

---

### 4.4 Reading the Risk Allocator Table
The table appears bottom-right and auto-populates from:
1. **Manual inputs** (if Entry/Stop > 0)
2. **Live algo signal** (if a signal just triggered and manual inputs = 0)
3. **Open trade** (if a trade is already active, shows live trailing numbers)

| Row | Content | Notes |
|-----|---------|-------|
| Asset Type | ETF / Stock | Drives risk % selection |
| Entry | Planned entry price | |
| Stop | Planned stop price | Red text |
| Adjusted Risk % | Dynamic risk after volatility & Kelly | Orange text |
| **Quantity** | Shares to buy | **Yellow, large text — the key number** |
| Invested | Total capital deployed | |
| Risk Amount | Amount at stake for this trade | |
| Target 1 (xR) | First profit target | Green |
| Target 2 (xR) | Runner target | Lime |
| Trade Validation | Clear Room to T1 or T1 > Overhead Resistance | Orange warning if blocked |

---

### 4.5 Strategy Exit Logic (Complete)

#### Positional Exits (POS-BO, POS-ACCUM)
1. **Chandelier Exit Trailing Stop**: Ratchets upward as price rises; never moves down. Multiplier: 3.0x ATR(22). Tightens to 2.25x at 1.5R profit, 1.5x at 3.0R profit.
2. **Stage 4 Exit**: Immediate close on Stage 4 detection (weekly level)
3. **Time-Decay Exit**: Close if holding >10 days with <0.5R profit

#### Swing Exits (SWG-PB, SWG-BO, SWG-REV, SWG-GAP)
1. **20-EMA Trailing Stop**: Trail stop just below 20-EMA x (1 - trail buffer 1%)
2. **50MA Fail Exit**: Immediate close if daily close drops below 50-DMA
3. **Mean Reversion Time Stop**: Hard 5-day exit for SWG-REV trades
4. **T1 Partial Profit**: At Target 1, close 50% of position and set stop to breakeven
5. **Time-Decay Exit**: Same as Positional — exit if stagnant

---

<a name="zigzag"></a>
## 5. MODULE 3: WEINSTEIN SWING ZIGZAG STRICT v6.0

### 5.1 Purpose
The **Swing Zigzag** visualizes pure market structure — Higher Highs (HH), Higher Lows (HL), Lower Lows (LL), Lower Highs (LH) — using confirmed pivot points. It answers: **"Is the stock in a valid uptrend structure?"** before you enter.

### 5.2 Installation & Recommended Usage
- Apply on **Daily or Weekly** chart of the candidate stock
- Best paired **alongside** the Dashboard (dual-indicator setup)
- Use Weekly chart for positional trades, Daily for swing trades

### 5.3 Input Groups — Complete Reference

#### 5.3.1 MTF Pivot Settings
| Setting | Default | Purpose |
|---------|---------|---------|
| Monthly Pivot Length | 1 | Bars left/right for monthly pivots |
| Weekly Pivot Length | 5 | Key setting: 5 weeks left, 5 right for confirmed weekly pivots |
| Daily Pivot Length | 2 | 2 days left, 2 right for daily pivots |
| Intraday Pivot Length | 2 | For intraday analysis |

> The indicator **auto-selects** the correct pivot length based on chart timeframe. You don't need to change these unless you want to fine-tune sensitivity.

#### 5.3.2 Display Settings
| Setting | Default | Purpose |
|---------|---------|---------|
| Show Trend State Panel | ON | Displays the info panel |
| Show Projection Line | ON | Shows live trend projection from current pivot |
| Panel Position | Top Right | Where the info panel appears |
| Choppiness Lookback (weeks) | 52 | Rolling window for counting direction flips |

#### 5.3.3 Fibonacci Levels
| Setting | Default | Purpose |
|---------|---------|---------|
| Show 50% & 61.8% Retracement | ON | Draws Fib levels for the current swing |
| Extend Lines (bars right) | 20 | How far right Fib lines extend |

> **Fib Line Colors:**
> - Purple = 50% retracement level
> - Orange = 61.8% retracement level
> - **Solid** = Actionable (uptrend or BoS confirmed)
> - **Dotted** = Reference only (downtrend, price below locked high)

#### 5.3.4 Major / Minor Pivot Settings
| Setting | Default | Purpose |
|---------|---------|---------|
| Major Pivot Mode | Auto | Auto-detects ETF (>=4% swing) vs Stock (>=8% swing) |
| Custom Threshold (%) | 8.0% | Used only if Mode = "Custom" |

> **Major pivots** draw with **thick (width 3) lines** and normal-size labels.
> **Minor pivots** draw with **thin (width 1) lines** and small labels.

---

### 5.4 Reading the Zigzag — Chart & Panel Guide

#### Chart Visuals
| Visual | Meaning |
|--------|---------|
| **Green lines** | HH after HL (confirmed uptrend leg) |
| **Red lines** | LH after LL (confirmed downtrend leg) |
| **White/faded lines** | Mixed structure (broadening / sideways) |
| **Dotted gray horizontal** | Lock line marking the confirmed pivot level |
| **Dashed projection line** | Current unconfirmed swing direction |
| Labels: HH (+12.3%) | Higher High, X% gain from prior low |
| Labels: HL (-5.1%) | Higher Low, X% pullback from prior high |

#### Trend State Panel
```
+-------------------------------------+
| TREND    | UPTREND                  |
| STRUCTURE| HH / HL                 |
| SWING COUNT| 4 swing(s)            |
| AMPLITUDE | 23.5%                  |
| CHOPPINESS| 3 flips / 52W          |
| CONFIG   | Pivot: L=5 R=5          |
+-------------------------------------+
```

| Field | Interpretation |
|-------|----------------|
| **TREND** | Current confirmed trend: UPTREND / DOWNTREND / SIDEWAYS |
| **STRUCTURE** | Last confirmed pivot pair (e.g., HH/HL = healthy uptrend) |
| **SWING COUNT** | Number of consecutive swings in current trend direction |
| **AMPLITUDE** | % change from locked low to locked high (size of the move) |
| **CHOPPINESS** | # of direction flips in last N weeks. <=4 = Trending (green), 5-8 = OK (yellow), >8 = Choppy (red) |
| **CONFIG** | Active pivot length (auto-selected) |

#### Pivot Classification Logic
| Pivot | Prior Pivot | Trend Signal  |
|-------|-------------|---------------|
| HH (Higher High) | HL (Higher Low) | Uptrend confirmed |
| LH (Lower High) | LL (Lower Low) | Downtrend confirmed |
| HL (Higher Low) | HH (Higher High) | Uptrend continuation |
| LL (Lower Low) | LH (Lower High) | Downtrend continuation |
| HH after LL | — | Broadening (avoid) |
| EH (Equal High) | — | Sideways indecision |
| EL (Equal Low) | — | Sideways indecision |

---

### 5.5 Using Fib Levels for Entry Timing
The Zigzag draws Fibonacci retracement from the **current swing low -> current swing high** in real time.

**For Swing Trades (Long):**
- 50% retracement (purple line) = Ideal pullback entry zone
- 61.8% retracement (orange line) = Deep pullback entry (aggressive)
- Entry rule: Price must bounce from zone WITH a reversal candle (hammer/engulfing)

**Validation:**
- Fib lines are **solid** = trend is up or BoS confirmed -> levels are actionable
- Fib lines are **dotted** = trend is down, no BoS -> levels are reference only, do not enter

---

### 5.6 Break of Structure (BoS) Alerts
The indicator fires two alert conditions automatically when activated via TradingView Alert System:

| Alert | Trigger | Action |
|-------|---------|--------|
| **Bullish BoS** | Price closes above locked high for first time | Alert on phone — check for entry |
| **Bearish BoS** | Price closes below locked low for first time | Alert on phone — check for exit |
| **Uptrend Confirmed** | Pivot structure officially transitions to HH+HL | Confirm with Dashboard before acting |
| **Downtrend Confirmed** | Pivot structure officially transitions to LH+LL | Start reducing exposure |

---

<a name="fundamental"></a>
## 6. MODULE 4: WEINSTEIN FUNDAMENTAL X-RAY v2.1

### 6.1 Purpose
The **Fundamental X-Ray** provides a comprehensive fundamental quality check — Minervini's 8-point growth scorecard, full financial data panel, and the new 17-point Overall Fundamental Rating. Use this after technical setup validation to confirm the business deserves your capital.

### 6.2 Installation
- Apply on the **candidate stock's daily chart**
- Works for **NSE-listed Indian stocks** (uses request.financial with Indian accounting conventions)
- Data updates every time a new quarterly/annual report is published by the company

### 6.3 Understanding the Data Sources

All financial data is fetched directly from TradingView's request.financial() function. There are two reporting periods used:

| Code | Meaning |
|------|---------|
| **FQ** | Latest reported Fiscal Quarter (most recent 3-month data) |
| **TTM** | Trailing Twelve Months (annualized; preferred for profitability ratios) |

> **YoY Growth Approximation**: The indicator compares current quarter vs. 252 bars ago (approx 1 trading year) for YoY calculations. This is a TradingView constraint — native prior-year comparison is unavailable.

---

### 6.4 Input Groups

#### 6.4.1 UI Settings
| Setting | Default | Options | Purpose |
|---------|---------|---------|---------|
| Show Data Table | ON | ON/OFF | Toggle entire panel |
| Table Position | Bottom Right | 9 positions | Where on chart |
| Text Size | Small | Tiny/Small/Normal/Large/Auto | Readability |
| Spacer Rows | 0 | 0-50 | Add blank rows below table for stacking with other indicators |
| Background Color | Dark Navy | Color picker | |
| Text Color | Light Blue-Gray | Color picker | |
| Healthy Color | Green | Color picker | Metrics in healthy range |
| Warning Color | Amber | Color picker | Metrics in borderline range |
| Danger Color | Red | Color picker | Metrics in poor range |
| Border Color | Dark Blue | Color picker | |

---

### 6.5 Reading the Dashboard — Section by Section

#### SECTION 1: MACRO & CLIMATE
Live macroeconomic context fetched directly from TradingView:

| Row | Metric | Green Signal | Red Signal |
|-----|--------|-------------|------------|
| India 10Y Yield | Current yield + trend | FALLING | RISING |
| USD/INR | Current rate + trend | STRENGTHENING | WEAKENING |
| CNX500 Trend | Broad market health | STRONG UPTREND | DOWNTREND |
| Sector | Stock's sector | Yellow = informational | — |

> **Why Yields Matter:** Falling bond yields make equities relatively more attractive. A strengthening INR signals Foreign Institutional Investor (FII) inflows favorable to Indian markets.

#### SECTION 2: MOMENTUM (Revenue & Earnings Growth)
| Row | Metric | Threshold | Color Scale |
|-----|--------|-----------|-------------|
| Market Cap | Total market cap (INR format) | — | Reference |
| Revenue (TTM) | Annual turnover | — | Reference |
| Rev Growth (YoY) | Quarterly revenue vs year-ago | >20% green, >0% amber, <0% red |
| NI Growth (YoY) | Quarterly net income vs year-ago | >25% green, >0% amber, <0% red |
| Net Income (TTM) | Trailing 12M net profit | >0 green, <0 red |
| EPS Diluted (FQ) | Latest quarter EPS | >0 green, <0 red |
| EPS Growth (YoY) | EPS vs year-ago quarter | >25% green, >0% amber, <0% red |
| Earnings Acceleration | Sequential QoQ growth accelerating? | YES green, NO red |

> **Key Minervini Insight:** Both Revenue AND Earnings must grow >20-25% YoY. Earnings Acceleration (Q3 growth rate > Q2 growth rate) is especially powerful for identifying stocks about to make major moves.

#### SECTION 3: MARGINS (TTM)
| Row | Metric | Green | Amber | Red |
|-----|--------|-------|-------|-----|
| Gross Margin | (Gross Profit / Revenue) x 100 | >30% | 15-30% | <15% |
| EBITDA Margin | (EBITDA / Revenue) x 100 | >20% | 10-20% | <10% |
| Operating Margin | (Op Income / Revenue) x 100 | >15% | 0-15% | <0% |
| ROE (TTM) | Return on Equity (annualized) | >20% | 12-20% | <12% |
| ROA (TTM) | Return on Assets (annualized) | >10% | 5-10% | <5% |

#### SECTION 4: HEALTH & VALUE
| Row | Metric | Green | Amber | Red |
|-----|--------|-------|-------|-----|
| Debt/Equity | Total Debt / Total Equity | <0.5x | 0.5-1.5x | >1.5x |
| Current Ratio | Current Assets / Current Liabilities | >2.0x | 1.0-2.0x | <1.0x |
| FCF (TTM) | Free Cash Flow = OCF minus CapEx | Positive | — | Negative |
| P/E Ratio | Price / TTM EPS | <25x | 25-50x | >50x or negative |
| P/B Ratio | Price / Book Value per Share | <1.5x | 1.5-5.0x | >5.0x |

#### SECTION 5: MINERVINI FUNDAMENTAL SCORE (0-8)
Eight binary pass/fail criteria. Thresholds are minimum bars — the **display colors** reflect quality:

| Criterion | Pass Threshold | Score |
|-----------|----------------|-------|
| Revenue Growth > 20% | YoY Rev > 20% | +1 |
| NI Growth > 25% | YoY Net Income > 25% | +1 |
| Accelerating EPS | Current Q growth > prior Q growth | +1 |
| ROE > 15% | ROE TTM > 15% | +1 |
| Gross Margin > 15% | Gross Margin TTM > 15% | +1 |
| D/E < 1.5 | Debt/Equity < 1.5x | +1 |
| Current Ratio > 1.0 | Current Assets / Current Liabilities > 1.0 | +1 |
| FCF Positive | Free Cash Flow TTM > 0 | +1 |

**Star Scale:**
| Score | Stars | Color |
|-------|-------|-------|
| 7-8 | 5 Stars | Green |
| 5-6 | 4 Stars | Green |
| 3-4 | 3 Stars | Amber |
| 1-2 | 2 Stars | Red |
| 0 | 0 Stars | Red |

#### SECTION 6: OVERALL FUNDAMENTAL RATING (0-17)
A holistic composite score across four domains with **stricter thresholds** than the Minervini 8-pt score:

| Domain | Max Points | Criteria |
|--------|-----------|---------|
| **Macro** | 3 | CNX500 Strong Uptrend (+1) · Yield Falling (+1) · INR Strengthening (+1) |
| **Momentum** | 5 | Rev YoY>20% · NI YoY>25% · EPS YoY>25% · Accelerating · Net Income Positive |
| **Margins** | 4 | Gross>30% · EBITDA>20% · Op Margin>15% · ROE>20% |
| **Health & Value** | 5 | D/E<1.0 · CR>1.5 · FCF>0 · P/E<40 · P/B<5.0 |

**Grade Scale:**
| Score | Grade | Meaning |
|-------|-------|---------|
| 15-17 | A+ EXCEPTIONAL | Institutional-grade quality |
| 12-14 | A STRONG | Excellent fundamentals |
| 9-11 | B GOOD | Solid, tradeable quality |
| 6-8 | C FAIR | Acceptable; watch carefully |
| 3-5 | D WEAK | Avoid for positional trades |
| 0-2 | F POOR | Never trade — avoid completely |

---

### 6.6 Fundamental Screening Rules

**Minimum requirements for a Positional Trade:**
- Minervini Score >= 5 (4+ Stars)
- Overall Rating >= B (score >= 9)
- ROE >= 15%, Revenue Growth >= 15%, FCF Positive
- D/E Ratio < 1.5x

**Minimum for a Swing Trade:**
- Minervini Score >= 3 (3+ Stars)
- Overall Rating >= C (score >= 6)
- FCF Positive preferred but not mandatory

**Red Flags (Never Trade):**
- Negative net income with D/E > 2.0x
- Earnings deceleration for 2+ consecutive quarters
- FCF negative AND high debt
- P/E > 80x in a bearish macro environment

---

<a name="ultimate"></a>
## 7. MODULE 5: COMMANDER SCREENER DASHBOARD ULTIMATE v3.5

### 7.1 Purpose
The **Ultimate Screener** is a **multi-stock batch analysis tool** that simultaneously analyzes up to **30 stocks** and ranks them by your chosen criteria. Use it to scan a watchlist, compare a sector's constituents, or rank your portfolio candidates in one view.

### 7.2 Installation
- Apply on **any chart** (the underlying chart symbol is irrelevant — the screener uses the ticker list)
- Best used on a **blank or index chart** (e.g., NSE:NIFTY) so the screener table is unobstructed

### 7.3 Input Groups

#### 7.3.1 Watchlist Symbols
- **Input type**: Text area (multi-line supported)
- **Format**: Comma-separated tickers, e.g.: `NSE:RELIANCE, NSE:TCS, NSE:INFY`
- **Maximum**: 30 tickers (adds beyond 30 are ignored)
- **Exchange prefix**: NSE: or BSE: required for proper data fetching

> **TIP:** To quickly populate 30 tickers, paste from a CSV file. The parser automatically trims spaces.

#### 7.3.2 Ranking & Table Config
| Setting | Options | Purpose |
|---------|---------|---------|
| Benchmark (For RS) | NSE:NIFTY | Benchmark for Mansfield RS calculation |
| **Rank/Sort By** | Score/Grade, Volume Thrust, Proximity to 52-Wk High, Proximity to 50-SMA, Relative Strength (Qtr) | Primary sort criterion |
| Sort Direction | Descending (Best to Worst) / Ascending (Worst to Best) | Sort order |
| Table Position | 9 positions | Where the table renders on chart |

---

### 7.4 Column Reference — The 16-Column Table

The table renders a **Market Health Banner** at top, then a header row, then one row per stock sorted by your ranking.

#### Banner Row
```
COMMANDER SCREENER | Market: BULLISH (Confirmed) | Bench: NSE:NIFTY
```

#### Column Definitions

| # | Column | Values | Color Guide |
|---|--------|--------|-------------|
| 0 | **RANK** | 1, 2, 3... | Row background: Green (S2-UP), Gold (S1), Orange (S3), Red (S4) |
| 1 | **TICKER** | Stock name | White text |
| 2 | **SCORE** | Stars + number + Grade | Stars color = lime (80+), yellow (60+), orange (40+), red (<40) |
| 3 | **STAGE** | STAGE 2 (UP) / STAGE 1 (BASE) etc | White |
| 4 | **STG WKS** | 12W, 5W | Days in current stage |
| 5 | **RS / SEC RS** | LEADING / Sec: BEAT | Teal=leading, red=lagging |
| 6 | **50D SLOPE** | Rising / Flat / Falling | Green=rising, red=falling |
| 7 | **VOLATILITY** | SQUEEZE / Normal / Expanded | Green=squeeze (ideal) |
| 8 | **VOL%** | 185% | Green=150%+ (thrust), amber=120-150% |
| 9 | **ATH DIST%** | -3.5% | Green=within 5% of ATH |
| 10 | **50SMA DIST%** | +8.2% | Green=above 50SMA |
| 11 | **RSI** | 58.3 / 72.1 (OB) | Red=overbought (>70) |
| 12 | **TRADE** | ACTIVE / BLOCKED / AVOID / WAIT | Color-coded by action |
| 13 | **CATALYST** | POS-BO / SWG-PB / NONE etc | Color by catalyst type |
| 14 | **STYLE** | BOTH / POS / SWING / WAIT | Gold=both, blue=positional |
| 15 | **PERSONA** | LEADER / MOMENTUM / TURN / LAGGARD | Color-coded |

---

### 7.5 Scoring Engine (0-100)

The Score is calculated from six weighted components:

| Component | Score Added | Condition |
|-----------|-------------|-----------|
| Stage 2 (UP) | +25 | Stateful stage machine confirms Stage 2 above 150SMA |
| Stage 1 (BASE) | +10 | Stage 1 basing |
| RS Leading | +15 | Mansfield RS slope > 0.02 |
| RS Improving | +5 | RS slope neutral but value positive |
| 50DMA Rising & Aligned | +10 | Slope > threshold AND 50 > 150 > 200 |
| 50DMA Rising (not aligned) | +5 | Slope > threshold only |
| Alpha Performance (Q3 + H1) | +20 | Stock Q3 alpha > 20% AND H1 alpha > 30% vs benchmark |
| Alpha Performance (partial) | +10 | Q3 alpha > 10% AND H1 alpha > 15% |
| Alpha Negative | -10 | Either Q3 or H1 negative alpha |
| Volume Thrust | +10 | Volume > 150% of 50-day average |
| RSI 50-70 | +5 | RSI in healthy trending zone |
| VCP Squeeze | +10 | ATR(10) < ATR(40) x 0.70 (volatility contraction) |
| SMC Liquidity Sweep | +20 | 50MA swept intrabar, reclaimed with volume |
| Vol Shelf (VWMA>SMA) | +5 | Institutional volume participation confirmed |

**Score-to-Grade:**
| Score | Grade | Trade Action |
|-------|-------|-------------|
| 80-100 | A (Stage 2 full alignment) | STRONG BUY |
| 60-79 | B | BUY |
| 40-59 | C (Stage 1) | WATCHLIST |
| 20-39 | D | AVOID |
| 0-19 | D/F | AVOID / SHORT |

---

### 7.6 Trade Column — Understanding ACTIVE vs BLOCKED

- **ACTIVE** -> Setup has a valid T1 target with clear overhead room. Shows T1 and SL prices.
- **BLOCKED** -> T1 target is above the 52W high or overhead resistance. Trade has poor RR.
- **AVOID** -> Stage 4 confirmed or grade D
- **WAIT** -> No active catalyst detected

---

### 7.7 Catalyst Decode

| Catalyst Code | Full Name | Meaning |
|---------------|-----------|---------|
| POS-ACCUM | Positional Accumulation (OBV divergence) | Institutional loading while price lags |
| POS-BO | Positional Breakout (52W high touch) | Breaking out from Stage 1 base |
| SWG-PB | Swing Pullback (EMA bounce) | EMA20 pullback in Stage 2 |
| SWG-BO | Swing Breakout (VCP pivot) | VCP breakout with volume |
| SWG-REV | Swing Mean Reversion (RSI-3 < 20) | Extreme oversold bounce |
| SWG-GAP | Swing Gap & Go (4%+ gap) | Institutional gap up |
| NONE | No active catalyst | Wait for setup |

---

### 7.8 Sector RS Column
The second line in the RS column shows sector relative performance:
- `BEAT` -> Stock outperforming its own sector (best signal)
- `N+` -> Neutral-positive vs sector
- `N-` -> Neutral-negative vs sector
- `LAGGING` -> Underperforming its own sector

---

<a name="beta"></a>
## 8. MODULE 6: COMMANDER SCREENER BETA EDITION v2.2

### 8.1 Purpose
The **Beta Edition** is a **single-stock deep-dive screener** that outputs **26 precisely calibrated data columns** visible in TradingView's Data Window and Stock Screener's Custom Columns. Unlike the Ultimate Screener (which shows a table), the Beta Edition **plots data as invisible series** — making it compatible with TradingView's Screener tool.

### 8.2 Installation for TradingView Screener
1. **Add the indicator** to any chart
2. In TradingView **Screener**, add a new screening condition -> select "Custom" -> choose Weinstein Beta Edition output columns
3. Sort and filter your entire watchlist by Score, Catalyst, Stage, and more

### 8.3 Key Differences from Ultimate Screener

| Feature | Ultimate v3.5 | Beta v2.2 |
|---------|----------------|-----------|
| Stocks per view | Up to 30 simultaneously | Single stock |
| Display type | Visual table on chart | Data Window / Screener columns |
| Use case | Quick batch ranking | Deep single-stock detail + Screener filtering |
| Sector RS | Pre-fetched 8 indices | Auto-detected via keyword mapper |
| Stage engine | Stateful hysteresis (daily proxy) | Stateful hysteresis (direct weekly request) |
| Anti-algo gate | In Ultimate engine only | SWG-BO only (independent filter) |

### 8.4 Input Groups — Strategy Inputs (Tuning Parameters)
These should **stay in sync** with the Dashboard v63.0 values for consistent signals:

| Setting | Default (Keep Synced With Dashboard) |
|---------|--------------------------------------|
| Weinstein SMA Length (Weekly) | 30 |
| 30 WMA Slope Lookback (Weeks) | 4 |
| 30WMA Slope Threshold (Flat) | 0.0005 |
| Benchmark (Nifty 50) | NSE:NIFTY |
| Benchmark (Nifty 500/Breadth) | NSE:CNX500 |
| Mansfield RS Length | 26 weeks |
| RS Slope Lookback (Weeks) | 8 |
| 50 DMA Length | 50 |
| 150 DMA Length | 150 |
| 200 DMA Length | 200 |
| 50DMA Slope Lookback (Days) | 21 |
| Slope Flat Threshold (Daily) | 0.0005 |
| **Macro Edge: Institutional Vol Bias** | ON |

---

### 8.5 Data Window Columns — All 26 Outputs

The Beta Edition outputs these plots to TradingView's Data Window:

| Column | Range | Meaning |
|--------|-------|---------|
| **Alpha Score** | 0-100+ | Raw composite momentum quality score |
| **Dashboard Quality Score** | 0-100 | Stage-weighted overall score |
| **Alpha Stars (0-5)** | 0-5 | Quick 5-star ranking (score / 20) |
| **Confluence (0-6 Stars)** | 0-6 | Price/Volume/EMA/RSI/ADX confluence |
| **Stage (1/2.0/2.1/3/4)** | 1.0, 2.0, 2.1, 3.0, 4.0 | Numeric stage for screener filtering |
| **Persona (0-5)** | 0=Lag, 2=Vol, 3=Turn, 4=Mom, 5=Lead | Stock personality classification |
| **Style (0-3)** | 0=Wait, 1=Pos, 2=Swing, 3=Both | Optimal trade style |
| **Catalyst (0-6)** | 0=None...6=Gap | Active catalyst ID |
| **Recommended SL Price** | Price | Algorithm-calculated stop loss |
| **Distance to SL (%)** | % | SL distance from current price |
| **Target 1 (2.0R)** | Price | First profit target |
| **Target 2 (3.0R)** | Price | Runner profit target |
| **Warn: T1 Hits Resistance** | 0 or 1 | 1 = T1 is blocked by overhead resistance |
| **Signal: True Breakout** | 0 or 1 | 1 = POS-BO signal active |
| **Signal: Pullback Hit** | 0 or 1 | 1 = SWG-PB signal active |
| **Minervini Trend Template** | 0 or 1 | 1 = Full Minervini criteria met |
| **RS Value (vs Nifty 50)** | Float | Raw Mansfield RS vs Nifty 50 |
| **RS Value (vs Nifty 500)** | Float | Raw Mansfield RS vs Nifty 500 |
| **Sector RS Value** | Float | Raw Mansfield RS vs sector |
| **Vol Shelf (VWMA50>SMA50)** | 0 or 1 | 1 = Institutional vol participation |
| **Daily Trend** | 1 or -1 | 1 = bullish daily |
| **Weekly Trend** | 1 or -1 | 1 = bullish weekly |
| **Current Price** | Price | Live close |
| **Distance to 20 EMA (%)** | % | EMA proximity (+/-2% = in pullback zone) |
| **Relative Volume (x-avg)** | Multiplier | Volume vs 50-day average |
| **Anti-Algo SWG-BO Gate** | 0 or 1 | 1 = Breakout passed quality filter |

---

### 8.6 Using Beta Edition in TradingView Screener

**Recommended Filter Combinations:**

**Strong Buy Pre-filter:**
```
Stage = 2.1 (UP) AND Catalyst > 0 AND Dashboard Score >= 60 AND T1 Resistance = 0
```

**Pullback Opportunity:**
```
Signal: Pullback Hit = 1 AND Weekly Trend = 1 AND Stage >= 2.0 AND Vol Shelf = 1
```

**Positional Breakout:**
```
Signal: True Breakout = 1 AND Minervini Template = 1 AND Vol Shelf = 1 AND Alpha Stars >= 4
```

---

<a name="workflow"></a>
## 9. THE COMPLETE TRADING WORKFLOW (END-TO-END)

### 9.1 Weekly Workflow (Every Weekend — Sunday)

```
STEP 1: MARKET HEALTH CHECK (15 minutes)
  - Open NSE:CNX500 on Daily chart
  - Check: Is price > 50DMA AND 50DMA > 200DMA?
      YES: BULLISH — Full position sizing, all strategies active
      NO: Check if correction (price < 50DMA but 50DMA > 200DMA)
          YES: CORRECTION — 75% position size, pullbacks only
          NO: BEARISH — No new longs, maintain stops on existing

STEP 2: SECTOR ROTATION SCAN (20 minutes)
  - Open each sector index (BANKNIFTY, CNXMETAL, CNXIT, CNXPHARMA, CNXENERGY, CNXAUTO)
  - For each sector: Check Stage (v63 Dashboard) and RS trend
  - Create shortlist: Sectors in Stage 2 with Rising RS = Priority sectors

STEP 3: WATCHLIST SCREENING WITH ULTIMATE v3.5 (30 minutes)
  - Load 30 stocks from priority sectors into Ultimate Screener
  - Sort by: Score/Grade (Descending)
  - Filter: Stage 2 (UP) only + Score >= 40
  - Note: Top 10 candidates for further analysis

STEP 4: FUNDAMENTAL VALIDATION (20 minutes)
  - For each top candidate: Open stock chart + load X-Ray v2.1
  - Minimum check: Minervini Score >= 5/8 AND Overall Grade >= B
  - Red flag check: D/E > 1.5 OR FCF < 0 — Remove from list

STEP 5: STRUCTURE VALIDATION WITH ZIGZAG v6.0 (15 minutes)
  - For each fundamental-passing candidate: Load Zigzag on weekly chart
  - Check: Trend = UPTREND AND Structure = HH/HL
  - Check: Choppiness <= 4 flips/52W (trending, not choppy)
  - Check: Swing count >= 2 (trend has legs, not a single spike)

STEP 6: UPDATE PORTFOLIO SLOTS (10 minutes)
  - In Dashboard v63.0: Update any slots needed (price changes, new trades)
  - Review all open positions: R-multiple, days held, approaching stops
  - Set alerts via Zigzag's BoS alerts for watchlist candidates
```

### 9.2 Daily Workflow (Every Evening Before Close — 3:15 PM IST)

```
STEP 1: MARKET PULSE (5 minutes)
  - Dashboard: Check mktState — any change from yesterday?
  - If state worsened: Reduce existing positions, tighten stops

STEP 2: DASHBOARD CHECK ON OPEN POSITIONS (10 minutes)
  - For each active portfolio slot:
      - How many R is the trade (1.5R = consider partial exit)?
      - Is trade status NEAR SL or AT RISK? Tighten stop or reduce
      - Did Stage flip to 3 or 4? Plan exit
      - Are Target 1/2 levels visible on chart?

STEP 3: WATCHLIST CATALYST CHECK (10 minutes)
  - For each watchlist candidate: open chart with Beta Edition v2.2
  - Did any catalyst activate today? (Catalyst column > 0)
  - Is Catalyst + Stage 2 + RS Leading all active simultaneously?
      YES: Prepare entry order for next session

STEP 4: ENTRY EXECUTION PROTOCOL
  - Open Strategy v4.4 on the candidate's chart
  - Risk Allocator shows: Entry, SL, Qty, T1, T2
  - Validate: Trade Validation = Clear Room to T1?
      YES: Place limit or market order at next open
      NO: BLOCKED — skip this setup, wait for better entry

STEP 5: ORDER MANAGEMENT
  - For new entries: Set GTT stop loss order at SL price
  - AT 1.5R profit: Move stop to breakeven, peel 25% position
  - AT T1 (2R): Close 50% position, trail remainder with Chandelier
```

---

### 9.3 Entry Decision Matrix

```
ENTRY DECISION TREE

Is Market State = BULLISH?
  NO: Reduce position size; only takes STRONG BUY signals on 75% size

Is Stage = STAGE 2 (any variant)?
  NO: Stop. No entry. Place on watchlist if Stage 1 constructive.

Is RS vs Nifty 500 = "Leading" or "Weakening"?
  NO: Weak leadership. Skip unless other factors exceptional.

Is Overhead Resistance Count <= 3?
  NO: BLOCKED signal likely. Confirm with Trade Validation row.

Is Catalyst detected?
  NO: Add to watchlist. Set BoS alert on Zigzag.
  POS-BO: Check: Vol > 1.5x avg? Close in top 25% of range? YES: Enter
  POS-ACCUM: Check: OBV breakout? Price lagging? Flat base? YES: Enter
  SWG-PB: Check: RSI 40-60? Near 20-EMA +/-1.5%? Vol dry? YES: Enter
  SWG-BO: Check: VCP tight? Pivot break? Vol > 1.2x? Anti-algo pass? YES: Enter
  SWG-REV: Check: RSI-3 < 20? Vol spike? In Stage 2? YES: Enter (small size)
  SWG-GAP: Check: Gap > 4%? Vol > 3x? Up-close? Stage 2? YES: Enter

Is Trade Validation = Clear Room to T1?
  NO: Skip. Bad Risk/Reward. Wait for better setup.
  YES: Execute as per Risk Allocator quantities.
```

---

<a name="risk"></a>
## 10. RISK MANAGEMENT FRAMEWORK

### 10.1 Position Sizing Formula

```
Risk Amount   = Portfolio Capital x Risk %
              = 100000 x 0.75% = 750 (for stocks)

Risk Per Share = Entry Price - Stop Loss Price
              = 500 - 475 = 25

Risk-Sized Qty = Risk Amount / Risk Per Share
              = 750 / 25 = 30 shares

Cap-Sized Qty  = Max Allocation / Entry Price
              = 25000 / 500 = 50 shares

Final Qty      = MIN(30, 50) = 30 shares
Invested       = 30 x 500 = 15000
```

### 10.2 Dynamic Risk Adjustments

| Market Condition | Adjustment |
|-----------------|------------|
| Bull Market + Kelly Grade 3/3 | 1.25x base risk (Kelly boost) |
| Bull Market base | 1.0x base risk |
| Bear Market (automatic) | -0.25% deduction from base |
| High Volatility (ATR > 3% of price) | Proportional ATR discount |
| Kelly Grade 1/3 | 0.75x base risk |
| Floor (minimum) | 0.25% — never goes below |

### 10.3 Target Levels

| Trade Type | T1 (Partial Exit - 50%) | T2 (Runner Exit) |
|------------|------------------------|-----------------|
| Positional (Bull Market) | 2.5R | 3.5R |
| Positional (Bear/Correction) | 2.0R | 3.0R |
| Swing Pullback | 2.5R (Bull) / 2.0R (Bear) | 3.5R |
| Mean Reversion | 2.0R (strict minimum) | 3.0R |

> **R = Initial Risk per share** = Entry Price - SL Price (at time of trade entry)

### 10.4 Stop Loss Management

| Phase | Stop Loss Rule |
|-------|---------------|
| Trade Entry | Hard SL = structural low (10-day) minus 0.2x ATR, OR EMA-based |
| At Breakeven (1.5R) | Move SL to entry price (free trade) |
| First Partial Profit (T1) | Trail with 20-EMA for swing; Chandelier for positional |
| At 3R (Super-tight) | Chandelier multiplier reduced to 0.5x ATR |

### 10.5 Portfolio Exposure Rules

| Rule | Threshold |
|------|-----------|
| Maximum single position | 25% of portfolio |
| Maximum correlated sector exposure | 30% of portfolio |
| Maximum total long exposure (Bull) | 80% of portfolio |
| Maximum total long exposure (Correction) | 50% of portfolio |
| Cash in Bear Market | >= 50% of portfolio |

---

<a name="glossary"></a>
## 11. SIGNAL GLOSSARY & DECISION TREES

### Signal Strength Hierarchy

```
STRONG BUY    = Stage 2 + RS Leading + Vol Shelf + Macro Edge + Micro Edge
BUY           = Stage 2 + RS OK + Catalyst (Edge partially met)
PULLBACK      = Stage 2 + RSI 40-60 + Near EMA + Vol Dry + Micro Edge
WAIT          = Setup valid but no catalyst yet
AVOID         = Stage 3/4 OR Bearish market
```

### Catalyst Priority Order (Best to Least Reliable)

1. **POS-BO (Stage 2 Breakout)** — Highest win rate in Bull markets
2. **SWG-PB (Pullback at EMA)** — High win rate; best risk/reward
3. **POS-ACCUM (OBV divergence)** — Early-stage setup; patience required
4. **SWG-BO (VCP breakout)** — Fast moves; smaller targets typical
5. **SWG-GAP (Gap & Go)** — High gain potential; volatile
6. **SWG-REV (Mean Reversion)** — Lowest win rate; only use in Bull markets with small size

### RS Velocity States

| State | Meaning | Action |
|-------|---------|--------|
| ACCELERATING LEADER | Outperforming AND momentum increasing | Increase position size |
| EXHAUSTED LEADER | Outperforming BUT momentum waning | Take partial profits |
| HIDDEN ACCUMULATION | Currently lagging BUT momentum turning up | Early watchlist entry |
| DEAD MONEY / STATIC | Lagging AND no improvement | Avoid entirely |

---

<a name="mistakes"></a>
## 12. COMMON MISTAKES & HOW TO AVOID THEM

| Mistake | What Goes Wrong | Prevention |
|---------|----------------|------------|
| Buying in Stage 4 hoping for reversal | Stage 4 stocks continue lower 70%+ of the time | Never enter unless Stage 2 confirmed |
| Ignoring overhead resistance | T1 hit before stock moves to target; early reversal | Always check Overhead Resistance Count and Trade Validation |
| Trading with RS Lagging | Stock underperforms even in bull markets | RS must be at least "Improving" (not Lagging) |
| Chasing gaps without volume | False breakout; stock reverses same day | Anti-algo gate: close must be in top 60% of range |
| Over-sizing in correction markets | Normal drawdowns hit stops faster | Kelly multiplier automatically reduces; also manually reduce to 75% |
| Holding Stage 3 positions | Tops are violent; large loss risk | Zigzag BoS alert triggers on breakdown — exit immediately |
| Not monitoring days held | Capital tied up in stagnant trades | Time-Decay Exit at 10 days with <0.5R gain (Strategy handles automatically) |
| Using wrong sector for RS | Incorrect RS state causes wrong recommendation | Use the Hybrid Sector Lookup (auto-corrects via DB mapping for NSE stocks) |
| Fundamentally weak fast-movers | Pump-and-dump risk; no institutional support | X-Ray must show Grade B or higher for positional trades |
| Entering blocked setups | T1 blocked by resistance = bad RR | Only enter when Trade Validation = Clear Room to T1 |

---

<a name="cheatsheet"></a>
## 13. QUICK REFERENCE CHEAT SHEET

### Pre-Trade Checklist (Print & Use Daily)

```
[ ] 1. Market State = BULLISH or CORRECTION (never BEARISH)
[ ] 2. Stage = STAGE 2 (any variant) on Weekly chart
[ ] 3. RS vs Nifty 500 = Leading or at minimum NOT Lagging
[ ] 4. RS vs Sector = NOT Lagging
[ ] 5. Overhead Resistance <= 3 levels (or 0 for best setups)
[ ] 6. Active Catalyst detected (non-NONE)
[ ] 7. Trade Validation = Clear Room to T1
[ ] 8. Fundamental Grade >= B (for positional) or >= C (for swing)
[ ] 9. Zigzag shows UPTREND + HH/HL structure
[ ] 10. Risk Allocator shows valid quantity > 0
```

### Recommended Module Stacking on TradingView

For each candidate stock, load these 4 indicators simultaneously:
1. **Swing Pro Dashboard v63.0** — primary analysis table
2. **Swing Zigzag Strict v6.0** — structure visualization
3. **Fundamental X-Ray v2.1** — quality validation
4. **Strategy v4.4** — entry/exit execution guide

Use pane settings:
- Dashboard v63.0: Overlay (same pane as price)
- Zigzag v6.0: Overlay (same pane as price)
- X-Ray v2.1: Overlay (bottom-left to avoid covering Zigzag)
- Strategy v4.4: Overlay (shows chart lines and allocator table)

### Key Parameter Summary (Keep All Modules Synced)

| Parameter | Value to Use Everywhere |
|-----------|------------------------|
| Weinstein WMA | 30 weeks |
| Slope Lookback | 4 weeks |
| Slope Threshold | 0.0005 |
| Mansfield RS Length | 26 weeks (= 130 daily bars) |
| RS Slope Lookback | 8 weeks |
| 50 DMA | 50 days |
| 150 DMA | 150 days |
| 200 DMA | 200 days |
| ATR Length | 14 days |
| VCP Detection | ATR(10) < SMA50(ATR10) x 1.5 |
| Vol Baseline | SMA(50) of volume |
| ETF Risk % | 1.0% |
| Stock Risk % | 0.75% |
| T1 R:R | 2.0R minimum (2.5R in Bull market) |
| T2 R:R | 3.5R (Bull) / 3.0R (Bear) |

---

## APPENDIX A: NSE Sector Index Reference

| Sector | TradingView Symbol | Use For |
|--------|-------------------|---------|
| Banking & Finance | NSE:BANKNIFTY | Banks, NBFCs, Insurance |
| Information Technology | NSE:CNXIT | IT Services, Software |
| Pharmaceuticals | NSE:CNXPHARMA | Pharma, Healthcare |
| Automobiles | NSE:CNXAUTO | Auto OEMs, Components |
| FMCG | NSE:CNXFMCG | Consumer staples, food |
| Metals & Mining | NSE:CNXMETAL | Steel, Aluminium, Mining |
| Energy | NSE:CNXENERGY | Oil & Gas, Power |
| Real Estate | NSE:CNXREALTY | Builders, REITs |
| Infrastructure | NSE:CNXINFRA | Capital goods, Utilities |
| Broad Market | NSE:CNX500 | Default fallback |

---

## APPENDIX B: Version History & Key Fixes

| Version | Module | Key Change |
|---------|--------|------------|
| v63.0 | Dashboard | Overhead Resistance fixed (ATH-epoch bounded, deduplicated pivot counting) |
| v4.4 | Strategy | Kelly probability sizing, SMC Liquidity Sweep, Time-Decay exit |
| v6.0 | Zigzag | Full MTF support, BoS alerts, rolling choppiness counter, Fib levels |
| v2.1 | X-Ray | Overall 17-pt rating, currency bug fix, row allocation fix |
| v3.5 | Ultimate | Sector RS added, Vol Shelf scoring, SMC sweep, stateful stage machine |
| v2.2 | Beta | Stage machine hysteresis, Anti-algo SWG-BO gate, Vol baseline aligned, 3-way RS |

---

*Weinstein Commander Suite — Developed for disciplined, process-driven trading on Indian equity markets (NSE/BSE). All signals are algorithmic aids — apply personal judgment and never risk more than you can afford to lose.*

---
End of Document
