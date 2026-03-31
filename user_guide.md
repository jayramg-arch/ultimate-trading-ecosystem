# 📘 Weinstein & Minervini Trading Suite: User Guide

Welcome to the comprehensive technical documentation for the **Weinstein & Swing Pro Dashboard [v60.0]** and the **Unified Strategic Engine [v2.0]**. This guide covers every metric, logic gate, and parameter outcome to help you master the suite.

---

## 🏗️ Part 1: Suite Overview
This suite is designed as a **dual-engine system**:
1.  **The Dashboard (Indicator):** Acts as your "Mission Control." It monitors 25 portfolio slots, analyzes global market health, sector relative strength, and scans for the highest-probability setups using the **Alpha Screener**.
2.  **The Strategy (Backtester/Execution):** Handles the automated trade execution, risk management, and backtesting. It uses the exact same logic as the dashboard to ensure what you see is what you trade.

---

## 📊 Part 2: Weinstein & Swing Pro Dashboard v60.0

The Dashboard uses a **4-Column Layout** to maximize visibility while minimizing chart real estate.

### Column 1: Macro & Portfolio Context

| Metric | Description | Possible Outcomes |
| :--- | :--- | :--- |
| **Recommendation** | The primary bias for the current ticker. | `STRONG BUY`, `BUY (PB)`, `WAIT`, `EXIT NOW`. |
| **Asset Quality** | A 100-point score evaluating the stock's fundamental and technical "pedigree." | `A (Elite)`, `B (Good)`, `C (Weak)`. |
| **Action Signal** | Real-time entry/exit trigger. | `BREAKOUT!`, `PULLBACK 🎯`, `NEUTRAL`. |
| **Trade Style** | The recommended way to play the current chart. | `CORE (Long)`, `SWING`, `WAIT`. |
| **Persona** | Identifies if the stock is a leader or a laggard. | `LEADER`, `STEADY`, `LAGGARD`. |
| **Portfolio Health** | Displays real-time PnL and distribution of your 25 slots. | `RISK ON (Green)`, `RISK OFF (Red)`. |
| **My Trade** | Status of the specific slot matching the current chart. | `PROFIT %`, `STOP HIT`, `NO POSITION`. |
| **Entry Date** | The date the position was opened (Historical reference). | `YYYY-MM-DD`, `N/A`. |
| **Days Held** | Total duration of the current trade in days. | `X Day(s)`. |

### Column 2: Institutional Edge & Filters (Mathematical Edges)

| Metric | Logic / Threshold | Outcomes |
| :--- | :--- | :--- |
| **Macro Edge (Vol)** | Volume Shelf (VWMA>SMA) + Volume Accumulation. | `PASS` (Inst. Bias), `PENALTY`. |
| **Micro Edge (Sqz)** | Price > CPR + Monthly VWAP + 20/50 Squeeze. | `PASS` (Confluence), `WAIT`. |
| **Daily Close > CPR** | Price relative to the Central Pivot Range. | `YES` (Bullish Support), `NO`. |
| **Price > M-VWAP** | Price relative to the Monthly Volume Weighted Average Price. | `YES` (Inst. Accumulation), `NO`. |
| **Vol Shelf (VWMA)** | Check if 20-period VWMA is above the 20-period SMA. | `YES` (High Conviction), `NO`. |
| **VCP Tightness** | Price is consolidating tighter than its average ATR. | `PASS` (Contraction), `WAIT`. |

### 🚦 Signal Interpretation (Dashboard vs. Strategy)

It is important to understand that the **Dashboard** and **Strategy** use mirrored logic but different "trigger" sensitivities.

| Feature | Dashboard Signal | Strategy Signal | Key Difference |
| :--- | :--- | :--- | :--- |
| **Breakout** | `Breakout Signal` (Tiny Blue Triangle) | `★ W-POS` (Blue Star Triangle) | Dashboard is faster; Strategy requires strict Alpha Score > 70. |
| **Pullback** | `Pullback Hit` (Tiny Purple Circle) | `▲ M-SWING` (Purple Circle) | **Dashboard** marks the "Dip Zone" (Early); **Strategy** waits for the "Pivot Break" (Confirmation). |
| **Momentum** | `Strong Buy` (Lime Star) | N/A | Dashboard only. High-confluence RS + Trend scan. |

> [!TIP]
> Use the **Dashboard** for early alerts and the **Strategy** for confirmed mathematical entries.

### Column 3: Breadth & Sector Analysis
| Metric | Description | Outcomes |
| :--- | :--- | :--- |
| **Mkt Health (N500)** | Nifty 500 relative to its 200 DMA. | `BULLISH` (Safety), `BEARISH` (Caution). |
| **Sector Velocity** | The "Internal Momentum" of the sector RS slope. | `ACCELERATING LEADER`, `DEAD MONEY`, `HIDDEN ACCUM.`. |
| **RS (vs Benchmark)** | Mansfield RS value evaluating relative outperformance. | `Leading`, `Improving`, `Weakening`, `Lagging`. |
| **Next Earnings** | Date of the next earnings release. | `DATE`, `N/A`. |

### Column 4: Strategy Engines (Positional & Swing)
| Section | Metric | Logic |
| :--- | :--- | :--- |
| **🦁 POSITIONAL** | Market Structure | Stage 1 (Base), **Stage 2 (Advance)**, Stage 3 (Top), Stage 4 (Decline). |
| | Master Trend (W) | Direction of the Weekly Pivot structure. |
| | 30-Week MA Slope | `RISING` (Required for Phase 1), `FALLING`, `FLAT`. |
| **🎯 SWING** | Daily Trend (D) | Direction of the Daily Pivot structure. |
| | Trend Template | Price > 50 > 150 > 200 (Minervini's core filter). |
| | PB Health | Evaluates if the pullback is "Low Volume" (Healthy) or "Dump" (Dangerous). |

---

## ⚔️ Part 3: Weinstein_Minervini_Strategy v2.0

### Strategy Modes
- **Hybrid (Both):** Actively hunts for both long-term Stage 2 breakouts (Weinstein) and short-term volatility contraction pullbacks (Minervini).
- **Breakout Only / Pullback Only:** Narrow the scope to your preferred trading style.

### Key Logic Integrations
#### 🛡️ Alpha Score Engine (0-100)
Every trade must pass the `Min Alpha Score` (Default: 70).
- **Trend (30 pts):** Price > EMA 20 and SMA 50.
- **Momentum (30 pts):** RSI > 60 and ADX > 20.
- **Volume (20 pts):** Volume Expansion on up-days.
- **Safety (20 pts):** Proximity to Moving Averages (No buying extended stocks).
- **Edge Boost/Penalty:**
    - **Macro Edge PASS:** +10 points bonus.
    - **Macro Edge FAIL:** -20 points penalty (Heavily penalizes low-volume breakouts).

#### 📈 Dynamic R:R Targets
The strategy senses "Market Health" (Nifty 500 Trend).
- **Bull Market:** Targets `2.5R` (Aiming for runners).
- **Bear Market:** Targets `1.5R` (Take profits early).

### Risk Management
- **Manual Risk Allocator Table:** Visible on the chart. Enter your Entry/Stop prices in the settings to see exact **Quantity** suggestions based on your % Portfolio Capital.
- **Time Stop:** Automatically exits trades that stagnate for more than 10 days without moving.

---

---

## ⚙️ Part 4: Detailed Parameter Reference

### 📈 Dashboard Inputs (Indicator)
#### 1. Portfolio & Symbols
- **Slot 1-25:** Enter the ticker (e.g., `NSE:RELIANCE`). The dashboard will auto-index this symbol.
- **Entry / SL:** Manual fields to track your specific position PnL and stop distance.
- **Date:** The date/time you took the trade. This is used to calculate "Days Held" and to **visually start** the trade lines (Entry/SL/Targets) on the chart from that point forward.
- **Sector Override:** Manually link a slot to a specific sector index if the auto-mapper is insufficient.

#### 2. Mathematical Edges (Backtested)
- **Macro Edge: Institutional Vol Bias:**
    - **Logic:** Only fires if Volume Shelf (VWMA > SMA) AND Volume Accumulation rules are met.
    - **Outcome:** Provides the highest P-Factor edge based on 5-year backtests.
- **Micro Edge: Price & Squeeze Validation:**
    - **Logic:** Requires Price > CPR, Price > Monthly VWAP, and Active 20/50 Squeeze.
    - **Outcome:** Ensures entry is made at a high-confluence "cheat" area.
- **Filter: VCP Tightness:** 
    - **Logic:** ATR(10) must be lower than SMA-ATR(50) * Tightness Factor. 
    - **Outcome:** `PASS` identifies the "pivot" areas of a volatility contraction.

#### 3. Alpha Screener Logic
- **Minimum Alpha Score:** Threshold (0-100) for the `BUY` recommendation.
    - **Score > 85:** Elite Setup (High Probability).
    - **Score > 70:** Solid Trade (Good Risk/Reward).
    - **Score < 50:** Avoid (Laggard or Extended).

### 🛡️ Strategy Inputs (Automated Engine)
#### 1. Strategy Modes
- **Strategy Mode:** Defines which setups fire orders (`Breakout`, `Pullback`, or `Hybrid`).
- **Asset Type:** Switches risk calculation between `Stock` (Standard) and `ETF` (Lower volatility risk).

#### 2. Risk Management
- **Total Portfolio Capital:** Used to calculate position size.
- **Stock/ETF Risk %:** The amount of **Total Equity** you are willing to lose per trade.
- **Time Stop:** Number of days to wait. If the stock doesn't move 1R in this time, it exits to free up capital.

#### 3. Exit Mechanics
- **Use Dynamic R:R:** If `enabled`, the strategy automatically lowers targets in bear markets and raises them in bull markets.
- **Chandelier Exit (Positional TSL):**
    - **Logic:** A "Smart" structural trailing stop that ratchets up based on ATR and highest high.
    - **Adaptive Scaling:** Automatically adjusts parameters for different timeframes (Weekly vs Daily).
    - **Ratchet Effect:** Once it moves up, it never moves down, ensuring profit lock-in.
- **Adaptive TSL (Swing):** If price hits `1.5R`, the stop tightens by `25%`. At `3.0R`, it tightens by `50%`.

#### 4. Technical Core Settings
- **Weinstein SMA Length (Weekly):** Default `30`. This is the "Stage Analysis" line.
    - **Outcome:** Price above rising 30 SMA = Stage 2. Price below falling 30 SMA = Stage 4.
- **Mansfield RS Length:** Default `52`. Evaluates relative performance over a 1-year window.
- **Daily MA Settings (50, 150, 200):** 
    - **Minervini Trend Template:** All three must be in alignment (`50 > 150 > 200`) for a `PASS`.
- **VDU (Volume Dry-Up):** 
    - **Logic:** Volume must drop by `30%` or more compared to its 50-day average during a pullback.
    - **Outcome:** High VDU = "Low supply," which is bullish.

---

---

## 🧠 Part 7: The "Brain" - Deep Logic Reference

### 1. Weinstein Stage Analysis (The State Machine)
The script uses a persistent **State Machine** to track the long-term health of a stock. Unlike simple indicators, this logic remembers the previous bar's state to ensure smooth transitions.

| Stage | Definition | Logical Conditions |
| :--- | :--- | :--- |
| **Stage 1 (Base)** | Consolidation | Price is above/around a **flat** 30-Week SMA. |
| **Stage 2 (Advance)** | Bull Market | 30-Week SMA is **rising** + Price > SMA + Weekly Trend is Up. |
| **Stage 3 (Top)** | Distribution | 30-Week SMA flattens out + Price starts oscillating around it. |
| **Stage 4 (Decline)** | Bear Market | 30-Week SMA is **descending** + Price < SMA. |

**The "Cheat Code":** The Strategy looks for the **Stage 1 → Stage 2 Transition**. This is where the big money is made. 

---

### 2. Alpha Screener Scoring (The 100-Point Engine)
This engine looks at 4 pillars of technical health. If a stock doesn't score above `70`, the strategy considers it "low conviction."

#### **Pillar A: Trend Structure (30 Points)**
- **+15 pts:** Price > 20 EMA (Short term strength).
- **+15 pts:** Price > 50 SMA (Medium term health).

#### **Pillar B: Momentum (30 Points)**
- **+20 pts:** RSI(14) > 60 (Active institutional bidding).
- **+10 pts:** ADX > 20 (Strong current trend). *Note: If RSI is only > 50, it only gets +10.*

#### **Pillar C: Volume Thrust (20 Points)**
- **+20 pts:** Current Volume > 150% of 50-day average + Price is Up.
- **+10 pts:** Current Volume > 100% of 50-day average + Price is Up.

#### **Pillar D: Safety / Mean Reversion (20 Points)**
*This prevents you from "buying the top."*
- **+20 pts:** Price is within **5%** of the 20 EMA (Low risk entry).
- **+10 pts:** Price is within **10%** of the 20 EMA.
- **+0 pts:** Price is > 10% extended (Danger Zone).

---

### 3. Institutional "Smart Money" Filters
#### **A. Central Pivot Range (CPR)**
- **Logic:** Calculates the `Pivot`, `Bottom Central`, and `Top Central` based on the previous day's H/L/C.
- **Signal:** Price > `Top Central` means the "Floor" is holding.

#### **B. Volume Accumulation Density**
- **Logic:** Looks back 10 days. Counts days where:
    1.  Price Close > Yesterday's Close.
    2.  Volume > 50-day Average.
    3.  Close is in the **top 40%** of the daily range.
- **Requirement:** Must have at least `2` such days in the last 10 to PASS.

#### **C. VDU (Volume Dry-Up)**
- **Logic:** During a pullback, volume must be low.
- **Math:** `Current Volume < (50-Day Avg Volume * 0.70)`. This proves sellers are exhausted.

---

### 4. Market Health & Dynamic Targeting
#### **The Bull/Bear Switch**
- **Trigger:** Checks if the benchmark (`Nifty 500`) is above its own **200-day Moving Average**.
- **Effect:**
    - **Bullish:** Strategy target = `2.5 x Risk`.
    - **Bearish:** Strategy target = `1.5 x Risk`.

---

### 5. Relative Strength (Mansfield RS) Math
- **Formula:** `((Close / 52W SMA of Close) / (Benchmark / 52W SMA of Benchmark)) - 1`
- **Logic:** We aren't just looking if the stock is up. We are looking if the stock is **outperforming its peers**. 
- **Outcomes:** 
    - **RS Line > 0:** Beating the market.
    - **RS Line Rising:** Gaining momentum vs the market.

---

### 6. Sector Velocity Logic
- **Math:** The script calculates the **Slope** of the RS line (Lead/Lag) and compare it to the slope from **5 days ago**.
- **Outcomes:** 
    - **🔥 ACCELERATING:** Current slope > Past slope (Gaining traction).
    - **🛑 EXHAUSTED:** Slope is positive but declining (Buying exhaustion).
    - **⚡ HIDDEN ACCUM.:** Slope is negative but turning up (Early turnaround).

---

---

### 7. VCP (Volatility Contraction) Logic
- **The "Tightness" Formula:** `Current ATR(10) < (SMA of ATR(50) * Tightness Factor)`.
- **Logic:** This identifies when the "noise" in a stock is shrinking. If the Tightness Factor is `1.5`, the current ATR must be less than 1.5x the average volatility.
- **VDU Requirement:** VCP is only valid if volume is also "drying up" (Volume < Average).

---

### 8. Pullback Pattern Triggers
The Strategy doesn't just buy "near" the EMA 20. It waits for a specific **Bullish Reaction**:
1.  **Bullish Engulfing:** Today's body completely swallows yesterday's red body.
2.  **Hammer / Pin Bar:** Long lower wick (2x body) showing price rejection of lower levels.
3.  **Morning Star:** A 3-candle reversal pattern (Big Red -> Small Star -> Big Green).

---

### 9. Adaptive TSL (Trailing Stop) Logic
This is a "Smart" stop loss that matures as the trade enters profit.
- **Phase 1 (Normal):** Trail at `3.0 x ATR`.
- **Phase 2 (Tight):** If Profit > `1.5R`, trailing distance is reduced to `2.25 x ATR` (25% tighter).
- **Phase 3 (Lock):** If Profit > `3.0R`, trailing distance is reduced to `1.5 x ATR` (50% tighter).

---

---

### 10. Secondary Strategy "Safety" Logic
These extra layers of protection ensure the strategy only takes the "perfect" trades.

#### **A. Gap Extension Check**
- **Logic:** `(Close - Breakout Level) / Breakout Level`. 
- **Rule:** If the stock is already `> 5%` above the breakout level on the day of entry, the strategy skips it to avoid "chasing" a move.

#### **B. Stage 2 "Freshness" Filter**
- **Logic:** Counts how many weeks the stock has been in Stage 2.
- **Rule:** If the stock has been in Stage 2 for more than `20 weeks` (default), it's considered "mature" and potentially ready for a Stage 3 top. It stops taking new breakouts in these mature stocks.

#### **C. Smart Fibonacci Retracement**
- **Logic:** `Highest(21) - (Range(21) * 0.5)`. 
- **Rule:** For a pullback to be valid, it must retract to at least the **50% level** of its recent 21-day range, but not break below the absolute 21-day low.

---

## 🏗️ Part 11: Manual Risk Allocator Example
1.  **Set the Portfolio:** Match your Dashboard inputs to the symbols you are tracking.
2.  **Filter with Alpha:** Use the Alpha Screener on the Dashboard to find the `[PULLBACK 🎯]` setups.
3.  **Confirm on Strategy:** If the Strategy shows a `YES` for the setup, it is a high-probability trade.
4.  **Execute:** Use the Risk Allocator table to determine your position size and enter the trade.

> [!TIP]
> **Pro Tip:** Always prioritize symbols that are in **Stage 2 (Advance)** on the Weekly chart while showing **VCP Tightness** on the Daily chart. These are the "Super-performance" setups identified by Mark Minervini.

---
*Guide generated for Weinstein Commander Suite v60.0 / v2.0*
