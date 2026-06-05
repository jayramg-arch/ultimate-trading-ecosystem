# Commander Bull Screener v3.3 (Pure Price Action) — User & Trading Guide

> **Module Role:** The **primary bull-market discovery engine** of the Weinstein Commander suite. Where the Recovery Screener finds beaten-down quality, the Bull Screener finds the market's strongest breakout, accumulation, and pullback stocks. It implements six Minervini/Weinstein catalysts and grades each with a 0–100 Alpha Score.
>
> **Canonical implementation:** `bull_screener.py` (Python — the source of truth for backtests, the web app, and live picks). **Pine mirror:** `Commander_Bull_Screener_v3.3.pine` + the catalyst engine inside `Weinstein_Unified_Ecosystem_v3.4.pine` and `Weinstein and Swing Pro Dashboard v67.4.12.pine`.

---

## 0. What Changed — the Pure Price-Action Conversion (June 2026)

This is the single biggest change in the screener's history. Per the trading DNA ("replace lagging indicators with pure price action, wherever possible"), **every catalyst gate and the Alpha Score were converted off RSI / MACD / BB / ADX onto price-action equivalents.** Python and all three Pine surfaces are now consistent with each other and with this design.

### Indicator → price-action replacements (the rosetta stone)

| Was (lagging indicator) | Now (pure price action) | Used in |
|---|---|---|
| `RSI > 60 / > 50` | close **>** its 10-bar-ago **and** 5-bar-ago value (N-bar momentum) | Alpha Score |
| `ADX strong` | **≥ 7 of last 14 bars** are up-closes making higher highs (directional structure) | Alpha Score, POS-BO |
| Weekly `RSI ≥ 60` | weekly close **>** its 5-week-ago close (PA weekly momentum) | POS-BO |
| Daily `RSI ≤ 50` (anti-chase) | close **≤** its 5-day-ago close × 1.05 (not extended / not chasing a run-up) | POS-ACCUM |
| `RSI 30–70` pocket | retrace **38–62%** of the 20-bar range off the swing high | SWG-PB |
| `RSI < 35` oversold | prior down-structure (close[1]<close[2]<close[3]) + bullish reversal bar | SWG-REV |

### Structural bug fixes that un-blackouted the catalysts

- **Squeeze gate removed from `weinstein_setup`.** The positional base gate had wrongly AND-ed in `ma_sqz` (10% coil) + `bb_sqz` (NR7) — a *squeeze* is mutually exclusive with a *breakout*, so it nullified the entire positional book (0 POS picks for 24 months). Removed to match canonical Pine line 1622. POS-BO/POS-ACCUM now fire.
- **SWG-PB quality restored + structural stop.** The pullback was firing on weak, rolling-over stocks; restored the full Minervini stack (`close>50>150>200`) and added entry **confirmation** (close > prior day's high — enter on resumption, not into the falling dip). Stop changed to a **structural EMA20-floor** (your hard-floor rule) instead of a fixed ATR that got whipsawed. Forward window widened 30 → 60 days (8–12-week hold).
- **SWG-REV logic contradiction fixed.** It had required *today be a down close* AND *close > prior high* simultaneously (impossible). `pa_oversold` now measures **prior** weakness, leaving today as the reversal bar.
- **Macro-edge added to the Alpha Score** for Python↔Pine parity (volume regime: +10 if volume > average, −20 if thin).

### Validated edge (24-month nifty500, catalyst-aware matched windows)

| Catalyst | Win% | Matched α | Notes |
|---|---|---|---|
| **POS-ACCUM** | 43% | **+3.20%** | strongest; un-starved by the PA anti-chase |
| **SWG-BO** | 51% | **+1.80%** | |
| **SWG-REV** | 53% | **+0.95%** | |
| **POS-BO** | 48% | **+0.60%** | your core positional edge |
| **SWG-PB** | — | regime-sensitive | momentum-continuation; underperforms in corrective tapes |

Edge is concentrated in **down/defensive tapes** (relative strength when the market falls). SWG-PB is the right tool only in confirmed up-trends.

---

## 1. What It Does

For each symbol it:
1. Fetches 2y daily + 3y weekly OHLCV (date-pinnable via `data_provider` for backtests).
2. Computes daily indicators, the **weekly Weinstein Stage** (30-WMA slope + price position), **Mansfield/JdK RS** vs `^CRSLDX` (Nifty 500), RRG quadrant, and VCP/pivot context.
3. Computes the **Alpha Score** (0–100, pure price action).
4. Runs the **catalyst priority cascade** — assigns at most one catalyst label per symbol.
5. Computes a catalyst-aware **SL / T1 / T2** and a composite **Score**.

Liquidity floor: `min_turnover_cr = 5.0` (₹5 Cr/day) unless `force_output`. Alpha gate: `alpha_gate = 60`.

---

## 2. The Six Catalysts — Priority Cascade (pure price action)

Evaluated in this order; the first match wins. `mkt_bull` (Nifty 500 close>SMA200 and SMA50>SMA200) is required for all bull catalysts.

### POS-BO — Positional Breakout *(your core strategy)*
`base_confirmed AND alpha_ok AND 20-bar-high breakout AND volume>1.25× AND PA weekly momentum AND PA directional strength`
- `base_confirmed` = `(weinstein_setup OR mature_trend_ok) AND mpa_pass` (close>sma150>sma200).
- `weinstein_setup` = Stage 1/2 + full trend stack + RS>0 + volume-accumulation + Stage-2-fresh + 52-week trend-template (NO squeeze).
- Forward window: **120 days**. SL: **4× ATR**. Targets: **5R / 10R** (let winners run).

### POS-ACCUM — Stage 1→2 Accumulation
`base_confirmed AND alpha_ok AND OBV rising AND is_vcp_accum AND within 10% of 30-bar high AND pa_not_extended`
- `pa_not_extended` (PA anti-chase) = close ≤ 5-day-ago close ×1.05 — don't buy an already-extended accumulation.
- `is_vcp_accum` = looser VCP (1.5× ATR) so quiet accumulation isn't starved.
- Forward window: **180 days**. SL: 4× ATR. Targets: 5R / 10R.

### SWG-GAP — Gap-and-Go
`gap_up AND gap ≥ 4% AND close in top 40% of the gap bar AND volume > 3×` (pure price action; no weinstein gate).
- Forward window: **30 days**. SL: 1.5× ATR. Targets: 2R / 4R.

### SWG-BO — Swing Breakout
`is_vcp_tight AND 20-bar-high breakout AND volume > 1.5×` (clean price/volume structure).
- Forward window: 30 days. SL: 1.5× ATR. Targets: 3R / 5R.

### SWG-PB — Swing Pullback *(your favourite — quality pullback)*
`minervini stack AND bull_pullback AND is_vcp_tight AND PA pullback pocket AND volume dry-up AND close > prior-day high`
- `bull_pullback` = close>sma50, low ≤ EMA20 (tagged), close > EMA20, up day.
- `pb_pocket_pa` = 38–62% Fib retrace of the 20-bar range (50% sweet spot).
- **Entry confirmation:** close > prior day's high (enter the bounce, not the knife).
- **Stop = structural EMA20 floor** (2% below EMA20, min 1× ATR room) — EMA20 is the hard floor.
- Forward window: **60 days** (8–12-week swing). *Regime note: needs a confirmed up-trend; underperforms in corrections.*

### SWG-REV — Swing Reversal
`NOT Stage 4 AND rev_struct (close>sma200, close<ema20) AND pa_oversold (prior 3-bar down) AND close>open AND close>prior-day high`
- Forward window: 30 days. SL: 1.5× ATR. Targets: 2R / 2R.

---

## 3. The Alpha Score (0–100, pure price action)

| Component | Points | Logic |
|---|---|---|
| Above EMA20 | +15 | close > EMA20 |
| Above SMA50 | +15 | close > SMA50 |
| **PA momentum** | +20 / +10 | close>close[10] **and** close>close[5] / only close>close[10] *(replaces RSI)* |
| **PA directional** | +10 | ≥7 of last 14 bars up + higher high *(replaces ADX)* |
| Volume thrust | +20 / +10 | up day & rel-vol ≥1.5 / ≥1.0 |
| Tight to EMA20 | +20 / +10 | distance < 5% / < 10% |
| **Macro edge** | +10 / −20 | rel-vol > 1.0 (participation) / thin (distribution) |

`alpha_ok` = Alpha ≥ 60. Drives the `POS-*` gates and the 5-star grade across the ecosystem.

---

## 4. Catalyst-Aware Stops & Targets

| Catalyst family | Forward window | Stop | T1 / T2 |
|---|---|---|---|
| POS-* | 120–180 d | 4× ATR | 5R / 10R |
| WYC-* | 120 d | 3.5× ATR | — |
| REV-* | 90 d | 2.5× ATR | — |
| **SWG-PB** | 60 d | **EMA20 structural floor** | 3R / 5R |
| SWG-BO / SWG-PB | 30–60 d | 1.5× ATR | 3R / 5R |
| SWG-GAP | 30 d | 1.5× ATR | 2R / 4R |
| SWG-REV | 30 d | 1.5× ATR | 2R / 2R |

**Why catalyst-aware:** a 1.5× daily-ATR stop on a 120-day positional trade gets whipsawed in the first weeks; a positional 4× stop on a swing gives back too much. Match the stop to the design horizon. *The recurring lesson this session: the signals find edge; tight stops on long holds give it back.*

---

## 5. Output Columns (`Bull_Screener_*_Results.csv`)

`Symbol · Catalyst · Score · Catalyst_Score · Alpha · Stage · JdK_RS_Ratio · JdK_RS_Momentum · RRG_Quadrant · RRG_Trajectory · ML_Prob · Rel_Vol · RSI · VCP_Valid · VCP_Score · Days_Since_Pivot · Entry · SL_pct · T1_pct · T2_pct · Suggested_Size · …`

*(RSI is still shown as a display column for reference — it is no longer in any gate.)*

---

## 6. How to Use

- **Python / web app:** runs via `run_bull_screener()` (Web Commander → Hunter, or `python bull_screener.py`). Writes the results CSVs consumed by the matcher and the Golden Picks pipeline.
- **TradingView:** `Commander_Bull_Screener_v3.3.pine` shows the catalyst label + Alpha Score per chart. **Recompile after any sync.**
- **Live workflow:** screener catalysts → matcher conviction filter (≥6) → Top-N → Golden Picks. Over-tight individual gates compound across these layers, so the gates are calibrated to keep a workable candidate set flowing.

---

## 7. Diagnostics

The catalyst **FUNNEL** (printed each run + mirrored to `Bull_Screener_Funnel.log`) counts per-gate pass rates for POS-BO, POS-ACCUM, SWG-PB and the `weinstein_setup` composition — the tool used to find and fix the catalyst blackouts. Read it when a catalyst stops firing: it shows exactly which gate is collapsing.
