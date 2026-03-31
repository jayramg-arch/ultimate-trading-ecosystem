# CLAUDE.md — Jay (Jayram G) | Trading System DNA & Agent Context

> **Purpose:** Persistent context file for Claude across Chat, Cowork, and Code.
> Place this file in the root of any project folder used with Cowork or Code.
> Last updated: March 2026

---

## Identity & Role

- **Name:** Jay (Jayram G)
- **Location:** India
- **Languages:** English (primary), Hindi
- **Role:** Independent systematic quantitative & technical trader
- **Operating style:** Institutional-grade risk management, solo operator

---

## Core Methodology

### Weinstein Stage Analysis (Primary Framework)
- **Anchor:** 30-week Moving Average (Weekly chart)
- Stage 1 (Basing) → Stage 2 (Advancing) → Stage 3 (Topping) → Stage 4 (Declining)
- Only trade Stage 2 breakouts; avoid/exit Stage 3–4
- Weekly-anchored Stage and Relative Strength (RS) logic is the foundation

### Minervini-Style Growth Stock Selection
- RS/VCP (Volatility Contraction Pattern) setups
- Relative Strength benchmarked against: **Nifty 50, Nifty 500, and Sector Indices**
  - 52-week RS: primary ranking
  - 3-month & 6-month RS: tactical/timing

### Alpha Score (5-Star Grading System)
- Composite score based on: **Stage + RS + Volatility**
- Drives stock selection and portfolio priority

---

## Trading Styles (NSE)

### Swing Trading
- **Timeframe:** 8–12 weeks
- **Target:** 5–8% per trade
- **Strategy:** Supply/Demand zones, S&R, Price Action
- **Charts:** Daily, 125-min, 75-min

### Positional Trading
- **Timeframe:** 6–8 months
- **Target:** 10–30% per trade
- **Strategy:** Weinstein Stage Analysis, RRG charts, Mansfield RS for sector/stock selection

### Common Rules
- **Risk per trade:** 1% of capital
- **Higher Timeframe (HTF):** Demand/Supply Zones (Weekly/Monthly)
- **Lower Timeframe (LTF):** Daily, 125-min, 75-min
- **Approach:** Pure price action — indicators for confluence only

---

## Risk Management (Institutional Grade)

- **Position Sizing:** Volatility-adjusted using 14-day ATR
- **Stop-Loss:** Mandatory 14-day ATR-based trailing stops
- **Formula:** Position Size = (Risk Amount) / (ATR × Multiplier)
- **No discretionary overrides** — system rules are final

---

## Structural Indicators (Unified Across All Platforms)

> **CRITICAL RULE:** All structural indicators MUST be mathematically identical across TradingView, Streamlit, screeners, and any other platform. Zero signal drift tolerance.

| Indicator | Specification |
|-----------|--------------|
| EMA 20 | On chart (Daily and above); EMA20(Daily) overlaid on 125/75-min |
| SMA 50 | Volume baseline |
| 30-Week MA | Weinstein Stage anchor (Weekly) |
| RS (Relative Strength) | Mansfield RS vs Nifty 50/500/Sector; 52-wk primary, 3/6-mo tactical |
| Volume Baselines | 50-SMA of volume |
| Stage Classification | Weekly-anchored, derived from 30-WMA slope + price position |

Additional confluence: Trendlines, Fibonacci, Order Flow, RSI, ATR

---

## The ULTIMATE Ecosystem

### [ULTIMATE] Indicator (TradingView / Pine Script)
- **Version:** v60.0+ (Pine Script v6)
- Alpha Screener (v60.4) — stock screening engine
- Unified Hybrid Trading Engine — synchronized signals across platforms
- Screener User Guide — logic and threshold documentation

### Weinstein Commander Web App
- **File:** `weinstein_commander_web_v2.5.py`
- **Stack:** Python / Streamlit
- Real-time portfolio health vitals dashboard
- Indian currency formatting: **₹1,23,456** (mandatory across all financial displays)

### GTT_Auto_Shield
- Automated stop-loss management system
- Built for **Dhan** brokerage platform
- Enforces ATR-based trailing stops programmatically

### TradingView Automation
- Watchlist synchronization engine
- Data scraping via Playwright/Selenium
- Keeps TradingView watchlists aligned with screener outputs

---

## Tech Stack

| Domain | Tools |
|--------|-------|
| Charting / Indicators | Pine Script v6 (TradingView) |
| Web Apps / Dashboards | Python, Streamlit |
| Browser Automation | Playwright, Selenium |
| Broker Integration | Dhan API |
| Data Analysis | Python (pandas, numpy) |

---

## Working Rhythm

| Day | Activity |
|-----|----------|
| **Weekend** | Strategic planning — Hunter Picks, EarlyBird Picks (fresh Stage 2 breakouts) |
| **Weekday** | Tactical execution — Pullback Picks (entries on retracements within existing setups) |

---

## Portfolio Context

- Active portfolio: ~21 stocks (variable)
- Exit strategy analysis during market drawdowns
- **Sell-to-Buy Capital Rotation Matrix** — systematic capital recycling from exits into new setups

---

## Output & Communication Preferences

### Analysis Output Requirements
- In-depth Technical Analysis with catalysts, thematic rationale, fundamentals, and sentiment
- Structured trade plans: **Entry / Stop-Loss / Target**
- Pure price action narrative — indicators referenced for confluence only

### Formatting Rules
- Indian currency: ₹1,23,456 (always, no exceptions)
- Use structured tables for comparisons and data
- Code outputs: well-commented, production-grade
- Pine Script: always v6 syntax (v60.0+)

### Tone
- Direct, professional, trader-to-trader
- No hand-holding — assume institutional-level understanding
- Flag risks and edge cases proactively

---

## Standing Instructions for All Modes

1. **Signal consistency is sacred.** Never introduce indicator calculations that diverge from the unified specifications above.
2. **Risk management is non-negotiable.** All trade plans must include ATR-based stops and volatility-adjusted sizing.
3. **Indian market context.** Default exchange is NSE. Default currency is INR (₹). Trading hours: 9:15 AM – 3:30 PM IST.
4. **Pine Script discipline.** Always use v6 syntax. Test for `na` values. Handle `request.security()` correctly for MTF logic.
5. **When building tools or dashboards:** Apply ₹ formatting, use the 5-star Alpha Score system, and align with Weinstein Stage logic.
6. **When analyzing stocks:** Lead with Stage + RS assessment, then price action, then fundamentals/catalysts.
7. **Portfolio decisions:** Reference the Sell-to-Buy rotation matrix and current portfolio context when relevant.

---

## File Placement Guide

```
your-project-folder/
├── CLAUDE.md          ← This file (root of any project)
├── scripts/
├── data/
└── ...
```

- **Cowork:** Select the folder containing this file as your working directory
- **Code:** Open the folder in VS Code or point Claude Code CLI to it
- **Chat:** Memory handles this automatically (but keep this file as the canonical source of truth)

---

*This file is the persistent memory and strategic DNA of Jay's trading environment. All Claude interactions should remain consistent with these established systems.*
