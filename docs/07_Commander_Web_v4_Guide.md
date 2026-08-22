# Weinstein Commander Web v4.0 — Complete User & Trading Guide

> **What this is:** `weinstein_commander_web_v4.0.py` is a **Streamlit** desktop web app — your single command centre for the whole ecosystem. It is *not* a Flask "tabs" app (an earlier version of this guide described it wrongly). It runs locally, talks to Dhan (live book + GTT), yfinance (prices/fundamentals), NSE (option chain, breadth), Gemini (AI briefs), and your paid ET Prime / Moneycontrol Pro sessions, and it launches every backend Python script for you so you never touch a terminal.
>
> **How to read this guide:** It is in three parts.
> - **Part A — User Guide:** every Menu → Page → Tab → Field, what each field *is*, and the values you will see.
> - **Part B — Trading Guide:** how to *read* those fields to make a decision (Stage / RS / Alpha / risk lens).
> - **Part C — Workflows:** the exact click-path for a **Swing** trade (8–12 wks) and a **Positional** trade (6–8 mo).
>
> Convention throughout: money is shown the Indian way (₹1,23,456). NSE is the default exchange. Anything that *generates signals* is mathematically identical to the Pine surfaces — zero drift is sacred.

---

## 0. Launching & the Global Shell

### 0.1 Start the app
```powershell
cd C:\Users\jayra\Documents\GeminiVSCode
streamlit run weinstein_commander_web_v4.0.py
```
It opens in your browser (default `http://localhost:8501`). Keep it running through the trading day. It is a **single-operator local app** — there is no login.

### 0.2 The Top Status Bar
A thin strip pinned above every page. Three live readouts:

| Field | Meaning | How to read it |
|---|---|---|
| **System status** | `READY` / `AUTH EXPIRED` / degraded | `AUTH EXPIRED` = your Dhan token died (they expire **daily**). Live book, GTT and order entry are dead until you repaste the token (see §0.4). |
| **India VIX** | Live volatility index | <13 complacent · 13–16 normal · 16–20 caution · >20 fear. Sizing should shrink as VIX rises. |
| **FII flow** | Latest FII net (₹ Cr) | Green = foreign buying, red = selling. The single most important daily flow number for NSE. |

### 0.3 The Sidebar (left rail)
Top-to-bottom:

1. **🤖 Run Auto-Pilot** — fires `run_pipeline.py`, the full daily watchlist pipeline (scanners → fundamentals → Golden Matcher → watchlist sync). This is the one-click "make my watchlists" button. Runs in a **separate console window**; takes 5–10 min. Output lands in `Generated_Watchlists/` and the `FINAL_*.csv` files.
2. **Navigation groups** — six labelled groups, each a stack of page buttons (full map in §1). The active page button is highlighted.
3. **🔑 Token detail** (expander, bottom) — shows token expiry; paste a fresh Dhan Access Token here (from web.dhan.co → API → Access Token) and click **💾 Save Token**. Writes to `.env`, then reload the app.
4. **📱 Mobile / Standalone** — links to the slim standalone pages (`Home`, `X-Ray`, `Journal`, `Autopsy`) designed for phone use.

### 0.4 When something says "AUTH EXPIRED"
Repaste the Dhan token in the sidebar expander → Save → reload. Everything that needs the broker (Portfolio vitals, GTT view, Sniper order, Command Center launchers) comes back. Screeners and analysis pages work **without** a token (they use yfinance/NSE).

### 0.5 The two button styles you'll see everywhere
- **Launcher buttons** (multi-line, end in "→ Run / Launch / Generate") fire a **backend script in a separate console**. The web page does not block — watch the spawned console for progress, then come back and refresh.
- **Inline actions** (Run Screener, Pull Sentiment, Add Alert) run **inside** the page with a live progress bar.

---

## 1. Navigation Map (Menu → Sub-Menu)

The sidebar groups 18 pages by *when in your day you use them*:

| Group | Page | One-line job |
|---|---|---|
| 🩺 **STATE OF MARKET** | 🌐 **MACRO** | Global risk environment, VIX, currencies, commodities, sector RRG |
| | 📈 **BREADTH** | Nifty 500 internals — regime score, A/D, McClellan, stage map |
| | 📰 **NEWS** | Live RSS + paid ET/MC analyst recos + per-stock filter |
| 📅 **DAILY INTEL** | 🌅 **PRE-MARKET** | 8:30 AM hub — overnight pulse, calendar, options, AI brief |
| | 📊 **DASHBOARD** | Your open-book health, live P&L, correlation risk |
| | 🌙 **POST-MARKET** | EOD summary, provisional FII/DII, top movers |
| 🔍 **DISCOVERY** | 🎯 **HUNTER** | The screening engine — Chartink, Bull, Recovery, Matcher, X-Ray batch |
| | 📋 **WATCHLIST** | Generate/sync watchlists, Smart Rank, sector DB, replay, track record |
| | 🧬 **X-RAY** | Single-stock deep fundamental dive + scorecards + news |
| | 🪙 **ETF** | ETF rotation, asset-class regime, liquidity scoring |
| | 🗂️ **PORTFOLIO** | Factor exposure, VaR/CVaR, stress tests, walk-forward backtest |
| ⚡ **EXECUTION** | ⚡ **COMMAND** | Live trade management — exit/trail engines, GTT, alerts, agents |
| | 📐 **OPTIONS** | Live NSE option chain — PCR, max pain, OI, IV skew |
| | 📺 **TV SIDECAR** | Quick-look quote + key levels + RSI/MACD chart beside TradingView |
| 🔬 **ANALYSIS** | 🔬 **AUTOPSY** | Closed-trade post-mortem + performance attribution |
| | 📈 **BACKTEST** | Forward-return analysis of screener signals |
| | 🧪 **AI LAB** | Gemini pre-flight scoring, analysis, auto-pilot, weekly report |
| 📁 **RECORDS** | 📓 **JOURNAL** | Opens the full trade journal app (`dhan_journal_v7.py`) |

> **Daily reading order** (per your Bible): STATE OF MARKET first (never trade against the tape) → PRE-MARKET → DASHBOARD → DISCOVERY → EXECUTION. ANALYSIS pages are for evenings/weekends.

---

# PART A — USER GUIDE (every page, tab & field)

## 🩺 STATE OF MARKET

### 🌐 MACRO — Macro Radar
*Global risk environment // VIX // Currencies // Commodities.* Four tabs.

**Tab: 🌍 Overview**
- **Global Macro Snapshot** — a metric tile per instrument (S&P, Nasdaq, Nikkei, Dow, Gold, Crude, USDINR, US10Y, etc.). Each shows last value + **1-month % change** as the delta.
- **Regime Indicators** — quick risk-on/risk-off read of the macro complex.
- **12-Month Trend — Normalised to 100** — every series rebased to 100 at the start so you can compare relative performance on one axis.

**Tab: 📊 Global Indices** — Full board of world indices (LTP, % change, 52W H/L) in a table.

**Tab: 💰 FII/DII Flows** — Cumulative foreign vs domestic institutional flow chart over time.

**Tab: 🔄 Sector RRG** — Relative Rotation Graph of the 12 NSE sector indices vs Nifty 500. Quadrants: **LEADING** (strong & improving), **WEAKENING**, **LAGGING**, **IMPROVING**. *This is the sector-level filter you apply before drilling to stocks.* (RRG maths is locked — read only.)

### 📈 BREADTH — Market Breadth Engine
*Nifty 500 internals.* Five tabs.

**Tab: 🚦 Regime** — **Market Regime — Composite Score**. A single composite (built from breadth, A/D, McClellan, % above MAs) that classifies the tape: roughly RISK-ON / NEUTRAL / RISK-OFF. **This is your master gate** — it decides whether bull setups or recovery setups are in season.

**Tab: 📊 Overview — Nifty 500 Universe** (8 metric tiles):
| Field | What it tells you |
|---|---|
| **Above SMA 50** | % of N500 above 50-day MA (short-term participation) |
| **Above SMA 150** | % above 150-day MA (intermediate) |
| **Above SMA 200** | % above 200-day MA (long-term health — the big one) |
| **Stage 2** | % of universe in Weinstein Stage 2 (advancing) |
| **New 52W Highs / Lows** | Count of fresh highs vs lows |
| **A/D Ratio** | Advancers ÷ Decliners (>1 bullish) |
| **High/Low Ratio** | New-highs ÷ new-lows |

**Tab: 🏭 Sectors** — Sector Breadth: each sector's stage tally (🟢 Stage 2 / 🟡 Stage 1 / 🟡 Stage 3 / 🔴 Stage 4). **Lookback period** selectbox controls the window.

**Tab: 📉 McClellan** — Oscillator (+ = improving breadth), Summation Index (trend of breadth), Signal (text verdict), Breadth Thrust EMA10. Reads `mcclellan_state.json`; warns if data is >7 days stale.

**Tab: 🗺️ Stage Map** — Full Stage Distribution histogram across the Nifty 500.

### 📰 NEWS — Financial News & Sentiment
**Top controls:** **Max per feed** (10/15/20), **Sources** multiselect (ET, Moneycontrol, Business Standard, LiveMint, NDTV Profit). **Headline metrics:** Headlines count, 🟢 Bullish, 🔴 Bearish, ⬜ Neutral, **Sentiment** (net % with a label). Three tabs:
- **📰 Market News (Free RSS)** — headlines sorted by recency, keyword-sentiment colour-coded.
- **💎 ET Prime + MC Pro** — your *paid* analyst recos & news (needs cookies fresh via `setup_paid_news_cookies.py`; a 🟢/🟡/🔴 cookie-status row shows freshness). Cards colour-coded by analyst action (Strong Buy → green, Sell → red) with brokerage badges.
- **🔍 Stock Filter** — type a symbol to see only its news.

---

## 📅 DAILY INTEL

### 🌅 PRE-MARKET — Pre-Market Intelligence Hub *(use ~8:30 AM)*
Five tabs:
- **📋 Brief** — the **canonical** full AI pre-market briefing (single source of truth; the Dashboard only shows a 300-word snippet of this).
- **🌍 Global** — Overnight pulse: Equity Indices, Commodities, Currencies & Bonds.
- **📅 Calendar** — Economic & corporate events calendar.
- **📐 Options** — Pre-market Nifty options snapshot: **PCR (OI)**, **PCR (Vol)**, **Max Pain**, **ATM IV**, Total Call/Put OI, **Call Wall / Put Wall** (strongest OI strikes = magnet/resistance & support).
- **💎 ET + MC Pro** — paid feed filtered to opening/overnight/GIFT-Nifty/morning-brief headlines.

### 📊 DASHBOARD — Mission Dashboard
*Your open-book at a glance.* No tabs — a stacked layout:

1. **📰 AI Brief — Quick Preview** (expander) — 300-word snippet of the latest pre-market brief; button to open the full one, or generate a quick ~30s brief.
2. **Quick Launch → 📝 Market Briefing** — fires `workflow_strategic_briefing.py` (produces a PDF strategic analysis + sector rotation).
3. **Open Portfolio Health Vitals** (8 tiles):
   | Tile | Definition |
   |---|---|
   | Unrealized P&L | Total open P&L (₹) |
   | Return on Deployed | Open P&L ÷ deployed cost |
   | Portfolio Return | Open P&L ÷ total capital |
   | Current Value | Market value of open positions |
   | Win Rate | % of open positions in profit (W/L count) |
   | Avg Gain % / Avg Loss % | Mean of winners / losers |
   | Risk/Reward | Avg Gain% ÷ |Avg Loss%| (∞ = all green) |
4. **🔴 Exit Signal Scan** (expander) — runs `exit_signal_engine` on open positions: checks SL proximity, R-multiple, Weinstein stage decay, RS fading. Flags positions needing **ACTION** vs healthy. Regime-aware.
5. **Portfolio Analytics — Closed Trade Performance** (6 tiles): Sharpe, Sortino, Max Drawdown (₹ & %), Profit Factor, Expectancy/trade, Total Realized.
6. **Portfolio Heatmap** (treemap, sized by capital deployed, coloured by P&L%) + **Alpha Benchmarking vs Nifty 500** (your equity curve vs ^NSEI).
7. **Active Positions — Live P&L** table: Symbol, Entry, LTP, P&L ₹, P&L %, **SL Status** (🔒 LOCKED if SL>entry / ⚠️ BREACHED / distance%), Dist Tgt %, **SL (ATR×)** = how many ATRs your stop sits below price, Days held.
8. **Portfolio Correlation Risk** (expander) — **Diversification Score /10**, **Shadow Concentration** pairs (positions secretly correlated → effective N is smaller than you think), and the full correlation heatmap.

### 🌙 POST-MARKET — Post-Market Analysis *(use ~4:30 PM)*
Four tabs:
- **📋 Summary** — AI EOD summary.
- **💰 FII/DII** — Provisional flows: FII Net (latest), DII Net (latest), FII 5-Day Sum, DII 5-Day Sum.
- **📊 Movers** — **Universe** radio (📂 My Holdings / 📊 Nifty 50 / 🔀 Both) → Top Gainers & Top Losers tables.
- **💎 ET + MC Pro** — paid feed filtered to closing-bell/EOD/wrap headlines.

---

## 🔍 DISCOVERY

### 🎯 HUNTER — Stock Discovery Engine
The screening workhorse. **Six tabs** in workflow order.

**Tab 1: 🔍 Chartink Scans** — launcher buttons (each runs `chartink_scanner_pro.py` with a strategy number, output to `Generated_Watchlists/`):
- *Positional:* **Stage 2 Hunter** (long-horizon stage breakout), **Early Birds Accumulation** (early-stage accumulation).
- *Swing:* **Stage 2 Pullback** (pullback within uptrend), **Strong Leaders** (RS momentum leaders).
- *Recovery (post-shock):* **REV-RS** (RS survivor breaking 20D high), **REV-CB** (climax-bottom panic-volume bounce), **REV-EARLY** (near golden cross, VCP base). *Use when market is ≥7% off 52W high.*

**Tab 2: 🧬 Fundamentals** — two launchers: **🌐 Fetch Screener.in Data** (`screener_fetcher.py`) → **⚙️ Process HTML to CSV** (`screener_processor.py`). This produces the fundamental snapshot the Matcher needs.

**Tab 3: 🥇 Golden Matcher** — **🏆 Run Golden Matcher** (`brute_force_match_pro.py`) combines technical scans (Layer 1) with fundamental conviction (Layer 2) → `FINAL_*_Picks.csv`. Shows last-generated freshness (warns if >28h old). Below: **Ultimate Golden Meta-Ranking** — concatenates all four FINAL files, ranks by **Conviction** (High=3/Med=2/Low=1) then %Chg. **Filter by Strategy** selectbox narrows to one bucket. Includes an **Analyst Sentiment** panel for the picks.

**Tab 4: 🐂 Bull Screener** — Python port of the 6 Pine catalysts (pure price-action).
- **Symbol Source** radio: 📂 Default (`FINAL_COMBINED_BULL_PICKS.csv`) / 🌐 Nifty 500 (backtest-aligned) / ⚡ F&O Basket (~210) / ⬆️ Upload CSV/TXT.
- **Run Bull Screener** (live progress bar). 🌐/⚡ runs are *strict* (full catalyst gate); upload keeps tracker mode.
- **Filters:** **Catalyst Filter** selectbox + **Min Score** (0–100).
- **Catalysts:** POS-AC (OBV accumulation), POS-BO (Stage-2 breakout — your core positional edge), SWG-PB (EMA-20 pullback), SWG-BO (VCP breakout), SWG-REV (mean reversion), GAP-GO (gap & go).
- **Exports:** filtered CSV + **Pine symbol array**.
- **Catalyst Drill-Down** — pick one catalyst, see only its signals with all columns.
- **Analyst Sentiment** — pull Buy/Hold/Sell consensus for top-N by Score.

**Tab 5: 🔄 Recovery Screener** (Python edition; hold-window aware, safe post-market/weekend).
- **Symbol Source** radio: 📂 Default (Chartink CSVs 5-7) / 🌐 Nifty 500 / ⚡ F&O / ⬆️ Upload.
- **Run** → results with **Filters:** Signal (All Actionable / =4 REV-EARLY / =3 REV-RS / =2 REV-CB / =1 CB-Watch / Show All), **Min Mansfield RS**, **Max Signal Age** (trading days, default 5).
- **Output columns:** Symbol, Signal_Label, Signal_Date, **Age_Days**, Score, **RFF_Score** (fundamental gate, ≥4 = strong), Weinstein_Stage, Mansfield_RS, RSI14, Rel_Vol, Entry, SL, T1, RR_T1, SL%, T1%, Details. Pine-array export available.

**Tab 6: 🧬 X-Ray Screener** (batch deep fundamentals — Weinstein Fundamental X-Ray v2.2).
- **Symbol Source:** 📂 Default (Generated Watchlists) / ⬆️ Upload.
- **Filters:** **Min Overall Rating** (0–17), **Min Piotroski Score** (0–9).
- Plus a single-symbol **Quick Look** box (analyst sentiment + paid news) at the top.

### 📋 WATCHLIST — Watchlist Sync
**Top of page:** **🤖 Latest Auto-Pilot Output** metrics (FINAL_*.csv files present, total rows, freshest file age) + **🩺 Pipeline Health & Targeted Regeneration** (re-run a single broken phase rather than the whole pipeline). **Eight tabs:**

- **🗂️ Generate** — *1. Local Generation* (**📁 Generate CSVs**, `watchlist_manager.py`); *2. TV Pine Screener Generator* (upload a `.txt` watchlist → Pine symbol array).
- **☁️ Sync Cloud** — External cloud sync (**💸 Sync to Strike.Money**) + Email Dispatches.
- **📊 Smart Rank** — **Weinstein Setup Scorer**. **Symbol source** radio + **Lookback period** (3mo/6mo/1y) → ranks stocks; metrics: Stocks Ranked, Stage 2 count, Grade A+/A count, Top Score. (2-decimal numeric formatting.)
- **🗄️ Sectors DB** — **Unified Sector Database** stats (Symbols, Sectors, Aliases, coverage), Sector Index Coverage, a **Lookup** tool, and **Maintenance** (rebuild).
- **💾 Data Cache** — **Unified OHLCV Cache** stats: Cache Entries, Fresh, Expired, Disk Size (MB), Format, Parquet OK + Maintenance (clear/refresh).
- **📈 Pipeline Status** — Auto-Pilot phase report: Phases OK, Failed, Skipped, Running, Total Time.
- **⏱️ Replay** — **Screener Replay — As-of-Date Backtest**: pick a **date**, a **screener**, and **forward days** → see what that screener *would* have picked and how those picks performed (Picks, Win rate, Avg return, Benchmark, alpha). Below it: **12-Month Validation Backtest** (`validation.py`) with **Months**, **Forward days**, **Top-N**, **catalyst-windows** checkbox → Anchor Avg Alpha, Median Alpha, Alpha Hit Rate, Avg Win Rate, Best/Worst Anchor.
- **📒 Track Record** — **Live Pick Track Record**: Total Picks Logged, Evaluated, First/Last Pick, plus a per-screener summary (Picks Evaluated, Win Rate, Avg/Median Return) at a chosen forward horizon.

### 🧬 X-RAY — Stock X-Ray (single-stock deep dive)
Type an **NSE symbol** at top. Six tabs:
- **📈 Snapshot** — Price, Market Cap, 52W vs High, Beta; **Valuation** (P/E, Fwd P/E, P/B, EV/EBITDA, P/S); **Profitability** (Net & Op Margin, ROE, ROA, Div Yield); **Balance Sheet** (Revenue TTM, Net Income, Debt/Equity, Current Ratio).
- **📑 Income Statement** — full statement(s).
- **📊 Quarterly Results** — quarterly table + Revenue & Profit trend chart.
- **🎯 Scorecard** — **Minervini Score /8** + Overall breakdown + **Piotroski F-Score /9**.
- **🔍 Screen** — Multi-stock fundamental screener (Max P/E, Min ROE%, Max Debt/Eq, Min Net Margin%, universe selector).
- **📰 News** — Matching articles + NSE corporate announcements + **Analyst Sentiment + Paid News** (Strong Buy/Buy/Hold/Sell/Strong Sell).

### 🪙 ETF — ETF Trading System
Four tabs (parallel pipeline for NSE ETFs; alpha source = rotation, not stock-picking):
- **🎯 Top Picks** — regime-aware ETF picks.
- **🔄 Sector Rotation** — composite RS (60% 12W + 40% 4W). Quadrant counts: 🟢 OVERWEIGHT / 🟡 NEUTRAL+ / 🟠 NEUTRAL− / 🔴 UNDERWEIGHT.
- **📊 Asset-Class Regime** — RISK_ON / GOLD_LED / INTL_LED / RISK_OFF / MIXED detector + Risk-On asset-class count + allocation donut.
- **💧 Liquidity & Universe** — per-ETF scoring; tiles: Universe size, Stage 2 count, LEADING count, **Liquid (≥₹2 Cr/day)** count. *Liquidity is the #1 ETF risk — half of NSE ETFs trade thin.*

### 🗂️ PORTFOLIO — Portfolio Analytics
**Source** radio (live holdings / manual). Four tabs:
- **📊 Overview** — Positions, Portfolio Value, Total Cost, Unrealised P&L; All Holdings, Top 5, Sector Allocation. (Optional **portfolio value input**.)
- **⚠️ Risk Metrics & Factor** — controls: **VaR Confidence** (0.90/0.95/0.99), **Lookback** (126/252/504 d), **Factor Period** (6mo/1y/2y). Outputs: **VaR** (1-day %/₹, CVaR, 10-day, Parametric), Annual Vol/Return, Max DD; **Factor Exposure vs Nifty50**: Portfolio Beta, Correlation, Tracking Error, Alpha (annual), Sharpe, Sortino; per-symbol beta.
- **🌪️ Stress** — Historical stress scenarios (replays crashes against your book).
- **🔁 Walk-Forward** — Weinstein Stage-2 backtest: **Start Date**, **Rebalance** (Weekly/Bi-Weekly/Monthly), **Universe** (holdings/Nifty50/Custom) → Strategy CAGR vs Benchmark CAGR, Sharpe, Max DD, Avg Positions.

---

## ⚡ EXECUTION

### ⚡ COMMAND — Command Center
*Live trade management.* Three tabs.

**Tab: ⚡ Active Ops** — launcher buttons for the live agents:
- **🎯 Sniper Entry AI v2** (`sniper_trigger.py`) — order execution with AI analysis.
- **🛡️ GTT Auto-Shield** (`gtt_auto_shield.py`) — auto-protect holdings with journal-derived ATR stops on Dhan.
- **📲 Telegram Sentinel** (`telegram_sentinel.py`) — mobile market monitoring.
- **🤖 Market Monitor Agent** (`market_monitor_agent.py`) — live intraday scans + Telegram alerts.
- **🔌 Dhan Webhook Gateway** (`dhan_tv_webhook.py`) — exposes port 8000 via ngrok for TradingView alert → auto-order.
- Inline engines: **🚨 Scan Exit Signals** (`exit_signal_engine.py`), **E-02 Trailing Stop Engine**, **Portfolio Rotation Guard** (`portfolio_rotation_guard.py` — grades every open position), and **GTT Orders — Live View** (**🔄 Fetch GTTs** pulls your live Dhan GTT book).

**Tab: 📒 Ledger** — External Apps + **Live Trade Ledger** (**🔄 Sync to TV** pushes the active ledger into the Pine Dashboard portfolio slots).

**Tab: 🔔 Price Alerts** — **Price Alert Manager**: add an alert (symbol, **condition** selectbox above/below, **price**), **⚡ Check Prices Now**, active-alerts list (🔕 Pause / 🗑️ Remove), and Fired History (🧹 Clear).

### 📐 OPTIONS — Options Desk
Three tabs:
- **📡 Live Chain** — **Symbol** (NIFTY/BANKNIFTY/stock) + **Expiry** selectboxes, **Auto-load** checkbox. **Live Snapshot:** Spot, **PCR**, **Max Pain**, Total CE OI, Total PE OI. **Strike range** slider → **OI by Strike**, **Change in OI (buildup)**, **IV Skew**, and a near-ATM option-chain table.
- **🔗 External Tools** — direct NSE option links.
- **📚 Quick Reference** — key concepts cheat-sheet (PCR, max pain, OI buildup).

### 📺 TV SIDECAR — TradingView companion
**Symbol** text input (auto-appends `.NS`) + **Timeframe context** (Daily/Weekly/15min/60min). Shows a **quote strip** (LTP, Prev Close, 52W H/L, Volume, **Vol/Avg**), **Key Technical Levels** (price vs SMA20/50/200 with 🟢/🔴 and distance%, 10D High/Low, ATR(14)), and a **multi-panel chart** (Price + Volume + RSI(14) + MACD(12,26,9)). A fast read-out to glance at while your real chart is in TradingView.

---

## 🔬 ANALYSIS

### 🔬 AUTOPSY — Trade Autopsy
*Closed-trade post-mortem.* Five tabs:
- **📊 Overview** — Total Trades, Win Rate, Total Realized, Sharpe, Profit Factor, Expectancy/trade, Max Drawdown, Avg Win ₹, Avg Loss ₹; Holding-period analysis (avg days all/winners/losers); Equity Curve.
- **📅 Calendar** — Monthly P&L calendar + table.
- **🏭 Sectors** — Sector P&L breakdown + Sector Coverage (traded vs untraded of all 19 NSE sectors).
- **🎯 Trade Quality** — Trade quality distribution + Win/Loss streak analysis (Max Win Streak, Max Loss Streak).
- **📐 Attribution** — **Performance Attribution** (`performance_attribution.run_attribution()`): headline realized metrics (Trades alpha-only, Win Rate, Total Realized, Expectancy, Profit Factor, Avg ROI) + a **data-quality/honesty line** (cash-park excluded, quarantined incomplete rows, snapshot coverage) + per-dimension tables led by the **entry-signal drivers** (setup / stage / alpha / RS / conviction). *Reads the journal DB directly, no network.*

### 📈 BACKTEST — Signal Backtest Lab
**Signal Source** radio (recovery results / upload). **Backtest Configuration** → per **hold** horizon: Win Rate, Avg/Median Return, Best/Worst signal, **By Edge Type** breakdown, return distribution, return-vs-signal-age, cumulative average return, and the raw backtest log.

### 🧪 AI LAB — AI Laboratory
Four tabs:
- **🛫 Pre-Flight** — **AI-Trade Proposer**: enter symbol, **Entry Price**, **Risk ₹** → **🛫 Run Analysis** returns Weinstein Grade, Quant Score /100, Suggested SL, Rec. Quantity. Then **MISS-8 Atomic Entry + GTT** (one click places entry + protective GTT via `gtt_auto_shield.py`).
- **🤖 Generative** — two sub-tabs: *Stock Analysis* (Gemini; **Report depth** Quick 100w / Full 250w / Trade Setup, optional entry price) and *Portfolio Review* (AI review of closed trades). Cache-clear buttons.
- **⚙️ Workflows** — **🤖 Run Full Auto-Pilot** (same as sidebar) + **Sniper Entry web interface**: **Entry Price**, **Stop Loss**, **Max Risk %** (0.25–2.0 slider) → Quantity, Trade Value, Risk/Trade ₹, Risk %, Target 2R/3R, and **🚀 Execute CNC Order via Dhan**.
- **📆 Weekly Report** — generates the weekly market report.

## 📁 RECORDS

### 📓 JOURNAL
Sidebar button launches the standalone **`dhan_journal_v7.py`** Streamlit app (separate window) — the full trade journal with entry-signal snapshots. It is kept in sync with your Dhan book by the scheduled `TradingJournal_DhanSync` task (4:30 PM IST daily), so the journal you open is already reconciled.

> *Legacy note:* a `FUNDAMENTALS` page still exists in code but was **absorbed into X-RAY** (10 May 2026) and is not in the sidebar. Use X-RAY → Snapshot/Scorecard/Screen instead.

---

# PART B — TRADING GUIDE (how to read the fields)

The app surfaces the same DNA everywhere: **Stage → RS → Volatility → Alpha → Risk**. Read in that order.

### B.1 The decision stack (top-down)
1. **Tape (MACRO + BREADTH):** Is the **Regime Composite** risk-on? Is **% above SMA200** rising? Is **A/D** > 1 and McClellan positive? *If the tape is risk-off, only Recovery setups (RFF≥4, beaten-down) earn a look; bull breakouts are low-probability.*
2. **Sector (MACRO → Sector RRG):** Only hunt stocks whose sector is **LEADING** or **IMPROVING**. Skip stocks in LAGGING sectors regardless of their own chart.
3. **Stock catalyst (HUNTER → Bull/Recovery):** Match the catalyst to your style (see B.3).
4. **Quality (X-RAY scorecards):** Minervini /8 and Piotroski /9 confirm the fundamental backbone. RFF≥4 is the recovery gate.
5. **Location + trigger (TV SIDECAR / your TradingView chart):** Price at a fresh demand zone, then a *closed* trigger bar. **Never buy at the zone on the touch — wait for the confirmed close** (your #1 historical mistake).
6. **Risk (AI LAB Sniper / Pre-Flight):** Size off ATR so risk = a fixed % of capital. Place the protective GTT the same evening.

### B.2 Reading the key fields
- **Weinstein Stage:** 1 Basing → 2 Advancing (only buy here) → 3 Topping → 4 Declining (exit/avoid). The Dashboard Exit Scan flags Stage decay on open positions.
- **Mansfield RS:** >0 and rising = outperforming the benchmark. Primary ranking input. RS *fading* on an open position is an early exit tell.
- **Alpha Score (0–100) / Stars:** composite of Stage + RS + volatility + catalyst. Rank candidates by this.
- **RRG Quadrant:** LEADING > IMPROVING > WEAKENING > LAGGING for new longs.
- **SL (ATR×):** how many ATRs your stop sits below price — keeps stops volatility-normalised. Your catalyst-aware multipliers: POS≈4.0×, WYC≈3.5×, REV≈2.5×, SWG≈1.5×.
- **RFF Score (recovery):** fundamental backbone of a beaten-down name; **≥4/6 required** — quality on sale, not falling knives.
- **Correlation / Diversification Score:** if shadow-concentration pairs appear, your real risk is concentrated — trim before adding a correlated name.
- **VaR/CVaR (Portfolio):** the ₹ you can lose on a bad day at chosen confidence — sanity-check against your risk budget.

### B.3 Catalyst → trade-style map
| Catalyst | Style | Horizon | Notes |
|---|---|---|---|
| **POS-BO** (Stage-2 breakout) | Positional | 6–8 mo | Your validated core edge (+7.67%, PF 3.14 in backtests). Wide ATR stop; let it breathe. |
| **POS-AC** (OBV accumulation) | Positional | 6–8 mo | Institutional footprint before the move. |
| **SWG-PB** (EMA-20 pullback) | Swing | 8–12 wk | Best in confirmed up-trends only (regime-sensitive). |
| **SWG-BO** (VCP breakout) | Swing | 8–12 wk | Tight stop; respect the pivot. |
| **SWG-REV** (mean reversion) | Swing | days–wks | Counter-trend; smallest size. |
| **GAP-GO** | Swing/intraday | short | Needs the 3× volume + strong close. |
| **REV-CB / REV-RS / REV-EARLY** | Recovery | 90–180 d | Only in risk-off/recovering tape; RFF≥4 mandatory. |

> **Lesson baked into the system:** *the signals find edge; tight stops on long holds give it back.* Match stop width to the catalyst's horizon, and judge results per-family, never pooled.

---

# PART C — WORKFLOWS

## C.1 Swing Trade (8–12 weeks, target 5–8%)
1. **Morning tape check** — MACRO (VIX, Sector RRG) + BREADTH (Regime, A/D). Proceed only if risk-on / neutral.
2. **Generate fresh lists** — sidebar **🤖 Run Auto-Pilot** (or HUNTER → Chartink → *Stage 2 Pullback* / *Strong Leaders*).
3. **Screen** — HUNTER → **🐂 Bull Screener** → Source = Default or F&O → filter **Catalyst = SWG-PB or SWG-BO**, sort by **Score**.
4. **Sector gate** — drop any pick whose sector isn't LEADING/IMPROVING on the RRG.
5. **Quality** — X-RAY → Scorecard (Minervini /8) on the top 3–5 names.
6. **Location & trigger** — open the name in TradingView; use **TV SIDECAR** to confirm price is above SMA20/50 and near a fresh daily demand zone. **Wait for a closed trigger bar.**
7. **Size & protect** — AI LAB → **Sniper** (Entry, Stop = below the zone, Max Risk 0.25–1%). Place a **buy-stop above the trigger bar**, not a limit at the zone. Set the GTT the same evening (GTT Auto-Shield).
8. **Manage** — DASHBOARD Exit Scan + COMMAND Trailing Stop Engine. Trail under structure; take partials into the 5–8% zone.

## C.2 Positional Trade (6–8 months, target 10–30%)
1. **Regime + sector** — same top-down, but you want **% above SMA200 rising** and a sector in early **LEADING** (Stage 2 sector).
2. **Hunt the core edge** — HUNTER → Bull Screener → **Catalyst = POS-BO** (or POS-AC) on the **🌐 Nifty 500** source (backtest-aligned). Rank by Alpha Score.
3. **Stage confirm** — the name must be a clean **Weinstein Stage 2** (weekly, above rising 30-WMA). Verify on the weekly chart.
4. **Fundamental backbone** — X-RAY → Minervini /8 + Piotroski /9; reject weak balance sheets.
5. **Entry** — buy the breakout *or* the first pullback to the breakout/EMA-20; wide **ATR≈4×** stop so normal volatility doesn't shake you out.
6. **Size** — 1% (or your current 0.25% freeze-mode) risk; respect the wide stop → smaller share count.
7. **Hold & review** — let it run months. Weekly review via WATCHLIST → Track Record and DASHBOARD vitals. Exit only on **Stage 3 confirmation**, RS breakdown, or the trailing stop — not on noise.
8. **Rotation** — when a position hits Stage 3/4 (Exit Scan flags it), use the Sell-to-Buy logic: free that capital into the highest-conviction Golden Pick.

## C.3 End-of-day & weekend
- **EOD:** POST-MARKET (FII/DII, movers) → DASHBOARD vitals → COMMAND (confirm GTTs live) → set tomorrow's alerts.
- **Weekend:** AUTOPSY (what worked, by catalyst/sector) → BACKTEST/Replay (is the edge holding?) → AI LAB Weekly Report → refresh watchlists.

---

# PART D — SUB-MODULE REFERENCE (every Python file behind the app)

The web app is a thin UI shell. The real work lives in ~55 supporting modules. They come in two flavours:
- **In-process imports** — called *inside* the Streamlit process; their functions return DataFrames/dicts the UI renders live.
- **Launched scripts** — fired via `launch_script()` as a **separate console subprocess**; they write CSV/DB/PDF artifacts the UI reads back.

Below, grouped by role.

## D.1 Data & Infrastructure Layer
| Module | Type | Functionality |
|---|---|---|
| **data_provider.py** | import | The single chokepoint for all OHLCV. Rate-limited, on-disk cached (Parquet when `pyarrow` present, CSV fallback). Wraps `yf.download` in a daemon thread with a hard timeout (`YF_DOWNLOAD_TIMEOUT_S`) so a yfinance brownout degrades *one* place, not the whole app. Every screener/analytics module routes through it. |
| **sector_lookup.py** | import | Hot-path **read** API for the unified `sectors.db`. `get_sector()`, `get_sector_index()` (e.g. `NSE:CNXIT`), `get_sector_name()` (e.g. "Nifty IT"). In-memory cached so the SQL cost is paid once per process. Used by Dashboard heatmap, screeners, rotation guard, journal. |
| **sector_manager.py** | launched | The **write/maintenance** side of `sectors.db` (v2.0, SQLite). Single source of truth for stock→sector mappings shared with the Pine Dashboard family. Args: `refresh-yf` (re-pull from yfinance), `audit` (coverage report). |
| **dhan_symbols.py** | import | Downloads the Dhan Scrip Master CSV and builds `securityId ↔ NSE ticker` maps (`get_nse_id_map`, `get_nse_secid_to_symbol`). Required to translate broker IDs (which carry no ticker) into symbols — fixed the journal-reconcile "silent empty" bug. |
| **pine_generator.py** | import | `generate_pine_code(symbols)` — turns a symbol list into a `NSE:`-prefixed Pine `array.from(...)` block for TradingView import. Powers the "Export Pine Array" buttons. |

## D.2 Broker / Authentication / Execution
| Module | Type | Functionality |
|---|---|---|
| **dhan_auth.py** | import | Auto-refreshes the Dhan access token via TOTP+PIN (reads `DHAN_CLIENT_ID/PIN/TOTP_KEY` from `.env`). Exposes `ensure_valid_token`, `get_valid_token`, `token_status`, `refresh_token`, `get_dhan_client`. Drives the sidebar token strip. |
| **broker_options.py** | import | Dhan-primary option-chain fetch → `(calls_df, puts_df, spot, expiries)`, same shape as the NSE parser. `dhan_subscription_check` gates the live-chain feature. |
| **gtt_auto_shield.py** | launched | Reads journal SL levels and **places/updates protective GTT orders on Dhan** (ATR-based trailing stops). The mechanical enforcement of "mandatory ATR stops". |
| **sniper_trigger.py** | launched | Order-execution path with an AI pre-flight banner — position-size + place a CNC entry on Dhan. |
| **master_portfolio_sync.py** | launched | Pulls the live Dhan book and **injects holdings into the Pine Dashboard's portfolio slots** (uses `sector_manager` for sector tagging). |
| **dhan_tv_webhook.py** | launched | A FastAPI/uvicorn server (port 8000, exposed via ngrok) that receives TradingView alert webhooks and fires Dhan orders + email. |

## D.3 Screening Engines (signal generation — zero-drift core)
| Module | Type | Functionality |
|---|---|---|
| **bull_screener.py** | import | The 6-catalyst bull engine (POS-AC/POS-BO/SWG-PB/SWG-BO/SWG-REV/GAP-GO), pure price-action, 0–100 Alpha Score. Mirrors the Pine Beta Edition exactly. `run_bull_screener(symbols, out_file, strict, progress_callback)`. Auto-logs picks to `pick_log`. |
| **recovery_screener.py** | import | REV-CB/REV-RS/REV-EARLY + the merged **Wyckoff cascade** (Spring/SOS/JAC). RFF fundamental hard-gate (≥4/6). `run_recovery_screener(...)`. Hold-window aware (90–180d). |
| **weinstein_xray_screener.py** | import | Deep Weinstein **Fundamental X-Ray v2.2** logic — `get_xray_scorecard()` returns Minervini /8 + Piotroski /9 + overall rating. Used by the single-stock X-RAY page. |
| **xray_screener_job.py** | import/launched | Batch wrapper that runs `get_xray_scorecard` over a watchlist → `FINAL_XRay_Picks.csv` (the HUNTER → X-Ray Screener tab). |
| **chartink_scanner_pro.py** | launched | The Layer-1 scanners (Chartink-equivalent). Arg `1`–`7` selects the scan: 1 Hunter, 2 Pullback, 3 EarlyBirds, 4 Strong Leaders, 5 REV-RS, 6 REV-CB, 7 REV-EARLY. |
| **brute_force_match_pro.py** | launched | The **Golden Matcher** (Layer 2/3) — joins `MASTER_scan_results.csv` (Screener.in fundamentals) to each Chartink output, keeps conviction ≥6.0 → `FINAL_*_Picks.csv`. |
| **screener_fetcher.py** | launched | Pulls raw fundamental HTML from Screener.in. |
| **screener_processor.py** | launched | Parses that HTML → structured `MASTER_scan_results.csv` (with BSE-code→NSE-ticker corrections). |
| **watchlist_ranker.py** | import | **Smart Rank** — Weinstein Stage-2 setup scorer, 0–100 + stage/grade label per symbol. `rank_watchlist`, `load_watchlist_symbols`. |
| **watchlist_manager.py** | launched | Generates clean watchlist CSVs (+ Tk GUI bits) for local use and TV import. |

## D.4 Market State (regime, breadth, macro, options, news)
| Module | Type | Functionality |
|---|---|---|
| **market_data_hub.py** | import | Central hub for global indices, commodities, currencies, bonds, India VIX, FII/DII, NSE breadth, economic calendar, options (PCR/Max Pain), GIFT Nifty. Builds the pre/post-market snapshots the AI briefs consume. |
| **breadth_engine.py** | import | Nifty 500 internals: A/D ratio, McClellan Oscillator/Summation, % above SMA50/150/200, Stage distribution, sector breadth. Backs the BREADTH page. |
| **market_regime.py** | import | Classic timing tools the stack was missing: Distribution-Day tracker (O'Neil), Follow-Through Day, Zweig Breadth Thrust, + a **composite regime classifier**. Feeds the BREADTH Regime tab and the exit engine's regime-awareness. |
| **nse_options.py** | import | NSE option-chain fetch via the two-step Akamai-cookie session (fallback to cache/off-hours msg). Powers OPTIONS → Live Chain. |
| **news_feed.py** | import | Free RSS aggregator (ET, MC, BS, LiveMint, NDTV Profit) → DataFrame with keyword sentiment + colour. Backs the NEWS page; `get_last_feed_health` for the staleness row. |
| **news_fetcher.py** | import | Per-stock news + NSE corporate announcements (RSS + NSE), 30-min cache. Backs X-RAY → News. |

## D.5 Paid News & Analyst Sentiment
| Module | Type | Functionality |
|---|---|---|
| **paid_news_cookies.py** | import | Loads ET + Moneycontrol Pro session cookies exported once from Chrome (`data/paid_news_cookies/*.json`). The auth substrate for the paid scrapers. |
| **et_scraper.py** | import | Economic Times analyst-recos + per-stock news scraper (uses the ET session). Parses headlines into structured reco fields. |
| **mc_scraper.py** | import | Moneycontrol equivalent, mirrors `et_scraper`'s shape. |
| **analyst_sentiment.py** | import | Aggregates ET+MC into one per-symbol verdict (Strong Buy/Buy/Hold/Sell/Strong Sell counts + raw items). 6-h per-symbol cache. Powers every "Analyst Sentiment" panel. |

## D.6 AI / Reporting
| Module | Type | Functionality |
|---|---|---|
| **gemini_reporter.py** | import | Google Gemini (genai SDK) report generator: `generate_premarket_brief`, post-market summary, `generate_stock_analysis`, `generate_portfolio_review`, `generate_weekly_market_report`. |
| **ai_risk_manager.py** | import | The AI-Trade Proposer backend (AI LAB Pre-Flight) — scores/sizes a proposed trade. |
| **ai_grading_engine.py** | import | `get_weinstein_score()` — the Weinstein grade + quant score (calls an LLM via `ai_provider_manager`). |
| **scheduler_daemon.py** | import/launched | APScheduler daemon for automated report delivery; `load_latest_report()` lets the UI show the freshest cached brief. Writes to `reports/`. |
| **workflow_strategic_briefing.py** | launched | Chains the daily strategic briefing steps → a PDF (the Dashboard "Market Briefing" button). |

## D.7 Fundamentals & Portfolio Risk
| Module | Type | Functionality |
|---|---|---|
| **fundamental_hub.py** | import | yfinance fundamentals: stock info, statements, quarterly results, valuation scorecards, screening, Gemini-ready text summaries. Backs X-RAY Snapshot/Scorecard/Screen. |
| **portfolio_analytics.py** | import | Overview, factor exposure (beta/alpha/tracking error vs Nifty50), VaR/CVaR (historical + parametric), historical stress scenarios, walk-forward Stage-2 backtest. Backs the PORTFOLIO page. |
| **performance_attribution.py** | import/launched | Phase-0 engine — decomposes **realized** P&L across 11 dimensions incl. entry-signal drivers (setup/stage/alpha/RS/conviction). Quarantines incomplete rows (no NaN→0). Backs AUTOPSY → Attribution. |

## D.8 Backtest & Track Record
| Module | Type | Functionality |
|---|---|---|
| **replay.py** | import | As-of-date screener replay + realistic execution sim (commission, catalyst-aware forward windows, Sharpe/Sortino/Calmar, split Initial/Trail SL). Backs WATCHLIST → Replay. |
| **validation.py** | import | Multi-anchor walk-forward backtest over a fixed universe (`default_universe('nifty500'/'fno')`), bootstrap CI. Backs the 12-Month Validation Backtest + supplies universes to the screeners. |
| **pick_log.py** | import | SQLite log (`pick_log.db`) of every live screener pick + N-day forward evaluation → the Live Pick Track Record. |
| **pipeline_status.py** | import | Writes `pipeline_status.json` after each Auto-Pilot phase (Phase/Status/Duration/Records) → WATCHLIST Pipeline Status grid. |

## D.9 Execution Engines & Agents (live management)
| Module | Type | Functionality |
|---|---|---|
| **exit_signal_engine.py** | import/launched | MISS-1 watchdog — scans open positions for STOP-LOSS / TARGET / R-multiple / stage-decay / RS-fade; regime-aware. `run_exit_scan(silent)`. Dashboard + COMMAND. |
| **portfolio_rotation_guard.py** | launched | Grades every open position (hold/trim/exit) for the Sell-to-Buy rotation matrix. |
| **alert_engine.py** | import | Price-alert store (`reports/price_alerts.json`): `add_alert`, `remove_alert`, `toggle_alert`, `list_alerts`, `get_current_price`. Backs COMMAND → Price Alerts. |
| **market_monitor_agent.py** | launched | Background intraday agent — runs scanners + Bull/Recovery screeners during market hours, pushes new triggers to Telegram. |
| **telegram_sentinel.py** | launched | Telegram bot for on-demand mobile market queries. |

## D.10 ETF System (parallel pipeline)
| Module | Type | Functionality |
|---|---|---|
| **etf_universe.py** | import | ~60 curated liquid NSE ETFs with category metadata (asset class, sub-category, benchmark, liquidity tier). |
| **etf_screener.py** | import | Per-ETF 4-axis score (Liquidity/Trend/RS/Rotation, 0–40). Output `ETF_Screener_Results.csv`. |
| **etf_rotation.py** | import | Sector rotation (composite RS 60% 12W + 40% 4W), asset-class regime detector, RRG coords, regime-conditioned top picks. Backs the ETF page. |

## D.11 Pipeline, Journal & External Sync
| Module | Type | Functionality |
|---|---|---|
| **run_pipeline.py** | launched | The **Auto-Pilot** orchestrator — chains scanners → fundamentals → Golden Matcher → watchlist sync, writing per-phase status. |
| **dhan_journal_v7.py** | launched (Streamlit) | The full trade-journal app (SQLite) — entry-signal snapshots, exit reconcile, `get_sector` helper. Kept in sync by the scheduled `journal_sync.py`/`TradingJournal_DhanSync` task. |
| **tradingview_automation_v2.py** | launched | Playwright browser automation — injects generated watchlists into TradingView. |
| **strike_automation.py** | launched | Playwright sync of watchlists to Strike.money (`--mode watchlist`). |
| **gmail_dispatcher.py** | launched | Emails watchlist/match digests (`--mode test|matches`); also used by the webhook gateway. |

> Modules **not** in the sidebar but used internally: `ai_provider_manager.py` (LLM router behind the grading engine), `journal_sync.py` (the scheduled daily Dhan↔journal reconcile — runs outside the app). Anything you don't see here was likely part of the 127 dead `.py` files archived in June 2026 (commit 7c12686) — not wired into the live app.

---

## Appendix — Backend scripts the buttons fire

| Button / action | Script |
|---|---|
| 🤖 Run Auto-Pilot | `run_pipeline.py` |
| Market Briefing | `workflow_strategic_briefing.py` |
| Chartink scans (1–7) | `chartink_scanner_pro.py <n>` |
| Fetch / Process fundamentals | `screener_fetcher.py` / `screener_processor.py` |
| Golden Matcher | `brute_force_match_pro.py` |
| Bull / Recovery screen (inline) | `bull_screener.py` / `recovery_screener.py` |
| Generate CSVs | `watchlist_manager.py` |
| Exit Signal / Rotation Guard | `exit_signal_engine.py` / `portfolio_rotation_guard.py` |
| Sniper / GTT Shield | `sniper_trigger.py` / `gtt_auto_shield.py` |
| Telegram / Monitor / Webhook | `telegram_sentinel.py` / `market_monitor_agent.py` / `dhan_tv_webhook.py` |
| Validation backtest | `validation.py` |
| Attribution | `performance_attribution.py` |
| Journal app | `dhan_journal_v7.py` |

> **Zero-drift rule:** every signal field here (Stage, RS, Alpha, catalysts) is computed by the same Python core that mirrors the Pine surfaces. If you ever see a value here disagree with TradingView, treat it as a bug to chase, not a tuning knob.

---

### Common Issues
| Symptom | Cause | Fix |
|---|---|---|
| Status = AUTH EXPIRED | Dhan token expired (daily) | Sidebar 🔑 → paste new token → Save → reload |
| Bull Screener shows old date | Input watchlist newer than last run | Re-run Bull Screener (the page warns you) |
| Recovery/Bull screen very slow | Cold OHLCV cache | WATCHLIST → Data Cache; or reduce universe to F&O |
| Paid news cards empty | ET/MC cookies stale | Re-run `setup_paid_news_cookies.py` |
| McClellan "stale" banner | `mcclellan_state.json` >7d old | Re-run BREADTH calc |
| GTT / order buttons dead | No valid token | Repaste token (§0.4) |
| Auto-Pilot console closed instantly | A phase errored | WATCHLIST → Pipeline Status → regenerate the failed phase |
