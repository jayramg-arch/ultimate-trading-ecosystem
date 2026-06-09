# Commander Bull Screener v3.3 (Pure Price Action) — User & Trading Guide

> **Module Role:** The **primary bull-market discovery engine** of the Weinstein Commander suite. Where the Recovery Screener finds capitulation candidates, the Bull Screener finds the market's strongest breakout and momentum stocks. It implements all six Minervini/Weinstein catalysts from the Unified Ecosystem in a compact screener format — use it to scan your watchlist in TradingView, or batch-scan via `bull_screener.py` in the web app.
>
> **Current file:** `Commander_Bull_Screener_v3.2.pine` (renamed from `Commander_Screener_Beta_Edition_v2.9.pine`).

---

## 🆕 v3.3.1 (June 2026) — Honest "no-setup" trade levels

Small but important display fix. The `LEVELS` row used to print a `dClose × 0.95` (−5%) stop and mechanical 2R/3R targets **even when no catalyst was active** — a placeholder that looked like a real trade plan. It now prints **`P <price> · SL/T1/T2 — (no active setup)`** whenever `CATALYST = NONE`, so a generic round-number stop is never mistaken for a structural level. Full field reference in **§7 → 📋 TRADE LEVELS Row**.

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
- **POS-ACCUM Catalyst RE-ENABLED.** The v3.2 decision to disable POS-ACCUM was based on a 30-day forward window backtest, which is the wrong horizon for a Stage 1→2 accumulation setup designed for 6–8 month positional holds. It is now re-enabled (live).

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

## What's New in v3.x — Decision-Mode Architecture

The v3.x line aligns this Screener with the Dashboard's `v67.3.x` cross-tool architecture. Two architectural principles drive the changes:

1. **Dashboard owns the Mansfield RS engine.** This Screener now mirrors the Dashboard's canonical `f_calc_rs_logic` (dual-SMA: 52w level + 26w slope-Mansfield + 8w slope window + 4-bar momentum + 130-bar warm-up). The slope window default bumped 5 → 8 to match. New input `rsLevelLen` (default 52). See Dashboard guide §16.
2. **Each tool owns what's unique to it.** Rows that duplicated the Dashboard's display were removed from this Screener. The underlying computations are still performed (the catalyst engine consumes them); they just no longer occupy table real estate.

### v3.2 — Backtest Validation & Physical DB Sync (current)

- **POS-ACCUM Catalyst Re-enabled:** See Pure PA section above.
- **Physical 664-Symbol Sector Database:** Removed unreliable string-matching hacks. The Pine code now includes a hardcoded SQLite export block (`<DB_LOOKUP_START>`) guaranteeing 100% parity with the Python ecosystem.
- **JdK RRG Formula & Strike Parity:** The Mansfield slope computation was fully replaced by the JdK RS-Ratio model matched to Strike.Money, using a `+2` score for the LEADING quadrant only.

### v3.1 — Composite-merge pass

The table is now organised by the catalyst-validation workflow with composite cells replacing one-field-per-row clutter.

**Layout (~13 rows, was 18):**

```
TITLE + DATE                              (full-width)
── 🎯 SETUP VERDICT ──                    (header)
VERDICT compound: Catalyst · Signal · Alpha/Grade · Confluence · gates blocking
── ⚙️ POS-BO GATES X/9 [PRIME/WATCH/WEAK] ── (header with status pill)
G1 Stage 2/1     ✓  |  G2 Price > 200MA  ✓     (paired)
G3 Sector RS     ✗  |  G4 Sector S1/2    ✗     (paired)
G5 Trend Tpl     ✓  |  G6 Vol Accum      ✓     (paired)
G7 Fresh (40w)   ✗  |  G8 MA Squeeze     ✓     (paired)
G9 BB Squeeze    ✓  |                          (solo)
→ See Dashboard for: RS · Stage · Trend · Vol · Persona  (full-width footer)
── 📋 TRADE LEVELS ──                     (header)
LEVELS compound: P 1113 · SL 1057 (5%) · T1 1224 (2R) · T2 1280 (3R) · Sig —
── 🛠 HOW TO TRADE [status pill] ──       (header)
ENTRY     · SIZE
CONFIRM   · MANAGE
RISK      · KEY LVL
```

**Merger map** (every original datapoint preserved):

| Compound row | Encodes |
|---|---|
| `VERDICT` | Catalyst code · Signal (STRONG BUY/BUY/WATCH/WAIT) · Alpha + Grade · Confluence · blocking count |
| Paired gate row | Two coloured ✓/✗ gate cells side-by-side — each gate keeps its independent visual state |
| `LEVELS` | Price · SL with % distance · T1 (2R, ΓÜáRESIST if blocked) · T2 (3R) · Today's signal (BREAKOUT/PULLBACK/—) |

### Rows removed (Dashboard owns them — read them there)

`STAGE` · `RS N500` · `RS SECTOR` · `RRG QUAD` · `VOL SHELF` · `OBV TREND` · `VCP TIGHT` · `MINERVINI TT` · `REL VOLUME` · `DIST EMA20`

These are **still computed** (the catalyst engine + 9 gates consume them) — they just don't occupy a row in this panel any more. Cross-reference footer at the bottom-left points the reader to the Dashboard for them.

### Inherited from v2.7ΓÇôv2.9 (still active)

- **v2.7 Hunter sync.** `hunter_weekly_rsi_min` (default 60) and `hunter_daily_adx_min` (default 25). POS-BO requires `wRsiVal ΓëÑ 60 AND ADX ΓëÑ 25`.
- **v2.8 POS-ACCUM RSI cap.** `pos_accum_rsi_max` (default 50). POS-ACCUM suppressed when daily RSI > 50.
- **v2.9 Python-aligned `pyScore`.** Toggle `use_python_aligned_score` (default ON) overwrites displayed `score` with `pyScore` for cross-platform consistency.

### v3.0 (intermediate) — RS engine port + duplicate removal

Shipped 17 May 2026. Established the architectural-contract header, ported `f_calc_rs_logic` from the Dashboard, and stripped 10 duplicate rows. v3.2 is the display-compression follow-up.

---

## 1. What It Does

The Beta Screener evaluates each chart ticker across **six bullish catalysts** and generates:
- An **Alpha Score** (0ΓÇô100) for setup quality
- A **Confluence Score** (0ΓÇô6) counting how many catalyst gates are simultaneously active
- A **Catalyst ID** identifying the primary active catalyst
- A **Recommendation** (STRONG BUY / BUY / PULLBACK / WATCH / WAIT)
- A **detailed table panel** showing all 9 POS-BO gates and quality factors

---

## 2. The Six Catalysts

| ID | Code | Description | Style |
|---|---|---|---|
| 1 | **POS-AC** | OBV momentum breakout + institutional volume in a base | Positional |
| 2 | **POS-BO** | 9-gate Weinstein Stage 2 breakout above 21-day high | Positional |
| 3 | **SWG-PB** | EMA-20 pullback in Minervini Trend Template | Swing |
| 4 | **SWG-BO** | VCP/pivot breakout with anti-algo filter | Swing |
| 5 | **SWG-REV** | RSI(3) mean-reversion in Stage 1/2 with weekly RSI > 40 | Swing |
| 6 | **GAP-GO** | Gap-and-Go (ΓëÑ4% gap, ΓëÑ3├ù volume, intraday range ΓëÑ60%) | Swing |

---

## 3. Inputs — Field-by-Field

### Strategy & Benchmark Settings
| Input | Default | Explanation |
|---|---|---|
| **Weinstein SMA Length** | `30` | 30-week SMA — the canonical Weinstein MA. Do not change. |
| **30WMA Slope Lookback** | `4` | Weeks to measure 30W SMA slope direction. |
| **30WMA Slope Threshold** | `0.0005` | Minimum slope to register as Rising (not Flat). |
| **Benchmark 1 (N50)** | `NSE:NIFTY` | Nifty 50 for RS calculation 1. |
| **Benchmark 2 (N500)** | `NSE:CNX500` | Nifty 500 — the primary Mansfield RS benchmark. |
| **RS Slope Length** | `26` | Weeks for Mansfield RS calculation (6-month window). |
| **RS Slope Lookback** | `8` | Weeks for RS momentum direction. |
| **RS Slope Sensitivity** | `0.2` | Minimum ROC on ├ù100 scale to register as Rising/Declining. |

### Daily MA Settings
| Input | Default | Explanation |
|---|---|---|
| **50 DMA Length** | `50` | Core daily trend MA. |
| **150 DMA Length** | `150` | Mid-term trend — part of Minervini Trend Template. |
| **200 DMA Length** | `200` | Long-term trend — Stage 2 minimum. |
| **50DMA Slope Lookback** | `21` | Days to assess 50 DMA slope direction. |

### Mathematical Edges
| Input | Default | Explanation |
|---|---|---|
| **Macro Edge (Institutional Vol)** | `true` | Requires VWMA50 > SMA50 to allow STRONG BUY. |
| **Micro Edge (CPR/VWAP/Squeeze)** | `true` | Requires price > CPR + Monthly VWAP + squeeze for PULLBACK signals. |

### Technical Settings
| Input | Default | Explanation |
|---|---|---|
| **ATR Length** | `14` | Standard ATR for volatility and stop-loss calculations. |
| **Pivot Lookback Left/Right** | `2/2` | **Must match the Zigzag indicator settings.** |
| **VP Lookback Bars** | `100` | Volume Profile window for inline POC/VAH/VAL calculation. |

### Display
| Input | Default | Explanation |
|---|---|---|
| **Show Dashboard Table** | `true` | Toggles the main screener summary table |
| **Show Alpha Score Gauge** | `true` | Renders a visual 0ΓÇô100 gauge for the Alpha Score |
| **Show 9-Gate Status** | `true` | Shows the full POS-BO gate checklist (✓/✗ per gate) |
| **Show Trade Lines** | `true` | Draws Entry/T1/T2/SL horizontal lines when a catalyst fires |
| **Show Sector RS** | `true` | Adds the auto-detected sector RS row to the table |
| **Table Position** | `Top Right` | Placement of the screener table |

---

### v2.7ΓÇôv2.9 Inputs (NEW — Backtest-Locked)

These input groups appear in the script's settings panel and surface the v1 FINAL + v2 LOCK + v2.9 alignment thresholds. Defaults are backtest-verified — only change if you've re-run the ablation.

#### Hunter Scan — v1 FINAL (Locked 2026-05-08)
| Input | Default | Range | Why |
|---|---|---|---|
| **Hunter Weekly RSI Min** | `60` | 40ΓÇô80 | v1 FINAL (was 55 pre-tune). POS-BO requires `wRsiVal >= this`. Mirrors `chartink_replay.SCAN_PARAMS["hunter"]["weekly_rsi_min"]`. |
| **Hunter Daily ADX Min** | `25` | 10ΓÇô50 | v1 FINAL (was 20 pre-tune). POS-BO requires numeric ADX(14) ΓëÑ this. Mirrors `chartink_replay.SCAN_PARAMS["hunter"]["daily_adx_min"]`. |

#### v2 FINAL — Catalyst Filters (Locked 2026-05-10)
| Input | Default | Range | Why |
|---|---|---|---|
| **POS-ACCUM Daily RSI Max** | `50` | 30ΓÇô70 | v2 LOCKED. POS-ACCUM is suppressed when daily RSI > this. Mirrors `v2_fixes.V2_PARAMS["pos_accum_rsi_threshold"]`. Reason: late-stage POS-ACCUM at high RSI is a chase trap (HCLTECH-style failure documented in `BACKTEST_RESULTS_v2.docx` §6). |

#### v2.9 — Python-Aligned Score & Defensive Toggle
| Input | Default | Why |
|---|---|---|
| **Use Python-Aligned pyScore (recommended)** | `true` | When ON, the displayed `score` mirrors `bull_screener.calculate_score()` exactly. Turn OFF only if you want the legacy Pine-native composite (Stage+RS+slope+alpha_vs_bench+liq_sweep). |
| **Defensive Mode: Days_Since_Pivot Penalty** | `false` | Mirrors `v2_fixes.V2_FLAGS["days_since_pivot_penalty"]`. When ON, `pyScore -= 10` if bars since last `isBreakout` > `days_since_pivot_max`. Backtest evidence: **lifts hit-rate but truncates upside on filtered universe**. Use only in market drawdowns where hit-rate matters more than alpha. |
| **Days_Since_Pivot Max (bars)** | `30` | Threshold for the defensive penalty. |
| **Days_Since_Pivot Penalty Points** | `10` | Points subtracted from pyScore when defensive mode triggers. |

---

## 4. Two Scoring Systems — Alpha Score & pyScore (v2.9+)

The Beta Screener now exposes **two parallel scores**. Understand the difference:

### 4A. `alphaScore` — Daily Momentum Gate (UNCHANGED, v2.5+)

This is the gate that determines whether catalysts are allowed to fire. `alpha_ok = alphaScore >= 60`.

| Condition | Points |
|---|---|
| Close > EMA20 | +15 |
| Close > SMA50 | +15 |
| RSI(14) > 60 | +20 |
| RSI(14) 50ΓÇô60 | +10 |
| ADX > 20 with +DI > -DI | +10 |
| Green bar + volume > 1.5├ù avg | +20 |
| Green bar + volume > avg (but < 1.5├ù) | +10 |
| Distance to EMA20 < 5% | +20 |
| Distance to EMA20 5ΓÇô10% | +10 |
| Macro Edge active (VWMA50 > SMA50) | +10 |
| Macro Edge OFF AND volume < avg | ΓêÆ20 |

**Threshold:** Alpha ΓëÑ 60 required for any active signal. Alpha ΓëÑ 80 = STRONG BUY eligible.

### 4B. `pyScore` — Python-Aligned Composite (NEW, v2.9)

This is the displayed `score` in the dashboard table when `use_python_aligned_score = true` (default). It is a **byte-equivalent mirror of `bull_screener.calculate_score()`** so the Pine reading and the Python pipeline reading agree on the same stock.

| Component | Points | Notes |
|---|---|---|
| Catalyst tier — POS-BO / SWG-BO / GAP-GO | +30 | |
| Catalyst tier — SWG-REV | +20 | |
| Catalyst tier — SWG-PB | +10 | |
| Catalyst tier — POS-ACCUM | +15 | (already gated by v2.8 `dailyRsi <= 50`) |
| Stage 2 (UP) confirmation | +10 | |
| Mansfield RS > 0 | +10 | (cumulative — adds to next tier) |
| Mansfield RS ΓëÑ 10 | +10 | (additional, on top of above) |
| Mansfield 4w momentum > 0 | +5 | |
| RRG quadrant LEADING | +5 | |
| RRG quadrant WEAKENING | ΓêÆ10 | |
| RRG quadrant LAGGING | ΓêÆ5 | |
| Volume tier — relVol ΓëÑ 2.0 | +15 | |
| Volume tier — relVol ΓëÑ 1.5 | +10 | |
| Volume tier — relVol ΓëÑ 1.0 | +5 | |
| Sector strength (Stage 2 sector) | +5 | approximation via `secStageNum` |
| Sector strength (Stage 4 sector) | ΓêÆ5 | approximation via `secStageNum` |
| Trend template pass | +10 | |
| Distance off 52W high — Γëñ 5% | +10 | |
| Distance off 52W high — Γëñ 10% | +7 | |
| Distance off 52W high — Γëñ 15% | +5 | |
| Distance off 52W high — Γëñ 25% | +3 | |
| **Defensive penalty** (off by default) | ΓêÆ10 | If `days_since_pivot_penalty_on=true` AND bars since last `isBreakout` > `days_since_pivot_max` |

**Clamped to [0, 100].**

### 4C. Which Score Should I Use?

- **`alphaScore`** is fixed and always governs whether catalysts fire (the `alpha_ok >= 60` gate).
- **`pyScore`** is what the dashboard displays as the headline "Score" (when the toggle is ON, which is the default). Use it for **picking between candidates** — it captures composite quality the way the Python backtest does.
- If you want the legacy Pine-native composite (Stage25 + RS15 + slope15 + alpha_q3+_h1 + liq_sweep), turn `use_python_aligned_score` OFF.

---

## 5. The POS-BO 9-Gate Checklist

For POS-BO specifically, all 9 gates must pass:

| Gate | Condition | Why |
|---|---|---|
| 1 | Weekly Stage 2 (UP) or Stage 1 (BASE) | Only trade in the right macro stage |
| 2 | Close > 200 DMA | Minervini Trend Template baseline |
| 3 | Sector RS not LAGGING | Don't buy a leader in a sinking sector |
| 4 | Sector Stage 1 or 2 | Sector-level Weinstein alignment |
| 5 | Trend Template: within 25% of ATH AND >30% above 52W low | Growth stock prerequisite |
| 6 | vol_acc_ok: ΓëÑ6/20 bars = green + upper 60% + vol > avg | Institutional accumulation evidence |
| 7 | stage2_fresh_ok: wStageWks Γëñ 26 | Fresh Stage 2 only — not late-cycle |
| 8 | ma_sqz_ok: SMA20 and SMA50 within 5% | Coiling — compression before breakout |
| 9 | bb_sqz_ok: BB width < BB width SMA120 | Bollinger squeeze — confirmed compression |

The 9-gate panel shows ✓ or ✗ for each gate. A stock showing 8/9 gates is a high-priority watch even if POS-BO hasn't fired.

---

## 6. Catalyst-Specific Logic

### POS-AC (OBV Accumulation)
```
obv_breakout: OBV > highest OBV of last 20 bars (OBV making new highs)
AND institutional_vol: volume > 2├ù avg on an OBV-positive bar
AND price_lag: close < highest_high_63_bars ├ù 0.95  (price hasn't run yet)
AND alpha_ok: score ΓëÑ 60
→ Identifies smart-money accumulation before the price breakout
```

### POS-BO (All 9 gates +)
```
All 9 gates above PLUS:
close > highest_high_21[1]  (21-day breakout)
AND close in top 25% of today's range
AND volume ΓëÑ 1.25├ù avg
AND alpha_ok
→ The full Weinstein Stage 2 breakout confirmation
```

### SWG-PB (Minervini EMA-20 Pullback)
```
Trend Template active: 50 DMA > 150 DMA > 200 DMA
AND price within ┬▒1.5% of EMA20
AND RSI(14) in 40ΓÇô60 zone
AND weekly RSI > 60
AND volume < 70% of avg  (Volume Dry-Up = VDU)
AND close < prior close  (actual pullback, not chop)
AND Micro Edge active (CPR + Monthly VWAP + squeeze)
AND alpha_ok
```

### SWG-BO (VCP Breakout)
```
VCP compression: ATR14/close < VCP ATR threshold  (tight price action)
AND close > highest_15_bar_high[1]  (15-day pivot breakout)
AND anti_algo_ok: bar range < 2├ù ATR (not a fakeout extension bar)
AND volume ΓëÑ 1.5├ù avg
AND alpha_ok
```

The **anti-algo filter** (`anti_algo_ok`) is unique to v2.6 — it prevents entries on abnormally wide bars that are often algorithmic stop-hunts rather than genuine breakouts.

### SWG-REV (RSI(3) Mean-Reversion)
```
RSI(3) < 20  (short-term oversold)
AND stage in (Stage1, Stage2)  (not in a downtrend)
AND weekly RSI > 40  (no genuine weekly weakness)
AND close > SMA50  (above medium-term trend)
AND alpha_ok
→ Captures short-term pullbacks in healthy uptrends
```

### GAP-GO (Gap-and-Go)
```
gap_size: (open - close[1]) / close[1] ├ù 100 ΓëÑ 4%
AND gap_vol: volume ΓëÑ 3├ù avg50  (institutional gap)
AND intraday_strength: close ΓëÑ low + (high - low) ├ù 0.60
AND alpha_ok
→ Captures strong morning gaps that hold and close near the high
```

---

## 7. The Screener Table

### Left Panel: Setup Summary
| Row | Content |
|---|---|
| **CATALYST** | Active catalyst code (POS-BO / SWG-PB / etc.) |
| **ALPHA** | 0ΓÇô100 score with stars (ΓÿàΓÿàΓÿàΓÿàΓÿà) |
| **GRADE** | A+/A/B/C/D letter grade |
| **STAGE** | Weekly Weinstein Stage + weeks in stage |
| **PERSONA** | AUTO-DETECTED persona: "Growth Leader" / "Momentum Breakout" / "Recovery Play" / "Value Base" |
| **STYLE** | Positional / Swing / Both |
| **RECOMMENDATION** | STRONG BUY / BUY / PULLBACK / WATCH / WAIT |

### Right Panel: Quality Factors
| Row | Content |
|---|---|
| **RS N50** | Mansfield RS vs Nifty 50 + RRG Quadrant |
| **RS N500** | Mansfield RS vs Nifty 500 + RRG Quadrant |
| **RS SECTOR** | RS vs auto-detected sector + quadrant |
| **VOL SHELF** | VWMA50 > SMA50? (Macro Edge) |
| **VCP TIGHT** | VCP compression active? |
| **OBV TREND** | OBV in uptrend? |
| **ATR%** | Current ATR/Close ├ù 100 (volatility %) |

### 📋 TRADE LEVELS Row (compound)
The stop and targets are no longer four separate rows — they are consolidated into **one compound `LEVELS` row** under the `── 📋 TRADE LEVELS ──` header. The field-by-field content depends on whether a catalyst is currently active.

**When a catalyst is firing (`CATALYST ≠ NONE`):**

```
P 1234.50 · SL 1180.20 (4.4%) · T1 1342.90 (2R) ⚠RESIST · T2 1451.30 (3R) · Sig BREAKOUT
```

| Field | Meaning | Possible values |
|---|---|---|
| **P** | Current daily close (your reference entry price) | any price, `#.00` |
| **SL** | Structural stop-loss for the active catalyst (catalyst-aware ATR/structural anchor) | price `#.00`, with `(x.x%)` = stop distance below P |
| **T1** | First target = entry + 2R | price `#.00 (2R)`; appends **`⚠RESIST`** when a supply/resistance level sits between entry and T1 (target may stall) |
| **T2** | Second target = entry + 3R | price `#.00 (3R)` |
| **Sig** | What fired on the *current* bar | `BREAKOUT`, `PULLBACK`, `BREAKOUT PULLBACK` (both), or `—` (catalyst is in HOLD window, nothing fresh today) |

**When NO catalyst is active (`CATALYST = NONE`) — v3.3.1 change:**

```
P 1234.50 · SL/T1/T2 — (no active setup) · Sig —
```

> **Why this changed (v3.3.1, June 2026):** previously the row always printed numbers — but with no catalyst, the "SL" was just a generic `dClose × 0.95` (−5%) placeholder and T1/T2 were mechanical 2R/3R off that fake stop. That looked like a real, tradeable plan when it was nothing of the sort. The row now prints **`SL/T1/T2 — (no active setup)`** so you never mistake a placeholder for a structural level. **Only act on the numeric LEVELS line when `CATALYST` shows a real code** (POS-BO / POS-AC / SWG-* / GAP-GO). The `VERDICT` row directly above also stays neutral-coloured in this state.

### Gate Panel (POS-BO only)
Shows ✓ or ✗ for all 9 gates with a pass-count score (e.g., 7/9 gates).

> **CSV limitation:** The 9-gate checklist is **not exported as individual columns** in the CSV file. Gates 2 (Close > 200 DMA), 6 (vol_acc_ok), 8 (ma_sqz_ok), and 9 (bb_sqz_ok) have no dedicated CSV column — they are embedded in compound fields. Use the CSV proxy columns below and open the TradingView chart to see the full ✓/✗ breakdown for any POS-BO candidate:
>
> | Gate | CSV Proxy | Column |
> |---|---|---|
> | 1 — Stage | `Stage` | col 7 |
> | 2 — Close > 200 DMA | Embedded in `Minervini Trend Template` | col 18 |
> | 3 — Sector RS | `Sector RS Value` + `RRG Quad` | cols 20ΓÇô21 |
> | 4 — Sector Stage | `Sector Stage Gate` | col 32 |
> | 5 — Trend Template | `Minervini Trend Template` | col 18 |
> | 6 — vol_acc_ok | `Vol Shelf` + `OBV Trend Rising` (partial) | cols 22, 29 |
> | 7 — stage2_fresh_ok | `Stage Duration (Weeks)` Γëñ 26 | col 31 |
> | 8 — ma_sqz_ok | `VCP Tight` (partial) | col 30 |
> | 9 — bb_sqz_ok | `VCP Tight` (partial) | col 30 |
>
> For CSV-only screening, use `Confluence` (col 6) as the POS-BO gate proxy: a `Catalyst=2` stock with `Confluence ΓëÑ 5` has nearly all 9 gates passing.

---

## 8. The SMC Liquidity Sweep Catalyst (+20 Alpha Points)

New in v2.6: when a **Bullish Liquidity Sweep** is detected (price wicks below 5-day low, then closes above it AND above the 50 DMA, with volume > 1.5├ù avg), the Alpha Score receives a bonus +20 points. This integrates SMC Zones v1.0 logic directly into the screener's quality scoring.

```
liq_sweep = dLow5 < dMA50 and dClose > dMA50 and dVol > avg * 1.5
→ if true: alpha_score += 20 (capped at 100)
```

---

## 9. Persona System

The Screener auto-classifies each setup into a persona based on the combined profile:

| Persona | Stage | Catalyst | RS | Alpha |
|---|---|---|---|---|
| **Growth Leader** | 2 (Γëñ26 wks) | POS-BO | LEADING | ΓëÑ80 |
| **Momentum Breakout** | 2 | SWG-BO or SWG-PB | ΓëÑ0 | ΓëÑ60 |
| **Recovery Play** | 1 or early-2 | Any | ΓëÑΓêÆ0.5 | ΓëÑ40 |
| **Value Base** | 1 | POS-AC | ΓëÑΓêÆ1 | ΓëÑ40 |
| **Speculative** | Any | SWG-REV or GAP-GO | Any | ΓëÑ60 |
| **Avoid** | 3/4 | None or negative | LAGGING | <40 |

---

## 10. Ecosystem Integration

| Module | Connection |
|---|---|
| **Unified Ecosystem v2.2** | All 6 catalysts, Alpha Score, and 9-gate check are exact mirrors — Screener finds candidates, Unified Ecosystem manages the trade |
| **Dashboard v67.0** | Alpha Score, Catalyst, Persona, Recommendation, and Sector RS are duplicated inline on the Dashboard |
| **Bull Screener (Python)** | `bull_screener.py` is the batch Python version of this indicator — all 30 output columns mirror the Screener's table |
| **Risk Allocator v1.0** | After confirming a signal here, feed the Screener's `STOP SL` into the Allocator for position sizing |
| **SMC Zones v1.0** | The Liquidity Sweep bonus directly integrates SMC logic |
| **Volume Profile v1.0** | VP levels (POC, VAH, VAL) are shown in the Trade Lines section when `Show Trade Lines = true` |

---

## 11. Daily Workflow with the Beta Screener

### Pre-Market
1. Scan your watchlist via TradingView's Screener (filter: `catalyst_id > 0` AND `alpha_score ΓëÑ 60`)
2. Sort by Alpha Score descending → top 10 candidates
3. For each: verify on Dashboard that Stage 2, RS = LEADING, VOL SHELF = ✓
4. Check the 9-gate panel for POS-BO candidates — aim for ΓëÑ7/9

### Intraday (After Open)
5. GAP-GO only fires after open — run a fresh scan at 9:20 AM (post-gap stabilisation)
6. SWG-PB opportunities arise as strong stocks pull back — check EMA proximity row
7. For SWG-BO: only act if anti-algo filter passes AND volume has expanded by 10:30 AM

### Post-Market
8. Review any missed signals — note tickers that fired but were not on your watchlist for future monitoring

---

## 12. Version History — v2.5 → v2.9

| Feature | v2.5 | v2.6 | v2.7 (8 May) | v2.8 (10 May) | v2.9 (10 May) |
|---|---|---|---|---|---|
| Anti-Algo Filter (SWG-BO) | Introduced | Refined | unchanged | unchanged | unchanged |
| SMC Liquidity Sweep bonus | +20 Alpha | Capped at 100 + log | unchanged | unchanged | unchanged |
| Persona System | 6 personas | unchanged | unchanged | unchanged | unchanged |
| Dashboard Reference | v65.0 | v67.0 | v67.0 | v67.0 | v67.0 |
| Ecosystem Reference | Minervini v4.53 | Unified v2.2 | Unified v2.2 | Unified v2.2 | **Unified v2.3** |
| Hunter (POS-BO) gate | structural only | structural only | **+ wRSI ΓëÑ 60 + numeric ADX ΓëÑ 25** | unchanged | unchanged |
| `f_calc_adx_bool` | bool only | bool only | **renamed `f_calc_adx`, returns [bool, float]** | unchanged | unchanged |
| POS-ACCUM gate | OBV+VCP+weinstein | unchanged | unchanged | **+ dailyRsi Γëñ 50 (v2 LOCK)** | unchanged |
| Score formula | Pine-native composite | unchanged | unchanged | unchanged | **+ pyScore (mirrors `bull_screener.calculate_score`)** |
| `use_python_aligned_score` | n/a | n/a | n/a | n/a | **NEW (default ON)** |
| `days_since_pivot_penalty_on` | n/a | n/a | n/a | n/a | **NEW (default OFF, defensive toggle)** |
| Filename | `_v2.5.pine` | `_v2.6.pine` | `_v2.6.pine` (in-file v2.7) | `_v2.6.pine` (in-file v2.8) | **`_v2.9.pine`** |

**Backtest evidence:** v2.7 + v2.8 promotion verdict from 12-anchor walk-forward ├ù 2 universes (raw Nifty500 + filtered Chartink+conviction). Only `pos_accum_rsi_nullout` cleared the cross-universe verification rule (raw +0.14pp ╬▒ / filtered +0.26pp ╬▒, hit-rate held both). Full evidence in `BACKTEST_RESULTS_v2.docx`.

---

## 13. CSV Export — Field-by-Field Reference & Trading Use

When you click **Export** in TradingView's Pine Screener panel, the screener writes a CSV (e.g. `pinescreener_Commander_Screener_Beta_Edition_v2_6_<date>_<hash>.csv`) with **32 columns**. Many fields are encoded as integers because the Pine Screener can only emit numeric values — the legend below decodes each one and tells you exactly how to use it.

### 13.1 Column-by-Column Legend

| # | CSV Column | Type | Decoded Meaning | How to Use It |
|---|---|---|---|---|
| 1 | `Symbol` | text | Ticker (e.g. `APARINDS`) | Primary key. Sort/filter your other tools (Risk Allocator, Strategy v4.53) by this. |
| 2 | `Description` | text | Full company name | Sanity check the ticker is what you think (avoid demerged/renamed tickers). |
| 3 | `Alpha Score` | 0ΓÇô100 | Setup quality score | **Mandatory gate ΓëÑ60**. ΓëÑ80 = STRONG BUY eligible. Never enter <60. |
| 4 | `Dashboard Quality Score (0-100)` | 0ΓÇô100 | Composite from Dashboard v67.0 (RS, vol, trend, breadth) | Tie-breaker when two stocks have equal Alpha. Higher Dashboard score = healthier macro context. |
| 5 | `Alpha Stars (0-5 Γÿà)` | 0ΓÇô5 | `floor(Alpha/20)` | Quick visual rank. 4Γÿà+ = primary watchlist. |
| 6 | `Confluence (0-6 Stars)` | 0ΓÇô6 | Number of catalyst gates simultaneously firing | ΓëÑ3 = unusually strong setup. **But ΓëÑ3 alone is not entry** — confirm Stage and RS first (see §13 mistake #4). |
| 7 | `Stage` | float | `1`=Base, `2.1`=Stage 2 Up, `3`=Top, `4`=Downtrend | **Only trade `1` or `2.1`**. Skip every row with `3` or `4`. |
| 8 | `Persona` | 0ΓÇô5 | `5`=Growth Leader, `4`=Momentum, `3`=Turnaround, `2`=Volatile, `1`=Extended, `0`=Lagging | Match persona to your style. Positional traders want `5/4`. Avoid `0` regardless of Alpha. |
| 9 | `Style` | 0ΓÇô3 | `3`=Both, `2`=Swing, `1`=Positional, `0`=Wait | Filters out setups that don't match your holding period. |
| 10 | `Catalyst` | 0ΓÇô6 | `1`=POS-AC, `2`=POS-BO, `3`=SWG-PB, `4`=SWG-BO, `5`=SWG-REV, `6`=GAP-GO, `0`=none | Tells you which playbook section (§6) to follow for this row. `0` = no live signal — use as watchlist only. |
| 11 | `Recommended SL Price` | price | Calculated stop-loss | **Feed directly into Risk Allocator v1.0 → SL field**. Don't tighten or widen without re-running Allocator. |
| 12 | `Distance to SL (%)` | % | (Price ΓêÆ SL) / Price ├ù 100 | Risk per share. Reject anything > your max-risk% (typically 7ΓÇô10%). |
| 13 | `Target 1 (2.0R)` | price | First profit target at 2R | Book partial (typically 50%) here. Mirrors Strategy v4.53 T1 logic. |
| 14 | `Target 2 (3.0R)` | price | Second profit target at 3R | Trail remaining position. After T2 hit, switch to 21 EMA / 50 SMA trail. |
| 15 | `Warn: T1 Hits Resistance` | 0/1 | `1` = T1 lands inside a known resistance zone (PDH / VAH / weekly high) | If `1`, **reduce T1 to 1.5R** or scale out earlier — full T1 may not be reached. |
| 16 | `Signal: True Breakout` | 0/1 | `1` = bar closed above pivot with volume + range confirmation | Use as the **fire trigger** for POS-BO / SWG-BO entries. Don't enter on `0` even if Catalyst > 0 (means catalyst flagged but bar hasn't confirmed yet). |
| 17 | `Signal: Pullback Hit` | 0/1 | `1` = price tagged EMA20 in a Trend-Template stock | Use as **fire trigger** for SWG-PB. Combine with row 16=0 (no breakout) and row 9 in `2/3` for a clean pullback entry. |
| 18 | `Minervini Trend Template (1=Active)` | 0/1 | `1` = 50DMA > 150DMA > 200DMA, price > all three, within 25% of 52W high, > 30% above 52W low | **Hard requirement for SWG-PB**. Optional but strongly preferred for POS-BO. Reject `0` on swing entries. |
| 19 | `RS Value (vs Nifty 500)` | float (├ù100) | Mansfield RS — positive = leading the index, negative = lagging | **Filter ΓëÑ 0** for any entry. ΓëÑ 10 = LEADING. Γëñ ΓêÆ5 = LAGGING (skip). |
| 20 | `Sector RS Value` | float (├ù100) | Stock's RS vs auto-detected sector index | Catches stocks leading the broader market but lagging their sector (rotation risk). Want both row 19 and row 20 ΓëÑ 0. |
| 21 | `RRG Quad` | 1ΓÇô4 | `1`=Leading, `2`=Weakening, `3`=Lagging, `4`=Improving | **Best entries**: Quad `1` or `4` (Leading or Improving). Avoid `2`/`3` for new positions. |
| 22 | `Vol Shelf` | 0/1 | `1` = VWMA50 > SMA50 (Macro Edge / institutional accumulation) | **Required for STRONG BUY tier**. Without it, downgrade your size by 50%. |
| 23 | `Daily Trend` | ┬▒1 | `1`=daily uptrend, `ΓêÆ1`=daily downtrend | Don't fight the daily. `ΓêÆ1` + Catalyst > 0 = wait for daily to flip. |
| 24 | `Weekly Trend` | ┬▒1 | `1`=weekly uptrend, `ΓêÆ1`=weekly downtrend | Hard filter for positional trades. Reject `ΓêÆ1`. |
| 25 | `Current Price` | price | Last close at scan time | Use as Entry reference — but place actual order using Strategy v4.53 entry logic (e.g. above breakout high). |
| 26 | `Distance to 20 EMA (%)` | % | (Price ΓêÆ EMA20) / EMA20 ├ù 100 | **<5%** = optimal swing entry zone. **5ΓÇô10%** = neutral. **>10%** = extended, wait for pullback. |
| 27 | `Relative Volume (x-avg)` | float | Today's volume / 20-day avg | ΓëÑ1.25├ù = healthy. ΓëÑ1.5├ù = institutional participation. <0.7├ù = no commitment, downgrade. |
| 28 | `Anti-Algo SWG-BO Gate` | 0/1 | `1` = bar range < 2├ù ATR (not a stop-hunt wide bar) | **Required for SWG-BO entries**. If `0`, wait for next bar's confirmation before entering. |
| 29 | `OBV Trend Rising` | 0/1 | `1` = OBV in uptrend (accumulation) | Confirms smart-money flow. Want `1` on POS-AC and POS-BO. `0` on a "breakout" = suspicious. |
| 30 | `VCP Tight` | 0/1 | `1` = ATR14/Close below VCP threshold (compression present) | **Required for SWG-BO**. Adds quality to POS-BO. Without it, breakouts often fail. |
| 31 | `Stage Duration (Weeks)` | int | Weeks the stock has been in current stage | **Stage 2 sweet spot: 1ΓÇô26 weeks**. >26 wks in Stage 2 = late-cycle, downgrade size. >40 wks = avoid new entries. |
| 32 | `Sector Stage Gate` | 0/1 | `1` = sector index is itself in Stage 1 or 2 | **Required gate #4 of POS-BO**. `0` = you'd be buying a leader in a falling sector — skip. |

### 13.2 Filter Recipes (Excel / Python / Sheets)

Apply these filter stacks to the CSV to extract specific trade lists.

**A. STRONG BUY universe (highest conviction):**
```
Alpha Score >= 80
AND Confluence >= 3
AND Stage in (1, 2.1)
AND Persona in (4, 5)
AND RS Value >= 10
AND Sector RS Value >= 0
AND Vol Shelf = 1
AND Weekly Trend = 1
AND Stage Duration <= 26
```

**B. POS-BO breakout entries (today):**
```
Catalyst = 2
AND Signal: True Breakout = 1
AND Alpha Score >= 70
AND Sector Stage Gate = 1
AND Minervini Trend Template = 1
AND OBV Trend Rising = 1
```

**C. SWG-PB pullback entries:**
```
Catalyst = 3
AND Signal: Pullback Hit = 1
AND Minervini Trend Template = 1
AND Distance to 20 EMA (%) <= 5
AND Relative Volume <= 0.7
AND Weekly Trend = 1
```

**D. SWG-BO with anti-algo confirmation:**
```
Catalyst = 4
AND Anti-Algo SWG-BO Gate = 1
AND VCP Tight = 1
AND Relative Volume >= 1.5
AND Alpha Score >= 70
```

**E. Watchlist (no live signal, but setting up):**
```
Catalyst = 0
AND Alpha Score >= 60
AND Stage in (1, 2.1)
AND Vol Shelf = 1
AND Persona in (3, 4, 5)
AND RS Value >= 0
```
These are the stocks that haven't fired today but have all quality factors aligned — monitor for next-day breakouts.

### 13.3 CSV → Trade Workflow

1. **Open CSV in Excel/Sheets** → freeze row 1 → enable filters on all columns.
2. **Apply Filter A** (STRONG BUY universe) → sort by `Alpha Score` desc → take top 10.
3. **For each top-10 ticker**, look up the row's `Catalyst` (col 10) and apply the matching catalyst filter (B/C/D) to confirm the signal is live today.
4. **Reject** any row where `Distance to SL (%)` > your max-risk threshold (col 12).
5. **Reject** any row where `Warn: T1 Hits Resistance` = 1 (col 15) unless you size for 1.5R instead of 2R.
6. **Pass surviving rows to Risk Allocator v1.0**: feed `Current Price` (col 25) as Entry, `Recommended SL Price` (col 11) as SL, `Target 1` (col 13) as T1.
7. **Load on Unified Ecosystem v2.2** for actual order placement and trade management — the ecosystem handles entry triggers, exits, and sizing automatically.
8. **Save the CSV** with date stamp — over time, build a hit-rate database: which catalysts/personas/RS quadrants actually deliver T1/T2 in your trading.

### 13.4 Common CSV Pitfalls

- **The CSV is a snapshot at scan time, not real-time.** `Current Price` may have moved 1ΓÇô2% by the time you open the file. Always re-quote on TradingView before placing orders.
- **`Catalyst = 0` does not mean "skip"** — it means no signal *today*. Combined with high Alpha + good Stage, these are tomorrow's candidates.
- **`Signal: True Breakout = 0` with `Catalyst = 2`** means the breakout setup exists but the confirming close hasn't happened. Don't front-run — wait for col 16 to flip to 1.
- **`RS Value` is on the ├ù100 Mansfield scale**, not raw price ratio. A value of `15` means 15 percentage points outperformance over the lookback, not 15├ù the index.
- **`Stage = 2.1`** means Stage 2 Up. The decimal distinguishes from Stage 2 sub-states in the Strategy ecosystem — treat `2.x` as Stage 2 for filtering.
- **Two columns can show the same RS Value** (rows 19 and 20 may match) when the Sector index = Nifty 500, e.g. for sector-agnostic tickers. Not a bug.

---

## 14. Common Mistakes

1. **Acting on any catalyst without Alpha ΓëÑ 60** — The score gate is mandatory. A VCP breakout with score 45 has 3+ quality factors missing — the setup is incomplete.
2. **Ignoring the Persona** — An "Avoid" persona means the macro backdrop is wrong. Never enter Avoid-classified stocks regardless of how the chart pattern looks.
3. **Using GAP-GO intraday** — The gap catalyst requires the stock to hold its intraday gains through the first 30 minutes. Entering at the open is speculation, not system trading.
4. **Treating Confluence Score ΓëÑ 3 as automatic entry** — Confluence means multiple signals agree, but they could all be confirming a bad macro setup. Always check STAGE and RS first.
5. **Not verifying the anti-algo filter** — SWG-BO entries on wide bars frequently fail. If the anti-algo filter shows ✗ even though price broke out, wait for the next bar to confirm the breakout is genuine.

---

## 15. May 2026 Update — Catalyst-Aware SL Discipline + Roll-back of Premature Catalyst Removals

This section documents the May 2026 changes to `bull_screener.py` (v1.10, v1.11) and `Commander_Bull_Screener_v3.2.pine` (v3.3) made during a campaign to improve the validation framework. Read this if the picks you see today differ from what the v1.8 / v3.2 (pre-21-May) versions produced.

### 15.1 What Changed

| File | Version | Change |
|---|---|---|
| `bull_screener.py` | v1.10 | **POS-ACCUM RE-ENABLED**. The v1.8 "disabled" guard was based on a 30-day forward-window backtest, which is the wrong horizon for a Stage 1→2 accumulation setup (designed for 6-8 month positional holds per CLAUDE.md). |
| `bull_screener.py` | v1.11 | **Catalyst-aware SL multiplier**: POS=4.0├ù daily ATR, WYC=3.5├ù, REV=2.5├ù, SWG=1.5├ù (unchanged). Previously all catalysts used 1.5├ù — a positional trade with a swing-sized SL gets knocked out by routine pullbacks within the first 2 weeks. |
| `Commander_Bull_Screener_v3.2.pine` | v3.3 | POS-ACCUM trigger re-enabled (catalyst_id := 1 now assignable). |

### 15.2 Catalyst-Aware SL Discipline — How It Works

Position size is unchanged (still 1% of capital per trade). The SL distance now scales with the trade's design horizon:

| Catalyst | ATR mult | Typical SL distance | Why |
|---|---|---|---|
| `POS-BO`, `POS-ACCUM` | **4.0├ù** | ~6-12% | 4-6 month positional hold needs room for normal volatility |
| `WYC-*` (Wyckoff base) | **3.5├ù** | ~5-10% | Multi-month base structure |
| `REV-CB`, `REV-RS`, `REV-EARLY` | **2.5├ù** | ~4-7% | 90-day recovery / mean-reversion horizon |
| `SWG-BO`, `SWG-PB`, `SWG-GAP`, `SWG-REV` | **1.5├ù** | ~2-4% | Swing — unchanged |

**Practical effect:** because SL distance is wider for positional setups, the **position size for a POS-* trade is now smaller** at the 1% risk-per-trade rule. This is correct discipline — wider stops with smaller size, not the previous fragile-position approach.

### 15.3 What You'll Notice in Today's CSVs

- **POS-ACCUM picks reappear** after being absent since 2026-05-20. Expect 1-5 extra picks per Nifty 500 scan.
- **POS-* picks have wider `SL_pct`** (was ~3%, now ~6-12%). This is intentional — see §15.2.
- **`T1_pct` and `T2_pct` for POS-* are also wider** because targets are computed as `R ├ù SL_distance` (5R / 10R for POS-*). The Risk:Reward ratio is preserved.
- **Recovery screener now also has a wider SL fallback** (`recovery_screener.py` v1.6: safety floor widened from 1.5├ù → 2.5├ù daily ATR for REV-*).

### 15.4 Recommended Workflow Adjustment

For POS-* picks, **manually verify the SL price is structurally sound** before placing the order. The 4├ù ATR rule is a fallback when no structural anchor is available; in practice, the natural Weinstein SL would be:

- POS-BO: 2-3% below the breakout pivot
- POS-ACCUM: below the accumulation base low (often slightly tighter than the 4├ùATR fallback)

If your structural SL is *tighter* than the 4├ùATR fallback, use the structural SL (and reduce position size to keep 1% risk). If the structural SL would put SL above current close, fall back to the 4├ùATR rule.

### 15.5 What Was Rolled Back

These v1.8 / v3.2 changes are NO LONGER in effect:

- Γ¥î ~~POS-ACCUM disabled~~ — RESTORED to live trading
- Γ¥î ~~REV-* removed from recovery screener~~ — RESTORED (Wyckoff added alongside, not as replacement; see `09_Recovery_Screener_v1_7_Guide.md` §11)
- Γ¥î ~~"Bull screener has no edge" verdict~~ — withdrawn; was based on wrong-horizon measurement

### 15.6 Live Trading vs Backtest Numbers

If you read older backtest reports referencing `+14.81% cumulative alpha` (v1.8 verdict) or `ΓêÆ2.23 Sharpe` (Week-3 buggy run) — both were measurement artifacts and should be disregarded. The current honest baseline on properly-windowed validation (n500 ├ù 18mo, catalyst-aware horizons) is:

- Mean matched alpha per trade: **+0.90%**
- Cumulative alpha (18mo): **+8.84%**
- Bootstrap CI95 on mean alpha: **[ΓêÆ1.66%, +3.63%]** (straddles zero — small sample, not statistical confirmation yet)
- Probability of positive true alpha: **~74%**

These are point-in-time numbers, not a target. The CI will tighten with more anchors.
