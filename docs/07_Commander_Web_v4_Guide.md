# Weinstein Commander Web v4.0 — User & Trading Guide (Python Backend)

> **Module Role:** The **automation and command-centre backbone** of the Weinstein Commander ecosystem. This Python Flask web application is the bridge between your live trading accounts (Dhan), your screening data (NSE), and your TradingView charts. It automates the tedious mechanical work — portfolio sync, watchlist injection, screener execution — so you can focus purely on analysis and decisions.

---

## 1. Architecture Overview

`weinstein_commander_web_v4.0.py` is a **Flask web server** that runs locally (typically on `http://localhost:5000`) and exposes a multi-tab browser interface. The app coordinates several Python modules:

```
weinstein_commander_web_v4.0.py  ← Main Flask app / UI router
│
├── dhan_client.py               ← Dhan broker API integration
├── master_portfolio_sync.py     ← Pine script portfolio injector
├── sector_manager.py            ← Sector lookup DB generator
├── recovery_screener.py         ← REV-CB/RS/EARLY screening logic
├── bull_screener.py             ← Minervini/Weinstein bull catalyst screening
└── nse_data.py                  ← NSE symbol universe fetcher
```

---

## 2. Application Tabs

### Tab 1: Portfolio Sync

**Purpose:** Fetches your live Dhan portfolio holdings and automatically injects them into the Dashboard v67.4.12 Pine script.

**What it does:**
1. Authenticates with Dhan API using credentials from environment variables
2. Fetches all open positions (`/positions` API endpoint)
3. Maps each holding to: ticker symbol (NSE format), average entry price, current stop-loss, sector index (via `sector_manager.py`), and entry date
4. Writes these values directly into the `Weinstein and Swing Pro Dashboard v67.4.12.pine` file's input section — between the `<PORTFOLIO_START>` and `<PORTFOLIO_END>` markers
5. Fills portfolio slots 1–30 in order of position size (largest first)

**How to use:**
1. Open the web app at `http://localhost:5000`
2. Navigate to **Portfolio Sync** tab
3. Click **Sync from Dhan** button
4. Wait for the progress bar to complete (typically 10–30 seconds)
5. Open TradingView → reload the Dashboard indicator → your portfolio will be updated

**Key fields displayed:**
- Ticker / Exchange
- Quantity / Average Price / Current P&L
- Detected Sector
- Entry Date (parsed from Dhan order history)
- Stop-Loss status (set/not set)

---

### Tab 2: Watchlist Manager

**Purpose:** Manages and syncs TradingView watchlists with filtered NSE stock universes.

**Watchlist sources supported:**
- **NSE Top 500 (F&O eligible)** — high-liquidity universe for positional trading
- **NSE Nifty 200** — large-cap focused
- **Custom list** — manually entered tickers
- **Dhan positions** — your current holdings as a watchlist

**How to use:**
1. Select the watchlist source from the dropdown
2. Optionally apply filters: Min Market Cap, Min 30-day avg volume, Sector filter
3. Click **Generate Watchlist**
4. Copy the generated list and paste into TradingView's watchlist import

**Strike.money integration:** The Watchlist Manager also generates formatted lists compatible with Strike.money's portfolio tracker. The "Export for Strike" button formats tickers with the correct prefix for Strike import.

---

### Tab 3: Recovery Screener

**Purpose:** Runs the `recovery_screener.py` logic across the selected NSE universe and returns a ranked list of REV candidates.

**What it screens for:**
- REV-CB: 4-pillar capitulation + turn bar (aligned with Capitulation Screener v1.5)
- REV-RS: Strict-trend breakout with positive Mansfield RS
- REV-EARLY: NR7/inside-3 compression + 20-bar reclaim

**Inputs:**
| Field | Default | Explanation |
|---|---|---|
| **Universe** | NSE Top 500 | Stock pool to scan |
| **Min Daily Turnover (₹ Cr)** | `5` | Liquidity filter |
| **Min RFF Score** | `1` | Fundamental quality gate |
| **Regime Gate** | `Enabled` | Only show stocks in recovery-friendly macro conditions |
| **Min Recovery Score** | `6` | Minimum composite score to appear in results |

**Output columns:**
- Ticker / Close Price / Recovery Score (0–12)
- Signal Type (REV-CB / REV-RS / REV-EARLY)
- RFF Score / Mansfield RS / Weekly Stage
- Stop Loss Price / T1 / T2 / R:R to T1

**How to use:**
1. Set your filters
2. Click **Run Screener**
3. Watch real-time progress bar as each ticker is processed
4. Sort results by Recovery Score (descending) for highest-conviction candidates
5. Click any row to load that ticker in the quick-view chart preview
6. Click **Export CSV** to save results for offline analysis

---

### Tab 4: Bull Screener

**Purpose:** Runs the `bull_screener.py` logic — a port of the Bull Screener v3.2's 6 Minervini/Weinstein catalysts — across the NSE universe.

**What it screens for:**
| Catalyst | Code | Description |
|---|---|---|
| OBV Accumulation | POS-AC | OBV breakout + institutional vol + price lagging (was POS-ACCUM) |
| Stage 2 Breakout | POS-BO | 9-gate Weinstein breakout |
| EMA Pullback | SWG-PB | Minervini EMA-20 pullback setup |
| VCP Breakout | SWG-BO | VCP compression + pivot break with anti-algo filter |
| Mean Reversion | SWG-REV | RSI < 35 above SMA200; mean-reversion setup |
| Gap & Go | GAP-GO | 4%+ gap with 3× volume + intraday close ≥ 60% (was SWG-GAP) |

**Output columns:**
- Ticker / Alpha Score (0–100) / Alpha Stars (★★★★★)
- Dashboard Quality Score (0–100) / Confluence Score (0–6)
- Stage / Persona / Trade Style / Catalyst
- RS vs Nifty 500 / Sector RS / RRG Quadrant
- Recommended SL / T1 / T2 / Distance to SL%
- Stage Duration (weeks) / VCP Tight / Vol Shelf / OBV Trending Up

**How to use:**
1. Select universe and filters
2. Click **Run Bull Screener**
3. Sort by **Alpha Score** (descending) for highest quality setups
4. Filter by **Catalyst** to focus on specific trade types (e.g., show only SWG-PB)
5. Export CSV for session watchlist

---

### Tab 4.5: 🤖 Run Full Auto-Pilot — The Daily Watchlist Pipeline

**Purpose:** A single-click pipeline that chains every Python scanner, runs the conviction matcher, and writes dated watchlist files to `Generated_Watchlists/`. This is the canonical way to produce your daily Bull and Recovery watchlists; do **not** confuse the watchlist files this produces with the open-portfolio slots in Dashboard v67.4.12 (those are exclusively for live positions — see `08_Dashboard_v67_Guide.md`).

**What it does, step by step:**

1. **Layer 1 — Chartink-equivalent scans (`bull_screener.py` + `recovery_screener.py`)** run across the configured universe (default Nifty 500 + F&O):
   - Hunter (POS-BO equivalent) → `Bull_Hunter-DDMMMYY.txt`
   - Pullback → `Bull_Pullback-DDMMMYY.txt`
   - EarlyBird → `Bull_EarlyBird-DDMMMYY.txt`
   - StrongLeader → `Bull_StrongLeader-DDMMMYY.txt`
   - REV-CB → `Rec_Climax_Bounce-DDMMMYY.txt`
   - REV-RS → `Rec_RS_Survivor-DDMMMYY.txt`
   - REV-EARLY → `Rec_Early_Bird-DDMMMYY.txt`
2. **Layer 2 — Screener.in conviction filter (`brute_force_match_pro.py`)** runs `MASTER_scan_results.csv` (today's Screener.in fundamentals snapshot) against each Chartink output, keeping only stocks with conviction score ≥ 6.0 (matcher production default). Outputs:
   - `FINAL_Hunter_Picks.csv` (+ `_RRG.csv` variant)
   - `FINAL_Pullback_Picks.csv` (+ `_RRG`)
   - `FINAL_EarlyBird_Picks.csv` (+ `_RRG`)
   - `FINAL_Leader_Picks.csv` (+ `_RRG`)
   - `FINAL_Recovery_ClimaxBounce.csv`
   - `FINAL_Recovery_EarlyBirds.csv`
   - `FINAL_Recovery_RSLeaders.csv`
3. **Layer 3 — Combined watchlists**:
   - `FINAL_COMBINED_BULL_PICKS.csv` (union of all 4 bull FINAL files, deduplicated)
   - `FINAL_COMBINED_RECOVERY_PICKS.csv` (union of all 3 recovery FINAL files, deduplicated)
   - `FINAL_COMBINED_PICKS.csv` (everything, deduplicated)
   - `FINAL_WATCHLIST.csv` (matcher's golden watchlist with conviction scores)
4. **Layer 4 — TradingView watchlist sync** (`watchlist_manager.py` + `watchlist_ranker.py`): formats the FINAL_*.csv outputs as TradingView-importable `.txt` files in `Generated_Watchlists/` and (optionally) injects them into TradingView via the Playwright browser automation in `tradingview_automation_v2.py`.
5. **Forward archive** (`snapshot_archive.py`): copies the day's CSV outputs to `data/snapshots/YYYY-MM-DD/` so future backtests can use point-in-time historical data instead of yfinance fallbacks.

**Output filename conventions (in `Generated_Watchlists/`):**
- `Bull_*-DDMMMYY.txt` — Layer 1 raw Chartink-equivalent
- `Rec_*-DDMMMYY.txt` — Layer 1 raw recovery
- `Bull_Picks_All-DDMMMYY.txt` / `Recovery_Picks_All-DDMMMYY.txt` — Layer 3 combined
- `LATEST_*.txt` — symlink-style latest copies (no date stamp; used by automation)
- `Golden_Matcher_Picks-DDMMMYY.txt` — the conviction-filtered top-of-tier list

**How to use:**
1. Open the web app at `http://localhost:5000` (or the Streamlit port)
2. Navigate to the **Workflow** / **Auto-Pilot** tab
3. Click **🤖 Run Full Auto-Pilot** (button label: "Execute full pipeline: Scanners → Fundamentals → Golden Matching → Watchlist Sync")
4. Wait 5–10 minutes for the full pipeline to complete (depends on universe size and yfinance throttling)
5. Open TradingView; the watchlists are now ready for the Beta Edition v2.9 screener pass (Phase 3 of the daily workflow)

**Important — what these watchlists are NOT:**
- They are **not portfolio slots**. Do not paste these into Dashboard v67.4.12's portfolio slots 1–30 — those are reserved for OPEN positions tracked from Dhan.
- They are **not auto-traded**. The pipeline only generates and ranks; entry decisions go through the full Phase 3 (Pine re-screening) + Phase 4 (Unified Ecosystem signal-fire) workflow.

---

### Tab 5: Sector Dashboard

**Purpose:** Displays a sector rotation heatmap showing which sectors are in which Weinstein stage and which RRG quadrant.

**What it shows:**
- Each of 12 NSE sector indices (BANKNIFTY, CNXIT, CNXPHARMA, CNXAUTO, CNXFMCG, CNXMETAL, CNXENERGY, CNXREALTY, CNXINFRA, CNXFINANCE, CNXSERVICE, BSE:CG)
- Current Weinstein Stage (1/2/3/4) with colour coding
- Mansfield RS vs CNX500 and RRG Quadrant
- Weeks in current stage

**How to use:**
1. Open the tab (data auto-refreshes every 15 minutes)
2. Identify sectors in **Stage 2 + LEADING quadrant** → prioritise stocks from these sectors for long entries
3. Identify sectors in **Stage 3/4 + LAGGING quadrant** → avoid all long setups here regardless of individual stock signals
4. Use this as the top-level filter before running the Bull Screener

---

## 3. Supporting Python Modules

### `dhan_client.py`
- Handles all Dhan API authentication and HTTP calls
- Manages token refresh and session persistence
- Endpoints used: `/positions`, `/holdings`, `/orders`, `/orderbook`
- **Authentication:** Set `DHAN_CLIENT_ID` and `DHAN_ACCESS_TOKEN` as environment variables (or in a `.env` file). Tokens expire daily — the `token_refresh.py` script (if present) handles auto-renewal.

### `master_portfolio_sync.py`
- The Pine script injector — reads the `.pine` file and uses regex to find the `<PORTFOLIO_START>` and `<PORTFOLIO_END>` markers
- Replaces each `p{n}_tick`, `p{n}_ent`, `p{n}_sl`, `p{n}_sec`, `p{n}_date` input line with live data
- Entry date is formatted as Unix timestamp (milliseconds) for `input.time` compatibility
- **Run directly:** `python master_portfolio_sync.py` for a one-shot sync without the web UI
- **Sector assignment:** Calls `sector_manager.py`'s `get_sector(ticker)` function for each holding

### `sector_manager.py`
- Maintains the 500+ ticker → sector index mapping database
- `get_sector(ticker)` → returns the correct NSE/BSE sector index string
- `generate_pine_db()` → regenerates the `f_db_sector_lookup()` switch statement embedded in the Dashboard Pine script
- **Update the DB:** Run `python sector_manager.py --update` after adding new tickers to your watchlist

### `recovery_screener.py`
- Implements the REV-CB, REV-RS, and REV-EARLY detection logic in Python using `pandas` + `yfinance` (or Dhan's historical data API)
- Matches the logic in `Commander_Recovery_Screener_v2.0.pine` precisely
- Outputs a `pd.DataFrame` sorted by Recovery Score
- **Performance:** Scans 500 stocks in approximately 3–5 minutes with caching enabled

### `bull_screener.py`
- Implements all 6 Minervini/Weinstein catalysts from `Commander_Bull_Screener_v3.2.pine`
- Uses the same Alpha Score formula (0–100) as the Pine script
- Outputs a `pd.DataFrame` with all 30 screener columns mirrored from the Pine script

### `nse_data.py`
- Fetches and caches the NSE stock universe (Nifty 500, F&O list, full NSE list)
- Provides filtered subsets based on market cap, average volume, and sector
- Data is cached locally (24-hour TTL) to avoid repeated NSE website fetching

---

## 4. Setup & Running

### Prerequisites
```
Python 3.9+
pip install flask pandas yfinance requests python-dotenv
```

### Environment Variables (`.env` file)
```
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_access_token
PINE_SCRIPT_PATH=C:\Users\jayra\Documents\GeminiVSCode\Weinstein and Swing Pro Dashboard v67.4.12.pine
PORT=5000
```

### Starting the Server
```powershell
cd C:\Users\jayra\Documents\GeminiVSCode
python weinstein_commander_web_v4.0.py
```

The app will be available at `http://localhost:5000`. Keep it running in the background during trading hours.

---

## 5. Daily Automation Workflow

### Pre-Market Routine
1. **Start the web server** → `python weinstein_commander_web_v4.0.py`
2. **Portfolio Sync tab** → Click "Sync from Dhan" → updates Dashboard Pine file
3. **Sector Dashboard tab** → Identify leading and lagging sectors
4. **Bull Screener tab** → Run screener → sort by Alpha Score → export top 20
5. **Recovery Screener tab** (if market corrected) → Run screener → note any REV-CB/EARLY signals
6. Open TradingView → reload Dashboard → positions and watchlists are updated

### During Market
- Browser stays open for quick reference
- Re-run Bull Screener after any major index moves (≥1%)
- Use Portfolio Sync to update SL levels after trailing stops are moved

### Post-Market
- Run Portfolio Sync to capture the day's P&L snapshot
- Export Bull/Recovery screener results as CSV for evening review

---

## 6. Common Issues & Fixes

| Issue | Cause | Fix |
|---|---|---|
| Dhan auth error | Token expired (daily expiry) | Refresh token in Dhan portal → update `.env` → restart server |
| Portfolio sync overwrites wrong slots | Slot matching error | Verify ticker format — use `NSE:TICKER` in `DHAN_CLIENT_ID` mapping |
| Recovery Screener too slow | No caching | Ensure `nse_data.py` cache is active; reduce universe to Top 200 |
| Pine file not updating | Wrong path in `.env` | Verify `PINE_SCRIPT_PATH` points to the correct `.pine` file |
| Port 5000 in use | Another process | Change `PORT=5001` in `.env` |
| Sector wrong in sync | Ticker not in DB | Run `python sector_manager.py --update` to rebuild the DB |
