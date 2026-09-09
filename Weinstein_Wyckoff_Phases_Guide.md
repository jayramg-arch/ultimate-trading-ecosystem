# Weinstein Wyckoff Phases v1.0 - User & Trading Guide

> [!WARNING]
> **LEGACY REFERENCE MANUAL - ARCHIVAL USE ONLY**
> This guide (v1.0) has been superseded by the **Unified Ecosystem v2.2** and **Dashboard v67.0** documentation framework.
> 
> **Canonical Source of Truth:**
> *   For the latest unified configuration: **[docs/13_Unified_Ecosystem_User_Guide.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/13_Unified_Ecosystem_User_Guide.md)**
> *   For Wyckoff narrative: **[docs/02_Wyckoff_Phases_v1_Guide.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/02_Wyckoff_Phases_v1_Guide.md)**
> *   For the documentation index: **[docs/00_INDEX.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/00_INDEX.md)**
> 
> **For the current canonical documentation and latest logic, please refer to:**
> - **Module Guide:** [02_Wyckoff_Phases_v1_Guide.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/02_Wyckoff_Phases_v1_Guide.md)
> - **Documentation Index:** [00_INDEX.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/00_INDEX.md)
> 
> *Do not use this file for live trading execution.*


## Overview
The **Weinstein Wyckoff Phases v1.0 (WWP)** indicator automates the identification of Richard Wyckoff's classic Accumulation and Distribution schematics. By analyzing price pivots alongside volume expansion and contraction, this tool maps out institutional campaigns—helping you distinguish between a genuine trend reversal and a simple pullback.

---

## Core Concepts & Terminology

### Accumulation Schematic (Bottoming / Buying)
When institutions want to buy massive quantities of stock, they cannot do it all at once without spiking the price. They "accumulate" over time in a trading range.
* **PS (Preliminary Support):** The first attempt to halt the downtrend. Volume spikes, but the downtrend continues.
* **SC (Selling Climax):** Capitulation. Panic selling hits the market. Extremely high volume, wide spread, but price closes near its highs as institutions absorb the panic.
* **AR (Automatic Rally):** A relief bounce fueled by short covering and institutional buying off the SC.
* **ST (Secondary Test):** Price revisits the SC low to test supply. Volume should be *lower* here, indicating selling pressure is drying up.
* **Spring (SP):** The ultimate trap. Price breaks below the SC/ST support to flush out retail stop-losses, but immediately recovers on strong volume.
* **SOS (Sign of Strength):** A massive, high-volume bullish move breaking above the AR highs.
* **LPS (Last Point of Support):** A low-volume pullback after the SOS. This is the optimal entry point before the markup phase begins.

### Distribution Schematic (Topping / Selling)
When institutions want to offload shares, they distribute them to eager retail buyers at the top of a trend.
* **PSY (Preliminary Supply):** First sign of heavy resistance and volume at the top.
* **BC (Buying Climax):** Retail FOMO peaks. Huge volume and wide spreads, but price closes poorly (near the lows of the bar).
* **AR (Automatic Reaction):** A sharp decline as institutions temporarily stop supporting the price.
* **UT (Upthrust):** A false breakout above the BC high to trap late buyers. Closes poorly.
* **SOW (Sign of Weakness):** A massive, high-volume bearish move breaking market structure.
* **LPSY (Last Point of Supply):** A weak, low-volume rally after the SOW. The optimal short entry.

---

## Indicator Settings & Inputs

* **Pivot Length (Default: 10):** Defines the sensitivity of the swing highs and lows used to map the phases. 
* **Volume Avg Lookback (Default: 20):** The baseline used to calculate what constitutes "high" or "low" volume.
* **High Volume Threshold (Default: 1.5x):** Multiplier above the average volume required to trigger capitulation events like SC, BC, or SOS.
* **Low Volume Threshold (Default: 0.7x):** Multiplier below the average volume required to trigger dry-up events like ST or LPS.
* **Show Volume Multiplier in Label:** When enabled, the label (e.g., `SC (2.4x)`) shows exactly how massive the volume spike was compared to the average.

---

## Trading Guide: How to Trade Wyckoff Phases

Wyckoff is about understanding the *story* of the chart. Do not trade isolated labels; trade the sequence.

### The Accumulation Play (Going Long)
1. **The Shakeout:** Look for a sustained downtrend that prints an **SC (Selling Climax)**. 
2. **The Test:** Wait for the **ST (Secondary Test)**. Verify that the volume multiplier is significantly lower than the SC.
3. **The Trap (Optional but Powerful):** Look for a **Spring**. This is the ultimate confirmation that liquidity has been grabbed.
4. **The Entry (Conservative):** Wait for the **SOS (Sign of Strength)** to break market structure, followed by an **LPS (Last Point of Support)**. 
5. **Execution:** Enter on the LPS as it turns upward. Place your stop loss safely below the Spring or ST.

### The Distribution Play (Going Short)
1. **The Climax:** Look for an uptrend that prints a **BC (Buying Climax)**. This shows retail exhaustion.
2. **The Trap:** Watch for an **UT (Upthrust)**. This false breakout is a great aggressive short entry.
3. **The Entry (Conservative):** Wait for a **SOW (Sign of Weakness)** to smash through support, followed by an **LPSY (Last Point of Supply)**.
4. **Execution:** Enter short on the LPSY. Place your stop loss above the UT or BC.

### Combining with Other Indicators
Wyckoff is incredibly powerful when combined with Volume Profile and SMC.
* **Confluence:** If an LPS (Wyckoff) aligns with a Bullish Order Block (SMC) and perfectly bounces off the Point of Control (Volume Profile), it is a top-tier, high-probability setup.
