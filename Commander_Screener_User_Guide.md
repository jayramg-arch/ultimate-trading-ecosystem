# Commander Screener [Beta Edition]
## Comprehensive Advanced User Guide

The **Commander Screener Beta Edition** is specifically engineered for TradingView's new **Pine Screener Beta** interface. Unlike traditional Pine indicators that artificially draw tables on the chart, this script converts hundreds of lines of complex Minervini and Weinstein mathematical calculations into native, sortable, and filterable numerical columns suitable for high-speed multi-stock screening.

---

### 1. Initial Setup & Screener Configuration

Because TradingView's Pine Screener defaults to a blank workspace, integrating the Commander Screener requires a few specific steps:

1.  **Add to Screener:** After saving the script, open the Pine Screener (Products -> Screeners -> Pine Screener Beta).
2.  **Select Watchlist:** Choose your desired watchlist from the top left dropdown.
3.  **Apply Indicator:** Click the indicator dropdown (next to the watchlist selector) and apply `Commander Screener Beta Edition`.
4.  **Activate Your Columns:** 
    *This is a critical step.* By default, TradingView only adds the indicator to the "Filter Toolbar" at the very top. It does *not* automatically populate the columns in the actual table.
    - Go to the far right end of the dark grey column header bar (the line that says `Symbol`).
    - Click the **Column Setup Icon** (usually three vertical sliders or a `+` sign).
    - Scroll down and manually check the boxes for all the Commander metrics: *Alpha Score, Dashboard Quality Score, Confluence, Stage, Persona, Styles, Signals, and RS values*.
5.  **Native Sector Column:** Pine script mathematically evaluates numbers, not plain-text strings. To see the actual text name of a stock's sector, enable TradingView's native **Sector** column from the same Column Setup menu.

---

### 2. Under The Hood: Technical Metrics & Logic Explained

The script outputs 13 distinct numerical columns. Below is the advanced logic dictating exactly how these values are generated.

#### A. Alpha Score `(0 to 100)`
The ultimate ranking engine for identifying A+ Setups. It aggressively evaluates trend structure, momentum, safety, and institutional action.
*   **+15 Pts:** Price is currently trading above the 20 EMA.
*   **+15 Pts:** Price is currently trading above the 50 SMA.
*   **+20 Pts:** Daily RSI > 60 *(+10 Pts if RSI belongs in the > 50 consolidation phase).*
*   **+10 Pts:** ADX > 25 & Positive Directional Index > Negative Directional Index (Strong dominant trend).
*   **+20 Pts:** Bullish Close (Green Candle) AND Volume expanded > 1.5x the 20-day average. *(+10 Pts if Volume > 1x avg).*
*   **+20 Pts:** Proximity / Squeeze Safety. Distance to the 20 EMA is tight (< 5%). *(+10 Pts if distance < 10%).*
*   **+10 Pts:** [Macro Edge Toggle] Volume Bias confirms institutional accumulation. Subtracts 20 points if volume is aggressively lacking.

#### B. Dashboard Quality Score `(0 to 100)`
This calculates the overarching macro-health of the asset over a longer timeframe.
*   **+25 Pts:** Stock is confirmed in a pure Stage 2 (Up) phase. *(+10 Pts if Stage 1 Base).*
*   **+15 Pts:** Validated as 'Leading' against the Nifty 500 Relative Strength line.
*   **+15 Pts:** Perfect SMAs Aligned (50 > 150 > 200).
*   **+20 Pts:** Q3 and H1 historical outperformance outpaces the underlying benchmark.

#### C. Confluence `(0 to 5 Stars)`
A brutal, rapid-fire daily checklist. The stock scores 1 point for meeting each of the following:
1.  Close > 20 EMA
2.  Daily RSI remains strongly bullish (> 50)
3.  Smart Money confirmation: Heavy volume occurs on green days, light volume on red days.
4.  ADX > 25 (Trend firmly established)
5.  Body is bullish (Close > Open).

#### D. Stage Mapping `(1.0 to 4.0)`
Stan Weinstein's phases, converted into floats for instant screener sorting:
*   **1.0:** Stage 1 (Base) - Constructive consolidation beneath declining MAs.
*   **2.0:** Stage 2 (Pullback) - Valid structural uptrend experiencing a temporary reversion.
*   **2.1:** Stage 2 (Up) - Full throttle Stage 2 breaking out.
*   **3.0:** Stage 3 (Top) - High volatility, churning, distribution and exhaustion.
*   **4.0:** Stage 4 (Down) - Absolute downtrend. The "avoid entirely" phase.

#### E. Persona Mapping `(0 to 5)`
Categorizes the current "personality" of the chart hierarchy:
*   **5 (Leader):** Leading the RS line, price actively trading above 200 and 50 SMAs.
*   **4 (Momentum):** High RSI, accelerating RS slope.
*   **3 (Turnaround):** Improving RS trajectory, reclaimed the 50 SMA but still stuck below the 200 SMA.
*   **2 (Volatile):** Average Daily Range (ADR) > 5%. Dangerously whip-saw action.
*   **1 (Extended):** >20% above the 20 EMA rubber-band, or RSI > 75. High risk of immediate drop.
*   **0 (Laggard):** Dead money. Lagging RS and buried beneath the 200 SMA.

#### F. Trading Styles `(1 = Match, 0 = Fail)`
*   **Positional (1=Yes):** The stock mathematically qualifies as a Stage 2 or Stage 1 candidate, is confidently above the 200 DMA, and guarantees it is not lagging its sector's RS line. 
*   **Swing (1=Yes):** The stock sits in a shorter-term Minervini sweet spot (Price > 20 EMA > 50 SMA), shows immediate momentum (RSI > 55 or heavy volume thrusts), guarantees it is not dangerously extended (< 15% distance from EMA), and displays Volatility Contraction (VCP) mechanics.

#### G. Actionable Trade Signals `(1 = Triggering Today, 0 = No Action)`
These are true zero-day execution signals.
*   **True Breakout:** The current closing price cleanly broke above the **absolute highest high of the last 21 trading days (1 full month)**. Concurrently, it closed mathematically in the top 25% of the daily candle's range (no heavy selling wicks), and volume expanded by at least 25% over the average.
*   **Pullback Hit:** The price dipped perfectly within the bounds of the 20 EMA "Buy Zone" (Between -2% under to +6% over). The Weekly RSI remains firmly bullish (> 55) but the Daily RSI cooled off into the 40s. Additionally, Volume must have dried up (< 1.1x average).

#### H. Key Technical Metrics (Raw Outputs)
These pure data columns are incredibly powerful for creating your own custom filters outside of the automated Master Signals:
*   **Distance to 20 EMA (%):** A strictly numeric percentage representing exactly how far price is currently stretched away from its core 20-day baseline. 
    *   **Positive Numbers (e.g., `3.43`, `15.2`):** The stock is trading *above* the 20 EMA. Readings > `15%` suggest dangerous rubber-band over-extension prone to sharp regressions. Tightly coiled setups resting perfectly in the buy zone hover around `0%` to `5%`.
    *   **Negative Numbers (e.g., `-1.36`, `-8.43`):** The stock is trading *below* the 20 EMA. Deeply negative numbers mean the stock is currently in a breakdown or heavy pullback phase.
*   **Relative Volume (x-avg):** The real-time volume of the current day divided by its 20-day moving average. A value of `1.0` is exactly an average day of trading. A value of `3.5` indicates the stock is experiencing a massive institutional thrust `3.5x` (350%) larger than normal. This column is the absolute backbone for manually validating strong True Breakouts and identifying aggressive institutional accumulation.

---

### 3. Advanced Filtering Strategy: Avoiding the "0 Results" Trap

The most common mistake when using a multi-metric screener is aggressively using the **"AND" logic trap**: applying multiple filters in the top toolbar simultaneously.

If you filter for: `Alpha Score > 80` + `Dashboard Quality > 80` + `Confluence = 5` + `Stage = 2.1` + `True Breakout = 1`... 

You are asking the screener to find a single stock out of your watchlist that is breaking a 1-month high on massive volume, while exhibiting the highest mathematically possible trends in every other metric, *on this precise day*. In a 200-stock watchlist, the mathematical probability of a "unicorn" hitting every single one of those maximums simultaneously is extremely low, leading to **0 Results**.

**The Pro-Screening Workflow:**
1.  **Clear All Filters First:** Your top filter toolbar should contain no rule boxes.
2.  **Use Sorting, Not Filtering:** Want the best long-term setups? Just click the `Alpha Score` column header on the table so the arrow points down (`Z-A`). This bubbles the absolute strongest charts right to your eyes without deleting the rest of your list.
3.  **Single-Target Filtering:** Instead of building a wall of filters, apply one sniper shot at a time.
    *   *Looking for instant trades?* Apply one filter: `Signal: Pullback Hit = 1`. 
    *   *Looking for strong trenders?* Apply one filter: `Style: Positional = 1`.

---

### 4. Technical Marvels & System Constraints

The TradingView Pine Screener Beta enforces a brutal technical limitation across its servers: Scripts may only query exactly **5** `request.security()` cross-calculations, or they are permanently suspended. 

The Commander Screener Beta circumvents this entirely via advanced engineering:
*   **Tuple Bundling:** It bundles massive arrays of calculations into isolated "Wrappers" allowing it to fetch dozens of Weekly metrics simultaneously using only 1 execution call.
*   **Timeframe Independence:** By specifically segregating and hardcoding the `request.security(..., "W", ...)` and `request.security(..., "D", ...)` calls independently of whatever Timeframe Dropdown the user selects on the Screener UI, the script guarantees flawless Weekly vs Daily relationship analysis across the board.
*   **Screener-Safe Signal Execution:** Screeners do not iterate through historical charts bar-by-bar like standard Pine indicators do, fundamentally breaking standard `var` state memory (which is why old breakout indicators fail in screeners). This script utilizes bulletproof absolute lookbacks (`ta.highest` logic) to guarantee signals evaluate instantly under any server constraints. 

---
