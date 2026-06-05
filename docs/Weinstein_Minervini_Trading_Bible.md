# Weinstein–Minervini Commander Trading Bible
## The Complete End-to-End Operational Trading Guide
### Version 6.0 — Cross-Tool Architecture + ML + Catalyst-Aware Backtest (22 May 2026)

> ## ⚡ JUNE 2026 SUPERSESSION — PURE PRICE ACTION (read before anything below)
> The signal engine was converted to **pure price action** after this Bible was written. **Wherever this document describes a catalyst or Alpha-Score gate using RSI / ADX / MACD / BB, that gate is now price-action** — the indicator references below are stale in mechanism (the *intent* and the catalyst names are unchanged). The canonical source is `bull_screener.py` (Python), with all three bull Pine files synced to it (Unified Ecosystem, Commander Bull Screener, Dashboard v67) — **recompiled clean in TradingView.**
>
> **Indicator → price-action map:** RSI>60/50 → `close>close[10]&[5]` · ADX → `≥7/14 up-bars w/ higher highs` · weekly RSI≥60 → `wClose>wClose[5]` · POS-ACCUM `d_rsi≤50` → `pa_not_extended` (`close≤close[5]×1.05`) · SWG-PB RSI-pocket → 38-62% retrace · SWG-REV RSI<35 → prior down-structure + reversal bar.
>
> **Other June-2026 changes:** the `weinstein_setup` squeeze-gate bug (killed the positional book for 24 months) is fixed; **Recovery now has a fundamental hard gate (RFF ≥ 4) + a 15-35% drawdown band**, and REV-EARLY is un-blackouted; new `walkforward_oos.py` / `catalyst_regime_partition.py` / Phase-0/1 journal modules; `data_provider` download timeout. **Validated edge is per-family and regime-dependent** (bull breakouts + recovery are defensive — positive in down/recovering tapes). True closed-trade baseline: **−₹4.99L / 25.6% win**. **Current versions:** Bull Screener **v3.3 (PA)**, Recovery Screener **v2.1 (RFF-gated)**. See `docs/11`, `docs/09`, `docs/16`, `docs/19`, and the CLAUDE.md "4–5 June 2026" handoff for full detail.

> **THIS IS THE SINGLE SOURCE OF TRUTH** for end-to-end swing and positional trading using the Weinstein Commander ecosystem. Everything you need — Python pipeline, watchlist generation, Pine validation, Dashboard reading, Unified Ecosystem execution, position sizing, exits, post-market — is in this document, in the order you'll perform it during a trading day.
>
> **What this document is:** A step-by-step operational guide for every decision in the trading workflow. It assumes you are running the production code (`chartink_replay.py` `SCAN_PARAMS_VERSION = "v2_FINAL_20260510"`, Bull Screener v3.2 (Py v1.11), Recovery Screener v2.0 (Py v1.6), Dashboard v67.4.12, Unified Ecosystem v3.4, Context Layers v1.2, Zigzag v6.2, Validation Framework v2.8).
>
> **What this document is not:** A field-by-field input reference. For that, consult the dedicated module guides in `docs/01_…` through `docs/16_…`. The Bible references them at every step.
>
> **What's new in v6.0 (this revision, 22 May 2026):**
>
> **Architectural shift — cross-tool field ownership.** Each tool in the ecosystem now owns exactly one domain. Other tools either mirror the owner's logic verbatim or remove the duplicate row from display. Owners:
> - **Mansfield RS engine** → Dashboard v67.4.12 (dual-SMA 52w level + 26w slope + 8w window + 4-bar momentum + 130-bar warm-up + JdK RS-Ratio model). Bull Screener / Recovery Screener / Unified Ecosystem mirror this engine and no longer render duplicate RS rows.
> - **Strict trend (HH/HL state)** → Zigzag v6.2. Dashboard reads via `f_getStrictTrend`.
> - **POS-BO 9-gate detail** → Bull Screener v3.2.
> - **4-pillar Capitulation Bottom + RFF + 60-bar DD** → Recovery Screener v2.0.
> - **Catalyst diagnostic panel + ML probability + WCL Gate** → Unified Ecosystem v3.4.
> - **Wyckoff / Volume Profile / SMC + CONTEXT SCORE** → Context Layers v1.2.
>
> **Eight headline upgrades since v5.0:**
> 1. **Dashboard bumped to v67.4.12.** Major price action campaign: neutralized 4 bearish detectors to Tier 0 (dist day, shooting star, failed bo) based on N500 regime-split validation; demoted OUTSIDE_BAR_BULL to Tier +1; fixed directional alpha reporting. Decision-Mode compression (13–18 composite rows, toggle "Show Detailed View" to expand to ~60). Physical 664-symbol sector database port — zero string-matching hacks, 100% offline parity with Python. JdK RRG formula matches Strike.Money. RS vs Nifty 50 row dropped (N500 is canonical breadth benchmark).
> 2. **Bull Screener v3.2.** Renamed `Commander_Bull_Screener_v3.2.pine`. **POS-ACCUM catalyst DISABLED** (backtest May 2025–Apr 2026 showed −10.04% mean alpha, zero wins). Composite-merge to ~13 rows. RS engine mirrors Dashboard. Physical DB port.
> 3. **Recovery Screener v2.0.** Renamed `Commander_Recovery_Screener_v2.0.pine`. Wyckoff phase detection added (Phase B base / Phase C Spring-Shakeout / Phase D SOS-JAC). Composite-merge to ~14 rows. 10 gates paired 2-per-row.
> 4. **Unified Ecosystem v3.4.** Three layers of change: (a) ported RS engine from Dashboard; (b) composite-merge + 4-column stacked CATALYST DIAG panel below main strategy panel showing *first failing gate per catalyst*; (c) added ML probability score + RSI 47–54 dead-zone filter + Wyckoff catalysts (Spring / SOS / JAC) + target realignment (swing 3R/5R was 5R/10R, partial 33%) + wider trails (SWG SMA50 trail, POS-BO 4.5× ATR Chandelier was 3.0×). (d) restored POS-ACCUM + REV-* to triggers; catalyst-aware fallback ATR multipliers (POS=4×, WYC=3.5×, REV=2.5×, SWG=1.5×).
> 5. **Context Layers v1.2.** Setup Detector contributes signed bonus to score (+2 S2 Spring/LPS, +2 S3 Sweep+CHoCH, +1 S1 OB Retest, −2 S7 Distribution, −1 S8 Choppy). Panel grew to 24 rows: BASE SCORE / SETUP BONUS / FINAL SCORE / BREAKDOWN. STRONG BULL threshold raised ≥ 8 → ≥ 9 to account for bonus headroom.
> 6. **Zigzag v6.2 (Strict).** EH/EL equal-pivot classes. Major/Minor pivots (Auto/Stock 8% / ETF 4% / Custom). MTF pivot lengths (Monthly/Weekly/Daily/Intraday). Section 3 developing-pivot detection (Trend / Structure / Swing Count / Swing Range / Choppiness all update live when a BoS or CHoCH is projected, not just on confirmed pivots). 11-row panel: TIMEFRAME / TREND / MTF TREND / STRUCTURE / SWING COUNT / SWING RANGE / CHOPPINESS / INVALIDATION / BOS LEVEL / VOL CONFIRM / BAR AGE. Longs-Only Mode default ON (Invalidation = latest swing low, BoS Level = latest swing high, Vol Confirm captures ↑ only). Fib extensions 1.272 / 1.618 added alongside 50% / 61.8% retracements.
> 7. **Validation Framework v2.8 (`validation.py` + `replay.py` + `sector_rotation.py`).** Catalyst-aware forward windows replace the single 30-day window: POS-BO 120d, POS-ACCUM 180d, WYC-* 120d, REV-* 90d, SWG-* 30d. Bootstrap CI on alpha (10,000 iterations). Realistic SL/T1/T2 bar-by-bar simulation. Optional risk overlays (sector cap / kill switch / sector rotation) — instrumented but NOT recommended as defaults; May 2026 testing showed they reduce alpha.
> 8. **Five-phase daily workflow** retained. The Confluence Sequence (§7D) is unchanged in spirit; **only the version numbers and the per-tool ownership references have been refreshed**. Hard floors and confluence-boost factors are stable.
>
> **Backtest verdict preserved:** v1 FINAL Hunter gates (`weekly_rsi_min=60`, `daily_adx_min=25`, `disable_rsi=True` for EarlyBirds) remain locked. The v2 LOCK `pos_accum_rsi_nullout=True` flag remains active in `v2_fixes.py` for the Python pipeline; the Pine-side POS-ACCUM catalyst is now disabled outright in the Bull Screener (different layer, same intent: stop bleeding capital on chase-zone accumulation entries).

---

## SECTION 1 — System Philosophy

### Three Schools, One Edge

The Commander ecosystem fuses three complementary methodologies:

**Stan Weinstein — Stage Analysis (the primary framework)**
Every stock is always in one of four stages. Stage 2 (under accumulation and trending up through its 30-week SMA) is the only stage where you want to own a stock. Everything else — Stage 1 base-building, Stage 3 topping, Stage 4 decline — is avoided for long entries. The 30-week SMA is the watershed line. Stage transitions are your buy and sell triggers.

**Mark Minervini — SEPA / Trend Template (the entry filter)**
Within Stage 2, Minervini's six-MA trend template filters for the strongest stocks. 50 DMA > 150 DMA > 200 DMA, all rising, with price above all three. VCP breakouts and EMA pullbacks provide low-risk, high-conviction entry points. The Alpha Score (0–100) quantifies this quality numerically.

**Wyckoff / SMC / Volume Profile (the context layer)**
Institutional footprints — volume shelf, order blocks, FVGs, liquidity sweeps, POC/VAH/VAL — confirm that smart money is genuinely accumulating, not distributing. The **Context Layers v1.2** indicator consolidates all three frameworks into a single CONTEXT SCORE (range −12 to +12) that tells you instantly whether all three modules are aligned bullish, neutral, or bearish.

### The Core Discipline

**Never trade against macro.** If CNX500 is in Bear or the sector is in Stage 3/4, no long setups exist — regardless of how good an individual stock looks. Macro kills more trades than any technical error.

**Never skip the Dashboard.** The Python screeners find candidates. The Pine screeners filter on raw data. The Dashboard is the final judge. No position is opened without a Dashboard reading of ≥ BUY with Alpha ≥ 60.

**Always cross-check Context Score before entry.** A BUY signal from the Unified Ecosystem with a CONTEXT SCORE below BULL (< 3) is a reduced-conviction entry. Size accordingly.

**Never size into a signal you cannot defend.** Know the stop-loss before entry. The Unified Ecosystem calculates the position size automatically; understand and verify the logic before placing the order.

---

## SECTION 2 — System Architecture & Daily Workflow

The complete end-to-end workflow runs in **five distinct phases**. The system is two-sided: a **Python backend** that does discovery + watchlist generation + portfolio sync, and a **TradingView frontend** that does signal validation + execution. The Bible walks both sides in the order you'll touch them.

```text
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 1 — PRE-MARKET INTELLIGENCE             (08:30–09:00 IST)        │
│  Commander Web v4.0                                                      │
│  ├── Macro+ Overview         → Global markets, India VIX, FII/DII       │
│  ├── Breadth Engine          → McClellan, Sector Breadth                 │
│  ├── AI Pre-Market Brief     → Gemini-generated strategy summary        │
│  └── Sector Dashboard        → Stage 2 + LEADING sector shortlist       │
└──────────────────────────┬───────────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 2 — DISCOVERY & WATCHLIST GENERATION    (08:00 batch OR ad-hoc)  │
│  Commander Web v4.0 → 🤖 Run Full Auto-Pilot                            │
│                                                                          │
│  Layer 1: chartink_replay.py (4 Bull scans + 3 Recovery scans)           │
│    SCAN_PARAMS_VERSION = "v2_FINAL_20260510" (Hunter wRSI≥60, ADX≥25)   │
│    Output: Bull_*.txt / Rec_*.txt in Generated_Watchlists/               │
│                                                                          │
│  Layer 2: matcher_replay.py — Screener.in conviction filter (≥6.0)      │
│    Output: FINAL_Hunter/Pullback/EarlyBird/Leader_Picks.csv (+ _RRG)   │
│            FINAL_Recovery_*.csv                                          │
│                                                                          │
│  Layer 3: Combined files + Golden Matcher                                │
│    Output: FINAL_COMBINED_BULL_PICKS.csv                                 │
│            FINAL_COMBINED_RECOVERY_PICKS.csv                             │
│            FINAL_WATCHLIST.csv (Golden Matcher conviction-ranked)       │
│                                                                          │
│  Layer 4: TradingView watchlist sync (Playwright/manual)                 │
│  + snapshot_archive.py → data/snapshots/YYYY-MM-DD/                      │
└──────────────────────────┬───────────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 3 — VALIDATION (TradingView, per-symbol)  (09:00–09:15 IST)      │
│  Bull Screener v3.2 (Bull) + Recovery Screener v2.0 (Recovery)          │
│  Dashboard v67.4.12 (final go/no-go)                                      │
│                                                                          │
│  For each ticker on the FINAL_* watchlists:                              │
│    ├── Bull Screener v3.2 — VERDICT row + 9 POS-BO gates                │
│    │      Hunter v1 FINAL: POS-BO needs wRSI≥60 + ADX≥25                │
│    │      POS-ACCUM catalyst DISABLED (backtest verdict — see §16)      │
│    │      pyScore: Python-aligned composite (use_python_aligned=ON)     │
│    ├── Dashboard v67.4.12 — Decision-Mode 13–18 composite rows:          │
│    │      Recommendation + Catalyst+Gates + Asset Quality (ACT NOW),    │
│    │      Weekly/Daily Structure + Price Action + Momentum + Levels,    │
│    │      Macro/Sector + RS (Mansfield) + Style, Portfolio, Top-5       │
│    └── Context Layers v1.2 — FINAL SCORE ≥ +4 (BULL); ≥ +9 (STRONG)    │
└──────────────────────────┬───────────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 4 — EXECUTION (TradingView, live chart) (09:15 onwards)          │
│  Weinstein_Unified_Ecosystem v3.6 (file: _v3.4.pine)                  │
│  + Context Layers v1.2 + Zigzag v6.2 (loaded on every chart)            │
│                                                                          │
│  Bull edges (6): POS-BO, POS-AC, SWG-PB, SWG-BO, SWG-REV, GAP-GO        │
│    + Wyckoff catalysts (3): WYC-SPRING, WYC-SOS, WYC-JAC                 │
│    POS-BO trigger: ... AND wRSI≥60 AND adx_val≥25                       │
│    POS-AC trigger: ... AND d_rsi≤50                                     │
│    ML probability score [ML: XX%] + RSI 47–54 dead-zone filter           │
│  Recovery edges (3): REV-CB, REV-RS, REV-EARLY                           │
│  Catalyst-aware trails: POS=4.5× ATR Chandelier (was 3.0×),             │
│    SWG=SMA50 trail (was EMA20). Swing targets 3R/5R (was 5R/10R) +33%.  │
│  CATALYST DIAG panel: shows first failing gate per catalyst.             │
│  Kelly position sizing                                                   │
└──────────────────────────┬───────────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 5 — POST-MARKET & PORTFOLIO MGMT           (16:00 onwards)       │
│  ├── master_portfolio_sync.py → Dashboard v67.4.12 OPEN portfolio slots      │
│  │     (slots 1–30 are for OPEN positions only — NEVER for watchlist)   │
│  ├── Telegram alerts via Risk Allocator v1.0                             │
│  ├── Trade Autopsy + Journal in Commander Web                            │
│  └── snapshot_archive.snapshot_today() → archive day's CSVs              │
└──────────────────────────────────────────────────────────────────────────┘
```

**Key architectural separations to internalize:**

| Concept | Lives In | Purpose |
|---------|----------|---------|
| **Watchlists** (Bull + Recovery) | `Generated_Watchlists/*.txt`, `FINAL_*.csv`, TradingView watchlist | Pre-validated candidates from Phase 2 — *not yet entered* |
| **Open positions** | Dashboard v67.4.12 portfolio slots 1–30 (filled by `master_portfolio_sync.py` from Dhan) | Stocks you actually hold — entry price, SL, date, P&L tracked |
| **The Score** that drives Top-N selection | Python `bull_screener.calculate_score()` | After v2.9, mirrored in Pine as `pyScore` |
| **The signal-fire trigger** | Pine `pos_bo_trigger` / `pos_ac_trigger` / etc. in Unified Ecosystem v3.4 | What actually creates an entry |

**Context overlay (loaded on every chart alongside the Unified Ecosystem):**
- `Zigzag v6.2` — HH/HL/LH/LL/EH/EL trend state with 11-row panel (TIMEFRAME, TREND, MTF TREND, STRUCTURE, SWING COUNT, SWING RANGE, CHOPPINESS, INVALIDATION, BOS LEVEL, VOL CONFIRM, BAR AGE). Longs-Only Mode default ON. Fib retracements (50/61.8) + extensions (1.272/1.618). All fields developing-pivot aware.
- `Context Layers v1.2` — unified institutional context: Wyckoff events, Volume Profile (POC/VAH/VAL), SMC zones (OBs, FVGs, Sweeps), CONTEXT SCORE panel. **v1.2 adds Setup Detector bonus** (+2 S2 Spring/LPS, +2 S3 Sweep+CHoCH, +1 S1 OB Retest, −2 S7 Distribution, −1 S8 Choppy). Panel grew to 24 rows: BASE SCORE / SETUP BONUS / FINAL SCORE / BREAKDOWN.

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
PINE_SCRIPT_PATH=C:\Users\jayra\Documents\GeminiVSCode\Weinstein and Swing Pro Dashboard v67.4.12.pine
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
1. `Weinstein & Swing Pro Dashboard v67.4.12` — mission control; Decision-Mode 13–18 composite rows. Toggle "Show Detailed View" to expand to ~60 rows.
2. `Weinstein_Unified_Ecosystem_v3.4.pine` (in-file `[v3.6]`) — single strategy script for 9 catalysts + 3 Wyckoff catalysts. ML probability score + CATALYST DIAG panel.
3. `Weinstein_Context_Layers_v1.2` — unified context overlay (Wyckoff + Volume Profile + SMC) with FINAL SCORE panel (BASE + SETUP BONUS + FINAL + BREAKDOWN).
4. `Commander_Recovery_Screener_v2.0.pine` — 4-pillar CB + Wyckoff Phases (B/C/D) + RFF + 10 gates paired 2-per-row.
5. `Commander_Bull_Screener_v3.2.pine` — Verdict + 9 POS-BO gates + Trade Levels.
6. `Wesinstein Swing Zigzag [Strict v6.2]` — HH/HL/LH/LL/EH/EL state, longs-only mode, MTF trend confluence, Invalidation + BoS Level lines, fib retracements + extensions, volume confirmation.

**Remove from layouts:** The three legacy standalone indicators — `Weinstein_Wyckoff_Phases_v1.0`, `Weinstein_Volume_Profile_v1.0`, `Weinstein_SMC_Zones_v1.0` — are now fully replaced by Context Layers v1.2. Running both creates duplicate labels and conflicting chart drawings.

**Critical input consistency** (must match across all indicators):
- Weinstein SMA Length: **30 weeks** (Weekly timeframe)
- Pivot Left/Right: **2/2** (Zigzag, Strategy, Recovery, Screeners)
- ATR Length: **14** (all Pine modules)
- Chandelier Exit Length: **22**, ATR Mult (Bull): **3.0** (Unified Ecosystem)
- RS Slope Lookback: **5 weeks** (Dashboard, Bull Screener)

---

## SECTION 4 — Context Layer (Load First, Change Never)

Before running any screener or reading any signal, load the context tools on a daily chart. These do not generate entry signals — they tell you *where you are* in market structure and confirm whether institutional activity supports the trade.

### Zigzag v6.2 (Strict)

The Zigzag is no longer just a label-on-pivot tool — it's an 11-row panel with developing-pivot awareness across every field. Default mode is **Longs-Only**.

**Reading the panel top-to-bottom:**

| Row | What it tells you |
|---|---|
| TIMEFRAME | Current chart resolution (Monthly / Weekly / Daily / N min) |
| TREND | 🟢 UPTREND / 🔴 DOWNTREND / 🟡 SIDEWAYS — developing-aware (flips live when projected BoS/CHoCH detected) |
| MTF TREND | Higher-TF trend state. Auto-resolves intraday→D, D→W, W→M. **Confluence with current TF = full conviction; conflict = countertrend** |
| STRUCTURE | `<high class> / <low class>` — e.g. `HH / HL` (uptrend), `LH / LL` (downtrend), `EH / EL` (equal sideways) |
| SWING COUNT | N swing(s) in current trend state. ≥ 3 = extended (yellow warning) |
| SWING RANGE | % distance of currently developing swing. Gray < majorThresh, Green 1–2×, Yellow > 2× |
| CHOPPINESS | N flips / 26W or 52W. Green ≤ 4 / Yellow 5–8 / Red > 8 |
| **INVALIDATION** | Latest swing **low** (longs-only) — your structural stop. e.g. `3479.00 (LL)` |
| **BOS LEVEL** | Latest swing **high** — your bullish BoS entry trigger. e.g. `3595.00 (LH)`. Stays visible after break (option-a retest reference) |
| VOL CONFIRM | Volume on last ↑ BoS vs 50-SMA. ✅ ≥ 1.5× / ❌ < 1.5×. Bearish breakdowns NOT captured in longs-only mode |
| BAR AGE | Bars elapsed since active pivot — swing maturity gauge |

**Read together:** an UPTREND with MTF confluence ✅, fresh BAR AGE, healthy SWING RANGE, low CHOPPINESS, BoS Level just broken on VOL CONFIRM ✅ 2.0× = textbook setup.

**Major/Minor pivots:** thicker lines + larger labels for pivots exceeding the major threshold (Auto: 8% Stock / 4% ETF, or custom).

**Fib levels on chart:** purple 50% / orange 61.8% retracements (pullback support); teal 1.272 / lime 1.618 extensions (long profit targets).

---

### Context Layers v1.2 (Unified Context Overlay)

**Context Layers v1.2 combines three frameworks into one indicator** with a Setup Detector that feeds a signed bonus back into the score. Load it once and you get Wyckoff phase labels, Volume Profile levels, SMC zones, and a Setup-aware FINAL SCORE.

#### BASE SCORE → SETUP BONUS → FINAL SCORE

```
BASE SCORE  = Wyckoff (−4 to +4) + VP (−3 to +3) + SMC (−3 to +3) + OB Proximity (−2 to +2)
            range: −12 to +12

SETUP BONUS = +2 (S2 Spring/LPS Reversal)    | +1 (S1 OB Retest + VP Support)
              +2 (S3 Sweep + CHoCH Reversal)  | 0  (S4/S5/S6 — already in components)
              −1 (S8 Choppy Range)            | −2 (S7 Distribution Breakdown)

FINAL SCORE = BASE + BONUS  (range: −14 to +14)
```

**Why bonus?** Without it, a confirmed S2 Spring fired at a borderline base score (e.g., 6) couldn't distinguish itself from a flat base 6. The +2 bonus tips it into STRONG BULL territory — making conviction visible on the panel.

**Anti-circularity is enforced by code order:** components compute → Setup Detector runs using BASE SCORE only → bonus computed from detected setup → FINAL = BASE + BONUS → band assigned from FINAL. Setups never see their own bonus.

| FINAL Score | Label | Meaning for Trading |
|---|---|---|
| ≥ 9 | **STRONG BULL** | All three modules aligned + active setup bonus. Full-size entry (1.25× Kelly). |
| 4 to 8 | **BULL** | Majority aligned bullish. Normal-size entry. |
| −3 to +3 | **NEUTRAL** | Mixed signals. Be selective; reduce size 25–50%. |
| −4 to −6 | **CAUTION** | Majority aligned bearish. No new longs. |
| ≤ −7 | **BEAR** | All modules aligned bearish + likely S7 bonus. Flat or exit. |

> **Threshold update:** STRONG BULL raised from ≥ 8 (v1.1) to ≥ 9 (v1.2) to account for bonus headroom. Other bands unchanged.

**Trading rule:** Only enter new positions when FINAL SCORE is BULL or STRONG BULL **and** SETUP BONUS ≥ 0. A negative SETUP BONUS comes from S7 (Distribution) or S8 (Choppy) — both are exit / sit-out signals even if FINAL SCORE is still in BULL band (stale signal).

**Panel rows added (rows 20–23):**

```
── SCORE ──                                       ← row 19 divider
BASE SCORE     ● 6                                ← row 20 (raw _total)
SETUP BONUS    ✓ +2 (from S2)                     ← row 21 (signed + attribution)
FINAL SCORE    ✓ STRONG BULL (6+2=8)              ← row 22
BREAKDOWN      Wyk:3 VP:3 SMC:0 Stg:0 Bns:+2      ← row 23
```

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

## SECTION 5 — Phase 1: Pre-Market Intelligence

**When:** 8:30 AM - 9:00 AM (Before market open)

**Where:** Commander Web v4.0 → `http://localhost:5000` (Pre-Market Hub)

**Goal:** Assess macro risk, track institutional flows, and synthesize the daily strategy.

### Step 5A — Macro & Breadth Check
1. **Navigate to the Pre-Market Hub** in Commander Web.
2. **Global Markets:** Check overnight US closes and morning Asian markets.
3. **FII/DII Activity:** Note institutional net flows from the previous session.
4. **India VIX:** A spiking VIX (> 15) requires smaller position sizing today.
5. **Breadth Engine:** Check the McClellan Oscillator. If negative, favor tightening stops over fresh longs.

### Step 5B — AI Pre-Market Briefing
1. Click **Generate AI Briefing**.
2. The Gemini Reporter synthesizes the macro data into a single strategy recommendation (e.g., "Risk On", "Defensive", "Cash Heavy").
3. Proceed to Phase 2 only if the AI Briefing allows capital deployment.

---

## SECTION 6 — Phase 2: Discovery & Screening (Python)

**When:** Evening after market close, or 30–45 minutes before market open.

**Where:** Commander Web v4.0 → `http://localhost:5000` (Scanners Tab)

**Goal:** Build the day's watchlist from 500 NSE stocks to 15–25 candidates.

---

### Step 6A — Sector Dashboard (First, Always)

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

### Step 6B — Bull Screener (Bull Market / Stage 2 Stocks)

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

### Step 6C — Recovery Screener (Corrected Market / Stage 1 Stocks)

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

### Step 6D — Portfolio Sync (Open Positions Only)

Open **Tab 1: Portfolio Sync**.

Click **"Sync from Dhan"**. This fetches all open Dhan positions and injects them into `Weinstein and Swing Pro Dashboard v67.4.12.pine`:
- Slots 1–30 populated with ticker, entry price, stop-loss, sector index, entry date
- Largest positions by value filled first

**After sync completes:** Open TradingView, right-click the Dashboard indicator → "Reload". Your portfolio data is now live.

**Verify the sync:** Load any current holding on the chart. The ENTRY, STOP, R-VALUE, and TIME WARN rows should show real data, not dashes.

> **CRITICAL — what NOT to put in portfolio slots:**
> Slots 1–30 are exclusively for **open positions** you actually hold in Dhan. They are NOT for watchlist candidates. The slot bookkeeping (P&L, R-multiple, days held, time-stop warnings, ATR-trailed stop alerts) only makes sense once a position is live with a real entry, SL, and date. If you put a watchlist ticker in a slot, all those metrics will lie to you.
>
> Watchlist stocks live in:
> - `Generated_Watchlists/Bull_*.txt` and `Generated_Watchlists/Rec_*.txt` (raw Layer 1 output)
> - `FINAL_Hunter_Picks.csv` / `FINAL_Pullback_Picks.csv` / etc. (Layer 2 conviction-filtered)
> - `FINAL_COMBINED_BULL_PICKS.csv` and `FINAL_COMBINED_RECOVERY_PICKS.csv` (Layer 3 union)
> - `FINAL_WATCHLIST.csv` (Golden Matcher conviction-ranked)
> - TradingView's native watchlist (imported via Watchlist Manager Tab 2)

---

### Step 6E — 🤖 Run Full Auto-Pilot — The Production Watchlist Pipeline

**This is the canonical way to generate the day's tradeable watchlist.** The Auto-Pilot button is in the Workflow / Auto-Pilot tab in the Commander Web. One click runs the entire 4-layer pipeline.

**What runs (in order):**

**Layer 1 — Chartink-equivalent scans** (`bull_screener.py` + `recovery_screener.py`):

| Scan | Output file | What it finds |
|------|-------------|---------------|
| Hunter (POS-BO equivalent) | `Bull_Hunter-DDMMMYY.txt` | Stage 2 breakouts (v1 FINAL: weekly RSI ≥ 60, ADX ≥ 25) |
| Pullback | `Bull_Pullback-DDMMMYY.txt` | EMA20 pullbacks in established uptrends |
| EarlyBird | `Bull_EarlyBird-DDMMMYY.txt` | Early-entry setups (`disable_rsi=True` per v1 FINAL) |
| StrongLeader | `Bull_StrongLeader-DDMMMYY.txt` | High RS + ADX leaders |
| REV-CB | `Rec_Climax_Bounce-DDMMMYY.txt` | Climax bottom + turn bar |
| REV-RS | `Rec_RS_Survivor-DDMMMYY.txt` | RS-positive recovery candidates |
| REV-EARLY | `Rec_Early_Bird-DDMMMYY.txt` | Trendline reclaim on compressed base |

**Layer 2 — Screener.in conviction filter** (`brute_force_match_pro.py` against today's `MASTER_scan_results.csv` snapshot):

For each Layer-1 output, only stocks with conviction score ≥ 6.0 (matcher production default) survive. Conviction score is a composite of profit growth, sales growth, ROE, ROCE, D/E, market cap, dividend yield, and promoter holding %.

| Filtered output | Equivalent RRG-tagged copy |
|-----------------|----------------------------|
| `FINAL_Hunter_Picks.csv` | `FINAL_Hunter_Picks_RRG.csv` |
| `FINAL_Pullback_Picks.csv` | `FINAL_Pullback_Picks_RRG.csv` |
| `FINAL_EarlyBird_Picks.csv` | `FINAL_EarlyBird_Picks_RRG.csv` |
| `FINAL_Leader_Picks.csv` | `FINAL_Leader_Picks_RRG.csv` |
| `FINAL_Recovery_ClimaxBounce.csv` | — |
| `FINAL_Recovery_EarlyBirds.csv` | — |
| `FINAL_Recovery_RSLeaders.csv` | — |

**Layer 3 — Combined files**:

- `FINAL_COMBINED_BULL_PICKS.csv` — union of all 4 bull FINAL files, deduplicated.
- `FINAL_COMBINED_RECOVERY_PICKS.csv` — union of all 3 recovery FINAL files, deduplicated.
- `FINAL_COMBINED_PICKS.csv` — everything bull + recovery, deduplicated.
- `FINAL_WATCHLIST.csv` — the **Golden Matcher** output, conviction-ranked. **This is the single best file to load into TradingView for Phase 3 validation.**

**Layer 4 — TradingView watchlist sync** (`watchlist_manager.py`, `watchlist_ranker.py`, optional Playwright automation in `tradingview_automation_v2.py`):

The Layer-3 outputs are formatted as TradingView-importable `.txt` files in `Generated_Watchlists/` (with a `LATEST_*.txt` symlink for the most recent run). You then either (a) manually copy-paste into TradingView's watchlist import, or (b) let the Playwright script inject them automatically.

**Forward archive** (`snapshot_archive.snapshot_today()`): copies the day's CSV outputs to `data/snapshots/YYYY-MM-DD/` — going forward, this builds a real point-in-time historical Screener.in dataset for future backtesting (currently the filtered-universe backtester falls back to yfinance for older anchors; see §16.4).

**How to use Run Full Auto-Pilot:**
1. Open Commander Web → Workflow / Auto-Pilot tab
2. Click **🤖 Run Full Auto-Pilot** ("Execute full pipeline: Scanners → Fundamentals → Golden Matching → Watchlist Sync → Initiate")
3. Wait 5–10 minutes (depends on universe size and yfinance throttling)
4. When complete: open TradingView, switch to your "Commander Auto-Pilot" watchlist (or import `LATEST_Bull_Picks_All.txt` + `LATEST_Recovery_Picks_All.txt` manually)
5. Proceed to Phase 3 (Pine validation per ticker)

> **Tip:** Run the Auto-Pilot **once per day** in the morning (08:00–08:30 IST). Mid-session re-runs rarely surface new candidates because the underlying data only updates EOD. If you must re-run intraday, do it after a major index move (≥1%) to capture late-day catalysts.

---

## SECTION 7 — Phase 3: TradingView Validation (Re-Screening & Dashboard)

**When:** During the first 30 minutes of market open, after overnight Python output is in hand.

**Purpose:** Re-screen Python shortlist against live candle data. Python EOD data misses pre-market gaps, intraday volatility shifts, and volume anomalies.

---

### Step 7A — Bull Candidates (Commander Screener Beta Edition v2.9)

**For each ticker on the FINAL_COMBINED_BULL_PICKS.csv (or `LATEST_Bull_Picks_All.txt`) watchlist:**

1. Load the ticker on TradingView (daily timeframe)
2. Bull Screener v3.2 plots signals directly on the chart. Look for active catalyst labels.
3. **Check `pyScore` (the displayed `score`)** — should be ≥ 60. (`pyScore` mirrors `bull_screener.calculate_score()` byte-for-byte; the `use_python_aligned_score` toggle is ON by default.)
4. **Check `alphaScore`** — independent gate, must be ≥ 60. Without alpha_ok, no catalyst can fire.
5. Verify RS line vs CNX500 — is it LEADING or IMPROVING?
6. Vol Shelf label: **VWMA20 > VWMA50** (institutional accumulation confirmed)
7. VCP Tight label: **ATR < 1.0× Average ATR** (squeeze active — Unified Ecosystem threshold)
8. OBV: **2-bar consecutive rise AND OBV > OBV SMA20** (Unified Ecosystem POS-AC gate)

**v2.9 Pass/fail by catalyst (NEW gates in bold):**

| Catalyst | Bull Screener v3.2 Re-Screen Check | Unified Ecosystem v3.4 Gate |
|---|---|---|
| POS-AC | OBV rising 2 bars + above OBV SMA20 + **dailyRsi ≤ 50 (v2 LOCK)** | VWMA20 > VWMA50; **d_rsi ≤ pos_accum_rsi_max (v2.3)** |
| POS-BO | Volume ≥ 1.5× 50-day avg on breakout candle + **wRsiVal ≥ 60 + numeric ADX ≥ 25 (v1 FINAL Hunter)** | VWMA20 > VWMA50; close above 20-bar high; **wRSI ≥ 60 + adx_val ≥ 25 (v2.3)** |
| SWG-PB | VCP Tight (ATR < 1.0×); MA stack (SMA150 > SMA200); RSI 30–70 | Volume dry-up: 3-bar vol < 50-bar avg |
| SWG-BO | ATR < 1.0× (VCP Tight); Volume < 50-bar avg (consolidation) | Volume ≥ 1.5× on breakout candle |
| SWG-REV | RSI < 35; price above SMA200; close > High[1] | 5-day time stop applies; quick-scalp trade |
| GAP-GO | Gap ≥ 4%; intraday close position ≥ 60%; volume ≥ 3× average | Check by 11:30 AM IST |

**v2.9 NEW — Defensive Mode:** If the broader market regime is weak (CNX500 in correction, McClellan negative, or you're cautious), turn on the input `Defensive Mode: Days_Since_Pivot Penalty`. This subtracts 10 from `pyScore` if the bars since the last `isBreakout` exceed 30 — penalising chases of extended bases. Backtest evidence: lifts hit-rate but truncates upside; use only when capital preservation matters more than upside magnitude.

**Reduce to 5–8 confirmed candidates.** Drop anything that fails the new Hunter or POS-ACCUM gates — these gates encode the v1 FINAL + v2 LOCK backtest verdict and are not negotiable.

---

### Step 7B — Recovery Candidates (Commander Recovery Screener v2.0)

**For each of your top 10 Python Recovery candidates:**

1. Load the ticker on TradingView (daily timeframe)
2. Recovery Screener v2.0 plots the four REV pillars + Wyckoff Phase labels (B/C/D) on the chart
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

### Step 7C — Dashboard Validation (Per Chart)

**When:** After Pine re-screening produces 5–8 bull + 3–5 recovery candidates.

**Where:** Load each candidate on its own chart with the Dashboard visible.

**Rule:** Every candidate must pass ALL applicable dashboard gates before proceeding to execution. No exceptions.

> **Recovery candidates note (v67.0):** Dashboard v67.4.12 has removed its dedicated Recovery section. Recovery candidates still pass through the Dashboard's macro, sector, RS, and Alpha gates (left column). Recovery-specific signal state — REV pillars, regime gate, RFF score — was already validated in Step 6B via the Recovery Screener v2.0 and Unified Ecosystem panel. Do not look for a RECOVERY row in the Dashboard right column; it no longer exists.

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

> **Note (v67.0):** The RECOVERY section has been removed from Dashboard v67.4.12. Recovery signal validation — REV-CB pillars, REV-RS breakout status, REV-EARLY compression check — is now handled exclusively through (a) the **Commander Recovery Screener v2.0** (real-time pillar display on chart) and (b) the **Weinstein_Unified_Ecosystem_v3.4.pine** recovery panel (regime gate, CB pillars P1–P4, RFF score). Do not expect a recovery row in the Dashboard right column.

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

## SECTION 7D — The Confluence Sequence: Module-by-Module Walkthrough

> **Read this section first when you sit down to trade.** This is the operational order in which you touch every module in the ecosystem, what to look at in each, the **minimum values** that are non-negotiable, and the **confluence factors** that distinguish a high-conviction setup from a marginal one.
>
> The sequence is one-directional: each step's output gates the next step. If a step fails at its hard floor, the candidate is **dead** for that day — do not "make up for it" with a strong reading downstream. The hard floors encode the v1 FINAL + v2 LOCK backtest verdicts; bypassing them is bypassing the system.

### The 9-Step Trading Sequence (top to bottom, every trade, every day)

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                     PRE-MARKET (08:00 – 09:15 IST)                      │
│  Step 1  Macro & Breadth Health Check          (Commander Web)          │
│  Step 2  Sector Stage Filter                   (Commander Web Tab 5)    │
│  Step 3  Run Full Auto-Pilot → Watchlist       (Commander Web Tab 4.5)  │
├─────────────────────────────────────────────────────────────────────────┤
│              PER-TICKER VALIDATION (09:15 – 10:30 IST)                  │
│  Step 4  Bull Screener v3.2 reading            (TradingView)            │
│  Step 5  Dashboard v67.4.12 final go/no-go      (TradingView)            │
│  Step 6  Context Layers v1.2 FINAL SCORE       (TradingView)            │
│  Step 7  Zigzag v6.2 structural confirmation   (TradingView)            │
├─────────────────────────────────────────────────────────────────────────┤
│              EXECUTION (signal-fire bar onwards)                        │
│  Step 8  Unified Ecosystem v3.4 trigger        (TradingView)            │
│  Step 9  Risk Allocator v1.0 sizing + alert    (TradingView)            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Step 1 — Macro & Breadth Health Check

**Module:** Commander Web v4.0 → Macro+ Overview, Breadth Engine, AI Pre-Market Brief
**Why first:** Macro kills more trades than any technical error. If the regime is wrong, no individual setup is good enough to overcome it.

| Reading | Hard Floor (must pass) | Confluence Factors |
|---------|------------------------|---------------------|
| **CNX500 regime** | NOT in BEAR (Stage 4 / below SMA200 + falling) | Want BULL (above SMA200, SMA50 > SMA200) for full size; RECOVERY (above SMA50 but SMA50 < SMA200) for half size |
| **India VIX** | < 22 | < 16 = optimal, calm market; 16–22 = elevated but tradeable; > 22 = halve all sizing |
| **McClellan Oscillator** | > −50 | > 0 = breadth confirms; > +50 = strong breadth thrust |
| **FII/DII flow (5-day)** | Not net selling > ₹10,000 Cr | Net buyers = wind at your back; persistent FII selling = avoid POS-BO, prefer POS-AC |
| **Sector Breadth** | ≥ 4 of 12 sectors in Stage 1/2 | ≥ 7 sectors = broad bull; ≤ 3 sectors = narrow leadership, swing-only |

**Disqualifier:** CNX500 in confirmed BEAR + VIX > 25 → **NO BULL TRADES TODAY**. Switch to Recovery-only mode (REV-CB / REV-RS / REV-EARLY) and even those at half normal sizing.

---

### Step 2 — Sector Stage Filter

**Module:** Commander Web v4.0 → Tab 5: Sector Dashboard
**Why second:** Even in a bull market, half the sectors are typically sideways or rolling over. You want stocks **in the leading sectors**, not just any Stage 2 stocks.

| Reading | Hard Floor | Confluence Factors |
|---------|-----------|---------------------|
| **Stock's auto-detected sector — Weinstein Stage** | Stage 1 or Stage 2 | Stage 2 + Rising 30W slope = ideal hunting ground |
| **Sector RRG quadrant** | NOT LAGGING | LEADING = full conviction; IMPROVING = early-cycle, smaller size; WEAKENING = avoid POS-BO |
| **Sector Mansfield RS vs CNX500** | ≥ 0 | ≥ +5 = sector is leading market; ≥ +10 = strong rotation in |
| **Weeks in current sector stage** | ≤ 26 weeks (Stage 2 freshness) | < 13 weeks = early Stage 2 (best); 13–26 = mature Stage 2 (still good); > 26 = late-cycle, downgrade size |

**Disqualifier:** Sector in **Stage 3 or 4** → skip the candidate regardless of how strong the individual stock looks. Don't fight sector rotation.

**Confluence boost:** Top 3 sectors all in Stage 2 + LEADING + Rising RS → bias your entire watchlist to those sectors for the day.

---

### Step 3 — Run Full Auto-Pilot — Watchlist Generation

**Module:** Commander Web v4.0 → Workflow tab → 🤖 Run Full Auto-Pilot
**Why third:** This narrows Nifty 500 down to ~10–33 candidates per day via the two-layer filter (Chartink-equivalent → Screener.in conviction ≥ 6.0). These are your candidates for Step 4 onwards.

| Output | What to use | Hard Floor |
|--------|-------------|-----------|
| `FINAL_WATCHLIST.csv` (Golden Matcher conviction-ranked) | Top 15 conviction-ranked candidates for the day | Conviction ≥ 6.0 (already enforced by matcher) |
| `FINAL_COMBINED_BULL_PICKS.csv` | All bull-side candidates (Hunter + Pullback + EarlyBird + Leader) deduplicated | All 4 Layer-1 scans passed |
| `FINAL_COMBINED_RECOVERY_PICKS.csv` | All recovery candidates (only relevant if regime is Recovery) | Use only when CNX500 ≥ 7% off 52W high |
| `FINAL_Hunter_Picks.csv` | Just the Hunter (POS-BO equivalent) candidates | wRSI ≥ 60 + ADX ≥ 25 (v1 FINAL Hunter, baked in) |

**Confluence boost:** A ticker that appears in BOTH `FINAL_Hunter_Picks.csv` AND `FINAL_Leader_Picks.csv` is a **dual-strategy confirmation** — highest priority for Step 4. (Example: NETWEB on the 8 May Master Picks list appeared in both Hunter and Strong Leaders at conviction 8.5.)

**Disqualifier:** A ticker that fails to make the Layer-2 conviction cut (≥ 6.0) is filtered out before this step. If you find yourself manually adding a ticker outside the Auto-Pilot output, you are bypassing the system — do not.

---

### Step 4 — Bull Screener v3.2 Reading (Per Ticker)

**Module:** `Commander_Screener_Beta_Edition_v2.9.pine` on each candidate's daily chart
**Why fourth:** Re-screens the Python output against live candle data. Catches gaps, intraday shifts, and volume anomalies the EOD pipeline missed.

| Reading | Hard Floor | Confluence Factors |
|---------|-----------|---------------------|
| **Catalyst** (POS-BO/POS-AC/SWG-PB/SWG-BO/SWG-REV/GAP-GO) | > 0 (some catalyst must be active) | Match the catalyst to today's market regime: bull = POS-BO/POS-AC; pullback day = SWG-PB; gap day = GAP-GO |
| **`alphaScore`** (the gate) | **≥ 60** | ≥ 80 = STRONG BUY tier; 60–79 = BUY tier; < 60 = NO catalyst can fire (alpha_ok blocks) |
| **`pyScore`** (Python-aligned, displayed as Score with toggle ON) | **≥ 60** | ≥ 80 = full size; 60–79 = normal size; 40–59 = half size maximum; < 40 = pass |
| **9-Gate POS-BO panel** (only for POS-BO) | **≥ 8 / 9 gates** ✓ | All 9 ✓ = highest conviction breakout; 7/9 = watch only, do not enter |
| **`hunter_adx_ok`** (numeric ADX ≥ 25, NEW v2.7) | TRUE for POS-BO | ADX 30+ = strong trend confirmation |
| **`wRsiVal ≥ 60`** (NEW v2.7) | TRUE for POS-BO | wRSI 65+ = momentum confirmed at weekly level |
| **POS-ACCUM RSI gate** (`dailyRsi ≤ 50`, NEW v2.8) | MUST hold for POS-AC to even fire | RSI ≤ 40 = textbook accumulation territory; 40–50 = late but still valid |
| **OBV trending up + above OBV SMA20** | TRUE for POS-AC and POS-BO | Confirms institutional accumulation |
| **VCP Tight** (ATR < 1.0× ATR SMA50) | REQUIRED for SWG-BO; preferred for POS-BO | Tighter base = sharper breakout |
| **Vol Shelf** (VWMA20 > VWMA50) | TRUE for POS-BO and POS-AC (Macro Edge) | Without it, downgrade size by 50% |
| **Catalyst-specific volume** | Per catalyst (POS-BO 1.5×, GAP-GO 3.0×) | Volume ≥ 2× = exceptional commitment |

**Disqualifier:** `alphaScore < 60` OR `pyScore < 60` OR no active catalyst → next candidate.

**Confluence boost (the gold standard):** `pyScore ≥ 80` + Catalyst = POS-BO + 9/9 gates ✓ + wRSI ≥ 65 + ADX ≥ 30 + Vol Shelf ✓ + OBV rising → STRONG BUY tier, full position size.

---

### Step 5 — Dashboard v67.4.12 Final Go/No-Go (Per Ticker)

**Module:** `Weinstein and Swing Pro Dashboard v67.4.12.pine` on the same chart
**Why fifth:** The Dashboard is the **final judge**. It synthesises every other module's reading into one table and produces the binary STRONG BUY / BUY / WAIT recommendation. Never enter a position without the Dashboard reading at ≥ BUY.

| Row | Hard Floor | Confluence Factors |
|-----|-----------|---------------------|
| **MACRO** | GREEN (Bull) or YELLOW (Recovery) — never RED | GREEN + sector at Stage 2 = full conviction |
| **SECTOR** | Stage 1 or 2 | Stage 2 + LEADING RRG = full conviction |
| **STAGE** (Weinstein weekly) | Stage 2 (UP) ideally; Stage 1 (BASE) for early entries | Stage 2.1 + Stage Weeks 4–13 = ideal early-cycle |
| **30W SMA** slope | Rising ↑ | Rising > 0.0005 threshold AND price above 30W SMA |
| **RS vs N50** | Positive Mansfield ×100 | LEADING = top quartile vs Nifty 50 |
| **RS vs N500** | LEADING (or IMPROVING for BUY tier) | LEADING + Mansfield ≥ +10 = textbook Minervini leader |
| **RS vs SECTOR** | Positive (stock leading its sector) | Positive on both axes (RS vs N500 + vs Sector) = sector rotation leader |
| **50DMA** | Above + Rising | Rising + price within 5% above = optimal pullback zone |
| **ALPHA SCORE** | **≥ 60** | ≥ 80 = full size; 60–79 = normal; < 60 = WAIT |
| **GRADE** | A or A+ | A+ = STRONG BUY tier; A = BUY tier; B = reduced size; C/D = pass |
| **PATTERN** | Active VCP / Base / Breakout / Flag | Pattern matches catalyst label = thesis intact |
| **CATALYST** (must match Bull Screener) | Active and matching | Same catalyst on Beta + Dashboard = high conviction |
| **RECOMMENDATION** | **STRONG BUY or BUY** | STRONG BUY = full size; BUY = normal; BUY* = check fundamentals first; PULLBACK = re-entry only; WAIT = pass |
| **ENTRY / STOP** (only if portfolio slot matches) | Real values, not dashes | Confirms slot mapping is correct |
| **RECOVERY panel** (if applicable) | All 4 REV-CB pillars or RS Survivor / Early Bird active | Use only when in Recovery regime |

**Disqualifier:** Recommendation = WAIT or WATCH OR Macro = RED OR Stage = 3/4 OR Alpha < 60 OR Grade = C/D → next candidate.

**Confluence boost:** STRONG BUY + Macro GREEN + Sector Stage 2 + Stage 2.1 + RS LEADING (both) + Vol Shelf YES + Pattern matches Catalyst → maximum confidence entry.

---

### Step 6 — Context Layers v1.2 Confluence

**Module:** `Weinstein_Context_Layers_v1.0.pine` overlay on the chart
**Why sixth:** Wyckoff narrative + Volume Profile (where the value is) + SMC institutional footprint, summarized into one CONTEXT SCORE panel (range −12 to +12). Tells you whether smart money is genuinely accumulating.

| Reading | Hard Floor | Confluence Factors |
|---------|-----------|---------------------|
| **CONTEXT SCORE** | **≥ +3 (BULL)** for full size; ≥ 0 (NEUTRAL) for half size | ≥ +6 = STRONG BULL; ≥ +9 = MAX CONVICTION |
| **Wyckoff Bias** | ACCUMULATION (for bull entries) or NEUTRAL | Bull = ACCUMULATION + SOS/LPS event ≤ last 20 bars |
| **Wyckoff Phase Event** (recent) | Sign of Strength (SOS) or Last Point of Support (LPS) for bull entries; SC/ST for REV-CB | SOS = best bull confirmation; LPS = textbook pullback entry trigger |
| **Volume Profile — Price location** | Price at or above POC (Point of Control) for bull entries | Above VAH (Value Area High) = strong; at POC = neutral; below VAL = WEAK, skip |
| **Volume Profile — Distance to POC** | Within 2 ATR | Buying near POC = lower-risk entry; far above = extended |
| **SMC Trend** | BULLISH or NEUTRAL | BULLISH + active OB support below = ideal |
| **Active Bull Order Block** | Should exist below current price | Recent bull OB within 1 ATR below current = high-quality SL location |
| **Liquidity Sweep** (if recent) | Bullish sweep below recent low + reclaim | Confirms a stop-hunt → trap setup; +20 Alpha bonus in Bull Screener |

**Disqualifier:** CONTEXT SCORE ≤ −3 (BEAR) OR Wyckoff Bias = DISTRIBUTION → skip regardless of Step 4–5 readings. The institutional context is telling you smart money is exiting.

**Confluence boost:** CONTEXT ≥ +6 + Wyckoff = ACCUMULATION + recent SOS event + price above POC + active bull OB below + recent bullish liquidity sweep → 5-of-5 institutional confluence, full size warranted.

---

### Step 7 — Zigzag v6.2 Structural Confirmation

**Module:** `Wesinstein Swing Zigzag [Strict v6.2].pine` overlay on the chart
**Why seventh:** Confirms the price structure (HH/HL/LH/LL state machine) actually agrees with the bull thesis. A POS-BO call on a chart printing LH/LL is structurally inconsistent — the catalyst may be a fakeout.

| Reading | Hard Floor | Confluence Factors |
|---------|-----------|---------------------|
| **Trend State** | HH-HL (Higher High / Higher Low) for bull entries | Pure HH-HL sequence over last 3 swings = clean uptrend |
| **Last Swing High** | Above previous swing high | Recent break of swing high = breakout structurally confirmed |
| **Last Swing Low** | Above previous swing low | Strong sequence = no recent pullback violations |
| **Pivot lookback** | Left=2, Right=2 (must match Bull Screener and Unified Ecosystem) | Inconsistent pivot settings = inconsistent signals across modules |

**Disqualifier:** LH-LL (Lower High / Lower Low) on the active timeframe → structural downtrend. Skip bull entries entirely.

**Confluence boost:** HH-HL on both daily AND weekly timeframes → multi-timeframe structural alignment.

---

### Step 8 — Unified Ecosystem v3.4 Signal Trigger (Entry)

**Module:** `Weinstein_Unified_Ecosystem_v3.4.pine` (in-file `[v3.6]`) on the chart
**Why eighth:** This is where the actual entry signal fires. By now Steps 1–7 have given you a fully validated candidate; the Unified Ecosystem decides the **exact bar** to enter.

| Trigger | Hard Floor (built into v2.3) | Manual Confluence Factors |
|---------|-----------------------------|----------------------------|
| **`pos_bo_trigger`** | base_confirmed + alpha_ok + rs_ok + micro_ok + breakout + 1.5× volume + vol_shelf_ok + **wRSI ≥ 60** + **ADX ≥ 25** | Wait for the breakout candle to CLOSE above the level (don't chase intraday penetration) |
| **`pos_ac_trigger`** | accum_struct + accum_action + 1.2× volume + alpha_ok + rs_ok + vcp_loose + obv_rising + obv_above_ma + vol_shelf_ok + **d_rsi ≤ 50** | Confirm OBV is making higher highs alongside price for at least 5 bars |
| **`swing_pb_trg`** | mkt_bull + bullish_pullback + vcp_tight + ma_stack + rsi_pocket + vol_dry | Pullback should tag EMA20 (within 1.5%) on dry volume; entry on first green close after the tag |
| **`swing_bo_trg`** | mkt_bull + vcp_tight + breakout + 1.5× volume + anti-algo | Anti-algo gate: bar range < 2× ATR (prevents stop-hunt entries) |
| **`gap_go_trg`** | mkt_bull + gap ≥ 4% + intraday_pos ≥ 60% + 3× volume | Wait until 11:30 IST to confirm the gap holds before entering |
| **REV-CB / REV-RS / REV-EARLY** | All recovery-specific gates + RFF Score ≥ 3 | Only fires if regime gate passes (CNX500 ≥ 7% off OR stock ≥ 10% off 52W high) |

**Bull Hold Window:** A signal stays in HOLD state for 3 bars after firing (`bull_hold_days` default). You can enter on bar of fire OR within the 3-bar hold window if conditions remain valid.

**Disqualifier:** Signal fails to fire even though Steps 4–7 all passed → wait. Reasons: macro_ok or micro_ok dropped intraday, volume came in light, ADX softened. Trust the system.

---

### Step 9 — Risk Allocator v1.0 Sizing & Telegram Alert

**Module:** `Commander_Risk_Allocator_v1.0.pine` overlay (or use Unified Ecosystem's built-in Kelly sizing)
**Why ninth:** Position sizing is non-negotiable. Compute the share count BEFORE placing the order; never reverse-engineer size from "how much I want to spend."

| Field | Hard Floor / Setting | Confluence Factors |
|-------|----------------------|---------------------|
| **Risk per trade** | 0.75% of capital (Bull) / 0.50% (Recovery) | Reduce to 0.50% / 0.25% if VIX > 22 or CONTEXT SCORE in NEUTRAL |
| **Stop-loss distance (ATR-based)** | Per Bull Screener / Unified Ecosystem output (typically 1.5× ATR14) | Use the ATR stop, not arbitrary % stops; respects volatility |
| **Max allocation per trade** | ₹25,000 (or ~25% of capital, whichever is lower) | Size cap protects against single-stock blowups |
| **Position size formula** | `(Capital × Risk%) / (Entry − SL)` | Round DOWN to nearest 1 share (never up) |
| **Sector concentration** | Max 25% of capital in any one sector | Hard cap; if hitting it, skip the next candidate from that sector |
| **Max open positions** | 6 simultaneously | Beyond 6, focus dilutes; re-evaluate weakest open position before adding |
| **Telegram alert dispatch** | Auto-fire on entry trigger | Receive on phone for confirmation; do not override the alert manually |

**Disqualifier:** Computed size = 0 (e.g. SL too wide vs risk budget) → skip the trade. The risk math is telling you it's too dangerous at current volatility.

**Confluence boost:** Position size at full risk (0.75%) + sector concentration < 15% + only 2–3 open positions → optimal portfolio capacity, take the trade.

---

### One-Page Confluence Cheatsheet (Print This)

| # | Module | Single Most Important Reading | Min Floor |
|---|--------|-------------------------------|-----------|
| 1 | Macro / Breadth | CNX500 regime | NOT RED |
| 2 | Sector Dashboard | Sector Stage | 1 or 2 |
| 3 | Auto-Pilot watchlist | Conviction score | ≥ 6.0 (matcher floor) |
| 4 | Bull Screener v3.2 | `pyScore` AND `alphaScore` | both ≥ 60 |
| 5 | Dashboard v67.4.12 | Recommendation | STRONG BUY or BUY |
| 6 | Context Layers v1.2 | CONTEXT SCORE | ≥ +3 (BULL) for full size |
| 7 | Zigzag v6.2 | Trend state | HH-HL |
| 8 | Unified Ecosystem v3.4 | Active trigger fires | the trigger boolean = TRUE |
| 9 | Risk Allocator v1.0 | Position size > 0 | per 0.75% Bull / 0.50% Recovery risk |

**The Trade-Quality Scorecard (max 9, target ≥ 7 for entry):**
- Each step where the reading is at the **confluence boost** level scores +1.
- Each step where the reading is at the hard floor (just barely passing) scores +0.5.
- Each step that fails the hard floor scores 0 — and disqualifies the trade entirely.

A 9/9 trade is a textbook STRONG BUY at full size. A 7/9 trade is a normal-size entry. A 5–6 / 9 trade is half size or skip. Below 5 → next candidate.

---

## SECTION 8 — Phase 4A: Bull Track Execution

**Module:** `Weinstein_Unified_Ecosystem_v3.4.pine` — Bull Market Strategy (daily chart)

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

### Trigger Gates — What Changed in the Unified Ecosystem (v2.3 → v3.6)

> **Two trigger conditions tightened on 10 May 2026.** These are mandatory for the v2 LOCK to behave consistently between Python and Pine. Defaults match `chartink_replay.SCAN_PARAMS` and `v2_fixes.V2_PARAMS`; do not change without re-running the backtest.

| Trigger | Original (v2.2) | v2.3 (added gates **bold**) | Source |
|---|---|---|---|
| `pos_bo_trigger` | base_confirmed + alpha_ok + rs_ok + micro_ok + breakout + 1.5× volume + vol_shelf_ok | + **wRSI ≥ hunter_weekly_rsi_min (60)** + **adx_val ≥ hunter_daily_adx_min (25)** | v1 FINAL Hunter — `chartink_replay.SCAN_PARAMS["hunter"]` |
| `pos_ac_trigger` | base_confirmed + accum_struct + accum_action + 1.2× volume + alpha_ok + rs_ok + micro_ok + vcp_loose + obv_rising + obv_above_ma + vol_shelf_ok | + **d_rsi ≤ pos_accum_rsi_max (50)** | v2 LOCK — `v2_fixes.V2_PARAMS["pos_accum_rsi_threshold"]` |

**Practical impact:**
- **POS-BO** fires less often. Only when weekly RSI shows real momentum (≥60) AND daily ADX confirms a trending move (≥25). Backtest evidence: this was the v1 FINAL lock, +17% relative alpha vs the un-tuned baseline (4.45 vs 3.81 on the filtered universe).
- **POS-AC** refuses to fire at high RSI. Backtest evidence: +0.14pp alpha on raw, +0.26pp on filtered, hit-rate held both. Median anchor alpha jumped 4.68 → 5.00 on the filtered universe.

> **The new ADX is computed numerically.** v2.3 added `[_dp14, _dm14, adx_val] = ta.dmi(14, 14)` so the strategy has access to the actual ADX value (not just the directional `adx_strong` boolean used by `alpha_score`). Both are kept side by side.

---

## SECTION 9 — Phase 4B: Recovery Track Execution

**Module:** `Weinstein_Unified_Ecosystem_v3.4.pine` — Recovery Market Strategy (daily chart)

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

## SECTION 12 — Phase 5: Post-Market & Portfolio Management

### 12A — Trade Journal Autopsy
1. Open the **Journal & Autopsy** tab in Commander Web v4.0.
2. Select your closed trades and run the AI Autopsy.
3. Review the system-generated insights on entry timing, edge validation, and exit execution vs the system rules.

### 12B — Options Desk (Hedging & Yield)
1. For long-term positional holdings, open the **Options Desk** tab.
2. Generate Covered Call or Cash Secured Put strategies based on current IV and the stock's support/resistance levels.
3. The system ensures the strike selected is safely outside the 20-day ATR channel.

### 12C — Routine Housekeeping (After Entry/Exit)
**After Entry:**
1. Note the `active_catalyst` label shown on the chart (entry comment in the Unified Ecosystem) — this locks in the trail type for the trade.
2. Set TradingView alerts:
   - Alert at T1 price (partial exit reminder)
   - Alert at Initial SL price (exit reminder)
   - Alert at 90% of time-stop date
3. Run **Portfolio Sync** in Commander Web to inject the new position into the Dashboard Pine inputs.

**After Exit:**
1. Update the portfolio slot: clear the ticker or overwrite with new position.
2. Re-run **Portfolio Sync** to sync the updated state.

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

### 14A. Backtest-Locked Parameters (v1 FINAL + v2 LOCK) — DO NOT MODIFY

| Parameter | Value | Source | Used In |
|---|---|---|---|
| **`SCAN_PARAMS_VERSION`** | **`v2_FINAL_20260510`** | `chartink_replay.py` | Python pipeline canonical version stamp |
| **Hunter `weekly_rsi_min`** | **60** (was 55) | v1 FINAL backtest | `chartink_replay.py`, Bull Screener v3.2 (`hunter_weekly_rsi_min`), Unified Ecosystem v3.4 (`hunter_weekly_rsi_min`), Dashboard ULTIMATE v3.9 |
| **Hunter `daily_adx_min`** | **25** (was 20) | v1 FINAL backtest | Same as above |
| **EarlyBirds `disable_rsi`** | **`True`** (was False) | v1 FINAL backtest | `chartink_replay.py` SCAN_PARAMS |
| **`pos_accum_rsi_threshold`** (v2 LOCK) | **50** | v2 ablation (only fix that promoted on both raw + filtered universes) | `v2_fixes.V2_PARAMS`, Bull Screener v3.2 (`pos_accum_rsi_max`), Unified Ecosystem v3.4 (`pos_accum_rsi_max`), Dashboard ULTIMATE v3.9 |
| **`V2_FLAGS["pos_accum_rsi_nullout"]`** | **`True`** (default) | v2 LOCK 10 May 2026 | `v2_fixes.py` |
| **`V2_FLAGS["days_since_pivot_penalty"]`** | **`False`** (default) | v2 ablation rejected as default; retained as defensive flag | `v2_fixes.py`; Bull Screener v3.2 input `days_since_pivot_penalty_on` |
| **Matcher `min_conviction`** | **6.0** | Production matcher default | `matcher_replay.filter_by_conviction`, `brute_force_match_pro.calculate_conviction_score` |
| **Validation Top-N** | **10** | Backtest spec | `validation.run_validation`, `validation.run_chartink_validation` |
| **Validation forward window** | **30 days** | Backtest spec | Same as above |
| **Validation anchors** | **12 monthly** | Backtest spec | Same as above |
| **Benchmark** | **`^CRSLDX` (Nifty 500)** | Backtest spec | Same as above |

> **Cross-surface invariant:** Whenever `chartink_replay.SCAN_PARAMS["hunter"]["weekly_rsi_min"]` is changed, the same value must be applied to: Bull Screener v3.2 input `Hunter Weekly RSI Min`, Unified Ecosystem v3.4 input `Hunter Weekly RSI Min (POS-BO)`, and Dashboard ULTIMATE v3.9 input `Hunter Weekly RSI Min`. Same for `daily_adx_min` and `pos_accum_rsi_threshold`. Zero signal drift between Python and Pine is the DNA-level rule.

### 14B. Canonical Module Versions (May 2026)

| Module | Version | File |
|---|---|---|
| Dashboard | **v67.4.4** | `Weinstein and Swing Pro Dashboard v67.2.pine` (in-file `[v67.4.4]`) |
| Unified Ecosystem | **v3.6** | `Weinstein_Unified_Ecosystem_v3.4.pine` |
| Bull Screener (Pine) | **v3.3** (file v3.2) | `Commander_Bull_Screener_v3.2.pine` |
| Bull Screener (Python) | **v1.11** | `bull_screener.py` + `v2_fixes.py` |
| Recovery Screener (Pine) | **v2.0** | `Commander_Recovery_Screener_v2.0.pine` |
| Recovery Screener (Python) | **v1.6** | `recovery_screener.py` |
| Risk Allocator | **v1.0** | `Commander_Risk_Allocator_v1.0.pine` |
| Context Layers | **v1.2** | `Weinstein_Context_Layers_v1.2.pine` |
| Swing Zigzag Strict | **v6.2** | `Wesinstein Swing Zigzag [Strict v6.2].pine` |
| Validation Framework | **v2.8** | `validation.py v2.8` + `replay.py v2.9` + `sector_rotation.py v1.0` |
| Commander Web | **v4.0** | `weinstein_commander_web_v4.0.py` |

### 14C. General Module Parameters

| Parameter | Value | Used In |
|---|---|---|
| Weinstein SMA (weekly) | 30 | Dashboard, Unified Ecosystem, Screeners |
| 30W SMA Slope Lookback | 4 weeks | Dashboard |
| RS Slope Lookback (canonical) | **26 weeks** (slope-Mansfield) + 8w window | Dashboard owner; mirrored in Bull/Recovery Screeners and Unified Ecosystem |
| RS Slope Lookback (legacy) | 5 weeks | Bull Screener (legacy field, still computed) |
| RS Level Period | 52 weeks | Dashboard |
| RS Slope Sensitivity | 0.2 (×100 scale) | Dashboard |
| BB Squeeze Lookback | 30 bars | Bull Screener |
| OBV Compound ROC short | 5 bars | Bull Screener, Dashboard |
| OBV Compound ROC long | 10 bars | Bull Screener, Dashboard |
| OBV SMA anchor | 20 bars | Bull Screener, Dashboard |
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
| Min Alpha Score (entry) | 60 (personal floor) | Dashboard, Bull Screener |
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

4. **Running scans without a fresh Dhan token.** Portfolio Sync will silently fail if the Dhan auth token has expired. Check the `.env` file first and verify the path points to `Dashboard v67.4.12.pine`.

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

## SECTION 16 — Backtest v2 LOCK (10 May 2026)

This section documents the backtesting evidence behind the v1 FINAL + v2 LOCK parameters. Read this when you want to understand *why* the system trades the way it does, *what* was tested, and *what's still on the bench* as v3 candidates.

### 16.1 The Two Validators

The Python pipeline supports two validation paths in `validation.py`:

| Validator | Universe | Use For |
|-----------|----------|---------|
| `run_validation()` | Raw Nifty 100/500 (no filter) | Robustness check on a wide universe |
| `run_chartink_validation(use_fundamentals=True, min_conviction=6.0)` | Chartink replay → matcher conviction filter → bull screener | The **realistic deployed pipeline** — answers "how does v1 perform on the universe I actually trade?" |

**Filtered ≠ raw.** The filtered universe averages **23 candidates per anchor** vs ~100 raw. It compresses Nifty 500 down to the same ~10–33 stocks per month that the deployed Run Full Auto-Pilot produces.

### 16.2 Backtest Spec

- **12 monthly anchors:** 2025-04-15 → 2026-03-16
- **30-day forward window** for return measurement
- **Top-N = 10** picks per anchor
- **Benchmark:** `^CRSLDX` (Nifty 500)
- **Metric:** Anchor-average alpha (pick avg return − benchmark return), hit-rate (% anchors beating benchmark), per-pick win-rate, median anchor alpha

### 16.3 v1 FINAL Headline

| Metric | Filtered baseline | v1 FINAL Δ |
|--------|------------------:|------------|
| Avg anchor alpha | 4.37% | **4.45%** in original lock (Run `20260508_105114`); 4.37% reproduced this session within 0.08pp of cache-refresh noise |
| Hit rate | 83.3% (10/12 anchors) | held |
| Win rate | 59.2% | 60–62% range |
| Median anchor alpha | 4.68% | similar |

**On raw Nifty 500 (`run_validation`):** baseline alpha 2.81% (clean), 2.61% (with old hook), hit-rate 91.7%. The 1.76pp gap between raw and filtered baselines proves the filter (Chartink + Screener.in conviction) **adds real edge** — the deployed pipeline is meaningfully better than blind Top-N on raw Nifty 500.

### 16.4 v2 Ablation — Five Candidates, One Winner

| Candidate Fix | Raw α Δ | Raw Hit | Filtered α Δ | Filtered Hit | Verdict |
|---|---:|---:|---:|---:|---|
| `tiebreak_rs_momentum` | +0.13 | ↓ 83.3% | −0.14 | ↓ 75.0% | ✗ Reject — fails on both |
| `vcp_score_multiplier` (0.5×) | −0.21 | held | −0.17 | held | ✗ Reject — alpha drops on both |
| `days_since_pivot_penalty` | **+0.65** | held | **−0.42** | ↑ 91.7% | ⚠ Universe-dependent — kept as defensive runtime flag |
| `sector_cap_top_n` (3-per-sector hard) | −0.53 | ↓ 83.3% | −0.12 | held | ✗ Reject — blocks quality picks at strong-sector anchors |
| **`pos_accum_rsi_nullout`** | **+0.14** | held | **+0.26** | held | **✓ PROMOTE — only fix winning both universes** |

**Cross-universe verification rule:** A v2 fix promotes to FINAL only if it lifts alpha while holding hit-rate on **both** universes. Only `pos_accum_rsi_nullout` cleared that bar.

**The mechanism:** POS-ACCUM is meant to surface accumulation patterns at *low* RSI (institutions buying while sentiment is muted). When RSI > 50, the catalyst label becomes a false positive — the stock is already running, so the institutional accumulation signal is just confirming late-stage chase. The HCLTECH-style failure (Jan-15-26 anchor in v1: HCLTECH was the #1 ranked POS-ACCUM pick at RSI 52, returned −16.14% over 30 days, single-handedly causing the lone losing anchor) is exactly the failure mode this fix prevents.

### 16.5 The §8.1 Baseline-Drift Investigation (Resolved)

A 4.45 → 2.61 drift was observed when re-running the baseline on a different validator path. Root cause decomposed into:

1. **1.64pp apples-to-oranges:** the original v1 FINAL ran `run_chartink_validation` (filtered); the new ablation harness ran `run_validation` (raw). Different validators, different baselines — **not** a regression.
2. **0.20pp real hook side-effect:** `v2_fixes.select_top_n()` was using `kind="mergesort"` + `reset_index()` even with all flags off, vs the validation.py fallback's plain quicksort. Tiebreak winners differed at tied Scores. **Fixed** with a fast-path early-return at the top of `select_top_n` that is byte-identical to the fallback when both relevant flags are off.

Empirical confirmation: a hook-neutered baseline run (`test_baseline_no_hook.py`, Run `20260510_064122`) returned alpha 2.81 vs the hook-active 2.61 — exactly matching the 0.20pp predicted delta.

### 16.6 Forward Archive (Future-Proofing)

Currently the filtered-universe backtester falls back to **yfinance fundamentals** for historical anchors (because we don't have point-in-time Screener.in data). This introduces a minor look-ahead via today's promoter-% snapshot (~1–3pp/yr drift, acceptable for now).

Going forward, `snapshot_archive.snapshot_today()` is run after every Auto-Pilot batch to copy the day's CSV outputs to `data/snapshots/YYYY-MM-DD/`. After ~6 months of accumulated snapshots, the entire backtest can be re-run against the genuine point-in-time Screener.in data, removing the look-ahead entirely. Today's archive is at `data/snapshots/2026-05-08/` (Day 1).

### 16.7 Pine Surfaces — All Synced With Python

| Surface | Version | v1 FINAL Hunter | v2 LOCK POS-ACCUM | Python-aligned Score |
|---------|---------|-----------------|-------------------|----------------------|
| `chartink_replay.py` | `v2_FINAL_20260510` | ✓ in `SCAN_PARAMS` | ✓ via `v2_fixes` flag default | source of truth |
| `bull_screener.py` + `v2_fixes.py` | v2 LOCK | n/a | ✓ flag default `True` | source of truth |
| Bull Screener Pine | **v3.3** | ✓ POS-BO gated | POS-ACCUM catalyst DISABLED (backtest verdict — see §16) | ✓ `pyScore` mirrors Python (default ON) |
| Dashboard ULTIMATE | **v3.9** | ✓ POS-BO catId=2 gated | ✓ catId=1 gated on `_rsi ≤ pos_accum_rsi_max` | n/a |
| Unified Ecosystem | **v3.6 (in-file)** | ✓ `pos_bo_trigger` gated | ✓ `pos_ac_trigger` gated on `d_rsi ≤ 50` (POS-AC restored in v3.5/v3.6) | n/a |

Zero signal drift between Python and TradingView. The DNA rule "signal consistency is sacred" is now enforced at every surface.

### 16.8 What's On the v3 Bench

When you next run an ablation cycle, these are the candidates worth re-testing with revised thresholds:

- **`vcp_score_multiplier`** at a milder multiplier (e.g. 0.85× instead of 0.5×). 0.5× was too aggressive — α dropped on both universes.
- **`sector_cap_top_n`** as a *soft* cap (e.g. 5-per-sector with a penalty rather than a hard limit). Hard cap was too rigid at strong-sector anchors.
- **`tiebreak_rs_momentum`** is structurally rejected — the Jan-15-26 single-anchor counterfactual was misleading; recovery on one anchor came at the cost of breakage elsewhere.
- **`days_since_pivot_penalty`** at a higher threshold (e.g. > 45 instead of > 30). Backtest evidence: it works on raw but truncates upside on filtered. A higher threshold might preserve the upside while still penalising true late-cycle chases.

For full evidence and decision tables, see `BACKTEST_RESULTS_v2.docx` (root) and `BACKTEST_RESULTS_v2_SESSION.md` (the markdown source).

---

## SECTION 17 — v6.0 Architectural Additions (Quick Reference)

### Cross-Tool Field Ownership Map

| Domain | Canonical Owner | Mirrored In | Removed From Display In |
|---|---|---|---|
| Mansfield RS engine (52w level + 26w slope + 8w window + 4-bar momentum + 130-bar warm-up + JdK RS-Ratio) | **Dashboard v67.4.12** | Bull Screener v3.2, Recovery Screener v2.0, Unified Ecosystem v3.4 | All three mirrors (Bull dropped 3 rows, Recovery 2, Unified 1) |
| Strict trend (HH/HL/LH/LL/EH/EL) | **Zigzag v6.2** | Dashboard via `f_getStrictTrend` | — |
| POS-BO 9-gate detail | **Bull Screener v3.2** | Unified Ecosystem references via diag panel | — |
| 4-pillar Capitulation Bottom + RFF + 60-bar DD + RSI(3) FEAR | **Recovery Screener v2.0** | Unified Ecosystem references via diag panel | Dashboard (removed Recovery section in v67.0) |
| ML probability score + WCL Gate + first-failing-gate diag | **Unified Ecosystem v3.4** | — | — |
| Wyckoff + Volume Profile + SMC + Setup Detector | **Context Layers v1.2** | — | Legacy `Weinstein_Wyckoff_Phases`, `_Volume_Profile`, `_SMC_Zones` standalone modules (deprecated; remove from layouts) |

### Unified Ecosystem v3.4 — New Catalysts and Filters

**Wyckoff catalysts (added in v3.4):**
- **WYC-SPRING** — Spring / Shakeout pattern (Phase C accumulation)
- **WYC-SOS** — Sign of Strength (Phase D advancing)
- **WYC-JAC** — Jump Across the Creek (early Phase D)
- **WYC-SPRING+SOS** — Combined high-conviction sequence

All Wyckoff catalysts use a 120-day forward window in validation (multi-month bases).

**ML Probability Score:**
- Logistic regression on structural features (Stage, RS, OBV, Volume, ATR, RSI, breakout magnitude, fundamentals)
- Displayed as `[ML: XX%]` next to each catalyst
- Backtest evidence: ML ≥ 60% picks outperform ML < 40% picks by meaningful alpha on 18-month n500 sample

**RSI Dead-Zone Filter:**
- RSI 47–54 is a documented "edge vanishes" zone — no directional bias, high false-positive rate
- Filter applied to bull catalysts (POS-BO, POS-AC, SWG-*); skips entries when daily RSI is in this band
- Can be disabled per-chart via input

**Catalyst-Aware Trails (v3.4 widened, v3.5/v3.6 fallback ATR multipliers):**
- POS-BO: Chandelier 4.5× ATR (was 3.0×) — wider trails let breakouts breathe through normal volatility
- SWG-PB / SWG-BO / GAP-GO: SMA50 trail (was EMA20) — same logic, longer leash
- Fallback ATR multipliers: POS=4×, WYC=3.5×, REV=2.5×, SWG=1.5×

**Swing Targets Realigned (v3.4):**
- T1 = 3R (was 5R), T2 = 5R (was 10R)
- Partial = 33% at T1 (was 50%)
- Better reflects observed 1–4 week swing holds vs the 6–8 week assumption baked into the original 5R/10R

**CATALYST DIAG panel (v2.8+):**
- 4-column stacked layout below main strategy panel
- Each catalyst row shows the **first failing gate** — collapses "stare at 30 rows" into "read one cell"
- "See Other Tools" footer points to canonical owners

### Validation Framework v2.8 — Catalyst-Aware Backtesting

**Catalyst-aware forward windows** replace the old single 30-day window:

| Catalyst | Forward Window | Rationale |
|---|---|---|
| POS-BO | 120 days (~6mo) | Positional breakout |
| POS-ACCUM | 180 days (~9mo) | Stage 1→2 accumulation |
| WYC-SPRING / WYC-SOS / WYC-JAC | 120 days | Multi-month bases |
| REV-CB / REV-RS / REV-EARLY | 90 days | Mean-reversion / recovery |
| SWG-BO / SWG-PB / SWG-GAP / SWG-REV | 30 days | Original swing window |

**Bootstrap CI on alpha:** 10,000 iterations. Statistical bounds replace point-estimate alphas.

**Realistic SL/T1/T2 simulation:** bar-by-bar replay with commission. Per-trade matched-horizon alpha vs Nifty 500.

**Run command:**
```bash
python -u validation.py --months 18 --universe nifty500 --catalyst_windows --bootstrap_n 10000
```

Output written to `validation_runs/validation_<run_id>_summary.csv` + `_details.csv` + `_meta.json`.

**Opt-in risk overlays** (`--sector_cap`, `--kill_switch_*`, `--sector_rotation`) are instrumented but NOT recommended as defaults — May 2026 testing showed they reduce alpha when applied to the current Bull screener. They remain available for future ablation studies.

### Dashboard v67.4.12 — Decision-Mode at a Glance

The default view collapses 60+ raw rows into **13–18 composite rows** organised by decision-rank:

```
🎯 ACT NOW          Recommendation · Action Signal · Catalyst+Gates · Asset Quality
📊 STRUCTURE        Weekly Structure · Daily Structure · Price Action · Momentum · Levels/Room
🌐 CONTEXT          Macro/Sector · RS (Mansfield) · Style/Persona
📦 PORTFOLIO        Portfolio Health · My Trade (active) · Position Status (active)
⚡ ALPHA SCREENER  Top-5 watchlist
```

Toggle `Show Detailed View = ON` to expand to ~60 raw rows for debugging / tuning.

**664-symbol physical sector database** ported to Pine (`<DB_LOOKUP_START>` block) — zero string-matching hacks, 100% offline parity with the Python ecosystem.

**JdK RRG model** matched to Strike.Money. LEADING quadrant scores `+2`; other quadrants no longer score (was: graded 0 to +2 across quadrants).

### Zigzag v6.2 — Longs-Only Command Center

11-row panel with developing-pivot awareness across every field. Default mode is **Longs-Only**.

| Row | Use |
|---|---|
| TIMEFRAME | Current chart resolution label |
| TREND | 🟢 / 🔴 / 🟡 — flips live on projected BoS/CHoCH |
| MTF TREND | Auto-resolves intraday→D, D→W, W→M, M→12M. Confluence check. |
| STRUCTURE | High class / Low class — e.g. `HH / HL` |
| SWING COUNT | Consecutive pivots in current trend. ≥3 = extended (yellow) |
| SWING RANGE | % of developing swing. Gray < majorThresh / Green 1–2× / Yellow > 2× |
| CHOPPINESS | Flips / 26W or 52W. Green ≤4 / Yellow 5–8 / Red >8 |
| **INVALIDATION** | Latest swing low — structural stop |
| **BOS LEVEL** | Latest swing high — bullish BoS entry trigger |
| VOL CONFIRM | ✅ ≥ 1.5× / ❌ < 1.5× on last ↑ BoS bar (Weinstein vol gate) |
| BAR AGE | Bars since active pivot — swing maturity |

**On-chart drawings:** dotted red invalidation line, dotted green BoS level line, fib retracements (50% / 61.8%) and extensions (1.272 / 1.618), pivot zigzag, projection line.

### Context Layers v1.2 — Setup-Aware Score

```
BASE SCORE  = Wyckoff (−4..+4) + VP (−3..+3) + SMC (−3..+3) + OB Prox (−2..+2)   ← range −12 to +12
SETUP BONUS = S2/S3 +2 · S1 +1 · S4/S5/S6 0 · S8 −1 · S7 −2
FINAL SCORE = BASE + BONUS                                                          ← range −14 to +14
```

| FINAL | Band | Action |
|---|---|---|
| ≥ 9 | STRONG BULL | Full size (1.25× Kelly) |
| 4 to 8 | BULL | Normal size |
| −3 to +3 | NEUTRAL | Half size, selective |
| −4 to −6 | CAUTION | No new longs |
| ≤ −7 | BEAR | Flat / exit |

**Trading rule:** SETUP BONUS must be ≥ 0 for entry. Negative bonus = S7 (Distribution) or S8 (Choppy) = sit out signal, even if FINAL SCORE is still BULL band.

---

*Weinstein–Minervini Commander Trading Bible v6.0 — 22 May 2026*

*Built on the Weinstein Commander Suite with cross-tool architecture (Dashboard owns RS, Zigzag owns trend, Bull Screener owns POS-BO gates, Recovery Screener owns CB pillars, Unified Ecosystem owns catalyst diag + ML, Context Layers owns institutional context). For field-by-field input reference, consult the module guides:*

- *`docs/00_INDEX.md` — master index (canonical version list)*
- *`docs/01_Swing_Zigzag_Strict_v6_Guide.md` — Zigzag v6.2 (longs-only, MTF, vol confirm, fib extensions, all developing-pivot aware)*
- *`docs/02`–`04` — Legacy context modules (superseded by Context Layers v1.2 — remove from layouts)*
- *`docs/05`–`06` — DEPRECATED strategy guides (Minervini + Recovery — superseded by Unified Ecosystem v3.4)*
- *`docs/07_Commander_Web_v4_Guide.md` — Commander Web v4.0 (with Run Full Auto-Pilot pipeline)*
- *`docs/08_Dashboard_v67_Guide.md` — Dashboard v67.4.12 (Decision-Mode + 664-symbol DB + JdK RRG)*
- *`docs/09_Recovery_Screener_v2_0_Guide.md` — Recovery Screener v2.0 (Wyckoff Phases B/C/D + 10 paired gates)*
- *`docs/10_Risk_Allocator_v1_Guide.md` — Risk Allocator v1.0*
- *`docs/11_Bull_Screener_v3_2_Guide.md` — Bull Screener v3.2 (POS-ACCUM disabled, composite-merged, RS engine mirrored)*
- *`docs/13_Unified_Ecosystem_User_Guide.md` — Unified Ecosystem v3.4 (user guide)*
- *`docs/14_Unified_Ecosystem_Trading_Guide.md` — Unified Ecosystem v3.4 (trading guide)*
- *`docs/15_Context_Layers_v1.2_Guide.md` — Context Layers v1.2 (Setup Bonus + Final Score)*
- *`docs/16_Validation_Framework_Guide.md` — Validation Framework v2.8 (catalyst-aware windows + bootstrap CI)*
- *`BACKTEST_RESULTS_v2.docx` (root) — Backtest v2 LOCK institutional report*
