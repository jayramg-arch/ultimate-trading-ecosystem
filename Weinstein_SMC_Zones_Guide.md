# Weinstein SMC Zones v1.0 - User & Trading Guide

> [!WARNING]
> **LEGACY REFERENCE MANUAL - ARCHIVAL USE ONLY**
> This guide (v1.0) has been superseded by the **Unified Ecosystem v2.2** and **Dashboard v67.0** documentation framework.
> 
> **Canonical Source of Truth:**
> *   For the latest unified configuration: **[docs/13_Unified_Ecosystem_User_Guide.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/13_Unified_Ecosystem_User_Guide.md)**
> *   For institutional context: **[docs/12_Context_Layers_v1_Guide.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/12_Context_Layers_v1_Guide.md)**
> *   For the documentation index: **[docs/00_INDEX.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/00_INDEX.md)**
> 
> **For the current canonical documentation and latest logic, please refer to:**
> - **Module Guide:** [04_SMC_Zones_v1_Guide.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/04_SMC_Zones_v1_Guide.md)
> - **Documentation Index:** [00_INDEX.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/00_INDEX.md)
> 
> *Do not use this file for live trading execution.*


## Overview
The **Weinstein SMC Zones v1.0** indicator brings institutional-grade Smart Money Concepts (SMC) directly to your TradingView charts. Designed and optimized specifically for the NSE/India markets, this tool identifies institutional footprints—revealing where major players are accumulating, distributing, and hunting liquidity.

---

## Core Concepts & Terminology

### 1. Order Blocks (OB)
Order blocks represent the last opposite-colored candle before a significant impulsive move that breaks market structure. 
* **Bullish OB (Green Box):** The last bearish candle before a strong bullish impulse. Institutions accumulated massive long positions here. When price returns to this zone, they often defend it, making it a high-probability buy zone.
* **Bearish OB (Red Box):** The last bullish candle before a strong bearish dump. This is where institutions built short positions. It serves as heavy resistance.

### 2. Fair Value Gaps (FVG / Imbalances)
FVGs represent aggressive price pricing where buyers or sellers overwhelmed the other side, leaving a "gap" in price delivery (a 3-bar pattern where the 1st and 3rd bars do not overlap).
* **Bullish FVG (Teal Box):** Rapid upward movement. Price often retraces to "fill" this gap and mitigate the imbalance before continuing higher.
* **Bearish FVG (Orange Box):** Rapid downward movement. Price acts as a magnet to fill this gap before continuing the downtrend.

### 3. Break of Structure (BOS) & Change of Character (CHoCH)
* **BOS (Break of Structure):** Occurs when price breaks and closes past a previous swing high (in an uptrend) or swing low (in a downtrend). It signals **trend continuation**.
* **CHoCH (Change of Character):** The *first* BOS that goes against the prevailing trend. It acts as an early warning signal of a **trend reversal**.

### 4. Liquidity Sweeps
Retail traders often place stop losses just above swing highs or below swing lows. Institutions "sweep" these areas to grab liquidity to fill their massive orders.
* **Sweep Indicator:** A label (`Liq Sweep 🩸`) appears when price pierces a prior swing point but immediately reverses and closes back inside the range.

---

## Indicator Settings & Inputs

* **Swing Length for OB/BOS (Default: 5/10):** Determines how sensitive the indicator is to swing highs and lows. Lower numbers spot micro-structure; higher numbers spot macro-structure.
* **Max OBs / FVGs to Show:** Keeps your chart clean by only displaying the most recent institutional zones.
* **Keep Mitigated OBs/FVGs:** By default, once an OB or FVG is pierced/tested ("mitigated"), it disappears to keep the chart clean. You can toggle this to keep historical zones visible.
* **Min Gap Size (% of price) (Default: 0.05%):** Filters out insignificant micro-gaps. Only FVGs larger than this threshold will be highlighted.

---

## Trading Guide: How to Trade SMC Zones

### The "Return to Origin" Setup (High Probability)
The most powerful way to trade this indicator is combining CHoCH, FVGs, and Order Blocks.

**The Bullish Setup:**
1. **Identify the Shift:** Look for a downtrend that suddenly prints a **Bullish CHoCH** (Change of Character).
2. **Find the Footprint:** Look below the CHoCH for a fresh **Bullish Order Block (OB)** and a **Bullish Fair Value Gap (FVG)**.
3. **Wait for the Retest:** Do *not* buy the breakout. Wait for price to pull back down into the FVG or Order Block (this is the "Return to Origin").
4. **Execution:** Enter your long position when price taps the OB.
5. **Stop Loss:** Place your stop loss safely below the Order Block.
6. **Take Profit:** Target unmitigated Bearish FVGs or older Liquidity Sweeps above.

**The Bearish Setup:**
1. Wait for an uptrend to print a **Bearish CHoCH**.
2. Identify the **Bearish OB** and **Bearish FVG** left behind near the top.
3. Wait for the relief rally to tap into the Bearish OB/FVG.
4. Short the market, placing your stop loss just above the Bearish OB.

### The "Liquidity Trap" Setup
1. Wait for a **Liquidity Sweep** label (`Liq Sweep 🩸`) to print at a major high or low.
2. For a Bullish Sweep (price swept lows and closed higher), wait for a micro-timeframe Bullish CHoCH.
3. Enter long, anticipating that the institutions have finished accumulating and are now driving price higher. Stop loss goes below the sweep wick.
