# Weinstein Unified Ecosystem [v3.4] — User Guide

**Script:** `Weinstein_Unified_Ecosystem_v3.4.pine`
**Type:** Strategy (Overlay)
**Market:** NSE/BSE — Nifty 500 Universe
**Timeframe:** Daily (primary)

---

## What's New in v3.4 — ML Integration, Wyckoff & DB Sync

v3.4 represents a major evolution of the Unified Ecosystem, introducing machine learning probability scoring, physical database syncing, and Wyckoff accumulation logic.

### 1. Machine Learning Integration
- **Logistic Regression Probability Model:** The ecosystem now integrates an ML probability score (`[ML: XX%]`) that assesses the likelihood of a setup succeeding based on structural features.
- **RSI Dead Zone Filter:** Backtesting identified RSI 47-54 as a critical "dead zone" where edge vanishes. The ecosystem now applies this ML-derived gate to filter out low-probability setups.

### 2. Physical Sector Database Porting
- **664-Symbol Hardcoded Database:** The ecosystem now contains a physically ported SQLite mapping block (`<DB_LOOKUP_START>`), moving away from string-matching hacks. This guarantees 100% offline consistency between the Python screeners and Pine indicators for all 664 NSE stocks tracked in `sectors.db`.

### 3. Wyckoff Phases & Adjusted Targets
- **Wyckoff Catalysts:** The ecosystem now natively detects Wyckoff Accumulation phases (Spring, SOS, JAC) alongside the traditional Weinstein & Minervini setups.
- **Target Realignment:** Swing trades now target 3R/5R (was 5R/10R) with a 33% partial take-profit, better reflecting the 1-4 week hold times. Positional targets remain 5R/10R.
- **Widened Trails:** Swing trades now use a wider SMA50 trail (was EMA20), and POS-BO uses a 4.5x ATR Chandelier (was 3.0x), to prevent premature exits and let winners run.

---

## What's New in v2.6 → v3.4 — Decision-Mode Architecture

The v2.6+ line aligns this Strategy with the Dashboard's `v67.3.x` cross-tool architecture.

**Architectural principle:** Each tool in the ecosystem owns exactly one domain. This Strategy is the **cross-engine verdict aggregator**. The Dashboard owns the Mansfield RS engine (mirrored here). The Bull Screener owns POS-BO setup detail (referenced here). The Recovery Screener owns capitulation pillars (referenced here).

### v2.6 — RS engine ported from Dashboard

`f_rs_math()` rewritten as a verbatim mirror of the Dashboard's canonical engine:
- **Dual-SMA**: 26w for slope-Mansfield, 52w for level-Mansfield (was 26w only — non-canonical).
- **Slope formula**: Δ Mansfield (was Δ price ratio — non-standard).
- **130-bar warm-up gate** suppresses junk RS during early history.
- Returns `[mansfield_level, slope, rs_momentum]` — same tuple signature as before; only internal math changed. See Dashboard guide §16.

**Removed display rows** (Dashboard owns them — read them there):
- `Weinstein Stage (W)` → Dashboard "Market Structure" + "Stage 2 Age"
- `Alpha Score` → Dashboard "Asset Quality"
- `Stage 2 Freshness` → Dashboard "Stage 2 Age" (richer: leg + macro + tag)
- `Trend Coiling (MA)` → Bull Screener G8 "MA Squeeze"
- `Volatility Squeeze` → Bull Screener G9 "BB Squeeze"
- `52W Correction (%)` → Recovery Screener "CORRECTION"
- `CB Pillars` → Recovery Screener 4-pillar panel
- `Active Recovery Edge` → Recovery Screener "SIGNAL"
- `Recovery Score` → Recovery Screener "SCORE / GRADE"

### v2.7 — Composite-merge pass

Rows compressed via Dashboard-style composite cells:
- **BULL SETUP** row merges Base Confirmed + Py Score (was 2 rows)
- **REC STATE** row merges Recovery Regime + RFF Filter (was 2 rows)
- **Footer** merges 3 cross-ref rows into 1

### v2.8 / v2.8.1 / v2.8.2 / v3.4 — 4-column stacked layout

The CATALYST DIAG panel was rendering on the right side (cols 2-3) parallel to the main strategy panel (cols 0-1), leaving the right side ending earlier than the left. Now:
- **Diag panel stacks BELOW the main strategy panel**, using all 4 columns evenly.
- 9 catalysts paired 2-per-row (BULL: 3 paired rows; RECOVERY: 1 paired + 1 solo).
- META section (Sector Ticker + WCL Gate paired; Base Confirm Path solo).
- **"See Other Tools:" footer** is now the absolute last row of the panel (label in col 0, description merged across cols 1-3).

---

## Inherited from v2.3 (still active)

> **Hunter / POS-ACCUM gates (locked 10 May 2026):**
>
> - **Hunter Weekly RSI Min** = `60` — POS-BO requires `wRSI >= 60`.
> - **Hunter Daily ADX Min** = `25` — POS-BO requires `ADX >= 25`.
> - **POS-ACCUM Daily RSI Max** = `50` — POS-ACCUM suppressed when daily RSI > 50.
>
> All three thresholds are exposed as `input.int` and can be tuned per chart, but defaults match the locked Python pipeline. Do not change without re-running the backtest.

---

## 1. Overview

The **Weinstein Unified Ecosystem** is a single, fully integrated strategy script that merges two previously separate indicators:

| Legacy Script | What it brought |
|---|---|
| `Weinstein_Minervini_Strategy v4.53` | Bull market positional & swing edges, Alpha Score, VCP detection, RS scoring, exit engine with T1/T2 partials |
| `Weinstein_Recovery_Strategy v1.4` | Bear/correction market edges (Climax Bottom, RS Survivor, Early Bird), RFF Fundamental Filter, regime gating |

By running a single script you get:
- **One dashboard** showing both Bull and Recovery strategy states simultaneously
- **One exit engine** managing all trade types with the correct trail logic per catalyst
- **One set of position sizing rules** applied consistently across all 9 edges
- **No duplication** of weekly data calls, sector lookups, or market health checks

---

## 2. Installation & First-Time Setup

### Step 1 — Add to Chart
1. Open TradingView, navigate to a **Daily chart** of any Nifty 500 stock.
2. Open the **Pine Script Editor** (bottom panel).
3. Paste the full script and click **Add to chart**.
4. The strategy will compile and load. You will see the dashboard panel (bottom-right by default) and signal shapes appear.

### Step 2 — Set Capital Parameters
Go to **Settings → Shared: Portfolio & Risk**:

| Parameter | Default | Set to |
|---|---|---|
| Total Capital (INR) | ₹1,00,000 | Your actual portfolio capital |
| Risk per Trade % — Bull | 0.75% | 0.5%–1.0% recommended |
| Risk per Trade % — Recovery | 0.50% | Keep 0.25% lower than Bull |
| Max Allocation per Trade | ₹25,000 | ~20–25% of capital per slot |
| Max Open Positions | 6 | Match your portfolio band count |

### Step 3 — Configure Backtest Period
Go to **Settings → Backtest Period**:
- **Filter Date Range?** → Enable and set Start/End dates to scope your backtest
- Leave disabled for live analysis (full history)

### Step 4 — Sector Detection
Go to **Settings → Shared: Indicators & General**:
- **Auto-Detect Sector?** → Leave **ON** for Nifty 500 stocks (uses 500-stock DB lookup + keyword fallback)
- If the sector shown in the dashboard is wrong, turn this **OFF** and manually select the correct sector ETF in **Manual Sector Override**

---

## 3. Input Groups — Complete Reference

### 3.1 Master Toggles

| Input | Default | Description |
|---|---|---|
| Enable Bull Market Strategy? | ✓ | Activates all 6 Bull edges (POS-BO, POS-AC, SWG-PB, SWG-BO, SWG-REV, GAP-GO) |
| Enable Recovery Market Strategy? | ✓ | Activates all 3 Recovery edges (REV-CB, REV-RS, REV-EARLY) |

> **Tip:** Disable Recovery in a strong bull market to reduce noise. Disable Bull in a confirmed Stage 4 bear to focus on recovery setups only.

---

### 3.2 Bull: Positional

| Input | Default | Description |
|---|---|---|
| [EDGE] Positional Breakout | ✓ | POS-BO edge — Stage 2 breakout above N-bar high |
| [EDGE] Positional Accumulation | ✓ | POS-AC edge — OBV-confirmed base building inside Stage 2 |
| Breakout Confirmation | Daily Close | `Daily Close` = signal only if price closes above level. `Intraday Penetration` = stop order fires as soon as price touches the level |
| Breakout Lookback (Bars) | 20 | How many bars back to define the resistance level for POS-BO |
| Positional Time Stop (Weeks) | 6 | Max hold time for positional trades if gain < 0.5R |

---

### 3.3 Bull: Hybrid Swing

| Input | Default | Description |
|---|---|---|
| [EDGE] Swing Pullback | ✓ | SWG-PB — EMA20 bounce in uptrend with tight base |
| [EDGE] Swing Breakout (VCP) | ✓ | SWG-BO — VCP tight-base breakout on volume |
| [EDGE] Swing Reversion | ✓ | SWG-REV — Oversold bounce off SMA200 support |
| [EDGE] Gap & Go | ✓ | GAP-GO — Institutional gap-up held into close |
| Swing Time Stop (Days) | 10 | Max hold for swing trades if gain < 0.5R |
| Dynamic T1 RR (Market Aware) | ✓ | T1 target adjusts: bull market = 2.5R, bear = 2.0R |
| Fixed T1 R-Multiple | 2.0 | Used only when Dynamic T1 is OFF |

---

### 3.4 Bull: Filters & Edge Gates

| Input | Default | Description |
|---|---|---|
| Require Macro Edge (Trend+Vol) | ✓ | Alpha score penalises below-average volume setups |
| Require Micro Edge (CPR/VWAP) | ✓ | Price must be above Daily CPR pivot AND Monthly VWAP |
| Min Alpha Score | 50 | Minimum composite quality score (0–100) to allow entry |
| Bull Signal Hold Window (bars) | 3 | How many bars a fired signal stays in "HOLD" state on the dashboard |
| Require Positive RS? | ✓ | RS Quadrant must be LEADING or IMPROVING for bull entries |
| Detect SMC Liquidity Sweeps? | ✓ | Reserved for future SMC overlay logic |

---

### 3.5 Recovery: Edges

| Input | Default | Description |
|---|---|---|
| [EDGE] REV-CB: Climax Bottom | ✓ | Detects panic washout + institutional reversal candle |
| [EDGE] REV-RS: RS Survivor | ✓ | RS-positive stock breaking out during market correction |
| [EDGE] REV-EARLY: Early Bird | ✓ | Trendline reclaim + compressed base before mainstream recovery |

---

### 3.6 Recovery: Regime Gate

| Input | Default | Description |
|---|---|---|
| Require Recovery Market Regime? | ✓ | All recovery edges require the market or stock to be in a correction regime |
| Min Correction from 52W High (%) | 10% | Stock must be at least 10% off its 52-week high |
| Max Correction from 52W High (%) | 40% | Stocks down >40% are typically structural failures, not recoveries |

---

### 3.7 Recovery: Climax Bottom Config

| Input | Default | Description |
|---|---|---|
| Min Climax Volume Mult | 2.0× | Bar volume must be ≥2× the 50-bar average to qualify as a climax |
| Climax Detection Window | 10 bars | A climax must have occurred within the last 10 bars |
| Drawdown Lookback (Bars) | 60 | Lookback period to measure the drawdown from peak |
| Min Drawdown From Lookback High (%) | 15% | Minimum percentage drop from the lookback high |
| Washout Red-Bar Window | 7 bars | Window to count consecutive red bars |
| Min Red Bars in Washout | 5 | Minimum red bars within the washout window |
| Climax Range Lookback | 20 bars | Lookback to find the widest bar range (climax bar identification) |

---

### 3.8 Recovery: Early Bird Config

| Input | Default | Description |
|---|---|---|
| RS Breakout Lookback | 20 bars | Lookback for the prior resistance level for REV-RS breakout |
| Higher-Low Recent Window | 5 bars | Recent swing low window for higher-low check |
| Higher-Low Prior Window | 10 bars | Prior swing low window for higher-low comparison |
| RS-Line Slope Window (Weeks) | 4 weeks | Window to measure whether the RS line is rising |
| Trendline: Skip Recent Bars | 10 bars | Bars to skip from right when drawing the reference trendline |
| Trendline: Swing-High Window | 10 bars | Window to find the swing high for the trendline pivot |
| NR7 Length | 7 bars | Lookback for NR7 compression detection |
| Inside-Bar Lookback | 10 bars | Window to count inside bars for compression confirmation |
| Min Inside Bars | 3 | Minimum inside bars within the lookback to confirm base compression |

---

### 3.9 Recovery: Fundamental Filter (RFF)

| Input | Default | Description |
|---|---|---|
| Minimum RFF Score (0=Off, 6=Max) | 3 | Minimum number of fundamental checkpoints the stock must pass |

**RFF Checks (max score = 6):**
1. Net Income > 0 (profitable)
2. Free Cash Flow > 0 (OCF − CAPEX)
3. Interest Coverage Ratio > 3.5× (EBITDA / Interest)
4. Debt/Equity < 2.0
5. Current Ratio > 1.0 (CA / CL)
6. Return on Assets > 5% (Net Income / Total Assets)

> Set to `0` to disable the filter. Score of `3` means at least 3 of 6 checks must pass.

---

### 3.10 Shared: Indicators & General

| Input | Default | Description |
|---|---|---|
| Auto-Detect Sector? | ✓ | Full Nifty 500 DB lookup + keyword fallback |
| Manual Sector Override | NSE:CNXIT | Used when Auto-Detect is OFF |
| EMA Length | 20 | EMA period for swing trail and T1 reference |
| ATR Length | 14 | ATR period for all SL and risk calculations |
| SL Padding % | 0.2% | Buffer below structural lows for swing SLs |
| EMA Trail Buffer % | 1.0% | Buffer below EMA20 for trailing stop |
| Chandelier Exit Length | 22 | CE lookback for positional and recovery trail |
| Chandelier Exit ATR Mult (Bull) | 3.0 | ATR multiplier; auto +0.5 in bear regime |
| Use Fixed SL %? | ✗ | Override structural SLs with a fixed % |
| Fixed SL % | 10% | Active only when Fixed SL is enabled |
| Enable Trailing SL? | ✓ | Enables all ratchet trailing logic |
| Show Strategy Signals? | ✓ | Entry signal shapes on chart |
| Show Moving Averages? | ✓ | EMA20, SMA50, SMA150, SMA200 |
| Fast Backtest Mode | ✗ | Reduces overhead (may skip checks) |
| Pivot Right Bars | 2 | Right-side confirmation bars for daily pivots |

---

### 3.11 Unified Panel Table

| Input | Default | Description |
|---|---|---|
| Show Unified Panel Table? | ✓ | Toggles the entire dashboard |
| Table Position | Bottom Right | 9 position options available |
| Show Bull Metrics? | ✓ | Shows Bull Strategy section |
| Show Recovery Metrics? | ✓ | Shows Recovery Strategy section |

---

## 4. Visual Elements on the Chart

### 4.1 Stage Background Colors
| Color | Stage | Meaning |
|---|---|---|
| Faint Green | Stage 2 | Advancing — primary zone for bull entries |
| Faint Yellow | Stage 1 | Basing — watch for breakout |
| Faint Orange | Stage 3 | Topping — tighten stops, no new entries |
| Faint Red | Stage 4 | Declining — immediate exit for POS trades |

### 4.2 Moving Averages
| Line | Color | Use |
|---|---|---|
| EMA 20 | Yellow | Swing trail, T1 for REV-CB |
| SMA 50 | Red | Positional trail floor, 50MA-Fail exit |
| SMA 150 | Blue | Minervini MA stack check |
| SMA 200 | White | Long-term trend, T2 for REV-CB |

### 4.3 Entry Signal Shapes
| Shape Text | Color | Edge |
|---|---|---|
| `BO` | Lime | POS-BO |
| `AC` | Teal | POS-AC |
| `PB` | Yellow | SWG-PB |
| `S-BO` | Orange | SWG-BO |
| `REV` | Fuchsia | SWG-REV |
| `GAP` | Aqua | GAP-GO |
| `CB` | Red | REV-CB |
| `RS` | Purple | REV-RS |
| `EAR` | Blue | REV-EARLY |
| `PRE-S2` | Yellow circle (above bar) | Early Stage 2 warning |

### 4.4 Exit / Trail Lines
| Plot | Color | Description |
|---|---|---|
| CE Trailing Stop | Fuchsia step-line | Always visible when in position |
| Active Stop Loss | Red line-break | Live ratchet SL for open position only |

---

## 5. The Unified Dashboard Panel

### Bull Market Strategy Section
| Row | Signal Colors |
|---|---|
| Market Health | Green=BULL, Red=BEAR, Amber=CORRECTION |
| Weinstein Stage (W) | Green=Stage2, Amber=Stage1, Red=Stage4 |
| RS Quadrant | Green=LEADING/IMPROVING, Red=LAGGING |
| Sector Stage | Green=Stage1or2, White=Other |
| Base Confirmed | Green=YES, White=NO |
| Alpha Score | Green=Pass, Amber=Near, Red=Fail |
| VCP / Tight Base | Green=TIGHT, White=LOOSE |
| BB Squeeze | Green=SQUEEZE, White=OPEN |
| CPR / MVWAP | Green=ABOVE, White=BELOW |
| Positional Signals | 🟢Fire / 🟡Hold / ⚫Wait per edge |
| Swing Signals | 🟢Fire / 🟡Hold / ⚫Wait per edge |

### Recovery Strategy Section
| Row | Notes |
|---|---|
| Recovery Regime Gate | RECLAIM / CORRECTION / OPEN |
| 52W Correction (%) | Must be 10%–40% for recovery edges |
| CB Pillars | P1–P4 checklist (N/4) |
| Active Recovery Edge | Currently triggering edge name |
| Recovery Score | N/4 composite score |
| Recovery Signals | 🟢Fire / 🟡Hold / ⚫Wait per edge |
| RFF Fundamental Filter | N/6 + pass/warn/fail |

**CB Pillars:**
- **P1** — Stock stretched ≥15% from 60-bar high
- **P2** — Oversold: ≥5 red bars in 7-bar window, price in bottom 25% of 10-bar range
- **P3** — Climax bar: volume ≥2× average on widest-range down day
- **P4** — Turn bar: bullish close above prior high, close in top 40% of bar

---

## 6. Common Operational Workflows

### Morning Scan (Daily Routine)
1. Load the Ecosystem on each watchlist stock (Daily chart)
2. Check **Market Health** — BEAR means recovery signals only
3. Check **Weinstein Stage** — must be Stage 2 for bull entries
4. Check signal rows for 🟢 (firing today) or 🟡 (hold window)

### Backtest a Period
1. Settings → Backtest Period → Enable Filter Date Range
2. Set Start/End dates
3. Open Strategy Tester for P&L, trades, equity curve

### Conservative Profile
- Min Alpha Score → 60–70
- Require Positive RS → ON
- Risk per Trade % → 0.5%
- Min Correction % → 15%

### Aggressive Profile
- Min Alpha Score → 40
- Breakout Confirmation → Intraday Penetration
- Risk per Trade % → 1.0%–1.25%
- Min RFF Score → 0

---

## 7. Known Limitations

| Limitation | Detail |
|---|---|
| Single position | One long position managed per chart |
| Daily timeframe | Weekly stage logic unreliable below daily |
| RFF data gaps | Some NSE small caps lack financials on TradingView |
| Sector fallback | Conglomerates fall back to CNX500 |
| Pyramiding set to 6 | Script logic enforces one entry at position_size == 0 |


# Weinstein Unified Ecosystem [v3.4] — Trading Guide

**Script:** `Weinstein_Unified_Ecosystem_v3.4.pine`
**Companion to:** `13_Unified_Ecosystem_User_Guide.md`

---

## What's New in v2.6 → v3.4 — Decision-Mode Architecture

The v2.6+ line aligns this Strategy with the Dashboard's `v67.3.x` cross-tool architecture. **Trading workflow is unchanged** — the same 9 catalysts, same 4-pillar capitulation logic, same RFF fundamental gate. What changed is the on-chart panel: less duplicated info, denser composite cells, cross-references to the canonical tools.

### Practical impact on the trader

1. **Open the Dashboard alongside.** This Strategy no longer duplicates Stage / RS / Trend / PA / Vol — read them on the Dashboard. The Strategy's panel now focuses on what only it can tell you: which catalysts are firing, what's blocking them, and the cross-engine verdict.
2. **Use the right tool for the right question:**
   - "Should I be looking at this stock?" → **Dashboard** (Action Signal · Recommendation · Stage 2 Age)
   - "Why isn't a bull catalyst firing?" → **Bull Screener** (9 POS-BO gates with first-blocking-gate detail)
   - "Is this a capitulation setup?" → **Recovery Screener** (4 CB pillars + RSI(3) FEAR + 60-bar DD)
   - "Cross-engine consensus?" → **Unified Ecosystem** (this Strategy — catalyst diagnostic panel below the main panel)
3. **Catalyst-firing logic is unchanged.** Backtest results from v2.3+ remain valid. The architectural refactor is display-only.

### What the new panel shows

After v3.4 the on-chart panel renders ~14 rows in two zones, plus a stacked 4-column CATALYST DIAG section below:

```
🌿 BULL MARKET STRATEGY                   (header)
BULL SETUP             | ✓ BASE · Py 60/100
Positional Signals     | POS-BO ●  POS-AC ●            ← 🟢 FIRE / 🟡 HOLD / 🔵 ACTIVE / ⚫ WAIT
Swing Signals          | SWG-PB ●  SWG-BO ●  SWG-REV ●  GAP ●

🔄 RECOVERY MARKET STRATEGY               (header)
REC STATE              | Regime: OFF · RFF: 3/6✓
Recovery Signals       | REV-CB ●  REV-RS ●  REV-EAR ●

◈ CATALYST DIAG  (catalyst · ✓ FIRE / ✗ first-blocking-gate [hits])   (full-width)
── 🌿 BULL ──
POS-BO    | ✗ mkt_bull [0]      | POS-ACCUM   | ✗ mkt_bull [0]
SWG-PB    | ✗ mkt_bull [4]      | SWG-BO      | ✗ mkt_bull [0]
SWG-REV   | ✗ rev struct [0]    | SWG-GAP     | ✗ mkt_bull [0]
── 🔄 RECOVERY ──
REV-CB    | ✗ no climax [0]     | REV-RS      | ✗ RS slope ≤0 [0]
REV-EARLY | ✗ no HL+trend up [0]|             |
── 🛈 META ──
Sector Ticker     | NSE:CNX500 [AUTO] (S4) | WCL Gate | OFF
Base Confirm Path | WEINSTEIN (WStg:11w)   |          |

→ See Other Tools:  Dashboard (RS/Stage/PA)  ·  Bull Screener (Gates/Levels)  ·  Recovery Screener (Pillars/RFF)
```

### Why the diag panel is the headline value

Every catalyst row shows **the first failing gate** — the specific reason a setup isn't firing. This collapses what used to be "stare at 30 rows and figure out which constraint is binding" into "read one cell." When a stock looks promising on the Dashboard but the Strategy isn't firing, the diag panel tells you instantly which gate to fix (or accept).

---

## Inherited from v2.3 (still active — backtest-locked thresholds)

> **Hunter / POS-ACCUM trigger gates (locked 10 May 2026):**
>
> | Trigger | Added gate (v2.3) |
> |---|---|
> | `pos_bo_trigger` | + **wRSI ≥ 60** + **adx_val ≥ 25** |
> | `pos_ac_trigger` | + **d_rsi ≤ 50** |
>
> Practical impact:
> - **POS-BO** fires only when weekly RSI shows real momentum (≥60) AND daily ADX confirms a trending move (≥25). This is the v1 FINAL Hunter scan ported into the strategy.
> - **POS-AC** refuses to fire on stocks with already-elevated daily RSI (>50). Reason: late-stage POS-ACCUM at high RSI is a documented chase trap (HCLTECH-style failure, see `BACKTEST_RESULTS_v2.docx` §6).
> - All three thresholds are exposed as `input.int` and can be tuned per chart, but defaults match the locked Python pipeline. **Do not change without re-running the backtest.**

---

## 1. Ecosystem Architecture — The 9 Edges

The script routes each trade into one of 9 named **edges** (catalysts). Each edge has its own entry logic, stop-loss type, trail method, and profit-taking rules.

```
BULL MARKET STRATEGY (6 Edges)
├── POSITIONAL GROUP
│   ├── POS-BO   — Positional Breakout (Stage 2 momentum breakout)
│   └── POS-AC   — Positional Accumulation (OBV-gated base entry)
└── SWING GROUP
    ├── SWG-PB   — Swing Pullback (EMA20 bounce, VCP-tight)
    ├── SWG-BO   — Swing Breakout (VCP pattern breakout)
    ├── SWG-REV  — Swing Reversion (SMA200 mean-reversion)
    └── GAP-GO   — Gap & Go (institutional gap held into close)

RECOVERY MARKET STRATEGY (3 Edges)
├── REV-CB    — Climax Bottom (panic washout reversal)
├── REV-RS    — RS Survivor (corrected market, RS-positive breakout)
└── REV-EARLY — Early Bird (trendline reclaim + compressed base)
```

---

## 2. Prerequisites — Market Conditions Required Per Edge

Before any edge fires, a **hierarchy of filters** must pass from top to bottom.

### 2.1 Universal Pre-Checks (All Edges)
| Check | Requirement |
|---|---|
| Date Filter | Bar must be within the configured backtest window (if enabled) |
| Max Open Positions | `strategy.opentrades < max_open_positions` |
| No Existing Position | `strategy.position_size == 0` |
| Fundamental Filter (RFF) | Score ≥ min_rff_score (recovery edges only; bull edges bypass) |

### 2.2 Bull Strategy Prerequisites
| Check | Requirement |
|---|---|
| Market Health | CNX500 close > SMA200 AND SMA50 > SMA200 |
| Weinstein Stage (Weekly) | Stage 2 (or Early Stage 2 for POS edges) |
| Base Confirmed | Stage 2 + Market Bull + MPA Pass (close > SMA150 > SMA200) |
| Alpha Score | ≥ Min Alpha Score (default 50) |
| RS Quadrant | LEADING or IMPROVING (if Require Positive RS is ON) |
| Micro Edge | Close > Daily CPR Pivot AND Close > Monthly VWAP (if enabled) |

### 2.3 Recovery Strategy Prerequisites
| Check | Requirement |
|---|---|
| Regime Gate | Market corrected ≥7% from 52W high OR stock corrected 10%–40% |
| Sector Stage | Sector ETF must be in Stage 1 or Stage 2 (REV-RS and REV-EARLY only) |
| RS Positive | RS slope > 0 (REV-RS and REV-EARLY only) |
| RFF Score | ≥ configured minimum (default 3/6) |

---

## 3. The 6 Bull Market Edges — Entry Criteria

### 3.1 POS-BO — Positional Breakout

**Concept:** Price breaks above the N-bar (default 20) resistance high in a confirmed Stage 2 uptrend on above-average volume. The cleanest institutional signal — stock is escaping a base into open air.

**Entry Conditions (all must be true):**
1. Bull Master Toggle: ON
2. POS-BO Edge Toggle: ON
3. Base Confirmed: Stage 2 + Market Bull + MPA Pass
4. Alpha Score ≥ Min Alpha
5. RS Quadrant: LEADING or IMPROVING
6. Micro Edge: Close > CPR + Monthly VWAP
7. Close (or High, if Intraday mode) > 20-bar High (prior bar)
8. Volume > 1.5× 50-bar average
9. **VWMA20 > VWMA50** (volume shelf gate — rules out false spikes)

**Stop Loss:** 10-bar structural low − 0.2× ATR14

**Position Size:** Kelly-adjusted, capped at Max Allocation
- Full Kelly (1.25×): Stage 2 + RS Positive + Volume > 50-bar SMA
- Half Kelly (0.75×): Fewer conditions met

**Dashboard Signal State:** POS-BO turns 🟢 on the trigger bar

---

### 3.2 POS-AC — Positional Accumulation

**Concept:** Buy during the base-building phase itself — before the breakout — when OBV confirms smart money is quietly accumulating. Lower risk entry than POS-BO but requires the stock to be in a tightening VCP-like structure.

**Entry Conditions (all must be true):**
1. Bull Master Toggle: ON
2. POS-AC Edge Toggle: ON
3. Base Confirmed: Stage 2 + Market Bull + MPA Pass
4. Accumulation Structure: Close > EMA20 > SMA50
5. Accumulation Action: Close > Open AND Close in top 30% of bar
6. Volume > 1.2× average
7. Alpha Score ≥ Min Alpha
8. RS Quadrant: LEADING or IMPROVING
9. Micro Edge: Close > CPR + MVWAP
10. **VCP Loose**: ATR < 2× Average ATR AND Volume < 50-bar SMA (consolidation)
11. **OBV Rising**: OBV > OBV[1] > OBV[2] (2-bar momentum)
12. **OBV > OBV SMA20** (above its 20-bar moving average)
13. **VWMA20 > VWMA50** (volume shelf gate)

**Stop Loss:** Same as POS-BO (10-bar low − 0.2× ATR)

**Trail:** Chandelier Exit ratchet (CE-POS). Once T1 is hit, the SL floor becomes the entry price (breakeven lock).

---

### 3.3 SWG-PB — Swing Pullback

**Concept:** Price pulls back from a Stage 2 advance into the EMA20, tightens (VCP Tight), and closes back above the EMA20 with a bullish bar. This is a continuation entry after an established trend.

**Entry Conditions (all must be true):**
1. Bull Master Toggle: ON
2. SWG-PB Edge Toggle: ON
3. Market Health: BULL
4. Close > SMA50 (price is above its trend MA)
5. Low touched or pierced EMA20 (pullback reached the EMA)
6. Close > EMA20 (recovered above the EMA)
7. Close > Open (bullish close)
8. **VCP Tight**: ATR < 1.0× Average ATR (very narrow range)
9. **MA Stack**: SMA150 > SMA200 (Minervini structural filter)
10. **RSI Pocket**: RSI > 30 AND RSI < 70 (not extreme overbought/oversold)
11. **Volume Dry-Up**: 3-bar volume SMA[1] < 50-bar volume average (prior consolidation on thin volume)

**Stop Loss:** 5-bar swing low × (1 − SL Padding %)

**Trail:** EMA20 ratchet. The SL rises each bar to: max(current SL, EMA20 × (1 − trail buffer %)). Breakeven lock after T1.

**Time Stop:** 10 days (if gain < 0.5R at day 10, close position)

**Contextual Exit:** Immediate close if price falls below SMA50

---

### 3.4 SWG-BO — Swing VCP Breakout

**Concept:** A very tight VCP base (ATR < 1× average) breaks above the N-bar high on volume. Unlike POS-BO, this is a shorter-hold swing trade without the full positional prerequisite stack.

**Entry Conditions:**
1. Bull Master Toggle: ON
2. SWG-BO Edge Toggle: ON
3. Market Health: BULL
4. VCP Tight: ATR < 1.0× Average ATR AND Volume < 50-bar SMA
5. Close (or High) > 20-bar prior High
6. Volume > 1.5× average

> Note: SWG-BO does **not** require Base Confirmed or Alpha Score. It is a pure momentum/pattern trade.

**Stop Loss:** 5-bar swing low × (1 − SL Padding %)

**Trail:** EMA20 ratchet (same as SWG-PB)

---

### 3.5 SWG-REV — Swing Reversion

**Concept:** A mean-reversion trade when the stock is severely oversold (RSI < 35) but above its SMA200 (trend intact). Price must close above the prior bar's high (reversal confirmation).

**Entry Conditions:**
1. Bull Master Toggle: ON
2. SWG-REV Edge Toggle: ON
3. Close > SMA200 (long-term trend intact)
4. Close < EMA20 (short-term depressed)
5. RSI < 35 (oversold)
6. Close > Open (bullish bar)
7. Close > High[1] (breaks prior bar's high)

**Stop Loss:** 5-bar swing low × (1 − SL Padding %)

**T1:** Fixed 2.0R (strict for mean-reversion — no dynamic adjustment)

**Time Stop:** 5 days maximum (mean-reversion trades are short-duration by design — if not moving in 5 days, exit)

**Contextual Exit:** Immediate close if price falls below SMA50

---

### 3.6 GAP-GO — Gap & Go

**Concept:** An institutional-grade gap-up where a stock opens above the prior day's high, gaps at least 4%, and closes in the top 40% of the gap bar on ≥3× volume. This signals conviction buying, not a fade.

**Entry Conditions (all must be true):**
1. Bull Master Toggle: ON
2. GAP-GO Edge Toggle: ON
3. Market Health: BULL
4. **Gap Confirmed**: Open > High[1] AND Close > Open
5. **Gap Size ≥ 4%**: (Open − High[1]) / High[1] ≥ 0.04
6. **Intraday Position ≥ 60%**: (Close − Open) / (High − Open) ≥ 0.60 — price must close in the top 40% of the gap bar's range
7. **Volume ≥ 3× average**

**Stop Loss:** Gap bar's low × (1 − SL Padding %)

**Trail:** EMA20 ratchet (same as other swing trades)

**Time Stop:** 10 days (same as SWG-PB)

---

## 4. The 3 Recovery Market Edges — Entry Criteria

### 4.1 REV-CB — Climax Bottom

**Concept:** Identifies a panic capitulation event followed by an institutional reversal. The sequence is: Stretched stock → Panic selling (washout) → Climax bar (highest volume down-day) → Turn bar (bullish close above prior high). This is a high-risk, high-reward counter-trend entry.

**Entry Conditions — 4 Pillars (all must pass):**

| Pillar | Condition | Dashboard |
|---|---|---|
| P1 — Stretched | Stock down ≥15% from 60-bar high | ✓ / ✗ |
| P2 — Oversold | ≥5 red bars in 7-bar window AND close in bottom 25% of 10-bar range | ✓ / ✗ |
| P3 — Climax Bar | Volume ≥ 2× average ON widest-range down bar within 20-bar lookback | ✓ / ✗ |
| P4 — Turn Bar | Close > Open, Close > High[1], Close in top 40% of bar | ✓ / ✗ |

**Additional Gates:**
- Recent Climax: Climax bar occurred within last 10 bars
- RFF Score ≥ minimum
- Regime Gate: Market corrected ≥7% OR stock corrected 10–40%

**Stop Loss:** Climax structural low − 0.5× ATR14 (snapped at climax event)

**T1 Target:** EMA20 reclaim
**T2 Target:** SMA200 reclaim

**Trail (after T1):** EMA20 ratchet trail. Pre-T1, stop stays at the climax low snap.

**Time Stop:** 15 trading days if gain < 0.5R

---

### 4.2 REV-RS — RS Survivor

**Concept:** During a market correction, most stocks fall. An RS Survivor is one that holds up relatively well (RS slope positive) and forms a higher low, then breaks out of its own local resistance on volume. These stocks often lead the next bull leg.

**Entry Conditions (all must be true):**
1. Recovery Master Toggle: ON
2. REV-RS Edge Toggle: ON
3. RS Slope > 0 (Mansfield RS relative to Nifty 500 benchmark)
4. Higher Low Structure: Recent 5-bar low > Prior 10-bar low[5]
5. Daily Trend: Strict pivot trend = Uptrend
6. Stock corrected: 10%–40% from 52W high
7. Breakout: Close > 20-bar prior High
8. Volume > 1.5× average
9. Sector Stage: Stage 1 or Stage 2
10. RFF Score ≥ minimum
11. Regime Gate: Market or stock in correction

**Stop Loss:** Recent higher low × (1 − SL Padding %)

**Trail:** Chandelier Exit ratchet (CE-REC). Once T1 hit, breakeven lock.

**T1:** Entry + 2.5R
**T2:** 52-Week High

**Time Stop:** 15 days if gain < 0.5R

---

### 4.3 REV-EARLY — Early Bird

**Concept:** The earliest possible recovery entry — before RS turns fully positive and before the breakout is confirmed by volume. The stock must show a compressed base (NR7 or inside-bar series) AND reclaim its downtrend trendline. This is the highest-risk recovery edge.

**Entry Conditions (all must be true):**
1. Recovery Master Toggle: ON
2. REV-EARLY Edge Toggle: ON
3. Trendline Reclaim: Close > highest high from bar[10] to bar[20] (downtrend resistance)
4. RS Recovery Structure: Higher Low AND Daily trend Uptrend
5. Base Compressed: NR7 (narrowest range in 7 bars) OR ≥3 inside bars in 10-bar lookback
6. Pivot Break: Close > 15-bar prior high with volume > 1.5× average
7. RS Slope > 0
8. Sector Stage: Stage 1 or Stage 2
9. RFF Score ≥ minimum
10. Regime Gate: Market or stock in correction

**Stop Loss:** Lowest low within NR7 window × (1 − SL Padding %)

**Trail:** Chandelier Exit ratchet (same as REV-RS)

**T1:** Entry + 2.5R
**T2:** 52-Week High

---

## 5. Exit Engine — Complete Rules

### 5.1 T1 Partial Exit (Breakeven Trigger)

| Edge Group | T1 Target | Exit % |
|---|---|---|
| POS-BO / POS-AC | Entry + 2.5R | 30% of position |
| SWG-PB / SWG-BO / GAP-GO | Entry + 2.5R (bull) or 2.0R (bear) | 50% of position |
| SWG-REV | Entry + 2.0R (fixed) | 50% of position |
| REV-CB | EMA20 reclaim price | 50% of position |
| REV-RS / REV-EARLY | Entry + 2.5R | 50% of position |

> **Breakeven Lock:** Once T1 is hit, `is_breakeven = true`. All trailing stops are immediately floored at the entry price — you cannot lose on the remaining runner.

### 5.2 T2 Runner Exit

| Edge Group | T2 Target | Exit % |
|---|---|---|
| SWG-PB / SWG-BO / GAP-GO | Entry + 3.5R (bull) or 3.0R (bear) | 50% of remaining |
| REV-CB | SMA200 reclaim | 50% of remaining |
| REV-RS / REV-EARLY | 52-Week High | 50% of remaining |
| POS-BO / POS-AC | No fixed T2 — full CE trail | Trail to exit |

### 5.3 Trailing Stop Logic by Position Type

**Position A — POS-BO / POS-AC (Chandelier Exit Ratchet):**
- Initial SL: 10-bar low − 0.2× ATR
- Trail: `max(current SL, CE trailing stop)` — only ratchets upward, never down
- CE = `Highest Close[22] − ATR[22] × 3.0` (bull) or `× 3.5` (bear)
- Stage 4 Exit: Immediate close if Weekly Stage turns to 4

**Position B — SWG Trades (EMA20 Ratchet):**
- Initial SL: 5-bar swing low × (1 − SL Padding %)
- Trail: `max(current SL, EMA20 × (1 − trail buffer %))`
- Contextual Kill Switch: Close below SMA50 → immediate exit
- SWG-REV Kill: 5-day time limit regardless of P&L

**Position C — REV-CB (EMA20 Trail after T1):**
- Initial SL: Climax structural low − 0.5× ATR (snapped at climax bar)
- Pre-T1: Fixed at climax low snap
- Post-T1: `max(snapped SL, EMA20 × (1 − trail buffer %), entry price)`

**Position D — REV-RS / REV-EARLY (Chandelier Exit Ratchet):**
- Initial SL: Higher low × (1 − SL Padding %)
- Trail: `max(current SL, CE trailing stop)` — same CE as Position A
- Breakeven lock applied after T1

### 5.4 Time-Decay Exits

| Edge Group | Max Hold | Condition |
|---|---|---|
| POS-BO / POS-AC | 6 weeks (30 trading days) | Unrealised gain < 0.5R AND not yet breakeven |
| SWG Trades | 10 trading days | Same |
| Recovery Trades | 15 trading days | Same |

> Time stops exist to free capital from stagnant positions. They do **not** fire if the trade has already hit breakeven — the runner is protected and can be held via the trailing stop.

---

## 6. Position Sizing Logic

### 6.1 Base Risk Calculation
```
Risk Amount     = Portfolio Capital × (Risk % / 100)
SL Distance     = Entry Price − Initial Stop Loss
Qty by Risk     = Risk Amount / SL Distance
Qty by Capital  = Max Allocation / Entry Price
Final Qty       = min(Qty by Risk, Qty by Capital)
```

### 6.2 Regime Discount
- In a bear market (Market Health ≠ BULL), the risk % is reduced:
  `Regime Risk = max(Base Risk − 0.25%, 0.25%)`

### 6.3 Recovery Edge Discount
- Recovery trades always use the **Recovery Risk %** (default 0.5%), which is typically lower than the Bull Risk % to account for higher uncertainty.

### 6.4 Kelly Multiplier (Bull Trades Only)
| Conditions Met | Kelly Multiplier |
|---|---|
| All 3: Stage 2 + RS Positive + Volume > SMA50 | 1.25× (Full Kelly) |
| Any 2 of 3 | 1.0× (Standard) |
| Only 1 of 3 | 0.75× (Half Kelly) |

### 6.5 Volatility Discount
- ATR % of price is calculated: `atr_pct = ATR / Close × 100`
- High-volatility stocks get a discount: `vol_disc = min(3.0 / atr_pct, 1.0)`
- Final position: `Qty = Qty × max(vol_disc × kelly_mult, 0.75)`

---

## 7. Signal Quality Filters — The 4 Gate System

These filters were added specifically to prevent low-quality signal fires that inflate trade count without improving edge.

### Gate 2 — POS-AC OBV Momentum Filter
**Problem solved:** Accumulation signals firing when price is quiet but no institutional buying is detectable.
**Solution:** OBV must show 2-bar consecutive rises AND OBV must be above its 20-bar SMA.
**Effect:** Confirms that volume-weighted buying (smart money) is actually increasing before calling accumulation.

### Gate 3 — SWG-PB Quality Stack
**Problem solved:** Pullback entries firing in weak or structurally broken trends.
**Solution:** Three additional checks:
- **MA Stack** (SMA150 > SMA200): Confirms Minervini-style structural alignment
- **RSI Pocket** (30–70): Avoids entries at RSI extremes (overextended or crashing)
- **Volume Dry-Up** (3-bar vol SMA < 50-bar avg): Prior bars must show consolidation, not distribution

### Gate 4 — GAP-GO Quality Filter
**Problem solved:** Small gaps or gaps that immediately fade triggering entries.
**Solution:** Three additional checks:
- **4% Minimum Gap**: Rules out tiny overnight moves
- **Intraday Position ≥ 60%**: Close must be in the upper 40% of the gap bar (held its gains)
- **3× Volume**: Confirms institutional participation, not retail noise

### Gate 5 — Volume Shelf Filter (POS-BO / POS-AC)
**Problem solved:** Volume spikes on a single bar triggering breakout signals without sustained volume interest.
**Solution:** `VWMA(volume, 20) > VWMA(volume, 50)` — the 20-bar volume-weighted average must be above the 50-bar average, confirming that elevated volume has been sustained across multiple recent bars.

---

## 8. Market Regime Decision Tree

Use this tree at the start of each trading day to frame your session context:

```
Check CNX500 vs SMA200
│
├── CNX500 > SMA200 AND SMA50 > SMA200?
│   └── BULL MARKET → Focus on Bull edges (POS-BO, POS-AC, SWG-PB, SWG-BO, GAP-GO)
│       └── Recovery edges remain armed — look for REV-RS / REV-EARLY leaders
│
└── CNX500 < SMA200?
    ├── CNX500 down ≥7% from recent high?
    │   └── CORRECTION → Prioritise REV-CB, REV-RS, REV-EARLY
    │       └── Bull edges still fire but use reduced sizing (regime discount applies)
    │
    └── CNX500 far below SMA200?
        └── BEAR → Recovery edges only. Disable Bull edges OR accept reduced sizing.
            └── Watch for market reclaim (recent low > prior low) as recovery signal
```

---

## 9. Workflow Integration with the Weinstein Commander

The Unified Ecosystem is designed to work alongside the rest of the Weinstein Commander suite:

| Tool | Role |
|---|---|
| **Weinstein and Swing Pro Dashboard v67.0** | Provides day-to-day multi-stock overview, entry date tracking, portfolio slot management |
| **Web Commander (Bull + Recovery Screeners)** | Weekly/daily scan to shortlist candidates; outputs a watchlist |
| **Weinstein_Unified_Ecosystem_v2.2.pine** | Applied per stock from the shortlist for final signal confirmation and position sizing |
| **Context Layers v1.0** | Provides Wyckoff, Volume Profile, SMC, and CONTEXT SCORE overlay on the same chart for institutional context confirmation |

### Recommended Workflow

**Step 1 (Weekend / Any Day):**
Run the Web Commander Bull Screener and Recovery Screener to get the candidate shortlist.

**Step 2 (Daily Pre-Market):**
Load the Unified Ecosystem on each shortlisted stock. Check:
- Market Health, Stage, RS Quadrant (top 3 rows)
- Any 🟢 signal in the Bull or Recovery sections

**Step 3 (Entry Decision):**
- 🟢 on POS-BO or SWG-BO → Place a buy-stop limit order above the breakout level at the open
- 🟢 on POS-AC or SWG-PB → Place a market order at the open or a limit order at EMA20
- 🟢 on GAP-GO → Only valid on the gap day itself; confirm volume by 11:30 AM before acting
- 🟢 on REV-CB → Enter on the next bar open after the turn bar

**Step 4 (Position Management):**
- Note the Initial SL from the dashboard or strategy tester
- Log the `active_catalyst` label (shown on chart as the entry comment) — this determines your trail type
- Watch for T1 target (🟡 label on chart) — set a limit sell order at T1 price
- After T1, your stop is automatically at breakeven — hold the runner via the CE or EMA trail

**Step 5 (Exit Review):**
Each day, check:
- Is the trailing stop still valid? (CE step-line rising = yes)
- Has Stage 4 been reached? → Close POS trades immediately
- Has price closed below SMA50? → Close SWG trades immediately
- Has the time stop been triggered? → Close if < 0.5R and not breakeven

---

## 10. Edge Selection Cheat Sheet

| Market Condition | Best Edges | Avoid |
|---|---|---|
| Strong Bull, Stage 2 | POS-BO, POS-AC | REV-CB (counterproductive) |
| Bull with tight VCP | SWG-PB, SWG-BO | REV-EARLY (low reward) |
| Bull gap-up day | GAP-GO | SWG-REV (wrong direction) |
| Oversold in bull | SWG-REV | REV-CB (need correction context) |
| Market correction | REV-RS, REV-EARLY | POS-BO (no base confirmed) |
| Panic/capitulation | REV-CB | All bull edges |
| Stage 4 confirmed | None | All edges — stay flat |

---

## 11. R-Multiple Reference Table

| Edge | T1 (exit %) | T2 (exit %) | Remainder |
|---|---|---|---|
| POS-BO | 2.5R → 30% out | No T2 (CE trail) | 70% runs |
| POS-AC | 2.5R → 30% out | No T2 (CE trail) | 70% runs |
| SWG-PB | 2.5R → 50% out | 3.5R → 50% of rest | ~25% runs |
| SWG-BO | 2.5R → 50% out | 3.5R → 50% of rest | ~25% runs |
| SWG-REV | 2.0R → 50% out | No T2 | 50% closed |
| GAP-GO | 2.5R → 50% out | 3.5R → 50% of rest | ~25% runs |
| REV-CB | EMA20 → 50% out | SMA200 → 50% of rest | ~25% runs |
| REV-RS | 2.5R → 50% out | 52W High → 50% of rest | ~25% runs |
| REV-EARLY | 2.5R → 50% out | 52W High → 50% of rest | ~25% runs |

> **Note:** The `SWG-REV` has a hard 5-day time stop and only a T1 target. It is designed as a quick mean-reversion trade, not a runner.

---

## 12. Troubleshooting Signals

| Symptom | Likely Cause | Fix |
|---|---|---|
| No bull signals on any stock | Market Health = CORRECTION/BEAR | Check CNX500 — regime discount may be suppressing signals |
| POS-BO fires but not POS-AC | OBV gate blocking POS-AC | Normal — POS-AC needs OBV confirmation; wait for OBV to trend up |
| SWG-PB not firing on obvious pullbacks | MA Stack (150 > 200) failing | Check if SMA150 has crossed below SMA200 — stock may be weakening |
| REV-CB firing on every bounce | CB Pillar thresholds too loose | Increase Min Climax Volume Mult or Min Red Bars in Washout |
| Recovery signals fire in bull market | Regime gate not blocking | Confirm "Require Recovery Market Regime?" is ON |
| Alpha Score shows 🔴 on quality stocks | Min Alpha Score too high | Lower from 50 to 40, or disable Macro Edge requirement |
| Stage shows Stage 1 but looks like Stage 2 | Slope threshold too tight | Reduce `slopeThresh` input slightly |
| RFF shows "NO DATA" | TradingView lacks financials for this ticker | Set Min RFF Score to 0 for this stock, or skip |

---

## 13. May 2026 Update — v3.5 + v3.6 Changes

This section documents the May 2026 changes to `Weinstein_Unified_Ecosystem_v3.4.pine`.

### 13.1 What Changed

| Version | Date | Change |
|---|---|---|
| **v3.4** | 2026-05-20 | Added Wyckoff Spring/SOS/JAC entries to `trigger_rec_raw`; POS-ACCUM and REV-CB/RS/EARLY temporarily removed from triggers. **[Superseded]** |
| **v3.5** | 2026-05-21 | **POS-ACCUM and REV-* RE-ADDED to triggers.** The v3.4 removals were based on a 30-day forward-window backtest (wrong horizon for positional / accumulation / recovery setups). Wyckoff catalysts remain **additive** alongside REV-*, not replacements. |
| **v3.6** | 2026-05-21 | **Catalyst-aware fallback ATR multipliers** when the structural SL anchor is above close. POS=4.0×, WYC=3.5×, REV-RS/EARLY=2.5×, SWG=1.5×. Previously all catalysts fell back to 1.5×, which knocked positional trades out within the first 2 weeks. |
| **v4.0** | 2026-05-22 | **ML & DB Integration**: Added Machine Learning Logistic Regression Probability model and RSI 47-54 Dead Zone filter. Replaced all sector/string mapping hacks with a physical 664-symbol `sectors.db` sync. |

### 13.2 Triggers Currently Active (v4.0+)

```
trigger_bull_raw = pos_bo_trigger OR pos_ac_trigger OR swing_pb_trg
                   OR swing_bo_trg OR swing_rev_trg OR gap_go_trg

trigger_rec_raw  = trigger_wyc_spring_sos OR trigger_wyc_jac
                   OR trigger_wyc_sos OR trigger_wyc_spring
                   OR trigger_rev_cb OR trigger_rev_rs OR trigger_rev_early
```

Both Wyckoff (5 triggers) and REV-* (3 triggers) fire simultaneously. The strategy enters on whichever fires first (priority order: WYC > REV per Commander_Recovery v2.0).

### 13.3 SL Discipline (v3.6)

Initial SL anchors are **structural** (unchanged):
- POS-*: `lowest_low_10 − 0.2×ATR14`
- WYC-*: `wyc_base_low × 0.98` (Spring) or `wyc_base_low − 0.3×ATR14`
- REV-CB: `climax_low_snap − 0.5×ATR14`
- REV-RS / REV-EARLY: structural low − pad
- SWG-*: `lowest_low_5 × (1 − sl_pad_pb)` or gap-bar low

**Fallbacks** (when structural anchor is above close) now scale with the trade horizon:
| Catalyst | Fallback | Was |
|---|---|---|
| POS-BO, POS-ACCUM | `close − 4.0×ATR14` | `close − 1.5×ATR14` |
| WYC-* | `close − 3.5×ATR14` | `close − 1.5×ATR14` |
| REV-RS, REV-EARLY | `close − 2.5×ATR14` | `close − 1.5×ATR14` |
| SWG-* | `close × 0.99` | (unchanged) |
| REV-CB | `nz(cb_sl_raw, close × 0.92)` | (unchanged) |

### 13.4 Pine Recompile Required

After updating from v3.4 (or earlier) to v3.6, you must:
1. Open `Weinstein_Unified_Ecosystem_v3.4.pine` in TradingView Pine Editor
2. Save (Ctrl+S) and `Add to Chart` to recompile

### 13.5 Catalyst Behavior You Should Expect

- **POS-BO / POS-ACCUM trades will have wider initial SL** (~6-12% rather than ~3%) when the fallback path triggers. Position sizing at 1% risk automatically halves the share count — this is correct discipline.
- **Wyckoff trades fire alongside REV-***; you may see WYC and REV signals on the same chart, with WYC taking precedence in the priority cascade.
- **No catalyst is suppressed**. If a setup qualifies, it fires.
