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
