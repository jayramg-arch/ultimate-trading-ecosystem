# Weinstein–Minervini Commander Trading Bible
## The Complete End-to-End Operational Trading Guide
### Version 4.0 — May 2026 | NSE India

---

> **What this document is:** The single operational guide for every decision in the Weinstein Commander ecosystem — from Python overnight discovery through Pine screener validation, Dashboard confirmation, strategy execution, position sizing, and trade exit. This is not a module-reference summary. It is a step-by-step workflow guide for using all modules in the correct sequence.
>
> **What this document is not:** A field-by-field input reference. For that, consult the dedicated module guides in `docs/01_…` through `docs/13_…`.
>
> **v4.0 changes from v3.0:** (1) The three standalone context indicators — Wyckoff, Volume Profile, SMC — are now combined into **Context Layers v1.0**, which provides a unified CONTEXT SCORE panel. (2) The two strategy scripts — Minervini Strategy v4.53 and Recovery Strategy v1.4 — are now combined into **Weinstein_Unified_Ecosystem_v2.2.pine**, a single script running all 9 edges with one exit engine and one position-sizing framework. (3) Dashboard upgraded to **v67.0**.

---

## SECTION 1 — System Philosophy

### Three Schools, One Edge

The Commander ecosystem fuses three complementary methodologies:

**Stan Weinstein — Stage Analysis (the primary framework)**
Every stock is always in one of four stages. Stage 2 (under accumulation and trending up through its 30-week SMA) is the only stage where you want to own a stock. Everything else — Stage 1 base-building, Stage 3 topping, Stage 4 decline — is avoided for long entries. The 30-week SMA is the watershed line. Stage transitions are your buy and sell triggers.

**Mark Minervini — SEPA / Trend Template (the entry filter)**
Within Stage 2, Minervini's six-MA trend template filters for the strongest stocks. 50 DMA > 150 DMA > 200 DMA, all rising, with price above all three. VCP breakouts and EMA pullbacks provide low-risk, high-conviction entry points. The Alpha Score (0–100) quantifies this quality numerically.

**Wyckoff / SMC / Volume Profile (the context layer)**
Institutional footprints — volume shelf, order blocks, FVGs, liquidity sweeps, POC/VAH/VAL — confirm that smart money is genuinely accumulating, not distributing. The **Context Layers v1.0** indicator consolidates all three frameworks into a single CONTEXT SCORE (range −12 to +12) that tells you instantly whether all three modules are aligned bullish, neutral, or bearish.

### The Core Discipline

**Never trade against macro.** If CNX500 is in Bear or the sector is in Stage 3/4, no long setups exist — regardless of how good an individual stock looks. Macro kills more trades than any technical error.

**Never skip the Dashboard.** The Python screeners find candidates. The Pine screeners filter on raw data. The Dashboard is the final judge. No position is opened without a Dashboard reading of ≥ BUY with Alpha ≥ 60.

**Always cross-check Context Score before entry.** A BUY signal from the Unified Ecosystem with a CONTEXT SCORE below BULL (< 3) is a reduced-conviction entry. Size accordingly.

**Never size into a signal you cannot defend.** Know the stop-loss before entry. The Unified Ecosystem calculates the position size automatically; understand and verify the logic before placing the order.

---

## SECTION 2 — System Architecture

The complete workflow runs in four stages (S1 → S4):

```
┌──────────────────────────────────────────────────────────────────────┐
│  S1 — DISCOVERY (Python, overnight)                                  │
│  Commander Web v4.0                                                   │
│  ├── Sector Dashboard → leading/lagging sectors                      │
│  ├── Bull Screener → top Alpha Score candidates (NSE universe)       │
│  ├── Recovery Screener → REV-CB / REV-RS / REV-EARLY candidates     │
│  └── Portfolio Sync → live positions injected into Dashboard Pine    │
└──────────────────────────┬───────────────────────────────────────────┘
                           │  Shortlist exported as CSV
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  S2 — RE-SCREENING (Pine, live market)                               │
│  Commander Screener Beta Edition v2.6 (Bull candidates)                      │
│  Commander Capitulation Screener v1.5 (Recovery candidates)          │
│  ├── Real-time candle data (not EOD)                                 │
│  ├── Alpha Score, Catalyst, RS confirmation                          │
│  └── Shortlist reduced to 5–10 high-conviction setups               │
└──────────────────────────┬───────────────────────────────────────────┘
                           │  Confirmed candidates
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  S3 — VALIDATION (Dashboard, per chart)                              │
│  Weinstein & Swing Pro Dashboard v67.0                               │
│  ├── Macro + Sector gate                                             │
│  ├── Stage / RS / Alpha / RFF gate                                   │
│  ├── Recommendation (STRONG BUY / BUY / BUY* / WAIT)                │
│  └── Entry, SL, T1, T2, R:R confirmed                               │
└──────────────────────────┬───────────────────────────────────────────┘
                           │  Trade blueprints
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  S4 — EXECUTION (Unified Ecosystem, live chart)                      │
│  Weinstein_Unified_Ecosystem_v2.2.pine — 9 edges in one script           │
│  ├── 6 Bull edges: POS-BO, POS-AC, SWG-PB, SWG-BO, SWG-REV, GAP-GO│
│  ├── 3 Recovery edges: REV-CB, REV-RS, REV-EARLY                    │
│  ├── Chandelier Exit trail (POS / REV) + EMA20 ratchet (SWG)        │
│  └── T1/T2 partials with automatic breakeven lock                   │
└──────────────────────────────────────────────────────────────────────┘
```

**Context overlay (loaded on every chart alongside the Unified Ecosystem):**
- `Zigzag v6.0` — HH/HL/LH/LL trend state, swing pivot reference levels
- `Context Layers v1.0` — unified institutional context: Wyckoff events, Volume Profile (POC/VAH/VAL), SMC zones (OBs, FVGs, Sweeps), and CONTEXT SCORE panel

---

## SECTION 3 — Setup & Configuration

### 3A — Python Environment (Commander Web v4.0)

**Prerequisites:**
```
Python 3.9+
pip install flask pandas yfinance requests python-dotenv
```

**Environment file (`.env` in the project folder):**
```
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_access_token
PINE_SCRIPT_PATH=C:\Users\jayra\Documents\GeminiVSCode\Weinstein and Swing Pro Dashboard v67.0.pine
PORT=5000
```

**Starting the server:**
```powershell
cd C:\Users\jayra\Documents\GeminiVSCode
python weinstein_commander_web_v4.0.py
```

The web app runs at `http://localhost:5000`. Keep it running during all trading hours.

**Token refresh:** Dhan tokens expire daily. Before market open, check the `.env` file has a fresh `DHAN_ACCESS_TOKEN`. If Portfolio Sync throws an auth error, get a new token from the Dhan portal, update `.env`, and restart the server.

### 3B — TradingView Setup

**Required indicators (add once, save to layout):**
1. `Weinstein & Swing Pro Dashboard v67.0` — mission control; Stage, RS, Alpha, Recommendation, Portfolio P&L
2. `Weinstein_Unified_Ecosystem_v2.2.pine` — single strategy script for all 9 bull and recovery edges
3. `Weinstein_Context_Layers_v1.0` — unified context overlay (Wyckoff + Volume Profile + SMC) with CONTEXT SCORE panel
4. `Commander Capitulation Screener v1.5` — recovery signal validation and pillar display
5. `Wesinstein Swing Zigzag [Strict v6.0]` — trend pivot context and HH/HL state

**Remove from layouts:** The three legacy standalone indicators — `Weinstein_Wyckoff_Phases_v1.0`, `Weinstein_Volume_Profile_v1.0`, `Weinstein_SMC_Zones_v1.0` — are now fully replaced by Context Layers v1.0. Running both creates duplicate labels and conflicting chart drawings.

**Critical input consistency** (must match across all indicators):
- Weinstein SMA Length: **30 weeks** (Weekly timeframe)
- Pivot Left/Right: **2/2** (Zigzag, Strategy, Recovery, Screeners)
- ATR Length: **14** (all Pine modules)
- Chandelier Exit Length: **22**, ATR Mult (Bull): **3.0** (Unified Ecosystem)
- RS Slope Lookback: **5 weeks** (Dashboard, Beta Screener)

---

## SECTION 4 — Context Layer (Load First, Change Never)

Before running any screener or reading any signal, load the context tools on a daily chart. These do not generate entry signals — they tell you *where you are* in market structure and confirm whether institutional activity supports the trade.

### Zigzag v6.0
Read the current trend state from the label on the last confirmed swing:
- `HH + HL` = confirmed uptrend — long bias
- `LH + LL` = confirmed downtrend — no new longs
- `HH + LL` or `LH + HL` = ambiguous/choppy — wait for resolution

The Zigzag's most recent pivot high and pivot low are the key reference points for all S/R decisions. T1 and T2 targets are plotted against previous swing highs.

---

### Context Layers v1.0 (Unified Context Overlay)

**Context Layers combines three frameworks into one indicator.** Load it once and you get Wyckoff phase labels, Volume Profile levels, and SMC zones all on the same chart — plus the CONTEXT SCORE panel that synthesises all three.

#### The CONTEXT SCORE

The CONTEXT SCORE is the single most important number on the panel. Range: −12 to +12.

```
CONTEXT SCORE = Wyckoff Component (−4 to +4)
              + VP Component      (−3 to +3)
              + SMC Component     (−3 to +3)
              + OB Proximity      (−2 to +2)
```

| Score | Label | Meaning for Trading |
|---|---|---|
| ≥ 6 | **STRONG BULL** | All three modules aligned bullish. Full-size entry. |
| 3–5 | **BULL** | Majority aligned bullish. Normal-size entry. |
| −2 to +2 | **NEUTRAL** | Mixed signals. Be selective; reduce size 25–50%. |
| −3 to −5 | **CAUTION** | Majority aligned bearish. No new longs. |
| ≤ −6 | **BEAR** | All modules aligned bearish. Flat or exit. |

**Trading rule:** Only enter new positions when CONTEXT SCORE is BULL or STRONG BULL. A BUY signal from the Unified Ecosystem at NEUTRAL context gets 50% size maximum.

#### Wyckoff Module

Identifies 13 events via pivot analysis + volume confirmation. The **WYCKOFF BIAS** (ACCUMULATION / DISTRIBUTION / NEUTRAL) and **LAST EVENT** are the key panel rows.

Key accumulation events and their Wyckoff score contribution:
- **SOS** (Sign of Strength): +4 — strongest bullish event. High-vol, wide up-bar, close near high. Entry trigger.
- **Spring / LPS**: +3 each — Spring is the false breakdown trap; LPS is the low-vol pullback after SOS. Both are excellent entry zones.
- **SC** (Selling Climax): +2 — capitulation bar, early floor. Not yet actionable alone.
- **PS / ST**: +1 each — preliminary support and secondary test. Building the base.

Key distribution events (all negative score):
- **SOW / LPSY**: −4 each — sign of weakness / last point of supply. Exit immediately.
- **UT** (Upthrust): −3 — false breakout above resistance. Do not chase.
- **BC** (Buying Climax): −2 — exhaustion top. Tighten stops.

**Check the `bars ago` counter.** The LAST EVENT field shows how many bars ago the event fired. An SOS from 5 bars ago is highly actionable; an SOS from 80 bars ago contributes to the score but is historical context, not an immediate setup trigger.

#### Volume Profile Module

Three key levels on the chart: POC (red line), VAH (green dashed), VAL (orange dashed).

| VP POSITION on panel | Score | Trading Read |
|---|---|---|
| `✓ ABOVE VAH` | +3 | In the control zone. Breakouts here have institutional backing. |
| `✓ IN VA (upper)` | +1 | Above POC. Healthy. Pullbacks to POC = re-entry. |
| `✗ IN VA (lower)` | −1 | Below POC. Weak. Wait for reclaim or skip. |
| `✗ BELOW VAL` | −3 | In the rejection zone. No positional longs. |

The **DIST TO POC** row (+/−%) tells you how extended the current price is from the institutional value consensus. DIST TO POC between 0% and +5% = ideal pullback entry zone.

#### SMC Module

Three elements contribute to the panel and chart:

**Order Blocks (OBs):** The last opposing candle before a Break of Structure. Bull OBs below price = demand zones. Bear OBs above price = supply zones.
- **BULL OB ZONE:** `✓ [range]` = support present below. If price is *inside* the OB (`C_STRONG` colour), this is maximum-confluence zone — OB Proximity adds +2 to Context Score.
- **BEAR OB ZONE:** `✓ CLEAR` = no overhead OB supply — ideal entry environment. `✗ [range]` = supply zone overhead — reduce conviction.

**Fair Value Gaps (FVGs):** 3-bar imbalance zones. The **OPEN FVGs** row shows the bull/bear balance. More bull FVGs than bear = structural buying dominance.

**BOS/CHoCH:** The **SMC TREND** row (`✓ BULLISH ▲` / `✗ BEARISH ▼`) is derived from the last structure break. The **LAST SMC EVENT** shows whether the most recent break was a CHoCH (trend reversal signal) or BOS (trend continuation).

**Liquidity Sweeps:** **LAST LIQ SWEEP** resets to `—` after 20 bars. A `✓ Sweep ▲` within the last 10 bars means stops below a prior low were hunted and reversed — a bullish tell. Combined with a Bull OB, this is one of the most reliable SMC entry patterns.

---

### Reading Context Layers Alongside the Unified Ecosystem

The three highest-conviction entry setups require all three context layers to confirm:

**Setup 1: OB Retest + VP Support**
- Unified Ecosystem shows POS-AC or SWG-PB signal
- BULL OB ZONE is active at or near the current price
- VP POSITION = `✓ ABOVE VAH` or DIST TO POC near 0%
- WYCKOFF BIAS = ACCUMULATION
- CONTEXT SCORE ≥ BULL (≥ 3)

**Setup 2: Wyckoff Spring / LPS + SMC Trend Bullish**
- LAST EVENT = Spring or LPS, within 15 bars
- SMC TREND = `✓ BULLISH`
- VP POSITION = `✓ IN VA (upper)` or above
- CONTEXT SCORE = STRONG BULL (≥ 6)
- *Action:* This is a maximum-conviction entry. Use Full Kelly (1.25×).

**Setup 3: Liquidity Sweep Reversal + CHoCH**
- LAST LIQ SWEEP = `✓ Sweep ▲`, within 5–10 bars
- LAST SMC EVENT = `✓ CHoCH ▲`
- VP POSITION not `✗ BELOW VAL`
- *Action:* High-probability counter-move. Enter via SWG-PB or SWG-BO trigger on the Unified Ecosystem.

---

## SECTION 5 — Stage 1: Overnight Python Discovery

**When:** Evening after market close, or 30–45 minutes before market open.

**Where:** Commander Web v4.0 → `http://localhost:5000`

**Goal:** Build the day's watchlist from 500 NSE stocks to 15–25 candidates.

---

### Step 5A — Sector Dashboard (First, Always)

Open **Tab 5: Sector Dashboard**. This is your macro filter. Before touching any individual stock, you must know the sector landscape.

**Read the heatmap:**
- Sectors in **Stage 2 + LEADING RRG quadrant** → these are your hunting grounds. Prioritise stocks from these sectors.
- Sectors in **Stage 1** → acceptable for early-entry setups only
- Sectors in **Stage 3 or Stage 4** → hard block. No long setups regardless of individual stock signals.
- Sectors in **LAGGING RRG quadrant** → caution even in Stage 2; require very high Alpha Score (≥ 80)

**Key sectors to watch for NSE India:**
- BANKNIFTY, CNXFINANCE — financials (largest weight in Nifty)
- CNXIT — IT services (defensive/export, dollar-sensitive)
- CNXPHARMA — pharma (often counter-cyclical)
- CNXMETAL, CNXENERGY — cyclicals (amplify market moves)
- CNXAUTO — auto (consumer economy proxy)

**Record the leading sectors.** You will filter the screener output by these sectors.

---

### Step 5B — Bull Screener (Bull Market / Stage 2 Stocks)

Open **Tab 4: Bull Screener**.

**Settings:**
- Universe: **NSE Top 500 (F&O eligible)** for liquidity
- Min Daily Turnover: **₹5 Cr** (never reduce below ₹3 Cr)
- Min Alpha Score filter: **60** (change to 70 in late-stage bull markets)

**Run the screener.** Typical scan time: 3–5 minutes for 500 stocks.

**Sort by Alpha Score (descending).** Work through the results top to bottom.

**First filter — Sector:** Cross-reference against the sectors you identified in Step 5A. Discard any result in a Stage 3/4 or LAGGING sector, regardless of Alpha Score.

**Second filter — Catalyst:** Group remaining results by catalyst code. Note the updated catalyst naming in the Unified Ecosystem:

| Catalyst Code | Unified Ecosystem Edge | Setup Type |
|---|---|---|
| `POS-AC` | POS-AC — Positional Accumulation | OBV-confirmed base building; early Stage 2 |
| `POS-BO` | POS-BO — Positional Breakout | 9-gate Stage 2 breakout above N-bar high |
| `SWG-PB` | SWG-PB — Swing Pullback | EMA-20 pullback in established Stage 2 uptrend |
| `SWG-BO` | SWG-BO — Swing VCP Breakout | VCP tight-base breakout on volume |
| `SWG-REV` | SWG-REV — Swing Reversion | Oversold (RSI < 35) above SMA200; mean-reversion |
| `GAP-GO` | GAP-GO — Gap & Go | 4%+ institutional gap held into close, 3× volume |

**Third filter — Quality columns:** For each remaining candidate, check:
- Alpha Score ≥ 60 (required), ≥ 80 (preferred)
- RS vs Nifty 500: LEADING or IMPROVING (never LAGGING)
- RFF Score ≥ 1 (fundamental quality gate)
- OBV Trending Up: YES
- Vol Shelf: YES (VWMA20 > VWMA50 confirmed)

**Output:** Export top 20–25 as CSV. Mark top 10 for immediate Pine re-screening.

---

### Step 5C — Recovery Screener (Corrected Market / Stage 1 Stocks)

Open **Tab 3: Recovery Screener**.

**When to run:** When CNX500 has corrected ≥ 7% from its recent high (the Unified Ecosystem's regime gate threshold), or when specifically hunting REV setups.

**Settings:**
- Universe: **NSE Top 500**
- Min Daily Turnover: **₹5 Cr**
- Min RFF Score: **1** (Python screener uses simplified RFF; Unified Ecosystem applies the full 6-checkpoint RFF)
- Regime Gate: **Enabled** (never disable)
- Min Recovery Score: **6** (raise to 8 during strong bull markets to avoid false-positives)

**Run the screener.** Results sorted by Recovery Score (0–12).

**Read the Signal Type column:**
- `REV-CB` — Climax Bottom. Four-pillar confirmation (stretch → washout → climax bar → turn bar). Highest conviction recovery signal.
- `REV-RS` — RS Survivor. RS-positive stock forming higher lows and breaking out during a market correction. Leadership signal.
- `REV-EARLY` — Early Bird. Trendline reclaim + compressed base (NR7/inside-bar). Earliest possible detection; requires additional confirmation from the Unified Ecosystem before acting.

**Regime gate (Unified Ecosystem threshold):** The Unified Ecosystem uses a market correction gate of ≥7% from 52W high on CNX500, OR a stock correction of 10–40% from its own 52W high. The Python screener uses a 10% stock-correction threshold — use that as your initial filter, then let the Unified Ecosystem's regime gate provide final validation.

**Export top 10–15 REV candidates** for Pine re-screening.

---

### Step 5D — Portfolio Sync

Open **Tab 1: Portfolio Sync**.

Click **"Sync from Dhan"**. This fetches all open Dhan positions and injects them into `Weinstein and Swing Pro Dashboard v67.0.pine`:
- Slots 1–30 populated with ticker, entry price, stop-loss, sector index, entry date
- Largest positions by value filled first

**After sync completes:** Open TradingView, right-click the Dashboard indicator → "Reload". Your portfolio data is now live.

**Verify the sync:** Load any current holding on the chart. The ENTRY, STOP, R-VALUE, and TIME WARN rows should show real data, not dashes.

---

## SECTION 6 — Stage 2: Live Pine Re-Screening

**When:** During the first 30 minutes of market open, after overnight Python output is in hand.

**Purpose:** Re-screen Python shortlist against live candle data. Python EOD data misses pre-market gaps, intraday volatility shifts, and volume anomalies.

---

### Step 6A — Bull Candidates (Commander Screener Beta Edition v2.6)

**For each of your top 10 Python Bull candidates:**

1. Load the ticker on TradingView (daily timeframe)
2. The Beta Screener plots signals directly on the chart. Look for active catalyst labels.
3. Check Alpha Score displayed on the chart (must be ≥ 60)
4. Verify RS line vs CNX500 — is it LEADING or IMPROVING?
5. Vol Shelf label: **VWMA20 > VWMA50** (institutional accumulation confirmed)
6. VCP Tight label: **ATR < 1.0× Average ATR** (squeeze active — Unified Ecosystem threshold)
7. OBV: **2-bar consecutive rise AND OBV > OBV SMA20** (Unified Ecosystem POS-AC gate)

**Pass/fail by catalyst:**

| Catalyst | Pine Re-Screen Check | Unified Ecosystem Gate |
|---|---|---|
| POS-AC | OBV rising 2 bars + above OBV SMA20 | VWMA20 > VWMA50 (Volume Shelf) |
| POS-BO | Volume ≥ 1.5× 50-day average on breakout candle | VWMA20 > VWMA50; close above 20-bar high |
| SWG-PB | VCP Tight (ATR < 1.0×); MA stack (SMA150 > SMA200); RSI 30–70 | Volume dry-up: 3-bar vol < 50-bar avg |
| SWG-BO | ATR < 1.0× (VCP Tight); Volume < 50-bar avg (consolidation) | Volume ≥ 1.5× on breakout candle |
| SWG-REV | RSI < 35; price above SMA200; close > High[1] | 5-day time stop applies; quick-scalp trade |
| GAP-GO | Gap ≥ 4%; intraday close position ≥ 60%; volume ≥ 3× average | Check by 11:30 AM IST |

**Reduce to 5–8 confirmed candidates.**

---

### Step 6B — Recovery Candidates (Commander Capitulation Screener v1.5)

**For each of your top 10 Python Recovery candidates:**

1. Load the ticker on TradingView (daily timeframe)
2. Capitulation Screener plots the four REV pillars on the chart
3. Verify all four pillars against the Unified Ecosystem's updated REV-CB thresholds:

| Pillar | Unified Ecosystem Condition | What to check on chart |
|---|---|---|
| **P1 — Stretched** | Stock down ≥15% from 60-bar high | Price well below recent range ceiling |
| **P2 — Oversold** | ≥5 red bars in 7-bar window; close in bottom 25% of 10-bar range | Cluster of red bars; price at or near recent lows |
| **P3 — Climax Bar** | Volume ≥2× 50-bar average on the widest-range down bar within last 20 bars | Massive down-volume candle with widest range |
| **P4 — Turn Bar** | Close > Open; Close > High[1]; close in top 40% of bar | Bullish engulfing or hammer closing above prior high |

4. Check that the Context Layers panel shows **WYCKOFF BIAS = ACCUMULATION** (the SC or ST event in the Wyckoff module should have fired within the last 20 bars to confirm)
5. Regime gate: CNX500 must be ≥7% off its 52W high **OR** the stock must be 10–40% off its 52W high

**For REV-RS:** Higher low visible in recent 5 bars vs prior 10-bar low; RS slope positive; close above 20-bar high on 1.5× volume.

**For REV-EARLY:** Compressed base confirmed (NR7 or ≥3 inside bars in 10 bars); trendline reclaimed (close above highest high from bar[10] to bar[20]). Do not act without Unified Ecosystem confirmation.

**Reduce to 3–5 confirmed Recovery candidates.**

---

## SECTION 7 — Stage 3: Dashboard Validation (Per Chart)

**When:** After Pine re-screening produces 5–8 bull + 3–5 recovery candidates.

**Where:** Load each candidate on its own chart with the Dashboard visible.

**Rule:** Every candidate must pass ALL applicable dashboard gates before proceeding to execution. No exceptions.

> **Recovery candidates note (v67.0):** Dashboard v67.0 has removed its dedicated Recovery section. Recovery candidates still pass through the Dashboard's macro, sector, RS, and Alpha gates (left column). Recovery-specific signal state — REV pillars, regime gate, RFF score — was already validated in Step 6B via the Capitulation Screener and Unified Ecosystem panel. Do not look for a RECOVERY row in the Dashboard right column; it no longer exists.

---

### Row-by-Row Dashboard Reading

**Left column (work top to bottom):**

| Row | Required Reading | Pass Condition |
|---|---|---|
| **MACRO** | CNX500 regime | GREEN (Bull) or YELLOW (Recovery). Never trade in RED (Bear). |
| **SECTOR** | Auto-detected sector + stage | Sector must be Stage 1 or 2. Stage 3/4 = hard reject. |
| **STAGE** | Weinstein weekly stage | Stage 2 (UP) = ideal. Stage 1 (BASE) acceptable for early entry only. |
| **30W SMA** | Slope direction | ↑ Rising = confirmed Stage 2. → Flat = transition risk. ↓ Falling = Stage 3/4. |
| **RS vs N50** | Mansfield RS vs Nifty 50 | Any positive reading acceptable. LEADING = preferred. |
| **RS vs N500** | Mansfield RS vs Nifty 500 | LEADING = required for STRONG BUY. IMPROVING = acceptable for BUY. |
| **RS vs SECTOR** | Stock RS vs its sector | Positive = stock is leading its sector (sector rotation leader). |
| **50DMA** | Daily 50 SMA slope | Rising + price above = strong. Flat or declining = reduce size by 25%. |
| **ALPHA SCORE** | 0–100 quality score | ≥ 60 required. ≥ 80 = full size. 40–59 = half size maximum. |
| **GRADE** | A+/A/B/C/D | A or A+ = act on signals. B = act with reduced size. C/D = watch only. |
| **PATTERN** | Active chart pattern | VCP, Base, Breakout, Flag — confirms catalyst label matches visible structure. |
| **CATALYST** | Active catalyst code | Must match the catalyst from Python/Pine screening. |
| **RECOMMENDATION** | Final signal | STRONG BUY = full size. BUY = normal size. BUY* = check fundamentals first. PULLBACK = re-entry only. WAIT = skip. |
| **ENTRY** | Portfolio entry price | If slot matched, confirms existing position data is correct. |
| **STOP** | Active stop-loss | Flashes red if price is within 3% of stop. |
| **R-VALUE** | Current unrealised R-multiple | For existing positions: ≥ 1R = trade working well. |

**Right column:**

| Row | What to check |
|---|---|
| **WEEKLY SETUP** | POS-BO or POS-AC must be active for bull track |
| **SWING SETUP** | SWG-PB / SWG-BO / GAP-GO / SWG-REV for swing track |
| **RFF LITE** | 2/2 ✓ = fundamentals confirmed. 1/2 ⚠ = proceed with caution. 0/2 ✗ = skip unless Alpha ≥ 90. |
| **VOL SHELF** | YES = VWMA20 > VWMA50 confirmed. Institutional accumulation present. |
| **VCP TIGHT** | YES = ATR < 1.0× ATR-SMA (squeeze active). Entry is optimal. |
| **EMA PROXIMITY** | "OverExtended" = wait for pullback. ≤ 1.5% from EMA-20 = ideal swing entry. |
| **RSI** | 30–70 = optimal. > 70 = Overbought (bull track: wait). < 35 = Oversold (SWG-REV territory). |
| **TIME WARN** | Position open ≥ 10 days (swing) or ≥ 6 weeks (positional) with P&L < 0.5R. Apply time-stop. |
| **PORTFOLIO P&L** | W/L/Stop count. If ≥ 3 stops recently, reduce new sizes. |

> **Note (v67.0):** The RECOVERY section has been removed from Dashboard v67.0. Recovery signal validation — REV-CB pillars, REV-RS breakout status, REV-EARLY compression check — is now handled exclusively through (a) the **Commander Capitulation Screener v1.5** (real-time pillar display on chart) and (b) the **Weinstein_Unified_Ecosystem_v2.2.pine** recovery panel (regime gate, CB pillars P1–P4, RFF score). Do not expect a recovery row in the Dashboard right column.

---

### Dashboard Decision Matrix

| RECOMMENDATION | Alpha Score | RFF Lite | Context Score | Action |
|---|---|---|---|---|
| STRONG BUY | ≥ 80 | 2/2 | STRONG BULL | Full size entry (1.25× Kelly) |
| STRONG BUY | ≥ 80 | 2/2 | BULL | Full size entry (1.0× Kelly) |
| BUY | 60–79 | 2/2 | BULL | Normal size entry (1.0× Kelly) |
| BUY | 60–79 | 2/2 | NEUTRAL | Half size. Be selective. |
| BUY | 60–79 | 1/2 | any | Half size. Set alert for RFF improvement. |
| BUY* | any | 0/2 | any | Fundamentals failed. Skip unless Alpha ≥ 90 with clear catalyst. |
| PULLBACK | any | any | any | Re-entry signal on existing position only |
| WATCH | any | any | any | No entry. Set price alert for stage transition. |
| WAIT | any | any | any | Hard pass. Move to next candidate. |

---

## SECTION 8 — Stage 4A: Bull Track Execution

**Module:** `Weinstein_Unified_Ecosystem_v2.2.pine` — Bull Market Strategy (daily chart)

**Master prerequisites (all must pass before any bull edge fires):**
1. Enable Bull Market Strategy toggle: ON
2. Market Health: CNX500 close > SMA200 AND SMA50 > SMA200
3. Weinstein Stage (Weekly): Stage 2 (or Early Stage 2 for POS edges)
4. Alpha Score ≥ Min Alpha Score (default 50 in script; use 60 as your personal floor)
5. RS Quadrant: LEADING or IMPROVING
6. Micro Edge: Close > Daily CPR Pivot AND Close > Monthly VWAP

**Entry condition summary:** Dashboard shows BUY or STRONG BUY. All dashboard gates passed. CONTEXT SCORE ≥ BULL.

---

### Edge-by-Edge Entry Rules

**POS-BO — Positional Breakout**
- *Concept:* Price closes above the 20-bar high in a confirmed Stage 2 uptrend on above-average volume. Institutional escape from base into open air.
- *Entry Conditions:* All master prerequisites + Base Confirmed (Stage 2 + MPA pass: close > SMA150 > SMA200) + Close > 20-bar High (prior bar) + Volume > 1.5× 50-bar average + VWMA20 > VWMA50
- *Entry type:* Buy-stop limit 0.25% above the 20-bar high. Market order on confirmed break.
- *Never chase:* If price is already ≥ 3% above the breakout level, skip. Wait for first pullback to the breakout level.
- *Initial SL:* 10-bar structural low − 0.2× ATR14
- *Trail:* Chandelier Exit ratchet (CE-POS). CE = Highest Close[22] − ATR[22] × 3.0 (bull) / ×3.5 (bear). Ratchets up only.
- *T1:* Entry + 2.5R → exit 30% of position. Breakeven lock activates.
- *T2:* Full Chandelier Exit trail on remaining 70%. No fixed T2.
- *Time stop:* 6 weeks (30 trading days) if gain < 0.5R and not yet at breakeven.
- *Stage exit:* Immediate full close if Weekly Stage transitions to Stage 4.

**POS-AC — Positional Accumulation**
- *Concept:* Buy during the base-building phase when OBV confirms smart money accumulation before the breakout. Lower risk than POS-BO; requires VCP consolidation structure.
- *Entry Conditions:* All master prerequisites + Base Confirmed + Close > EMA20 > SMA50 + Close > Open + Close in top 30% of bar + Volume > 1.2× average + OBV rising 2 bars consecutively + OBV > OBV SMA20 + VWMA20 > VWMA50
- *Entry type:* Limit order 0.25% below close. This is a quiet accumulation entry, not a breakout.
- *Initial SL:* 10-bar structural low − 0.2× ATR14 (same as POS-BO)
- *Trail:* CE-POS (same as POS-BO). Breakeven lock after T1.
- *T1:* Entry + 2.5R → exit 30%. T2 = full CE trail.
- *Time stop:* 6 weeks if gain < 0.5R and not breakeven.

**SWG-PB — Swing Pullback**
- *Concept:* Price pulls back to EMA20 in an established Stage 2 trend, tightens (VCP Tight), and closes above the EMA with a bullish bar. Continuation entry.
- *Entry Conditions:* Market Health BULL + Close > SMA50 + Low pierced EMA20 + Close > EMA20 + Close > Open + VCP Tight (ATR < 1.0× ATR-SMA) + MA Stack (SMA150 > SMA200) + RSI 30–70 + Volume Dry-Up (3-bar vol SMA[1] < 50-bar vol SMA)
- *Entry type:* Market order on close, or limit order 0.25% below close.
- *Initial SL:* 5-bar swing low × (1 − SL Padding %) (default SL Padding = 0.2%)
- *Trail:* EMA20 ratchet: SL rises each bar to max(current SL, EMA20 × (1 − 1.0% trail buffer)). Never moves down.
- *T1:* Entry + 2.5R (bull) or +2.0R (bear regime) → exit 50%. Breakeven lock.
- *T2:* Entry + 3.5R (bull) or +3.0R (bear) → exit 50% of remainder. ~25% of original position runs.
- *Time stop:* 10 trading days if gain < 0.5R and not breakeven.
- *Contextual exit:* Immediate close if price closes below SMA50.

**SWG-BO — Swing VCP Breakout**
- *Concept:* Very tight VCP base (ATR < 1× average) breaks above the 20-bar high on volume. Shorter-hold swing trade; does not require the full positional prerequisite stack.
- *Entry Conditions:* Market Health BULL + VCP Tight (ATR < 1.0× average AND Volume < 50-bar SMA) + Close > 20-bar prior High + Volume > 1.5× average
- *Entry type:* Buy-stop 0.5% above the VCP pivot high.
- *Initial SL:* 5-bar swing low × (1 − SL Padding %)
- *Trail:* EMA20 ratchet (same as SWG-PB)
- *T1:* Entry + 2.5R → 50% exit. T2: Entry + 3.5R → 50% of remainder.
- *Time stop:* 10 trading days.
- *Contextual exit:* Close below SMA50.

**SWG-REV — Swing Reversion**
- *Concept:* Severely oversold stock (RSI < 35) above SMA200 (long-term trend intact). Mean-reversion back to EMA20. Quick-scalp trade — not a runner.
- *Entry Conditions:* Market Health BULL + Close > SMA200 + Close < EMA20 + RSI < 35 + Close > Open + Close > High[1]
- *Entry type:* Market order on confirmed reversal candle.
- *Initial SL:* 5-bar swing low × (1 − SL Padding %)
- *T1:* Entry + 2.0R (fixed, not dynamic) → exit 50%. **No T2.**
- *Time stop:* **5 trading days** maximum. SWG-REV is short-duration by design. If not at T1 in 5 days, exit.
- *Contextual exit:* Close below SMA50.

**GAP-GO — Gap & Go**
- *Concept:* An institutional-grade gap-up where the stock opens above the prior day's high, gaps ≥4%, and closes in the top 40% of the gap bar on ≥3× volume. Conviction buying.
- *Entry Conditions:* Market Health BULL + Open > High[1] + Close > Open + Gap size (Open − High[1])/High[1] ≥ 4% + Intraday position (Close − Open)/(High − Open) ≥ 60% + Volume ≥ 3× average
- *Entry type:* Wait until 11:30 AM IST. Enter above the first-candle high if volume criteria are confirmed. Do not enter at the open.
- *Disqualify if:* First 15-min candle retraces > 50% of the gap. This is a gap fill, not a gap and go.
- *Initial SL:* Gap bar's low × (1 − SL Padding %)
- *Trail:* EMA20 ratchet (same as SWG-PB)
- *T1:* Entry + 2.5R → 50% exit. T2: Entry + 3.5R → 50% of remainder.
- *Time stop:* 10 trading days.

---

### Bull Track Exit Summary Table

| Edge | T1 Trigger | T1 Exit % | T2 Trigger | Remaining | Trail Type | Time Stop |
|---|---|---|---|---|---|---|
| POS-BO | Entry +2.5R | 30% | CE Trail | 70% runs | CE-POS ratchet | 6 weeks |
| POS-AC | Entry +2.5R | 30% | CE Trail | 70% runs | CE-POS ratchet | 6 weeks |
| SWG-PB | Entry +2.5R | 50% | Entry +3.5R | ~25% runs | EMA20 ratchet | 10 days |
| SWG-BO | Entry +2.5R | 50% | Entry +3.5R | ~25% runs | EMA20 ratchet | 10 days |
| SWG-REV | Entry +2.0R | 50% | None | 50% closes | EMA20 ratchet | 5 days |
| GAP-GO | Entry +2.5R | 50% | Entry +3.5R | ~25% runs | EMA20 ratchet | 10 days |

**Breakeven lock rule (applies to all edges):** Once T1 is hit, the trailing stop floor is immediately raised to the entry price. You cannot lose on the remaining runner.

---

## SECTION 9 — Stage 4B: Recovery Track Execution

**Module:** `Weinstein_Unified_Ecosystem_v2.2.pine` — Recovery Market Strategy (daily chart)

**Master prerequisites (all must pass before any recovery edge fires):**
1. Enable Recovery Market Strategy toggle: ON
2. Regime Gate: CNX500 corrected ≥7% from 52W high **OR** stock corrected 10–40% from 52W high
3. RFF Score ≥ 3/6 (recovery edges require the full 6-checkpoint fundamental filter)

**Entry condition summary:** Dashboard shows REV signal active. Context Layers shows WYCKOFF BIAS = ACCUMULATION. Recovery Screener score ≥ 6.

---

### Edge-by-Edge Recovery Entry Rules

**REV-CB — Climax Bottom (highest conviction)**

The sequence: Stretched stock → Panic selling (washout) → Climax bar (highest-volume down day) → Turn bar (bullish reversal above prior high). All four pillars must pass simultaneously.

| Pillar | Condition |
|---|---|
| **P1 — Stretched** | Stock down ≥15% from 60-bar high |
| **P2 — Oversold** | ≥5 red bars in 7-bar window AND close in bottom 25% of 10-bar range |
| **P3 — Climax Bar** | Volume ≥2× 50-bar average on widest-range down bar within last 20 bars |
| **P4 — Turn Bar** | Close > Open AND Close > High[1] AND close in top 40% of bar |

**Additional gates:** Climax bar occurred within last 10 bars + RFF ≥ 3 + Regime Gate active.

- *Entry:* On the next bar open after P4 (Turn Bar) confirms. Do not enter on the Turn Bar itself.
- *Initial SL:* Climax structural low (P3 bar's low) − 0.5× ATR14. This is the invalidation point. If violated, the "turn" has failed.
- *T1:* EMA20 reclaim → exit 50%. Breakeven lock activates.
- *Post-T1 trail:* EMA20 ratchet: max(snapped SL, EMA20 × (1 − trail buffer %), entry price).
- *T2:* SMA200 reclaim → exit 50% of remainder.
- *Time stop:* 15 trading days if gain < 0.5R and not breakeven.

**REV-RS — RS Survivor (market correction leaders)**

During a market correction, this stock held up relatively well (positive RS slope) and is now breaking out of local resistance on volume, forming a higher-low structure.

- *Entry Conditions:* RS slope > 0 + Higher Low (recent 5-bar low > prior 10-bar low[5]) + Daily strict pivot trend = Uptrend + Stock corrected 10–40% from 52W high + Close > 20-bar prior High + Volume > 1.5× average + Sector Stage 1 or 2 + RFF ≥ 3 + Regime Gate
- *Entry type:* Buy-stop at the 20-bar high + 0.25% buffer on the breakout bar.
- *Initial SL:* Recent higher low × (1 − SL Padding %)
- *Trail:* Chandelier Exit ratchet (CE-REC). Breakeven lock after T1.
- *T1:* Entry + 2.5R → exit 50%. Breakeven lock.
- *T2:* 52-Week High → exit 50% of remainder.
- *Time stop:* 15 trading days if gain < 0.5R and not breakeven.

**REV-EARLY — Early Bird (highest risk, earliest entry)**

The earliest possible recovery entry — before RS turns fully positive and before the breakout is volume-confirmed. Requires compressed base + trendline reclaim.

- *Entry Conditions:* Trendline Reclaim (close > highest high from bar[10] to bar[20]) + Higher Low structure + Daily trend Uptrend + Compressed Base (NR7 or ≥3 inside bars in 10-bar lookback) + Close > 15-bar prior high + Volume > 1.5× average + RS slope > 0 + Sector Stage 1 or 2 + RFF ≥ 3 + Regime Gate
- *Entry type:* Market order on the trendline-reclaim close.
- *Initial SL:* Lowest low within the NR7 window × (1 − SL Padding %)
- *Trail:* CE-REC (same as REV-RS). Breakeven lock after T1.
- *T1:* Entry + 2.5R → exit 50%. T2: 52-Week High → exit 50% of remainder.
- *Time stop:* 15 trading days.
- **Important:** REV-EARLY is the highest-risk recovery edge. Context Layers must show WYCKOFF BIAS = ACCUMULATION and CONTEXT SCORE ≥ NEUTRAL before acting. Never take REV-EARLY when CONTEXT SCORE is CAUTION or BEAR.

---

### Recovery Track Exit Summary

| Edge | Initial SL | T1 | T1 Exit | T2 | Trail Post-T1 | Time Stop |
|---|---|---|---|---|---|---|
| REV-CB | Climax low − 0.5× ATR | EMA20 reclaim | 50% | SMA200 reclaim | EMA20 ratchet | 15 days |
| REV-RS | Higher low − SL pad | Entry + 2.5R | 50% | 52W High | CE-REC | 15 days |
| REV-EARLY | NR7 low − SL pad | Entry + 2.5R | 50% | 52W High | CE-REC | 15 days |

**Regime change exit (mandatory override):**
If CNX500 falls back through the regime gate (market correction resolves into a full Bear), exit ALL recovery positions immediately. The regime is the thesis. If macro fails, the recovery trade fails.

---

## SECTION 10 — Position Sizing

**Primary mechanism:** The Unified Ecosystem calculates position size automatically on each signal. The formula is:

```
Risk Amount     = Portfolio Capital × (Risk % / 100)
                  [Bull: default 0.75%; Recovery: default 0.50%]
SL Distance     = Entry Price − Initial Stop Loss
Qty by Risk     = Risk Amount / SL Distance
Qty by Capital  = Max Allocation / Entry Price
Base Qty        = min(Qty by Risk, Qty by Capital)
```

**Kelly Multiplier (Bull edges only):**

| Conditions Met | Kelly Multiplier |
|---|---|
| All 3: Stage 2 + RS Positive + Volume > SMA50 | **1.25×** (Full Kelly) |
| Any 2 of 3 | **1.0×** (Standard) |
| Only 1 of 3 | **0.75×** (Half Kelly) |

```
Kelly-adjusted Qty = Base Qty × Kelly Mult
```

**Volatility Discount (applied last):**
```
ATR% = ATR14 / Close × 100
Vol Discount = min(3.0 / ATR%, 1.0)
Final Qty = Kelly-adjusted Qty × max(Vol Discount, 0.75)
```

High-volatility stocks automatically receive reduced sizing. Stocks with ATR% > 3% (e.g., small caps or penny stocks) get at least a 25% size reduction.

**Regime Discount (bear/correction markets):**
In a bear market (Market Health ≠ BULL), the risk % is reduced automatically:
```
Regime Risk % = max(Base Risk % − 0.25%, 0.25%)
```
This applies to both bull and recovery edges during bear conditions.

**Manual Pre-Trade Verification (Risk Allocator v1.0):**
Use the Risk Allocator as a manual sanity check before placing any order, particularly for large positions (> 5% of capital). Compare its output to the Unified Ecosystem's calculated quantity. They should agree within ±5%.

### Portfolio Concentration Limits

| Limit | Value |
|---|---|
| Single position | Maximum 10% of total capital |
| Single sector | Maximum 25% of total capital |
| Pyramid lot | 50% of initial lot (only after first lot at ≥1R) |
| Maximum pyramids | 2 (initial + 1 add) |
| Maximum open positions | 6 (configurable in Unified Ecosystem settings) |

### Declare the Trade Blueprint

Before placing any order, record:
```
Ticker:          ___________
Edge (catalyst): ___________  [POS-BO / POS-AC / SWG-PB / SWG-BO / SWG-REV / GAP-GO / REV-CB / REV-RS / REV-EARLY]
Entry:           ₹___________
Initial SL:      ₹___________
Risk/share:      ₹___________
Qty (auto):      ___________  (from Unified Ecosystem display)
Kelly mult:      ___________×
T1 price:        ₹___________  (T1 exit %)
T2 price:        ₹___________  (T2 exit %)
Trail type:      ___________  [CE-POS / CE-REC / EMA20 ratchet]
Time stop date:  ___________  (T+5/10/15 days or T+6 weeks)
Context Score:   ___________  [STRONG BULL / BULL / NEUTRAL]
```

---

## SECTION 11 — Trade Management

### Adding to Winners (Pyramiding)

Add a second lot ONLY when:
1. First lot is ≥ 1R in profit (position is working; Unified Ecosystem shows breakeven lock active)
2. Alpha Score has not declined since entry
3. Vol Shelf is still YES (VWMA20 > VWMA50)
4. Context Score is still BULL or STRONG BULL
5. A new lower-risk entry point exists (pullback to EMA-20, or a new mini-VCP breakout)

Pyramid lot size: 50% of the initial lot. Never exceed 10% total capital in one name.

### Trailing Stop Management

The Unified Ecosystem manages the trail automatically:

**CE-POS trail (POS-BO and POS-AC):**
- After T1: Breakeven lock active. CE trail continues rising with price.
- The CE step-line is plotted as fuchsia on the chart. Never manually override it downward.
- Stage 4 exit: Immediate full close if Weekly Stage transitions to Stage 4 — do not wait for the CE.

**EMA20 ratchet trail (SWG trades and REV-CB post-T1):**
- SL rises each bar to max(current SL, EMA20 × (1 − trail buffer %)).
- SWG Kill Switch: If price closes below SMA50, exit immediately regardless of trail level.

### Handling Gap-Downs Against Position

If a position gaps down significantly at open (≥ 2× ATR):
- If below the stop: Exit immediately at market on open. Do not wait for "recovery."
- If above the stop but close to it: Check the Context Layers panel. If WYCKOFF BIAS = ACCUMULATION and a new SC or Spring event is forming, hold with stop intact. Otherwise exit before it violates the stop.
- Never average down on a loss. The initial stop is sacrosanct.

### The Time Stop Protocol

When TIME WARN fires on the Dashboard:

1. Check if a structural reason exists for stagnation (sector underperformance, earnings blackout, broad market weakness). If the underlying thesis is still intact and stagnation is macro-driven, one extension of 5 days is permitted.
2. If no macro reason exists, or if the extension also produces no progress, exit the position.
3. Log the trade as "time-stopped." Review whether the setup was ambiguous or the catalyst was weak.

**SWG-REV is an exception:** Its time stop is 5 days — not 10. If mean-reversion has not occurred in 5 days, the setup has failed. Exit regardless of other factors.

---

## SECTION 12 — Post-Trade Housekeeping

### After Entry

1. Note the `active_catalyst` label shown on the chart (entry comment in the Unified Ecosystem) — this locks in the trail type for the trade.
2. Set TradingView alerts:
   - Alert at T1 price (partial exit reminder)
   - Alert at Initial SL price (exit reminder)
   - Alert at 90% of time-stop date
3. Run **Portfolio Sync** in Commander Web to inject the new position into the Dashboard Pine inputs.
4. Verify Dashboard ENTRY, STOP, and R-VALUE rows show correct data on next chart load.

### After Exit

1. Update the portfolio slot: clear the ticker or overwrite with new position.
2. Re-run **Portfolio Sync** to sync the updated state.
3. Log the trade: entry, exit, R-multiple achieved, which edge triggered, which exit rule fired.
4. One-sentence post-mortem: *"I entered because X, the trade worked/failed because Y, the Context Score was Z at entry."*

### Weekly Review (Sunday evening)

1. Run Portfolio Sync to snapshot week-end positions.
2. Run Sector Dashboard — note any sector stage transitions.
3. Run Bull Screener — check if current holdings remain in the top quartile by Alpha Score.
4. Run Recovery Screener — check if any recovery positions have reached Stage 2 (upgrade from REV track to bull track).
5. Update any stops that the Chandelier Exit has moved during the week.
6. Review PORTFOLIO P&L row. If recent win rate has dropped below 40%, go to reduced sizing (0.75× Kelly max) until it recovers.
7. Load Context Layers on each current holding. Check CONTEXT SCORE — if any position has dropped to CAUTION, tighten the trailing stop by 50%.

---

## SECTION 13 — Intraday Quick-Decision Reference

| Situation | Dashboard reads | Context Score | Unified Ecosystem signal | Action |
|---|---|---|---|---|
| POS-BO trigger | STRONG BUY, Alpha ≥ 80, Vol Shelf YES | STRONG BULL | POS-BO 🟢, volume confirmed | Buy-stop above 20-bar high + 0.25% buffer |
| POS-BO on thin volume | BUY, Alpha 60–79 | BULL | POS-BO but vol < 1.5× | Wait for next day's open to confirm volume |
| POS-AC in base | BUY, Alpha ≥ 60 | BULL | POS-AC 🟢, OBV rising | Limit order 0.25% below close |
| SWG-PB fired | BUY, EMA PROX ≤ 1.5% | BULL | SWG-PB 🟢 | Limit order 0.25% below close |
| SWG-PB but overextended | WAIT | NEUTRAL | No active signal | Do not enter. Set alert at EMA-20. |
| GAP-GO gap day | N/A pre-market | Check live | GAP-GO 🟢 | Wait until 11:30 AM. Enter above first-candle high. |
| GAP-GO fading immediately | — | — | — | Skip. Gap fill in progress. |
| SWG-REV oversold | BUY, RSI < 35 | BULL or NEUTRAL | SWG-REV 🟢 | Market order. 5-day max hold. |
| REV-CB all 4 pillars | REV active, 4 pillars filled | ACCUMULATION + CONTEXT ≥ NEUTRAL | REV-CB 🟢 | Enter next bar open after Turn Bar |
| REV-CB 3/4 pillars | REV partial | — | REV-CB 🟡 Hold | Wait for P4. Set alert. |
| REV-RS breaking out | — | ACCUMULATION | REV-RS 🟢 | Buy-stop above 20-bar high + 0.25% |
| REV-EARLY trendline reclaim | — | ACCUMULATION, CONTEXT ≥ NEUTRAL | REV-EARLY 🟢 | Market order on reclaim close |
| Context Score drops to CAUTION during hold | — | CAUTION | — | Tighten stop to current CE level − 0.5× ATR |
| SMC TREND flips BEARISH on open position | — | BEAR | — | Raise stop to breakeven immediately |
| Macro turns Bear mid-trade | MACRO turns RED | BEAR | — | Exit all non-recovery POS positions immediately |
| Sector drops to Stage 3 | SECTOR row shows Stage 3 | — | — | Exit all positions in that sector |

---

## SECTION 14 — Parameter Master Table

These are the canonical parameter values. Do not change these without updating all relevant modules simultaneously.

| Parameter | Value | Used In |
|---|---|---|
| **Dashboard version** | **v67.0** | Dashboard Pine file |
| Weinstein SMA (weekly) | 30 | Dashboard, Unified Ecosystem, Screeners |
| 30W SMA Slope Lookback | 4 weeks | Dashboard |
| RS Slope Lookback | 5 weeks | Dashboard, Beta Screener |
| RS Level Period | 52 weeks | Dashboard |
| RS Slope Sensitivity | 0.2 (×100 scale) | Dashboard |
| BB Squeeze Lookback | 30 bars | Beta Screener |
| OBV Compound ROC short | 5 bars | Beta Screener, Dashboard |
| OBV Compound ROC long | 10 bars | Beta Screener, Dashboard |
| OBV SMA anchor | 20 bars | Beta Screener, Dashboard |
| Vol Shelf fast VWMA | 20 bars | Unified Ecosystem, Dashboard |
| Vol Shelf slow VWMA | 50 bars | Unified Ecosystem, Dashboard |
| ATR Length | 14 | Unified Ecosystem, Context Layers |
| Chandelier Exit Length | 22 | Unified Ecosystem |
| CE ATR Mult (Bull) | 3.0 (3.5 in bear) | Unified Ecosystem |
| EMA Length | 20 | Unified Ecosystem |
| SL Padding % | 0.2% | Unified Ecosystem |
| EMA Trail Buffer % | 1.0% | Unified Ecosystem |
| Breakout Lookback (POS-BO) | 20 bars | Unified Ecosystem |
| GAP-GO min size | 4% | Unified Ecosystem |
| GAP-GO min intraday position | 60% | Unified Ecosystem |
| GAP-GO min volume mult | 3× | Unified Ecosystem |
| SWG-REV RSI threshold | 35 | Unified Ecosystem |
| Positional Time Stop | 6 weeks (30 days) | Unified Ecosystem, Dashboard |
| Swing Time Stop | 10 trading days | Unified Ecosystem, Dashboard |
| SWG-REV Time Stop | 5 trading days | Unified Ecosystem |
| Recovery Time Stop | 15 trading days | Unified Ecosystem, Dashboard |
| REV-CB Min Drawdown | 15% (from 60-bar high) | Unified Ecosystem |
| REV-CB Max Drawdown | 40% | Unified Ecosystem |
| REV-CB Min Climax Vol Mult | 2.0× | Unified Ecosystem |
| REV-CB Climax Detection Window | 10 bars | Unified Ecosystem |
| REV-CB Drawdown Lookback | 60 bars | Unified Ecosystem |
| REV-CB Washout Window | 7 bars | Unified Ecosystem |
| REV-CB Min Red Bars | 5 | Unified Ecosystem, Dashboard |
| REV-CB Climax Range Lookback | 20 bars | Unified Ecosystem |
| Regime Gate (market correction) | 7% from 52W high | Unified Ecosystem |
| Regime Gate (stock correction) | 10–40% from 52W high | Unified Ecosystem, Screeners |
| Min RFF Score (Recovery) | 3/6 | Unified Ecosystem |
| Min Alpha Score (entry) | 60 (personal floor) | Dashboard, Beta Screener |
| Min Recovery Score (entry) | 6 | Recovery Screener |
| Min Daily Turnover | ₹5 Cr | Bull + Recovery Screeners |
| Pivot Right Bars | 2 | Zigzag, Unified Ecosystem |
| Max open positions | 6 | Unified Ecosystem |
| Max allocation per trade | ₹25,000 (adjust to ~25% of capital) | Unified Ecosystem |
| Wyckoff Pivot Length | 10 | Context Layers |
| Wyckoff Vol Lookback | 20 | Context Layers |
| Wyckoff High Vol Threshold | 1.5× | Context Layers |
| Wyckoff Low Vol Threshold | 0.7× | Context Layers |
| VP Lookback | 100 bars | Context Layers |
| VP Value Area % | 70% | Context Layers |
| VP Profile Rows | 40 | Context Layers |
| SMC OB Swing Length | 5 | Context Layers |
| SMC BOS Swing Length | 10 | Context Layers |
| SMC Liq Sweep Length | 10 | Context Layers |
| Liq Sweep display window | 20 bars | Context Layers |
| Context Score STRONG BULL threshold | ≥ 6 | Context Layers (trading rule) |
| Context Score BULL threshold | ≥ 3 | Context Layers (trading rule) |

---

## SECTION 15 — Common Mistakes, by Stage

### Mistakes at Python Discovery Stage

1. **Skipping the Sector Dashboard.** Running the Bull Screener without first checking which sectors are in Stage 3/4 fills your shortlist with names you will be forced to discard at the Dashboard stage. Do sector analysis first, always.

2. **Setting Min Alpha Score too low.** At 40–50, the Python screener will flood you with marginal setups. Set 60 as the floor and raise it to 70 in extended bull markets.

3. **Ignoring the Regime Gate on the Recovery Screener.** The Regime Gate is not optional. During strong bull markets, "recovery" setups are often normal pullbacks. The gate prevents treating them as capitulation events. The Unified Ecosystem's regime gate uses a 7% market correction or 10–40% stock correction threshold — be aware this differs slightly from the Python screener's 10% stock threshold.

4. **Running scans without a fresh Dhan token.** Portfolio Sync will silently fail if the Dhan auth token has expired. Check the `.env` file first and verify the path points to `Dashboard v67.0.pine`.

5. **Not exporting the shortlist to CSV.** Without a CSV, you lose the screener context (scores, stops, targets) by the time you reach the Pine re-screening step.

### Mistakes at Pine Re-Screening Stage

6. **Confusing the old catalyst names.** The Unified Ecosystem uses updated names: `POS-AC` (was `POS-ACCUM`) and `GAP-GO` (was `SWG-GAP`). The Python screener may still output old names. Map them correctly before the Pine step.

7. **Not checking live volume during POS-BO.** A breakout on below-average volume is a trap. Python uses EOD volume; the Pine re-screen must verify with live intraday data.

8. **Entering GAP-GO without waiting until 11:30 AM.** Gap openings are often reversed in the first hour. The entry rule is *above the first-candle high* after volume is confirmed, not at the open.

9. **Taking REV-EARLY as a standalone signal.** REV-EARLY is the highest-risk recovery edge. It requires Context Layers to confirm ACCUMULATION bias and CONTEXT SCORE ≥ NEUTRAL. Never act on REV-EARLY in CAUTION or BEAR context.

10. **Ignoring the SWG-REV 5-day time limit.** SWG-REV is designed as a 5-day maximum trade. If not at T1 within 5 days, exit regardless of dashboard signals. Mean-reversion trades that fail to revert quickly typically become trend-following losers.

### Mistakes at Dashboard Validation Stage

11. **Acting on BUY* without checking fundamentals.** The asterisk means the technical signal fired but both RFF Lite conditions failed. Verify the fundamental reasons before entering. Most BUY* signals should be skipped.

12. **Leaving Quick Check values populated.** `quick_ent` and `quick_sl` override the portfolio slot for the matched ticker. After analysing a potential trade with Quick Check, reset both values to 0.

13. **Not cross-checking the Context Score.** A Dashboard BUY with CONTEXT SCORE = CAUTION is not a valid entry. The two tools must both confirm before sizing normally. A BUY at NEUTRAL context gets 50% size at most.

14. **Trusting a BUY signal in a Stage 3 sector.** The SECTOR row on the left column of the Dashboard is authoritative — never override it. Stage 3 sector = no new longs, regardless of individual stock dashboard signals.

15. **Treating IMPROVING quadrant as equivalent to LEADING.** IMPROVING means the stock is still underperforming the benchmark, just improving its rate of underperformance. It is a watch condition, not a full-conviction buy condition, for new entries.

### Mistakes at Context Layers Stage

16. **Running Context Layers alongside the three original modules.** Context Layers replaces `Weinstein_Wyckoff_Phases_v1.0`, `Weinstein_Volume_Profile_v1.0`, and `Weinstein_SMC_Zones_v1.0`. Running all four simultaneously creates duplicate labels, doubled FVG boxes, and conflicting VP lines. Remove the originals.

17. **Over-relying on a stale Wyckoff LAST EVENT.** The LAST EVENT field is persistent — it remains until replaced by a newer event. An SOS from 60 bars ago still contributes +4 to the score. Check the `bars ago` value. Events older than 30 bars are historical context, not immediate triggers.

18. **Misreading LAST LIQ SWEEP ▼ as a short trigger.** A Liq Sweep ▼ means stops above a prior high were hunted, then price reversed. If you are already long and the SMC TREND is still `✓ BULLISH`, this is often a continuation setup — the market took liquidity to fuel the next leg up. React only if the sweep is followed by a bearish CHoCH.

19. **Using VP Lookback of 100 on weekly charts.** On weekly timeframes, 100 bars = nearly 2 years of data. The profile will be too diffuse. Use VP Lookback = 52 on weekly charts. Context Layers is designed for the daily timeframe as its primary use.

### Mistakes at Execution Stage (Unified Ecosystem)

20. **Chasing a POS-BO more than 3% extended.** Once price is ≥ 3% above the 20-bar high breakout level, the risk/reward has deteriorated. Wait for the first pullback to the breakout level.

21. **Not moving the stop to breakeven after T1.** The Unified Ecosystem handles this automatically (breakeven lock). Do not manually override or delete the breakeven floor on the CE trail.

22. **Pyramiding before 1R is confirmed.** Adding before the first lot is working introduces averaging-up risk before the thesis is validated. Wait for the Unified Ecosystem breakeven lock to activate (= T1 hit) before adding.

23. **Using SWG-BO without confirming VCP Tight.** SWG-BO requires ATR < 1.0× ATR-SMA. Without the VCP squeeze, you are entering a loose, high-risk breakout. The VCP TIGHT row on the Dashboard must show YES.

### Mistakes at Recovery Track Stage

24. **Applying the old 25% drawdown threshold for REV-CB.** The Unified Ecosystem uses 15% drawdown from the 60-bar high (not 25% from 52W high). The entry condition is more accessible, but requires all four pillars — P3 (climax volume) and P4 (turn bar above prior high) are the new gates that enforce discipline.

25. **Trading REV-CB setups with CONTEXT SCORE = BEAR.** A stock in full BEAR context (SMC BEARISH + BELOW VAL + DISTRIBUTION Wyckoff bias) is not recovering — it is breaking down further. Only act on REV-CB when Context Score is at least NEUTRAL (≥ −2).

26. **Holding recovery trades through a macro regime reversal.** If CNX500 falls through the regime gate, exit ALL recovery positions immediately. No exceptions.

27. **Setting the stop above the climax bar's low for REV-CB.** The climax low (P3 bar) is the invalidation point for the recovery thesis. If it breaks, the turn has failed. Stops must be placed *below* this level (at least − 0.5× ATR14).

### Mistakes at Portfolio Management Stage

28. **Not syncing entry dates.** Without a correct date in the portfolio slot's `input.time` field, the Days Held counter and TIME WARN cannot function. Always set the date immediately after entering a position.

29. **Exceeding the 25% sector concentration limit.** When a sector is performing well, there is a natural temptation to load up on its stocks. The 25% sector cap is not optional — sector rotations can reverse violently, and concentration makes drawdowns severe.

30. **Forgetting to re-run Portfolio Sync after adjusting stops.** If you move a stop manually (after trailing it up), Portfolio Sync will overwrite your manual value with the last Dhan-fetched value on the next sync. Update the stop in Dhan first, or use the `quick_sl` override in the Dashboard as a temporary measure.

---

*Weinstein–Minervini Commander Trading Bible v4.0 — May 2026*

*Built on the Weinstein Commander Suite. For field-by-field input reference, consult the module guides in `docs/01_` through `docs/13_`:*
- *01 — Zigzag Strict v6.0 | 02–04 — Legacy context modules (superseded by Context Layers)*
- *05–06 — Legacy strategy modules (superseded by Unified Ecosystem)*
- *07 — Commander Web v4.0 | 08 — Dashboard v67.0 | 09 — Capitulation Screener v1.5*
- *10 — Risk Allocator v1.0 | 11 — Beta Screener v2.6 | 12 — Context Layers v1.0*
- *12 — Unified Ecosystem User Guide | 13 — Unified Ecosystem Trading Guide*
