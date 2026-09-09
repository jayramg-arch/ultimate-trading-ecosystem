# Weinstein Volume Profile v1.0 - User & Trading Guide

> [!WARNING]
> **LEGACY REFERENCE MANUAL - ARCHIVAL USE ONLY**
> This guide (v1.0) has been superseded by the **Unified Ecosystem v2.2** and **Dashboard v67.0** documentation framework.
> 
> **Canonical Source of Truth:**
> *   For the latest unified configuration: **[docs/13_Unified_Ecosystem_User_Guide.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/13_Unified_Ecosystem_User_Guide.md)**
> *   For volume profile framework: **[docs/03_Volume_Profile_v1_Guide.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/03_Volume_Profile_v1_Guide.md)**
> *   For the documentation index: **[docs/00_INDEX.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/00_INDEX.md)**
> 
> **For the current canonical documentation and latest logic, please refer to:**
> - **Module Guide:** [03_Volume_Profile_v1_Guide.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/03_Volume_Profile_v1_Guide.md)
> - **Documentation Index:** [00_INDEX.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/00_INDEX.md)
> 
> *Do not use this file for live trading execution.*


## Overview
The **Weinstein Volume Profile v1.0 (WVP)** indicator is an advanced charting tool that displays trading activity over a specified period at specified price levels. Unlike traditional volume (which shows volume per *time* period), Volume Profile shows volume per *price* level. This reveals the most accepted prices (value areas) and rejected prices, providing unparalleled context for support and resistance.

---

## Core Concepts & Terminology

### 1. Point of Control (POC)
The **Red Line**. This is the single price level where the highest volume of trading occurred during the lookback period. 
* It represents the "fairest" price in the market.
* It acts as a massive magnet for price; price often gravitates toward it.
* It also acts as extremely strong support or resistance once price moves away from it.

### 2. Value Area (VA)
The shaded histogram region that encompasses a specific percentage (default: 70%) of the total volume traded. This is where the majority of institutional business was conducted.

### 3. Value Area High (VAH) & Value Area Low (VAL)
* **VAH (Green Dashed Line):** The upper boundary of the Value Area.
* **VAL (Orange Dashed Line):** The lower boundary of the Value Area.

### 4. Volume Histogram
The horizontal bars stretching from the right side of the chart. 
* **Thick/Long Nodes (High Volume Nodes - HVN):** Areas of high liquidity. Price tends to chop and consolidate in these zones because both buyers and sellers are comfortable trading here.
* **Thin/Short Nodes (Low Volume Nodes - LVN):** Areas of low liquidity. Price tends to slice through these zones rapidly because there is no historical interest in defending them.

---

## Indicator Settings & Inputs

* **Lookback Bars (Default: 100):** Defines the range of bars to profile. 
  * *Tip:* For intraday/session context, use 75-100 bars. For weekly/swing context, use 250-500 bars.
* **Profile Rows (Default: 40):** The resolution of the histogram. Higher numbers = finer granularity but can look cluttered. 40 is a balanced default.
* **Value Area % (Default: 70.0):** The percentage of volume defining the Value Area. 70% is the industry standard (roughly one standard deviation).
* **Extend POC/VA Lines Left:** Toggles whether the POC, VAH, and VAL lines extend all the way to the left side of the lookback period for easier visual reference.

---

## Trading Guide: How to Trade Volume Profile

### Strategy 1: The "80% Rule" (Value Area Play)
This is a classic Volume Profile strategy regarding market acceptance.
1. If the price opens *outside* the Value Area but then penetrates the VAH (moving down) or VAL (moving up) and stays inside for 2 consecutive closes...
2. There is an 80% statistical probability that the price will traverse the *entire* Value Area to touch the opposite side (e.g., from VAH down to VAL).
3. **Execution:** Enter a trade in the direction of the traverse, targeting the POC first, and the opposite VA boundary second.

### Strategy 2: Break and Retest of High Volume Nodes (HVN)
Because POC and thick histogram nodes represent accepted value, they are strong support/resistance.
1. Wait for price to aggressively break out of the Value Area (past VAH or VAL).
2. Wait for a pullback to the POC or the outer boundary (VAH/VAL).
3. Enter in the direction of the breakout. The POC acts as a launchpad.

### Strategy 3: Slicing Through Low Volume Nodes (LVN)
Low Volume Nodes (the "valleys" in the histogram) act as vacuums. 
1. Identify a large LVN gap between two HVNs.
2. Once price enters the LVN, expect a rapid, volatile move to the next HVN.
3. **Execution:** Do not try to reverse trade inside an LVN. Ride the momentum through the vacuum until it hits the next thick volume node.
