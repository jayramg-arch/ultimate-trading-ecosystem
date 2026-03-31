# Weinstein & Minervini System Development Skills

This document serves as a centralized knowledge base and "skills" repository for the AI Assistant. It codifies the architectural patterns, debugging techniques, design standards, and workflows established during the development of the Weinstein Commander Suite, TradingView Pine Scripts, and associated automations.

## 1. Pine Script Development & Optimization

**Context:** Development of complex indicators like `Weinstein & Swing Pro Dashboard`, `Weinstein Fundamental X-Ray`, and unified strategy scripts.

- **State Persistence Management:** Always ensure state variables (like Trailing Stop Loss, `tm_tsl`) are properly reset upon chart symbol changes to avoid state leaking from previously viewed symbols.
- **Variable Scoping Checks:** Carefully monitor the scope of dynamic variables (e.g., `_b_c` for IBD RS Proxy calculations). Avoid trapping necessary variables inside protective `if` blocks (like `if str.length(bench500) > 1`) when they are required for later downstream calculations.
- **Dynamic Prompt Engineering:** When exporting data from Pine Script to external LLMs (like Gemini), ensure the prompt string reflects *live bar data* (Current Market Price, Broad Market Health) and uses descriptive, expanded terms rather than technical abbreviations.
- **Relative Strength & Dashboard Metric Clarity:** Ensure all dashboard metrics are unambiguously labeled. For example, explicitly refer to "Weekly Pullback Health" instead of just "Weekly Health," and distinctly track RS fields against multiple benchmarks (Nifty 50, Nifty 500, Sector).

## 2. Streamlit UI/UX Design ("Terminal-X" Aesthetic)

**Context:** UI overhauls for the `Weinstein Commander web app`.

- **Design Philosophy:** Prioritize a professional, modern "Terminal-X" look.
- **Layout & Navigation:** Execute designs using a glass-card layout constraint for modularity. Ensure primary navigation elements are clearly positioned (e.g., top of the left pane) and rendered as interactive buttons rather than raw bulleted lists.
- **Data Visualization Enhancement:** Implement comprehensive, interactive visual analytics that give immediate insight into portfolio and sector health, extending functionality beyond basic pie charts.
- **Conditional Styling (`fundamental_xray.py`):** Apply automated R/Y/G (Red, Yellow, Green) color-coding thresholds to critical fundamental metrics (Sector P/E, Sector Div Yield, Sector ROCE) to enable rapid visual analysis.

## 3. Data Integration & Financial APIs

**Context:** Handling broker connections and fundamental scanners.

- **Data Freshness & Cache Busting:** When displaying critical live financial data (like available cash balance from the Dhan API), ensure the script pulls fresh data and explicitly bypassing aggressive caching mechanisms.
- **API Payload Validation:** Verify strict key-value matching when extracting data from exchange/broker APIs (e.g., ensuring exact accuracy for keys like `availableBalance`).
- **Data Export Consolidation:** Standardize all output artifacts from scanner scripts. Ensure generated files (`FINAL_Hunter_Picks.csv`, `FINAL_Pullback_Picks.csv`, etc.) uniformly prepend `NSE:` to the Symbol column to ensure seamless imports into TradingView.

## 4. Browser Automation & Watchlist Sync

**Context:** Automating the synchronization of local screener outputs with TradingView watchlists.

- **DOM Interaction Integrity:** Use robust selectors and waits for interacting with dynamic web elements inside TradingView's UI.
- **Off-Screen Management:** Implement explicit scrolling logic to ensure elements (like duplicate watchlists out of the current viewport) are brought into the DOM and correctly handled/deleted.
- **State Cleanup:** Always verify that legacy or duplicate watchlists are purged prior to uploading fresh lists to prevent clutter and synchronization errors.
