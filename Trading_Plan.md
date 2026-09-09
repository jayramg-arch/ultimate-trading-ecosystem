# Weinstein–Minervini Commander Trading Plan

The following comprehensive table formalizes the operational instructions from the Weinstein–Minervini Commander Trading Bible (v5.0). It maps the specific parameters, constraints, and strategy conditions for all primary Pine Script modules across both Swing and Positional trading tracks.

## 1. Commander_Screener_Beta_Edition_v2.9.pine
*(Bull Screener & Re-Screening Validation)*

| Sr# | Parameter | Constraint | Value | Swing Trading | Positional Trading | Remarks |
|---|---|---|---|---|---|---|
| 1.1 | **alphaScore** | Hard Floor | ≥ 60 | ≥ 60 (≥ 80 for full size) | ≥ 60 (≥ 80 for full size) | < 60 = NO catalyst can fire. |
| 1.2 | **pyScore** | Hard Floor | ≥ 60 | ≥ 60 | ≥ 60 | ≥ 80 = full size. Mirrors Python `bull_screener`. |
| 1.3 | **Catalyst** | Hard Floor | Active (> 0) | SWG-PB, SWG-BO, SWG-REV, GAP-GO | POS-BO, POS-AC | Must match the current market regime. |
| 1.4 | **9-Gate POS-BO Panel** | Confluence | ≥ 8/9 ✓ | N/A | ≥ 8/9 ✓ | 9/9 ✓ = highest conviction breakout. |
| 1.5 | **wRsiVal** | Hard Floor | ≥ 60 | N/A | ≥ 60 | Required for POS-BO. wRSI 65+ = momentum confirmed. |
| 1.6 | **hunter_adx_ok** | Hard Floor | ≥ 25 | N/A | ≥ 25 | Required for POS-BO. ADX 30+ = strong trend. |
| 1.7 | **POS-ACCUM RSI Gate** | Hard Floor | dailyRsi ≤ 50 | N/A | dailyRsi ≤ 50 | Required for POS-AC. RSI ≤ 40 = textbook accumulation. |
| 1.8 | **OBV Trending Up** | Hard Floor | 2-bar rise + > SMA20 | N/A | Required | Required for POS-AC and POS-BO. |
| 1.9 | **VCP Tight** | Hard Floor | ATR < 1.0x ATR-SMA | Required (SWG-BO) | Confluence (POS-BO) | Tighter base = sharper breakout. |
| 1.10 | **Vol Shelf** | Hard Floor | VWMA20 > VWMA50 | N/A | Required | Without it, downgrade size by 50%. |
| 1.11 | **Catalyst Volume** | Hard Floor | ≥ 1.5x to 3.0x avg | 1.5x (SWG-BO), 3.0x (GAP-GO) | 1.5x (POS-BO), 1.2x (POS-AC) | Volume confirms institutional commitment. |
| 1.12 | **Defensive Mode** | Confluence | Penalty if > 30 bars | Optional (-10 pyScore) | Optional (-10 pyScore) | Use when capital preservation is paramount. |

---

## 2. Commander_Capitulation_Screener_v1.5.pine
*(Recovery Track Validation)*

| Sr# | Parameter | Constraint | Value | Swing / Positional (Recovery) | Remarks |
|---|---|---|---|---|---|
| 2.1 | **Regime Gate** | Hard Floor | TRUE | Required for all Recovery edges | CNX500 ≥ 7% off 52W high OR Stock 10-40% off 52W high. |
| 2.2 | **P1 — Stretched** | Hard Floor | Down ≥ 15% from 60-bar high | Trigger (REV-CB) | Price well below recent range ceiling. |
| 2.3 | **P2 — Oversold** | Hard Floor | ≥ 5 red bars in 7-bar win. | Trigger (REV-CB) | Close in bottom 25% of 10-bar range. |
| 2.4 | **P3 — Climax Bar** | Hard Floor | Vol ≥ 2x 50-bar avg | Trigger (REV-CB) | Widest-range down bar in last 20 bars. |
| 2.5 | **P4 — Turn Bar** | Hard Floor | Close > Open & Close > High[1] | Trigger (REV-CB) | Close in top 40% of bar. Bullish reversal. |
| 2.6 | **REV-RS (RS Survivor)** | Hard Floor | Higher low & RS slope > 0 | Trigger (REV-RS) | Close > 20-bar high on 1.5x vol. |
| 2.7 | **REV-EARLY** | Hard Floor | Comp. Base + Trendline Reclaim | Trigger (REV-EARLY) | Earliest entry; highest risk. NR7 or ≥3 inside bars. |

---

## 3. Weinstein_Context_Layers_v1.0.pine
*(Unified Institutional Context: Wyckoff, Volume Profile, SMC)*

| Sr# | Parameter | Constraint | Value | Swing Trading | Positional Trading | Remarks |
|---|---|---|---|---|---|---|
| 3.1 | **CONTEXT SCORE** | Hard Floor | ≥ +3 (BULL) | ≥ 0 (NEUTRAL) for half size | ≥ +3 (BULL) for full size | ≥ +6 = STRONG BULL. ≤ -3 = BEAR (Disqualify). |
| 3.2 | **Wyckoff Bias** | Hard Floor | ACCUMULATION | ACCUMULATION or NEUTRAL | ACCUMULATION or NEUTRAL | DISTRIBUTION = Skip / Exit. |
| 3.3 | **Wyckoff Phase Event** | Confluence | SOS or LPS | SOS/LPS (Bull), SC/ST (Recovery) | SOS/LPS (Bull) | SOS = strongest bullish event. |
| 3.4 | **VP Position** | Hard Floor | At or above POC | At or above POC | At or above POC | Above VAH = strong, below VAL = weak/skip. |
| 3.5 | **VP Distance to POC** | Confluence | Within 2 ATR | Within 2 ATR | Within 2 ATR | Buying near POC = lower-risk entry. |
| 3.6 | **SMC Trend** | Hard Floor | BULLISH | BULLISH or NEUTRAL | BULLISH or NEUTRAL | Trend continuation / change of character. |
| 3.7 | **Bull Order Block** | Confluence | Active OB below | Active OB below | Active OB below | Maximum-confluence zone for support/SL. |
| 3.8 | **Liquidity Sweep** | Confluence | Bullish sweep + reclaim | Bullish sweep | Bullish sweep | Confirms stop-hunt (+20 Alpha bonus in Screener). |

---

## 4. Wesinstein Swing Zigzag [Strict v6.0].pine
*(Trend Pivot Context)*

| Sr# | Parameter | Constraint | Value | Swing Trading | Positional Trading | Remarks |
|---|---|---|---|---|---|---|
| 4.1 | **Trend State** | Hard Floor | HH-HL (Higher High/Higher Low) | HH-HL | HH-HL | LH-LL = Structural downtrend (Disqualify). |
| 4.2 | **Last Swing High** | Confluence | Above previous swing high | Breakout confirmed | Breakout confirmed | Higher High validation. |
| 4.3 | **Last Swing Low** | Confluence | Above previous swing low | Pullback held | Pullback held | Higher Low validation. |
| 4.4 | **Pivot Lookback** | Hard Floor | Left=2, Right=2 | Left=2, Right=2 | Left=2, Right=2 | Must match Beta Screener & Ecosystem. |

---

## 5. Weinstein_Unified_Ecosystem_v2.3.pine
*(Strategy Execution, Triggers, & Position Management)*

| Sr# | Parameter | Constraint | Value | Swing Trading | Positional Trading | Remarks |
|---|---|---|---|---|---|---|
| 5.1 | **Market Health** | Hard Floor | CNX500 > SMA200 & SMA50 > SMA200 | Required (Bull) | Required (Bull) | Macro prerequisite. |
| 5.2 | **pos_bo_trigger** | Hard Floor | TRUE | N/A | Trigger | Requires wRSI ≥ 60 AND adx_val ≥ 25. |
| 5.3 | **pos_ac_trigger** | Hard Floor | TRUE | N/A | Trigger | Requires d_rsi ≤ 50 AND VWMA20 > VWMA50. |
| 5.4 | **swing_pb_trg** | Hard Floor | TRUE | Trigger | N/A | Pullback to EMA20 on dry volume. |
| 5.5 | **swing_bo_trg** | Hard Floor | TRUE | Trigger | N/A | VCP tight base breakout on 1.5x volume. |
| 5.6 | **gap_go_trg** | Hard Floor | TRUE | Trigger | N/A | Gap ≥ 4%, Intraday Pos ≥ 60%, 3x vol. |
| 5.7 | **swg_rev_trg** | Hard Floor | TRUE | Trigger | N/A | RSI < 35 above SMA200 (mean-reversion). |
| 5.8 | **Bull Hold Window** | Confluence | ≤ 3 bars | Valid entry window | Valid entry window | Can enter within 3 bars if valid. |
| 5.9 | **T1 Target** | Hard Floor | Reached | +2.5R (Bull), +2.0R (SWG-REV) | +2.5R | Breakeven lock activates on T1. |
| 5.10| **T2 Target / Trail** | Hard Floor | Reached | EMA20 ratchet, +3.5R | CE-POS ratchet | Dynamic trailing logic. |
| 5.11| **Time Stop / WARN** | Hard Floor | Triggered | 10 days (5 days SWG-REV) | 6 weeks (30 days) | Exit if gain < 0.5R and not at breakeven. |
| 5.12| **Regime Change Exit** | Hard Floor | CNX500 fails Regime Gate | Exit all Recovery | N/A | If macro fails, the recovery trade fails. |

---

## 6. Commander_Risk_Allocator_v1.0.pine
*(Position Sizing, Limits & Alerts)*

| Sr# | Parameter | Constraint | Value | Swing Trading | Positional Trading | Remarks |
|---|---|---|---|---|---|---|
| 6.1 | **Risk per Trade** | Hard Floor | 0.75% (Bull) / 0.50% (Recovery) | Max 0.75% / 0.50% | Max 0.75% / 0.50% | VIX > 22 → reduce to 0.50% / 0.25%. |
| 6.2 | **Stop-Loss Distance** | Hard Floor | ATR-based (1.5x ATR14) | ATR-based | ATR-based | Follow ATR, don't use arbitrary % stops. |
| 6.3 | **Max Allocation** | Hard Floor | ≤ ₹25,000 or 25% of capital | Max 25% | Max 25% | Protects against single-stock blowups. |
| 6.4 | **Position Size** | Hard Floor | > 0 shares | Round down to 1 share | Round down to 1 share | If Size = 0, skip trade. |
| 6.5 | **Kelly Multiplier** | Confluence | 0.75x to 1.25x | 0.75x to 1.25x | 0.75x to 1.25x | 1.25x requires Stage 2 + RS Pos + Vol > SMA50. |
| 6.6 | **Volatility Discount** | Hard Floor | Max 1.0 (reduce if ATR% > 3%) | ≥ 25% reduction | ≥ 25% reduction | Curbs sizing on high volatility / penny stocks. |
| 6.7 | **Sector Concentration** | Hard Floor | Max 25% of capital | Max 25% | Max 25% | Hard cap; if hitting it, skip the next candidate. |
| 6.8 | **Max Open Positions** | Hard Floor | Max 6 simultaneously | Max 6 | Max 6 | Beyond 6, focus dilutes. |
| 6.9 | **Telegram Alert** | Confluence | Auto-fire on entry | ON | ON | Do not override the alert manually. |

---

## 7. Weinstein and Swing Pro Dashboard v67.0.pine
*(Visual Ecosystem Aggregator & Trade Management UI)*

| Sr# | Module Area | Component / Parameter | Constraint | Value | Remarks |
|---|---|---|---|---|---|
| 7.1 | **Left Column: Macro & Sector** | Market Regime & Sector RS | Hard Floor | CNX500 > SMA200 | Visually confirms macro alignment. Disqualifies if sector is lagging. |
| 7.2 | **Left Column: Asset Quality** | RRG Quadrant & Volume | Confluence | LEADING / IMPROVING | Uses Mansfield RS to position stock in RRG quadrant. |
| 7.3 | **Left Column: Action/Setup** | Active Catalyst | Hard Floor | Catalyst string | Shows POS-BO, POS-AC, SWG-PB, SWG-BO, SWG-GAP, etc. |
| 7.4 | **Right Column: Positional** | Weekly Stage (Mansfield) | Hard Floor | Stage 2 (UP) | Disqualifies Stage 4 (DOWN) immediately. |
| 7.5 | **Right Column: Swing** | Daily Trend | Hard Floor | Valid Trend | Maps to Swing Zigzag (HH-HL) visually. |
| 7.6 | **Right Column: Screener** | Alpha Score / pyScore | Hard Floor | ≥ 60 | Displays real-time score matching the Python Screener. |
| 7.7 | **Trade Lines (Chart)** | Dyn T1/T2 & Trailing SL | Hard Floor | SL/T1/T2 active | Provides visual algorithmic management (2R/3R targets) on the chart. |

---

## 8. Unified Step-by-Step Trading Workflow
*(Comprehensive Synthesis of All Ecosystem Modules)*

| Step | Workflow Stage | Key Tool / Module | Key Field / Parameter | Constraint | Swing Trading | Positional Trading | Remarks |
|---|---|---|---|---|---|---|---|
| **1** | **Macro & Market Filter** | Dashboard / Screener | `Market Health` & `Regime Gate` | Hard Floor | CNX500 > SMA200 | CNX500 > SMA200 | Do not initiate new long trades if macro trend is bearish. |
| **2** | **Asset Quality (Positional)** | Dashboard / Context Layers | `Weekly Stage` & `Wyckoff Bias` | Hard Floor | Stage 2 (UP) | Stage 2 (UP) & Accumulation | Disqualify Stage 4 / Distribution assets immediately. |
| **3** | **Trend & Structure (Swing)** | Swing Zigzag / Dashboard | `Trend State` | Hard Floor | HH-HL | HH-HL | Must be in an active structural uptrend (HH-HL). |
| **4** | **Momentum & Liquidity** | Context Layers / Screener | `VP Position` & `wRsiVal` | Hard Floor / Confluence | > POC | > POC, wRSI ≥ 60 | Price must be accepted above Volume Point of Control. |
| **5** | **Catalyst Identification** | Unified Ecosystem / Screener | `Catalyst` & `alphaScore` | Hard Floor | SWG-PB, SWG-BO, SWG-GAP, SWG-REV | POS-BO, POS-AC | Must have a valid, active ecosystem signal & alphaScore ≥ 60. |
| **6** | **Signal Confirmation** | Unified Ecosystem / Dashboard | `Bull Hold Window` & `Volume Shelf` | Hard Floor | ≤ 3 bars | ≤ 3 bars & Vol > VWMA50 | Trade must be taken near the pivot, not chased. |
| **7** | **Risk Calculation** | Risk Allocator | `Risk per Trade` & `Stop-Loss` | Hard Floor | Max 0.75%, SL at 1.5x ATR | Max 0.75%, SL at 1.5x ATR | Standardize risk across all trades; ignore arbitrary % stops. |
| **8** | **Position Sizing** | Risk Allocator | `Max Allocation` & `Volatility Discount` | Hard Floor | Max 25%, reduce if ATR% > 3% | Max 25%, reduce if ATR% > 3% | Scale down for high-volatility/penny stocks. |
| **9** | **Active Management** | Unified Ecosystem / Dashboard | `T1 Target` & `T2 Trail` | Hard Floor | +2.5R → Breakeven SL | +2.5R → Breakeven SL | Lock breakeven at +2.5R, trail remainder with EMA20/CE. |
| **10** | **Time Stop & Exits** | Unified Ecosystem / Screener | `Time Stop` & `Regime Exit` | Hard Floor | Exit < 0.5R at 10 days | Exit < 0.5R at 30 days | Free up capital if the trade stagnates. |
