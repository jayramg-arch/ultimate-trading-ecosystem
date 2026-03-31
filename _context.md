# Project Specification & Domain Constraints

## 1. Domain Logic: Trading Strategy
**Role:** Swing/Positional Trader (NSE India)
**Risk Management:** Max risk 1% of total capital per trade.

### A. Timeframes & Horizons
* **Swing Horizon:** 8 to 12 weeks (Target: 5-8% profit).
* **Positional Horizon:** 6 to 8 months (Target: 10-30% profit).
* **Analysis Timeframes:**
    * *High:* Weekly/Monthly (Demand & Supply Zones).
    * *Low:* Daily, 125 Minutes, 75 Minutes.

### B. Technical Constraints & Indicators
The system must prioritize **Pure Price Action**; indicators are for confluence only.
1.  **Core Methodology:** Supply/Demand Zones, Support/Resistance (S&R).
2.  **Key Indicators:**
    * EMA 20 (Daily/Higher).
    * EMA 20 (Daily applied to 125/75 min charts).
    * RSI, ATR, Volume, Order Flow.
    * Fibonacci Retracements.
3.  **Positional Specifics:**
    * Stan Weinstein's Stage Analysis.
    * RRG Charts & Mansfield Relative Strength.

### C. Output Requirements for Analysis
Any generated trade plan must include:
* **Thematic Rationale:** Catalysts, fundamentals, and sentiment.
* **Trade Structure:** Clearly defined Entry, Stoploss, and Target.
* **Technical Deep Dive:** Analysis of the setup based on the indicators above.

---

## 2. Development Environment
**IDE:** Google Antigravity (VS Code Fork)
**AI Engine:** Gemini 3 (Pro/Flash)

### Workflow Constraints
* **Agent Management:** Use "Parallel Agent Swarming" for multi-file edits.
* **Context Injection:** This file (`_context.md`) serves as the immutable ground truth for strategy logic.
* **Skills:** Use `.antigravity/skills` for custom automation scripts (e.g., data fetching scripts).